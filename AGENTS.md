# Repository Guidelines

## Project Structure & Module Organization
This repository combines a Streamlit app, Databricks bundle config, ETL pipelines, and SQL assets. App entrypoints live in `app/`, with reusable UI in `app/components/`, page views in `app/pages/`, and data access helpers in `app/services/`. Pipeline code is organized by layer under `pipelines/bronze`, `pipelines/silver`, and `pipelines/gold`. SQL assets live in `sql/views`, `sql/genie`, and `sql/lakebase`. Configuration files are under `config/`, while design notes and problem framing live in `docs/`. Keep sample schemas in `data/schemas`; do not commit raw datasets or secrets.

## Build, Test, and Development Commands
Install runtime dependencies with `pip install -r requirements.txt`. Run the app locally with `streamlit run app/main.py`. Validate Python style with `ruff check .`. Run tests with `pytest`. For Databricks workflows, use `./deploy.sh` to validate and deploy the bundle, `./scripts/run_pipeline.sh --target dev` to trigger the ETL job, and `./scripts/setup_uc.sh` to create Unity Catalog and Lakebase objects once credentials are set.

## Coding Style & Naming Conventions
Target Python 3.11 and follow the existing Ruff configuration in `pyproject.toml`: 100-character lines, sorted imports, and modern Python upgrades enabled. Use 4-space indentation. Prefer `snake_case` for functions, variables, modules, and test files; keep Streamlit page filenames numeric, such as `app/pages/2_Drill_Down.py`, to preserve navigation order. Keep service modules focused on one responsibility, such as SQL access or Lakebase writes.

## Testing Guidelines
Pytest is configured to discover tests from `tests/`, and the current layout uses `tests/unit/` with files named `test_*.py`. Add fast unit coverage for pure scoring and transformation logic before adding integration coverage for Databricks-dependent paths. The checked-in CI workflow runs `ruff check .` and `pytest`; note that it references `requirements-dev.txt`, which is not currently present, so install `pytest` and `ruff` manually if needed.

## Commit & Pull Request Guidelines
Recent commits use short, imperative summaries like `Added initial codebase` and `Added new files`. Prefer concise subject lines that describe the user-visible change. Pull requests should explain the problem, summarize the approach, list local validation steps, and include screenshots for Streamlit UI changes. Link the relevant issue or hackathon task when available.
