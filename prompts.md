# COIE Prompts for Feature Implementation
Use these prompts in order.  COIE format used below:**C = Context****O = Objective****I = Instructions****E = Expected Output**
---
## Prompt 1 — Gold Contract Decision (Blocker)
### C (Context)You are working in the databricks-hackathon-dais2026 repo. There are two competing Gold models:gold.h3_care_score, gold.care_score_by_state, gold.care_score_by_districtgold.medical_desert_h3, gold.medical_desert_districts
The app currently reads the first set, while docs describe both.
### O (Objective)Produce a concrete decision proposal choosing one canonical Gold contract and identifying exact deprecations/changes needed.
### I (Instructions)1. Review features.md, docs/audit_report.md, docs/followup_fix_backlog.md.2. Compare both models on:   - UI compatibility   - citation support   - uncertainty semantics   - demo readiness risk3. Recommend one canonical model for this codebase now.4. List exact files to change for this decision.5. Do not edit code in this step; planning only.
### E (Expected Output)Short decision memo with:  - chosen model  - rationale  - impact table  - file-level change list  - rollback option
---
## Prompt 2 — Implement Gold Contract Alignment in App
### C (Context)Canonical Gold contract has been chosen in Prompt 1.
### O (Objective)Update the app and services to fully align with the chosen Gold model so UI labels, metrics, and queries are consistent.
### I (Instructions)1. Update read-side service queries in app/services/gold.py.2. Update affected pages (app/pages/1_Care_Gap_Navigator.py, app/pages/3_Action_Center.py, and any related component/tooltips).3. Ensure naming consistency (score vs gap_score, confidence labels/states).4. Keep fallback behavior graceful if tables are missing.5. Run lint/tests relevant to touched files and fix issues.6. Summarize all functional behavior changes.
### E (Expected Output)Working code changes with:  - updated SQL queries  - updated UI metric labels/tooltips  - no broken imports/lints  - concise test/run notes
---
## Prompt 3 — Documentation Consistency Pass
### C (Context)Docs currently drift from implementation (Kepler vs pydeck, Lakebase wording, Mosaic wording, broken path, duplicate docs, draft text).
### O (Objective)Make documentation accurate, concise, and consistent with actual implementation decisions.
### I (Instructions)1. Update:   - docs/logical_architecture.md   - docs/more.md   - README.md   - any other doc impacted by canonical model decision2. Fix broken absolute image path to repo-relative path.3. Remove unfinished draft-style prose.4. Deduplicate:   - docs/Why_Medical_Desert_Planner.md   - docs/Medical_Desert_Planner.md   (keep one, remove one)5. Ensure docs mention current actual map/persistence/spatial stack.
### E (Expected Output)Clean docs with:  - accurate architecture narrative  - no duplicate track-strategy file  - fixed links/paths  - no AI-draft artifacts
---
## Prompt 4 — Portability and Config Hardening
### C (Context)Catalog has been moved to psb_catalog; deployment should be workspace-portable and reviewer-friendly.
### O (Objective)Harden environment configuration so local run and deployment do not depend on hidden hard-coded values.
### I (Instructions)1. Verify and align catalog defaults across:   - databricks.yml   - config/ingestion/sources.yml   - pipelines/common/config.py   - app/app.yaml   - config/.env.example   - scripts/setup_uc.sh   - scripts/setup_genie.sh2. Minimize brittle hard-coded envs where reasonable.3. Add/update a short "Required env vars" section in README.md.4. Validate local app startup command still works.
### E (Expected Output)Consistent config defaults and clear README setup guidance.
---
## Prompt 5 — Shortlist Path Decision and Execution
### C (Context)lakebase.shortlists exists, but no service methods/UI wiring currently use it.
### O (Objective)Either implement shortlist feature end-to-end or remove it cleanly.
### I (Instructions)1. Choose one path:   - Implement shortlist add/list UX + service methods, or   - Remove shortlist schema + references.2. If implementing:   - Add methods in app/services/lakebase.py.   - Add UI actions in Action Center or Scenarios.   - Ensure persisted records are visible in UI.3. If removing:   - Remove DDL and mentions from docs/comments.4. Add tests for whichever path you choose.
### E (Expected Output)No dead shortlist path remaining in code/docs.
---
## Prompt 6 — Dependency Cleanup
### C (Context)streamlit-keplergl / keplergl are likely unused and currently problematic in install.
### O (Objective)Make dependency installation reliable and minimal.
### I (Instructions)1. Verify whether streamlit-keplergl and keplergl are used.2. Remove unused deps from requirements.txt (and related files if needed).3. Re-run dependency install check.4. Ensure app launch still works.
### E (Expected Output)Clean dependency files with successful install path and no runtime regressions.
---
## Prompt 7 — Performance Page Real History
### C (Context)Performance page uses synthetic projection today.
### O (Objective)Replace synthetic trend with real history from scored runs.
### I (Instructions)1. Design and implement snapshot persistence for trend history.2. Update Gold pipeline writes so history accumulates (not just overwrite current tables).3. Update app/pages/4_Performance.py to query real historical series.4. Keep a guarded fallback if history is insufficient.5. Add tests/validation query examples.
### E (Expected Output)Real historical trend rendering in Performance page, with deterministic fallback behavior.
---
## Prompt 8 — Genie Alignment with Canonical Metrics
### C (Context)Genie should reflect same canonical metric semantics as app and docs.
### O (Objective)Align Genie instructions and setup with the canonical Gold model and current tables/views.
### I (Instructions)1. Update sql/genie/instructions.md glossary, sample questions, and style notes to canonical model.2. Validate scripts/setup_genie.sh registers correct tables/views.3. Ensure prompt examples return confidence-aware outputs.
### E (Expected Output)Genie docs/setup that match canonical app semantics and avoid conflicting metric language.
---
## Prompt 9 — Integration Contract Tests
### C (Context)Current tests are mostly unit-level and do not protect app query contracts.
### O (Objective)Add integration-contract coverage for key schema and query assumptions.
### I (Instructions)1. Add tests that validate expected columns and types required by app query functions.2. Cover:   - map query contract   - rollup query contract   - drill-down/citation contract3. Keep tests fast and deterministic with fixtures/mocks.4. Ensure CI runs new tests.
### E (Expected Output)Additional tests preventing silent breakage in app-table contracts.
---
## Prompt 10 — Demo Readiness Script and Checklist
### C (Context)Hackathon demo must show requirement coverage in ~3 minutes.
### O (Objective)Create a deterministic demo playbook proving end-to-end workflow.
### I (Instructions)1. Create a concise demo checklist doc with exact steps:   - run pipeline   - open app   - show map + uncertainty   - drill down citations   - save scenario/override   - ask Genie query2. Add troubleshooting notes for common failures.3. Keep it short and operator-friendly.
### E (Expected Output)A practical demo runbook that any teammate can execute without tribal knowledge.
 
Prompt 11
## Goal
Improve readability, spacing, hierarchy, and first-time usability for non-technical planners.

## Constraints
Do NOT change backend table contracts or scoring logic.
Do NOT remove existing features/pages.
Keep the same workflows and actions.
Prioritize low-risk UI refactors only.

## Scope
Primary files:
app/Home.py
app/pages/1_Care_Gap_Navigator.py
app/pages/3_Action_Center.py
app/pages/4_Performance.py
app/pages/5_Scenarios.py
app/components/filters.py
app/components/legend.py
app/components/care_map.py
app/components/facility_map.py
app/services/brand.py (if needed for visual consistency)

## UX improvements to implement
1. Reduce density:
   - Add breathing space between major sections.
   - Move secondary content into expanders.
   - Keep primary actions above the fold.
2. Improve visual hierarchy:
   - Clear page title -> subtitle -> key action flow.
   - Standardize section headers and captions.
   - Make KPI strips compact and scannable.
3. Improve filter ergonomics:
   - Group filters into “Primary” and “Advanced”.
   - Keep the default view simple.
4. Improve table readability:
   - Show only essential columns by default.
   - Use concise labels and formatting.
5. Improve clarity for first-time users:
   - Add short “How to use this page” helper text at top of Navigator and Action Center.
   - Add explicit empty/error state copy that tells users the next step.
6. Improve consistency:
   - Use one consistent metric vocabulary across pages.
   - Standardize icon/badge styles and status wording.
7. Keep map legibility:
   - Ensure legend is compact and visible near the map.
   - Keep tooltips clean and short.

## Deliverables
Implement code changes directly.
Provide a concise summary of what changed per page.
List before/after UX outcomes.
Run lint checks for touched files and fix any introduced issues.