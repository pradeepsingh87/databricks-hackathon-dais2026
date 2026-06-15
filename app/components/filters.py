"""Sidebar filters shared across all pages.

Selections persist in st.session_state under stable keys so Care-Gap →
Action-Center → Scenarios all read the same context. Each page calls
render_sidebar() at the top and gets back the current Filters object.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from app.services import gold
from app.services.domains import load_domains

KEYS = {
    "domain":         "filter_domain",
    "capability":     "filter_capability",
    "state":          "filter_state",
    "h3_resolution":  "filter_h3_resolution",
    "h3_cell":        "selected_h3_cell",   # set by Care-Gap when a cell is picked
    "confidence_min": "filter_confidence_min",
    "admin_overlay":  "filter_admin_overlay",
    "indicator":      "filter_nfhs5_indicator",
}

ADMIN_OVERLAYS = ["None", "State", "District"]


@dataclass
class Filters:
    domain: str | None
    capability: str
    state: str | None
    h3_resolution: int
    h3_cell: str | None
    confidence_min: float
    admin_overlay: str
    indicator: str | None


def _capability_choices() -> tuple[list[str], str | None]:
    """Capability options for the active domain, plus the indicator pre-pick."""
    domain_id = st.session_state.get(KEYS["domain"])
    if domain_id and domain_id != "All capabilities":
        for d in load_domains():
            if d.id == domain_id:
                indicator = d.indicators[0].column if d.indicators else None
                return list(d.capabilities), indicator
    return gold.list_capabilities(), None


def render_sidebar() -> Filters:
    st.sidebar.header("Filters")

    # ---- Domain (top of the funnel) -----------------------------------
    domains = load_domains()
    domain_options = ["All capabilities"] + [d.id for d in domains]
    domain_labels = {d.id: f"{d.icon}  {d.name}" for d in domains}
    if KEYS["domain"] not in st.session_state:
        st.session_state[KEYS["domain"]] = "All capabilities"
    domain_choice = st.sidebar.selectbox(
        "Domain",
        domain_options,
        format_func=lambda d: "All capabilities" if d == "All capabilities" else domain_labels.get(d, d),
        key=KEYS["domain"],
        help="Bundles a set of capabilities + NFHS-5 indicators relevant to one planning lens.",
    )

    # ---- Capability (filtered by domain) ------------------------------
    caps, default_indicator = _capability_choices()
    if KEYS["capability"] not in st.session_state or st.session_state[KEYS["capability"]] not in caps:
        st.session_state[KEYS["capability"]] = caps[0]
    capability = st.sidebar.selectbox("Capability", caps, key=KEYS["capability"])

    # ---- Geography ----------------------------------------------------
    states = gold.list_states()
    state_options = ["(All India)"] + states
    if KEYS["state"] not in st.session_state:
        st.session_state[KEYS["state"]] = "(All India)"
    state = st.sidebar.selectbox("State", state_options, key=KEYS["state"])
    state_value = None if state == "(All India)" else state

    # ---- H3 resolution ------------------------------------------------
    if KEYS["h3_resolution"] not in st.session_state:
        st.session_state[KEYS["h3_resolution"]] = 7
    h3_resolution = st.sidebar.select_slider(
        "H3 resolution",
        options=[6, 7, 8],
        key=KEYS["h3_resolution"],
        help="6 ≈ 36 km cells (state view) · 7 ≈ 5 km (district) · 8 ≈ 0.7 km (city block)",
    )

    # ---- Confidence threshold ----------------------------------------
    if KEYS["confidence_min"] not in st.session_state:
        st.session_state[KEYS["confidence_min"]] = 0.0
    confidence_min = st.sidebar.slider(
        "Min confidence",
        min_value=0.0, max_value=1.0, step=0.05,
        key=KEYS["confidence_min"],
        help="Hide cells whose evidence confidence is below this threshold. "
             "Useful for stripping data-deficient cells out of the map.",
    )

    # ---- Admin-boundary overlay ---------------------------------------
    if KEYS["admin_overlay"] not in st.session_state:
        st.session_state[KEYS["admin_overlay"]] = "None"
    admin_overlay = st.sidebar.radio(
        "Admin overlay",
        ADMIN_OVERLAYS,
        key=KEYS["admin_overlay"],
        horizontal=True,
        help="Overlay administrative boundaries on top of the H3 grid for context.",
    )

    # ---- NFHS-5 indicator (optional, for the disease-burden ribbon) ---
    indicator_options = ["(none)"] + sorted({i.column for d in domains for i in d.indicators})
    if KEYS["indicator"] not in st.session_state:
        st.session_state[KEYS["indicator"]] = default_indicator or "(none)"
    elif default_indicator and st.session_state.get("_indicator_domain") != domain_choice:
        # If the active domain just changed, snap the indicator to the
        # domain's first indicator so the page reflects the new lens.
        st.session_state[KEYS["indicator"]] = default_indicator
    st.session_state["_indicator_domain"] = domain_choice

    indicator_choice = st.sidebar.selectbox(
        "Disease-burden indicator (NFHS-5)",
        indicator_options,
        key=KEYS["indicator"],
        help="Pulls a district-level health indicator from NFHS-5 to contextualise supply.",
    )
    indicator_value = None if indicator_choice == "(none)" else indicator_choice

    if not states:
        st.sidebar.info(
            "Silver tables not deployed yet. Run the ETL job to populate filters.",
            icon="ℹ️",
        )

    return Filters(
        domain=None if domain_choice == "All capabilities" else domain_choice,
        capability=capability,
        state=state_value,
        h3_resolution=int(h3_resolution),
        h3_cell=st.session_state.get(KEYS["h3_cell"]),
        confidence_min=float(confidence_min),
        admin_overlay=admin_overlay,
        indicator=indicator_value,
    )


def set_selected_cell(h3_cell: str | None) -> None:
    st.session_state[KEYS["h3_cell"]] = h3_cell
