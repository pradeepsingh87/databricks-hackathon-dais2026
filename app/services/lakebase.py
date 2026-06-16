"""Persistence for user actions: overrides, scenarios.

Backed by `<catalog>.lakebase.*` Delta tables (DDL in sql/lakebase/schema.sql).
All writers return bool so pages can show a clean success/failure UX without
try/except scattered around.

Note: the column is `user_name` (not `user`); `user` is reserved in Spark SQL.
"""

from __future__ import annotations

import json

import pandas as pd

from ._shared_config import fq_schema

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


# ----- NACHC Root-Cause Categorisations ----------------------------------
# Each row classifies one cell or district as a Data Gap, Service Delivery
# Gap, or Engagement Gap, with optional severity + planner note. Rendered on
# the side-panel component on every Gold-data page.

CATEGORY_VALUES = ("data", "service", "engagement")
SEVERITY_VALUES = ("low", "medium", "high")


def add_gap_categorization(
    user: str,
    capability: str,
    category: str,
    *,
    state: str | None = None,
    district: str | None = None,
    h3_cell: str | None = None,
    severity: str | None = None,
    note: str | None = None,
) -> bool:
    """Persist one root-cause categorization.

    `category` must be one of CATEGORY_VALUES. Returns False if not.
    The cell-or-district choice is up to the caller — both can be NULL when
    the planner is categorising at the state/capability grain.
    """
    if category not in CATEGORY_VALUES:
        return False
    if severity is not None and severity not in SEVERITY_VALUES:
        return False
    return execute(
        f"INSERT INTO {LAKEBASE}.gap_categorizations "
        f"(user_name, capability, state, district, h3_cell, category, severity, note, created_at) "
        f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, current_timestamp())",
        (user, capability, state, district, h3_cell, category, severity, note),
    )


def list_gap_categorizations(
    user: str | None = None,
    *,
    capability: str | None = None,
    state: str | None = None,
) -> pd.DataFrame:
    """Read recent categorizations. All filters are optional and AND'd."""
    where_parts: list[str] = []
    params: list = []
    if user:
        where_parts.append("user_name = ?")
        params.append(user)
    if capability:
        where_parts.append("capability = ?")
        params.append(capability)
    if state:
        where_parts.append("state = ?")
        params.append(state)
    where_sql = "WHERE " + " AND ".join(where_parts) if where_parts else ""
    return query_df(
        f"""
        SELECT id, user_name, capability, state, district, h3_cell,
               category, severity, note, created_at
        FROM {LAKEBASE}.gap_categorizations
        {where_sql}
        ORDER BY created_at DESC
        LIMIT 200
        """,
        tuple(params) if params else None,
    )


# ----- Bookmarks (filter-state snapshots for multi-team collaboration) ---

def save_bookmark(user: str, name: str, filters: dict, *, shared: bool = False) -> bool:
    """Snapshot the current sidebar filter set so a teammate can land on the
    same view. `shared=True` makes the bookmark visible to everyone."""
    if not name or not name.strip():
        return False
    return execute(
        f"INSERT INTO {LAKEBASE}.bookmarks "
        f"(user_name, name, filters_json, shared, created_at) "
        f"VALUES (?, ?, ?, ?, current_timestamp())",
        (user, name, json.dumps(filters), shared),
    )


def list_bookmarks(user: str | None = None, *, include_shared: bool = True) -> pd.DataFrame:
    """List my bookmarks (and optionally everyone's shared ones)."""
    if user and include_shared:
        return query_df(
            f"SELECT id, user_name, name, filters_json, shared, created_at "
            f"FROM {LAKEBASE}.bookmarks "
            f"WHERE user_name = ? OR shared = TRUE "
            f"ORDER BY created_at DESC LIMIT 200",
            (user,),
        )
    if user:
        return query_df(
            f"SELECT id, user_name, name, filters_json, shared, created_at "
            f"FROM {LAKEBASE}.bookmarks WHERE user_name = ? "
            f"ORDER BY created_at DESC LIMIT 200",
            (user,),
        )
    return query_df(
        f"SELECT id, user_name, name, filters_json, shared, created_at "
        f"FROM {LAKEBASE}.bookmarks ORDER BY created_at DESC LIMIT 200"
    )
