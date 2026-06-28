"""User identity and deployment naming helpers without UI framework coupling."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any


def _slug(s: str) -> str:
    s = s.split("@")[0].lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "demo"


def _headers_from_request(request: Any | None) -> Mapping[str, str]:
    return getattr(request, "headers", {}) or {}


def current_user(request: Any | None = None) -> str:
    """Return the email or username for the current request/runtime."""
    headers = _headers_from_request(request)
    for header in (
        "X-Forwarded-Email",
        "X-Forwarded-User",
        "X-Forwarded-Preferred-Username",
    ):
        value = headers.get(header)
        if value:
            return value
    for env in ("DATABRICKS_USER", "APP_USER"):
        value = os.environ.get(env)
        if value:
            return value
    return "demo"


def app_prefix(request: Any | None = None) -> str:
    """Stable namespace used in titles and Databricks resource names."""
    return os.environ.get("APP_PREFIX") or _slug(current_user(request))


def app_title(base: str = "Trust-Weighted Care Gap Navigator") -> str:
    """Example: 'pradeep · Trust-Weighted Care Gap Navigator'."""
    prefix = app_prefix()
    return f"{prefix} · {base}" if prefix and prefix != "demo" else base
