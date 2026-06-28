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

_APP_ROOT = Path(__file__).resolve().parents[1]
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from components.filters import render_sidebar  # noqa: E402
from services import brand, gold  # noqa: E402
from services.performance import projected_trend, risk_band  # noqa: E402

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
districts = districts.copy()
districts["risk"] = districts["score"].apply(risk_band)
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

# ---- Gap-closure trend (real history if available, projection otherwise)
st.divider()

WORST_N = 8

# Try real history first — `gold.score_history` accumulates one row per
# (capability, state, district, score_run_id). When ≥ 2 snapshots exist we
# render real movement; otherwise fall back to the deterministic projection
# below so the page stays demo-able even on a fresh workspace.
history = gold.fetch_score_history(
    filters.capability, state=filters.state, top_n_districts=WORST_N,
)

if not history.empty:
    st.markdown("#### Gap-closure trajectory · actual history")
    st.caption(
        f"From `gold.score_history` ({history['snapshot_ts'].nunique()} runs · "
        f"{history['district'].nunique()} districts). One line per district."
    )
    pivot_real = history.pivot_table(
        index="snapshot_ts", columns="district", values="score", aggfunc="mean",
    ).sort_index()
    st.line_chart(pivot_real, height=360, use_container_width=True)
    st.success(
        "Real history. Each point is a Gold ETL run.",
        icon="✅",
    )
else:
    st.markdown("#### Projected gap-closure trajectory")
    st.caption(
        "**Projected** — generated from the current Gold scores using a "
        "deterministic monotonic improvement curve. The page switches to "
        "actual history once `gold.score_history` accumulates ≥ 2 snapshots "
        "(every Gold ETL run appends one)."
    )

    trend_df = pd.DataFrame(projected_trend(ranked, top_n_districts=WORST_N, months=12))

    if not trend_df.empty:
        pivot = trend_df.pivot(index="month", columns="district", values="score")
        st.line_chart(pivot, height=360, use_container_width=True)
    else:
        st.caption("Not enough districts with scores to chart.")

# ---- Honest banner ------------------------------------------------------
if history.empty:
    st.info(
        "💡 **Real history replaces the projection** automatically once the "
        "Gold ETL snapshots ≥ 2 runs. Each `bundle run care_gap_etl` appends "
        "one row per (capability, district) to `gold.score_history`.",
        icon="ℹ️",
    )
