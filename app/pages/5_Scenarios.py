import sys
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parents[1]
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

import json  # noqa: E402

import streamlit as st  # noqa: E402

from components import facility_map  # noqa: E402
from components.filters import render_sidebar  # noqa: E402
from services import brand, gold, lakebase  # noqa: E402
from services.user import current_user  # noqa: E402

st.set_page_config(
    page_title=f"Scenarios · {brand.load_brand().name}",
    page_icon="📋", layout="wide",
)
brand.render_header(subtitle="Planning scenarios persisted to Lakebase")
filters = render_sidebar()

st.markdown("### Planning Scenarios")
st.caption(f"Save what-if allocations and overrides — signed in as **{current_user()}**.")

USER = current_user()

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
        payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
    except Exception:  # noqa: BLE001
        payload = None

    payload_col, map_col = st.columns([1, 1])
    with payload_col:
        if payload is not None:
            st.json(payload)
        else:
            st.code(str(payload_str))

    with map_col:
        # Replay the saved filter set as a small location preview so the
        # planner can see *where* the scenario applies, not just abstract
        # filter chips.
        sf = (payload or {}).get("filters") or {}
        cap = sf.get("capability") or filters.capability
        scenario_locations = gold.fetch_facility_locations(
            capability=cap,
            state=sf.get("state") if not sf.get("h3_cell") else None,
            h3_cell=sf.get("h3_cell"),
            resolution=sf.get("h3_resolution") or 7,
            limit=500,
        )
        st.caption(f"Locations in scope · capability **{cap}**")
        facility_map.render(scenario_locations, height=320, key=f"scn-map-{pick}")
        facility_map.render_legend()

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

# ---- Filter bookmarks (multi-team coordination) ------------------------
# A bookmark is a JSON snapshot of the current filter set; teammates can
# load one to land on the same view their colleague was looking at.
st.divider()
st.subheader("Filter bookmarks")
st.caption("Save the current sidebar filter state. Share with teammates so they land on the same view.")

bm_left, bm_right = st.columns([3, 2])
with bm_left:
    with st.form("new-bookmark"):
        bm_name = st.text_input(
            "Bookmark name",
            placeholder="e.g. 'Bihar maternity — high desert risk'",
        )
        bm_shared = st.checkbox(
            "Share with teammates", value=False,
            help="When checked, this bookmark is visible to everyone in the workspace.",
        )
        if st.form_submit_button("Save bookmark", use_container_width=True):
            ok = lakebase.save_bookmark(
                USER, bm_name,
                {
                    "capability":    filters.capability,
                    "state":         filters.state,
                    "h3_resolution": filters.h3_resolution,
                    "h3_cell":       filters.h3_cell,
                    "indicator":     filters.indicator,
                    "domain":        filters.domain,
                },
                shared=bm_shared,
            )
            if ok:
                st.success(f"Saved bookmark '{bm_name}'.", icon="🔖")
                st.rerun()
            else:
                st.error("Save failed — name required, or Lakebase not deployed.")

with bm_right:
    bookmarks = lakebase.list_bookmarks(USER, include_shared=True)
    if bookmarks.empty:
        st.caption("No bookmarks yet — create one to your left.")
    else:
        st.dataframe(
            bookmarks[["name", "user_name", "shared", "created_at"]].head(8),
            use_container_width=True, hide_index=True,
            column_config={
                "name":       st.column_config.TextColumn("name"),
                "user_name":  st.column_config.TextColumn("by"),
                "shared":     st.column_config.CheckboxColumn("shared", disabled=True),
                "created_at": st.column_config.DatetimeColumn("when", format="MMM D, h:mma"),
            },
        )

# ---- Root-cause categorisations (cross-team summary) -------------------
st.divider()
st.subheader("Recent root-cause tags (NACHC)")
st.caption("All teammates' gap categorisations across capabilities. Filter via the sidebar.")
gap_log = lakebase.list_gap_categorizations(
    capability=filters.capability,
    state=filters.state,
)
if gap_log.empty:
    st.caption("No categorisations yet — tag a cell from the **Care Gap Navigator** or **Action Center**.")
else:
    st.dataframe(
        gap_log[["created_at", "user_name", "category", "severity",
                 "capability", "state", "district", "h3_cell", "note"]].head(20),
        use_container_width=True, hide_index=True,
    )

# ---- Recent overrides -----------------------------------------------------
st.divider()
st.subheader("Recent overrides")
ov = lakebase.list_overrides(USER)
if ov.empty:
    st.caption("No overrides yet. Add them from the **Action Center** page.")
else:
    st.dataframe(ov, use_container_width=True, hide_index=True)
