# Databricks notebook source
"""Silver entrypoint — runs every source declared in config/ingestion/sources.yml.

Order is metadata-aware: pincode_directory first so facilities can join it
for district/state geocoding.
"""

# COMMAND ----------
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd().parents[1]))

# COMMAND ----------
from pipelines.framework import silver  # noqa: E402

# COMMAND ----------
results = silver.run_all(spark)  # noqa: F821
print(results)
