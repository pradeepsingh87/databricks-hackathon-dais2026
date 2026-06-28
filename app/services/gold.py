"""Read-side services backed by the canonical Gold contract.

Canonical Gold model (per docs/gold_contract_decision.md):
  - gold.h3_care_score               — score, confidence, evidence_state per (capability, h3 cell)
  - gold.care_score_by_state         — state rollup of the above
  - gold.care_score_by_district      — district rollup of the above

Metric vocabulary used everywhere in the app:
  - score (0..1)         · 0 = no verified care, 1 = well-served
  - confidence (0..1)    · 0 = data-poor, 1 = strong evidence; drives map alpha
  - evidence_state       · 'data_deficient' | 'care_gap' | 'covered'
  - data_deficient       · TRUE when confidence is too low to trust the score

We deliberately do NOT use 'gap_score' / 'desert_flag' / 'confidence_label'
in this layer — those belong to the supplemental medical_desert_* tables and
are not part of the canonical app contract.

Every function returns a pandas DataFrame — empty if the underlying table
isn't deployed yet, so pages render their own empty-state UI.
"""

from __future__ import annotations

import pandas as pd

from app.core.sql_client import query_df

from ._shared_config import CAPABILITIES, fq_schema

SILVER = fq_schema("silver")
GOLD = fq_schema("gold")


def list_capabilities() -> list[str]:
    """Drive the sidebar selector. Stay aligned with capability_taxonomy.yml."""
    return CAPABILITIES


FALLBACK_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chandigarh",
    "Chhattisgarh", "Dadra and Nagar Haveli and Daman and Diu", "Delhi",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
    "Jammu and Kashmir", "Jharkhand", "Karnataka", "Kerala",
    "Ladakh", "Lakshadweep", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Puducherry",
    "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
]


def list_states() -> list[str]:
    """Canonicalized India state/UT list (~36 rows).

    Reads from `bronze.state_alias_reference.canonical_state` rather than from
    `silver_facilities.state` — the latter mixes 200+ values including city
    names, JSON fragments, and country names, so it's unusable as a dropdown.
    The alias reference is the curated truth set the silver runner joins
    against, so dropdown values always match what silver rows can carry.

    NOTE: ORDER BY references the projected alias `state`, not the original
    column. After `SELECT DISTINCT … AS state`, Spark only resolves columns
    in the projection; ordering by `canonical_state` raises UNRESOLVED_COLUMN.

    Falls back to FALLBACK_STATES when the database table is not available
    (e.g. local development or before the bronze layer is deployed).
    """
    try:
        df = query_df(
            f"""
            SELECT DISTINCT canonical_state AS state
            FROM {fq_schema('bronze')}.state_alias_reference
            WHERE canonical_state IS NOT NULL
            ORDER BY state
            """
        )
        return df["state"].tolist() if not df.empty else FALLBACK_STATES
    except Exception:
        return FALLBACK_STATES


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


def fetch_map_kpis(capability: str, resolution: int = 7, state: str | None = None) -> dict:
    """Single-row KPI summary for the Map page header.

    Cheap query — one aggregate against gold.h3_care_score for the active
    capability/state/resolution. Returns plain Python ints/floats so the
    Streamlit metric() widgets render cleanly.
    """
    where = "capability = ? AND h3_resolution = ?"
    params: tuple = (capability, resolution)
    if state:
        where += " AND state = ?"
        params = (capability, resolution, state)
    df = query_df(
        f"""
        SELECT
          COUNT(*)                                              AS n_cells,
          SUM(n_facilities)                                     AS n_facilities,
          AVG(score)                                            AS avg_score,
          AVG(confidence)                                       AS avg_confidence,
          SUM(CASE WHEN evidence_state = 'data_deficient' THEN 1 ELSE 0 END) AS n_data_deficient,
          SUM(CASE WHEN evidence_state = 'care_gap'        THEN 1 ELSE 0 END) AS n_care_gap,
          SUM(CASE WHEN evidence_state = 'covered'         THEN 1 ELSE 0 END) AS n_covered
        FROM {GOLD}.h3_care_score
        WHERE {where}
        """,
        params,
    )
    if df.empty:
        return {
            "n_cells": 0, "n_facilities": 0, "avg_score": None, "avg_confidence": None,
            "n_data_deficient": 0, "n_care_gap": 0, "n_covered": 0,
        }
    row = df.iloc[0].to_dict()
    return {k: (None if pd.isna(v) else (float(v) if k.startswith("avg_") else int(v)))
            for k, v in row.items()}


def fetch_nfhs5_indicator(
    column: str,
    state: str | None = None,
) -> pd.DataFrame:
    """Pull one NFHS-5 indicator at district grain.

    `column` MUST come from app.services.domains.all_indicators() — the names
    are guarded by the YAML registry so we never construct arbitrary strings
    from user input here. Returns rows with state/district/value columns.
    """
    from .domains import all_indicators

    valid = {i.column for i in all_indicators()}
    if column not in valid:
        return pd.DataFrame()

    where = ""
    params: tuple = ()
    if state:
        where = "WHERE state = ?"
        params = (state,)
    return query_df(
        f"""
        SELECT state, district, {column} AS value
        FROM {SILVER}.silver_nfhs5_district
        {where}
        ORDER BY value DESC NULLS LAST
        """,
        params,
    )


def search_facilities(query: str, limit: int = 25) -> pd.DataFrame:
    """Free-text search across facility name, city, district, state.

    Used by the homepage's Search & Ask bar. Cheap LIKE-based search;
    upgrade to UC's vector search when we have the budget.
    """
    q = (query or "").strip()
    if not q:
        return pd.DataFrame()
    pattern = f"%{q.lower()}%"
    return query_df(
        f"""
        SELECT facility_id, name, city, district, state, latitude, longitude
        FROM {SILVER}.silver_facilities
        WHERE LOWER(name) LIKE ?
           OR LOWER(city) LIKE ?
           OR LOWER(district) LIKE ?
           OR LOWER(state) LIKE ?
        LIMIT ?
        """,
        (pattern, pattern, pattern, pattern, limit),
    )


def fetch_score_history(
    capability: str,
    *,
    state: str | None = None,
    top_n_districts: int = 8,
) -> pd.DataFrame:
    """Real time-series of district scores from `gold.score_history`.

    Returns up to `top_n_districts × n_snapshots` rows with columns
    (snapshot_ts, state, district, score, confidence, n_facilities). Empty
    DataFrame when fewer than 2 distinct snapshots exist — the Performance
    page falls back to its synthetic projection in that case.
    """
    where = "capability = ?"
    params: tuple = (capability,)
    if state:
        where += " AND state = ?"
        params = (capability, state)

    # Pre-flight: do we have enough history to be useful?
    n_snaps = query_df(
        f"SELECT COUNT(DISTINCT score_run_id) AS n FROM {GOLD}.score_history "
        f"WHERE capability = ?",
        (capability,),
    )
    if n_snaps.empty or int(n_snaps.iloc[0]["n"]) < 2:
        return pd.DataFrame()

    # Top-N most-current worst districts, then pull every snapshot for them.
    return query_df(
        f"""
        WITH worst AS (
          SELECT state, district
          FROM {GOLD}.care_score_by_district
          WHERE {where}
          ORDER BY score ASC NULLS LAST
          LIMIT {int(top_n_districts)}
        )
        SELECT h.snapshot_ts, h.state, h.district,
               h.score, h.confidence, h.n_facilities
        FROM {GOLD}.score_history h
        JOIN worst w
          ON  h.state = w.state
          AND h.district = w.district
        WHERE h.capability = ?
        ORDER BY h.state, h.district, h.snapshot_ts
        """,
        params + (capability,),
    )


def fetch_top_care_gaps(capability: str, limit: int = 5) -> pd.DataFrame:
    """Worst-served districts (by score) for a capability — homepage card."""
    return query_df(
        f"""
        SELECT state, district, score, confidence, n_facilities
        FROM {GOLD}.care_score_by_district
        WHERE capability = ?
        ORDER BY score ASC NULLS LAST
        LIMIT ?
        """,
        (capability, limit),
    )


def fetch_facility_locations(
    capability: str,
    state: str | None = None,
    h3_cell: str | None = None,
    resolution: int = 7,
    limit: int = 2000,
) -> pd.DataFrame:
    """Per-facility points for the location map.

    Joins silver_facility_capability_claims (for evidence_strength + filter by
    capability) with silver_facilities (for lat/lng/capacity/n_doctors).
    Drops rows missing coords or outside the India bounding box — pydeck would
    silently render them in the middle of the ocean otherwise.
    """
    where_clauses = ["f.in_india_bbox = TRUE",
                     "f.latitude IS NOT NULL", "f.longitude IS NOT NULL",
                     "c.capability = ?"]
    params: list = [capability]
    if h3_cell:
        h3_col = f"h3_{resolution if resolution in {6, 7, 8} else 7}"
        where_clauses.append(f"f.{h3_col} = ?")
        params.append(h3_cell)
    elif state:
        where_clauses.append("f.state = ?")
        params.append(state)
    where_sql = " AND ".join(where_clauses)
    return query_df(
        f"""
        SELECT
          f.facility_id,
          f.name,
          f.state,
          f.district,
          f.city,
          f.latitude,
          f.longitude,
          f.capacity,
          f.number_doctors,
          c.evidence_strength,
          c.claim_weight
        FROM {SILVER}.silver_facilities f
        JOIN {SILVER}.silver_facility_capability_claims c USING (facility_id)
        WHERE {where_sql}
        LIMIT {int(limit)}
        """,
        tuple(params),
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
