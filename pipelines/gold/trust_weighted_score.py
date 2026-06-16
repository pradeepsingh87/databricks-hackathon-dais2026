# Databricks notebook source
"""Gold: trust-weighted care score per capability and H3 cell."""

# COMMAND ----------
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd().parents[1]))

# COMMAND ----------
from pyspark.sql import functions as F  # noqa: E402

from pipelines.common.config import fq_schema, get_catalog  # noqa: E402
from pipelines.gold.scoring import DATA_DEFICIENT_THRESHOLD  # noqa: E402

# COMMAND ----------
catalog = get_catalog()
silver_schema = fq_schema("silver", catalog)
gold_schema = fq_schema("gold", catalog)
claims_table = f"{silver_schema}.silver_facility_capability_claims"
h3_score_table = f"{gold_schema}.h3_care_score"
state_rollup_table = f"{gold_schema}.care_score_by_state"
district_rollup_table = f"{gold_schema}.care_score_by_district"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {gold_schema}")  # noqa: F821

claims = spark.read.table(claims_table)  # noqa: F821

claims_h3 = None
for resolution in (6, 7, 8):
    h3_df = (
        claims.where(F.col(f"h3_{resolution}").isNotNull())
        .select(
            "facility_id",
            "capability",
            "state",
            "district",
            F.lit(resolution).alias("h3_resolution"),
            F.col(f"h3_{resolution}").alias("h3_cell"),
            "claim_weight",
            "has_source_url",
        )
    )
    claims_h3 = h3_df if claims_h3 is None else claims_h3.unionByName(h3_df)

aggregated = (
    claims_h3.groupBy("capability", "state", "district", "h3_resolution", "h3_cell")
    .agg(
        F.countDistinct("facility_id").alias("n_facilities"),
        F.sum("claim_weight").alias("total_weight"),
        F.avg("claim_weight").alias("avg_claim_weight"),
        F.avg(F.when(F.col("has_source_url"), F.lit(1.0)).otherwise(F.lit(0.0))).alias(
            "source_url_coverage"
        ),
    )
    .withColumn(
        "score",
        F.round(
            F.least(
                F.col("total_weight") / F.greatest(F.col("n_facilities"), F.lit(1)),
                F.lit(1.0),
            ),
            4,
        ),
    )
    .withColumn(
        "confidence",
        F.round(
            F.least(
                F.lit(0.4) * F.least(F.col("n_facilities") / F.lit(5.0), F.lit(1.0))
                + F.lit(0.4) * F.coalesce(F.col("avg_claim_weight"), F.lit(0.0))
                + F.lit(0.2) * F.coalesce(F.col("source_url_coverage"), F.lit(0.0)),
                F.lit(1.0),
            ),
            4,
        ),
    )
    .withColumn(
        "data_deficient",
        (F.col("n_facilities") == 0)
        | (F.col("confidence") < F.lit(DATA_DEFICIENT_THRESHOLD)),
    )
    .withColumn(
        "evidence_state",
        F.when(F.col("data_deficient"), F.lit("data_deficient"))
        .when(F.col("score") < F.lit(0.35), F.lit("care_gap"))
        .otherwise(F.lit("covered")),
    )
    .select(
        "capability",
        "state",
        "district",
        "h3_resolution",
        "h3_cell",
        "n_facilities",
        "score",
        "confidence",
        "data_deficient",
        "evidence_state",
    )
)

(
    aggregated.write
    .mode("overwrite")
    .option("mergeSchema", "true")
    .saveAsTable(h3_score_table)
)

state_rollup = (
    aggregated.groupBy("capability", "state")
    .agg(
        F.round(F.avg("score"), 4).alias("score"),
        F.round(F.avg("confidence"), 4).alias("confidence"),
        F.sum("n_facilities").alias("n_facilities"),
        F.sum(F.when(F.col("data_deficient"), F.lit(1)).otherwise(F.lit(0))).alias(
            "n_data_deficient_cells"
        ),
    )
)

district_rollup = (
    aggregated.groupBy("capability", "state", "district")
    .agg(
        F.round(F.avg("score"), 4).alias("score"),
        F.round(F.avg("confidence"), 4).alias("confidence"),
        F.sum("n_facilities").alias("n_facilities"),
        F.sum(F.when(F.col("data_deficient"), F.lit(1)).otherwise(F.lit(0))).alias(
            "n_data_deficient_cells"
        ),
    )
)

state_rollup.write.mode("overwrite").option("mergeSchema", "true").saveAsTable(
    state_rollup_table
)
district_rollup.write.mode("overwrite").option("mergeSchema", "true").saveAsTable(
    district_rollup_table
)

# ---- Snapshot history ----------------------------------------------------
# Append-only log of district rollups so the Performance page can show a
# real time-series instead of a synthetic projection. Each ETL run stamps a
# fresh `score_run_id` (UUID) and a `snapshot_ts`. Cheap (~1 row per district
# per capability per run) and Liquid-clustered for fast slice queries.
score_history_table = f"{gold_schema}.score_history"

snapshot = (
    district_rollup
    .withColumn("score_run_id", F.expr("uuid()"))
    .withColumn("snapshot_ts", F.current_timestamp())
    .select(
        "score_run_id", "snapshot_ts",
        "capability", "state", "district",
        "score", "confidence", "n_facilities", "n_data_deficient_cells",
    )
)
(
    snapshot.write
    .mode("append")
    .option("mergeSchema", "true")
    .saveAsTable(score_history_table)
)

print(
    f"[gold] wrote {h3_score_table}, {state_rollup_table}, "
    f"{district_rollup_table}, +1 snapshot to {score_history_table}"
)
