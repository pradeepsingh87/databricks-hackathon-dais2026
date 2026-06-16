"""Genie AI Discovery — inline conversational room.

The user types a question; we POST it to the Genie API; we render the answer
right here (text + generated SQL + result table + follow-up chips). No
handoff to a separate page or tab. Conversation state persists in
`st.session_state` so multi-turn questions keep context.
"""

import sys
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parents[1]
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

import os  # noqa: E402

import streamlit as st  # noqa: E402

from components.filters import render_sidebar  # noqa: E402
from services import brand, genie  # noqa: E402

st.set_page_config(
    page_title=f"Genie · {brand.load_brand().name}",
    page_icon="🧞", layout="wide",
)
brand.render_header(subtitle="Natural-language Q&A over the Gold + Silver layers")
filters = render_sidebar()

st.markdown("### Ask Genie")
st.caption(
    "Genie translates your question into SQL using the Unity Catalog "
    "semantic layer, runs it on the warehouse, and renders the result here. "
    "Every answer carries the SQL it generated for transparency."
)

# ---- Configuration check ------------------------------------------------
if not genie.is_configured():
    with st.container(border=True):
        st.warning(
            "Genie is not configured. Set `GENIE_SPACE_ID` on the app and "
            "make sure Databricks auth is available — on Databricks Apps "
            "this is automatic; locally, run `databricks auth login` or set "
            "`DATABRICKS_HOST` + `DATABRICKS_TOKEN` in your `.env`. "
            "Provision the space with `./scripts/setup_genie.sh`.",
            icon="🧞",
        )
    st.stop()

# ---- Chat state ---------------------------------------------------------
HIST_KEY = "genie_history"          # list[dict]: {role, text, sql?, rows?, follow_ups?}
CONV_KEY = "genie_conversation_id"
PEND_KEY = "genie_pending_question"  # set when a follow-up chip is clicked

if HIST_KEY not in st.session_state:
    st.session_state[HIST_KEY] = []
if CONV_KEY not in st.session_state:
    st.session_state[CONV_KEY] = None


def _ask_and_record(q: str) -> None:
    """Send question, collect response, append to history."""
    st.session_state[HIST_KEY].append({"role": "user", "text": q})
    with st.spinner("Genie is thinking…"):
        try:
            answer = genie.ask(q, conversation_id=st.session_state.get(CONV_KEY))
        except Exception as e:  # noqa: BLE001 — surface the message verbatim
            st.session_state[HIST_KEY].append({"role": "error", "text": str(e)})
            return
    if answer is None:
        st.session_state[HIST_KEY].append({"role": "error",
                                           "text": "Genie not configured."})
        return
    st.session_state[CONV_KEY] = answer.conversation_id

    rows = None
    if answer.sql:
        try:
            rows = genie.fetch_rows(answer)
        except Exception as e:  # noqa: BLE001
            rows = None
            answer.text = (answer.text or "") + f"\n\n*(could not run SQL: {e})*"

    st.session_state[HIST_KEY].append({
        "role": "genie",
        "text": answer.text,
        "sql": answer.sql,
        "sql_description": answer.sql_description,
        "rows": rows,
        "follow_ups": answer.follow_ups,
    })


# ---- Pending question (from a follow-up chip) ---------------------------
if PEND_KEY in st.session_state:
    pending = st.session_state.pop(PEND_KEY)
    if pending:
        _ask_and_record(pending)

# ---- Top bar: starter prompts (only when history is empty) -------------
if not st.session_state[HIST_KEY]:
    state = filters.state or "Bihar"
    starters = [
        f"Where are the highest-risk {filters.capability} gaps in {state}?",
        f"Which districts have low {filters.capability} coverage but high evidence confidence?",
        f"List facilities claiming {filters.capability} services with only suspicious evidence.",
        f"Compare {filters.capability} care scores across states.",
    ]
    st.markdown("**Try one of these to start:**")
    cols = st.columns(2)
    for i, s in enumerate(starters):
        with cols[i % 2]:
            if st.button(s, key=f"starter-{i}", use_container_width=True):
                st.session_state[PEND_KEY] = s
                st.rerun()
    st.divider()

# ---- Render conversation history ---------------------------------------
for i, turn in enumerate(st.session_state[HIST_KEY]):
    if turn["role"] == "user":
        with st.chat_message("user"):
            st.markdown(turn["text"])
    elif turn["role"] == "error":
        with st.chat_message("assistant", avatar="🧞"):
            st.error(turn["text"])
    else:  # genie
        with st.chat_message("assistant", avatar="🧞"):
            if turn.get("text"):
                st.markdown(turn["text"])
            rows = turn.get("rows")
            if rows is not None and not rows.empty:
                # Pick a sensible default rendering: ≤ 1 row → metric-style;
                # 2..50 rows with one numeric column → bar chart; else table.
                numeric_cols = [c for c in rows.columns
                                if str(rows[c].dtype).startswith(("int", "float"))]
                if len(rows) == 1 and len(rows.columns) == 1:
                    st.metric(rows.columns[0], f"{rows.iloc[0, 0]}")
                elif 1 < len(rows) <= 50 and len(numeric_cols) == 1 and len(rows.columns) >= 2:
                    label_col = next(c for c in rows.columns if c not in numeric_cols)
                    st.bar_chart(rows.set_index(label_col)[numeric_cols], height=320)
                else:
                    st.dataframe(rows, hide_index=True, use_container_width=True)
            elif turn.get("sql"):
                st.caption("Query returned no rows.")

            if turn.get("sql"):
                with st.expander("Generated SQL", expanded=False):
                    if turn.get("sql_description"):
                        st.caption(turn["sql_description"])
                    st.code(turn["sql"], language="sql")

            follow_ups = turn.get("follow_ups") or []
            if follow_ups and i == len(st.session_state[HIST_KEY]) - 1:
                # Only show follow-ups for the latest turn — keeps the page tidy.
                st.markdown(
                    "<div style='font-size:12px;color:var(--brand-muted);"
                    "margin-top:8px;'>Suggested follow-ups</div>",
                    unsafe_allow_html=True,
                )
                fcols = st.columns(min(3, len(follow_ups)))
                for fi, fq in enumerate(follow_ups[:3]):
                    with fcols[fi % len(fcols)]:
                        if st.button(fq, key=f"fup-{i}-{fi}", use_container_width=True):
                            st.session_state[PEND_KEY] = fq
                            st.rerun()

# ---- Input box (sticky bottom) -----------------------------------------
prompt = st.chat_input("Ask about care gaps, facilities, indicators…")
if prompt:
    _ask_and_record(prompt)
    st.rerun()

# ---- Reset / open external link ----------------------------------------
if st.session_state[HIST_KEY]:
    cols = st.columns([1, 1, 6])
    with cols[0]:
        if st.button("Clear conversation", use_container_width=True):
            st.session_state[HIST_KEY] = []
            st.session_state[CONV_KEY] = None
            st.rerun()
    with cols[1]:
        external = os.environ.get("GENIE_SPACE_URL", "").strip()
        if external:
            st.link_button("Open in Genie ↗", url=external, use_container_width=True)
