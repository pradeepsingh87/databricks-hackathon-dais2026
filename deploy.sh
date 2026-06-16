#!/usr/bin/env bash
# ============================================================
#  Care Gap Navigator — full-stack Databricks deploy
#  Profile: DEFAULT  (override via DATABRICKS_PROFILE)
#  Target : dev      (override via BUNDLE_TARGET)
#
#  Two phases run in sequence by default:
#
#  Phase A — bundle assets (skipped when APP_ONLY=1):
#    1. CLI version + auth preflight
#    2. bundle validate
#    3. bundle deploy                  (uploads code + creates Job resource)
#    4. setup_uc.sh                    (creates UC schemas + Lakebase tables)
#    5. setup_genie.sh                 (idempotent Genie space provision)
#    6. apply uc_metadata.sql          (table comments + tags + certified)
#    7. bundle run care_gap_etl --no-wait
#
#  Phase B — app lifecycle (skipped when BUNDLE_ONLY=1):
#    8. apps create-or-update          (idempotent, payload at
#                                       config/apps/care_gap_navigator.json)
#    9. apps deploy                    (binds bundle-uploaded source path)
#   10. apps stop  +  apps start       (clean restart so new code loads)
#
#  Phase flags (mutually exclusive):
#    BUNDLE_ONLY=1      run Phase A only (alias: SKIP_APP=1, deprecated)
#    APP_ONLY=1         run Phase B only (still reads bundle summary
#                                          to compute APP_SOURCE_PATH)
#
#  Skip / customise via env vars:
#    SKIP_UC=1          skip UC schema + Lakebase table creation
#    SKIP_GENIE=1       skip Genie space provision
#    SKIP_METADATA=1    skip table comments + tags + certified pass
#    SKIP_ETL=1         skip ETL trigger
#    APP_PREFIX=foo     override the per-developer prefix
#    DATABRICKS_WAREHOUSE_ID=...   warehouse for setup_uc.sh + setup_genie.sh
# ============================================================
set -euo pipefail

PROFILE="${DATABRICKS_PROFILE:-DEFAULT}"
TARGET="${BUNDLE_TARGET:-dev}"

# Per-developer namespace stamped onto Job + App resource names via
# ${var.app_prefix}. Sanitised so it survives Databricks resource-name rules.
sanitize() { echo "$1" | tr 'A-Z' 'a-z' | tr -c 'a-z0-9-' '-' | sed 's/^-*//; s/-*$//'; }
APP_PREFIX="${APP_PREFIX:-$(sanitize "${USER:-pradeep}")}"
echo "[deploy] app_prefix     : $APP_PREFIX"

# ---- Phase flag parsing ------------------------------------------------
# SKIP_APP is the historical name; map it onto BUNDLE_ONLY for one cycle.
if [ "${SKIP_APP:-0}" = "1" ] && [ "${BUNDLE_ONLY:-0}" != "1" ]; then
  echo "[deploy] WARN: SKIP_APP is deprecated — use BUNDLE_ONLY=1 instead."
  BUNDLE_ONLY=1
fi
if [ "${BUNDLE_ONLY:-0}" = "1" ] && [ "${APP_ONLY:-0}" = "1" ]; then
  echo "[deploy] ERROR: BUNDLE_ONLY=1 and APP_ONLY=1 are mutually exclusive."
  exit 1
fi
RUN_PHASE_A=1
RUN_PHASE_B=1
[ "${APP_ONLY:-0}" = "1" ]    && RUN_PHASE_A=0
[ "${BUNDLE_ONLY:-0}" = "1" ] && RUN_PHASE_B=0
echo "[deploy] phases         : A=$RUN_PHASE_A (bundle)  B=$RUN_PHASE_B (app)"

# ---- Preflight ---------------------------------------------------------
MIN_CLI_MAJOR=0
MIN_CLI_MINOR=260
if ! command -v databricks >/dev/null 2>&1; then
  echo "[deploy] ERROR: databricks CLI not found on PATH."
  echo "[deploy]   brew install databricks  (or)  curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh"
  exit 1
fi
CLI_VER="$(databricks --version | awk '{print $NF}' | sed 's/^v//')"
CLI_MAJOR="$(echo "$CLI_VER" | cut -d. -f1)"
CLI_MINOR="$(echo "$CLI_VER" | cut -d. -f2)"
if [ "$CLI_MAJOR" -lt "$MIN_CLI_MAJOR" ] \
   || { [ "$CLI_MAJOR" -eq "$MIN_CLI_MAJOR" ] && [ "$CLI_MINOR" -lt "$MIN_CLI_MINOR" ]; }; then
  echo "[deploy] ERROR: databricks CLI v$CLI_VER is too old (bundle deploys hit 'openpgp: key expired')."
  echo "[deploy]   Upgrade: brew upgrade databricks"
  exit 1
fi
echo "[deploy] databricks CLI : v$CLI_VER"

if ! command -v jq >/dev/null 2>&1; then
  echo "[deploy] ERROR: jq is required."
  echo "[deploy]   brew install jq"
  exit 1
fi

if ! databricks --profile "$PROFILE" current-user me >/dev/null 2>&1; then
  echo "[deploy] ERROR: profile '$PROFILE' is not authenticated."
  echo "[deploy]   Run: databricks auth login --profile $PROFILE"
  exit 1
fi

# Default warehouse — used by setup_uc.sh, setup_genie.sh, and the metadata
# SQL pass. Pulled from the bundle's app.yaml default.
WAREHOUSE_ID="${DATABRICKS_WAREHOUSE_ID:-5954d90879db71e9}"
export DATABRICKS_WAREHOUSE_ID="$WAREHOUSE_ID"

# ============================================================
#  PHASE A — bundle assets
# ============================================================
if [ "$RUN_PHASE_A" = "1" ]; then
  # ---- 1. Validate -----------------------------------------------------
  echo
  echo "[deploy] (1/7) Validating bundle ..."
  databricks --profile "$PROFILE" bundle validate --target "$TARGET" \
    --var="app_prefix=${APP_PREFIX}"

  # ---- 2. Deploy -------------------------------------------------------
  echo
  echo "[deploy] (2/7) Deploying bundle to target '$TARGET' ..."
  databricks --profile "$PROFILE" bundle deploy --target "$TARGET" \
    --var="app_prefix=${APP_PREFIX}"
fi

# Resolve workspace file path + Genie space ID + job name from bundle summary.
# This works in both phases:
#   - Phase A on its own: post-deploy summary read.
#   - APP_ONLY=1: read-only summary (no deploy) to discover the path the
#     bundle previously synced /app/ to.
SUMMARY="$(databricks --profile "$PROFILE" bundle summary --target "$TARGET" \
  --var="app_prefix=${APP_PREFIX}" -o json 2>/dev/null)"
JOB_NAME="$(echo "$SUMMARY" | jq -r '.resources.jobs.care_gap_etl.name // empty')"
WS_FILE_PATH="$(echo "$SUMMARY" | jq -r '.workspace.file_path // empty')"
GENIE_SPACE_ID="$(echo "$SUMMARY" | jq -r '.variables.genie_space_id.value // empty')"
APP_NAME="${APP_PREFIX}-care-gap-navigator"
APP_SOURCE_PATH=""
[ -n "$WS_FILE_PATH" ] && APP_SOURCE_PATH="${WS_FILE_PATH}/app"

if [ "$RUN_PHASE_B" = "1" ] && [ -z "$APP_SOURCE_PATH" ]; then
  echo "[deploy] ERROR: could not resolve workspace.file_path from bundle summary."
  echo "[deploy]        Run 'databricks bundle summary --target $TARGET' manually."
  exit 1
fi
[ "$RUN_PHASE_A" = "1" ] && echo "[deploy] resolved Job  : ${JOB_NAME:-<unknown>}"
echo "[deploy] resolved App  : $APP_NAME"

if [ "$RUN_PHASE_A" = "1" ]; then
  # ---- 3. UC schemas + Lakebase ----------------------------------------
  if [ "${SKIP_UC:-0}" = "1" ]; then
    echo
    echo "[deploy] (3/7) SKIP_UC=1 — skipping UC + Lakebase setup."
  else
    echo
    echo "[deploy] (3/7) Provisioning UC schemas + Lakebase tables ..."
    ./scripts/setup_uc.sh
  fi

  # ---- 4. Genie space --------------------------------------------------
  if [ "${SKIP_GENIE:-0}" = "1" ]; then
    echo
    echo "[deploy] (4/7) SKIP_GENIE=1 — skipping Genie space provision."
  else
    echo
    echo "[deploy] (4/7) Provisioning Genie space ..."
    ./scripts/setup_genie.sh || \
      echo "[deploy] WARN: Genie provision returned non-zero (continuing)."
  fi

  # ---- 5. UC metadata (comments + tags + certified) -------------------
  # Best-effort; some ALTERs SKIP cleanly when target tables aren't
  # materialised yet (medical_desert_*, silver_facilities_geo). The Python
  # helper handles UTF-8 in COMMENTs, which the shell-piped jq pattern can't.
  if [ "${SKIP_METADATA:-0}" = "1" ]; then
    echo
    echo "[deploy] (5/7) SKIP_METADATA=1 — skipping UC metadata pass."
  elif [ ! -f sql/tags/uc_metadata.sql ]; then
    echo
    echo "[deploy] (5/7) sql/tags/uc_metadata.sql missing — skipping."
  else
    echo
    echo "[deploy] (5/7) Applying UC metadata (table comments + tags + certified) ..."
    python3 - <<'PY' "$PROFILE" "$WAREHOUSE_ID" "sql/tags/uc_metadata.sql" || \
      echo "[deploy] WARN: metadata pass had failures (continuing)."
import json, re, subprocess, sys

profile, warehouse, sql_path = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(sql_path).read()
text = re.sub(r'^\s*--.*$', '', text, flags=re.MULTILINE)
stmts = [s.strip() for s in re.split(r';\s*\n', text) if s.strip()]
ok = skipped = failed = 0
for stmt in stmts:
    body = json.dumps({"warehouse_id": warehouse, "statement": stmt, "wait_timeout": "30s"})
    p = subprocess.run(
        ["databricks", "--profile", profile, "api", "post",
         "/api/2.0/sql/statements", "--json", body],
        capture_output=True, text=True,
    )
    try:
        out = json.loads(p.stdout)
    except Exception:
        failed += 1; continue
    state = out.get("status", {}).get("state", "?")
    if state == "SUCCEEDED":
        ok += 1
    else:
        err = out.get("status", {}).get("error", {}).get("message", "")
        if "TABLE_OR_VIEW_NOT_FOUND" in err or "cannot be found" in err:
            skipped += 1
        else:
            failed += 1
print(f"[deploy]     metadata: {ok} ok, {skipped} skipped (table not built), {failed} failed")
PY
  fi

  # ---- 6. Trigger ETL (fire-and-forget) --------------------------------
  if [ "${SKIP_ETL:-0}" = "1" ]; then
    echo
    echo "[deploy] (6/7) SKIP_ETL=1 — skipping ETL trigger."
  else
    echo
    echo "[deploy] (6/7) Triggering ETL job '${JOB_NAME:-<unknown>}' (fire-and-forget) ..."
    databricks --profile "$PROFILE" bundle run care_gap_etl \
      --target "$TARGET" --var="app_prefix=${APP_PREFIX}" --no-wait || {
      echo "[deploy] WARN: ETL trigger failed. Run manually:"
      echo "[deploy]       databricks --profile $PROFILE bundle run care_gap_etl --target $TARGET --var=app_prefix=${APP_PREFIX}"
    }
  fi

  echo
  echo "[deploy] (7/7) Phase A done."
fi

# ============================================================
#  PHASE B — app lifecycle
# ============================================================
if [ "$RUN_PHASE_B" != "1" ]; then
  echo "[deploy] BUNDLE_ONLY=1 — skipping Phase B (app)."
  echo "[deploy] Done."
  exit 0
fi

APP_PAYLOAD_TEMPLATE="config/apps/care_gap_navigator.json"
if [ ! -f "$APP_PAYLOAD_TEMPLATE" ]; then
  echo "[deploy] ERROR: $APP_PAYLOAD_TEMPLATE not found."
  exit 1
fi
if [ -z "$GENIE_SPACE_ID" ]; then
  echo "[deploy] ERROR: could not resolve genie_space_id from bundle summary."
  echo "[deploy]        Check 'databricks bundle summary --target $TARGET' or set"
  echo "[deploy]        databricks.yml variables.genie_space_id."
  exit 1
fi

# Render the create/update payload by injecting the resolved name + space id
# into the template. The template ships with sentinel placeholders; jq rewrites
# them so callers can re-run with a different APP_PREFIX without editing JSON.
APP_PAYLOAD="$(jq \
  --arg name "$APP_NAME" \
  --arg sid  "$GENIE_SPACE_ID" \
  '.name = $name | .resources[0].genie_space.space_id = $sid' \
  "$APP_PAYLOAD_TEMPLATE")"

echo
echo "[deploy] (8/10) Ensuring App '${APP_NAME}' exists (with Genie binding) ..."
if databricks --profile "$PROFILE" apps get "$APP_NAME" >/dev/null 2>&1; then
  echo "[deploy]        App exists — applying update payload ..."
  databricks --profile "$PROFILE" apps update "$APP_NAME" --json "$APP_PAYLOAD" >/dev/null 2>&1 || \
    echo "[deploy] WARN: apps update returned non-zero (continuing — apps deploy may still proceed)."
else
  echo "[deploy]        App not found — creating ..."
  databricks --profile "$PROFILE" apps create --json "$APP_PAYLOAD" --no-compute >/dev/null
  echo "[deploy]        App created."
fi

# Push the latest code by binding the bundle-uploaded source path to the App.
echo
echo "[deploy] (9/10) Pushing latest code to App '${APP_NAME}' ..."
databricks --profile "$PROFILE" apps deploy "$APP_NAME" \
  --source-code-path "$APP_SOURCE_PATH" --no-wait >/dev/null 2>&1 || \
  echo "[deploy] WARN: apps deploy returned non-zero (continuing — start may still pick up new code)."

# Read state. Stop only if running so the start sees fresh code.
APP_STATE_RAW="$(databricks --profile "$PROFILE" apps get "$APP_NAME" 2>/dev/null \
  | jq -r '.compute_status.state // .app_status.state // "UNKNOWN"')"
echo
echo "[deploy] (10/10) App state: ${APP_STATE_RAW}"

if [ "$APP_STATE_RAW" = "RUNNING" ] || [ "$APP_STATE_RAW" = "STARTING" ]; then
  echo "[deploy]      Stopping for clean restart ..."
  databricks --profile "$PROFILE" apps stop "$APP_NAME" >/dev/null 2>&1 || \
    echo "[deploy] WARN: stop call failed (continuing)."
fi

echo "[deploy]      Starting App ..."
if ! databricks --profile "$PROFILE" apps start "$APP_NAME" >/dev/null 2>&1; then
  echo "[deploy] WARN: start call returned non-zero. Polling status ..."
fi

# Poll up to 5 minutes for RUNNING / ACTIVE.
deadline=$(( $(date +%s) + 300 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  APP_STATE_RAW="$(databricks --profile "$PROFILE" apps get "$APP_NAME" 2>/dev/null \
    | jq -r '.compute_status.state // .app_status.state // "UNKNOWN"')"
  if [ "$APP_STATE_RAW" = "RUNNING" ] || [ "$APP_STATE_RAW" = "ACTIVE" ]; then
    break
  fi
  if [ "$APP_STATE_RAW" = "ERROR" ] || [ "$APP_STATE_RAW" = "FAILED" ]; then
    echo "[deploy] ERROR: App entered $APP_STATE_RAW. Check:"
    echo "[deploy]   databricks --profile $PROFILE apps logs $APP_NAME"
    exit 1
  fi
  printf "."
  sleep 5
done
echo

APP_URL="$(databricks --profile "$PROFILE" apps get "$APP_NAME" 2>/dev/null \
  | jq -r '.url // empty')"

echo
echo "[deploy] Done."
[ "$RUN_PHASE_A" = "1" ] && echo "[deploy]   ETL job   : ${JOB_NAME:-<unknown>}  (running in background)"
echo "[deploy]   App       : ${APP_NAME}  (state: ${APP_STATE_RAW})"
[ -n "$APP_URL" ] && echo "[deploy]   App URL   : ${APP_URL}"
echo "[deploy]"
[ "$RUN_PHASE_A" = "1" ] && echo "[deploy] Watch ETL progress:" && \
  echo "[deploy]   databricks --profile $PROFILE bundle open --target $TARGET care_gap_etl"
echo "[deploy] Tail App logs:"
echo "[deploy]   databricks --profile $PROFILE apps logs $APP_NAME"
