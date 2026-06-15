#!/usr/bin/env bash
# ============================================================
#  Care Gap Navigator - Databricks bundle deploy
#  Profile: DEFAULT  (https://dbc-f6607f85-16a2.cloud.databricks.com)
#  Target : dev      (catalog: dais_hackathon_2026)
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

echo
echo "[deploy] Validating bundle ..."
databricks --profile "$PROFILE" bundle validate --target "$TARGET" \
  --var="app_prefix=${APP_PREFIX}"

echo
echo "[deploy] Deploying bundle to target '$TARGET' ..."
databricks --profile "$PROFILE" bundle deploy --target "$TARGET" \
  --var="app_prefix=${APP_PREFIX}"

echo
echo "[deploy] Done."
echo "[deploy] Resources deployed: ${APP_PREFIX}-care-gap-navigator, ${APP_PREFIX}-care-gap-etl"
echo "[deploy] To run the ETL job:"
echo "[deploy]   databricks --profile $PROFILE bundle run care_gap_etl --target $TARGET --var=app_prefix=${APP_PREFIX}"
