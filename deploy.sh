#!/usr/bin/env bash
# ============================================================
#  Care Gap Navigator - Databricks bundle deploy
#  Profile: DEFAULT  (https://dbc-f6607f85-16a2.cloud.databricks.com)
#  Target : dev      (catalog: dais_hackathon_2026)
#
#  Steps the script performs:
#    1. Sanity-check CLI version + auth
#    2. bundle validate
#    3. bundle deploy
#    4. bundle run care_gap_etl --no-wait    (fire-and-forget, prints run URL)
#    5. apps stop  (best-effort — only if the app was already running)
#    6. apps start (waits for app to reach RUNNING, prints URL)
#
#  Skip steps with env vars:
#    SKIP_ETL=1   ./deploy.sh    # skip the ETL trigger
#    SKIP_APP=1   ./deploy.sh    # skip the App restart
# ============================================================
set -euo pipefail

PROFILE="${DATABRICKS_PROFILE:-DEFAULT}"
TARGET="${BUNDLE_TARGET:-dev}"

# Per-developer namespace for the deployed Bundle, Job, and App. Stamped onto
# the resource names via ${var.app_prefix} in databricks.yml so two
# side-by-side deployments don't collide. Override with: APP_PREFIX=foo ./deploy.sh
sanitize() { echo "$1" | tr 'A-Z' 'a-z' | tr -c 'a-z0-9-' '-' | sed 's/^-*//; s/-*$//'; }
APP_PREFIX="${APP_PREFIX:-$(sanitize "${USER:-pradeep}")}"
echo "[deploy] app_prefix     : $APP_PREFIX"

# Newer CLIs ship with refreshed signing keys for the Terraform binary
# download that bundle deploy uses internally. Older CLIs hit
# "openpgp: key expired". 0.260+ is known good.
MIN_CLI_MAJOR=0
MIN_CLI_MINOR=260

if ! command -v databricks >/dev/null 2>&1; then
  echo "[deploy] ERROR: databricks CLI not found on PATH."
  echo "[deploy]   Install it via: brew install databricks   (or)   curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh"
  exit 1
fi

CLI_VER="$(databricks --version | awk '{print $NF}' | sed 's/^v//')"
CLI_MAJOR="$(echo "$CLI_VER" | cut -d. -f1)"
CLI_MINOR="$(echo "$CLI_VER" | cut -d. -f2)"

if [ "$CLI_MAJOR" -lt "$MIN_CLI_MAJOR" ] \
   || { [ "$CLI_MAJOR" -eq "$MIN_CLI_MAJOR" ] && [ "$CLI_MINOR" -lt "$MIN_CLI_MINOR" ]; }; then
  echo "[deploy] ERROR: databricks CLI v$CLI_VER is too old."
  echo "[deploy]   Bundle deploys on this CLI hit 'openpgp: key expired' downloading Terraform."
  echo "[deploy]   Upgrade with: brew upgrade databricks"
  echo "[deploy]   Or:           curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh"
  exit 1
fi
echo "[deploy] databricks CLI : v$CLI_VER"

if ! databricks --profile "$PROFILE" current-user me >/dev/null 2>&1; then
  echo "[deploy] ERROR: profile '$PROFILE' is not authenticated."
  echo "[deploy]   Run: databricks auth login --profile $PROFILE"
  exit 1
fi

# -- 1. Validate ---------------------------------------------------------
echo
echo "[deploy] (1/5) Validating bundle ..."
databricks --profile "$PROFILE" bundle validate --target "$TARGET" \
  --var="app_prefix=${APP_PREFIX}"

# -- 2. Deploy -----------------------------------------------------------
echo
echo "[deploy] (2/5) Deploying bundle to target '$TARGET' ..."
databricks --profile "$PROFILE" bundle deploy --target "$TARGET" \
  --var="app_prefix=${APP_PREFIX}"

APP_NAME="${APP_PREFIX}-care-gap-navigator"
JOB_NAME="${APP_PREFIX}-care-gap-etl"

# -- 3. Trigger ETL (fire-and-forget) -----------------------------------
if [ "${SKIP_ETL:-0}" = "1" ]; then
  echo
  echo "[deploy] (3/5) SKIP_ETL=1 — skipping ETL trigger."
else
  echo
  echo "[deploy] (3/5) Triggering ETL job '${JOB_NAME}' (fire-and-forget) ..."
  # --no-wait returns immediately with the run id. The job runs in the
  # background; the caller can watch it in the Databricks Jobs UI.
  databricks --profile "$PROFILE" bundle run care_gap_etl \
    --target "$TARGET" --var="app_prefix=${APP_PREFIX}" \
    --no-wait || {
    echo "[deploy] WARN: ETL trigger failed. Continuing — bundle is deployed; "
    echo "[deploy]       you can run it manually with:"
    echo "[deploy]       databricks --profile $PROFILE bundle run care_gap_etl --target $TARGET --var=app_prefix=${APP_PREFIX}"
  }
fi

# -- 4 & 5. Restart App --------------------------------------------------
if [ "${SKIP_APP:-0}" = "1" ]; then
  echo
  echo "[deploy] (4/5) SKIP_APP=1 — skipping App restart."
  echo "[deploy] Done."
  exit 0
fi

# Resolve the App's URL up front so we can print it even if start spits warnings.
APP_URL="$(databricks --profile "$PROFILE" apps get "$APP_NAME" 2>/dev/null \
  | jq -r '.url // empty')"

# Read current state so we know whether to stop first. Fresh deploys won't
# have an existing running instance — that's fine; we just skip the stop.
APP_STATE="$(databricks --profile "$PROFILE" apps get "$APP_NAME" 2>/dev/null \
  | jq -r '.compute_status.state // .app_status.state // "UNKNOWN"')"
echo
echo "[deploy] (4/5) App '${APP_NAME}' state: ${APP_STATE}"

if [ "$APP_STATE" = "RUNNING" ] || [ "$APP_STATE" = "STARTING" ]; then
  echo "[deploy]       Stopping for clean restart so new code loads ..."
  databricks --profile "$PROFILE" apps stop "$APP_NAME" >/dev/null 2>&1 || \
    echo "[deploy] WARN: stop call failed (continuing — start will reconcile)."
fi

echo
echo "[deploy] (5/5) Starting App '${APP_NAME}' ..."
# 'apps start' on the modern CLI blocks until the App reaches RUNNING (or
# fails). On older CLIs it returns immediately and we need to poll. We try
# the blocking call first; if it returns instantly with a non-RUNNING state,
# we poll for up to 5 minutes.
if ! databricks --profile "$PROFILE" apps start "$APP_NAME" >/dev/null 2>&1; then
  echo "[deploy] WARN: start call returned non-zero. Polling status ..."
fi

deadline=$(( $(date +%s) + 300 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  APP_STATE="$(databricks --profile "$PROFILE" apps get "$APP_NAME" 2>/dev/null \
    | jq -r '.compute_status.state // .app_status.state // "UNKNOWN"')"
  if [ "$APP_STATE" = "RUNNING" ] || [ "$APP_STATE" = "ACTIVE" ]; then
    break
  fi
  if [ "$APP_STATE" = "ERROR" ] || [ "$APP_STATE" = "FAILED" ]; then
    echo "[deploy] ERROR: App entered $APP_STATE. Check `databricks apps logs $APP_NAME`."
    exit 1
  fi
  printf "."
  sleep 5
done
echo

if [ -z "$APP_URL" ] || [ "$APP_URL" = "null" ]; then
  APP_URL="$(databricks --profile "$PROFILE" apps get "$APP_NAME" 2>/dev/null \
    | jq -r '.url // empty')"
fi

echo
echo "[deploy] Done."
echo "[deploy]   ETL job   : ${JOB_NAME}  (running in background)"
echo "[deploy]   App       : ${APP_NAME}  (state: ${APP_STATE})"
[ -n "$APP_URL" ] && echo "[deploy]   App URL   : ${APP_URL}"
echo "[deploy]"
echo "[deploy] Watch ETL progress:"
echo "[deploy]   databricks --profile $PROFILE bundle open --target $TARGET care_gap_etl"
