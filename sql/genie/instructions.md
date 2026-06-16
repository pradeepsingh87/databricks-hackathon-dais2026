# Genie Space — Care Gap Navigator

## Purpose

Allow non-technical NGO coordinators and healthcare planners to ask natural-
language questions about the trust-weighted care gap data without writing
SQL. Genie translates the question into SQL using the Unity Catalog semantic
layer and renders a chart or table — every answer can be traced back to the
underlying Gold tables.

## Canonical metric vocabulary

This section is **authoritative**. The app, docs, and Genie agree on these
exact column names and semantics — do not introduce synonyms in answers.

- `score` (0..1) — supply quality. 0 = no verified care; 1 = well-served.
- `confidence` (0..1) — evidence trust. 0 = data-poor; 1 = well-evidenced.
  **Drives the alpha channel of the map** in the app, so a high score with
  low confidence renders translucent — meaningfully different from "covered".
- `evidence_state` — categorical: `data_deficient` | `care_gap` | `covered`.
- `data_deficient` (BOOL) — TRUE when confidence is too low to trust the
  score. **Treat data-deficient cells as "we don't know", not "no care".**
- `evidence_strength` (per facility/capability) — `strong` | `partial` |
  `suspicious` | `none`. Lives on `silver_facility_capability_claims`.
- `capability` — one of `icu` | `nicu` | `maternity` | `oncology` |
  `emergency` | `trauma`.

We deliberately do NOT use `gap_score` / `desert_flag` / `confidence_label`
in canonical answers. Those columns belong to the supplemental
`medical_desert_*` tables and have their own semantics there; mixing them
into a canonical answer creates terminology drift.

## Canonical tables (catalog: `dais_hackathon_2026`)

| Table | Grain | What's in it |
| --- | --- | --- |
| **`gold.h3_care_score`** | (capability, h3_resolution, h3_cell) | Trust-weighted score + confidence + evidence_state per cell. The map's source of truth. |
| **`gold.care_score_by_state`** | (capability, state) | State rollup. Use for top-line questions. |
| **`gold.care_score_by_district`** | (capability, state, district) | District rollup. Use for risk stratification. |
| `silver.silver_facility_capability_claims` | (facility_id, capability) | Per-facility evidence_strength + citations JSON. Use when the user asks for the *underlying text* behind a score. |
| `silver.silver_facilities` | (facility_id) | Coords, capacity, doctors, description. |
| `silver.silver_nfhs5_district` | (state, district) | NFHS-5 health indicators (120 cols) — disease-burden / demand signal. |
| `silver.silver_facilities_geo` | (facility_id) | Spatial fact: H3 9/10/11 + NFHS-5 demand attached. |

## Optional / supplemental tables (use only if explicitly asked)

| Table | Grain | When to use |
| --- | --- | --- |
| `gold.medical_desert_h3` | (capability, h3 cell) | Only if the user explicitly asks for "medical deserts" or `gap_score`. |
| `gold.medical_desert_districts` | (capability, state, district) | Same — explicit-ask only. |
| `gold.score_history` | (capability, state, district, snapshot_ts) | Use for time-series / "how has X changed over time" questions. |

## Sample questions (User Skills)

### Regional risk reports
- "Generate a regional risk report for maternity care in Bihar."
- "Generate a regional risk report for ICU care in Kerala — flag districts where confidence is low."

### Care gaps & rankings
- "Where are the highest-risk maternity gaps in Bihar?"
- "Show ICU care scores ranked by state."
- "List the top 10 districts for trauma where score is low AND confidence is high."

### Trust & uncertainty
- "List facilities claiming trauma services with only suspicious evidence."
- "How many cells are data-deficient for NICU in Kerala?"
- "Compare confidence levels between Punjab and Haryana for emergency care."

### Disease-burden context (NFHS-5 join)
- "Where is institutional birth coverage low AND maternity care thin?"
- "Show districts with high stunting where pediatric care is also weak."

### Time series
- "How has the maternity care score for Bihar changed across the last 3 ETL runs?"

## Style notes for Genie's answers

- **Always include `confidence` alongside `score`** when displaying scores —
  the trust story is the whole point of this app.
- **For "where are the gaps" questions**, sort `score ASC NULLS LAST` and
  filter out `evidence_state = 'data_deficient'` unless the user explicitly
  asked about data quality — otherwise data-poor regions will pollute the
  ranking.
- **Prefer the rollup tables** (`care_score_by_state` / `_by_district`) over
  `h3_care_score` for state/district-grain questions — already aggregated,
  much faster.
- **Cite citations** when the user asks "why" or "show evidence" — pull
  `silver_facility_capability_claims.citations` (JSON array of
  `{text, source_field, source_url}`).
- **Never blend supply-only (`score`) with demand-aware (`gap_score`) metrics
  in the same answer**. If the user asks for both, render two clearly-labelled
  result blocks.
