import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import json  # noqa: E402

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.components.filters import render_sidebar  # noqa: E402
from app.services import gold, lakebase  # noqa: E402

st.set_page_config(page_title="Drill-down", page_icon="🔎", layout="wide")
filters = render_sidebar()

st.title("Drill-down: Facilities & Citations")
st.caption("Every aggregate is backed by direct quotes from facility text.")

if not filters.h3_cell and not filters.state:
    st.info(
        "Pick a state from the sidebar **or** select an H3 cell on the **Map** page first.",
        icon="👆",
    )
    st.stop()

if filters.h3_cell:
    st.subheader(f"Cell {filters.h3_cell} · capability **{filters.capability}**")
    df = gold.fetch_facilities_in_cell(filters.h3_cell, filters.capability)
else:
    st.subheader(f"State {filters.state} · capability **{filters.capability}**")
    df = gold.fetch_facilities_in_region(filters.capability, filters.state)

if df.empty:
    st.warning(
        "No facilities found for this selection. "
        "Either Silver isn't deployed, or this region truly has no records — "
        "the **Map** transparency channel signals which.",
        icon="⚠️",
    )
    st.stop()

st.write(f"**{len(df)} facilities**")

for _, row in df.iterrows():
    title = f"**{row.get('name') or 'Unnamed'}**"
    badge = row.get("evidence_strength")
    if pd.notna(badge):
        title += f" · _{badge}_"
    with st.expander(f"{title} — {row.get('city') or ''}, {row.get('state') or ''}"):
        st.write(f"facility_id: `{row.get('facility_id')}`")

        cites = row.get("citations")
        if isinstance(cites, str):
            try:
                cites = json.loads(cites)
            except Exception:  # noqa: BLE001
                cites = [{"text": cites, "source_field": "description"}]
        if isinstance(cites, list) and cites:
            st.markdown("**Citations**")
            for c in cites:
                if isinstance(c, dict):
                    st.markdown(
                        f"> {c.get('text', '')}\n\n"
                        f"_— {c.get('source_field', '?')}"
                        f"{' · ' + c.get('source_url', '') if c.get('source_url') else ''}_"
                    )
                else:
                    st.markdown(f"> {c}")
        else:
            st.caption("No structured citations yet — claim extraction (gap #1) pending.")

        with st.form(f"override-{row.get('facility_id')}"):
            note = st.text_area(
                "Override / note",
                placeholder="e.g. 'Visited in 2024 — ICU not actually staffed'",
                key=f"note-{row.get('facility_id')}",
            )
            if st.form_submit_button("Save override"):
                ok = lakebase.add_override(
                    user="demo",  # TODO: replace with Databricks Apps user header
                    facility_id=row.get("facility_id"),
                    capability=filters.capability,
                    note=note,
                )
                if ok:
                    st.success("Saved.", icon="✅")
                else:
                    st.error("Save failed — see the error in the sidebar / main page.")
