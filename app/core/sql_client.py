"""Framework-neutral Databricks SQL helpers."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from functools import lru_cache

import pandas as pd
from cachetools import TTLCache, cached
from databricks import sql
from databricks.sdk.core import Config

log = logging.getLogger(__name__)

_QUERY_CACHE = TTLCache(maxsize=128, ttl=300)


@lru_cache(maxsize=1)
def _config() -> Config | None:
    """SDK Config that resolves auth from env vars or ~/.databrickscfg."""
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
    conn = sql.connect(
        server_hostname=_host(),
        http_path=f"/sql/1.0/warehouses/{_warehouse_id()}",
        credentials_provider=(lambda: cfg.authenticate()) if cfg is not None else None,
    )
    try:
        yield conn.cursor()
    finally:
        conn.close()


@cached(_QUERY_CACHE)
def query_df(sql_text: str, params: tuple | None = None) -> pd.DataFrame:
    """Run a SELECT and return a DataFrame. Empty DataFrame on any failure."""
    if not is_configured():
        log.warning("Databricks SQL is not configured; returning empty DataFrame")
        return pd.DataFrame()
    try:
        with cursor() as cur:
            cur.execute(sql_text, list(params) if params else None)
            cols = [c[0] for c in cur.description] if cur.description else []
            return pd.DataFrame(cur.fetchall(), columns=cols)
    except Exception as e:  # noqa: BLE001
        log.warning("query failed: %s", e)
        return pd.DataFrame()


def execute(sql_text: str, params: tuple | None = None) -> bool:
    """Run a non-SELECT statement. Returns True on success."""
    if not is_configured():
        log.warning("Databricks SQL is not configured; skipping execute")
        return False
    try:
        with cursor() as cur:
            cur.execute(sql_text, list(params) if params else None)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("execute failed: %s", e)
        return False
