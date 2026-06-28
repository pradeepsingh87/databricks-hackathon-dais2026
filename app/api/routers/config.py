"""Configuration endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from app.api.schemas import Brand, Domain, Indicator
from app.services import brand, domains, gold

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/brand", response_model=Brand)
def get_brand() -> Brand:
    return Brand(**asdict(brand.load_brand()))


@router.get("/domains", response_model=list[Domain])
def get_domains() -> list[Domain]:
    return [
        Domain(
            id=domain.id,
            name=domain.name,
            icon=domain.icon,
            blurb=domain.blurb,
            capabilities=list(domain.capabilities),
            indicators=[Indicator(**asdict(indicator)) for indicator in domain.indicators],
        )
        for domain in domains.load_domains()
    ]


@router.get("/capabilities", response_model=list[str])
def get_capabilities() -> list[str]:
    return gold.list_capabilities()


@router.get("/states", response_model=list[str])
def get_states() -> list[str]:
    return gold.list_states()


@router.get("/indicators", response_model=list[Indicator])
def get_indicators() -> list[Indicator]:
    return [Indicator(**asdict(indicator)) for indicator in domains.all_indicators()]
