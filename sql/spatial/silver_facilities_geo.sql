-- ===========================================================================
-- silver.silver_facilities_geo  —  Silver geospatial fact + NFHS-5 demand
-- ===========================================================================
-- Replaces the prior pipelines/silver/spatial_geocode.py notebook (which
-- depended on the `databricks-mosaic` pip package — that broke our cluster
-- run with a `pip install` failure).
--
-- The Databricks AI Dev Kit's `databricks-dbsql/geospatial-collations.md`
-- skill documents the modern preferred path: the DBR-built-in H3 functions
-- (`h3_longlatash3`, `h3_h3tostring`, etc.) shipped since DBR 11.2 with the
-- H3 Java library 3.7.0. **No library install required.** Same algorithm
-- under the hood as Mosaic's `grid_pointascellid`.
--
-- Why BIGINT (not STRING) for the H3 IDs:
--   • 8-byte int vs 16-char string — 2x smaller storage, ~2-3x faster joins.
--   • Spark spatial-indexing optimizer routes BIGINT-keyed h3 joins through
--     the optimized physical plan (~17x faster than equivalent string-key
--     hash joins on classic clusters per the kit's geospatial skill).
--   • Convert to hex for display via h3_h3tostring(h3_9) — only at read time.
--
-- Why a separate table from silver_facilities:
--   • silver_facilities is rebuilt by the metadata-driven framework runner;
--     we don't want to special-case spatial logic in that loop.
--   • Geometry + 3 H3 columns + ~5 NFHS-5 columns roughly doubles row width.
--     Lean queries (homepage search, override list) keep reading the slim
--     silver_facilities and don't pay for it.
--
-- Run via: databricks --profile DEFAULT api post /api/2.0/sql/statements
--          (paste this file's CREATE TABLE statement) — or via the bundle
--          DAG (config/resources/jobs.yml::silver_spatial_geocode).
-- ===========================================================================

CREATE OR REPLACE TABLE dais_hackathon_2026.silver.silver_facilities_geo
USING DELTA
CLUSTER BY (state, district, h3_9)            -- Liquid Clustering on the join keys
COMMENT 'Spatial fact table: silver_facilities augmented with H3 cells at resolutions 9/10/11 (neighborhood/block/building grain) and the matching NFHS-5 demand row for the facility''s district. Powers high-fidelity geospatial Gold queries. H3 IDs are BIGINT for fast hash-based joins.'
AS
WITH nfhs_canonical AS (
  -- NFHS-5 has 5 state spellings that don't match the canonical alias-resolved
  -- list silver_facilities was built against (Maharastra, Andaman & Nicobar
  -- Islands, Dadra ... & ... & Diu, Jammu & Kashmir, Nct Of Delhi).
  -- bronze.state_alias_reference maps these to canonical names; the LEFT
  -- JOIN here falls back to the raw value when no alias is found, so we
  -- never lose rows.
  SELECT
    COALESCE(a.canonical_state, n.state) AS state_canonical,
    n.district,
    n.institutional_birth_5y_pct,
    n.child_u5_who_are_stunted_height_for_age_18_pct,
    n.hh_member_covered_health_insurance_pct,
    n.women_age_30_49_years_ever_undergone_a_cervical_screen_pct,
    n.w15_plus_with_high_bp_sys_gte_140_mmhg_and_or_dia_gte_90_mm_pct
  FROM dais_hackathon_2026.silver.silver_nfhs5_district n
  LEFT JOIN dais_hackathon_2026.bronze.state_alias_reference a
    ON lower(trim(n.state)) = lower(trim(a.alias))
)
SELECT
  -- ===== facility identity & administrative geography ======================
  f.facility_id,
  f.name,
  f.state,
  f.district,
  f.city,
  f.pincode,
  f.latitude,
  f.longitude,

  -- ===== H3 hexagonal spatial index, BIGINT, resolutions 9/10/11 ===========
  h3_longlatash3(f.longitude, f.latitude,  9) AS h3_9,
  h3_longlatash3(f.longitude, f.latitude, 10) AS h3_10,
  h3_longlatash3(f.longitude, f.latitude, 11) AS h3_11,

  -- ===== facility supply attributes ========================================
  f.capacity,
  f.number_doctors,
  f.year_established,

  -- ===== NFHS-5 demand indicators (district-grain join, alias-normalized) ==
  -- LEFT JOIN keeps facilities even where (state, district) doesn't match
  -- an NFHS-5 row. Misses are mostly *district-name* mismatches that we
  -- haven't built an alias table for yet (e.g. 'Bengaluru Urban' vs
  -- 'Bangalore Urban', 'Gurugram' vs 'Gurgaon'). Misses surface as NULL
  -- demand, which the Gold scorer treats as 'demand unknown' transparently.
  n.institutional_birth_5y_pct,
  n.child_u5_who_are_stunted_height_for_age_18_pct,
  n.hh_member_covered_health_insurance_pct,
  n.women_age_30_49_years_ever_undergone_a_cervical_screen_pct,
  n.w15_plus_with_high_bp_sys_gte_140_mmhg_and_or_dia_gte_90_mm_pct,

  -- ===== audit =============================================================
  current_timestamp() AS _geo_built_at
FROM dais_hackathon_2026.silver.silver_facilities f
LEFT JOIN nfhs_canonical n
  ON  lower(trim(f.state))    = lower(trim(n.state_canonical))
  AND lower(trim(f.district)) = lower(trim(n.district))
WHERE f.in_india_bbox = TRUE
  AND f.latitude  IS NOT NULL
  AND f.longitude IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Column comments + tags  (Genie One reads these as the semantic layer)
-- ---------------------------------------------------------------------------
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN h3_9  COMMENT 'Hexagonal Spatial ID at H3 resolution 9 (~174 m edge — neighborhood grain). BIGINT for fast hash-based joins; convert to hex via h3_h3tostring() for display.';
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN h3_10 COMMENT 'Hexagonal Spatial ID at H3 resolution 10 (~65 m edge — city block grain). BIGINT for fast hash-based joins.';
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN h3_11 COMMENT 'Hexagonal Spatial ID at H3 resolution 11 (~25 m edge — building grain). BIGINT for fast hash-based joins.';

ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN h3_9  SET TAGS ('geography' = 'h3_index');
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN h3_10 SET TAGS ('geography' = 'h3_index');
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN h3_11 SET TAGS ('geography' = 'h3_index');

ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN institutional_birth_5y_pct
    COMMENT 'NFHS-5: % of births in the last 5 years that took place in a health facility. Low values indicate high MATERNITY demand.';
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN child_u5_who_are_stunted_height_for_age_18_pct
    COMMENT 'NFHS-5: % of children under 5 who are stunted (low height-for-age). Proxy for NICU / child-health demand.';
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN hh_member_covered_health_insurance_pct
    COMMENT 'NFHS-5: % of households with health insurance. Low values mean patients defer care — proxy for EMERGENCY demand.';
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN women_age_30_49_years_ever_undergone_a_cervical_screen_pct
    COMMENT 'NFHS-5: % of women 30-49 ever screened for cervical cancer. Proxy for ONCOLOGY demand.';
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN w15_plus_with_high_bp_sys_gte_140_mmhg_and_or_dia_gte_90_mm_pct
    COMMENT 'NFHS-5: % of women 15+ with high BP. Proxy for ICU and TRAUMA demand.';

-- ---------------------------------------------------------------------------
-- Domain tag (already replayed in sql/tags/uc_metadata.sql)
-- ---------------------------------------------------------------------------
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  SET TAGS ('domain' = 'healthcare_supply');

-- ---------------------------------------------------------------------------
-- Smoke-test query (for the demo, not for production)
-- ---------------------------------------------------------------------------
-- SELECT
--   COUNT(*)                                         AS total_rows,
--   COUNT(h3_11)                                     AS with_h3_11,
--   COUNT(institutional_birth_5y_pct)                AS with_nfhs5,
--   ROUND(100.0 * COUNT(institutional_birth_5y_pct) / COUNT(*), 1) AS match_pct,
--   COUNT(DISTINCT h3_9)                             AS unique_h3_9_cells
-- FROM dais_hackathon_2026.silver.silver_facilities_geo;
-- Expected: 9,964 rows, 100% h3_11, ~63% NFHS-5, ~8,645 unique h3_9 cells.
