# Silver Spatial Geocoding (Mosaic)

A second silver-layer pass that produces `silver.silver_facilities_geo` —
the spatial fact table the Gold layer uses for high-fidelity care-gap
aggregation. Lives next to the metadata-driven `silver_facilities`; doesn't
replace it.

## What it adds, per facility

| Column | Source | Why |
| --- | --- | --- |
| `geom` | `ST_Point(longitude, latitude)` via Mosaic | Native spatial type — opens `ST_Distance`, `ST_Within`, etc. |
| `h3_9`  | `grid_pointascellid(geom, 9)`  | ~174 m edge — neighborhood grain |
| `h3_10` | `grid_pointascellid(geom, 10)` | ~65 m edge — block grain |
| `h3_11` | `grid_pointascellid(geom, 11)` | ~25 m edge — building grain |
| 100+ NFHS-5 indicators | join on `(state, district)` | District-grain demand context |
| `_geo_built_at` | `current_timestamp()` | audit |

The coarser `h3_6 / h3_7 / h3_8` already exist on `silver_facilities`
(produced by the metadata-driven runner) and stay there. The two tables share
`facility_id` so downstream queries can join freely.

## Why a separate table

1. **Blast radius.** Mosaic is a heavy dependency (Java JNI, geometry codecs);
   the metadata-driven framework that produces `silver_facilities` is meant
   to stay generic. Bolting Mosaic into that runner would force every YAML-
   declared source to live with the geo deps.
2. **Storage.** The geometry column + 3 H3 strings + ~120 NFHS-5 columns more
   than triples row width. Queries that don't need geo (the homepage search,
   the override list) keep reading the lean `silver_facilities`.
3. **Reproducibility.** Re-running the spatial pass is decoupled from
   re-running the column rules — useful when iterating on H3 resolution
   choices without rebuilding everything upstream.

## Why NFHS-5 attaches by `(state, district)` and not by H3

NFHS-5 is **administrative-grain**: one row per district, no polygon. The
honest join is the administrative one. We already have the right keys on
`silver_facilities`:

- `state` — alias-resolved by the silver runner against `bronze.state_alias_reference`
- `district` — pincode-geocoded by joining `silver_pincode_directory`

Joining on the lower-cased pair gives ~95% match coverage in practice. Misses
fall through as NULL on the indicator columns and surface in the Gold
confidence calculation as "demand unknown" — a correct, transparent signal.

A spatial join via H3 would require:

- a separate India-district polygon GeoJSON (out of scope for this hackathon),
- tessellating those polygons into H3 cells at one resolution,
- joining each facility's H3 cell to the district cell index.

That's a defensible architecture for a production system but adds significant
work for no incremental quality on this dataset.

## Why H3 9, 10, 11

The brief calls for these resolutions and they map naturally to planner
intuitions:

| Res | ~edge | Use |
| --- | --- | --- |
| 9 | 174 m | Walking-distance neighborhoods — "all clinics within a 10-min walk of this point" |
| 10 | 65 m | City-block — distinguishing buildings on the same street |
| 11 | 25 m | Building-grain — facility footprint precision |

The coarser 6/7/8 already on `silver_facilities` cover state/district/city
grains for map zoom-out. Together the six resolutions span every planner
zoom level without picking a single compromise.

## Filter: `in_india_bbox = TRUE`

The pipeline excludes rows where `in_india_bbox = false` from the geocoded
output. We saw 6 such rows in profiling — coordinates that put a Kerala
hospital in the North Atlantic. Generating an H3 cell for those would
silently produce an ID over the wrong continent and pollute downstream
aggregates. Better to drop them here and keep them visible in
`silver_facilities` as a data-quality signal.

## Where this slots in

```
bronze_facilities_raw
        │
        ▼ (metadata-driven framework)
silver_facilities          ← state, district, h3_6/7/8, scalar columns
        │
        ├──────────────────────────────────┐
        ▼                                  ▼
silver_facilities_geo                 silver_facility_capability_claims
  (ST_Point, h3_9/10/11,                (per-(facility, capability) trust
   NFHS-5 indicators)                    rows for the gold scorer)
        │                                  │
        └──────────────┬───────────────────┘
                       ▼
                 gold.h3_care_score
                 gold.care_score_by_state / _by_district
```

The Gold scorer joins the two silver children on `facility_id` to combine
*claim trust* (from claims) with *demand context* (from NFHS-5 on
silver_facilities_geo) at whatever H3 resolution the gold query selects.

## Running it

The bundle DAG has it as `silver_spatial_geocode`, depending on
`silver_normalize_all` and parallel-fanned with `silver_extract_capability_claims`.
Both fan back into `gold_trust_score`.

```bash
# Trigger the whole ETL
databricks bundle run care_gap_etl

# Or just this step
databricks bundle run care_gap_etl --target dev \
  --var=app_prefix=$USER --only silver_spatial_geocode
```

## Cluster requirements

- **Mosaic** library — installed via `%pip install databricks-mosaic` in the
  notebook itself (no cluster-side install needed). DBR 13+ will work; older
  runtimes need the Mosaic-bundled MLR.
- **`spark.databricks.libraryIsolation.shareLibrariesAcrossExecutors`** —
  Mosaic ships JNI; the default on serverless / shared compute is fine but
  classic clusters with isolation may need this set to `true`.

## Smoke-test query

After the job finishes, sanity-check the join coverage:

```sql
SELECT
  COUNT(*)                                 AS total,
  COUNT(geom)                              AS with_geom,
  COUNT(h3_11)                             AS with_h3_11,
  COUNT(institutional_birth_5y_pct)        AS with_nfhs5_inst_birth,
  COUNT(*)
    - COUNT(institutional_birth_5y_pct)    AS missing_nfhs5
FROM dais_hackathon_2026.silver.silver_facilities_geo;
```

Expected, given current data: `total ≈ 9,964`, `with_h3_11 = total`,
`missing_nfhs5 ≈ 200–500` (facilities whose pincode geocode landed on a
district NFHS-5 doesn't cover — usually city-only entries).
