# Trust-Weighted Care Gap Navigator

Track 2 — **Medical Desert Planner** for the Databricks Apps & Agents Hackathon for Good (DAIS 2026).

A Databricks App that turns 10,000 messy Indian healthcare facility records into a **Trust-Weighted Care Gap Map**, helping NGO coordinators distinguish *real* care gaps from *data-poor* regions.

See [docs/problem_statement.md](docs/problem_statement.md) for the problem framing, [docs/logical_architecture.md](docs/logical_architecture.md) for the architecture, [docs/gold_contract_decision.md](docs/gold_contract_decision.md) for the canonical Gold model decision, and [docs/demo_runbook.md](docs/demo_runbook.md) for the 3-minute demo path.

## Repo layout

```
app/             Streamlit + pydeck Databricks App (5 pages, 7 services, 7 components)
pipelines/       Bronze / Silver / Gold ETL — metadata-driven, declarative
sql/             Genie + Gold views + Lakebase DDL + UC tag/comment replay
config/          Databricks Asset Bundle config + ingestion registry + brand
scripts/         setup_uc.sh · setup_genie.sh · run_pipeline.sh · deploy.sh
tests/           Unit + integration-contract tests
data/            Sample data + schema specs (raw data not committed)
docs/            Problem framing, architecture, ingestion + spatial + gold notes
```

## Quick start

```bash
# 1 · install deps
pip install -r requirements.txt

# 2 · configure
cp config/.env.example .env       # then fill in DATABRICKS_TOKEN

# 3 · run locally
streamlit run app/Home.py

# 4 · deploy to Databricks Apps
./deploy.sh                       # bundle deploy + smoke tests
```

## Required env vars

For local `streamlit run app/Home.py`:

| Var | Used by | Notes |
| --- | --- | --- |
| `DATABRICKS_HOST` | `app/services/sql_client.py`, `app/services/genie.py` | https URL of your workspace |
| `DATABRICKS_TOKEN` | same | PAT or OAuth token; must have SQL warehouse access |
| `DATABRICKS_WAREHOUSE_ID` | `app/services/sql_client.py` | the warehouse the app reads from |
| `APP_CATALOG` | `pipelines/common/config.py` (`get_catalog()`) | Unity Catalog name; defaults to `dais_hackathon_2026` |
| `GENIE_SPACE_ID` | `app/services/genie.py` | required for inline chat; from `setup_genie.sh` output |
| `GENIE_SPACE_URL` | `app/pages/2_Genie.py` | iframe fallback if inline chat fails |

When deployed as a Databricks App, the workspace injects `DATABRICKS_HOST` and an OAuth token automatically — only `DATABRICKS_WAREHOUSE_ID` and `GENIE_SPACE_ID` need to be set on the App resource.

## Architecture (one-liner)

Raw records → **Bronze** (Delta) → **Silver** (DBR built-in `h3_longlatash3` + claim extraction with citations + NFHS-5 demand) → **Gold** (`gold.h3_care_score` + state/district rollups; supplemental `medical_desert_*` for demand-aware scoring) → **Streamlit + pydeck** map (color = score, alpha = confidence) → **Lakebase** persists scenarios, overrides, NACHC root-cause tags, and shareable filter bookmarks → **Genie** answers natural-language questions over the same gold layer.
