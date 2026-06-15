"""Kepler.gl map component, embedded via streamlit-keplergl."""

from __future__ import annotations


def render_h3_map(rows, key: str = "care-gap-map"):
    """Render H3 cells coloured by trust-weighted score, alpha by confidence.

    rows: iterable of (h3_cell, score, confidence, n_facilities)
    """
    # TODO: build pandas DataFrame, configure KeplerGl with H3 layer
    raise NotImplementedError
