"""Lakebase action endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import current_user
from app.api.schemas import (
    GapCategorization,
    GapCategorizationCreate,
    Override,
    OverrideCreate,
)
from app.core.serialization import records_from_df
from app.services import lakebase

router = APIRouter(prefix="/api", tags=["actions"])


@router.post("/overrides", status_code=status.HTTP_201_CREATED)
def create_override(payload: OverrideCreate, user: str = Depends(current_user)) -> dict[str, bool]:
    ok = lakebase.add_override(user, payload.facility_id, payload.capability, payload.note)
    if not ok:
        raise HTTPException(status_code=400, detail="Unable to create override")
    return {"ok": True}


@router.get("/overrides", response_model=list[Override])
def list_overrides(user: str | None = None) -> list[dict]:
    return records_from_df(lakebase.list_overrides(user))


@router.post("/gap-categorizations", status_code=status.HTTP_201_CREATED)
def create_gap_categorization(
    payload: GapCategorizationCreate,
    user: str = Depends(current_user),
) -> dict[str, bool]:
    ok = lakebase.add_gap_categorization(user, **payload.model_dump())
    if not ok:
        raise HTTPException(status_code=400, detail="Unable to create gap categorization")
    return {"ok": True}


@router.get("/gap-categorizations", response_model=list[GapCategorization])
def list_gap_categorizations(
    user: str | None = None,
    capability: str | None = None,
    state: str | None = Query(default=None),
) -> list[dict]:
    return records_from_df(
        lakebase.list_gap_categorizations(user, capability=capability, state=state)
    )
