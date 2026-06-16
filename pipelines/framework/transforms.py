"""Named PySpark column transforms referenced by the source registry.

Each function takes a Column and returns a Column. The Silver runner
resolves transform names (strings in YAML) to these functions via TRANSFORMS.
"""

from __future__ import annotations

from pyspark.sql import functions as F
from pyspark.sql.column import Column


def trim(col: Column) -> Column:
    return F.trim(col)


def collapse_ws(col: Column) -> Column:
    return F.regexp_replace(col, r"\s+", " ")


def lower(col: Column) -> Column:
    return F.lower(col)


def title_case(col: Column) -> Column:
    return F.initcap(F.lower(col))


def digits_only(col: Column) -> Column:
    """Keep digits only — survives commas, units, and 'null' strings."""
    cleaned = F.regexp_replace(col.cast("string"), r"[^0-9]", "")
    return F.when(cleaned == "", None).otherwise(cleaned)


def left_6(col: Column) -> Column:
    return F.substring(col.cast("string"), 1, 6)


def year_in_range_1800_2026(col: Column) -> Column:
    """Coerce to int, NULL out impossible years."""
    normalized = F.trim(col.cast("string"))
    valid_year = normalized.rlike(r"^\d{4}$")
    y = F.when(valid_year, normalized.cast("int")).otherwise(None)
    return F.when((y >= 1800) & (y <= 2026), y).otherwise(None)


def null_if_string_null(col: Column) -> Column:
    """Treat literal 'null'/'NULL'/'' as SQL NULL — common dirty CSV pattern."""
    return F.when(F.lower(F.trim(col)).isin("null", "none", ""), None).otherwise(col)


TRANSFORMS = {
    "trim": trim,
    "collapse_ws": collapse_ws,
    "lower": lower,
    "title_case": title_case,
    "digits_only": digits_only,
    "left_6": left_6,
    "year_in_range_1800_2026": year_in_range_1800_2026,
    "null_if_string_null": null_if_string_null,
}


def apply_transforms(col: Column, names: list[str]) -> Column:
    out = col
    for n in names:
        if n not in TRANSFORMS:
            raise KeyError(f"Unknown transform '{n}'")
        out = TRANSFORMS[n](out)
    return out
