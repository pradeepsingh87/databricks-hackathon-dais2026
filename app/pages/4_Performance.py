"""Performance & Status Tracker — district risk + projected gap-closure trend.

Layout:
  1. Brand strip + page title
  2. Risk-band KPIs (Critical / At-risk / Adequate / Well-served)
  3. Ranked district list (worst-first), with progress bars
  4. Projected gap-closure trend — synthetic monotonic series so the chart
     renders meaningfully today; gets replaced by real history once the Gold
     job starts snapshotting `score_run_id`.
  5. Honest disclaimer banner about the synthetic series

We intentionally don't read from any not-yet-built history table; instead
we generate a deterministic per-state trajectory from the *current* score so
the page is demoable. The `Projected` framing in the chart legend keeps
honesty.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import math  # noqa: E402

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.components.filters import render_sidebar  # noqa: E402
from app.services import brand, gold  # noqa: E402

st.set_page_config(
    page_title=f"Performance · {brand.load_brand().name}",
    page_icon="📈", layout="wide",
)
brand.render_header(subtitle="District risk stratification · gap-closure trajectory")
filters = render_sidebar()

st.markdown("### Performance & Status Tracker")
st.caption(
    f"Capability: **{filters.capability}** · "
    f"Scope: **{filters.state or 'All India'}**"
)

# ---- Pull district rollup ----------------------------------------------
districts = gold.fetch_district_rollup(filters.capability, filters.state)
if districts.empty:
    st.info(
        "Risk stratification will appear once `gold.care_score_by_district` "
        "is populated by the Gold ETL job.",
        icon="📊",
    )
    st.stop()

# ---- Risk bands ---------------------------------------------------------
def _band(score: float) -> str:
    if pd.isna(score): return "Unknown"
    if score < 0.25:   return "Critical"
    if score < 0.50:   return "At-risk"
    if score < 0.75:   return "Adequate"
    return "Well-served"


districts = districts.copy()
districts["risk"] = districts["score"].apply(_band)
counts = districts["risk"].value_counts()

st.markdown("#### Risk stratification")
b1, b2, b3, b4 = st.columns(4)
b1.metric("🚨 Critical",      int(counts.get("Critical", 0)))
b2.metric("⚠️ At-risk",       int(counts.get("At-risk", 0)))
b3.metric("➖ Adequate",      int(counts.get("Adequate", 0)))
b4.metric("✅ Well-served",   int(counts.get("Well-served", 0)))

# ---- Ranked district list ----------------------------------------------
st.divider()
st.markdown("#### Districts ranked by care gap (worst first)")
ranked = districts.sort_values("score", ascending=True, na_position="last").reset_index(drop=True)
st.dataframe(
    ranked,
    use_container_width=True,
    hide_index=True,
    column_config={
        "score": st.column_config.ProgressColumn(
            "score", min_value=0.0, max_value=1.0, format="%.2f",
        ),
        "confidence": st.column_config.ProgressColumn(
            "confidence", min_value=0.0, max_value=1.0, format="%.2f",
        ),
        "n_facilities":           st.column_config.NumberColumn("n facilities", format="%d"),
        "n_data_deficient_cells": st.column_config.NumberColumn(
            "data-deficient", format="%d",
        ),
        "risk": st.column_config.TextColumn("band"),
    },
)

# ---- Projected gap-closure trend ---------------------------------------
st.divider()
st.markdown("#### Projected gap-closure trajectory")
st.caption(
    "**Projected** — these trajectories are generated from the current Gold "
    "scores using a deterministic monotonic improvement curve, so the page "
    "stays demoable. Once the Gold ETL starts snapshotting `score_run_id` "
    "rows, this chart will switch to *actual* historical movement."
)

MONTHS = 12
WORST_N = 8


def _project_series(current_score: float, months: int = MONTHS) -> list[float]:
    """Deterministic monotonic improvement.

    A district scoring 0.20 today projects to (0.20, 0.23, 0.27, …, ≤0.85)
    over `months` steps. The curve flattens as it approaches a ceiling.
    No randomness — same inputs always produce the same chart, so demos
    are reproducible.
    """
    if pd.isna(current_score):
        return [float("nan")] * months
    s = float(current_score)
    ceiling = min(0.95, max(s + 0.4, 0.6))
    out = []
    for i in range(months):
        # Geometric decay toward the ceiling.
        out.append(round(s + (ceiling - s) * (1 - math.exp(-i / 4.0)), 3))
    return out


worst = ranked.dropna(subset=["score"]).head(WORST_N)
trend_rows = []
for _, r in worst.iterrows():
    series = _project_series(float(r["score"]))
    for m, v in enumerate(series):
        trend_rows.append({"district": r["district"], "month": m, "score": v})
trend_df = pd.DataFrame(trend_rows)

if not trend_df.empty:
    pivot = trend_df.pivot(index="month", columns="district", values="score")
    st.line_chart(pivot, height=360, use_container_width=True)
else:
    st.caption("Not enough districts with scores to chart.")

# ---- Honest banner ------------------------------------------------------
st.info(
    "💡 **Real history will replace this** when the Gold ETL job starts "
    "writing one snapshot per run (we already have `score_run_id` and "
    "`as_of_ts` slots reserved on the Gold tables — wiring them is the "
    "next step on the gap list).",
    icon="ℹ️",
)
