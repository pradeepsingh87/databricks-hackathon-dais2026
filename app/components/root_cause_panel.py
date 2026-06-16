"""NACHC-inspired Root Cause Analysis side-panel.

Categorises a care gap as one of three root-cause buckets (NACHC's clinical-
gap-closure framework):

  - **Data Gap**         — we cannot tell whether care exists (data deficient,
                            stale records, no facility coverage at all).
  - **Service Delivery** — care is reported as available but evidence
                            (citations / capacity) suggests it isn't.
  - **Engagement**       — care exists but populations aren't reaching it
                            (e.g. low NFHS-5 institutional-birth coverage in a
                            district with adequate maternity infrastructure).

Renders inside an st.expander so it stays out of the way until the planner
clicks it. Persists to lakebase.gap_categorizations so multiple teams can
see who's working on which gap.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from services import lakebase
from services.user import current_user

CATEGORIES: list[tuple[str, str, str]] = [
    # (db value, display label, one-line explanation)
    ("data",       "🔍 Data Gap",         "We can't tell if care exists. Evidence is thin or stale."),
    ("service",    "🏥 Service Delivery", "Care is claimed but evidence suggests delivery is weak."),
    ("engagement", "📣 Engagement",       "Care exists; populations aren't reaching it (low utilisation)."),
]
SEVERITIES = ["low", "medium", "high"]


@dataclass
class Selection:
    """The contextual selection that the categorization is tied to."""
    capability: str
    state: str | None = None
    district: str | None = None
    h3_cell: str | None = None


def render(selection: Selection, *, location: str = "page", key_prefix: str = "rc") -> None:
    """Render the side-panel.

    `location` is just a label for the expander title — usually "cell" or
    "district" so the planner sees what's being categorised.
    """
    st.markdown(
        '<div style="font-size:12px;color:var(--brand-muted);'
        'letter-spacing:0.06em;text-transform:uppercase;margin-bottom:6px;">'
        'Root Cause Analysis · NACHC</div>',
        unsafe_allow_html=True,
    )

    label_bits = [f"capability **{selection.capability}**"]
    if selection.h3_cell:
        label_bits.append(f"cell `{selection.h3_cell}`")
    if selection.district:
        label_bits.append(f"district **{selection.district}**")
    if selection.state:
        label_bits.append(f"state **{selection.state}**")
    st.caption(" · ".join(label_bits))

    cols = st.columns(3)
    for i, (val, label, blurb) in enumerate(CATEGORIES):
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"**{label}**")
                st.caption(blurb)
                with st.form(f"{key_prefix}-form-{val}", clear_on_submit=True):
                    severity = st.select_slider(
                        "Severity", options=SEVERITIES, value="medium",
                        key=f"{key_prefix}-sev-{val}",
                        label_visibility="collapsed",
                    )
                    note = st.text_area(
                        "Note (optional)",
                        placeholder="e.g. 'No registry coverage in 2 of 4 sub-districts.'",
                        key=f"{key_prefix}-note-{val}",
                        height=70,
                        label_visibility="collapsed",
                    )
                    submitted = st.form_submit_button(
                        f"Tag as {label.split(' ', 1)[1]}",
                        use_container_width=True,
                    )
                    if submitted:
                        ok = lakebase.add_gap_categorization(
                            user=current_user(),
                            capability=selection.capability,
                            state=selection.state,
                            district=selection.district,
                            h3_cell=selection.h3_cell,
                            category=val,
                            severity=severity,
                            note=note or None,
                        )
                        if ok:
                            st.success(f"Tagged as {label}.", icon="✅")
                        else:
                            st.error(
                                "Save failed — Lakebase may not be deployed yet "
                                "(run `./scripts/setup_uc.sh`)."
                            )

    # Recent categorisations for this scope (capability + state if set).
    history = lakebase.list_gap_categorizations(
        capability=selection.capability,
        state=selection.state,
    )
    if not history.empty:
        with st.expander(f"Recent categorisations ({len(history)})", expanded=False):
            st.dataframe(
                history[["created_at", "user_name", "category", "severity",
                         "district", "h3_cell", "note"]],
                use_container_width=True, hide_index=True,
                column_config={
                    "created_at": st.column_config.DatetimeColumn("when", format="MMM D, h:mma"),
                    "user_name":  st.column_config.TextColumn("by"),
                    "category":   st.column_config.TextColumn("category"),
                    "severity":   st.column_config.TextColumn("sev"),
                },
            )
