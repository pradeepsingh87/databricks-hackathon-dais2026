"""Home — Care Gap Navigator landing page.

Single-purpose, narrative-only landing. The deeper tools live in the sidebar:
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
        max-width: 880px;
        margin: 48px auto 24px auto;
        padding: 32px 36px;
        border-radius: var(--radius-lg);
        background: linear-gradient(135deg,
            rgba(13,111,122,0.06) 0%,
            rgba(244,162,97,0.04) 100%);
        border: 1px solid rgba(13,111,122,0.10);
    ">
      <div style="
          font-size: 13px;
          font-weight: 600;
          letter-spacing: 0.10em;
          text-transform: uppercase;
          color: var(--brand-primary);
          margin-bottom: 12px;
      ">Trust-weighted healthcare planning</div>

      <div style="
          font-size: 40px;
          line-height: 1.15;
          font-weight: 700;
          color: var(--brand-text);
          margin-bottom: 18px;
      ">{b.name}</div>

      <div style="
          font-size: 18px;
          line-height: 1.55;
          color: var(--brand-text);
          margin-bottom: 14px;
      ">
        Every district has a story buried in its data —
        a maternity ward without a delivery suite,
        an ICU label on a hospital with no ventilator,
        a city marked &ldquo;covered&rdquo; that has never seen a neonatal incubator.
      </div>

      <div style="
          font-size: 18px;
          line-height: 1.55;
          color: var(--brand-text);
          margin-bottom: 22px;
      ">
        We weigh every claim against the evidence behind it,
        layer it on top of the people who actually live there,
        and surface the gaps that matter — so the next clinic,
        the next ambulance, the next trained nurse
        lands where it will save the most lives.
      </div>

      <div style="
          display: flex;
          flex-wrap: wrap;
          gap: 18px;
          font-size: 14px;
          color: var(--brand-muted);
          padding-top: 18px;
          border-top: 1px solid rgba(13,111,122,0.10);
      ">
        <div>🗺️&nbsp; <b style="color:var(--brand-text);">See</b> where care exists — and where it only claims to</div>
        <div>🔎&nbsp; <b style="color:var(--brand-text);">Question</b> the evidence behind every facility</div>
        <div>📋&nbsp; <b style="color:var(--brand-text);">Plan</b> the intervention that closes the gap</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- Quiet handoff to the sidebar --------------------------------------
st.markdown(
    """
    <div style="
        max-width: 880px;
        margin: 8px auto 0 auto;
        text-align: center;
        font-size: 13px;
        color: var(--brand-muted);
    ">
      Open <b>Care Gap Navigator</b> in the sidebar to begin.
    </div>
    """,
    unsafe_allow_html=True,
)
