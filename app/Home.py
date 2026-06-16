"""Home — Care Gap Navigator landing page.

Single-purpose narrative landing. The deeper tools live in the sidebar:
Care Gap Navigator (map), Genie (NL Q&A), Action Center (drill-down),
Performance (trajectory), Scenarios (saved plans).
"""

import sys
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

import streamlit as st  # noqa: E402

from services import brand  # noqa: E402

st.set_page_config(
    page_title="Home",
    page_icon="🏥",
    layout="wide",
)

brand.inject_css()
b = brand.load_brand()

# ---- Hero ---------------------------------------------------------------
st.markdown(
    f"""
    <div style="
        max-width: 720px;
        margin: 96px auto 0 auto;
        text-align: center;
    ">
      <div style="
          font-size: 12px;
          font-weight: 600;
          letter-spacing: 0.16em;
          text-transform: uppercase;
          color: var(--brand-primary);
          margin-bottom: 20px;
      ">Trust-weighted healthcare planning</div>

      <div style="
          font-size: 44px;
          line-height: 1.12;
          font-weight: 700;
          color: var(--brand-text);
          letter-spacing: -0.01em;
          margin-bottom: 24px;
      ">{b.name}</div>

      <div style="
          font-size: 19px;
          line-height: 1.6;
          color: var(--brand-text);
          opacity: 0.82;
          font-weight: 400;
      ">
        We weigh every claim against the evidence behind it,
        layer it on the people who actually live there,
        and surface the gaps that matter — so the next clinic,
        the next ambulance, the next trained nurse
        lands where it will save the most lives.
      </div>

      <div style="
          margin-top: 56px;
          font-size: 13px;
          color: var(--brand-muted);
          letter-spacing: 0.04em;
      ">
        Open <span style="color:var(--brand-primary);font-weight:600;">Care Gap Navigator</span>
        in the sidebar to begin.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
