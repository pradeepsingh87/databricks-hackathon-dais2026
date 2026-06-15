"""Shared pipeline config — table names, H3 resolutions, capabilities."""

from __future__ import annotations

CATALOG = "hackathon"
SCHEMA = "care_gap"

CAPABILITIES = ["icu", "maternity", "emergency", "oncology", "trauma", "nicu"]

# H3 resolution 7 ~ 5 km edge — good default for district-level planning.
# Resolution 8 ~ 0.5 km for city drill-down.
H3_RESOLUTIONS = [6, 7, 8]
DEFAULT_H3_RESOLUTION = 7


def t(name: str) -> str:
    """Fully-qualified table name."""
    return f"{CATALOG}.{SCHEMA}.{name}"
