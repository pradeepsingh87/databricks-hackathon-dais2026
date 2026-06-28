"""Facility read endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.schemas import Facility, FacilityLocation
from app.core.serialization import records_from_df
from app.services import gold

router = APIRouter(prefix="/api/facilities", tags=["facilities"])


@router.get("", response_model=list[Facility])
def get_facilities(
    capability: str,
    state: str | None = None,
    district: str | None = None,
    h3_cell: str | None = None,
    h3_resolution: int = Query(default=7, ge=1),
) -> list[dict]:
    if h3_cell:
        df = gold.fetch_facilities_in_cell(h3_cell, capability, h3_resolution)
    elif state:
        df = gold.fetch_facilities_in_region(capability, state, district)
    else:
        df = gold.search_facilities(capability, limit=100)
    return records_from_df(df)


@router.get("/locations", response_model=list[FacilityLocation])
def get_facility_locations(
    capability: str,
    state: str | None = None,
    h3_cell: str | None = None,
    h3_resolution: int = Query(default=7, ge=1),
    limit: int = Query(default=2000, ge=1, le=10000),
) -> list[dict]:
    return records_from_df(
        gold.fetch_facility_locations(
            capability,
            state=state,
            h3_cell=h3_cell,
            resolution=h3_resolution,
            limit=limit,
        )
    )


@router.get("/search", response_model=list[Facility])
def search_facilities(q: str, limit: int = Query(default=25, ge=1, le=100)) -> list[dict]:
    return records_from_df(gold.search_facilities(q, limit))
