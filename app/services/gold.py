"""Read-side services backed by Gold (and Silver, until claim extraction lands).

Every function returns a pandas DataFrame — empty if the underlying table
isn't deployed yet, so pages can show their own empty-state.

Tables this layer expects (target catalog: dais_hackathon_2026):
- silver.silver_facilities         — already produced by the ingestion framework
- gold.h3_care_score               — produced by Gold (planned)
- gold.care_score_by_state         — produced by Gold (planned)
- gold.care_score_by_district      — produced by Gold (planned)
"""

from __future__ import annotations

import pandas as pd

from pipelines.common.config import CAPABILITIES, fq_schema

from .sql_client import query_df

SILVER = fq_schema("silver")
GOLD = fq_schema("gold")


def list_capabilities() -> list[str]:
    """Drive the sidebar selector. Stay aligned with capability_taxonomy.yml."""
    return CAPABILITIES


def list_states() -> list[str]:
    """Distinct canonicalized states from Silver. Empty list if Silver isn't built yet."""
    df = query_df(
        f"SELECT DISTINCT state FROM {SILVER}.silver_facilities "
        f"WHERE state IS NOT NULL ORDER BY state"
    )
    return df["state"].tolist() if not df.empty else []


def fetch_h3_scores(capability: str, resolution: int = 7, state: str | None = None) -> pd.DataFrame:
    """Cells × score × confidence × n_facilities for the Kepler map."""
    if state:
        return query_df(
            f"""
            SELECT s.h3_cell, s.score, s.confidence, s.n_facilities, s.evidence_state
            FROM {GOLD}.h3_care_score s
            WHERE s.capability = ? AND s.h3_resolution = ? AND s.state = ?
            """,
            (capability, resolution, state),
        )
    return query_df(
        f"""
        SELECT h3_cell, score, confidence, n_facilities, evidence_state
        FROM {GOLD}.h3_care_score
        WHERE capability = ? AND h3_resolution = ?
        """,
        (capability, resolution),
    )


def fetch_state_rollup(capability: str) -> pd.DataFrame:
    return query_df(
        f"""
        SELECT state, score, confidence, n_facilities, n_data_deficient_cells
        FROM {GOLD}.care_score_by_state
        WHERE capability = ?
        ORDER BY score ASC
        """,
        (capability,),
    )


def fetch_district_rollup(capability: str, state: str | None = None) -> pd.DataFrame:
    if state:
        return query_df(
            f"""
            SELECT state, district, score, confidence, n_facilities, n_data_deficient_cells
            FROM {GOLD}.care_score_by_district
            WHERE capability = ? AND state = ?
            ORDER BY score ASC
            """,
            (capability, state),
        )
    return query_df(
        f"""
        SELECT state, district, score, confidence, n_facilities, n_data_deficient_cells
        FROM {GOLD}.care_score_by_district
        WHERE capability = ?
        ORDER BY score ASC
        """,
        (capability,),
    )


def fetch_facilities_in_cell(h3_cell: str, capability: str, resolution: int = 7) -> pd.DataFrame:
    """Facilities backing one H3 aggregate, with citations.

    Reads from silver_facility_capability_claims if it exists (the planned
    table from gap #1); otherwise falls back to a coarser silver_facilities
    listing so the drill-down still renders.
    """
    h3_col = f"h3_{resolution if resolution in {6, 7, 8} else 7}"
    df = query_df(
        f"""
        SELECT facility_id, name, state, district, city, evidence_strength, citations
        FROM {SILVER}.silver_facility_capability_claims
        WHERE {h3_col} = ? AND capability = ?
        ORDER BY CASE evidence_strength
            WHEN 'strong' THEN 1 WHEN 'partial' THEN 2 WHEN 'suspicious' THEN 3 ELSE 4 END
        """,
        (h3_cell, capability),
    )
    if not df.empty:
        return df
    # Fallback while claim extraction isn't deployed yet.
    return query_df(
        f"""
        SELECT facility_id, name, state, district, city,
               CAST(NULL AS STRING) AS evidence_strength,
               description AS citations
        FROM {SILVER}.silver_facilities
        WHERE {h3_col} = ?
        LIMIT 200
        """,
        (h3_cell,),
    )


def fetch_facilities_in_region(
    capability: str,
    state: str,
    district: str | None = None,
) -> pd.DataFrame:
    where = "state = ? AND capability = ?"
    params: tuple = (state, capability)
    if district:
        where += " AND district = ?"
        params = (state, capability, district)
    df = query_df(
        f"""
        SELECT facility_id, name, state, district, city, evidence_strength, citations
        FROM {SILVER}.silver_facility_capability_claims
        WHERE {where}
        LIMIT 500
        """,
        params,
    )
    if not df.empty:
        return df
    fallback_where = "state = ?"
    fallback_params: tuple = (state,)
    if district:
        fallback_where += " AND district = ?"
        fallback_params = (state, district)
    return query_df(
        f"""
        SELECT facility_id, name, state, city, district,
               CAST(NULL AS STRING) AS evidence_strength,
               description AS citations
        FROM {SILVER}.silver_facilities
        WHERE {fallback_where}
        LIMIT 500
        """,
        fallback_params,
    )
