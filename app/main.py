"""Executive Command Center — homepage of the Care Gap Navigator app.

Layout:
  1. Brand strip
  2. Search bar — facility/city/district lookup
  3. "For You" — recently saved scenarios + overrides for this user
  4. Domains — one card per domain, deep-links into the Care Gap Navigator
  5. Top care gaps — worst-served districts overall

Note: natural-language Q&A lives on the Genie page (sidebar), not here, so
this page stays focused on a single primary action — *find a facility*.
"""

import sys
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

import streamlit as st  # noqa: E402

from components.filters import KEYS as FILTER_KEYS  # noqa: E402
from services import brand, gold, lakebase  # noqa: E402
from services.domains import load_domains  # noqa: E402
from services.user import current_user  # noqa: E402

st.set_page_config(
    page_title="Home",
    page_icon="🏥",
    layout="wide",
)

brand.render_header(subtitle=f"Signed in as {current_user()}")

# ---- 1. Search ----------------------------------------------------------
with st.container(border=True):
    q = st.text_input(
        "Find a facility",
        key="home_search_q",
        placeholder="Facility name, city, district, or state — e.g. 'Apollo Mumbai' · 'Patna' · 'Bihar'",
        label_visibility="collapsed",
    )
    if q:
        results = gold.search_facilities(q, limit=20)
        if results.empty:
            st.caption("No facilities matched. Try a broader term.")
        else:
            st.dataframe(results, use_container_width=True, hide_index=True)
            st.caption(
                "Open the **Care Gap Navigator** to see one of these on the map, "
                "or **Genie** in the sidebar to ask a free-form question."
            )

st.markdown("&nbsp;")

# ---- 2. For You ---------------------------------------------------------
st.subheader("For you")
me = current_user()
left, right = st.columns(2)

with left:
    st.caption("**Recent scenarios**")
    scenarios = lakebase.list_scenarios(me)
    if scenarios.empty:
        st.info(
            "No saved scenarios yet. Open the **Care Gap Navigator** and use "
            "**Save scenario** on the Scenarios page.",
            icon="📋",
        )
    else:
        st.dataframe(
            scenarios.head(5).drop(columns=["payload"]),
            use_container_width=True,
            hide_index=True,
        )

with right:
    st.caption("**Recent overrides**")
    ov = lakebase.list_overrides(me)
    if ov.empty:
        st.info(
            "No overrides yet. Open a facility on the **Action Center** and "
            "add a note to flag suspicious or verified evidence.",
            icon="📝",
        )
    else:
        st.dataframe(ov.head(5), use_container_width=True, hide_index=True)

st.markdown("&nbsp;")

# ---- 3. Domains ---------------------------------------------------------
st.subheader("Browse by domain")
st.caption(
    "Each domain bundles the capabilities + NFHS-5 indicators that matter "
    "for one planning lens. Click a domain to open the Care Gap Navigator "
    "pre-filtered to that lens."
)

domains = load_domains()
if domains:
    cols = st.columns(min(4, len(domains)))
    for i, d in enumerate(domains):
        with cols[i % len(cols)]:
            with st.container(border=True):
                st.markdown(
                    f"<div style='font-size:24px;line-height:1;'>{d.icon}</div>"
                    f"<div style='font-weight:600;margin-top:6px;color:var(--brand-text);'>"
                    f"{d.name}</div>"
                    f"<div style='font-size:12px;color:var(--brand-muted);"
                    f"margin-top:4px;min-height:34px;'>{d.blurb}</div>",
                    unsafe_allow_html=True,
                )
                st.caption(f"Capabilities · `{', '.join(d.capabilities)}`")
                if st.button(
                    "Open in navigator",
                    key=f"open-{d.id}",
                    use_container_width=True,
                ):
                    # Pre-filter the navigator: domain + first capability + first indicator.
                    st.session_state[FILTER_KEYS["domain"]] = d.id
                    st.session_state[FILTER_KEYS["capability"]] = d.capabilities[0] if d.capabilities else None
                    st.session_state[FILTER_KEYS["indicator"]] = (
                        d.indicators[0].column if d.indicators else "(none)"
                    )
                    st.switch_page("pages/1_Care_Gap_Navigator.py")
else:
    st.info("No domains configured. Edit `config/domains.yml` to add them.")

st.markdown("&nbsp;")

# ---- 4. Top care gaps ---------------------------------------------------
st.subheader("Top care gaps right now")
gap_cap_col, _ = st.columns([1, 4])
with gap_cap_col:
    cap = st.selectbox(
        "Capability",
        gold.list_capabilities(),
        key="home_top_gaps_cap",
        label_visibility="collapsed",
    )
gaps = gold.fetch_top_care_gaps(cap, limit=8)
if gaps.empty:
    st.caption(
        "Top-gaps list will appear once `gold.care_score_by_district` is populated."
    )
else:
    st.dataframe(
        gaps,
        use_container_width=True,
        hide_index=True,
        column_config={
            "score":      st.column_config.ProgressColumn(
                "score", min_value=0.0, max_value=1.0, format="%.2f",
            ),
            "confidence": st.column_config.ProgressColumn(
                "confidence", min_value=0.0, max_value=1.0, format="%.2f",
            ),
            "n_facilities": st.column_config.NumberColumn("n facilities", format="%d"),
        },
    )

# ---- 5. Diagnostics tail ------------------------------------------------
if err := st.session_state.get("_last_query_error"):
    with st.expander("Last query error", expanded=False):
        st.code(err, language="text")
