"""Sidebar filters shared across all pages.

Selections persist in st.session_state under stable keys so Map → Drill-down
→ Scenarios all read the same context. Each page calls render_sidebar() at
the top and gets back the current selection.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from app.services import gold

KEYS = {
    "capability": "filter_capability",
    "state": "filter_state",
    "h3_resolution": "filter_h3_resolution",
    "h3_cell": "selected_h3_cell",     # set by the Map page when a cell is clicked
}


@dataclass
class Filters:
    capability: str
    state: str | None
    h3_resolution: int
    h3_cell: str | None


def render_sidebar() -> Filters:
    st.sidebar.header("Filters")

    caps = gold.list_capabilities()
    if KEYS["capability"] not in st.session_state:
        st.session_state[KEYS["capability"]] = caps[0]
    capability = st.sidebar.selectbox("Capability", caps, key=KEYS["capability"])

    states = gold.list_states()
    state_options = ["(All India)"] + states
    if KEYS["state"] not in st.session_state:
        st.session_state[KEYS["state"]] = "(All India)"
    state = st.sidebar.selectbox("State", state_options, key=KEYS["state"])
    state_value = None if state == "(All India)" else state

    if KEYS["h3_resolution"] not in st.session_state:
        st.session_state[KEYS["h3_resolution"]] = 7
    h3_resolution = st.sidebar.select_slider(
        "H3 resolution",
        options=[6, 7, 8],
        key=KEYS["h3_resolution"],
        help="6 ≈ 36 km cells (state view) · 7 ≈ 5 km (district) · 8 ≈ 0.7 km (city block)",
    )

    if not states:
        st.sidebar.info(
            "Silver tables not deployed yet. Run the ETL job to populate filters.",
            icon="ℹ️",
        )

    return Filters(
        capability=capability,
        state=state_value,
        h3_resolution=int(h3_resolution),
        h3_cell=st.session_state.get(KEYS["h3_cell"]),
    )


def set_selected_cell(h3_cell: str | None) -> None:
    st.session_state[KEYS["h3_cell"]] = h3_cell
