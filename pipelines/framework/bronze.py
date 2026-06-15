"""Bronze runner — verbatim copy of upstream tables into the target catalog.

Bronze rule: do NOT transform. Add only audit columns. Schema drift is
preserved so we can always reproduce Silver from Bronze without re-reading
the source. Quality assertions at this layer are limited to existence
(table reachable, row count > 0).
"""

from __future__ import annotations

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from .registry import Source, load_registry


def run_bronze(spark: SparkSession, source: Source) -> int:
    """Copy source -> bronze table. Returns the row count written."""
    spark.sql(
        f"CREATE SCHEMA IF NOT EXISTS {source.target_catalog}.{source.bronze_schema}"
    )

    df = spark.read.table(source.fq_source)

    if source.add_audit_columns:
        df = (
            df.withColumn("_ingested_at", F.current_timestamp())
              .withColumn("_source_table", F.lit(source.fq_source))
              .withColumn("_bronze_run_id", F.expr("uuid()"))
        )

    (
        df.write
        .mode(source.write_mode)
        .option("mergeSchema", "true")
        .saveAsTable(source.fq_bronze)
    )

    n = spark.read.table(source.fq_bronze).count()
    print(f"[bronze] {source.name}: wrote {n} rows -> {source.fq_bronze}")
    return n


def run_all(spark: SparkSession, registry_path: str | None = None) -> dict[str, int]:
    return {s.name: run_bronze(spark, s) for s in load_registry(registry_path)}
