# Databricks notebook source
"""Silver: Mosaic-based spatial geocoding + NFHS-5 demand attach.

Reads:
  - silver.silver_facilities       (lat/lng + canonicalized state + district from pincode)
  - silver.silver_nfhs5_district   (706 districts × 120 indicators)

Writes:
  - silver.silver_facilities_geo

Adds, per facility:
  - geom        ← ST_Point(longitude, latitude)
  - h3_9, h3_10, h3_11 ← Mosaic grid_pointascellid at the three high-fidelity
                         resolutions called out in the brief. Coarser 6/7/8
                         already live on silver_facilities and are kept there.
  - district-level NFHS-5 indicators joined by (state, district)

Why a new table and not a column-add to silver_facilities:
  - silver_facilities is rebuilt by the metadata-driven framework runner; we
    don't want to special-case Mosaic in that loop.
  - Mosaic is heavy (geom column, large H3 strings × 3 resolutions) — keeping
    it in a sibling table lets queries that don't need geometry stay fast.

Why NFHS-5 attaches by (state, district) and not by H3 polygon:
  - NFHS-5 is district-grain — one row per district, no polygons. Joining
    each facility's pincode-derived district against NFHS-5 is a clean
    administrative join. The H3 9/10/11 cells stay on the facility for
    Gold-side spatial aggregation; they're not used as the NFHS-5 join key.
"""

# COMMAND ----------
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd().parents[1]))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Mosaic bootstrap
# MAGIC `enable_mosaic` registers `ST_*` and `grid_*` SQL functions on the
# MAGIC active SparkSession. Cluster must be a recent DBR (Mosaic ships pre-
# MAGIC installed on DBR 13+ for ML/Standard runtimes; for plain runtimes use
# MAGIC `%pip install databricks-mosaic` first).

# COMMAND ----------
# MAGIC %pip install -q databricks-mosaic

# COMMAND ----------
import mosaic as mos  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

mos.enable_mosaic(spark, dbutils)  # noqa: F821 — provided by Databricks runtime

# COMMAND ----------
from pipelines.common.config import fq_schema, get_catalog  # noqa: E402

CATALOG = get_catalog()
SILVER = fq_schema("silver", CATALOG)

FACILITIES_TBL = f"{SILVER}.silver_facilities"
NFHS5_TBL = f"{SILVER}.silver_nfhs5_district"
TARGET_TBL = f"{SILVER}.silver_facilities_geo"

# H3 resolutions per the brief. 9 ≈ 174 m edge; 10 ≈ 65 m; 11 ≈ 25 m.
H3_RESOLUTIONS = [9, 10, 11]

# COMMAND ----------
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SILVER}")  # noqa: F821

# COMMAND ----------
# MAGIC %md
# MAGIC ## Build the spatial frame
# MAGIC One ST_Point per facility, plus H3 cell IDs at three resolutions.

# COMMAND ----------
facilities = spark.read.table(FACILITIES_TBL)  # noqa: F821

# Drop rows we cannot geocode at all. We keep `in_india_bbox = false` rows for
# diagnostic transparency on the map, but they will not get an H3 ID — the
# Mosaic call would silently produce a cell over the wrong continent.
geocodable = facilities.where(
    F.col("latitude").isNotNull()
    & F.col("longitude").isNotNull()
    & F.col("in_india_bbox")
)

with_geom = geocodable.withColumn(
    "geom",
    mos.st_point(F.col("longitude").cast("double"), F.col("latitude").cast("double")),
)

with_h3 = with_geom
for res in H3_RESOLUTIONS:
    with_h3 = with_h3.withColumn(
        f"h3_{res}",
        mos.grid_pointascellid(F.col("geom"), F.lit(res)),
    )

# COMMAND ----------
# MAGIC %md
# MAGIC ## Attach NFHS-5 disease-burden indicators
# MAGIC NFHS-5 is district-grain. silver_facilities already has both `state`
# MAGIC (canonical, alias-resolved) and `district` (from the pincode lookup).
# MAGIC Join on the lower-cased pair so casing differences don't kill matches.

# COMMAND ----------
nfhs5 = spark.read.table(NFHS5_TBL)  # noqa: F821

# We carry every NFHS-5 column through. Downstream Gold scoring picks the
# specific indicator(s) that matter for each capability (e.g. institutional
# birth for maternity demand) without forcing us to enumerate them here.
nfhs5_keyed = (
    nfhs5
    .withColumn("_state_key", F.lower(F.trim(F.col("state"))))
    .withColumn("_district_key", F.lower(F.trim(F.col("district"))))
    .drop("state", "district")
)

joined = (
    with_h3
    .withColumn("_state_key", F.lower(F.trim(F.col("state"))))
    .withColumn("_district_key", F.lower(F.trim(F.col("district"))))
    .join(nfhs5_keyed, ["_state_key", "_district_key"], "left")
    .drop("_state_key", "_district_key")
    .withColumn("_geo_built_at", F.current_timestamp())
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Persist
# MAGIC Write as Delta with mergeSchema=true so adding a new H3 resolution or
# MAGIC a new NFHS-5 column later doesn't require a manual `ALTER TABLE`.

# COMMAND ----------
(
    joined.write
    .mode("overwrite")
    .option("mergeSchema", "true")
    .saveAsTable(TARGET_TBL)
)

written = spark.read.table(TARGET_TBL)  # noqa: F821
print(
    f"[silver-geo] wrote {written.count()} rows -> {TARGET_TBL}  "
    f"(skipped {facilities.count() - geocodable.count()} non-geocodable facilities)"
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Smoke test
# MAGIC Confirm we have non-null geometry, all three H3 resolutions, and at
# MAGIC least one NFHS-5 indicator landed on most rows.

# COMMAND ----------
written.selectExpr(
    "COUNT(*) AS total",
    "COUNT(geom) AS with_geom",
    "COUNT(h3_9) AS with_h3_9",
    "COUNT(h3_10) AS with_h3_10",
    "COUNT(h3_11) AS with_h3_11",
    "COUNT(institutional_birth_5y_pct) AS with_nfhs5_inst_birth",
).show(truncate=False)
