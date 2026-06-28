"""Pydantic response and request contracts for the FastAPI backend."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FilterState(BaseModel):
    capability: str | None = None
    state: str | None = None
    h3_resolution: int = 7
    confidence_min: float = 0.0
    indicator: str | None = None
    h3_cell: str | None = None


class Indicator(BaseModel):
    column: str
    label: str
    good_when: Literal["high", "low"] | str = "high"


class Domain(BaseModel):
    id: str
    name: str
    icon: str
    blurb: str
    capabilities: list[str]
    indicators: list[Indicator]


class Brand(BaseModel):
    name: str
    sponsor: str
    tagline: str
    logo_url: str
    primary: str
    secondary: str
    accent: str
    background: str
    text: str
    muted: str


class MapKpis(BaseModel):
    n_cells: int = 0
    n_facilities: int = 0
    avg_score: float | None = None
    avg_confidence: float | None = None
    n_data_deficient: int = 0
    n_care_gap: int = 0
    n_covered: int = 0


class H3ScoreCell(BaseModel):
    h3_cell: str
    score: float | None = None
    confidence: float | None = None
    n_facilities: int | None = None
    evidence_state: str | None = None


class StateRollup(BaseModel):
    state: str
    score: float | None = None
    confidence: float | None = None
    n_facilities: int | None = None
    n_data_deficient_cells: int | None = None


class DistrictRollup(StateRollup):
    district: str


class Facility(BaseModel):
    facility_id: str | None = None
    name: str | None = None
    state: str | None = None
    district: str | None = None
    city: str | None = None
    evidence_strength: str | None = None
    citations: Any = None


class FacilityLocation(Facility):
    latitude: float | None = None
    longitude: float | None = None
    capacity: float | None = None
    number_doctors: float | None = None
    claim_weight: float | None = None


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class Scenario(BaseModel):
    id: int | str | None = None
    user_name: str | None = None
    name: str | None = None
    payload: Any = None
    created_at: str | None = None


class BookmarkCreate(BaseModel):
    name: str = Field(min_length=1)
    filters: dict[str, Any] = Field(default_factory=dict)
    shared: bool = False


class Bookmark(BaseModel):
    id: int | str | None = None
    user_name: str | None = None
    name: str | None = None
    filters_json: Any = None
    shared: bool | None = None
    created_at: str | None = None


class OverrideCreate(BaseModel):
    facility_id: str
    capability: str
    note: str = Field(min_length=1)


class Override(BaseModel):
    id: int | str | None = None
    user_name: str | None = None
    facility_id: str | None = None
    capability: str | None = None
    note: str | None = None
    created_at: str | None = None


class GapCategorizationCreate(BaseModel):
    capability: str
    category: Literal["data", "service", "engagement"]
    state: str | None = None
    district: str | None = None
    h3_cell: str | None = None
    severity: Literal["low", "medium", "high"] | None = None
    note: str | None = None


class GapCategorization(BaseModel):
    id: int | str | None = None
    user_name: str | None = None
    capability: str | None = None
    state: str | None = None
    district: str | None = None
    h3_cell: str | None = None
    category: str | None = None
    severity: str | None = None
    note: str | None = None
    created_at: str | None = None


class GenieAskRequest(BaseModel):
    question: str = Field(min_length=1)
    conversation_id: str | None = None


class GenieAnswerResponse(BaseModel):
    text: str
    sql: str | None = None
    sql_description: str | None = None
    statement_id: str | None = None
    rows: list[dict] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    conversation_id: str
    message_id: str


class PerformanceRiskBand(BaseModel):
    band: str
    count: int


class ProjectedTrendPoint(BaseModel):
    state: str | None = None
    district: str | None = None
    month: int
    score: float | None = None
