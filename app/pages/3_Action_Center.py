"""Evidence & Action Center — drill-down for a cell or a region.

Layout:
  1. Brand strip + page title + selection chips
  2. Location map (point markers, color = evidence_strength, size ∝ capacity)
  3. Trust-signal summary: counts of strong / partial / suspicious / none
  4. Facility cards — name, badge, structured citations, override form
  5. Save scenario shortcut — same context, persisted to Lakebase
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import json  # noqa: E402

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.components import facility_map, root_cause_panel  # noqa: E402
from app.components.filters import render_sidebar  # noqa: E402
from app.services import brand, gold, lakebase  # noqa: E402
from app.services.user import current_user  # noqa: E402

st.set_page_config(
    page_title=f"Action Center · {brand.load_brand().name}",
    page_icon="🔎", layout="wide",
)
brand.render_header(subtitle="Evidence drill-down · facility-level overrides & notes")
filters = render_sidebar()

# ---- Selection chips ---------------------------------------------------
st.markdown("### Action Center")
chip_html = (
    "<span style='font-size:13px;color:var(--brand-muted);'>"
    f"capability <b>{filters.capability}</b> · "
    f"{'cell <b>' + filters.h3_cell + '</b>' if filters.h3_cell else 'state <b>' + (filters.state or 'All India') + '</b>'}"
    "</span>"
)
st.markdown(chip_html, unsafe_allow_html=True)
with st.expander("How to use this page", expanded=False):
    st.markdown(
        "1. Each card shows one facility's claim for the selected capability.\n"
        "2. The badge (✅ / 🟡 / 🚩 / ⚪) summarises the evidence we found.\n"
        "3. Click a card to expand citations — the *exact text* from the "
        "facility record that justifies the claim.\n"
        "4. Use **Add note** to flag a claim, **Save scenario** at the bottom "
        "to bookmark this view for teammates.\n"
        "5. Use the **Root Cause Analysis** panel above the cards to "
        "categorise the gap (Data / Service / Engagement) — visible to "
        "everyone on your team."
    )

if not filters.h3_cell and not filters.state:
    st.info(
        "Pick a state from the sidebar **or** select an H3 cell on the "
        "**Care Gap Navigator** page first.",
        icon="👆",
    )
    st.stop()

# ---- Pull facility records & their per-capability claim ----------------
if filters.h3_cell:
    df = gold.fetch_facilities_in_cell(
        filters.h3_cell, filters.capability, resolution=filters.h3_resolution,
    )
else:
    df = gold.fetch_facilities_in_region(filters.capability, filters.state)

if df.empty:
    st.warning(
        "No facilities found for this selection. "
        "Either Silver isn't deployed, or this region truly has no records — "
        "the Care Gap Navigator's transparency channel signals which.",
        icon="⚠️",
    )
    st.stop()

# ---- Location map ------------------------------------------------------
st.markdown("#### Where these facilities are")
locations = gold.fetch_facility_locations(
    capability=filters.capability,
    state=filters.state if not filters.h3_cell else None,
    h3_cell=filters.h3_cell,
    resolution=filters.h3_resolution,
)
facility_map.render(
    locations,
    key=f"facmap-{filters.capability}-{filters.h3_cell or filters.state or 'all'}",
)
facility_map.render_legend()

# ---- Trust signal summary ----------------------------------------------
st.markdown("#### Trust signals in this view")
strength_counts = (
    df["evidence_strength"]
    .fillna("none")
    .astype(str)
    .str.lower()
    .value_counts()
)
c1, c2, c3, c4 = st.columns(4)
c1.metric("✅ Strong",     int(strength_counts.get("strong", 0)))
c2.metric("🟡 Partial",    int(strength_counts.get("partial", 0)))
c3.metric("🚩 Suspicious", int(strength_counts.get("suspicious", 0)))
c4.metric("⚪ Unknown",    int(strength_counts.get("none", 0)))

# ---- NACHC Root Cause Analysis side-panel ------------------------------
# Sits between the trust-signal summary and the per-facility workflow so the
# planner can categorise the gap *before* drilling into individual citations.
st.divider()
root_cause_panel.render(
    root_cause_panel.Selection(
        capability=filters.capability,
        state=filters.state,
        h3_cell=filters.h3_cell,
    ),
    location="cell" if filters.h3_cell else "state",
    key_prefix="ac",
)

# ---- Facility cards ----------------------------------------------------
st.divider()
st.markdown(f"#### Facility records & citations · **{len(df)}** facilities")

BADGE = {
    "strong":     ("✅ Strongly supported", "#1a9850"),
    "partial":    ("🟡 Partial evidence",   "#f4a261"),
    "suspicious": ("🚩 Suspicious",         "#d73027"),
    "none":       ("⚪ Unknown",            "#94a3b8"),
}


def _render_badge(strength) -> None:
    key = "none" if pd.isna(strength) else str(strength).lower()
    label, color = BADGE.get(key, BADGE["none"])
    st.markdown(
        f"<span style='display:inline-block;padding:2px 10px;border-radius:999px;"
        f"background:{color}22;color:{color};font-size:12px;font-weight:600;'>"
        f"{label}</span>",
        unsafe_allow_html=True,
    )


for _, row in df.iterrows():
    with st.expander(
        f"**{row.get('name') or 'Unnamed'}**  —  "
        f"{row.get('city') or ''}, {row.get('state') or ''}",
    ):
        col_left, col_right = st.columns([3, 2])
        with col_left:
            _render_badge(row.get("evidence_strength"))
            st.caption(f"facility_id · `{row.get('facility_id')}`")

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
                        url = c.get("source_url") or ""
                        url_html = (
                            f' · <a href="{url}" target="_blank" '
                            f'style="color:var(--brand-primary);">source</a>'
                            if url else ""
                        )
                        st.markdown(
                            f"> {c.get('text', '')}\n\n"
                            f"<span style='font-size:11px;color:var(--brand-muted);'>"
                            f"— {c.get('source_field', '?')}{url_html}</span>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(f"> {c}")
            else:
                st.caption("No structured citations available for this facility.")

        with col_right:
            with st.form(f"override-{row.get('facility_id')}", clear_on_submit=True):
                st.markdown("**Flag or note**")
                action = st.radio(
                    "Action",
                    ["Add note", "Flag suspicious", "Mark verified"],
                    horizontal=True,
                    label_visibility="collapsed",
                )
                note = st.text_area(
                    "Note",
                    placeholder="e.g. 'Verified via phone call — no functioning oxygen concentrators'",
                    label_visibility="collapsed",
                )
                if st.form_submit_button("Save", use_container_width=True, type="primary"):
                    annotated = f"[{action}] {note}".strip() if note else action
                    ok = lakebase.add_override(
                        user=current_user(),
                        facility_id=row.get("facility_id"),
                        capability=filters.capability,
                        note=annotated,
                    )
                    if ok:
                        st.success("Saved to Lakebase.", icon="✅")
                    else:
                        st.error(
                            "Save failed. Either the note was empty, or Lakebase "
                            "isn't provisioned yet (run `./scripts/setup_uc.sh`)."
                        )

# ---- Save current view as a scenario -----------------------------------
st.divider()
st.markdown("#### Save this view as a planning scenario")
with st.form("save-scenario-from-action"):
    name = st.text_input("Scenario name", placeholder="e.g. 'ICU drill-down — Patna'")
    summary = st.text_area(
        "Hypothesis / context",
        placeholder="What does this view tell you? What's the next planning step?",
    )
    if st.form_submit_button("Save scenario", type="primary"):
        payload = {
            "filters": {
                "capability": filters.capability,
                "state": filters.state,
                "h3_resolution": filters.h3_resolution,
                "h3_cell": filters.h3_cell,
                "indicator": filters.indicator,
                "domain": filters.domain,
            },
            "hypothesis": summary,
            "n_facilities": int(len(df)),
        }
        if lakebase.save_scenario(current_user(), name, payload):
            st.success(f"Saved scenario '{name}'. Open the **Scenarios** page to review.")
        else:
            st.error("Save failed — name required, or Lakebase not deployed yet.")
