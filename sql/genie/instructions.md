# Genie Space — Care Gap Navigator

## Purpose
Allow non-technical NGO coordinators and healthcare planners to ask
natural-language questions about the trust-weighted care gap data without
writing SQL. Genie translates the question into SQL using the Unity Catalog
semantic layer and renders a chart or table — every answer can be traced
back to the underlying Gold tables.

## Tables exposed (catalog: `dais_hackathon_2026`)

| Table | Grain | What's in it |
| --- | --- | --- |
| `gold.h3_care_score` | (capability, h3_resolution, h3_cell) | Trust-weighted score + confidence + evidence_state per cell. The map's source of truth. |
| `gold.care_score_by_state` | (capability, state) | State-level rollup |
| `gold.care_score_by_district` | (capability, state, district) | District-level rollup — used for risk stratification |
| `silver.silver_facility_capability_claims` | (facility_id, capability) | One row per facility / capability with `evidence_strength` + structured `citations` JSON |
| `silver.silver_nfhs5_district` | (state, district) | NFHS-5 health indicators (120 cols) — disease burden + demand signal |
| `silver.silver_facilities` | (facility_id) | Per-facility attributes — coords, capacity, doctors, description |

## Glossary

- **score** — 0 (no care) to 1 (well covered)
- **confidence** — 0 (data-poor) to 1 (well-evidenced)
- **evidence_state** — categorical: `data_deficient` | `care_gap` | `covered`
- **evidence_strength** (per facility/capability) — `strong` | `partial` | `suspicious` | `none`
- **data_deficient cell** — confidence below threshold; we cannot trust the score either way
- **capability** — one of: `icu`, `nicu`, `maternity`, `oncology`, `emergency`, `trauma`

## Sample questions

### Care gaps
- "Where are the highest-risk maternity gaps in Bihar?"
- "Show ICU care scores ranked by state."
- "Which districts have low ICU coverage AND low evidence confidence?"

### Trust & uncertainty
- "List facilities claiming trauma services with only suspicious evidence."
- "How many cells are data-deficient for NICU in Kerala?"
- "Compare confidence levels between Punjab and Haryana for emergency care."

### Disease burden context (NFHS-5 join)
- "Where is institutional birth coverage low AND maternity care thin?"
- "Show districts with high stunting where pediatric care is also weak."

## Style notes for Genie's answers

- Always include `confidence` alongside `score` when displaying scores —
  a high score with low confidence is meaningfully different from a high
  score with high confidence.
- For "where are the gaps" questions, sort `score ASC NULLS LAST` and
  filter out `evidence_state = 'data_deficient'` unless the user asked
  about data quality specifically.
- Prefer the rollup tables (`care_score_by_state` / `_by_district`) over
  `h3_care_score` for state/district-grain questions — they're already
  aggregated and faster.
