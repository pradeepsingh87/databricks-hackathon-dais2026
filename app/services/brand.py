"""Resolve and expose sponsor/NGO branding for the app chrome.

Layered config:
  1. config/brand.yml  — declarative defaults checked into the repo
  2. env vars          — per-deployment overrides (BRAND_NAME etc.)

Pages call brand.render_header() once at the top, and read brand.colors() if
they want to harmonise their own widgets with the active palette.
"""

from __future__ import annotations

import functools
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

_BRAND_PATH = Path(__file__).resolve().parents[2] / "config" / "brand.yml"


@dataclass(frozen=True)
class Brand:
    name: str
    sponsor: str
    tagline: str
    logo_url: str
    primary: str
    secondary: str
    accent: str
    background: str
    text: str
    muted: str

    def as_css_vars(self) -> str:
        """CSS custom-properties block usable from any st.markdown(unsafe=True)."""
        return (
            ":root {"
            f"--brand-primary:{self.primary};"
            f"--brand-secondary:{self.secondary};"
            f"--brand-accent:{self.accent};"
            f"--brand-bg:{self.background};"
            f"--brand-text:{self.text};"
            f"--brand-muted:{self.muted};"
            "}"
        )


@functools.lru_cache(maxsize=1)
def load_brand() -> Brand:
    raw: dict = {}
    if _BRAND_PATH.exists():
        with _BRAND_PATH.open() as f:
            raw = yaml.safe_load(f) or {}

    def pick(key: str, env: str, default: str) -> str:
        return os.environ.get(env) or raw.get(key) or default

    return Brand(
        name=pick("name", "BRAND_NAME", "Care Gap Navigator"),
        sponsor=pick("sponsor", "BRAND_SPONSOR", ""),
        tagline=pick("tagline", "BRAND_TAGLINE", ""),
        logo_url=pick("logo_url", "BRAND_LOGO_URL", ""),
        primary=pick("primary", "BRAND_PRIMARY", "#0d6f7a"),
        secondary=pick("secondary", "BRAND_SECONDARY", "#2a9d8f"),
        accent=pick("accent", "BRAND_ACCENT", "#f4a261"),
        background=pick("background", "BRAND_BACKGROUND", "#fafbfc"),
        text=pick("text", "BRAND_TEXT", "#1d3557"),
        muted=pick("muted", "BRAND_MUTED", "#6c757d"),
    )


def colors() -> dict[str, str]:
    b = load_brand()
    return {
        "primary": b.primary, "secondary": b.secondary, "accent": b.accent,
        "background": b.background, "text": b.text, "muted": b.muted,
    }


def inject_css() -> None:
    """Push brand variables + global polish CSS into the page head.

    2026 polish pass — adds the corner-radius / shadow / elevated-card
    treatments the brief calls out, plus a tightened type ramp so the app
    reads as a clinical tool rather than a default Streamlit dashboard.
    """
    import streamlit as st

    b = load_brand()
    # The CSS is intentionally a single string to keep the runtime CSS
    # injection cheap (one st.markdown call). Grouped by intent below.
    css = f"""
    <style>
    {b.as_css_vars()}

    /* ── design tokens (2026) ────────────────────────────────────────── */
    :root {{
      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 14px;
      --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 1px rgba(15, 23, 42, 0.06);
      --shadow-md: 0 4px 12px rgba(15, 23, 42, 0.06), 0 2px 4px rgba(15, 23, 42, 0.04);
      --shadow-lg: 0 12px 32px rgba(15, 23, 42, 0.08), 0 4px 12px rgba(15, 23, 42, 0.05);
      --border-soft: rgba(15, 23, 42, 0.07);
    }}

    /* ── page chrome ─────────────────────────────────────────────────── */
    section.main > div.block-container {{
      padding-top: 1.2rem;
      padding-bottom: 2.4rem;
      max-width: 1320px;
    }}

    /* Sidebar: subtle gradient + brand-tinted right border */
    section[data-testid='stSidebar'] {{
      border-right: 1px solid var(--border-soft);
      background: linear-gradient(180deg, #fbfdfd 0%, #f4f9fa 100%);
    }}
    section[data-testid='stSidebar'] [data-testid='stHeading'] h2 {{
      font-size: 14px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--brand-muted);
      font-weight: 600;
    }}

    /* ── metric KPI strip ────────────────────────────────────────────── */
    [data-testid='stMetricLabel'] {{
      font-size: 12px;
      letter-spacing: 0.02em;
      text-transform: uppercase;
      color: var(--brand-muted);
    }}
    [data-testid='stMetricValue'] {{
      color: var(--brand-text);
      font-weight: 600;
    }}
    [data-testid='stMetric'] {{
      background: #fff;
      border: 1px solid var(--border-soft);
      border-radius: var(--radius-md);
      padding: 12px 16px;
      box-shadow: var(--shadow-sm);
      transition: box-shadow 120ms ease, transform 120ms ease;
    }}
    [data-testid='stMetric']:hover {{
      box-shadow: var(--shadow-md);
      transform: translateY(-1px);
    }}

    /* ── containers (st.container(border=True)) ──────────────────────── */
    div[data-testid='stVerticalBlockBorderWrapper'] {{
      border-radius: var(--radius-md) !important;
      border-color: var(--border-soft) !important;
      box-shadow: var(--shadow-sm);
      background: #ffffffcc;
      backdrop-filter: blur(2px);
    }}

    /* ── inputs ──────────────────────────────────────────────────────── */
    [data-testid='stTextInput'] input,
    [data-testid='stTextArea'] textarea,
    [data-baseweb='select'] > div {{
      border-radius: var(--radius-sm) !important;
      border-color: var(--border-soft) !important;
    }}
    [data-testid='stTextInput'] input:focus,
    [data-testid='stTextArea'] textarea:focus {{
      border-color: var(--brand-primary) !important;
      box-shadow: 0 0 0 3px rgba(13, 111, 122, 0.12) !important;
    }}

    /* ── buttons ─────────────────────────────────────────────────────── */
    button[kind='primary'] {{
      background: var(--brand-primary) !important;
      border-color: var(--brand-primary) !important;
      border-radius: var(--radius-sm) !important;
      box-shadow: var(--shadow-sm);
      transition: filter 120ms ease, box-shadow 120ms ease;
    }}
    button[kind='primary']:hover {{
      filter: brightness(1.08);
      box-shadow: var(--shadow-md);
    }}
    button[kind='secondary'] {{
      border-radius: var(--radius-sm) !important;
      border-color: var(--border-soft) !important;
    }}

    /* ── tables ──────────────────────────────────────────────────────── */
    [data-testid='stDataFrame'] {{
      border-radius: var(--radius-md);
      overflow: hidden;
      box-shadow: var(--shadow-sm);
      border: 1px solid var(--border-soft);
    }}

    /* ── chat (Genie page) ───────────────────────────────────────────── */
    [data-testid='stChatMessage'] {{
      border-radius: var(--radius-md);
      box-shadow: var(--shadow-sm);
      margin-bottom: 8px;
    }}

    /* ── pydeck map gets a soft outer shadow so it lifts off the page ── */
    [data-testid='stDeckGlJsonChart'] {{
      border-radius: var(--radius-lg);
      overflow: hidden;
      box-shadow: var(--shadow-lg);
      border: 1px solid var(--border-soft);
    }}

    /* ── divider tightening ──────────────────────────────────────────── */
    hr {{ margin: 1.4rem 0 !important; border-color: var(--border-soft); }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def render_header(subtitle: str | None = None) -> None:
    """Render the top brand strip used on every page."""
    import streamlit as st

    b = load_brand()
    inject_css()

    logo_html = (
        f'<img src="{b.logo_url}" alt="logo" style="height:34px;'
        'border-radius:6px;margin-right:10px;">'
        if b.logo_url else
        # Inline mark — simple monogram from the first letter of the sponsor/name.
        '<div style="height:34px;width:34px;border-radius:8px;'
        'background:var(--brand-primary);color:#fff;'
        'display:flex;align-items:center;justify-content:center;'
        'font-weight:700;margin-right:10px;font-family:Inter,system-ui;">'
        f'{(b.sponsor or b.name)[:1].upper()}</div>'
    )
    sponsor_chip = (
        f'<span style="display:inline-block;background:rgba(13,111,122,0.10);'
        'color:var(--brand-primary);padding:2px 8px;border-radius:999px;'
        f'font-size:11px;margin-left:8px;">{b.sponsor}</span>'
        if b.sponsor else ""
    )
    line2 = subtitle or b.tagline
    st.markdown(
        '<div style="display:flex;align-items:center;'
        'border-bottom:1px solid rgba(0,0,0,0.06);'
        'padding-bottom:10px;margin-bottom:18px;">'
        f"{logo_html}"
        '<div style="line-height:1.15;">'
        f'<div style="font-weight:600;color:var(--brand-text);font-size:18px;">'
        f'{b.name}{sponsor_chip}</div>'
        f'<div style="font-size:12px;color:var(--brand-muted);">{line2}</div>'
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
