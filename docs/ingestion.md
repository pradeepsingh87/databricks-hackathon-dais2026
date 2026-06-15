# Ingestion Framework

Metadata-driven Bronze → Silver pipeline for the Trust-Weighted Care Gap Navigator. Adding a new source is a YAML edit, not a code change.

## Why metadata-driven?

The hackathon dataset is **deliberately messy**:

- 51 columns, almost all typed as `STRING` even when they hold integers, years, or JSON arrays
- `address_stateOrRegion` has **254 distinct values** (India has 28 states + 8 UTs) — it leaks city names, country names, and free text
- `latitude`/`longitude` include **6 rows outside the India bbox** (e.g. a Kerala hospital pinned at lat 59, lng −38)
- `capability`, `procedure`, `equipment`, `specialties`, `source_urls` are **JSON arrays serialized as strings**
- Values like `"null"`, `""`, and trailing whitespace need to be coerced to `NULL`
- Numeric fields like `numberDoctors`, `capacity`, `yearEstablished` are stored as strings with units, commas, and noise

Hand-writing per-column logic in PySpark would bury those rules across many notebooks. Instead we **declare** every rule in [`config/ingestion/sources.yml`](../config/ingestion/sources.yml) and have one runner per layer apply them uniformly. The runner is the same for `facilities`, `pincode_directory`, and `nfhs5`; only the YAML differs.

## Source registry

Three upstream tables in `psb_catalog.virtue_foundation_dataset`:

| Source | Rows | Role |
| --- | --- | --- |
| `facilities` | 10,088 | Primary entity — facility claims to evaluate |
| `india_post_pincode_directory` | 165,627 | Pincode → district/state reference |
| `nfhs_5_district_health_indicators` | 706 | District-level health context |

Each source has one entry in [`sources.yml`](../config/ingestion/sources.yml). The contract for an entry:

```yaml
- name: facilities
  source_table: facilities                # under defaults.source_catalog/schema
  bronze_table: bronze_facilities_raw     # under defaults.target_catalog
  silver_table: silver_facilities
  primary_key: unique_id
  parse_json_columns: [capability, procedure, equipment, specialties, source_urls]
  columns:
    - { source: address_stateOrRegion, target: state_raw, cast: string, transforms: [trim] }
    - { source: address_zipOrPostcode, target: pincode,   cast: string, transforms: [trim, digits_only, left_6] }
    - { source: latitude,              target: latitude,  cast: double }
    # ...
  standardize:
    - { rule: state_lookup,    from: state_raw, to: state,                  reference: india_state_alias, on_miss: keep_raw }
    - { rule: pincode_geocode, from: pincode,   to: [district, state_from_pincode], reference: pincode_directory }
  geo:
    lat_col: latitude
    lng_col: longitude
    india_bbox: { lat_min: 6.5, lat_max: 37.5, lng_min: 68.0, lng_max: 97.5 }
    on_outside_bbox: flag_only
    h3_resolutions: [6, 7, 8]
  expectations:
    - { name: pk_not_null, expr: "facility_id IS NOT NULL", severity: error }
    - { name: in_india_bbox, expr: "latitude BETWEEN 6.5 AND 37.5 AND longitude BETWEEN 68 AND 97.5", severity: warn }
    # ...
```

The runner consumes this entry. **No PySpark code needs to change** when a new source is added.

## Layer responsibilities

### Bronze — verbatim landing

[`pipelines/framework/bronze.py`](../pipelines/framework/bronze.py) does only this:

1. Read the source table.
2. Add audit columns: `_ingested_at`, `_source_table`, `_bronze_run_id`.
3. Write to `dais_hackathon_2026.bronze.<bronze_table>` with `mergeSchema=true`.

**Bronze never transforms.** If a downstream rule is wrong, we re-run Silver from Bronze without re-reading the source. Bronze is the source of truth for what actually arrived.

### Silver — clean, type, standardize, geocode

[`pipelines/framework/silver.py`](../pipelines/framework/silver.py) executes these stages, each driven by metadata:

1. **`_parse_json_columns`** — convert JSON-string columns (`capability`, `procedure`, `equipment`, `specialties`, `source_urls`) into `ARRAY<STRING>` using `from_json` in PERMISSIVE mode (so a single bad row doesn't kill the batch).
2. **`_apply_column_rules`** — for every entry in `columns`:
   - rename `source` → `target`
   - apply named transforms in order (see below)
   - cast to declared type
   - emit `NULL` if the column is missing upstream (schema-stable output)
3. **`_standardize`** — resolve declared lookups:
   - `india_state_alias` — left-join against [`config/ingestion/state_aliases.csv`](../config/ingestion/state_aliases.csv) to canonicalize 254 spellings to ~36 official states/UTs. `on_miss: keep_raw` preserves whatever was there if it's not a known alias.
   - `pincode_directory` — left-join against the silver pincode table to enrich every facility with `district` and `state_from_pincode` (a second source-of-truth for the state — disagreements are surfaced in Gold as a low-confidence signal).
4. **`_apply_geo`** — add `in_india_bbox` flag (we **flag, not drop** — keeping the row makes the data deficiency visible to the planner) and H3 cell columns at resolutions 6, 7, 8.
5. **Expectations** — every rule in the entry's `expectations:` block is evaluated and results land in `dais_hackathon_2026.bronze.dq_log` (one row per (source, expectation, run)).

### Transform catalog

Transform names in YAML map to PySpark functions in [`pipelines/framework/transforms.py`](../pipelines/framework/transforms.py):

| Transform | What it does | Why we need it here |
| --- | --- | --- |
| `trim` | strip whitespace | Pervasive in the source |
| `collapse_ws` | collapse runs of whitespace | Names like `"Apollo  Hospital "` |
| `lower`, `title_case` | case normalization | `"Punjab"` vs `"PUNJAB"` vs `"punjab"` |
| `digits_only` | regex out non-digits | `"100 beds"` → `"100"`; survives `"null"` strings |
| `left_6` | substring 0..6 | Fix 7-digit pincodes from typos |
| `year_in_range_1800_2026` | NULL-out impossible years | `"99"`, `"2099"` etc. |
| `null_if_string_null` | `"null"` / `""` → `NULL` | Common in CSV exports |

Adding a new transform means adding a function and registering it in `TRANSFORMS` — one place to extend.

## Data quality (DQ) log

Every Silver run appends to `dais_hackathon_2026.bronze.dq_log`:

```
source       string  -- e.g. 'facilities'
layer        string  -- 'silver'
expectation  string  -- e.g. 'in_india_bbox'
severity     string  -- 'error' | 'warn'
failed       bigint
total        bigint
checked_at   timestamp
```

The Gold layer reads this to compute per-region **confidence**: regions whose facilities fail many warn-level expectations get lower confidence, which in turn drives the **alpha channel** of the Kepler.gl map — the visual distinction between "proven absent" and "data-deficient".

## Dependency-aware execution

`silver.run_all()` runs `pincode_directory` before `facilities` so the pincode geocode join works. The order is metadata-aware (driven by the standardize rules) and not hardcoded — if a future source declares a dependency, the runner can be extended to topologically sort.

## Running it

Two ways:

```bash
# Via the bundle (preferred — runs as a Databricks Job)
databricks bundle run care_gap_etl

# Or, directly in a notebook
%run ../pipelines/bronze/ingest_facilities.py
%run ../pipelines/silver/normalize_claims.py
```

Both notebooks are 10-line entrypoints that just call `bronze.run_all(spark)` / `silver.run_all(spark)`.

## What's intentionally NOT in this framework

- **Trust scoring** — that lives in Gold ([`pipelines/gold/trust_weighted_score.py`](../pipelines/gold/trust_weighted_score.py)). Silver only normalizes; Gold judges.
- **NLP claim extraction from `description`** — Silver keeps the raw text; the LLM-assisted extraction step happens between Silver and Gold and writes to a separate `silver.facility_claims` table.
- **Mosaic explicit dependency** — we use the built-in `h3_longlatash3string` SQL function (DBR 13+). Mosaic can be swapped in by changing one line in `_apply_geo`.

## Layout

```
config/ingestion/
  sources.yml            # the registry — declarative source contracts
  state_aliases.csv      # alias → canonical state lookup

pipelines/framework/
  __init__.py
  registry.py            # YAML loader + dataclasses (Source, ColumnRule, ...)
  transforms.py          # named PySpark transforms (TRANSFORMS dict)
  bronze.py              # run_bronze(spark, source) / run_all(spark)
  silver.py              # run_silver(spark, source) / run_all(spark)
  expectations.py        # evaluate rules, write to dq_log

pipelines/bronze/ingest_facilities.py    # 10-line entrypoint -> bronze.run_all
pipelines/silver/normalize_claims.py     # 10-line entrypoint -> silver.run_all
```
