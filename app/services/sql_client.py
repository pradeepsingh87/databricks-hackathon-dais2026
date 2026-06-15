"""Thin wrapper around databricks-sql-connector for the app's read paths.

Returns pandas DataFrames so pages don't have to deal with cursor tuples.
On any error (missing table, no warehouse running, no auth), returns an empty
DataFrame and logs the reason — pages then show their empty-state UI.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager

import pandas as pd
import streamlit as st
from databricks import sql

log = logging.getLogger(__name__)


def _host() -> str:
    return os.environ.get("DATABRICKS_HOST", "").replace("https://", "").rstrip("/")


def _warehouse_id() -> str:
    return os.environ.get("DATABRICKS_WAREHOUSE_ID", "")


def _token() -> str:
    return os.environ.get("DATABRICKS_TOKEN", "")


def is_configured() -> bool:
    return all([_host(), _warehouse_id(), _token()])


@contextmanager
def cursor():
    conn = sql.connect(
        server_hostname=_host(),
        http_path=f"/sql/1.0/warehouses/{_warehouse_id()}",
        access_token=_token(),
    )
    try:
        yield conn.cursor()
    finally:
        conn.close()


@st.cache_data(ttl=300, show_spinner=False)
def query_df(sql_text: str, params: tuple | None = None) -> pd.DataFrame:
    """Run a SELECT and return a DataFrame. Empty DF on any failure."""
    if not is_configured():
        log.warning("DATABRICKS_HOST / WAREHOUSE_ID / TOKEN not set — returning empty DF")
        return pd.DataFrame()
    try:
        with cursor() as cur:
            cur.execute(sql_text, list(params) if params else None)
            cols = [c[0] for c in cur.description] if cur.description else []
            return pd.DataFrame(cur.fetchall(), columns=cols)
    except Exception as e:  # noqa: BLE001 — display layer; we surface the message
        log.warning("query failed: %s", e)
        st.session_state["_last_query_error"] = str(e)
        return pd.DataFrame()


def execute(sql_text: str, params: tuple | None = None) -> bool:
    """Run a non-SELECT. Returns True on success."""
    if not is_configured():
        return False
    try:
        with cursor() as cur:
            cur.execute(sql_text, list(params) if params else None)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("execute failed: %s", e)
        st.session_state["_last_query_error"] = str(e)
        return False
