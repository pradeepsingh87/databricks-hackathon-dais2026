import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st  # noqa: E402

from app.components.filters import render_sidebar, set_selected_cell  # noqa: E402
from app.components.kepler_map import render_h3_map  # noqa: E402
from app.services import gold  # noqa: E402

st.set_page_config(page_title="Map", page_icon="🗺️", layout="wide")
filters = render_sidebar()

st.title("Care Gap Map")
st.caption(
    f"Capability: **{filters.capability}** · "
    f"State: **{filters.state or 'All India'}** · "
    f"H3 res: **{filters.h3_resolution}**"
)

df = gold.fetch_h3_scores(
    capability=filters.capability,
    resolution=filters.h3_resolution,
    state=filters.state,
)

render_h3_map(df, key=f"map-{filters.capability}-{filters.h3_resolution}-{filters.state or 'all'}")

if not df.empty:
    st.subheader("Pick a cell to drill into")
    st.caption("Choose an H3 cell from the table — the Drill-down page will use it.")
    sorted_df = df.sort_values("score", ascending=True)
    selected = st.selectbox(
        "Cell",
        options=sorted_df["h3_cell"].tolist(),
        format_func=lambda h: (
            f"{h} · score={float(sorted_df.loc[sorted_df.h3_cell == h, 'score'].iloc[0]):.2f}"
            f" · n={int(sorted_df.loc[sorted_df.h3_cell == h, 'n_facilities'].iloc[0])}"
        ),
    )
    if st.button("Use this cell for drill-down", type="primary"):
        set_selected_cell(selected)
        st.success(f"Selected {selected}. Open the **Drill-down** page in the sidebar.")

    with st.expander("Underlying data", expanded=False):
        st.dataframe(df, use_container_width=True, hide_index=True)
