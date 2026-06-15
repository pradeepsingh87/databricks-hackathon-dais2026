#!/usr/bin/env bash
# One-shot setup: create UC catalog/schemas, Lakebase tables, and Gold views.
#
# Uses the SQL Statements API (`databricks api post /api/2.0/sql/statements`)
# because there is no `databricks sql query` CLI subcommand.
#
# Statements are inlined here rather than parsed from .sql files. The previous
# version split sql/lakebase/schema.sql on ';' via awk and consistently
# dropped statements on macOS bash 3.2 — inlining is both more robust and
# easier to read at review time.
set -euo pipefail

PROFILE="${DATABRICKS_PROFILE:-DEFAULT}"
CATALOG="${APP_CATALOG:-${UC_CATALOG:-dais_hackathon_2026}}"
: "${DATABRICKS_WAREHOUSE_ID:?must set DATABRICKS_WAREHOUSE_ID}"

run_sql() {
  local stmt="$1"
  echo "[setup] $(echo "$stmt" | tr -s '[:space:]' ' ' | cut -c1-90)..."
  local resp
  resp="$(databricks --profile "$PROFILE" api post /api/2.0/sql/statements \
    --json "$(jq -Rn --arg s "$stmt" --arg w "$DATABRICKS_WAREHOUSE_ID" \
      '{warehouse_id: $w, statement: $s, wait_timeout: "30s"}')")"

  local state
  state="$(echo "$resp" | jq -r '.status.state')"
  if [ "$state" != "SUCCEEDED" ]; then
    echo "[setup] FAILED ($state)"
    echo "$resp" | jq '.status.error // .status'
    exit 1
  fi
}

# 1. Catalog + schemas
run_sql "CREATE CATALOG IF NOT EXISTS $CATALOG"
for s in bronze silver gold lakebase; do
  run_sql "CREATE SCHEMA IF NOT EXISTS $CATALOG.$s"
done

# 2. Lakebase tables. Column is `user_name` (not `user`) because `user` is
#    reserved in Spark SQL — unquoted INSERTs would fail at parse time.
run_sql "
CREATE TABLE IF NOT EXISTS $CATALOG.lakebase.scenarios (
  id          BIGINT GENERATED ALWAYS AS IDENTITY,
  user_name   STRING NOT NULL,
  name        STRING NOT NULL,
  payload     STRING,
  created_at  TIMESTAMP NOT NULL
) USING DELTA
"
run_sql "
CREATE TABLE IF NOT EXISTS $CATALOG.lakebase.overrides (
  id           BIGINT GENERATED ALWAYS AS IDENTITY,
  user_name    STRING NOT NULL,
  facility_id  STRING NOT NULL,
  capability   STRING NOT NULL,
  note         STRING,
  created_at   TIMESTAMP NOT NULL
) USING DELTA
"
run_sql "
CREATE TABLE IF NOT EXISTS $CATALOG.lakebase.shortlists (
  id           BIGINT GENERATED ALWAYS AS IDENTITY,
  user_name    STRING NOT NULL,
  scenario_id  BIGINT,
  facility_id  STRING NOT NULL,
  rank         INT,
  created_at   TIMESTAMP NOT NULL
) USING DELTA
"

# 3. Gold convenience views — only create them once the underlying tables
#    have been populated by the ETL job. Creating them earlier would error.
gold_table_count="$(databricks --profile "$PROFILE" api post /api/2.0/sql/statements \
  --json "$(jq -Rn --arg w "$DATABRICKS_WAREHOUSE_ID" --arg c "$CATALOG" \
    '{warehouse_id: $w,
      statement: ("SELECT COUNT(*) AS n FROM " + $c +
                  ".information_schema.tables WHERE table_schema = '\''gold'\''"),
      wait_timeout: "20s"}')" \
  | jq -r '.result.data_array[0][0] // "0"')"

if [ "${gold_table_count:-0}" -ge 2 ]; then
  run_sql "
  CREATE OR REPLACE VIEW $CATALOG.gold.v_care_gap_by_state AS
  SELECT capability, state, score, confidence, n_facilities, n_data_deficient_cells
  FROM $CATALOG.gold.care_score_by_state
  "
  run_sql "
  CREATE OR REPLACE VIEW $CATALOG.gold.v_care_gap_by_district AS
  SELECT capability, state, district, score, confidence, n_facilities, n_data_deficient_cells
  FROM $CATALOG.gold.care_score_by_district
  "
else
  echo "[setup] Skipping Gold views — gold tables not populated yet (count=${gold_table_count:-0})."
  echo "[setup]   Run: databricks --profile $PROFILE bundle run care_gap_etl --target dev"
  echo "[setup]   Then re-run this script to create the views."
fi

echo "[setup] Done. Catalog: $CATALOG  Schemas: bronze, silver, gold, lakebase"
