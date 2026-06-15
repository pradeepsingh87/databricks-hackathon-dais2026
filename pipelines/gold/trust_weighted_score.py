# Databricks notebook source
"""Gold: trust-weighted care score per (capability, H3 cell).

Output: gold.h3_care_score
Columns: capability, h3_resolution, h3_cell, n_facilities,
         score (0..1), confidence (0..1), data_deficient (bool)

Score formula sketch:
  weight(strong)   = 1.0
  weight(partial)  = 0.5
  weight(suspicious) = 0.1
  score      = sum(weight) / max_expected_facilities_per_cell
  confidence = f(n_facilities, fraction_with_strong_evidence, source_url_coverage)
  data_deficient = (n_facilities == 0) OR (confidence < threshold)
"""

# COMMAND ----------
# MAGIC %md
# MAGIC ## Gold: trust-weighted aggregate
# MAGIC Distinguishes "proven-absent" (high confidence, low score) from
# MAGIC "data-deficient" (low confidence) — the core insight of the app.

# COMMAND ----------
# TODO: groupBy(capability, h3_resolution, h3_cell).agg(weighted score, confidence)
