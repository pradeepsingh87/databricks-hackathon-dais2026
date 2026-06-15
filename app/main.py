import streamlit as st

st.set_page_config(
    page_title="Trust-Weighted Care Gap Navigator",
    page_icon="🏥",
    layout="wide",
)

st.title("Trust-Weighted Care Gap Navigator")
st.caption("Track 2 — Medical Desert Planner")

st.markdown(
    """
    Use the sidebar to:

    - **Map** — explore care gaps by capability and geography
    - **Drill-down** — inspect facilities and citations behind an aggregate
    - **Scenarios** — save and compare what-if planning scenarios
    - **Genie** — ask natural-language questions over the Gold layer
    """
)
