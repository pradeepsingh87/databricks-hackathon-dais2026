"""Integration contract tests for the read-side gold/silver queries.

These don't hit a live warehouse — they monkeypatch `query_df` to capture
the SQL string the service emits. The asserts pin the exact tables and
columns each helper depends on so a Gold schema change can't silently
break the app at demo time.

Mirror this pattern when you add new gold service helpers.
"""

from __future__ import annotations

import importlib
import re

import pandas as pd
import pytest


@pytest.fixture
def gold(monkeypatch):
    """Reload services.gold with a captured-SQL stub for query_df."""
    mod = importlib.import_module("app.services.gold")
    mod = importlib.reload(mod)
    captured: list[tuple[str, tuple | None]] = []

    def fake(sql, params=None):
        captured.append((sql, params))
        return pd.DataFrame()

    monkeypatch.setattr(mod, "query_df", fake)
    return mod, captured


def _norm(sql: str) -> str:
    """Collapse whitespace so column-order assertions are deterministic."""
    return re.sub(r"\s+", " ", sql).strip().lower()


# ---- Map contract --------------------------------------------------------

def test_fetch_h3_scores_pulls_canonical_columns_from_h3_care_score(gold):
    mod, captured = gold
    mod.fetch_h3_scores(capability="icu", resolution=7, state="Bihar")
    sql, params = captured[0]
    s = _norm(sql)
    # Canonical Gold contract — every column drives a real UI element.
    assert "from " + mod.GOLD.lower() + ".h3_care_score" in s
    for col in ("h3_cell", "score", "confidence", "n_facilities", "evidence_state"):
        assert col in s, f"map query lost column `{col}`"
    # Capability + resolution are positional placeholders.
    assert params == ("icu", 7, "Bihar")


def test_fetch_h3_scores_no_state_filter_drops_state_predicate(gold):
    mod, captured = gold
    mod.fetch_h3_scores(capability="icu", resolution=7, state=None)
    sql, params = captured[0]
    assert "and s.state" not in _norm(sql)   # no state filter when state is None
    assert params == ("icu", 7)


# ---- KPI contract --------------------------------------------------------

def test_fetch_map_kpis_aggregates_evidence_state_buckets(gold):
    mod, captured = gold
    mod.fetch_map_kpis(capability="icu", resolution=7)
    sql, _ = captured[0]
    s = _norm(sql)
    # Three evidence_state buckets need to round-trip into KPI metrics.
    for bucket in ("'data_deficient'", "'care_gap'", "'covered'"):
        assert bucket in s, f"map_kpis dropped evidence_state bucket {bucket}"
    for col in ("avg(score)", "avg(confidence)", "sum(n_facilities)"):
        assert col in s, f"map_kpis dropped aggregate {col}"


# ---- Rollup contract -----------------------------------------------------

def test_state_rollup_pulls_n_data_deficient_cells(gold):
    mod, captured = gold
    mod.fetch_state_rollup(capability="maternity")
    s = _norm(captured[0][0])
    assert "from " + mod.GOLD.lower() + ".care_score_by_state" in s
    assert "n_data_deficient_cells" in s, (
        "rollup missing n_data_deficient_cells — Performance page risk strip "
        "depends on it"
    )


def test_district_rollup_supports_state_filter(gold):
    mod, captured = gold
    mod.fetch_district_rollup(capability="maternity", state="Bihar")
    sql, params = captured[0]
    assert "from " + mod.GOLD.lower() + ".care_score_by_district" in _norm(sql)
    assert params == ("maternity", "Bihar")


# ---- Drill-down / citation contract --------------------------------------

def test_fetch_facilities_in_cell_uses_silver_claims_with_citations(gold):
    mod, captured = gold
    mod.fetch_facilities_in_cell(h3_cell="877123abc", capability="icu", resolution=7)
    sql, params = captured[0]
    s = _norm(sql)
    assert "silver_facility_capability_claims" in s, (
        "drill-down query lost the silver_facility_capability_claims table — "
        "the citations source is gone"
    )
    for col in ("evidence_strength", "citations"):
        assert col in s, f"drill-down query lost `{col}` (citation contract)"
    assert params == ("877123abc", "icu")


# ---- History contract ----------------------------------------------------

def test_fetch_score_history_returns_empty_when_too_few_snapshots(monkeypatch):
    """Pre-flight count-distinct query short-circuits when N < 2."""
    mod = importlib.reload(importlib.import_module("app.services.gold"))
    monkeypatch.setattr(
        mod, "query_df",
        lambda sql, params=None: pd.DataFrame([{"n": 1}]),
    )
    out = mod.fetch_score_history("icu")
    assert out.empty, "history must fall back to projection when N<2 snapshots"


# ---- Search contract -----------------------------------------------------

def test_search_facilities_handles_empty_query_without_hitting_warehouse(gold):
    mod, captured = gold
    out = mod.search_facilities("   ")
    assert out.empty
    assert captured == [], (
        "search must not issue SQL on empty input — would scan silver_facilities"
    )
