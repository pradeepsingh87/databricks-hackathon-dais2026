#!/usr/bin/env bash
# One-shot setup: create UC catalog/schemas, Gold views, and Lakebase instance + schema.
set -euo pipefail

: "${DATABRICKS_HOST:?must set DATABRICKS_HOST}"
: "${DATABRICKS_TOKEN:?must set DATABRICKS_TOKEN}"
: "${DATABRICKS_WAREHOUSE_ID:?must set DATABRICKS_WAREHOUSE_ID}"
CATALOG="${APP_CATALOG:-${UC_CATALOG:-dais_hackathon_2026}}"

# ---------------------------------------------------------------------------
# Unity Catalog: catalog + schemas
# ---------------------------------------------------------------------------
databricks sql query --warehouse-id "$DATABRICKS_WAREHOUSE_ID" \
  --query "CREATE CATALOG IF NOT EXISTS $CATALOG"

for s in bronze silver gold; do
  databricks sql query --warehouse-id "$DATABRICKS_WAREHOUSE_ID" \
    --query "CREATE SCHEMA IF NOT EXISTS $CATALOG.$s"
done

# ---------------------------------------------------------------------------
# Gold convenience views (read by Genie / ad hoc SQL)
# ---------------------------------------------------------------------------
views_sql="$(mktemp /tmp/gold-views.XXXXXX.sql)"
trap 'rm -f "$views_sql"' EXIT

sed "s/__CATALOG__/$CATALOG/g" sql/views/gold_views.sql > "$views_sql"
databricks sql query --warehouse-id "$DATABRICKS_WAREHOUSE_ID" --file "$views_sql"

# ---------------------------------------------------------------------------
# Databricks Lakebase: create instance via Databricks CLI
# The `databases` resource is also declared in config/resources/lakebase.yml
# and provisioned by `./deploy.sh`, but can be created manually here too.
# ---------------------------------------------------------------------------
echo "[setup] Creating Lakebase instance 'care-gap-lakebase' (idempotent) ..."
databricks lakebase create --name care-gap-lakebase 2>/dev/null || \
  echo "[setup] Lakebase instance already exists — skipping creation."

# ---------------------------------------------------------------------------
# Lakebase schema: apply PostgreSQL DDL via psql
# Requires: LAKEBASE_HOST, LAKEBASE_PORT (default 5432), LAKEBASE_DATABASE,
#           LAKEBASE_USER, LAKEBASE_PASSWORD
# ---------------------------------------------------------------------------
: "${LAKEBASE_HOST:?must set LAKEBASE_HOST}"
: "${LAKEBASE_DATABASE:?must set LAKEBASE_DATABASE}"
: "${LAKEBASE_USER:?must set LAKEBASE_USER}"
: "${LAKEBASE_PASSWORD:?must set LAKEBASE_PASSWORD}"
LAKEBASE_PORT="${LAKEBASE_PORT:-5432}"

LAKEBASE_CONNECTION_STRING="postgresql://${LAKEBASE_USER}:${LAKEBASE_PASSWORD}@${LAKEBASE_HOST}:${LAKEBASE_PORT}/${LAKEBASE_DATABASE}?sslmode=require"

echo "[setup] Applying Lakebase schema (sql/lakebase/schema.sql) ..."
psql "$LAKEBASE_CONNECTION_STRING" -f sql/lakebase/schema.sql

echo "[setup] Done. Lakebase instance and schema are ready."
