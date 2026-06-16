"""Silver runner — apply column rules, parse JSON, standardize, geocode.

Driven entirely by the registry entry for one source. Same code path for
facilities, pincode, NFHS-5; behavior changes via YAML.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType

from .expectations import run_expectations
from .registry import Source, load_registry
from .transforms import apply_transforms


def _safe_cast(col, target_type: str):  # noqa: ANN001
    """Cast without aborting on malformed numeric strings like 'NA'."""
    normalized = F.trim(F.lower(col.cast("string")))
    if target_type == "int":
        valid = normalized.rlike(r"^-?\d+$")
        within_int_range = valid & (F.length(F.regexp_replace(normalized, "^-", "")) <= 9)
        return F.when(within_int_range, col.cast("int")).otherwise(F.lit(None).cast("int"))
    if target_type == "double":
        valid = normalized.rlike(r"^-?(\d+(\.\d+)?|\.\d+)$")
        return F.when(valid, col.cast("double")).otherwise(F.lit(None).cast("double"))
    return col.cast(target_type)


def _ensure_state_alias_reference(spark: SparkSession, target_catalog: str) -> str:
    from pathlib import Path

    sql_path = (
        Path(__file__).resolve().parents[2]
        / "sql" / "reference" / "state_aliases.sql"
    )
    sql_text = sql_path.read_text(encoding="utf-8").replace("__CATALOG__", target_catalog)
    for statement in sql_text.split(";"):
        stmt = statement.strip()
        if stmt:
            spark.sql(stmt)
    return f"{target_catalog}.bronze.state_alias_reference"


def _parse_json_columns(df: DataFrame, cols: list[str]) -> DataFrame:
    """Convert JSON-encoded string columns to ARRAY<STRING>.

    Source data uses Python-list-as-string ('["a","b"]') and dirty 'null'
    strings; from_json with permissive mode tolerates the messes we saw.
    """
    for c in cols:
        if c in df.columns:
            df = df.withColumn(
                c,
                F.from_json(F.col(c), ArrayType(StringType()), {"mode": "PERMISSIVE"}),
            )
    return df


def _apply_column_rules(df: DataFrame, source: Source) -> DataFrame:
    """Project + rename + cast + transform per registry."""
    if source.passthrough_all:
        # Keep every source column; only rename/cast the ones explicitly listed.
        rename_map = {c.source: c for c in source.columns}
        out = df
        for src_col, rule in rename_map.items():
            if src_col in df.columns:
                col = F.col(src_col)
                if rule.transforms:
                    col = apply_transforms(col, rule.transforms)
                out = out.withColumn(rule.target, _safe_cast(col, rule.cast))
                if rule.target != src_col:
                    out = out.drop(src_col)
        return out

    # Strict projection — only declared columns survive.
    selects = []
    for rule in source.columns:
        if rule.source not in df.columns:
            # Column missing upstream — emit NULL so downstream schema is stable.
            selects.append(F.lit(None).cast(rule.cast).alias(rule.target))
            continue
        col = F.col(rule.source)
        if rule.transforms:
            col = apply_transforms(col, rule.transforms)
        selects.append(_safe_cast(col, rule.cast).alias(rule.target))
    return df.select(*selects)


def _standardize(df: DataFrame, spark: SparkSession, source: Source) -> DataFrame:
    """Resolve metadata-described lookup joins (state aliases, pincode geocode)."""
    for rule in source.standardize:
        ref = rule["reference"]
        if ref == "india_state_alias":
            alias_table = _ensure_state_alias_reference(spark, source.target_catalog)
            alias = spark.read.table(alias_table).select(
                F.lower(F.trim("alias")).alias("_alias"),
                "canonical_state",
            )
            df = (
                df.alias("d")
                .join(alias, F.lower(F.trim(F.col(rule["from"]))) == F.col("_alias"), "left")
                .withColumn(
                    rule["to"],
                    F.coalesce(
                        "canonical_state",
                        (
                            F.col(rule["from"])
                            if rule.get("on_miss") == "keep_raw"
                            else F.lit(None)
                        ),
                    ),
                )
                .drop("_alias", "canonical_state")
            )
        elif ref == "pincode_directory":
            # Expects silver_pincode_directory to already exist (run pincode source first).
            pin_table = f"{source.target_catalog}.{source.silver_schema}.silver_pincode_directory"
            ref_df = (
                spark.read.table(pin_table)
                .groupBy("pincode")
                .agg(
                    F.first("district").alias("_district"),
                    F.first("state").alias("_state_from_pin"),
                )
            )
            tos = rule["to"] if isinstance(rule["to"], list) else [rule["to"]]
            df = (
                df.join(ref_df, df[rule["from"]] == ref_df["pincode"], "left")
                .drop(ref_df["pincode"])
            )
            if "district" in tos:
                df = df.withColumnRenamed("_district", "district")
            else:
                df = df.drop("_district")
            if "state_from_pincode" in tos:
                df = df.withColumnRenamed("_state_from_pin", "state_from_pincode")
            else:
                df = df.drop("_state_from_pin")
        else:
            raise KeyError(f"Unknown standardize reference '{ref}'")
    return df


def _apply_geo(df: DataFrame, source: Source) -> DataFrame:
    """Add `in_india_bbox` flag and H3 cell columns per configured resolution.

    Mosaic is the production choice for H3 on Databricks; we use the built-in
    `h3_longlatash3string` UDF which ships with DBR 13+ and avoids a Mosaic
    dependency at this stage. Fallback: NULL if the function isn't available.
    """
    if source.geo is None:
        return df
    g = source.geo
    bb = g.india_bbox
    df = df.withColumn(
        "in_india_bbox",
        (F.col(g.lat_col).between(bb["lat_min"], bb["lat_max"]))
        & (F.col(g.lng_col).between(bb["lng_min"], bb["lng_max"])),
    )
    for res in g.h3_resolutions:
        df = df.withColumn(
            f"h3_{res}",
            F.expr(f"h3_longlatash3string({g.lng_col}, {g.lat_col}, {res})"),
        )
    return df


def run_silver(spark: SparkSession, source: Source) -> int:
    """Apply registry-declared rules to Bronze and write Silver. Returns row count."""
    spark.sql(
        f"CREATE SCHEMA IF NOT EXISTS {source.target_catalog}.{source.silver_schema}"
    )

    df = spark.read.table(source.fq_bronze)

    df = _parse_json_columns(df, source.parse_json_columns)
    df = _apply_column_rules(df, source)
    df = _standardize(df, spark, source)
    df = _apply_geo(df, source)

    df = df.withColumn("_silver_built_at", F.current_timestamp())

    (
        df.write
        .mode(source.write_mode)
        .option("mergeSchema", "true")
        .saveAsTable(source.fq_silver)
    )

    final = spark.read.table(source.fq_silver)
    run_expectations(spark, final, source, layer="silver")

    n = final.count()
    print(f"[silver] {source.name}: wrote {n} rows -> {source.fq_silver}")
    return n


def run_all(spark: SparkSession, registry_path: str | None = None) -> dict[str, int]:
    """Run sources in dependency order: pincode first (so facilities can join it)."""
    sources = load_registry(registry_path)
    sources.sort(key=lambda s: 0 if s.name == "pincode_directory" else 1)
    return {s.name: run_silver(spark, s) for s in sources}
