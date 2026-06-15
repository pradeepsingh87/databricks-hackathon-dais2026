"""Unit tests for trust scoring helpers."""

from pipelines.gold.scoring import (
    confidence_from_components,
    evidence_state,
    is_data_deficient,
    score_from_weights,
)


def test_score_from_weights_caps_at_one():
    assert score_from_weights(total_weight=6.0, n_facilities=4) == 1.0


def test_confidence_uses_facilities_weight_and_sources():
    assert confidence_from_components(5, 1.0, 1.0) == 1.0
    assert confidence_from_components(1, 0.1, 0.0) == 0.12


def test_data_deficient_threshold_and_evidence_state():
    assert is_data_deficient(0, 0.9) is True
    assert is_data_deficient(2, 0.2) is True
    assert evidence_state(0.2, 0.9, 4) == "care_gap"
    assert evidence_state(0.8, 0.8, 4) == "covered"
