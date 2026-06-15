"""Load the domain registry (config/domains.yml).

A 'domain' bundles a set of capabilities + a set of NFHS-5 indicators that
matter for that planning lens. Used by the Executive Command Center home
page (one card per domain) and the Care Gap Navigator filter pane.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path

import yaml

_PATH = Path(__file__).resolve().parents[2] / "config" / "domains.yml"


@dataclass(frozen=True)
class Indicator:
    column: str
    label: str
    good_when: str  # "high" or "low" — how to color the headline number


@dataclass(frozen=True)
class Domain:
    id: str
    name: str
    icon: str
    blurb: str
    capabilities: tuple[str, ...]
    indicators: tuple[Indicator, ...]


@functools.lru_cache(maxsize=1)
def load_domains() -> list[Domain]:
    if not _PATH.exists():
        return []
    with _PATH.open() as f:
        cfg = yaml.safe_load(f) or {}
    out: list[Domain] = []
    for d in cfg.get("domains", []) or []:
        inds = tuple(
            Indicator(
                column=i["column"],
                label=i["label"],
                good_when=i.get("good_when", "high"),
            )
            for i in (d.get("indicators") or [])
        )
        out.append(
            Domain(
                id=d["id"],
                name=d["name"],
                icon=d.get("icon", "•"),
                blurb=d.get("blurb", ""),
                capabilities=tuple(d.get("capabilities") or []),
                indicators=inds,
            )
        )
    return out


def get_domain(domain_id: str) -> Domain | None:
    for d in load_domains():
        if d.id == domain_id:
            return d
    return None


def all_indicators() -> list[Indicator]:
    """Flat list (deduped by column) of every NFHS-5 indicator referenced."""
    seen: dict[str, Indicator] = {}
    for d in load_domains():
        for i in d.indicators:
            seen.setdefault(i.column, i)
    return list(seen.values())
