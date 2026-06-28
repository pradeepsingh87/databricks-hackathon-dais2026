"""API migration coverage that does not require a Databricks workspace."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
from fastapi.testclient import TestClient

from app.api.main import app
from app.core.serialization import records_from_df
from app.services.performance import projected_trend, risk_band


def test_healthz_returns_healthy():
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_care_gap_h3_scores_serializes_dataframe(monkeypatch):
    from app.api.routers import care_gaps

    def fake_scores(capability: str, resolution: int, state: str | None = None) -> pd.DataFrame:
        assert capability == "icu"
        assert resolution == 7
        assert state == "Bihar"
        return pd.DataFrame(
            [
                {
                    "h3_cell": "abc",
                    "score": Decimal("0.25"),
                    "confidence": 0.7,
                    "n_facilities": 2,
                    "evidence_state": "care_gap",
                },
                {
                    "h3_cell": "def",
                    "score": 0.9,
                    "confidence": 0.1,
                    "n_facilities": 5,
                    "evidence_state": "covered",
                },
            ]
        )

    monkeypatch.setattr(care_gaps.gold, "fetch_h3_scores", fake_scores)
    client = TestClient(app)

    response = client.get(
        "/api/care-gaps/h3-scores",
        params={"capability": "icu", "state": "Bihar", "confidence_min": 0.5},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "h3_cell": "abc",
            "score": 0.25,
            "confidence": 0.7,
            "n_facilities": 2,
            "evidence_state": "care_gap",
        }
    ]


def test_override_write_attaches_forwarded_user(monkeypatch):
    from app.api.routers import actions

    calls: list[tuple[str, str, str, str]] = []

    def fake_add_override(user: str, facility_id: str, capability: str, note: str) -> bool:
        calls.append((user, facility_id, capability, note))
        return True

    monkeypatch.setattr(actions.lakebase, "add_override", fake_add_override)
    client = TestClient(app)

    response = client.post(
        "/api/overrides",
        headers={"X-Forwarded-Email": "planner@example.com"},
        json={"facility_id": "fac-1", "capability": "icu", "note": "Verified locally"},
    )

    assert response.status_code == 201
    assert response.json() == {"ok": True}
    assert calls == [("planner@example.com", "fac-1", "icu", "Verified locally")]


def test_records_from_df_normalizes_api_values():
    df = pd.DataFrame(
        [
            {
                "created_at": pd.Timestamp("2026-06-28T12:34:00"),
                "score": Decimal("1.25"),
                "missing": pd.NA,
                "payload": '{"impact": 3}',
            }
        ]
    )

    assert records_from_df(df) == [
        {
            "created_at": "2026-06-28T12:34:00",
            "score": 1.25,
            "missing": None,
            "payload": {"impact": 3},
        }
    ]


def test_performance_projection_is_deterministic():
    districts = pd.DataFrame(
        [
            {"state": "Bihar", "district": "Patna", "score": 0.2},
            {"state": "Bihar", "district": "Gaya", "score": 0.1},
        ]
    )

    assert risk_band(0.2) == "Critical"
    assert projected_trend(districts, top_n_districts=1, months=3) == [
        {"state": "Bihar", "district": "Gaya", "month": 0, "score": 0.1},
        {"state": "Bihar", "district": "Gaya", "month": 1, "score": 0.211},
        {"state": "Bihar", "district": "Gaya", "month": 2, "score": 0.297},
    ]
