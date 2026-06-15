"""Thin wrapper around databricks-sql-connector for the app's read paths."""

from __future__ import annotations

import os
from contextlib import contextmanager

from databricks import sql


@contextmanager
def cursor():
    conn = sql.connect(
        server_hostname=os.environ["DATABRICKS_HOST"].replace("https://", ""),
        http_path=f"/sql/1.0/warehouses/{os.environ['DATABRICKS_WAREHOUSE_ID']}",
        access_token=os.environ["DATABRICKS_TOKEN"],
    )
    try:
        yield conn.cursor()
    finally:
        conn.close()
