-- Domain tags on the canonical "supply" and "demand" tables.
--
-- The brief asks for tags on `facilities` and `nfhs_5_district_health_indicators`.
-- We tag those source tables AND the bronze/silver/gold derivatives so Genie,
-- Catalog Explorer, and lineage views surface the domain consistently
-- regardless of which layer the user lands on.
--
-- Tag values:
--   domain = healthcare_supply         — datasets describing care-providing
--                                        facilities (where care exists)
--   domain = public_health_demand      — datasets describing population-level
--                                        health needs (where care is needed)
--   domain = mixed_supply_demand       — gold tables that combine both
--
-- Note on portability: Databricks SQL does NOT support `ALTER TABLE IF EXISTS`.
-- Skip the gold/geo lines until the corresponding ETL task has materialized
-- the table (the runner script in scripts/setup_uc.sh handles this safely).

-- ---------------------------------------------------------------------------
-- 1. Source tables (psb_catalog) — read-only marketplace
-- ---------------------------------------------------------------------------
ALTER TABLE psb_catalog.virtue_foundation_dataset.facilities
  SET TAGS ('domain' = 'healthcare_supply');

ALTER TABLE psb_catalog.virtue_foundation_dataset.nfhs_5_district_health_indicators
  SET TAGS ('domain' = 'public_health_demand');

-- ---------------------------------------------------------------------------
-- 2. Bronze landing tables (verbatim copies)
-- ---------------------------------------------------------------------------
ALTER TABLE dais_hackathon_2026.bronze.bronze_facilities_raw
  SET TAGS ('domain' = 'healthcare_supply');

ALTER TABLE dais_hackathon_2026.bronze.bronze_nfhs5_raw
  SET TAGS ('domain' = 'public_health_demand');

-- ---------------------------------------------------------------------------
-- 3. Silver tables (cleaned + standardized)
-- ---------------------------------------------------------------------------
ALTER TABLE dais_hackathon_2026.silver.silver_facilities
  SET TAGS ('domain' = 'healthcare_supply');

ALTER TABLE dais_hackathon_2026.silver.silver_facility_capability_claims
  SET TAGS ('domain' = 'healthcare_supply');

ALTER TABLE dais_hackathon_2026.silver.silver_nfhs5_district
  SET TAGS ('domain' = 'public_health_demand');

-- silver_facilities_geo blends both — facility supply with NFHS-5 demand
-- attached. Tag as supply (the primary entity); demand columns surface via
-- column comments in the Genie semantic model.
-- Skip if silver_spatial_geocode hasn't run yet.
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  SET TAGS ('domain' = 'healthcare_supply');

-- ---------------------------------------------------------------------------
-- 4. Gold tables — both domains converge here
-- ---------------------------------------------------------------------------
ALTER TABLE dais_hackathon_2026.gold.h3_care_score
  SET TAGS ('domain' = 'mixed_supply_demand');

ALTER TABLE dais_hackathon_2026.gold.care_score_by_state
  SET TAGS ('domain' = 'mixed_supply_demand');

ALTER TABLE dais_hackathon_2026.gold.care_score_by_district
  SET TAGS ('domain' = 'mixed_supply_demand');

-- gold_medical_desert task deliverables — skip until that task has run.
ALTER TABLE dais_hackathon_2026.gold.medical_desert_h3
  SET TAGS ('domain' = 'mixed_supply_demand');

ALTER TABLE dais_hackathon_2026.gold.medical_desert_districts
  SET TAGS ('domain' = 'mixed_supply_demand');
