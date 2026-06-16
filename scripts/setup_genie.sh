#!/usr/bin/env bash
# Provision the 'Care Gap Navigator' Genie space against the deployed Gold +
# Silver tables, idempotently.
#
# Strategy: list spaces; if a space with our title already exists, just print
# its URL and exit; otherwise create one with all 9 gold+silver objects
# registered as data sources. The Databricks Genie create-space API does not
# accept top-level instructions/sample-questions today (verified empirically),
# so those still need to be pasted from sql/genie/instructions.md via the UI
# the first time. This script handles the data-sources half declaratively.
set -euo pipefail

PROFILE="${DATABRICKS_PROFILE:-DEFAULT}"
CATALOG="${APP_CATALOG:-${UC_CATALOG:-dais_hackathon_2026}}"
SPACE_TITLE="${GENIE_SPACE_TITLE:-Care Gap Navigator}"
: "${DATABRICKS_WAREHOUSE_ID:?must set DATABRICKS_WAREHOUSE_ID}"

# Resolve the workspace host the CLI is targeting so we can mint URLs.
HOST="$(databricks --profile "$PROFILE" auth env 2>/dev/null \
  | awk -F= '/DATABRICKS_HOST/{print $2}' | tr -d '"')"
if [ -z "$HOST" ]; then
  HOST="https://dbc-f6607f85-16a2.cloud.databricks.com"   # fallback
fi

# 1. Look for an existing space by title (idempotency).
existing_id="$(databricks --profile "$PROFILE" api get /api/2.0/genie/spaces 2>/dev/null \
  | jq -r --arg t "$SPACE_TITLE" '.spaces[] | select(.title==$t) | .space_id' | head -1)"

if [ -n "$existing_id" ]; then
  url="$HOST/genie/rooms/$existing_id"
  echo "[genie] Space '$SPACE_TITLE' already exists."
  echo "[genie]   space_id : $existing_id"
  echo "[genie]   url      : $url"
  echo "GENIE_SPACE_URL=$url"
  exit 0
fi

# 2. Discover gold + silver tables (information_schema). The `tables` array
#    inside serialized_space MUST be sorted by identifier — the API rejects
#    unsorted input with 'data_sources.tables must be sorted by identifier'.
identifiers="$(databricks --profile "$PROFILE" api post /api/2.0/sql/statements \
  --json "$(jq -Rn --arg w "$DATABRICKS_WAREHOUSE_ID" --arg c "$CATALOG" '
    {warehouse_id:$w,
     statement:("SELECT table_schema || \".\" || table_name FROM " + $c +
                ".information_schema.tables WHERE table_schema IN (\"gold\",\"silver\") " +
                "AND table_type IN (\"BASE TABLE\",\"VIEW\",\"MANAGED\") " +
                "ORDER BY table_schema, table_name"),
     wait_timeout:"30s"}')" \
  | jq -r --arg c "$CATALOG" '.result.data_array[][] | "\($c).\(.)"' | sort)"

if [ -z "$identifiers" ]; then
  echo "[genie] No gold/silver tables found in $CATALOG. Run the ETL job first."
  exit 1
fi

tables_json="$(echo "$identifiers" | jq -R '{identifier: .}' | jq -s .)"
serialized="$(jq -nc --argjson t "$tables_json" \
  '{version:2, data_sources:{tables:$t}}')"

# 3. Create the space. We pass the description on the wire so the brief lands
#    on the space immediately; instructions / sample queries still need to be
#    set via UI (no documented field accepts them through this API today).
description="Track 2 — Trust-Weighted Care Gap Navigator. Score = supply quality (0..1). Confidence = how much we trust the score (0..1). evidence_state ∈ {data_deficient, care_gap, covered}. Always show confidence alongside score; treat 'data_deficient' cells as 'we don't know', not 'no care'. See sql/genie/instructions.md for the full brief and sample questions."

response="$(databricks --profile "$PROFILE" api post /api/2.0/genie/spaces \
  --json "$(jq -nc \
    --arg w "$DATABRICKS_WAREHOUSE_ID" \
    --arg t "$SPACE_TITLE" \
    --arg d "$description" \
    --arg s "$serialized" \
    '{warehouse_id:$w, title:$t, description:$d, serialized_space:$s}')")"

space_id="$(echo "$response" | jq -r '.space_id // empty')"
if [ -z "$space_id" ]; then
  echo "[genie] FAILED to create space:"
  echo "$response"
  exit 1
fi

url="$HOST/genie/rooms/$space_id"
n_tables="$(echo "$identifiers" | wc -l | tr -d ' ')"
echo "[genie] Created '$SPACE_TITLE'"
echo "[genie]   space_id : $space_id"
echo "[genie]   url      : $url"
echo "[genie]   tables   : $n_tables"
echo "[genie] Next: paste sql/genie/instructions.md into the space's"
echo "[genie]       'General instructions' field via the UI (one-time)."
echo "GENIE_SPACE_URL=$url"
