"""Scenario and bookmark endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import current_user
from app.api.schemas import Bookmark, BookmarkCreate, Scenario, ScenarioCreate
from app.core.serialization import records_from_df
from app.services import lakebase

router = APIRouter(prefix="/api", tags=["scenarios"])


@router.post("/scenarios", status_code=status.HTTP_201_CREATED)
def create_scenario(payload: ScenarioCreate, user: str = Depends(current_user)) -> dict[str, bool]:
    ok = lakebase.save_scenario(user, payload.name, payload.payload)
    if not ok:
        raise HTTPException(status_code=400, detail="Unable to create scenario")
    return {"ok": True}


@router.get("/scenarios", response_model=list[Scenario])
def list_scenarios(user: str | None = None) -> list[dict]:
    return records_from_df(lakebase.list_scenarios(user))


@router.post("/bookmarks", status_code=status.HTTP_201_CREATED)
def create_bookmark(payload: BookmarkCreate, user: str = Depends(current_user)) -> dict[str, bool]:
    ok = lakebase.save_bookmark(user, payload.name, payload.filters, shared=payload.shared)
    if not ok:
        raise HTTPException(status_code=400, detail="Unable to create bookmark")
    return {"ok": True}


@router.get("/bookmarks", response_model=list[Bookmark])
def list_bookmarks(
    user: str | None = None,
    include_shared: bool = Query(default=True),
) -> list[dict]:
    return records_from_df(lakebase.list_bookmarks(user, include_shared=include_shared))
