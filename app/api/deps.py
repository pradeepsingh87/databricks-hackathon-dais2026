"""FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from app.core.user import current_user as resolve_current_user


def current_user(request: Request) -> str:
    return resolve_current_user(request)
