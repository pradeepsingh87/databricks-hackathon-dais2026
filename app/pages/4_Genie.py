import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import os  # noqa: E402

import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

from app.components.filters import render_sidebar  # noqa: E402

st.set_page_config(page_title="Genie", page_icon="🧞", layout="wide")
filters = render_sidebar()

st.title("Ask Genie")
st.caption("Natural-language Q&A over the Gold layer.")

genie_url = os.environ.get("GENIE_SPACE_URL", "").strip()

st.markdown(
    f"""
    Sample questions you can ask in this space:

    - *"Show me the highest-risk **{filters.capability}** gaps in {filters.state or 'India'}"*
    - *"Which districts have **{filters.capability}** coverage but with low evidence confidence?"*
    - *"List facilities claiming **{filters.capability}** services with only suspicious evidence."*
    """
)

if not genie_url:
    st.warning(
        "No Genie space configured yet. Set the **GENIE_SPACE_URL** environment "
        "variable on the Databricks App resource (or in `.env` for local dev) to "
        "the URL of your Genie space. See `sql/genie/instructions.md` for the "
        "space prompt and table grants.",
        icon="🧞",
    )
    with st.expander("Genie setup checklist"):
        st.markdown(
            """
            1. In the Databricks workspace, open **Genie** → **New space**.
            2. Grant the space `SELECT` on:
               - `dais_hackathon_2026.gold.h3_care_score`
               - `dais_hackathon_2026.gold.care_score_by_state`
               - `dais_hackathon_2026.gold.care_score_by_district`
               - `dais_hackathon_2026.silver.silver_facility_capability_claims`
            3. Paste the contents of `sql/genie/instructions.md` into the
               space's general instructions.
            4. Copy the space URL into `GENIE_SPACE_URL`.
            """
        )
    st.stop()

components.iframe(genie_url, height=720, scrolling=True)
