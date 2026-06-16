"""Resolve the active user identity and the per-deployment prefix.

Identity precedence (most-authoritative first):
  1. X-Forwarded-Email or X-Forwarded-User HTTP header — Databricks Apps
     forwards these for the end user hitting the app.
  2. DATABRICKS_USER env — set by some Databricks runtime flavours.
  3. APP_USER env — local dev override (set in .env).
  4. The string "demo" — last-resort fallback so the app still renders.

The prefix (APP_PREFIX env, falling back to slugified user) is what the
bundle uses to namespace the deployed Job/App resources, and what the app
shows in its page title so two side-by-side deployments are distinguishable.
"""

from __future__ import annotations

import os
import re

import streamlit as st


def _slug(s: str) -> str:
    s = s.split("@")[0].lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "demo"


@st.cache_data(ttl=60, show_spinner=False)
def current_user() -> str:
    """Return the email or username of the human using the app."""
    headers = st.context.headers if hasattr(st, "context") else {}
    for h in ("X-Forwarded-Email", "X-Forwarded-User", "X-Forwarded-Preferred-Username"):
        v = headers.get(h) if headers else None
        if v:
            return v
    for env in ("DATABRICKS_USER", "APP_USER"):
        v = os.environ.get(env)
        if v:
            return v
    return "demo"


def app_prefix() -> str:
    """Stable namespace used in the app title and the Databricks resource names."""
    return os.environ.get("APP_PREFIX") or _slug(current_user())


def app_title(base: str = "Trust-Weighted Care Gap Navigator") -> str:
    """e.g. 'pradeep · Trust-Weighted Care Gap Navigator'."""
    p = app_prefix()
    return f"{p} · {base}" if p and p != "demo" else base
