"""pydeck-based H3 care-gap map.

Aesthetic target: matches the Databricks SQL dashboard map look —
  - Carto Positron-style light basemap (clean greys, no labels stealing focus)
  - white inter-cell strokes (the dashboard signature for choropleth-like layers)
  - saturated-but-translucent fills (so basemap context shows through)
  - compact dark tooltip with hairline white text

Encodings (the trust story this app exists to tell):
  color  ← score        red→amber→green diverging palette
  alpha  ← confidence   transparent=data-deficient, opaque=well-evidenced
  border ← evidence_state == 'data_deficient' rendered grey instead of red,
           plus a brighter white outline so weak cells visibly differ from
           a "proven absent" cell at the same color band.
"""

from __future__ import annotations

import pandas as pd
import pydeck as pdk
import streamlit as st


# RdYlGn diverging palette (6 stops). Score ∈ [0, 1] → index ∈ [0, 5].
_SCORE_PALETTE = [
    (215,  48,  39),   # 0.00–0.16  hard gap
    (252, 141,  89),   # 0.16–0.33
    (254, 224, 139),   # 0.33–0.50
    (217, 239, 139),   # 0.50–0.66
    (145, 207,  96),   # 0.66–0.83
    ( 26, 152,  80),   # 0.83–1.00  well-served
]
_DEFICIENT_RGB = (170, 174, 180)   # neutral grey — Databricks dashboards use
                                   # grey for "no/weak data" rather than a
                                   # red→green color, so we don't accidentally
                                   # imply a score that we don't trust.

# Carto Positron tile URL — matches the Databricks dashboard basemap look.
_BASEMAP_URL = (
    "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"
)
_INDIA_VIEW = pdk.ViewState(latitude=22.5, longitude=79.0, zoom=4, bearing=0, pitch=0)


def _color_for_row(score, evidence_state) -> tuple[int, int, int]:
    if str(evidence_state).lower() == "data_deficient":
        return _DEFICIENT_RGB
    if pd.isna(score):
        return _DEFICIENT_RGB
    idx = max(0, min(len(_SCORE_PALETTE) - 1, int(float(score) * len(_SCORE_PALETTE))))
    return _SCORE_PALETTE[idx]


def _alpha_for_confidence(confidence) -> int:
    """Confidence (0..1) → alpha (50..210).

    Floor at 50 so even data-deficient cells remain visible — they should be
    *faded*, not invisible. Ceiling at 210 so well-evidenced cells stay
    translucent enough that the basemap context bleeds through (the
    dashboard-map signature).
    """
    if pd.isna(confidence):
        return 50
    c = max(0.0, min(1.0, float(confidence)))
    return int(50 + c * 160)


def _prep_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Add the per-row pydeck attributes (rgba, line color, etc.).

    Done in pandas (not in deck.gl JS expressions) because it's clearer to
    debug and lets the legend reuse the exact same color logic.
    """
    plot = df.copy()
    for c in ("score", "confidence", "n_facilities"):
        if c in plot.columns:
            plot[c] = pd.to_numeric(plot[c], errors="coerce")

    rgb = [
        _color_for_row(s, e)
        for s, e in zip(plot.get("score", []), plot.get("evidence_state", []), strict=False)
    ]
    alpha = plot["confidence"].apply(_alpha_for_confidence)
    plot["fill_color"] = [
        [r, g, b, a] for (r, g, b), a in zip(rgb, alpha, strict=False)
    ]
    # White inter-cell strokes are the Databricks dashboard signature.
    plot["line_color"] = [[255, 255, 255, 220]] * len(plot)
    # Tooltip-friendly labels.
    plot["score_pct"] = (plot["score"].fillna(0) * 100).round(1)
    plot["confidence_pct"] = (plot["confidence"].fillna(0) * 100).round(1)
    return plot


def render(df: pd.DataFrame, height: int = 560, key: str = "care-map") -> None:
    """Draw the H3 care-score map. Empty state is the caller's responsibility."""
    if df.empty:
        st.info(
            "No care-score data for this selection. "
            "Run the Gold ETL job (`bundle run care_gap_etl`) to populate "
            "`gold.h3_care_score`.",
            icon="🗺️",
        )
        return

    plot = _prep_dataframe(df)

    layer = pdk.Layer(
        "H3HexagonLayer",
        data=plot,
        get_hexagon="h3_cell",
        get_fill_color="fill_color",
        get_line_color="line_color",
        line_width_min_pixels=1.2,
        extruded=False,
        pickable=True,
        stroked=True,
        coverage=0.93,
        # `id` lets pydeck/deck.gl track this layer across reruns — same role
        # the old `key=` on st.pydeck_chart was meant to play. The deployed
        # Streamlit runtime rejects `key=` on pydeck_chart, so we route the
        # caller's identifier here instead.
        id=key,
    )

    tooltip = {
        "html": (
            "<div style='font-family:Inter,system-ui,sans-serif;font-size:12px;"
            "min-width:160px;'>"
            "<div style='font-weight:600;color:#fff;margin-bottom:4px;'>{h3_cell}</div>"
            "<div>Score · <b>{score_pct}%</b></div>"
            "<div>Confidence · <b>{confidence_pct}%</b></div>"
            "<div>Facilities · <b>{n_facilities}</b></div>"
            "<div style='margin-top:4px;color:#cbd5e1;text-transform:uppercase;"
            "letter-spacing:0.04em;font-size:10px;'>{evidence_state}</div>"
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
        initial_view_state=_INDIA_VIEW,
        # No Mapbox token needed — Carto Positron tiles via map_provider="carto".
        map_provider="carto",
        map_style="light",
        tooltip=tooltip,
        # Older Streamlit builds (≤1.40 in the deployed Apps runtime) don't
        # accept `height=` or `key=` on st.pydeck_chart. Height goes on the
        # Deck; `key` is forwarded to the Layer's `id` parameter above.
        height=height,
    )
    st.pydeck_chart(deck, use_container_width=True)
