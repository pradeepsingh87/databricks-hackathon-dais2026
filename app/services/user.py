"""Backward-compatible import path for user helpers."""

from app.core.user import app_prefix, app_title, current_user

__all__ = ["app_prefix", "app_title", "current_user"]
