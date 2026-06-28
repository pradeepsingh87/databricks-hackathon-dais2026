"""Performance and status endpoints."""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Query

from app.api.schemas import DistrictRollup, PerformanceRiskBand, ProjectedTrendPoint
from app.core.serialization import records_from_df
from app.services import gold
from app.services.performance import projected_trend, risk_band

router = APIRouter(prefix="/api/performance", tags=["performance"])


@router.get("/district-risk", response_model=list[PerformanceRiskBand])
def district_risk(capability: str, state: str | None = None) -> list[PerformanceRiskBand]:
    df = gold.fetch_district_rollup(capability, state)
    if df.empty or "score" not in df.columns:
        return []
    counts = Counter(risk_band(score) for score in df["score"])
    order = ["Critical", "At-risk", "Adequate", "Well-served", "Unknown"]
    return [PerformanceRiskBand(band=band, count=counts.get(band, 0)) for band in order]


@router.get("/score-history")
def score_history(
    capability: str,
    state: str | None = None,
    top_n_districts: int = Query(default=8, ge=1, le=100),
) -> list[dict]:
    return records_from_df(
        gold.fetch_score_history(capability, state=state, top_n_districts=top_n_districts)
    )


@router.get("/projected-trend", response_model=list[ProjectedTrendPoint])
def projected_gap_trend(
    capability: str,
    state: str | None = None,
    top_n_districts: int = Query(default=8, ge=1, le=100),
    months: int = Query(default=12, ge=1, le=60),
) -> list[dict]:
    districts = gold.fetch_district_rollup(capability, state)
    return projected_trend(districts, top_n_districts=top_n_districts, months=months)


@router.get("/districts", response_model=list[DistrictRollup])
def performance_districts(capability: str, state: str | None = None) -> list[dict]:
    return records_from_df(gold.fetch_district_rollup(capability, state))
