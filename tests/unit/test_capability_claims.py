"""Unit tests for deterministic claim extraction."""

import json

from pipelines.common.capability_claims import build_claim_rows


def _base_record():
    return {
        "facility_id": "fac-1",
        "name": "Demo Hospital",
        "state": "Bihar",
        "district": "Patna",
        "city": "Patna",
        "h3_6": "866123",
        "h3_7": "877123",
        "h3_8": "888123",
        "description": "",
        "capability_raw": [],
        "procedure_raw": [],
        "equipment_raw": [],
        "specialties_raw": [],
        "source_urls_raw": ["https://example.com/facility"],
    }


def test_structured_claim_produces_strong_row():
    record = _base_record()
    record["capability_raw"] = ["ICU", "Emergency"]

    rows = build_claim_rows(record)

    icu = next(row for row in rows if row["capability"] == "icu")
    assert icu["evidence_strength"] == "strong"
    assert icu["claim_weight"] == 1.0
    assert icu["state"] == "Bihar"
    assert icu["h3_7"] == "877123"


def test_description_only_claim_is_suspicious():
    record = _base_record()
    record["description"] = "A small clinic with emergency support during evenings."

    rows = build_claim_rows(record)

    emergency = next(row for row in rows if row["capability"] == "emergency")
    assert emergency["evidence_strength"] == "suspicious"
    citations = json.loads(emergency["citations"])
    assert citations[0]["source_field"] == "description"


def test_mixed_evidence_upgrades_claim_strength():
    record = _base_record()
    record["description"] = "Offers oncology consultations and chemotherapy follow-up."
    record["procedure_raw"] = ["Chemotherapy"]

    rows = build_claim_rows(record)

    oncology = next(row for row in rows if row["capability"] == "oncology")
    assert oncology["evidence_strength"] == "strong"
    assert len(json.loads(oncology["citations"])) >= 2


def test_no_matching_evidence_produces_no_claims():
    rows = build_claim_rows(_base_record())
    assert rows == []
