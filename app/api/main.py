"""FastAPI application entrypoint."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routers import (
    actions,
    care_gaps,
    config,
    facilities,
    genie,
    health,
    performance,
    scenarios,
)

app = FastAPI(title="Care Gap Navigator API", version="0.1.0")
_STATIC_DIR = Path(__file__).resolve().parents[1] / "web" / "dist"

app.include_router(health.router)
app.include_router(config.router)
app.include_router(care_gaps.router)
app.include_router(facilities.router)
app.include_router(actions.router)
app.include_router(scenarios.router)
app.include_router(genie.router)
app.include_router(performance.router)

app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="web")
