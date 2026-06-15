"""Shared app + pipeline config."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # noqa: BLE001
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

DEFAULT_CATALOG = "dais_hackathon_2026"
BRONZE_SCHEMA = "bronze"
SILVER_SCHEMA = "silver"
GOLD_SCHEMA = "gold"
LAKEBASE_SCHEMA = "lakebase"

CAPABILITIES = ["icu", "maternity", "emergency", "oncology", "trauma", "nicu"]

# H3 resolution 7 ~ 5 km edge — good default for district-level planning.
# Resolution 8 ~ 0.5 km for city drill-down.
H3_RESOLUTIONS = [6, 7, 8]
DEFAULT_H3_RESOLUTION = 7


def get_catalog() -> str:
    """Resolve the active Unity Catalog name with backward-compatible fallbacks."""
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


def t(name: str, layer: str = "gold", catalog: str | None = None) -> str:
    """Fully-qualified table name."""
    return f"{fq_schema(layer, catalog)}.{name}"
