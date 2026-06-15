"""Unit tests for shared config and read-side services."""

from __future__ import annotations

import importlib

import pandas as pd

from pipelines.framework.registry import get_source


def test_registry_keeps_evidence_arrays_as_arrays():
    facilities = get_source("facilities")
    casts = {column.target: column.cast for column in facilities.columns}

    assert casts["capability_raw"] == "array<string>"
    assert casts["procedure_raw"] == "array<string>"
    assert casts["equipment_raw"] == "array<string>"
    assert casts["specialties_raw"] == "array<string>"
    assert casts["source_urls_raw"] == "array<string>"


def test_gold_service_uses_claims_table_and_capability_filter(monkeypatch):
    import app.services.gold as gold_service

    gold_service = importlib.reload(gold_service)
    calls: list[tuple[str, tuple | None]] = []

    def fake_query(sql_text: str, params: tuple | None = None) -> pd.DataFrame:
        calls.append((sql_text, params))
        return pd.DataFrame([{"facility_id": "fac-1"}])

    monkeypatch.setattr(gold_service, "query_df", fake_query)

    df = gold_service.fetch_facilities_in_region("icu", "Bihar")

    assert not df.empty
    assert "silver_facility_capability_claims" in calls[0][0]
    assert calls[0][1] == ("Bihar", "icu")


def test_gold_service_falls_back_to_silver_facilities(monkeypatch):
    import app.services.gold as gold_service

    gold_service = importlib.reload(gold_service)
    calls: list[tuple[str, tuple | None]] = []

    def fake_query(sql_text: str, params: tuple | None = None) -> pd.DataFrame:
        calls.append((sql_text, params))
        if "silver_facility_capability_claims" in sql_text:
            return pd.DataFrame()
        return pd.DataFrame([{"facility_id": "fac-2"}])

    monkeypatch.setattr(gold_service, "query_df", fake_query)

    df = gold_service.fetch_facilities_in_region("icu", "Bihar", district="Patna")

    assert not df.empty
    assert len(calls) == 2
    assert "silver_facilities" in calls[1][0]
    assert calls[1][1] == ("Bihar", "Patna")
