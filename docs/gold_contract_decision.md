# Decision Memo · Canonical Gold Contract

**Status:** Decided · 2026-06-16
**Decision:** **`h3_care_score` family is canonical.** `medical_desert_*` becomes a *derived* view family on top of it, not a competing root.

## What's in play

| Family | Tables | Built by | Read by | Cardinality |
|---|---|---|---|---|
| **A · score** | `gold.h3_care_score`, `care_score_by_state`, `care_score_by_district` | `pipelines/gold/trust_weighted_score.py` | every app page (services + 4/5 of pages) | (capability, h3 res, cell) ↔ rollups |
| **B · desert** | `gold.medical_desert_h3`, `medical_desert_districts` | `pipelines/gold/medical_desert.py` | docs only — no app reads | (capability, h3 cell), (capability, district) |

## Comparison

| Dimension | Family A — `*_care_score` | Family B — `medical_desert_*` |
|---|---|---|
| **UI compatibility** | ✅ Already wired across `app/services/gold.py`, `app/components/care_map.py`, `app/pages/{1,3,4,5}*.py`, `app/main.py` | ❌ Zero app reads. Adopting B = full re-wire of services + pages + tooltips. |
| **Citation support** | Citations live on `silver_facility_capability_claims`; pages join from there. Schema doesn't carry citations on the gold rows. | Carries `top_citations` ARRAY<STRUCT> directly on each row. *Slightly stronger.* |
| **Uncertainty semantics** | `score` (0..1) + `confidence` (0..1) + `evidence_state` ∈ `{data_deficient, care_gap, covered}` + `data_deficient` boolean. **Already drives the alpha-from-confidence map encoding** in [care_map.py](../app/components/care_map.py). | `gap_score` (NULL when demand unknown) + `confidence_label` (strong/partial/suspicious/none) + `desert_flag`. Cleaner naming, but the alpha encoding logic in the app reads `confidence`, not `confidence_label`. |
| **Demand model** | No NFHS-5 demand integration; scoring is supply-confidence only. | Joins NFHS-5 indicator per capability → multiplicative `gap = (1−supply) × demand`. *Genuinely better economics.* |
| **Demo readiness risk** | ✅ Live in workspace. Deployed app reads it. ETL job runs it. UC certified, mobile comments tightened, Genie space lists it. | 🟡 Notebook exists; **table not yet materialized** in the workspace (verified earlier in `setup_uc.sh` skip messages). Needs a successful gold ETL run before any app could read it. |
| **Operational maturity** | 5 tables/views, all certified, all column-commented (last task), all H3-tagged, all in Genie, all in `uc_metadata.sql` replay. | 2 tables, partially commented in `uc_metadata.sql` but those ALTERs SKIP today because the tables don't exist. |

## Decision

**Adopt Family A as canonical.** Re-frame Family B as **optional supplements**:

- `medical_desert_districts` becomes "the demand-aware variant of `care_score_by_district`" — the Performance page can opt in once it's materialized, but that's not blocking.
- `medical_desert_h3` is held back from the app entirely until we have a story for the citation extraction in the Care Gap Navigator drill-down (today citations are sourced from silver, which is fine).

### Rationale

1. **Demo risk is the dominant tiebreaker.** Family B isn't materialized; switching the canonical app to it = zero working app on demo day. Family A is fully alive and certified.
2. **Family A's semantics are sufficient** for the brief: `data_deficient` already does the proven-absent-vs-data-poor distinction the problem statement calls out, and `confidence` already drives the alpha channel on the map. Family B's "gap_score" is a richer story but not a *contractually different* signal.
3. **Citation strength of Family B is over-weighted in the discussion.** The drill-down already pulls citations directly from `silver_facility_capability_claims`; carrying them on the gold row is convenience, not capability.
4. **NFHS-5 demand can still be told as a story** without making it the core scorer — we already added the `silver_facilities_geo` table that joins NFHS-5 by district, and the Genie space exposes it. Demand-aware framing on the Performance page can layer on top of A.

## Impact table

| Change | Files | Effort |
|---|---|---|
| **Doc/header drift removal** — every reference to `medical_desert_*` as the headline gold contract gets reframed as supplemental | [docs/medical_desert.md](medical_desert.md) (rename + reframe), [docs/logical_architecture.md](logical_architecture.md), [docs/more.md](more.md), [README.md](../README.md) | Low |
| **Service ergonomics** — explicit metric vocabulary (e.g. `score` everywhere, never `gap_score`) | [app/services/gold.py](../app/services/gold.py) (docstring header), [app/components/legend.py](../app/components/legend.py) | Low |
| **Page tooltips** — confidence wording should match the canonical schema | [app/pages/1_Care_Gap_Navigator.py](../app/pages/1_Care_Gap_Navigator.py), [app/pages/3_Action_Center.py](../app/pages/3_Action_Center.py), [app/pages/4_Performance.py](../app/pages/4_Performance.py) | Low |
| **Genie alignment** — sample questions, glossary, and table list should not blend the two contracts | [sql/genie/instructions.md](../sql/genie/instructions.md), [scripts/setup_genie.sh](../scripts/setup_genie.sh) | Low |
| **Bundle DAG** — keep `gold_medical_desert` task (it doesn't break A) but mark it as "supplemental" so partial DAG runs don't fail the canonical path | [config/resources/jobs.yml](../config/resources/jobs.yml) | Trivial |
| **uc_metadata.sql** — the desert-table ALTERs are fine to keep (they SKIP gracefully when the table is absent); reorder so canonical lines run first | [sql/tags/uc_metadata.sql](../sql/tags/uc_metadata.sql) | Trivial |
| **Test coverage** — add contract test that asserts `gold.h3_care_score` columns the app reads | [tests/unit/](../tests/unit/) (new file) | Low |

## Files NOT changed by this decision

- [pipelines/gold/medical_desert.py](../pipelines/gold/medical_desert.py) — kept as-is. The desert scorer is real work; no reason to delete.
- [pipelines/gold/trust_weighted_score.py](../pipelines/gold/trust_weighted_score.py) — already canonical; needs no edits for the decision (a separate gap fix may add demand-awareness later).
- All bronze/silver tables and the `silver_facilities_geo` spatial fact table.

## Rollback

Single-file rollback if Family B turns out to be the better demo fit:

1. Revert `app/services/gold.py` to read `gold.medical_desert_h3` / `medical_desert_districts` via three new `fetch_*` helpers.
2. Switch `app/pages/4_Performance.py` rollup query and Care Gap Navigator KPI strip to the new helpers.
3. Update `sql/genie/instructions.md` table list.

The desert tables would need to be materialized first (currently only the notebook exists). A clean reverse path runs in <30 minutes once `gold_medical_desert` succeeds in the workspace.

## What I'm NOT doing in this decision

- Not deleting `medical_desert.md` or the desert pipeline.
- Not changing the UI's metric vocabulary in this prompt — that lands in **Prompt 2**.
- Not touching docs in this prompt — that's **Prompt 3**.

The next prompt operationalises this decision.
