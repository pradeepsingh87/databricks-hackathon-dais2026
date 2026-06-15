"""pydeck point map of individual facilities.

Aesthetic target: matches the Databricks SQL dashboard map look (Carto Positron
basemap, white marker borders, saturated translucent fills). Sister to
care_map.py — that one summarises *cells*, this one shows the facilities
behind a cell.

  color  ← evidence_strength    (strong=green, partial=amber, suspicious=red,
                                 unknown=grey)
  radius ← capacity (or number_doctors fallback, sqrt-scaled so the largest
                     hospital isn't 100× the size of the smallest)
"""

from __future__ import annotations

import math

import pandas as pd
import pydeck as pdk
import streamlit as st


_EVIDENCE_COLOR = {
    "strong":     ( 26, 152,  80, 220),   # green
    "partial":    (252, 141,  89, 220),   # amber
    "suspicious": (215,  48,  39, 220),   # red
    "none":       (160, 160, 160, 200),   # grey
}


def _row_color(strength) -> list[int]:
    if pd.isna(strength):
        return list(_EVIDENCE_COLOR["none"])
    return list(_EVIDENCE_COLOR.get(str(strength).lower(), _EVIDENCE_COLOR["none"]))


def _row_radius(row) -> float:
    """Radius in meters. Square-root scale so the largest hospital isn't 100×
    the size of the smallest on screen."""
    cap = row.get("capacity")
    docs = row.get("number_doctors")
    if pd.notna(cap) and cap > 0:
        base = float(cap)
    elif pd.notna(docs) and docs > 0:
        base = float(docs) * 5     # rough conversion: 1 doctor ≈ 5 beds
    else:
        base = 20                  # floor so unsized facilities are still visible
    return 200 + 80 * math.sqrt(min(base, 2000))


def _initial_view(df: pd.DataFrame) -> pdk.ViewState:
    """Centre on the data; fallback to India centroid if the DF is empty."""
    if df.empty:
        return pdk.ViewState(latitude=22.5, longitude=79.0, zoom=4)
    lat = df["latitude"].astype(float).mean()
    lng = df["longitude"].astype(float).mean()
    spread = df["latitude"].astype(float).max() - df["latitude"].astype(float).min()
    if spread < 0.5:
        zoom = 9
    elif spread < 2.5:
        zoom = 7
    elif spread < 6:
        zoom = 5
    else:
        zoom = 4
    return pdk.ViewState(latitude=float(lat), longitude=float(lng), zoom=zoom)


def render(df: pd.DataFrame, height: int = 420, key: str = "facility-map") -> None:
    if df.empty:
        st.info("No facility locations to plot for this selection.", icon="📍")
        return

    plot = df.copy()
    plot["fill_color"] = plot["evidence_strength"].apply(_row_color)
    plot["radius"] = plot.apply(_row_radius, axis=1)
    plot["capacity_disp"] = plot["capacity"].fillna(0).astype(int)
    plot["doctors_disp"] = plot["number_doctors"].fillna(0).astype(int)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=plot,
        get_position="[longitude, latitude]",
        get_fill_color="fill_color",
        get_radius="radius",
        radius_min_pixels=4,
        radius_max_pixels=42,
        pickable=True,
        stroked=True,
        get_line_color=[255, 255, 255, 220],   # white halo, dashboard-style
        line_width_min_pixels=1,
    )

    tooltip = {
        "html": (
            "<div style='font-family:Inter,system-ui,sans-serif;font-size:12px;"
            "min-width:200px;'>"
            "<div style='font-weight:600;color:#fff;margin-bottom:4px;'>{name}</div>"
            "<div style='color:#cbd5e1;margin-bottom:6px;'>{city}, {state}</div>"
            "<div>Evidence · <b>{evidence_strength}</b></div>"
            "<div>Capacity · <b>{capacity_disp}</b>  ·  "
            "Doctors · <b>{doctors_disp}</b></div>"
            "</div>"
        ),
        "style": {
            "backgroundColor": "rgba(15, 23, 42, 0.92)",
            "color": "white",
            "borderRadius": "6px",
            "padding": "8px 10px",
            "boxShadow": "0 4px 18px rgba(0,0,0,0.18)",
        },
    }

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=_initial_view(plot),
        map_provider="carto",
        map_style="light",
        tooltip=tooltip,
    )
    st.pydeck_chart(deck, use_container_width=True, height=height, key=key)


def render_legend() -> None:
    """Inline color legend for the evidence-strength encoding."""
    items = [
        ("Strong",     "#1a9850"),
        ("Partial",    "#fc8d59"),
        ("Suspicious", "#d73027"),
        ("Unknown",    "#a0a0a0"),
    ]
    chips = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:6px;'
        f'margin-right:14px;font-size:12px;color:#444;">'
        f'<span style="width:10px;height:10px;background:{c};'
        f'border-radius:50%;display:inline-block;"></span>{label}</span>'
        for label, c in items
    )
    st.markdown(
        f'<div style="margin-top:-6px;margin-bottom:6px;">'
        f'<span style="font-size:12px;color:#888;">Evidence:</span> {chips}'
        f'<span style="font-size:12px;color:#888;margin-left:14px;">'
        f'Marker size ∝ √capacity</span></div>',
        unsafe_allow_html=True,
    )
