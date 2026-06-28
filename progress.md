# Streamlit → FastAPI Migration Progress

## Current State: Phase 1-7 Complete

### ✅ Phase 1: FastAPI Dependencies & Health Endpoint
- Added fastapi, uvicorn, cachetools to `requirements.txt` and `app/requirements.txt`
- Created `app/api/main.py` with FastAPI app entrypoint
- Created `app/api/routers/health.py` with `GET /healthz` and `GET /api/status`

### ✅ Phase 2: Framework-Neutral Shared Services
- Refactored `app/services/sql_client.py` → `app/core/sql_client.py`
  - Removed `st.cache_data` → uses `cachetools.TTLCache`
  - Removed `st.session_state["_last_query_error"]` → structured logging
  - Fixed bug: `credentials_provider=lambda: cfg.authenticate` → `cfg.authenticate()`
- Refactored `app/services/user.py` → `app/core/user.py`
  - User identity resolved from forwarded headers (`X-Forwarded-Email`, etc.) or env vars
  - `app_prefix()` and `app_title()` preserved without Streamlit
- Created `app/core/serialization.py` with `records_from_df()` helper
  - Handles NaN/NaT → None, timestamps → ISO strings, Decimal/numpy → native, JSON string parse
- Backward-compat re-exports kept at `app/services/sql_client.py` and `app/services/user.py`

### ✅ Phase 3: API Contracts (Pydantic Schemas)
- Created `app/api/schemas.py` with all models:
  - FilterState, Domain, Indicator, Brand, MapKpis, H3ScoreCell
  - StateRollup, DistrictRollup, Facility, FacilityLocation
  - ScenarioCreate/Scenario, BookmarkCreate/Bookmark
  - OverrideCreate/Override, GapCategorizationCreate/GapCategorization
  - GenieAskRequest/GenieAnswerResponse
  - PerformanceRiskBand, ProjectedTrendPoint

### ✅ Phase 4: API Routers (25 endpoints)
| Router | Endpoints |
|--------|-----------|
| **Config** | `GET /api/config/brand`, `/domains`, `/capabilities`, `/states`, `/indicators` |
| **Care Gaps** | `GET /api/care-gaps/kpis`, `/h3-scores`, `/nfhs5`, `/rollup/state`, `/rollup/district` |
| **Facilities** | `GET /api/facilities` (list), `/locations`, `/search` |
| **Actions** | `POST/GET /api/overrides`, `POST/GET /api/gap-categorizations` |
| **Scenarios** | `POST/GET /api/scenarios`, `POST/GET /api/bookmarks` |
| **Genie** | `GET /api/genie/status`, `POST /api/genie/ask` |
| **Performance** | `GET /api/performance/district-risk`, `/score-history`, `/projected-trend`, `/districts` |
| **Health** | `GET /healthz`, `GET /api/status` |

### ✅ Phase 5: Frontend (SPA)
- Built standalone HTML/CSS/JS single-page app at `app/web/dist/index.html` (794 lines)
- Hash-based routing with 6 pages: Home, Care Gaps, Genie, Action Center, Performance, Scenarios
- Filter controls persist to localStorage
- Full API integration with all backend endpoints
- Responsive layout, branded via CSS custom properties from `/api/config/brand`

### ✅ Phase 6: Deployment Cutover
- `app/app.yaml` updated to use uvicorn command:
  ```yaml
  command: ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
  ```

### ✅ Phase 7: Tests
- Created `tests/unit/test_api_migration.py` with 5 tests:
  - Health check returns healthy
  - H3 scores endpoint serializes DataFrames correctly with confidence filter
  - Override writes attach forwarded user from headers
  - DataFrame serialization normalizes nulls/timestamps/Decimals/JSON
  - Performance projection is deterministic
- All 26 unit tests pass
- `ruff check .` passes clean

### Remaining Streamlit Code
Streamlit pages (`app/pages/`, `app/components/`, `app/Home.py`) are kept for parallel running. They import from the refactored `app.core.*` layer via backward-compat `app.services.*` re-exports. These can be removed once feature parity is fully validated against the new FastAPI + SPA stack.
