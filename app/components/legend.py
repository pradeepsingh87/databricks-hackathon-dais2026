"""Inline legend for the H3 care-gap map.

Three columns mirror the three encodings:
  1. Score gradient — red→green (hue carries the care score)
  2. Confidence ramp — green at increasing alphas (transparency = uncertainty)
  3. Data-deficient swatch — neutral grey, the "we don't know" state
"""

from __future__ import annotations

import streamlit as st

# Match care_map._SCORE_PALETTE — six diverging stops.
_SCORE_HEX = ["#d73027", "#fc8d59", "#fee08b", "#d9ef8b", "#91cf60", "#1a9850"]
_SCORE_LABELS = ["0", "0.2", "0.4", "0.6", "0.8", "1"]


def _color_strip(colors: list[str], height: str = "10px") -> str:
    cells = "".join(
        f'<div style="flex:1;background:{c};height:{height};"></div>' for c in colors
    )
    return (
        '<div style="display:flex;border-radius:3px;overflow:hidden;'
        'border:1px solid #e2e8f0;">'
        f"{cells}</div>"
    )


def render() -> None:
    cols = st.columns([2, 2, 1])
    with cols[0]:
        st.caption("**Score** · red = gap → green = well-served")
        st.markdown(_color_strip(_SCORE_HEX), unsafe_allow_html=True)
        st.markdown(
            '<div style="display:flex;justify-content:space-between;'
            'font-size:11px;color:#64748b;margin-top:2px;">'
            + "".join(f"<span>{lbl}</span>" for lbl in _SCORE_LABELS)
            + "</div>",
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.caption("**Confidence** · transparent = data-poor → solid = strong evidence")
        # Same hue (#1a9850), increasing alpha — mirrors the alpha ramp in care_map.
        ramp = [
            "rgba(26,152,80,0.20)",
            "rgba(26,152,80,0.45)",
            "rgba(26,152,80,0.72)",
            "rgba(26,152,80,0.95)",
        ]
        st.markdown(_color_strip(ramp), unsafe_allow_html=True)
        st.markdown(
            '<div style="display:flex;justify-content:space-between;'
            'font-size:11px;color:#64748b;margin-top:2px;">'
            "<span>0</span><span>1</span></div>",
            unsafe_allow_html=True,
        )
    with cols[2]:
        st.caption("**Data-deficient**")
        st.markdown(
            '<div style="border:2px solid #fff;outline:1px solid #cbd5e1;'
            "background:rgba(170,174,180,0.55);height:24px;width:24px;"
            'border-radius:3px;"></div>'
            '<div style="font-size:11px;color:#64748b;margin-top:4px;">'
            "rendered grey — score is unreliable</div>",
            unsafe_allow_html=True,
        )
