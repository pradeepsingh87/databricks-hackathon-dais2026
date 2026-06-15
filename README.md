# Trust-Weighted Care Gap Navigator

Track 2 — **Medical Desert Planner** for the Databricks Apps & Agents Hackathon for Good (DAIS 2026).

A Databricks App that turns 10,000 messy Indian healthcare facility records into a **Trust-Weighted Care Gap Map**, helping NGO coordinators distinguish *real* care gaps from *data-poor* regions.

See [docs/problem_statement.md](docs/problem_statement.md) for the full problem framing and [docs/logical_architecture.md](docs/logical_architecture.md) for the architecture.

## Repo layout

```
app/             Streamlit Databricks App (UI, pages, components)
pipelines/       Bronze / Silver / Gold ETL on Delta + Mosaic H3
sql/             Genie space definitions, Gold views, Lakebase DDL
config/          Databricks Asset Bundle + environment config
scripts/         One-off ingest / deploy / setup scripts
notebooks/       Exploration & demo notebooks
tests/           Unit + integration tests
data/            Sample data and schema specs (raw data is not committed)
docs/            Problem statement, architecture, hackathon brief
```

## Quick start

```bash
# 1. install deps
pip install -r requirements.txt

# 2. configure your workspace
cp config/.env.example .env

# 3. run the app locally
streamlit run app/main.py

# 4. deploy to Databricks Apps
databricks bundle deploy --target dev
```

## Architecture (one-liner)

Raw records → **Bronze** (Delta) → **Silver** (Mosaic H3 + claim normalization) → **Gold** (trust-weighted care score per H3 cell) → **Streamlit + Kepler.gl** map → **Lakebase** persists user notes & scenarios → **Genie** answers NL questions over the Gold layer.
