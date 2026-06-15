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
    """Push brand variables + global polish CSS into the page head."""
    import streamlit as st

    b = load_brand()
    css = (
        f"<style>{b.as_css_vars()}"
        # Tighten Streamlit's default header padding so the brand strip sits
        # closer to the top — matches the dashboard look.
        "section.main > div.block-container{padding-top:1.2rem;}"
        # Sidebar: subtle left border tinted with the brand primary.
        "section[data-testid='stSidebar']{"
        "border-right:1px solid rgba(13,111,122,0.15);"
        "background:linear-gradient(180deg,#fbfdfd 0%,#f4f9fa 100%);}"
        # Compact metric labels, dashboard-style.
        "[data-testid='stMetricLabel']{font-size:12px;letter-spacing:0.02em;"
        "text-transform:uppercase;color:var(--brand-muted);}"
        "[data-testid='stMetricValue']{color:var(--brand-text);font-weight:600;}"
        # Primary button: brand color with crisp focus ring.
        "button[kind='primary']{background:var(--brand-primary)!important;"
        "border-color:var(--brand-primary)!important;}"
        "</style>"
    )
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
