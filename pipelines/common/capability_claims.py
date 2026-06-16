"""Deterministic capability claim extraction for the Track 2 demo."""

from __future__ import annotations

import json
import re
from typing import Any

from .config import CAPABILITIES

WEIGHTS = {"strong": 1.0, "partial": 0.5, "suspicious": 0.1}

CAPABILITY_PATTERNS = {
    "icu": [r"\bicu\b", r"intensive care", r"critical care", r"ventilator"],
    "maternity": [r"maternity", r"obstetric", r"labor room", r"labour room", r"delivery"],
    "emergency": [r"emergency", r"\ber\b", r"casualty", r"ambulance"],
    "oncology": [r"oncology", r"cancer", r"chemotherapy", r"radiation"],
    "trauma": [r"trauma", r"accident", r"fracture", r"orthopedic trauma"],
    "nicu": [r"\bnicu\b", r"neonatal intensive care", r"newborn intensive"],
}

OUTPUT_FIELDS = (
    "facility_id",
    "name",
    "state",
    "district",
    "city",
    "h3_6",
    "h3_7",
    "h3_8",
    "capability",
    "evidence_strength",
    "claim_weight",
    "has_source_url",
    "citations",
)


def _ensure_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if str(v).strip()]
            except Exception:  # noqa: BLE001
                pass
        return [stripped]
    return [str(value).strip()]


def _ensure_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(_ensure_list(value))
    return str(value).strip()


def _sentence_snippet(text: str, patterns: list[str]) -> str:
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    for sentence in sentences:
        lowered = sentence.lower()
        if any(re.search(pattern, lowered) for pattern in patterns):
            return sentence.strip()
    return text.strip()[:240]


def _match_items(values: list[str], capability: str) -> list[str]:
    patterns = CAPABILITY_PATTERNS[capability]
    matches = []
    for value in values:
        lowered = value.lower()
        if any(re.search(pattern, lowered) for pattern in patterns):
            matches.append(value)
    return matches


def _build_citations(
    record: dict[str, Any],
    capability: str,
) -> tuple[list[dict[str, str]], set[str]]:
    patterns = CAPABILITY_PATTERNS[capability]
    source_url = next(iter(_ensure_list(record.get("source_urls_raw"))), "")
    citations: list[dict[str, str]] = []
    matched_fields: set[str] = set()

    for field in ("capability_raw", "procedure_raw", "equipment_raw", "specialties_raw"):
        matches = _match_items(_ensure_list(record.get(field)), capability)
        for match in matches:
            citations.append(
                {
                    "text": match,
                    "source_field": field,
                    "source_url": source_url,
                }
            )
            matched_fields.add(field)

    description = _ensure_text(record.get("description"))
    if description:
        snippet = _sentence_snippet(description, patterns)
        lowered = snippet.lower()
        if any(re.search(pattern, lowered) for pattern in patterns):
            citations.append(
                {
                    "text": snippet,
                    "source_field": "description",
                    "source_url": source_url,
                }
            )
            matched_fields.add("description")

    deduped = []
    seen: set[tuple[str, str]] = set()
    for citation in citations:
        key = (citation["source_field"], citation["text"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(citation)
    return deduped, matched_fields


def _strength_from_matches(matched_fields: set[str]) -> str | None:
    if not matched_fields:
        return None
    structured = "capability_raw" in matched_fields
    non_description = matched_fields - {"description"}
    if (
        structured
        or len(non_description) >= 2
        or ("description" in matched_fields and non_description)
    ):
        return "strong"
    if non_description:
        return "partial"
    return "suspicious"


def build_claim_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Create one normalized claim row per detected capability."""
    rows: list[dict[str, Any]] = []
    for capability in CAPABILITIES:
        citations, matched_fields = _build_citations(record, capability)
        strength = _strength_from_matches(matched_fields)
        if strength is None:
            continue
        rows.append(
            {
                "facility_id": record.get("facility_id"),
                "name": record.get("name"),
                "state": record.get("state"),
                "district": record.get("district"),
                "city": record.get("city"),
                "h3_6": record.get("h3_6"),
                "h3_7": record.get("h3_7"),
                "h3_8": record.get("h3_8"),
                "capability": capability,
                "evidence_strength": strength,
                "claim_weight": WEIGHTS[strength],
                "has_source_url": any(c.get("source_url") for c in citations),
                "citations": json.dumps(citations),
            }
        )
    return rows
