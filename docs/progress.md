# Migration Progress: Streamlit → FastAPI + Databricks App Deployment

## Goal
Complete the Streamlit to FastAPI migration, deploy via Databricks Asset Bundle, and get the app serving from the deployed source on `main`.

## Constraints
- Workspace enforces "Git repository required" policy on Apps — purely workspace-uploaded source paths are rejected
- App resource has auto-deploy configured for `main` branch, so code must be on `main` to deploy automatically
- Databricks Apps runtime looks for `app.yml` (not `app.yaml`) at the repo root or at `source_code_path`
- Bundle validation rejects unknown fields on the App resource schema (`command` is not recognized at the bundle level)
- Cannot deploy from a non-`main` branch while auto-deploy is configured for `main`

## Steps Taken

### 1. Codebase Analysis
- Analyzed project structure (`app/`, `pipelines/`, `sql/`, `config/`, `docs/`)
- Read the existing migration plan at `docs/migration_pan.md`
- Understood the Streamlit → FastAPI migration scope (25 API endpoints, SPA frontend, Databricks SDK auth)

### 2. Bug Fix: credentials_provider in sql_client.py
- **File**: `app/core/sql_client.py`
- **Issue**: `credentials_provider=lambda: cfg.authenticate` — missing `()` call, passing the function reference instead of its return value
- **Fix**: Changed to `lambda: cfg.authenticate()`
- **Impact**: All Databricks SQL warehouse queries would have failed at auth time

### 3. Lint Fixes: 22 ruff issues
- 12 auto-fixed import sort issues (I001)
- 10 line-too-long issues (E501) in legacy Streamlit files (`app/Home.py`, `app/pages/`)
- Ran `ruff check . --fix` for auto-fixable issues
- Manually broke long f-strings and comments in Streamlit files

### 4. Verification
- All 26 unit tests pass (`pytest`)
- `ruff check .` is clean (0 issues)
- All 25 FastAPI endpoints respond correctly via OpenAPI schema validation
- SPA frontend at `app/web/dist/index.html` serves correctly (6 pages, hash-routed)
- App runs locally on port 8000

### 5. Git Operations
- Committed and pushed FastAPI migration (42 files, +2350/−208 lines) to `feature_ps` branch
- Merged `feature_ps` into `main` and pushed

### 6. Root app.yml Creation
- **File**: `app.yml` (repo root)
- **Content**:
  ```yaml
  command: ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "$DATABRICKS_APP_PORT"]
  ```
- **Purpose**: Databricks Apps runtime clones the full repo and looks for `app.yml` at the root when `source_code_path` is not set

### 7. app/app.yml Rename
- Renamed `app/app.yaml` → `app/app.yml` because Databricks Apps runtime looks for `.yml` extension, not `.yaml`
- Kept `app/app.yaml` for local Streamlit backward compatibility
- `app/app.yml` uses `uvicorn api.main:app` (path relative to `app/` subdirectory)

### 8. Deployment via DAB
- App resource `pradeep-care-gap-navigator` deployed via `databricks bundles deploy`
- First deployment failed: `error loading app spec from app.yml` — commit `ec9ca25` did not include the root `app.yml`
- Subsequent auto-deploy on `main` also failed with same error

### 9. Deployment Fix Attempts
- **Attempt 1**: Manual deploy with `source_code_path: "app"` from `main`
  - Build succeeded, app crashed: `ModuleNotFoundError: No module named 'app'`
  - Root cause: `app/app.yml` had `uvicorn api.main:app`, but `api/main.py` imports `from app.api.routers import...` — `app/` package not importable when running from within `app/`
- **Attempt 2**: Manual deploy without `source_code_path` from `main` (uses repo root)
  - Root `app.yml` with `uvicorn app.api.main:app` was picked up
  - **Result**: `SUCCEEDED`

### 10. Final State
- **App URL**: `https://pradeep-care-gap-navigator-7474651416140351.aws.databricksapps.com`
- **State**: ACTIVE
- **Deployment**: SUCCEEDED
- **Branch**: main
- **Commit**: `0c9d711` (includes root `app.yml` with `uvicorn app.api.main:app`)
- **Frontend**: SPA serving HTML (requires Databricks auth to view)
- **API**: FastAPI running on port 8000 behind Databricks auth proxy

## Key Learnings
1. `source_code_path` changes where the runtime looks for `app.yml` AND sets the working directory for relative imports
2. Python imports (`from app.api.routers import...`) require the `app/` package to be importable from `sys.path` — this works from the repo root but not from within `app/`
3. Auto-deploy on `main` blocks manual deploys from other branches
4. Bundle App resource schema does not accept `command` field — the command must be in `app.yml` only
5. `$DATABRICKS_APP_PORT` env var is provided by the Databricks Apps runtime and must be used in the command

## Remaining / Deferred
- Configure `app.yml` to serve SPA static files and route Genie Space URLs
- Re-enable or adjust auto-deploy if desired
- Add CI/CD for automated deployments on push
