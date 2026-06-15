# Genie Space — Care Gap Navigator

## Purpose
Allow non-technical users to ask natural-language questions about the
trust-weighted care gap data without writing SQL.

## Tables exposed
- `gold.h3_care_score` — one row per (capability, h3_resolution, h3_cell)
- `gold.v_care_gap_by_state` — state-level rollup
- `silver.facility_claims` — per-facility claims with citations

## Sample questions
- "Show me the highest-risk maternity gaps in Bihar"
- "Which districts have ICU coverage but with low evidence confidence?"
- "List facilities claiming trauma services with only suspicious evidence"

## Sensitive vocabulary / glossary
- **score** — 0 (no care) to 1 (well covered)
- **confidence** — 0 (data-poor) to 1 (well-evidenced)
- **data_deficient** — TRUE means we cannot trust the score either way
