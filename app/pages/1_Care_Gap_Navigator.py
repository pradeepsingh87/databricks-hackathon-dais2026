"""Care Gap Navigator — H3 care-score grid with confidence-as-alpha.

Layout (top-down):
  1. Brand strip + page title
  2. KPI strip — n_cells, n_facilities, avg score/confidence, evidence-state mix
  3. Map (pydeck H3 layer) + legend
  4. Disease-burden ribbon (NFHS-5 indicator from the active domain)
  5. Cell picker — "use this cell for drill-down" hands off to Action Center
  6. Regional rollup (state-grain or district-grain)
  7. Diagnostics expander
"""

import sys
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parents[1]
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

import streamlit as st  # noqa: E402

from components import care_map, legend, root_cause_panel  # noqa: E402
from components.filters import render_sidebar, set_selected_cell  # noqa: E402
from services import brand, gold  # noqa: E402

st.set_page_config(
    page_title=f"Care Gap Navigator · {brand.load_brand().name}",
    page_icon="🗺️", layout="wide",
)
brand.render_header(subtitle="H3 supply/demand grid · trust-weighted")
filters = render_sidebar()

# ---- Header --------------------------------------------------------------
# brand.render_header() already shows the page title + tagline above. Just a
# single muted context line — what's currently filtered.
_b = "<b style='color:var(--brand-text);'>"
_eb = "</b>"
_chips = [
    f"capability {_b}{filters.capability}{_eb}",
    f"state {_b}{filters.state or 'All India'}{_eb}",
    f"H3 {_b}{filters.h3_resolution}{_eb}",
]
if filters.domain:
    _chips.append(f"domain {_b}{filters.domain}{_eb}")
if filters.confidence_min > 0:
    _chips.append(f"min confidence {_b}{filters.confidence_min:.2f}{_eb}")
st.markdown(
    "<div style='font-size:13px;color:var(--brand-muted);margin-bottom:14px;'>"
    + " &middot; ".join(_chips)
    + "</div>",
    unsafe_allow_html=True,
)

# ---- KPIs ---------------------------------------------------------------
kpis = gold.fetch_map_kpis(
    capability=filters.capability,
    resolution=filters.h3_resolution,
    state=filters.state,
)
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Cells", f"{kpis['n_cells']:,}")
k2.metric("Facilities", f"{kpis['n_facilities']:,}")
k3.metric(
    "Avg score",
    "—" if kpis["avg_score"] is None else f"{kpis['avg_score']:.2f}",
    help="0 = no care · 1 = well-served. Averaged over visible cells.",
)
k4.metric(
    "Avg confidence",
    "—" if kpis["avg_confidence"] is None else f"{kpis['avg_confidence']:.2f}",
    help="How much we trust the score in this view (0..1).",
)
k5.metric(
    "Data-deficient cells",
    f"{kpis['n_data_deficient']:,}",
    delta=f"{kpis['n_care_gap']:,} care-gap · {kpis['n_covered']:,} covered",
    delta_color="off",
)

st.divider()

# ---- Map ---------------------------------------------------------------
df = gold.fetch_h3_scores(
    capability=filters.capability,
    resolution=filters.h3_resolution,
    state=filters.state,
)
if not df.empty and filters.confidence_min > 0:
    df = df[df["confidence"].fillna(0) >= filters.confidence_min].reset_index(drop=True)

map_key = (
    f"care-{filters.capability}-{filters.h3_resolution}-"
    f"{filters.state or 'all'}-{filters.confidence_min}"
)
care_map.render(df, key=map_key)
legend.render()

# ---- Disease-burden ribbon (NFHS-5) ------------------------------------
if filters.indicator:
    st.markdown("&nbsp;")
    st.markdown("**Disease-burden context — NFHS-5**")
    burden = gold.fetch_nfhs5_indicator(filters.indicator, state=filters.state)
    if burden.empty:
        st.caption("No NFHS-5 rows for this indicator/region.")
    else:
        # Show top-3 worst and top-3 best — clinically actionable framing.
        top = burden.dropna(subset=["value"]).head(3)
        bot = burden.dropna(subset=["value"]).tail(3)[::-1]
        c1, c2 = st.columns(2)
        with c1:
            st.caption(f"**Highest** · {filters.indicator}")
            st.dataframe(top, hide_index=True, use_container_width=True)
        with c2:
            st.caption(f"**Lowest** · {filters.indicator}")
            st.dataframe(bot, hide_index=True, use_container_width=True)

# ---- Cell picker -------------------------------------------------------
if not df.empty:
    st.divider()
    st.subheader("Pick a cell to drill into")

    sort_options = {
        "Worst care first (lowest score)":   ("score",      True),
        "Best care first (highest score)":   ("score",      False),
        "Most facilities":                    ("n_facilities", False),
        "Lowest confidence":                  ("confidence", True),
    }
    sort_label = st.selectbox("Sort by", list(sort_options.keys()))
    col, ascending = sort_options[sort_label]
    sorted_df = df.sort_values(col, ascending=ascending).reset_index(drop=True)

    pick_left, pick_right = st.columns([2, 1])
    with pick_left:
        selected = st.selectbox(
            "Cell",
            options=sorted_df["h3_cell"].tolist(),
            format_func=lambda h: (
                f"{h}  ·  score={float(sorted_df.loc[sorted_df.h3_cell == h, 'score'].iloc[0]):.2f}"
                f"  ·  conf={float(sorted_df.loc[sorted_df.h3_cell == h, 'confidence'].iloc[0]):.2f}"
                f"  ·  n={int(sorted_df.loc[sorted_df.h3_cell == h, 'n_facilities'].iloc[0])}"
                f"  ·  {sorted_df.loc[sorted_df.h3_cell == h, 'evidence_state'].iloc[0]}"
            ),
        )
        # Cross-filter: writing the picked cell to session_state immediately
        # makes downstream sections (facility list + root-cause panel) react
        # without a separate "apply" step. Open in Action Center is still
        # available for the cross-page handoff.
        if selected and selected != filters.h3_cell:
            set_selected_cell(selected)
            filters.h3_cell = selected   # in-page reference, no rerun
    with pick_right:
        st.markdown("&nbsp;")
        if st.button("Open in Action Center →", type="primary", use_container_width=True):
            set_selected_cell(selected)
            st.switch_page("pages/3_Action_Center.py")

    if filters.h3_cell == selected:
        st.caption(f"Currently selected: `{filters.h3_cell}`")
    elif filters.h3_cell:
        st.caption(
            f"Drill-down currently set to `{filters.h3_cell}` — pick a new one above to change it."
        )

# ---- Cross-filtered facility list (clicked cell → live facility list) ----
# Renders only when a cell is picked. The "click a hexagon → filter the
# citation list" pattern from the brief, driven by st.session_state.
if filters.h3_cell:
    st.divider()
    st.subheader(f"Facilities in cell `{filters.h3_cell}`")
    st.caption(
        "Cross-filtered live from the picked cell. Use the **Action Center** "
        "page for the full citations + override workflow."
    )
    cell_facilities = gold.fetch_facilities_in_cell(
        filters.h3_cell, filters.capability, resolution=filters.h3_resolution,
    )
    if cell_facilities.empty:
        st.info(
            "No facilities backing this cell. Either it's data-deficient "
            "(no claims found) or the cell is genuinely empty.",
            icon="ℹ️",
        )
    else:
        st.dataframe(
            cell_facilities[
                [c for c in ["facility_id", "name", "city", "state", "evidence_strength"]
                 if c in cell_facilities.columns]
            ],
            use_container_width=True, hide_index=True,
        )

# ---- NACHC Root Cause Analysis side-panel -------------------------------
# Active whenever there's a non-trivial scope to categorise. Persists to
# lakebase.gap_categorizations for multi-team coordination.
if filters.h3_cell or filters.state:
    st.divider()
    root_cause_panel.render(
        root_cause_panel.Selection(
            capability=filters.capability,
            state=filters.state,
            district=None,           # the navigator doesn't pin a district yet
            h3_cell=filters.h3_cell,
        ),
        location="cell" if filters.h3_cell else "state",
        key_prefix="nav",
    )

# ---- Regional rollup (admin overlay) -----------------------------------
st.divider()
st.subheader("Regional coverage summary")
overlay = filters.admin_overlay
if overlay == "District" or (overlay == "None" and filters.state):
    st.caption(f"District-level rollup for **{filters.state or 'all states'}**.")
    summary = gold.fetch_district_rollup(filters.capability, filters.state)
elif overlay == "State" or (overlay == "None" and not filters.state):
    st.caption("State-level rollup. Pick a state in the sidebar to drop to district level.")
    summary = gold.fetch_state_rollup(filters.capability)
else:
    summary = gold.fetch_state_rollup(filters.capability)

if summary.empty:
    st.info(
        "Coverage summary will appear after the Gold ETL job populates "
        "`gold.care_score_by_state` / `care_score_by_district`.",
        icon="ℹ️",
    )
else:
    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "score":          st.column_config.ProgressColumn(
                "score", min_value=0.0, max_value=1.0, format="%.2f",
            ),
            "confidence":     st.column_config.ProgressColumn(
                "confidence", min_value=0.0, max_value=1.0, format="%.2f",
            ),
            "n_facilities":   st.column_config.NumberColumn("n facilities", format="%d"),
            "n_data_deficient_cells": st.column_config.NumberColumn(
                "data-deficient", format="%d",
                help="How many H3 cells in this region we cannot trust either way.",
            ),
        },
    )

# ---- Diagnostics -------------------------------------------------------
with st.expander("Diagnostics", expanded=False):
    st.write(
        f"`gold.h3_care_score` returned **{len(df)} rows**"
        + (
            f" (after confidence ≥ {filters.confidence_min:.2f} filter)"
            if filters.confidence_min > 0 else ""
        )
        + "."
    )
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    if err := st.session_state.get("_last_query_error"):
        st.markdown("**Last query error**")
        st.code(err, language="text")
