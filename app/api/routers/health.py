"""Health and status endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.core import sql_client
from app.services import genie

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/api/status")
def status() -> dict[str, bool | str]:
    return {
        "status": "ok",
        "sql_configured": sql_client.is_configured(),
        "genie_configured": genie.is_configured(),
    }
