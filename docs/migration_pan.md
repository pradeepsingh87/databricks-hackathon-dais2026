# Streamlit to FastAPI Migration Plan

## Goal

Migrate the current Streamlit application to a FastAPI-backed web application while preserving the existing Databricks, Lakebase, Genie, and Gold/Silver data workflows.

The migration should be incremental. Keep the Streamlit app running until the FastAPI API layer and replacement frontend reach feature parity.

## Current Application Shape

The repository already has a useful separation between page orchestration and service logic:

- Streamlit entry points live in `app/Home.py` and `app/pages/`.
- Reusable Streamlit UI lives in `app/components/`.
- Databricks SQL, Genie, Lakebase, config, brand, and user helpers live in `app/services/`.
- Gold/Silver/Lakebase data contracts are mostly centralized in `app/services/gold.py` and `app/services/lakebase.py`.

The most reusable migration assets are:

- `app/services/gold.py`: read-side queries for care scores, rollups, facilities, NFHS-5 indicators, and score history.
- `app/services/lakebase.py`: write/read persistence for overrides, scenarios, bookmarks, and root-cause categorizations.
- `app/services/genie.py`: Databricks Genie API wrapper.
- `app/services/domains.py`: domain and indicator registry loading.
- `app/services/brand.py`: brand configuration loading.

The main Streamlit couplings to remove are:

- `app/services/sql_client.py` imports Streamlit for caching and session error state.
- `app/services/user.py` reads user identity through Streamlit context.
- `app/components/filters.py` stores filter state in `st.session_state`.
- Pages directly convert DataFrames into Streamlit tables, metrics, charts, maps, and forms.

## Target Architecture

Use FastAPI as the backend and build a separate frontend for the interactive application.

Recommended target:

```text
app/
  api/
    main.py
    deps.py
    schemas.py
    routers/
      config.py
      care_gaps.py
      facilities.py
      genie.py
      actions.py
      scenarios.py
      performance.py
  core/
    sql_client.py
    user.py
    serialization.py
  services/
    gold.py
    lakebase.py
    genie.py
    domains.py
    brand.py
  web/
    # Optional React/Vite frontend if served from the same app
```

FastAPI should own:

- API routing.
- Request validation.
- Response contracts.
- User identity from forwarded headers.
- Databricks SQL access.
- Lakebase writes.
- Genie orchestration.
- Health checks and deployment readiness.

The frontend should own:

- Filter state.
- Navigation.
- Map rendering.
- Tables, cards, metrics, charts, forms, and chat UI.

## Phase 1: Add FastAPI Beside Streamlit

Add backend dependencies to `requirements.txt` and `app/requirements.txt`:

```text
fastapi
uvicorn[standard]
cachetools
```

Create a minimal FastAPI app:

```text
app/api/main.py
app/api/routers/health.py
```

Initial endpoints:

```text
GET /healthz
GET /api/status
```

Do not change `app/app.yaml` yet. Keep Streamlit as the deployed command until the API has useful coverage.

## Phase 2: Remove Streamlit from Shared Services

Move framework-neutral infrastructure into `app/core/`.

### SQL Client

Refactor `app/services/sql_client.py` into `app/core/sql_client.py`.

Replace:

- `st.cache_data` with `cachetools.TTLCache`, `functools.lru_cache`, or no cache for the first pass.
- `st.session_state["_last_query_error"]` with structured logging.

Keep the external interface close to the current one:

```python
def query_df(sql_text: str, params: tuple | None = None) -> pd.DataFrame: ...
def execute(sql_text: str, params: tuple | None = None) -> bool: ...
def is_configured() -> bool: ...
```

Then update `gold.py` and `lakebase.py` to import from `app.core.sql_client`.

### User Identity

Move user resolution into `app/core/user.py`.

FastAPI dependency:

```python
def current_user(request: Request) -> str:
    for header in (
        "X-Forwarded-Email",
        "X-Forwarded-User",
        "X-Forwarded-Preferred-Username",
    ):
        value = request.headers.get(header)
        if value:
            return value
    return os.environ.get("DATABRICKS_USER") or os.environ.get("APP_USER") or "demo"
```

Preserve `app_prefix()` and `app_title()` behavior without Streamlit.

## Phase 3: Define API Contracts

Create `app/api/schemas.py` with Pydantic models.

Core models:

- `FilterState`
- `Domain`
- `Indicator`
- `Brand`
- `MapKpis`
- `H3ScoreCell`
- `StateRollup`
- `DistrictRollup`
- `Facility`
- `FacilityLocation`
- `ScenarioCreate`
- `Scenario`
- `BookmarkCreate`
- `Bookmark`
- `OverrideCreate`
- `Override`
- `GapCategorizationCreate`
- `GapCategorization`
- `GenieAskRequest`
- `GenieAnswerResponse`
- `PerformanceRiskBand`
- `ProjectedTrendPoint`

Add a serialization helper in `app/core/serialization.py`:

```python
def records_from_df(df: pd.DataFrame) -> list[dict]:
    ...
```

This helper should handle:

- `NaN` and `NaT` as `None`.
- Pandas timestamps as ISO strings.
- Decimal/numpy scalar values as native Python values.
- JSON strings in payload/citations fields where appropriate.

## Phase 4: Build API Routers

### Config Router

```text
GET /api/config/brand
GET /api/config/domains
GET /api/config/capabilities
GET /api/config/states
GET /api/config/indicators
```

Backed by:

- `brand.load_brand()`
- `domains.load_domains()`
- `domains.all_indicators()`
- `gold.list_capabilities()`
- `gold.list_states()`

### Care Gaps Router

```text
GET /api/care-gaps/kpis
GET /api/care-gaps/h3-scores
GET /api/care-gaps/nfhs5
GET /api/care-gaps/rollup/state
GET /api/care-gaps/rollup/district
```

Query parameters should mirror current filter state:

- `capability`
- `state`
- `h3_resolution`
- `confidence_min`
- `indicator`

Backed by:

- `gold.fetch_map_kpis()`
- `gold.fetch_h3_scores()`
- `gold.fetch_nfhs5_indicator()`
- `gold.fetch_state_rollup()`
- `gold.fetch_district_rollup()`

### Facilities Router

```text
GET /api/facilities
GET /api/facilities/locations
GET /api/facilities/search
```

Backed by:

- `gold.fetch_facilities_in_cell()`
- `gold.fetch_facilities_in_region()`
- `gold.fetch_facility_locations()`
- `gold.search_facilities()`

### Actions Router

```text
POST /api/overrides
GET /api/overrides
POST /api/gap-categorizations
GET /api/gap-categorizations
```

Backed by:

- `lakebase.add_override()`
- `lakebase.list_overrides()`
- `lakebase.add_gap_categorization()`
- `lakebase.list_gap_categorizations()`

Use the FastAPI current-user dependency for all writes.

### Scenarios Router

```text
POST /api/scenarios
GET /api/scenarios
POST /api/bookmarks
GET /api/bookmarks
```

Backed by:

- `lakebase.save_scenario()`
- `lakebase.list_scenarios()`
- `lakebase.save_bookmark()`
- `lakebase.list_bookmarks()`

### Genie Router

```text
GET /api/genie/status
POST /api/genie/ask
```

Backed by:

- `genie.is_configured()`
- `genie.ask()`
- `genie.fetch_rows()`

Start with synchronous polling to match current behavior. Consider background jobs or streaming responses after parity.

### Performance Router

```text
GET /api/performance/district-risk
GET /api/performance/score-history
GET /api/performance/projected-trend
```

Backed by:

- `gold.fetch_district_rollup()`
- `gold.fetch_score_history()`

Move the current deterministic projection logic out of `app/pages/4_Performance.py` into a small service function so it can be tested and reused.

## Phase 5: Frontend Migration

FastAPI should not recreate Streamlit widgets directly. Build a browser frontend against the API.

Recommended option:

- React + Vite.
- deck.gl for H3 and facility maps.
- TanStack Query for API state.
- A small client-side store for filters and selected H3 cell.

Route mapping:

```text
/               -> Home
/care-gaps      -> Care Gap Navigator
/genie          -> Genie chat
/action-center  -> Evidence and Action Center
/performance    -> Performance and Status Tracker
/scenarios      -> Planning Scenarios
```

Current Streamlit state mapping:

- `filter_domain` -> frontend filter store.
- `filter_capability` -> frontend filter store.
- `filter_state` -> frontend filter store.
- `filter_h3_resolution` -> frontend filter store.
- `selected_h3_cell` -> frontend filter store or URL query param.
- `filter_confidence_min` -> frontend filter store.
- `filter_admin_overlay` -> frontend filter store.
- `filter_nfhs5_indicator` -> frontend filter store.
- `genie_history` -> frontend chat state.
- `genie_conversation_id` -> frontend chat state.

Prefer URL query params for shareable analysis views:

```text
/care-gaps?capability=icu&state=Bihar&h3_resolution=7&confidence_min=0.3
/action-center?capability=icu&h3_cell=...
```

## Phase 6: Deployment Cutover

Once FastAPI and the new frontend reach parity, update `app/app.yaml`.

Current command:

```yaml
command: ["streamlit", "run", "Home.py", "--server.port=8000", "--server.address=0.0.0.0"]
```

Target command:

```yaml
command: ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

If serving a built frontend from FastAPI, mount static assets in `api.main`:

```python
app.mount("/", StaticFiles(directory="web/dist", html=True), name="web")
```

Keep all existing Databricks environment variables:

- `DATABRICKS_HOST`
- `DATABRICKS_WAREHOUSE_ID`
- `APP_CATALOG`
- `GENIE_SPACE_ID`
- `GENIE_SPACE_URL`
- `APP_PREFIX`
- `APP_USER`

## Phase 7: Tests and Validation

Add API-focused tests under `tests/unit/` and, if needed, `tests/api/`.

Recommended coverage:

- `/healthz` returns healthy.
- Config endpoints serialize brand/domains/capabilities correctly.
- Care gap endpoints call service functions with expected parameters.
- DataFrame serialization handles nulls and timestamps.
- Lakebase write endpoints attach the current user.
- Genie endpoint returns configured/unconfigured status cleanly.
- Performance projection is deterministic.

Use `fastapi.testclient.TestClient` and monkeypatch Databricks-backed service functions so tests do not require a live workspace.

Run before cutover:

```text
ruff check .
pytest
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## Risks and Mitigations

### Streamlit Session State

Risk: The current app relies on `st.session_state` for cross-page filters and Genie chat state.

Mitigation: Move filter state to URL params and frontend state. Move durable collaboration state to Lakebase, as the app already does for scenarios, bookmarks, overrides, and root-cause tags.

### DataFrame Serialization

Risk: Pandas values are not always JSON-safe.

Mitigation: Centralize DataFrame-to-record conversion and test nulls, timestamps, numpy scalars, and JSON payload fields.

### Map Rendering

Risk: Current maps are implemented with Streamlit + PyDeck.

Mitigation: Return raw H3/facility data from FastAPI and render maps with deck.gl in the frontend. Port color rules from `app/components/care_map.py` and `app/components/facility_map.py`.

### Genie Latency

Risk: Genie can take up to two minutes because the current wrapper polls until completion.

Mitigation: Keep synchronous behavior for parity, then consider background tasks, server-sent events, or polling endpoints if user experience suffers.

### Databricks Auth

Risk: Auth currently depends on Databricks Apps runtime and SDK unified auth.

Mitigation: Preserve the SDK `Config()` approach and test local fallback through `databricks auth login` or environment variables.

## Suggested Implementation Order

1. Add FastAPI dependencies and a health endpoint.
2. Refactor SQL and user helpers to remove Streamlit imports.
3. Add Pydantic schemas and DataFrame serialization helpers.
4. Add config and care-gap read endpoints.
5. Add facility and performance endpoints.
6. Add Lakebase write endpoints.
7. Add Genie endpoints.
8. Build the new frontend against the API.
9. Run Streamlit and FastAPI in parallel for validation.
10. Flip `app/app.yaml` to `uvicorn`.
11. Remove Streamlit pages/components after parity is confirmed.

## Definition of Done

- FastAPI app starts locally and in Databricks Apps.
- Existing Gold/Silver/Lakebase/Genie workflows are available through typed API endpoints.
- New frontend covers all current Streamlit pages.
- Filters and selected cell can be shared through URL state.
- User writes are attributed from forwarded Databricks headers.
- `ruff check .` and `pytest` pass.
- Streamlit deployment command is replaced by the FastAPI command.
