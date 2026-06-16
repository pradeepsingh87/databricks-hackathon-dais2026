# Databricks notebook source
"""Gold: Medical Desert identification.

Combines verified supply (silver_facility_capability_claims, with rule-based
strong/partial/suspicious labels + structured citations) with district-level
NFHS-5 demand (silver_facilities_geo, NFHS-5 indicator per capability) to
produce per-(capability, h3_cell) GAP scores.

Outputs:
  - gold.medical_desert_h3       (capability, h3_resolution, h3_cell, ...)
      one row per cell × resolution × capability
  - gold.medical_desert_districts
      district-grain rollup with citations sample

Each row carries `top_citations` — up to 3 quoted excerpts from the
underlying facility text, satisfying the hackathon "cite the underlying
facility text for any score or ranking" requirement.

Score:
    verified_supply  = SUM(claim_weight where evidence_strength != suspicious)
                       (claim_weight: strong=1.0, partial=0.5, suspicious
                        excluded — suspicious is a *signal*, not supply)
    demand_score     = NFHS-5 indicator transformed to 0..1, where 1 = high
                       demand. Polarity per config/capability_demand.yml.
    gap_score        = max(0, 1 - verified_supply / max_supply_in_state)
                       × demand_score
                       (i.e. relative supply gap × demand-weight)
    confidence_label = strong | partial | suspicious | none — propagated from
                       the dominant facility-level label in the cell.
    desert_flag      = (gap_score > 0.6 AND confidence_label != 'suspicious')
                       The "this region is a Medical Desert" boolean.
"""

# COMMAND ----------
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd().parents[1]))

# COMMAND ----------
from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.window import Window   # noqa: E402

from pipelines.common.config import fq_schema, get_catalog  # noqa: E402

# COMMAND ----------
import yaml  # noqa: E402

CATALOG = get_catalog()
SILVER = fq_schema("silver", CATALOG)
GOLD = fq_schema("gold", CATALOG)

CLAIMS_TBL  = f"{SILVER}.silver_facility_capability_claims"
GEO_TBL     = f"{SILVER}.silver_facilities_geo"
DESERT_H3   = f"{GOLD}.medical_desert_h3"
DESERT_DIST = f"{GOLD}.medical_desert_districts"

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "capability_demand.yml"
with CONFIG_PATH.open() as f:
    DEMAND_CONFIG = yaml.safe_load(f)["capabilities"]

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {GOLD}")  # noqa: F821

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1 · Verified supply per facility × capability
# MAGIC `silver_facility_capability_claims` already carries `evidence_strength`
# MAGIC and structured `citations`. We exclude `suspicious` from supply (a
# MAGIC suspicious claim is a *flag*, not a service) and keep its rows for the
# MAGIC confidence rollup.

# COMMAND ----------
claims = (
    spark.read.table(CLAIMS_TBL)  # noqa: F821
    .withColumn(
        "verified_weight",
        F.when(F.col("evidence_strength") == "suspicious", F.lit(0.0))
         .otherwise(F.col("claim_weight")),
    )
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2 · NFHS-5 demand per facility × capability
# MAGIC The geocoded silver table carries every NFHS-5 column at district
# MAGIC grain. We pivot the per-capability indicator into a single
# MAGIC `demand_raw` column, then normalise per-state to 0..1.

# COMMAND ----------
geo = spark.read.table(GEO_TBL)  # noqa: F821

# Build a demand-per-(facility, capability) frame by emitting one row per
# capability with that capability's chosen NFHS-5 indicator inlined.
demand_rows = None
for capability, cfg in DEMAND_CONFIG.items():
    indicator = cfg["indicator"]
    if indicator not in geo.columns:
        # NFHS-5 column missing in this run (e.g. silver wasn't rebuilt).
        # Emit NULL demand; gold rows just won't have a desert flag.
        col = F.lit(None).cast("double")
    else:
        col = F.col(indicator).cast("double")

    # Polarity: convert the raw % into a 0..1 "demand intensity".
    # low_means_high_demand   →  (100 - x) / 100
    # high_means_high_demand  →  x / 100
    if cfg["direction"] == "low_means_high_demand":
        demand = (F.lit(100.0) - col) / F.lit(100.0)
    else:
        demand = col / F.lit(100.0)

    one_cap = (
        geo.select(
            "facility_id",
            "state", "district",
            "h3_6", "h3_7", "h3_8",
        )
        .withColumn("capability", F.lit(capability))
        .withColumn("indicator_name", F.lit(indicator))
        .withColumn("indicator_value", col)
        .withColumn(
            "demand_score",
            F.when(demand.isNotNull(), F.greatest(F.least(demand, F.lit(1.0)), F.lit(0.0)))
             .otherwise(F.lit(None).cast("double")),
        )
    )
    demand_rows = one_cap if demand_rows is None else demand_rows.unionByName(one_cap)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3 · Join supply ⨯ demand at facility-level grain
# MAGIC Inner-join on (facility_id, capability). Facilities that never made a
# MAGIC claim for a given capability simply don't appear — that's correct;
# MAGIC they're not supply for it.

# COMMAND ----------
joined = (
    claims.alias("c")
    .join(
        demand_rows.alias("d"),
        on=["facility_id", "capability"],
        how="inner",
    )
    # Keep cell IDs from the silver geo table (more authoritative — they came
    # from Mosaic's grid_pointascellid via in_india_bbox-filtered rows).
    .select(
        "c.facility_id", "c.capability",
        F.coalesce(F.col("d.state"), F.col("c.state")).alias("state"),
        F.coalesce(F.col("d.district"), F.col("c.district")).alias("district"),
        F.coalesce(F.col("d.h3_6"), F.col("c.h3_6")).alias("h3_6"),
        F.coalesce(F.col("d.h3_7"), F.col("c.h3_7")).alias("h3_7"),
        F.coalesce(F.col("d.h3_8"), F.col("c.h3_8")).alias("h3_8"),
        "c.evidence_strength",
        "c.claim_weight",
        "c.verified_weight",
        "c.citations",
        "c.has_source_url",
        "d.indicator_name",
        "d.indicator_value",
        "d.demand_score",
        "c.name",
        "c.city",
    )
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4 · Aggregate per (capability, h3_resolution, h3_cell)
# MAGIC We compute the cell metrics for resolutions 6, 7, 8 in one Spark plan
# MAGIC by emitting one row per (resolution, cell) up front.

# COMMAND ----------
expanded = None
for resolution in (6, 7, 8):
    one_res = joined.select(
        "capability", "state", "district",
        F.lit(resolution).alias("h3_resolution"),
        F.col(f"h3_{resolution}").alias("h3_cell"),
        "facility_id", "evidence_strength", "claim_weight", "verified_weight",
        "citations", "has_source_url",
        "indicator_name", "indicator_value", "demand_score",
        "name", "city",
    )
    expanded = one_res if expanded is None else expanded.unionByName(one_res)

expanded = expanded.where(F.col("h3_cell").isNotNull())

# Aggregations per cell — supply, demand, citations sample.
cell_agg = (
    expanded
    .groupBy("capability", "state", "h3_resolution", "h3_cell")
    .agg(
        F.countDistinct("facility_id").alias("n_facilities"),
        F.sum(F.when(F.col("evidence_strength") == "strong",     1).otherwise(0))
            .alias("n_strong"),
        F.sum(F.when(F.col("evidence_strength") == "partial",    1).otherwise(0))
            .alias("n_partial"),
        F.sum(F.when(F.col("evidence_strength") == "suspicious", 1).otherwise(0))
            .alias("n_suspicious"),
        F.sum("verified_weight").alias("verified_supply"),
        F.avg("demand_score").alias("demand_score"),
        F.avg(F.when(F.col("has_source_url"), 1.0).otherwise(0.0))
            .alias("source_url_coverage"),
        # Up to 3 distinct facilities' first citation entry, for the
        # "cite underlying facility text" obligation.
        F.slice(F.collect_set(F.struct(
            F.col("facility_id"),
            F.col("name"),
            F.col("city"),
            F.col("evidence_strength"),
            F.col("citations"),
        )), 1, 3).alias("top_citations"),
        F.first("indicator_name", ignorenulls=True).alias("indicator_name"),
        F.avg("indicator_value").alias("indicator_value"),
    )
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5 · Compute gap_score, confidence_label, desert_flag
# MAGIC Supply is normalised against the *max verified supply within the
# MAGIC state* — that's what "relative gap inside its own region" means; a
# MAGIC global denominator would make rural areas always look bad regardless
# MAGIC of how Indian healthcare distributes overall.

# COMMAND ----------
state_max = Window.partitionBy("capability", "state", "h3_resolution")

scored = (
    cell_agg
    .withColumn(
        "max_supply_in_state",
        F.max("verified_supply").over(state_max),
    )
    .withColumn(
        "supply_score",
        F.when(F.col("max_supply_in_state") > 0,
               F.col("verified_supply") / F.col("max_supply_in_state"))
         .otherwise(F.lit(0.0)),
    )
    .withColumn(
        "gap_score",
        F.when(
            F.col("demand_score").isNotNull(),
            F.greatest(F.lit(0.0), F.lit(1.0) - F.col("supply_score"))
            * F.col("demand_score"),
        ).otherwise(F.lit(None).cast("double")),
    )
    .withColumn(
        "confidence_label",
        F.when(F.col("n_strong") >= F.col("n_partial"),  F.lit("strong"))
         .when(F.col("n_partial") > 0,                     F.lit("partial"))
         .when(F.col("n_suspicious") > 0,                  F.lit("suspicious"))
         .otherwise(F.lit("none")),
    )
    .withColumn(
        "desert_flag",
        (F.col("gap_score") > 0.6) & (F.col("confidence_label") != "suspicious"),
    )
    .withColumn("score_run_id", F.expr("uuid()"))
    .withColumn("as_of_ts",     F.current_timestamp())
    .select(
        "capability", "state", "h3_resolution", "h3_cell",
        "n_facilities", "n_strong", "n_partial", "n_suspicious",
        "verified_supply", "max_supply_in_state",
        "supply_score",
        "indicator_name", "indicator_value", "demand_score",
        "gap_score",
        "source_url_coverage",
        "confidence_label", "desert_flag",
        "top_citations",
        "score_run_id", "as_of_ts",
    )
)

# COMMAND ----------
(
    scored.write
    .mode("overwrite")
    .option("mergeSchema", "true")
    .partitionBy("capability")
    .saveAsTable(DESERT_H3)
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 6 · District rollup
# MAGIC Same metrics, district grain. The per-cell `top_citations` are
# MAGIC flattened at this level so the planner gets a sample for the whole
# MAGIC district when looking at the choropleth.

# COMMAND ----------
district_agg = (
    expanded.where(F.col("h3_resolution") == 7)   # one canonical grain for the rollup
    .groupBy("capability", "state", "district")
    .agg(
        F.countDistinct("facility_id").alias("n_facilities"),
        F.sum(F.when(F.col("evidence_strength") == "strong",     1).otherwise(0))
            .alias("n_strong"),
        F.sum(F.when(F.col("evidence_strength") == "partial",    1).otherwise(0))
            .alias("n_partial"),
        F.sum(F.when(F.col("evidence_strength") == "suspicious", 1).otherwise(0))
            .alias("n_suspicious"),
        F.sum("verified_weight").alias("verified_supply"),
        F.avg("demand_score").alias("demand_score"),
        F.avg("indicator_value").alias("indicator_value"),
        F.first("indicator_name", ignorenulls=True).alias("indicator_name"),
        F.slice(F.collect_set(F.struct(
            F.col("facility_id"),
            F.col("name"),
            F.col("city"),
            F.col("evidence_strength"),
            F.col("citations"),
        )), 1, 5).alias("top_citations"),
    )
)

district_state_max = Window.partitionBy("capability", "state")
district_scored = (
    district_agg
    .withColumn("max_supply_in_state", F.max("verified_supply").over(district_state_max))
    .withColumn(
        "supply_score",
        F.when(F.col("max_supply_in_state") > 0,
               F.col("verified_supply") / F.col("max_supply_in_state"))
         .otherwise(F.lit(0.0)),
    )
    .withColumn(
        "gap_score",
        F.when(F.col("demand_score").isNotNull(),
               F.greatest(F.lit(0.0), F.lit(1.0) - F.col("supply_score"))
               * F.col("demand_score"))
         .otherwise(F.lit(None).cast("double")),
    )
    .withColumn(
        "confidence_label",
        F.when(F.col("n_strong") >= F.col("n_partial"),  F.lit("strong"))
         .when(F.col("n_partial") > 0,                     F.lit("partial"))
         .when(F.col("n_suspicious") > 0,                  F.lit("suspicious"))
         .otherwise(F.lit("none")),
    )
    .withColumn("desert_flag",
                (F.col("gap_score") > 0.6) & (F.col("confidence_label") != "suspicious"))
    .withColumn("score_run_id", F.expr("uuid()"))
    .withColumn("as_of_ts",     F.current_timestamp())
)

(
    district_scored.write
    .mode("overwrite")
    .option("mergeSchema", "true")
    .partitionBy("capability")
    .saveAsTable(DESERT_DIST)
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 7 · Smoke output
# MAGIC The deserts. Demos love this query.

# COMMAND ----------
print(
    f"[gold-desert] wrote "
    f"{spark.read.table(DESERT_H3).count()} rows -> {DESERT_H3}"  # noqa: F821
)
print(
    f"[gold-desert] wrote "
    f"{spark.read.table(DESERT_DIST).count()} rows -> {DESERT_DIST}"  # noqa: F821
)
print("Top-10 medical deserts (district grain, h3 res=7):")
spark.read.table(DESERT_DIST).where(F.col("desert_flag")).orderBy(  # noqa: F821
    F.col("gap_score").desc()
).select("capability", "state", "district",
         "n_facilities", "verified_supply", "demand_score", "gap_score",
         "confidence_label").show(10, truncate=False)
