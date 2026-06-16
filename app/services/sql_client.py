"""Thin wrapper around databricks-sql-connector for the app's read paths.

Returns pandas DataFrames so pages don't have to deal with cursor tuples.
On any error (missing table, no warehouse running, no auth), returns an empty
DataFrame and logs the reason — pages then show their empty-state UI.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from functools import lru_cache

import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _config() -> Config | None:
    """SDK Config that resolves auth from env vars or ~/.databrickscfg.

    Returns None when no auth source is available, so callers can degrade
    to an empty-state UI instead of raising at import time.
    """
    try:
        cfg = Config()
        cfg.authenticate()
        return cfg
    except Exception:
        return None


def _host() -> str:
    cfg = _config()
    host = cfg.host if cfg is not None else os.environ.get("DATABRICKS_HOST", "")
    return host.replace("https://", "").rstrip("/")


def _warehouse_id() -> str:
    return os.environ.get("DATABRICKS_WAREHOUSE_ID", "")


def is_configured() -> bool:
    return all([_host(), _warehouse_id(), _config() is not None])


@contextmanager
def cursor():
    cfg = _config()
    # databricks-sql-connector v3+ accepts a credentials_provider callable
    # that returns a header-injection function. Reusing the SDK Config keeps
    # OAuth refresh + PAT both working with no token plumbing here.
    conn = sql.connect(
        server_hostname=_host(),
        http_path=f"/sql/1.0/warehouses/{_warehouse_id()}",
        credentials_provider=(lambda: cfg.authenticate) if cfg is not None else None,
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
