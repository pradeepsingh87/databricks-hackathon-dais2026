"""Persistence for user actions: notes, overrides, saved scenarios."""

from __future__ import annotations

from .sql_client import cursor


def save_scenario(user: str, name: str, payload: dict) -> None:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO lakebase.scenarios (user, name, payload, created_at) "
            "VALUES (?, ?, ?, current_timestamp())",
            [user, name, payload],
        )


def list_scenarios(user: str):
    with cursor() as cur:
        cur.execute(
            "SELECT id, name, created_at FROM lakebase.scenarios "
            "WHERE user = ? ORDER BY created_at DESC",
            [user],
        )
        return cur.fetchall()


def add_override(user: str, facility_id: str, capability: str, note: str) -> None:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO lakebase.overrides (user, facility_id, capability, note, created_at) "
            "VALUES (?, ?, ?, ?, current_timestamp())",
            [user, facility_id, capability, note],
        )
