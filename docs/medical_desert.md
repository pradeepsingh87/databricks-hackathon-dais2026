# Gold: Medical Desert scorer

A `gold.medical_desert_h3` (one row per `(capability, h3_resolution, h3_cell)`)
plus a `gold.medical_desert_districts` rollup. Identifies regions where
verified care supply is meaningfully below the NFHS-5-implied demand —
"medical deserts" — and carries citations for every flagged region so
the planner can verify the claim against the underlying facility text.

## Inputs

| Source | Used for |
| --- | --- |
| `silver.silver_facility_capability_claims` | Per-(facility, capability) `evidence_strength`, `claim_weight`, structured `citations` JSON |
| `silver.silver_facilities_geo` | District + H3 cells + NFHS-5 indicators |
| `config/capability_demand.yml` | Mapping from each capability to its NFHS-5 demand indicator and polarity |

## Verified supply

The silver claim extractor already classifies every (facility, capability)
into `strong / partial / suspicious / none` and assigns `claim_weight`
(`1.0 / 0.5 / 0.1`). Gold trusts these labels — no second keyword pass —
and applies one transformation:

```
verified_weight = claim_weight  if evidence_strength != 'suspicious'
                = 0             otherwise
```

Suspicious claims are **logged** (`n_suspicious` per cell) but **excluded
from supply**. Counting them as supply would let a region full of
unverifiable claims look well-served; this is exactly the failure mode the
hackathon brief calls out.

## Demand

Each capability points to **one** NFHS-5 column with an explicit polarity:

| capability | indicator | direction |
| --- | --- | --- |
| maternity  | `institutional_birth_5y_pct` | `low_means_high_demand` |
| nicu       | `child_u5_who_are_stunted_height_for_age_18_pct` | `high_means_high_demand` |
| emergency  | `hh_member_covered_health_insurance_pct` | `low_means_high_demand` |
| oncology   | `women_age_30_49_years_ever_undergone_a_cervical_screen_pct` | `low_means_high_demand` |
| trauma, icu | `w15_plus_with_high_bp_sys_gte_140_mmhg_and_or_dia_gte_90_mm_pct` | `high_means_high_demand` |

Polarity rules:

```
low_means_high_demand   →  demand = (100 - x) / 100
high_means_high_demand  →  demand =        x  / 100
```

The result is clamped to `[0, 1]`. NULL NFHS-5 values produce NULL demand,
which then propagates to NULL `gap_score` — a transparent "we don't know"
rather than a false zero.

The polarity choices and rationale are in [`config/capability_demand.yml`](../config/capability_demand.yml).
Adding a new capability = one YAML entry.

## Gap score

```
supply_score   = verified_supply / MAX(verified_supply) OVER state
gap_score      = max(0, 1 - supply_score) * demand_score
```

Two deliberate choices:

- **State-relative supply, not absolute.** A rural cell with one good
  facility and a million people is still a medical desert *relative to its
  state*, even if Indian healthcare is broadly thin. Normalising per state
  also keeps the score comparable across regions on the map.
- **Multiplicative gap × demand.** A region with high supply but high demand
  isn't a desert (the supply matches the need). A region with low supply
  but no demand isn't either (no one needs the missing service). Only the
  product flags real deserts.

## Confidence label

Propagated from the dominant facility-level label in the cell:

```
confidence_label =
  'strong'      if n_strong   >= n_partial
  'partial'     if n_partial > 0
  'suspicious'  if n_suspicious > 0
  'none'        otherwise
```

This is what the App's badges (✅ / 🟡 / 🚩 / ⚪) on the Action Center display.

## Desert flag

```
desert_flag = gap_score > 0.6 AND confidence_label != 'suspicious'
```

The `'suspicious'` exclusion is the key honesty move: a region whose
"care gap" is built on suspicious-only claims is **data-deficient**, not a
medical desert. The Care Gap Navigator visually distinguishes those (grey
fill, white outline) so planners don't conflate the two.

## Citations carried per row

Each gold row carries `top_citations` — up to 3 (or 5 for districts)
distinct facility excerpts:

```
top_citations: ARRAY<STRUCT<
  facility_id:        STRING,
  name:               STRING,
  city:               STRING,
  evidence_strength:  STRING,
  citations:          STRING   -- JSON array of {text, source_field, source_url}
>>
```

The Action Center renders these inline so every score the planner sees has
direct, click-through-able underlying text — meeting the hackathon
"cite the underlying facility text" obligation at the gold-row grain, not
just at the silver-claim grain.

## Snapshot dimensions

Every gold row stamps `score_run_id` (UUID) and `as_of_ts`. Future
saved scenarios in Lakebase reference `score_run_id` so a saved view from
last week doesn't silently change meaning when Gold is re-run.

## Where the desert table fits

```
silver_facility_capability_claims    silver_facilities_geo
       (claim trust)                       (location + NFHS-5 demand)
                \                       /
                 \                     /
                  ▼                   ▼
                 gold.medical_desert_h3
                 gold.medical_desert_districts
                          │
                          ▼
                 App: Care Gap Navigator (map)
                       Action Center   (citations)
                       Performance     (district risk)
                       Genie space     (NL queries on the same Gold tables)
```

## Running

```bash
# Whole DAG (bronze → silver → gold, including the new desert task)
databricks bundle run care_gap_etl

# Just the desert scorer
databricks bundle run care_gap_etl --target dev \
  --var=app_prefix=$USER --only gold_medical_desert
```

After the run, the smoke output prints the **top-10 medical deserts** at
district grain — a one-line demo summary.

## Verification queries

```sql
-- 1. Top deserts overall
SELECT capability, state, district,
       n_facilities, verified_supply, demand_score, gap_score,
       confidence_label
FROM dais_hackathon_2026.gold.medical_desert_districts
WHERE desert_flag
ORDER BY gap_score DESC
LIMIT 20;

-- 2. Citation spot-check — pick one row, inspect its top_citations
SELECT capability, state, district, top_citations
FROM dais_hackathon_2026.gold.medical_desert_districts
WHERE state = 'Bihar' AND capability = 'maternity'
ORDER BY gap_score DESC
LIMIT 1;

-- 3. NULL-demand sanity (rows where NFHS-5 didn't match)
SELECT COUNT(*) AS rows_missing_demand
FROM dais_hackathon_2026.gold.medical_desert_h3
WHERE demand_score IS NULL;
```

## Future work (gap list, deferred)

- `score_run_id` is generated but not yet used for time-series. Once a few
  runs accumulate, the Performance page's "projected gap closure" can read
  real history instead of synthetic curves.
- Composite demand index (multiple NFHS-5 indicators per capability)
  would be more holistic but harder to defend per-component on demo day.
- Specialty-code cross-check (e.g. "criticalCare" specialty for ICU
  claims) is a cheap further trust signal — silver-side todo.
