"""Persistence for user actions: overrides, scenarios.

Backed by `dais_hackathon_2026.lakebase.*` Delta tables (DDL in
sql/lakebase/schema.sql). All writers return bool so pages can show a clean
success/failure UX without try/except scattered around.
"""

from __future__ import annotations

import json

import pandas as pd

from .sql_client import execute, query_df

CATALOG = "dais_hackathon_2026"
LAKEBASE = f"{CATALOG}.lakebase"


# ----- Overrides ---------------------------------------------------------

def add_override(user: str, facility_id: str, capability: str, note: str) -> bool:
    if not note or not note.strip():
        return False
    return execute(
        f"INSERT INTO {LAKEBASE}.overrides (user, facility_id, capability, note, created_at) "
        f"VALUES (?, ?, ?, ?, current_timestamp())",
        (user, facility_id, capability, note),
    )


def list_overrides(user: str | None = None) -> pd.DataFrame:
    if user:
        return query_df(
            f"SELECT id, user, facility_id, capability, note, created_at "
            f"FROM {LAKEBASE}.overrides WHERE user = ? ORDER BY created_at DESC",
            (user,),
        )
    return query_df(
        f"SELECT id, user, facility_id, capability, note, created_at "
        f"FROM {LAKEBASE}.overrides ORDER BY created_at DESC LIMIT 200"
    )


# ----- Scenarios ---------------------------------------------------------

def save_scenario(user: str, name: str, payload: dict) -> bool:
    if not name or not name.strip():
        return False
    return execute(
        f"INSERT INTO {LAKEBASE}.scenarios (user, name, payload, created_at) "
        f"VALUES (?, ?, ?, current_timestamp())",
        (user, name, json.dumps(payload)),
    )


def list_scenarios(user: str | None = None) -> pd.DataFrame:
    if user:
        return query_df(
            f"SELECT id, user, name, payload, created_at FROM {LAKEBASE}.scenarios "
            f"WHERE user = ? ORDER BY created_at DESC",
            (user,),
        )
    return query_df(
        f"SELECT id, user, name, payload, created_at FROM {LAKEBASE}.scenarios "
        f"ORDER BY created_at DESC LIMIT 200"
    )
