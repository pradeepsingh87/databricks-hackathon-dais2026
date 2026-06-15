#!/usr/bin/env bash
# One-shot setup: create UC catalog/schemas and Lakebase tables.
set -euo pipefail

: "${DATABRICKS_HOST:?must set DATABRICKS_HOST}"
: "${DATABRICKS_TOKEN:?must set DATABRICKS_TOKEN}"
: "${DATABRICKS_WAREHOUSE_ID:?must set DATABRICKS_WAREHOUSE_ID}"
CATALOG="${APP_CATALOG:-${UC_CATALOG:-dais_hackathon_2026}}"

databricks sql query --warehouse-id "$DATABRICKS_WAREHOUSE_ID" \
  --query "CREATE CATALOG IF NOT EXISTS $CATALOG"

for s in bronze silver gold lakebase; do
  databricks sql query --warehouse-id "$DATABRICKS_WAREHOUSE_ID" \
    --query "CREATE SCHEMA IF NOT EXISTS $CATALOG.$s"
done

lakebase_sql="$(mktemp /tmp/lakebase-schema.XXXXXX.sql)"
views_sql="$(mktemp /tmp/gold-views.XXXXXX.sql)"
trap 'rm -f "$lakebase_sql" "$views_sql"' EXIT

sed "s/__CATALOG__/$CATALOG/g" sql/lakebase/schema.sql > "$lakebase_sql"
sed "s/__CATALOG__/$CATALOG/g" sql/views/gold_views.sql > "$views_sql"

databricks sql query --warehouse-id "$DATABRICKS_WAREHOUSE_ID" --file "$lakebase_sql"
databricks sql query --warehouse-id "$DATABRICKS_WAREHOUSE_ID" --file "$views_sql"
