"""Read-side services backed by Gold tables."""

from __future__ import annotations

from .sql_client import cursor


def fetch_h3_scores(capability: str, resolution: int = 7):
    """Return [(h3_cell, score, confidence, n_facilities), ...] for a capability."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT h3_cell, score, confidence, n_facilities
            FROM gold.h3_care_score
            WHERE capability = ? AND h3_resolution = ?
            """,
            [capability, resolution],
        )
        return cur.fetchall()


def fetch_facilities_in_cell(h3_cell: str, capability: str):
    """List facility records (with citations) backing a given H3 aggregate."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT facility_id, name, state, city, evidence_strength, citation
            FROM silver.facility_claims
            WHERE h3_cell = ? AND capability = ?
            ORDER BY evidence_strength DESC
            """,
            [h3_cell, capability],
        )
        return cur.fetchall()
