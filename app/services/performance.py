"""Reusable performance/risk helpers shared by Streamlit and FastAPI."""

from __future__ import annotations

import math

import pandas as pd


def risk_band(score: float | None) -> str:
    if score is None or pd.isna(score):
        return "Unknown"
    if score < 0.25:
        return "Critical"
    if score < 0.50:
        return "At-risk"
    if score < 0.75:
        return "Adequate"
    return "Well-served"


def project_series(current_score: float | None, months: int = 12) -> list[float | None]:
    """Deterministic monotonic improvement curve used until real history exists."""
    if current_score is None or pd.isna(current_score):
        return [None] * months
    score = float(current_score)
    ceiling = min(0.95, max(score + 0.4, 0.6))
    return [
        round(score + (ceiling - score) * (1 - math.exp(-month / 4.0)), 3)
        for month in range(months)
    ]


def projected_trend(
    districts: pd.DataFrame,
    *,
    top_n_districts: int = 8,
    months: int = 12,
) -> list[dict]:
    """Return long-form projected trend rows for the worst current districts."""
    if districts.empty or "score" not in districts.columns:
        return []
    ranked = districts.sort_values("score", ascending=True, na_position="last")
    worst = ranked.dropna(subset=["score"]).head(top_n_districts)
    rows: list[dict] = []
    for _, district in worst.iterrows():
        for month, score in enumerate(project_series(district["score"], months=months)):
            rows.append(
                {
                    "state": district.get("state"),
                    "district": district.get("district"),
                    "month": month,
                    "score": score,
                }
            )
    return rows
