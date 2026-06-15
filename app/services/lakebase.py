"""Persistence for user actions: overrides, scenarios.

Backed by `<catalog>.lakebase.*` Delta tables (DDL in sql/lakebase/schema.sql).
All writers return bool so pages can show a clean success/failure UX without
try/except scattered around.

Note: the column is `user_name` (not `user`); `user` is reserved in Spark SQL.
"""

from __future__ import annotations

import json

import pandas as pd

from pipelines.common.config import fq_schema

from .sql_client import execute, query_df

LAKEBASE = fq_schema("lakebase")


# ----- Overrides ---------------------------------------------------------

def add_override(user: str, facility_id: str, capability: str, note: str) -> bool:
    if not note or not note.strip():
        return False
    return execute(
        f"INSERT INTO {LAKEBASE}.overrides "
        f"(user_name, facility_id, capability, note, created_at) "
        f"VALUES (?, ?, ?, ?, current_timestamp())",
        (user, facility_id, capability, note),
    )


def list_overrides(user: str | None = None) -> pd.DataFrame:
    if user:
        return query_df(
            f"SELECT id, user_name, facility_id, capability, note, created_at "
            f"FROM {LAKEBASE}.overrides WHERE user_name = ? ORDER BY created_at DESC",
            (user,),
        )
    return query_df(
        f"SELECT id, user_name, facility_id, capability, note, created_at "
        f"FROM {LAKEBASE}.overrides ORDER BY created_at DESC LIMIT 200"
    )


# ----- Scenarios ---------------------------------------------------------

def save_scenario(user: str, name: str, payload: dict) -> bool:
    if not name or not name.strip():
        return False
    return execute(
        f"INSERT INTO {LAKEBASE}.scenarios (user_name, name, payload, created_at) "
        f"VALUES (?, ?, ?, current_timestamp())",
        (user, name, json.dumps(payload)),
    )


def list_scenarios(user: str | None = None) -> pd.DataFrame:
    if user:
        return query_df(
            f"SELECT id, user_name, name, payload, created_at FROM {LAKEBASE}.scenarios "
            f"WHERE user_name = ? ORDER BY created_at DESC",
            (user,),
        )
    return query_df(
        f"SELECT id, user_name, name, payload, created_at FROM {LAKEBASE}.scenarios "
        f"ORDER BY created_at DESC LIMIT 200"
    )
