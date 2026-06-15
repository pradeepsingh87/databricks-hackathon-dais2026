#!/usr/bin/env bash
# One-shot setup: create UC catalog/schemas and Lakebase tables.
set -euo pipefail

: "${DATABRICKS_HOST:?must set DATABRICKS_HOST}"
: "${DATABRICKS_TOKEN:?must set DATABRICKS_TOKEN}"
: "${DATABRICKS_WAREHOUSE_ID:?must set DATABRICKS_WAREHOUSE_ID}"

databricks sql query --warehouse-id "$DATABRICKS_WAREHOUSE_ID" \
  --query "CREATE CATALOG IF NOT EXISTS hackathon"

for s in bronze silver gold lakebase; do
  databricks sql query --warehouse-id "$DATABRICKS_WAREHOUSE_ID" \
    --query "CREATE SCHEMA IF NOT EXISTS hackathon.$s"
done

databricks sql query --warehouse-id "$DATABRICKS_WAREHOUSE_ID" \
  --file sql/lakebase/schema.sql
