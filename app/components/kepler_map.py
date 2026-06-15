"""Deprecated. The Map page now uses pydeck via `app.components.care_map`.

The previous Kepler.gl-based component couldn't bind alpha to the confidence
column, so the headline visual ("proven absent vs data-deficient") didn't
work. Anything still importing `render_h3_map` from this module is forwarded
to the new pydeck implementation.
"""

from __future__ import annotations

import warnings

from .care_map import render as _render


def render_h3_map(df, key: str = "care-gap-map") -> None:  # noqa: ANN001
    warnings.warn(
        "app.components.kepler_map.render_h3_map is deprecated; "
        "use app.components.care_map.render instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    _render(df, key=key)
