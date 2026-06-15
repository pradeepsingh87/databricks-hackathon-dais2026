"""Load and validate the source registry (config/ingestion/sources.yml)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "ingestion" / "sources.yml"
)


@dataclass
class ColumnRule:
    source: str
    target: str
    cast: str = "string"
    transforms: list[str] = field(default_factory=list)


@dataclass
class Expectation:
    name: str
    severity: str = "warn"           # 'error' aborts the run, 'warn' is logged
    expr: str | None = None          # SQL boolean
    kind: str | None = None          # e.g. 'unique'
    columns: list[str] = field(default_factory=list)


@dataclass
class GeoConfig:
    lat_col: str = "latitude"
    lng_col: str = "longitude"
    india_bbox: dict[str, float] = field(default_factory=dict)
    on_outside_bbox: str = "flag_only"
    h3_resolutions: list[int] = field(default_factory=list)


@dataclass
class Source:
    name: str
    description: str
    source_catalog: str
    source_schema: str
    target_catalog: str
    bronze_schema: str
    silver_schema: str
    source_table: str
    bronze_table: str
    silver_table: str
    primary_key: str | None = None
    write_mode: str = "overwrite"
    add_audit_columns: bool = True
    parse_json_columns: list[str] = field(default_factory=list)
    columns: list[ColumnRule] = field(default_factory=list)
    standardize: list[dict[str, Any]] = field(default_factory=list)
    geo: GeoConfig | None = None
    expectations: list[Expectation] = field(default_factory=list)
    passthrough_all: bool = False

    @property
    def fq_source(self) -> str:
        return f"{self.source_catalog}.{self.source_schema}.{self.source_table}"

    @property
    def fq_bronze(self) -> str:
        return f"{self.target_catalog}.{self.bronze_schema}.{self.bronze_table}"

    @property
    def fq_silver(self) -> str:
        return f"{self.target_catalog}.{self.silver_schema}.{self.silver_table}"


def load_registry(path: Path | str | None = None) -> list[Source]:
    p = Path(path) if path else DEFAULT_REGISTRY_PATH
    with p.open() as f:
        cfg = yaml.safe_load(f)

    defaults = cfg.get("defaults", {}) or {}
    sources: list[Source] = []
    for s in cfg["sources"]:
        merged = {**defaults, **s}
        sources.append(
            Source(
                name=merged["name"],
                description=merged.get("description", ""),
                source_catalog=merged["source_catalog"],
                source_schema=merged["source_schema"],
                target_catalog=merged["target_catalog"],
                bronze_schema=merged["bronze_schema"],
                silver_schema=merged["silver_schema"],
                source_table=merged["source_table"],
                bronze_table=merged["bronze_table"],
                silver_table=merged["silver_table"],
                primary_key=merged.get("primary_key"),
                write_mode=merged.get("write_mode", "overwrite"),
                add_audit_columns=merged.get("add_audit_columns", True),
                parse_json_columns=merged.get("parse_json_columns", []) or [],
                columns=[ColumnRule(**c) for c in merged.get("columns", []) or []],
                standardize=merged.get("standardize", []) or [],
                geo=GeoConfig(**merged["geo"]) if merged.get("geo") else None,
                expectations=[Expectation(**e) for e in merged.get("expectations", []) or []],
                passthrough_all=merged.get("passthrough_all", False),
            )
        )
    return sources


def get_source(name: str, path: Path | str | None = None) -> Source:
    for s in load_registry(path):
        if s.name == name:
            return s
    raise KeyError(f"No source named '{name}' in registry")
