# Databricks notebook source
"""Bronze: land the raw 10,000 facility records into Delta as-is."""

# COMMAND ----------
# MAGIC %md
# MAGIC ## Bronze ingest
# MAGIC Reads the provided CSV/JSON dump and writes to `bronze.facilities_raw`
# MAGIC with no transformations beyond schema inference + audit columns.

# COMMAND ----------
from pyspark.sql import functions as F  # noqa: F401

# COMMAND ----------
RAW_PATH = "/Volumes/hackathon/care_gap/raw/facilities.csv"  # adjust per env

# COMMAND ----------
# df = (spark.read.option("header", True).option("multiLine", True).csv(RAW_PATH)
#         .withColumn("_ingested_at", F.current_timestamp())
#         .withColumn("_source_file", F.input_file_name()))
# df.write.mode("overwrite").saveAsTable("hackathon.care_gap.bronze_facilities_raw")
