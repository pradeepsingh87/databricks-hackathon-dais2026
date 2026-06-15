# Databricks notebook source
"""Silver: normalize raw facility text into per-(facility, capability) claims with H3 cells.

Output: silver.facility_claims
Columns: facility_id, name, state, city, lat, lng, h3_cell (per resolution),
         capability, claim_text, evidence_strength, citation
"""

# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver: claim extraction + H3 indexing
# MAGIC - Mosaic `grid_longlatascellid(lng, lat, resolution)` per resolution in config.
# MAGIC - Heuristic + LLM-assisted extraction of capability claims from `description`,
# MAGIC   `capability`, `procedure`, `equipment`, `specialties`.
# MAGIC - `evidence_strength` ∈ {strong, partial, suspicious, none} based on:
# MAGIC     - count of distinct supporting fields
# MAGIC     - presence of equipment/procedure terms vs. specialty-only mentions
# MAGIC     - source URL presence

# COMMAND ----------
# import mosaic as mos
# mos.enable_mosaic(spark, dbutils)

# COMMAND ----------
# TODO: read bronze, explode capabilities, attach H3 cells, score evidence
