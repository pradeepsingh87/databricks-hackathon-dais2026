"""Subset of pipelines.common.config that the Streamlit app depends on.

Vendored so the deployed App container does not need the pipelines/ tree on
its Python path. The pipelines layer remains the source of truth for ETL —
this file is only for app-side consumers (services/gold.py, services/lakebase.py).
Keep these constants and helpers in sync with pipelines/common/config.py.
"""

from __future__ import annotations

import os

DEFAULT_CATALOG = "dais_hackathon_2026"
BRONZE_SCHEMA = "bronze"
SILVER_SCHEMA = "silver"
GOLD_SCHEMA = "gold"
LAKEBASE_SCHEMA = "lakebase"

CAPABILITIES = ["icu", "maternity", "emergency", "oncology", "trauma", "nicu"]


def get_catalog() -> str:
    return (
        os.environ.get("APP_CATALOG")
        or os.environ.get("UC_CATALOG")
        or DEFAULT_CATALOG
    )


def schema_name(layer: str) -> str:
    names = {
        "bronze": BRONZE_SCHEMA,
        "silver": SILVER_SCHEMA,
        "gold": GOLD_SCHEMA,
        "lakebase": LAKEBASE_SCHEMA,
    }
    try:
        return names[layer]
    except KeyError as exc:
        raise KeyError(f"Unknown schema layer '{layer}'") from exc


def fq_schema(layer: str, catalog: str | None = None) -> str:
    return f"{catalog or get_catalog()}.{schema_name(layer)}"
