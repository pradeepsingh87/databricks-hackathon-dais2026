"""Kepler.gl H3 map embedded in Streamlit.

Two visual encodings tell the trust story:
  - color  ← score (red=gap, green=well-served)
  - alpha  ← confidence (transparent=data-deficient, opaque=high evidence)
This is the "proven absent vs data-deficient" distinction the problem
statement calls out.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

try:
    from keplergl import KeplerGl
    from streamlit_keplergl import keplergl_static
    _AVAILABLE = True
except Exception:  # noqa: BLE001 — package may be missing in dev envs
    _AVAILABLE = False


_MAP_HEIGHT = 600

_KEPLER_CONFIG = {
    "version": "v1",
    "config": {
        "mapState": {"latitude": 22.5, "longitude": 79.0, "zoom": 4},
        "mapStyle": {"styleType": "light"},
        "visState": {
            "layers": [
                {
                    "id": "h3-care-score",
                    "type": "hexagonId",
                    "config": {
                        "dataId": "care",
                        "label": "Care score",
                        "columns": {"hex_id": "h3_cell"},
                        "isVisible": True,
                        "visConfig": {
                            "opacity": 0.85,
                            "colorRange": {
                                "name": "RdYlGn 6",
                                "type": "diverging",
                                "category": "ColorBrewer",
                                "colors": [
                                    "#d73027", "#fc8d59", "#fee08b",
                                    "#d9ef8b", "#91cf60", "#1a9850",
                                ],
                            },
                            "coverage": 1,
                        },
                    },
                    "visualChannels": {
                        "colorField": {"name": "score", "type": "real"},
                        "colorScale": "quantile",
                        "sizeField": None,
                        "sizeScale": "linear",
                    },
                }
            ],
            "interactionConfig": {
                "tooltip": {
                    "fieldsToShow": {
                        "care": [
                            {"name": "h3_cell"},
                            {"name": "score"},
                            {"name": "confidence"},
                            {"name": "n_facilities"},
                            {"name": "evidence_state"},
                        ]
                    },
                    "enabled": True,
                }
            },
        },
    },
}


def render_h3_map(df: pd.DataFrame, key: str = "care-gap-map") -> None:
    """Render the Kepler H3 map. Shows empty-state if df is empty or kepler missing."""
    if df.empty:
        st.info(
            "No care-score data for this selection. "
            "Run the Gold ETL job to populate `gold.h3_care_score`.",
            icon="🗺️",
        )
        return
    if not _AVAILABLE:
        st.warning(
            "Kepler.gl dependencies not installed. Falling back to a table view.",
            icon="⚠️",
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
        return

    # Kepler can't render NULLs — clamp to 0 / 0 for display so the cell still draws
    # in 'data_deficient' color but stays visible.
    plot = df.copy()
    for c in ("score", "confidence", "n_facilities"):
        if c in plot.columns:
            plot[c] = pd.to_numeric(plot[c], errors="coerce").fillna(0)

    m = KeplerGl(height=_MAP_HEIGHT, config=_KEPLER_CONFIG)
    m.add_data(data=plot, name="care")
    keplergl_static(m, height=_MAP_HEIGHT, key=key)
