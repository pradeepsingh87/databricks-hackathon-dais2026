# Databricks notebook source
"""Bronze entrypoint — runs every source declared in config/ingestion/sources.yml.

This notebook is intentionally tiny. The work happens in the framework runner;
adding a new dataset is a YAML edit, not a code change.
"""

# COMMAND ----------
import sys
from pathlib import Path

# Repo-root on sys.path so 'pipelines.framework' imports work in the notebook.
sys.path.insert(0, str(Path.cwd().parents[1]))

# COMMAND ----------
from pipelines.framework import bronze  # noqa: E402

# COMMAND ----------
results = bronze.run_all(spark)  # noqa: F821 — `spark` is provided by Databricks
print(results)
