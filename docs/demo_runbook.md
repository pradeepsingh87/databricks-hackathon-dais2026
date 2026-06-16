# 3-minute demo runbook

A linear, copy-pasteable script for the hackathon demo. Hits every required
hackathon capability — extract structure, show evidence, communicate
uncertainty, persist user actions — in roughly three minutes.

> **Pre-flight (before the timer starts):** open Databricks workspace login,
> Streamlit app URL, and Genie space URL in three browser tabs. Run
> `databricks --profile DEFAULT current-user me` to confirm auth.

---

## Step 0 · Pre-stage data (one-time, ~2 minutes)

Run **before** the demo. If tables already exist, this is a no-op.

```bash
# 1. Provision UC schemas + Lakebase tables (idempotent)
DATABRICKS_WAREHOUSE_ID=5954d90879db71e9 ./scripts/setup_uc.sh

# 2. Run the bronze → silver → gold ETL
databricks bundle deploy --target dev --var=app_prefix=$USER
databricks bundle run care_gap_etl --target dev --var=app_prefix=$USER

# 3. Apply UC metadata (tags, comments, certified property)
databricks --profile DEFAULT api post /api/2.0/sql/statements \
  --json "$(jq -Rn --arg s "$(cat sql/tags/uc_metadata.sql)" \
    --arg w 5954d90879db71e9 \
    '{warehouse_id: $w, statement: $s, wait_timeout: "60s"}')"

# 4. Provision Genie space (prints the GENIE_SPACE_ID for your .env)
DATABRICKS_WAREHOUSE_ID=5954d90879db71e9 ./scripts/setup_genie.sh
```

Expected workspace state after Step 0:

| Catalog | Tables | Notes |
| --- | --- | --- |
| `dais_hackathon_2026.bronze` | 4 tables + dq_log + state_alias_reference | All source tables landed |
| `dais_hackathon_2026.silver` | 5 tables (facilities, claims, geo, pincode, nfhs5) | All certified or domain-tagged |
| `dais_hackathon_2026.gold` | 3 base + 2 views + 2 supplemental | Canonical: h3_care_score + state/district rollups |
| `dais_hackathon_2026.lakebase` | 4 tables (scenarios, overrides, gap_categorizations, bookmarks) | Empty until the demo writes |

---

## Step 1 · Open the app · 0:00 → 0:20

Open the deployed Databricks App. The **Executive Command Center** lands
first.

**Talk track:**

> "Coordinators in India face a 'data fog' across 10,000 facility records.
> This app turns those messy claims into a Trust-Weighted Care Gap Map. The
> homepage gives a 'For You' surface and four domain cards — Maternal,
> Trauma, Child Health, Oncology."

Click the **"Open in Care Gap Navigator"** button on a domain card (Maternal
Health works well — high signal in Bihar / Uttar Pradesh).

---

## Step 2 · The map · 0:20 → 1:00

Navigator page renders. Three visual encodings carry the trust story:

1. **Color** = score (red → green) = supply quality.
2. **Alpha** = confidence = how much we trust that score.
3. **Grey + outline** = `data_deficient` = "we don't know".

**Talk track:**

> "The headline insight isn't where care is bad — it's where we *don't
> know*. Faded grey cells are data-deficient. A bright red cell at full
> opacity is a real care gap; a faded red one is a data gap. The map
> distinguishes them automatically."

Switch the sidebar **State** filter to **Bihar**. KPI strip updates: cells,
facilities, average score, average confidence, evidence-state mix. Point at
the "Data-deficient cells" metric.

> "There are *X* cells in Bihar where we cannot trust the score either way.
> That's the first planning question, not the last."

---

## Step 3 · Drill-down with citations · 1:00 → 1:40

Click a low-score cell in the **"Pick a cell to drill into"** picker (sort by
"Worst care first"). Click **"Open in Action Center →"**.

Action Center renders with: location map, four trust badges (✅/🟡/🚩/⚪),
and the **NACHC Root Cause Analysis** side-panel.

**Talk track:**

> "Every score on the map is backed by underlying facility text. This panel
> classifies the gap into one of three buckets — Data Gap, Service Delivery
> Gap, or Engagement Gap — using the NACHC framework that real NGO
> coordinators already work in."

Click **🚩 Suspicious** on one of the facility cards. Show the citation —
the actual quoted text from `silver_facility_capability_claims.citations`.

> "The hackathon brief required citing underlying text. We carry every claim
> back to the source field — description, capability list, equipment list —
> with the source URL where we have one."

---

## Step 4 · Persist + share · 1:40 → 2:10

Stay on Action Center. Tag the gap as "Service Delivery Gap" with severity
"high" + a short note. Confirm the save toast.

> "Notes, overrides, and root-cause tags persist to Lakebase Delta. Anyone
> on the team — across capabilities, across days — sees the same record."

Switch to **Scenarios** page. Save the current filter set as a bookmark with
"Share with teammates" checked. Show the saved bookmark in the right column.

> "Bookmarks let one coordinator hand off a view to another without screen-
> sharing or copying URLs. The 'shared' flag opens it across the workspace."

---

## Step 5 · Genie · 2:10 → 2:45

Switch to **Genie** page. Click one of the pre-populated User Skills:

> "Generate a regional risk report for maternity care in Bihar."

Wait for the inline answer (~10s). Genie shows: text answer + generated SQL
+ result table or bar chart + 3 follow-up question chips.

> "The same Gold tables that drive the map answer natural-language questions
> through Genie. Every answer carries the SQL it generated for transparency,
> and the underlying tables are certified in Unity Catalog so Genie ranks
> them above the raw layers."

Click one of the follow-up chips ("What is the distribution of ICU
facilities across districts in Bihar?") to demonstrate context retention.

---

## Step 6 · Wrap · 2:45 → 3:00

Land back on the homepage's **Top care gaps** table.

> "Bottom line: 10,000 messy claims become a single ranked list of where to
> deploy ICU, maternity, NICU, oncology, trauma, and emergency capacity —
> with the *honesty* to say 'we don't know yet' when the evidence isn't
> there. Lakebase persists the work; Genie answers the next question."

---

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Map empty, "No care-score data for this selection" | Gold ETL hasn't run | `databricks bundle run care_gap_etl --only gold_trust_score` |
| State filter shows "(All India)" only | Silver pipeline didn't materialise the alias-resolved state column | `bundle run care_gap_etl --only silver_normalize_all` |
| Genie panel says "Genie is not configured" | Missing `GENIE_SPACE_ID` env var | `./scripts/setup_genie.sh` and copy printed ID into `.env` / app resource |
| "Save scenario" or root-cause tag fails silently | Lakebase tables missing | Re-run `./scripts/setup_uc.sh` |
| Performance page shows projection, not real history | Fewer than 2 ETL runs have appended to `gold.score_history` | Trigger one more `bundle run care_gap_etl` |
| Mobile cards truncate at table comments | Comment > 120 chars | Tighten via `sql/tags/uc_metadata.sql` (re-run only the affected COMMENT line) |

---

## What to *not* do during the demo

- **Don't** click into the supplemental `medical_desert_*` story unless
  asked. The canonical scoring is `h3_care_score` + rollups; medical_desert
  is a richer demand-aware story but not currently the app's primary
  contract (see [gold_contract_decision.md](gold_contract_decision.md)).
- **Don't** open the Genie space in its native UI — the embedded inline
  chat on the Genie page is what shows "Genie inside the app".
- **Don't** show the Performance page first. Most state filters today have
  a thin distribution; the Care Gap Navigator's map is the headline
  visual.
