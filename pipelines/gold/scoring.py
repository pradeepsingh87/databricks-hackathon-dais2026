"""Pure helpers for trust-weighted score aggregation."""

from __future__ import annotations

from pipelines.common.capability_claims import WEIGHTS

DATA_DEFICIENT_THRESHOLD = 0.45


def score_from_weights(total_weight: float, n_facilities: int) -> float:
    if n_facilities <= 0:
        return 0.0
    return round(min(total_weight / n_facilities, 1.0), 4)


def confidence_from_components(
    n_facilities: int,
    avg_claim_weight: float,
    source_url_coverage: float,
) -> float:
    facility_factor = min(max(n_facilities, 0) / 5.0, 1.0)
    confidence = (
        0.4 * facility_factor
        + 0.4 * max(avg_claim_weight, 0.0)
        + 0.2 * max(source_url_coverage, 0.0)
    )
    return round(min(confidence, 1.0), 4)


def is_data_deficient(n_facilities: int, confidence: float) -> bool:
    return n_facilities == 0 or confidence < DATA_DEFICIENT_THRESHOLD


def evidence_state(score: float, confidence: float, n_facilities: int) -> str:
    if is_data_deficient(n_facilities, confidence):
        return "data_deficient"
    if score < 0.35:
        return "care_gap"
    return "covered"


__all__ = [
    "DATA_DEFICIENT_THRESHOLD",
    "WEIGHTS",
    "confidence_from_components",
    "evidence_state",
    "is_data_deficient",
    "score_from_weights",
]
