#!/usr/bin/env bash
# Trigger the bronze->silver->gold ETL via the bundle-defined job.
set -euo pipefail
databricks bundle run care_gap_etl "$@"
