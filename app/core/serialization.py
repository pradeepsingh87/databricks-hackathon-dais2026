"""JSON-safe serialization helpers for API responses."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

JSON_FIELD_NAMES = {"payload", "payload_json", "filters", "filters_json", "citations"}


def json_safe(value: Any, *, field_name: str | None = None) -> Any:
    """Convert pandas/numpy/decimal values into JSON-safe Python values."""
    if value is None:
        return None
    if not isinstance(value, (dict, list, tuple)):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and pd.isna(value):
        return None
    if value is pd.NaT:
        return None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, np.datetime64):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.generic):
        return json_safe(value.item(), field_name=field_name)
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, str) and field_name in JSON_FIELD_NAMES:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    if isinstance(value, dict):
        return {k: json_safe(v, field_name=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v, field_name=field_name) for v in value]
    return value


def records_from_df(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to API records with nulls and scalar types normalized."""
    if df.empty:
        return []
    records = df.replace({pd.NaT: None}).to_dict(orient="records")
    return [
        {key: json_safe(value, field_name=key) for key, value in record.items()}
        for record in records
    ]
