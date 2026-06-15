import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import json  # noqa: E402

import streamlit as st  # noqa: E402

from app.components.filters import render_sidebar  # noqa: E402
from app.services import lakebase  # noqa: E402

st.set_page_config(page_title="Scenarios", page_icon="📋", layout="wide")
filters = render_sidebar()

st.title("Planning Scenarios")
st.caption("Save what-if allocations and overrides for NGO coordination.")

USER = "demo"  # TODO: replace with Databricks Apps end-user header

# ---- Saved scenarios ------------------------------------------------------
st.subheader("Saved scenarios")
saved = lakebase.list_scenarios(USER)
if saved.empty:
    st.info("No scenarios yet — create one below.", icon="📭")
else:
    st.dataframe(saved.drop(columns=["payload"]), use_container_width=True, hide_index=True)
    pick = st.selectbox(
        "Inspect a scenario",
        options=saved["id"].tolist(),
        format_func=lambda i: saved.loc[saved.id == i, "name"].iloc[0],
    )
    payload_str = saved.loc[saved.id == pick, "payload"].iloc[0]
    try:
        st.json(json.loads(payload_str) if isinstance(payload_str, str) else payload_str)
    except Exception:  # noqa: BLE001
        st.code(str(payload_str))

st.divider()

# ---- Create scenario ------------------------------------------------------
st.subheader("New scenario")
st.caption(
    f"Captures the current sidebar filter set "
    f"(capability=**{filters.capability}**, state=**{filters.state or 'All India'}**, "
    f"H3 res=**{filters.h3_resolution}**) plus your hypothesis below."
)

with st.form("new-scenario"):
    name = st.text_input("Name", placeholder="e.g. 'Add 3 ICUs in Bihar'")
    hypothesis = st.text_area(
        "Hypothesis / what-if",
        placeholder="Describe the hypothetical resource allocation or override.",
    )
    if st.form_submit_button("Save scenario", type="primary"):
        payload = {
            "filters": {
                "capability": filters.capability,
                "state": filters.state,
                "h3_resolution": filters.h3_resolution,
                "h3_cell": filters.h3_cell,
            },
            "hypothesis": hypothesis,
        }
        if lakebase.save_scenario(USER, name, payload):
            st.success(f"Saved scenario '{name}'.", icon="✅")
            st.rerun()
        else:
            st.error("Save failed — name required, or Lakebase tables not deployed.")

# ---- Recent overrides -----------------------------------------------------
st.divider()
st.subheader("Recent overrides")
ov = lakebase.list_overrides(USER)
if ov.empty:
    st.caption("No overrides yet. Add them from the **Drill-down** page.")
else:
    st.dataframe(ov, use_container_width=True, hide_index=True)
