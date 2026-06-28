"""Care-gap read endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.schemas import DistrictRollup, H3ScoreCell, MapKpis, StateRollup
from app.core.serialization import records_from_df
from app.services import gold

router = APIRouter(prefix="/api/care-gaps", tags=["care-gaps"])


@router.get("/kpis", response_model=MapKpis)
def get_kpis(
    capability: str,
    state: str | None = None,
    h3_resolution: int = Query(default=7, ge=1),
) -> MapKpis:
    return MapKpis(**gold.fetch_map_kpis(capability, h3_resolution, state))


@router.get("/h3-scores", response_model=list[H3ScoreCell])
def get_h3_scores(
    capability: str,
    state: str | None = None,
    h3_resolution: int = Query(default=7, ge=1),
    confidence_min: float = Query(default=0.0, ge=0.0, le=1.0),
) -> list[dict]:
    df = gold.fetch_h3_scores(capability, h3_resolution, state)
    if not df.empty and "confidence" in df.columns:
        df = df[df["confidence"].fillna(0.0) >= confidence_min]
    return records_from_df(df)


@router.get("/nfhs5")
def get_nfhs5(indicator: str, state: str | None = None) -> list[dict]:
    return records_from_df(gold.fetch_nfhs5_indicator(indicator, state))


@router.get("/rollup/state", response_model=list[StateRollup])
def get_state_rollup(capability: str) -> list[dict]:
    return records_from_df(gold.fetch_state_rollup(capability))


@router.get("/rollup/district", response_model=list[DistrictRollup])
def get_district_rollup(capability: str, state: str | None = None) -> list[dict]:
    return records_from_df(gold.fetch_district_rollup(capability, state))
