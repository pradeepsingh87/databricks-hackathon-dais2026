"""Persistence for user actions (overrides, scenarios) and low-latency reads
of Gold care-score data — all backed by Databricks Lakebase (PostgreSQL-
compatible managed DB).

DDL for all tables lives in sql/lakebase/schema.sql.
Gold mirror tables are populated by pipelines/gold/sync_to_lakebase.py.

Connection is configured via environment variables:
  LAKEBASE_HOST      — Lakebase read-write hostname
  LAKEBASE_PORT      — port (default 5432)
  LAKEBASE_DATABASE  — database name (default postgres)

Authentication uses short-lived OAuth tokens generated at call time via
the Databricks SDK (WorkspaceClient). No static password is required.

All writers return bool for clean success/failure UX.
All readers return an empty DataFrame on any connection failure.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Generator
from contextlib import contextmanager

import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st

log = logging.getLogger(__name__)

_INSTANCE_NAME = "care-gap-lakebase"


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _is_configured() -> bool:
    return bool(os.environ.get("LAKEBASE_HOST"))


def _fresh_token() -> str:
    """Generate a short-lived OAuth token scoped to the Lakebase instance."""
    import uuid

    from databricks.sdk import WorkspaceClient
    wc = WorkspaceClient()
    cred = wc.database.generate_database_credential(
        instance_names=[_INSTANCE_NAME],
        request_id=str(uuid.uuid4()),
    )
    return cred.token


def _lakebase_username() -> str:
    """Return the current Databricks user's email for PG auth."""
    from databricks.sdk import WorkspaceClient

    return WorkspaceClient().current_user.me().user_name


@contextmanager
def _conn() -> Generator:
    """Yield a psycopg2 connection; close it on exit."""
    connection = psycopg2.connect(
        host=os.environ["LAKEBASE_HOST"],
        port=int(os.environ.get("LAKEBASE_PORT", "5432")),
        dbname=os.environ.get("LAKEBASE_DATABASE", "postgres"),
        user=_lakebase_username(),
        password=_fresh_token(),
        sslmode="require",
        connect_timeout=10,
    )
    try:
        yield connection
    finally:
        connection.close()


def _query_df(sql: str, params: tuple | None = None) -> pd.DataFrame:
    """Execute a SELECT and return a DataFrame. Empty on any failure."""
    if not _is_configured():
        log.warning("Lakebase env vars not set — returning empty DataFrame")
        return pd.DataFrame()
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                return pd.DataFrame([dict(r) for r in rows])
    except Exception as exc:  # noqa: BLE001
        log.warning("lakebase query failed: %s", exc)
        return pd.DataFrame()


def _execute(sql: str, params: tuple | None = None) -> bool:
    """Execute a non-SELECT statement. Returns True on success."""
    if not _is_configured():
        return False
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("lakebase execute failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------

def add_override(user: str, facility_id: str, capability: str, note: str) -> bool:
    if not note or not note.strip():
        return False
    return _execute(
        "INSERT INTO overrides (\"user\", facility_id, capability, note) "
        "VALUES (%s, %s, %s, %s)",
        (user, facility_id, capability, note),
    )


def list_overrides(user: str | None = None) -> pd.DataFrame:
    if user:
        return _query_df(
            "SELECT id, \"user\", facility_id, capability, note, created_at "
            "FROM overrides WHERE \"user\" = %s ORDER BY created_at DESC",
            (user,),
        )
    return _query_df(
        "SELECT id, \"user\", facility_id, capability, note, created_at "
        "FROM overrides ORDER BY created_at DESC LIMIT 200"
    )


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def save_scenario(user: str, name: str, payload: dict) -> bool:
    if not name or not name.strip():
        return False
    return _execute(
        "INSERT INTO scenarios (\"user\", name, payload) VALUES (%s, %s, %s)",
        (user, name, json.dumps(payload)),
    )


def list_scenarios(user: str | None = None) -> pd.DataFrame:
    if user:
        return _query_df(
            "SELECT id, \"user\", name, payload, created_at FROM scenarios "
            "WHERE \"user\" = %s ORDER BY created_at DESC",
            (user,),
        )
    return _query_df(
        "SELECT id, \"user\", name, payload, created_at FROM scenarios "
        "ORDER BY created_at DESC LIMIT 200"
    )


# ---------------------------------------------------------------------------
# Gold mirror reads  (low-latency alternative to hitting the SQL warehouse)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def fetch_h3_scores(
    capability: str,
    resolution: int = 7,
    state: str | None = None,
) -> pd.DataFrame:
    """H3 cell-level care scores from the Gold mirror table."""
    if state:
        return _query_df(
            "SELECT h3_cell, score, confidence, n_facilities, evidence_state "
            "FROM h3_care_score "
            "WHERE capability = %s AND h3_resolution = %s AND state = %s",
            (capability, resolution, state),
        )
    return _query_df(
        "SELECT h3_cell, score, confidence, n_facilities, evidence_state "
        "FROM h3_care_score "
        "WHERE capability = %s AND h3_resolution = %s",
        (capability, resolution),
    )


@st.cache_data(ttl=300, show_spinner=False)
def fetch_state_rollup(capability: str) -> pd.DataFrame:
    """State-level care score rollup from the Gold mirror table."""
    return _query_df(
        "SELECT state, score, confidence, n_facilities, n_data_deficient_cells "
        "FROM care_score_by_state "
        "WHERE capability = %s ORDER BY score ASC",
        (capability,),
    )


@st.cache_data(ttl=300, show_spinner=False)
def fetch_district_rollup(capability: str, state: str | None = None) -> pd.DataFrame:
    """District-level care score rollup from the Gold mirror table."""
    if state:
        return _query_df(
            "SELECT state, district, score, confidence, n_facilities, n_data_deficient_cells "
            "FROM care_score_by_district "
            "WHERE capability = %s AND state = %s ORDER BY score ASC",
            (capability, state),
        )
    return _query_df(
        "SELECT state, district, score, confidence, n_facilities, n_data_deficient_cells "
        "FROM care_score_by_district "
        "WHERE capability = %s ORDER BY score ASC",
        (capability,),
    )
