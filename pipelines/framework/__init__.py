"""Metadata-driven ingestion framework.

Two runners:
  - bronze.run_bronze(spark, source) — verbatim copy + audit columns
  - silver.run_silver(spark, source) — apply column rules, parse JSON, geocode,
                                       run expectations, write Delta.

Both consume the same `Source` config object loaded from
config/ingestion/sources.yml. Adding a new dataset is a YAML edit.
"""
