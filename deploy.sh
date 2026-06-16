#!/usr/bin/env bash
# ============================================================
#  Care Gap Navigator — full-stack Databricks deploy
#  Profile: DEFAULT  (override via DATABRICKS_PROFILE)
#  Target : dev      (override via BUNDLE_TARGET)
#
#  What this does (in order):
#    1. CLI version + auth preflight
#    2. bundle validate
#    3. bundle deploy                  (creates/updates the Job AND the App
#                                       resource — including the App↔Genie
#                                       binding and the attached
#                                       git_repository declared in
#                                       config/resources/app.yml)
#    3b. apps deploy --json            (creates an App deployment from Git;
#                                       required because this workspace
#                                       enforces a "Git source required"
#                                       policy on Apps)
#    4. setup_uc.sh                    (creates UC schemas + Lakebase tables)
#    5. setup_genie.sh                 (idempotent Genie space provision)
#    6. apply uc_metadata.sql          (table comments + tags + certified)
#    7. bundle run care_gap_etl --no-wait
#    8. apps stop  +  apps start       (clean restart so new deployment loads)
#
#  Skip / customise via env vars:
#    SKIP_UC=1          skip UC schema + Lakebase table creation
#    SKIP_GENIE=1       skip Genie space provision
#    SKIP_METADATA=1    skip table comments + tags + certified pass
#    SKIP_ETL=1         skip ETL trigger
#    SKIP_APP=1         skip App restart
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

# ---- 1. Validate -------------------------------------------------------
echo
echo "[deploy] (1/8) Validating bundle ..."
databricks --profile "$PROFILE" bundle validate --target "$TARGET" \
  --var="app_prefix=${APP_PREFIX}"

# ---- 2. Deploy ---------------------------------------------------------
# `bundle deploy` creates/updates both the Job and the App *resource*
# (including the Genie binding and the attached git_repository declared in
# config/resources/app.yml). It does NOT create an App deployment that
# actually serves code — that's handled in step 2b below, which posts a
# git_source deployment so the workspace's "Git required" policy is
# satisfied.
echo
echo "[deploy] (2/8) Deploying bundle to target '$TARGET' ..."
databricks --profile "$PROFILE" bundle deploy --target "$TARGET" \
  --var="app_prefix=${APP_PREFIX}"

# Resolve actual deployed names from the bundle (dev-mode adds an extra
# prefix that we cannot reconstruct from APP_PREFIX alone — must read it
# back).
SUMMARY="$(databricks --profile "$PROFILE" bundle summary --target "$TARGET" \
  --var="app_prefix=${APP_PREFIX}" -o json 2>/dev/null)"
APP_NAME="$(echo "$SUMMARY" | jq -r '.resources.apps.care_gap_navigator.name // empty')"
JOB_NAME="$(echo "$SUMMARY" | jq -r '.resources.jobs.care_gap_etl.name // empty')"
APP_GIT_BRANCH="$(echo "$SUMMARY" | jq -r '.variables.app_git_branch.value // "main"')"
APP_GIT_SUBPATH="app"

if [ -z "$APP_NAME" ]; then
  echo "[deploy] ERROR: could not resolve the App name from bundle summary."
  echo "[deploy]        Check 'databricks bundle summary --target $TARGET' manually."
  exit 1
fi
echo "[deploy] resolved App  : $APP_NAME"
echo "[deploy] resolved Job  : $JOB_NAME"
echo "[deploy] git source     : branch=$APP_GIT_BRANCH path=$APP_GIT_SUBPATH"

# ---- 2b. Create an app deployment from Git ------------------------------
# `bundle deploy` creates the App *resource* and attaches the git_repository
# (config/resources/app.yml), but it does NOT create a deployment that
# actually serves code. The workspace's "Git required" policy means we
# can't deploy from the workspace-uploaded source path — we have to push a
# git_source deployment that points at the GitHub repo + branch.
echo
echo "[deploy] (2b/8) Creating App deployment from Git (branch=$APP_GIT_BRANCH) ..."
DEPLOY_PAYLOAD="$(jq -n \
  --arg branch  "$APP_GIT_BRANCH" \
  --arg subpath "$APP_GIT_SUBPATH" \
  '{mode: "SNAPSHOT", git_source: {branch: $branch, source_code_path: $subpath}}')"
databricks --profile "$PROFILE" apps deploy "$APP_NAME" \
  --json "$DEPLOY_PAYLOAD" --no-wait >/dev/null 2>&1 || \
  echo "[deploy] WARN: apps deploy returned non-zero (continuing — start may still pick up new code)."

# ---- 3. UC schemas + Lakebase ------------------------------------------
if [ "${SKIP_UC:-0}" = "1" ]; then
  echo
  echo "[deploy] (3/8) SKIP_UC=1 — skipping UC + Lakebase setup."
else
  echo
  echo "[deploy] (3/8) Provisioning UC schemas + Lakebase tables ..."
  ./scripts/setup_uc.sh
fi

# ---- 4. Genie space ----------------------------------------------------
if [ "${SKIP_GENIE:-0}" = "1" ]; then
  echo
  echo "[deploy] (4/8) SKIP_GENIE=1 — skipping Genie space provision."
else
  echo
  echo "[deploy] (4/8) Provisioning Genie space ..."
  ./scripts/setup_genie.sh || \
    echo "[deploy] WARN: Genie provision returned non-zero (continuing)."
fi

# ---- 5. UC metadata (comments + tags + certified) ---------------------
# Best-effort; some ALTERs SKIP cleanly when target tables aren't materialised
# yet (medical_desert_*, silver_facilities_geo). The Python helper handles
# UTF-8 in COMMENTs, which the shell-piped jq pattern can't.
if [ "${SKIP_METADATA:-0}" = "1" ]; then
  echo
  echo "[deploy] (5/8) SKIP_METADATA=1 — skipping UC metadata pass."
elif [ ! -f sql/tags/uc_metadata.sql ]; then
  echo
  echo "[deploy] (5/8) sql/tags/uc_metadata.sql missing — skipping."
else
  echo
  echo "[deploy] (5/8) Applying UC metadata (table comments + tags + certified) ..."
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

# ---- 6. Trigger ETL (fire-and-forget) ----------------------------------
if [ "${SKIP_ETL:-0}" = "1" ]; then
  echo
  echo "[deploy] (6/8) SKIP_ETL=1 — skipping ETL trigger."
else
  echo
  echo "[deploy] (6/8) Triggering ETL job '${JOB_NAME}' (fire-and-forget) ..."
  databricks --profile "$PROFILE" bundle run care_gap_etl \
    --target "$TARGET" --var="app_prefix=${APP_PREFIX}" --no-wait || {
    echo "[deploy] WARN: ETL trigger failed. Run manually:"
    echo "[deploy]       databricks --profile $PROFILE bundle run care_gap_etl --target $TARGET --var=app_prefix=${APP_PREFIX}"
  }
fi

# ---- 7-8. App restart --------------------------------------------------
# Step 2b created a fresh git_source deployment. Restart so the running
# container picks it up. (`apps deploy --no-wait` doesn't bounce the app.)
if [ "${SKIP_APP:-0}" = "1" ]; then
  echo
  echo "[deploy] (7/8) SKIP_APP=1 — skipping App restart."
  echo "[deploy] Done."
  exit 0
fi

# Read state. Stop only if running so the start sees fresh code.
APP_STATE_RAW="$(databricks --profile "$PROFILE" apps get "$APP_NAME" 2>/dev/null \
  | jq -r '.compute_status.state // .app_status.state // "UNKNOWN"')"
echo
echo "[deploy] (7/8) App state: ${APP_STATE_RAW}"

if [ "$APP_STATE_RAW" = "RUNNING" ] || [ "$APP_STATE_RAW" = "STARTING" ]; then
  echo "[deploy]      Stopping for clean restart ..."
  databricks --profile "$PROFILE" apps stop "$APP_NAME" >/dev/null 2>&1 || \
    echo "[deploy] WARN: stop call failed (continuing)."
fi

echo "[deploy] (8/8) Starting App ..."
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
echo "[deploy]   ETL job   : ${JOB_NAME}  (running in background)"
echo "[deploy]   App       : ${APP_NAME}  (state: ${APP_STATE_RAW})"
[ -n "$APP_URL" ] && echo "[deploy]   App URL   : ${APP_URL}"
echo "[deploy]"
echo "[deploy] Watch ETL progress:"
echo "[deploy]   databricks --profile $PROFILE bundle open --target $TARGET care_gap_etl"
echo "[deploy] Tail App logs:"
echo "[deploy]   databricks --profile $PROFILE apps logs $APP_NAME"
