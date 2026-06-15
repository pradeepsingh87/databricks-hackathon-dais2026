# Databricks notebook source
"""Silver claim extraction — deterministic v1 capability claims."""

# COMMAND ----------
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd().parents[1]))

# COMMAND ----------
from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.types import (  # noqa: E402
    ArrayType,
    BooleanType,
    DoubleType,
    StringType,
    StructField,
    StructType,
)

from pipelines.common.capability_claims import build_claim_rows  # noqa: E402
from pipelines.framework.registry import get_source  # noqa: E402

# COMMAND ----------
CLAIM_SCHEMA = ArrayType(
    StructType(
        [
            StructField("facility_id", StringType(), True),
            StructField("name", StringType(), True),
            StructField("state", StringType(), True),
            StructField("district", StringType(), True),
            StructField("city", StringType(), True),
            StructField("h3_6", StringType(), True),
            StructField("h3_7", StringType(), True),
            StructField("h3_8", StringType(), True),
            StructField("capability", StringType(), True),
            StructField("evidence_strength", StringType(), True),
            StructField("claim_weight", DoubleType(), True),
            StructField("has_source_url", BooleanType(), True),
            StructField("citations", StringType(), True),
        ]
    )
)


@F.udf(returnType=CLAIM_SCHEMA)
def extract_claims_udf(record):  # noqa: ANN001
    return build_claim_rows(record.asDict(recursive=True) if record is not None else {})


facilities = get_source("facilities")
target_table = (
    f"{facilities.target_catalog}.{facilities.silver_schema}."
    "silver_facility_capability_claims"
)
spark.sql(  # noqa: F821
    f"CREATE SCHEMA IF NOT EXISTS {facilities.target_catalog}.{facilities.silver_schema}"
)

silver_facilities = spark.read.table(facilities.fq_silver)  # noqa: F821

claims = (
    silver_facilities
    .withColumn(
        "_claims",
        extract_claims_udf(
            F.struct(
                "facility_id",
                "name",
                "state",
                "district",
                "city",
                "h3_6",
                "h3_7",
                "h3_8",
                "description",
                "capability_raw",
                "procedure_raw",
                "equipment_raw",
                "specialties_raw",
                "source_urls_raw",
            )
        ),
    )
    .withColumn("_claim", F.explode_outer("_claims"))
    .where(F.col("_claim").isNotNull())
    .select("_claim.*")
    .withColumn("_silver_claims_built_at", F.current_timestamp())
)

(
    claims.write
    .mode("overwrite")
    .option("mergeSchema", "true")
    .saveAsTable(target_table)
)

count = spark.read.table(target_table).count()  # noqa: F821
print(f"[silver-claims] wrote {count} rows -> {target_table}")
