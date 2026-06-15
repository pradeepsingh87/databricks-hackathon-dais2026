import sys
from pathlib import Path

# Ensure repo-root on sys.path so `from app...` works whether streamlit is
# launched from the repo root or from the app/ directory (Databricks Apps).
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st  # noqa: E402

from app.components.filters import render_sidebar  # noqa: E402

st.set_page_config(
    page_title="Trust-Weighted Care Gap Navigator",
    page_icon="🏥",
    layout="wide",
)

filters = render_sidebar()

st.title("Trust-Weighted Care Gap Navigator")
st.caption("Track 2 — Medical Desert Planner")

st.markdown(
    """
    Use the sidebar to pick a **capability** (e.g. ICU, maternity) and a **state**.
    Then navigate:

    - **Map** — H3 grid coloured by care score, transparency = confidence
    - **Drill-down** — facilities and citations behind a selected cell
    - **Scenarios** — save and compare what-if planning scenarios
    - **Genie** — natural-language Q&A over the Gold layer
    """
)

st.divider()
c1, c2, c3 = st.columns(3)
c1.metric("Capability", filters.capability)
c2.metric("State", filters.state or "All India")
c3.metric("H3 resolution", filters.h3_resolution)

if filters.h3_cell:
    st.success(
        f"Cell **{filters.h3_cell}** selected. Open the **Drill-down** page to inspect facilities.",
        icon="🎯",
    )

if err := st.session_state.get("_last_query_error"):
    with st.expander("Last query error", expanded=False):
        st.code(err, language="text")
