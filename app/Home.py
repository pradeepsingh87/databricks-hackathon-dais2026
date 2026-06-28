"""Home — Care Gap Navigator landing page.

Single-line slogan, fade-and-rise on load. Deeper tools live in the sidebar:
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

# inject_css() defines the --brand-* custom properties the slogan reads from
# and keeps the rest of the app's chrome (sidebar, buttons, focus rings) on
# brand. We still need it even though this page renders almost nothing.
brand.inject_css()
brand.load_brand()  # warms the lru_cache so first navigate-away is fast

# ---- Hero: single slogan, fade-and-rise on load ------------------------
st.markdown(
    """
    <style>
      .slogan-stage {
        min-height: calc(100vh - 220px);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 24px;
      }
      .slogan {
        max-width: 1100px;
        text-align: center;
        font-size: clamp(40px, 6vw, 76px);
        line-height: 1.08;
        font-weight: 700;
        letter-spacing: -0.015em;
        color: var(--brand-text);
        opacity: 1;
        transform: none;
      }
      .slogan .accent { color: var(--brand-primary); }

      @media (prefers-reduced-motion: no-preference) {
        @keyframes slogan-rise {
          from { opacity: 0; transform: translateY(24px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .slogan {
          animation: slogan-rise 1100ms cubic-bezier(0.16, 1, 0.3, 1) 120ms both;
        }
      }
    </style>

    <div class="slogan-stage">
      <div class="slogan">
        Closing India's Medical Deserts<br/>with <span class="accent">Data</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
