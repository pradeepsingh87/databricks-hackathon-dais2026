-- ===========================================================================
-- Unity Catalog metadata for the Care Gap Navigator
-- ===========================================================================
-- Programmatically applies the four metadata layers Genie One uses to
-- prioritise objects + render them well in the chat UI:
--
--   1. domain tags         — already in sql/tags/domain_tags.sql; replayed
--                            here so this file is self-contained.
--   2. table descriptions  — COMMENT ON TABLE for every materialized object.
--                            Genie reads these as the table-level semantic
--                            description and ranks tables by their presence.
--   3. column tags         — geography:h3_index on every H3 column so the
--                            optimizer's spatial-indexing path picks them
--                            up automatically (17x faster joins, per the
--                            DBSQL geospatial skill).
--   4. CERTIFIED property  — applied to every gold table so Genie One ranks
--                            them above silver/bronze in chat answers.
--
-- Skip patterns:
--   • Statements that target tables not yet built (medical_desert_*,
--     silver_facilities_geo) will fail with TABLE_OR_VIEW_NOT_FOUND. The
--     runner script handles that gracefully; if applying manually, ignore
--     those errors.
--   • `ALTER TABLE IF EXISTS` is NOT supported in Databricks SQL.

-- ---------------------------------------------------------------------------
-- 1. Table descriptions (Genie One reads these for ranking + display)
-- ---------------------------------------------------------------------------
COMMENT ON TABLE dais_hackathon_2026.bronze.bronze_facilities_raw IS
  'Raw landing table: 10,088 Indian healthcare facility records with capability claims, descriptions, equipment lists, and source URLs. Verbatim copy of psb_catalog.virtue_foundation_dataset.facilities. Use silver.silver_facilities or silver.silver_facility_capability_claims for verified analytics.';

COMMENT ON TABLE dais_hackathon_2026.bronze.bronze_pincode_directory IS
  'Raw landing: India Post pincode directory (~165k rows). Reference data used to enrich facilities with district + state from the postcode. Verbatim copy of psb_catalog.virtue_foundation_dataset.india_post_pincode_directory.';

COMMENT ON TABLE dais_hackathon_2026.bronze.bronze_nfhs5_raw IS
  'Raw landing: NFHS-5 district-level health indicators (706 districts, 120 indicators on maternal/child health, anaemia, hypertension, diabetes, vaccination coverage). Verbatim copy of psb_catalog.virtue_foundation_dataset.nfhs_5_district_health_indicators.';

COMMENT ON TABLE dais_hackathon_2026.silver.silver_facilities IS
  'Cleaned & geocoded facilities: 9,996 rows with canonical state (alias-resolved), pincode-derived district, H3 cells at resolutions 6/7/8, in-India bbox flag, and typed numeric columns (capacity, doctor counts). The lean entity table — every other silver/gold table joins back to this on facility_id.';

COMMENT ON TABLE dais_hackathon_2026.silver.silver_facility_capability_claims IS
  'Evidence-based facility trust signals: one row per (facility, capability) with rule-based evidence_strength (strong | partial | suspicious | none), claim_weight, and a citations JSON array of direct quotes from the underlying facility text. Powers the "cite the underlying text" hackathon obligation.';

COMMENT ON TABLE dais_hackathon_2026.silver.silver_pincode_directory IS
  'Cleaned pincode → (district, state, lat/lng) reference. Used by the silver runner to enrich facilities and by Gold for spatial fallback joins.';

COMMENT ON TABLE dais_hackathon_2026.silver.silver_nfhs5_district IS
  'District-level disease burden: 706 districts × 120 NFHS-5 health indicators (institutional-birth %, anaemia %, hypertension %, vaccination coverage, etc.). The demand denominator for the Gold medical-desert scorer.';

COMMENT ON TABLE dais_hackathon_2026.silver.silver_facilities_geo IS
  'Spatial fact table: silver_facilities augmented with Mosaic ST_Point geometry, H3 cells at resolutions 9/10/11 (neighborhood/block/building grain), and the matching NFHS-5 demand row for the facility''s district. Powers high-fidelity geospatial Gold queries.';

COMMENT ON TABLE dais_hackathon_2026.gold.h3_care_score IS
  'Trust-weighted care score per H3 cell × capability. Score = supply quality (0..1). Confidence = how much we trust that score (0..1). evidence_state ∈ {data_deficient, care_gap, covered}. The map''s primary source. Always show confidence alongside score.';

COMMENT ON TABLE dais_hackathon_2026.gold.care_score_by_state IS
  'State-level rollup of h3_care_score. One row per (capability, state) with average score, average confidence, total facilities, and count of data-deficient cells. Use for top-line "where are gaps the worst" questions.';

COMMENT ON TABLE dais_hackathon_2026.gold.care_score_by_district IS
  'District-level rollup of h3_care_score. One row per (capability, state, district). The granularity at which planners typically allocate resources; pairs naturally with NFHS-5 indicators on silver_nfhs5_district.';

COMMENT ON TABLE dais_hackathon_2026.gold.medical_desert_h3 IS
  'Medical desert flagging per H3 cell × capability. Combines verified supply (from silver_facility_capability_claims) with NFHS-5 demand (from silver_facilities_geo) to compute gap_score = max(0, 1 - state_relative_supply) × demand_score. desert_flag = TRUE when gap_score > 0.6 AND confidence_label is not "suspicious". Carries top_citations from underlying text.';

COMMENT ON TABLE dais_hackathon_2026.gold.medical_desert_districts IS
  'Medical desert flagging at district grain. Same gap_score formula as medical_desert_h3 but aggregated to (capability, state, district) for the Performance page''s risk stratification.';

-- ---------------------------------------------------------------------------
-- 2. Domain tags (replay — already applied earlier; idempotent)
-- ---------------------------------------------------------------------------
ALTER TABLE psb_catalog.virtue_foundation_dataset.facilities
  SET TAGS ('domain' = 'healthcare_supply');
ALTER TABLE psb_catalog.virtue_foundation_dataset.nfhs_5_district_health_indicators
  SET TAGS ('domain' = 'public_health_demand');

ALTER TABLE dais_hackathon_2026.bronze.bronze_facilities_raw
  SET TAGS ('domain' = 'healthcare_supply');
ALTER TABLE dais_hackathon_2026.bronze.bronze_nfhs5_raw
  SET TAGS ('domain' = 'public_health_demand');
ALTER TABLE dais_hackathon_2026.silver.silver_facilities
  SET TAGS ('domain' = 'healthcare_supply');
ALTER TABLE dais_hackathon_2026.silver.silver_facility_capability_claims
  SET TAGS ('domain' = 'healthcare_supply');
ALTER TABLE dais_hackathon_2026.silver.silver_nfhs5_district
  SET TAGS ('domain' = 'public_health_demand');
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  SET TAGS ('domain' = 'healthcare_supply');
ALTER TABLE dais_hackathon_2026.gold.h3_care_score
  SET TAGS ('domain' = 'mixed_supply_demand');
ALTER TABLE dais_hackathon_2026.gold.care_score_by_state
  SET TAGS ('domain' = 'mixed_supply_demand');
ALTER TABLE dais_hackathon_2026.gold.care_score_by_district
  SET TAGS ('domain' = 'mixed_supply_demand');
ALTER TABLE dais_hackathon_2026.gold.medical_desert_h3
  SET TAGS ('domain' = 'mixed_supply_demand');
ALTER TABLE dais_hackathon_2026.gold.medical_desert_districts
  SET TAGS ('domain' = 'mixed_supply_demand');

-- ---------------------------------------------------------------------------
-- 3. H3 column tags (geography:h3_index) — every H3 column across the
--    medallion stack. Mosaic & DBSQL spatial-indexing optimizer use this tag
--    to route H3-keyed joins through the optimised spatial-join physical
--    plan (~17x faster than a plain string-equality hash join).
-- ---------------------------------------------------------------------------
-- silver_facilities (resolutions 6/7/8 from the metadata-driven runner)
ALTER TABLE dais_hackathon_2026.silver.silver_facilities
  ALTER COLUMN h3_6 SET TAGS ('geography' = 'h3_index');
ALTER TABLE dais_hackathon_2026.silver.silver_facilities
  ALTER COLUMN h3_7 SET TAGS ('geography' = 'h3_index');
ALTER TABLE dais_hackathon_2026.silver.silver_facilities
  ALTER COLUMN h3_8 SET TAGS ('geography' = 'h3_index');

-- silver_facility_capability_claims carries h3 cells too
ALTER TABLE dais_hackathon_2026.silver.silver_facility_capability_claims
  ALTER COLUMN h3_6 SET TAGS ('geography' = 'h3_index');
ALTER TABLE dais_hackathon_2026.silver.silver_facility_capability_claims
  ALTER COLUMN h3_7 SET TAGS ('geography' = 'h3_index');
ALTER TABLE dais_hackathon_2026.silver.silver_facility_capability_claims
  ALTER COLUMN h3_8 SET TAGS ('geography' = 'h3_index');

-- silver_facilities_geo (resolutions 9/10/11 from the Mosaic-based notebook)
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN h3_9  SET TAGS ('geography' = 'h3_index');
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN h3_10 SET TAGS ('geography' = 'h3_index');
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN h3_11 SET TAGS ('geography' = 'h3_index');

-- gold tables expose h3_cell as the join column
ALTER TABLE dais_hackathon_2026.gold.h3_care_score
  ALTER COLUMN h3_cell SET TAGS ('geography' = 'h3_index');
ALTER TABLE dais_hackathon_2026.gold.medical_desert_h3
  ALTER COLUMN h3_cell SET TAGS ('geography' = 'h3_index');

-- ---------------------------------------------------------------------------
-- 4. CERTIFIED property on every Gold table
--    Genie One ranks certified objects above non-certified in chat answers
--    (per May/June 2026 release notes). Applied via TBLPROPERTIES because
--    Databricks does not yet have a first-class CERTIFY API; the property is
--    what surfaces the badge in Catalog Explorer and the Genie object picker.
-- ---------------------------------------------------------------------------
ALTER TABLE dais_hackathon_2026.gold.h3_care_score
  SET TBLPROPERTIES (
    'certified' = 'true',
    'data_quality_tier' = 'gold',
    'certified_by' = 'care-gap-navigator'
  );
ALTER TABLE dais_hackathon_2026.gold.care_score_by_state
  SET TBLPROPERTIES (
    'certified' = 'true',
    'data_quality_tier' = 'gold',
    'certified_by' = 'care-gap-navigator'
  );
ALTER TABLE dais_hackathon_2026.gold.care_score_by_district
  SET TBLPROPERTIES (
    'certified' = 'true',
    'data_quality_tier' = 'gold',
    'certified_by' = 'care-gap-navigator'
  );
ALTER TABLE dais_hackathon_2026.gold.medical_desert_h3
  SET TBLPROPERTIES (
    'certified' = 'true',
    'data_quality_tier' = 'gold',
    'certified_by' = 'care-gap-navigator'
  );
ALTER TABLE dais_hackathon_2026.gold.medical_desert_districts
  SET TBLPROPERTIES (
    'certified' = 'true',
    'data_quality_tier' = 'gold',
    'certified_by' = 'care-gap-navigator'
  );

-- Mirror the certified status as a table-level tag too — a few Genie One
-- ranking heuristics check tags rather than properties, so this is belt-and-
-- braces. Cheap to keep both.
ALTER TABLE dais_hackathon_2026.gold.h3_care_score
  SET TAGS ('certified' = 'true');
ALTER TABLE dais_hackathon_2026.gold.care_score_by_state
  SET TAGS ('certified' = 'true');
ALTER TABLE dais_hackathon_2026.gold.care_score_by_district
  SET TAGS ('certified' = 'true');
ALTER TABLE dais_hackathon_2026.gold.medical_desert_h3
  SET TAGS ('certified' = 'true');
ALTER TABLE dais_hackathon_2026.gold.medical_desert_districts
  SET TAGS ('certified' = 'true');
