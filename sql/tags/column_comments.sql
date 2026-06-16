-- User-friendly column descriptions on Silver + Gold.
--
-- Databricks doesn't have a separate "display name" attribute, so we use
-- column COMMENTs — Genie reads them as the semantic layer when it answers
-- questions, and the Catalog Explorer surfaces them prominently. These are
-- the columns that show up in Genie answers and would confuse non-technical
-- planners ("h3_9" means nothing; "Hexagonal Spatial ID (~174 m)" does).
--
-- Self-explanatory columns (state, district, name, city, latitude, etc.)
-- are intentionally not commented — Genie handles those fine without a hint.

-- ===========================================================================
-- Silver: silver_facilities
-- ===========================================================================
ALTER TABLE dais_hackathon_2026.silver.silver_facilities
  ALTER COLUMN h3_6 COMMENT 'Hexagonal Spatial ID at H3 resolution 6 (~36 km edge — state grain).';
ALTER TABLE dais_hackathon_2026.silver.silver_facilities
  ALTER COLUMN h3_7 COMMENT 'Hexagonal Spatial ID at H3 resolution 7 (~5 km edge — district grain).';
ALTER TABLE dais_hackathon_2026.silver.silver_facilities
  ALTER COLUMN h3_8 COMMENT 'Hexagonal Spatial ID at H3 resolution 8 (~0.7 km edge — city block grain).';
ALTER TABLE dais_hackathon_2026.silver.silver_facilities
  ALTER COLUMN in_india_bbox COMMENT 'TRUE when the facility coordinates fall inside the India bounding box. FALSE flags suspect lat/lng (e.g. a Kerala hospital pinned in the North Atlantic).';
ALTER TABLE dais_hackathon_2026.silver.silver_facilities
  ALTER COLUMN state_from_pincode COMMENT 'State derived from the facility pincode via the India Post pincode directory. Disagreement with the facility-reported state is a low-confidence signal.';

-- ===========================================================================
-- Silver: silver_facility_capability_claims  (per (facility, capability) row)
-- ===========================================================================
ALTER TABLE dais_hackathon_2026.silver.silver_facility_capability_claims
  ALTER COLUMN evidence_strength COMMENT 'Trust label assigned by the rule-based extractor. strong = capability claim supported by structured fields + free text. partial = some support. suspicious = claim made but text evidence is weak or contradictory. none = no claim found.';
ALTER TABLE dais_hackathon_2026.silver.silver_facility_capability_claims
  ALTER COLUMN claim_weight COMMENT 'Numeric weight derived from evidence_strength. strong = 1.0, partial = 0.5, suspicious = 0.1, none = 0.0. Used by the Gold scorer to compute verified supply.';
ALTER TABLE dais_hackathon_2026.silver.silver_facility_capability_claims
  ALTER COLUMN has_source_url COMMENT 'TRUE when at least one supporting citation has a source URL — extra trust signal.';
ALTER TABLE dais_hackathon_2026.silver.silver_facility_capability_claims
  ALTER COLUMN citations COMMENT 'JSON array of {text, source_field, source_url} — direct quotes from the facility text that justify the evidence_strength label. Powers the "cite the underlying text" hackathon requirement.';

-- ===========================================================================
-- Silver: silver_nfhs5_district  (only the indicators the scorer uses)
-- ===========================================================================
ALTER TABLE dais_hackathon_2026.silver.silver_nfhs5_district
  ALTER COLUMN institutional_birth_5y_pct COMMENT 'NFHS-5: % of births in the last 5 years that took place in a health facility. Low values indicate high MATERNITY demand (more births at home).';
ALTER TABLE dais_hackathon_2026.silver.silver_nfhs5_district
  ALTER COLUMN child_u5_who_are_stunted_height_for_age_18_pct COMMENT 'NFHS-5: % of children under 5 who are stunted (low height-for-age). High values are a systemic child-health signal — proxy for NICU demand.';
ALTER TABLE dais_hackathon_2026.silver.silver_nfhs5_district
  ALTER COLUMN hh_member_covered_health_insurance_pct COMMENT 'NFHS-5: % of households with at least one member covered by health insurance. Low values mean patients defer care until emergencies — proxy for EMERGENCY demand.';
ALTER TABLE dais_hackathon_2026.silver.silver_nfhs5_district
  ALTER COLUMN women_age_30_49_years_ever_undergone_a_cervical_screen_pct COMMENT 'NFHS-5: % of women 30-49 ever screened for cervical cancer. Low values are a leading indicator of late-stage cancer presentations — proxy for ONCOLOGY demand.';
ALTER TABLE dais_hackathon_2026.silver.silver_nfhs5_district
  ALTER COLUMN w15_plus_with_high_bp_sys_gte_140_mmhg_and_or_dia_gte_90_mm_pct COMMENT 'NFHS-5: % of women 15+ with systolic BP >= 140 or diastolic >= 90. High values correlate with stroke/CVD presentations — proxy for ICU and TRAUMA demand.';

-- ===========================================================================
-- Silver: silver_facilities_geo  (Mosaic spatial fact)
-- ===========================================================================
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN geom COMMENT 'ST_Point(longitude, latitude) — Mosaic geometry type used for ST_Distance and other spatial predicates.';
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN h3_9 COMMENT 'Hexagonal Spatial ID at H3 resolution 9 (~174 m edge — neighborhood grain). Generated by Mosaic grid_pointascellid.';
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN h3_10 COMMENT 'Hexagonal Spatial ID at H3 resolution 10 (~65 m edge — city block grain). Generated by Mosaic grid_pointascellid.';
ALTER TABLE dais_hackathon_2026.silver.silver_facilities_geo
  ALTER COLUMN h3_11 COMMENT 'Hexagonal Spatial ID at H3 resolution 11 (~25 m edge — building grain). Generated by Mosaic grid_pointascellid.';

-- ===========================================================================
-- Gold: h3_care_score  (per (capability, h3 cell))
-- ===========================================================================
ALTER TABLE dais_hackathon_2026.gold.h3_care_score
  ALTER COLUMN h3_resolution COMMENT 'H3 resolution: 6 ≈ 36 km, 7 ≈ 5 km, 8 ≈ 0.7 km, 9 ≈ 174 m. Filter on this when querying a single zoom level.';
ALTER TABLE dais_hackathon_2026.gold.h3_care_score
  ALTER COLUMN h3_cell COMMENT 'Hexagonal Spatial ID at the corresponding h3_resolution.';
ALTER TABLE dais_hackathon_2026.gold.h3_care_score
  ALTER COLUMN n_facilities COMMENT 'Number of distinct facilities reporting capability claims in this cell.';
ALTER TABLE dais_hackathon_2026.gold.h3_care_score
  ALTER COLUMN score COMMENT 'Care Score (0..1). 0 = no verified care, 1 = well-served. Always interpret alongside confidence.';
ALTER TABLE dais_hackathon_2026.gold.h3_care_score
  ALTER COLUMN confidence COMMENT 'Evidence Confidence (0..1). 0 = data-poor, 1 = strong, multi-source evidence. A high score with low confidence is meaningfully different from a high score with high confidence.';
ALTER TABLE dais_hackathon_2026.gold.h3_care_score
  ALTER COLUMN data_deficient COMMENT 'TRUE when confidence is too low to call the score either way. Distinguishes "data-deficient" cells from "proven absent" / "well-served".';
ALTER TABLE dais_hackathon_2026.gold.h3_care_score
  ALTER COLUMN evidence_state COMMENT 'Categorical: data_deficient | care_gap | covered. The "what does this region look like?" headline label.';

-- ===========================================================================
-- Gold: care_score_by_state, care_score_by_district  (regional rollups)
-- ===========================================================================
ALTER TABLE dais_hackathon_2026.gold.care_score_by_state
  ALTER COLUMN score COMMENT 'Average Care Score across H3 cells in the state (0..1).';
ALTER TABLE dais_hackathon_2026.gold.care_score_by_state
  ALTER COLUMN confidence COMMENT 'Average Evidence Confidence across H3 cells in the state (0..1).';
ALTER TABLE dais_hackathon_2026.gold.care_score_by_state
  ALTER COLUMN n_data_deficient_cells COMMENT 'Number of H3 cells in the state where confidence was too low to trust the score. A high count signals a data quality problem in that region.';

ALTER TABLE dais_hackathon_2026.gold.care_score_by_district
  ALTER COLUMN score COMMENT 'Average Care Score across H3 cells in the district (0..1).';
ALTER TABLE dais_hackathon_2026.gold.care_score_by_district
  ALTER COLUMN confidence COMMENT 'Average Evidence Confidence across H3 cells in the district (0..1).';
ALTER TABLE dais_hackathon_2026.gold.care_score_by_district
  ALTER COLUMN n_data_deficient_cells COMMENT 'Number of H3 cells in the district where confidence was too low to trust the score.';

-- ===========================================================================
-- Gold: medical_desert_h3, medical_desert_districts  (gap scorer)
-- These tables are produced by the gold_medical_desert task; skip lines until
-- the task has run.
-- ===========================================================================
ALTER TABLE dais_hackathon_2026.gold.medical_desert_h3
  ALTER COLUMN verified_supply COMMENT 'Sum of claim_weight across non-suspicious facility claims in this cell. Suspicious claims are EXCLUDED — a suspicious claim is a flag, not service.';
ALTER TABLE dais_hackathon_2026.gold.medical_desert_h3
  ALTER COLUMN supply_score COMMENT 'verified_supply normalised against the maximum verified supply in the same state. State-relative so rural cells are not penalised by a nationwide denominator.';
ALTER TABLE dais_hackathon_2026.gold.medical_desert_h3
  ALTER COLUMN demand_score COMMENT 'NFHS-5 indicator transformed to 0..1. 1 = high demand. Polarity per config/capability_demand.yml.';
ALTER TABLE dais_hackathon_2026.gold.medical_desert_h3
  ALTER COLUMN gap_score COMMENT 'Medical Desert Gap Score: max(0, 1 - supply_score) * demand_score. Higher = bigger desert. NULL when NFHS-5 demand is unknown for the district.';
ALTER TABLE dais_hackathon_2026.gold.medical_desert_h3
  ALTER COLUMN confidence_label COMMENT 'Dominant evidence label across facilities in the cell: strong | partial | suspicious | none. Drives the trust badge in the App.';
ALTER TABLE dais_hackathon_2026.gold.medical_desert_h3
  ALTER COLUMN desert_flag COMMENT 'TRUE when gap_score > 0.6 AND confidence_label is not "suspicious". The headline "this region is a Medical Desert" boolean.';
ALTER TABLE dais_hackathon_2026.gold.medical_desert_h3
  ALTER COLUMN top_citations COMMENT 'Up to 3 sample facility excerpts (name, city, evidence_strength, citations JSON) supporting this gap score. Carries the underlying text into Genie answers.';
ALTER TABLE dais_hackathon_2026.gold.medical_desert_h3
  ALTER COLUMN score_run_id COMMENT 'UUID per Gold run. Saved scenarios reference this so they do not silently change meaning when Gold is re-run.';
ALTER TABLE dais_hackathon_2026.gold.medical_desert_h3
  ALTER COLUMN as_of_ts COMMENT 'Timestamp of the Gold run that produced this row.';

-- (medical_desert_districts mirrors the same columns; same comments apply.)
ALTER TABLE dais_hackathon_2026.gold.medical_desert_districts
  ALTER COLUMN verified_supply COMMENT 'Sum of claim_weight across non-suspicious facility claims in this district.';
ALTER TABLE dais_hackathon_2026.gold.medical_desert_districts
  ALTER COLUMN gap_score COMMENT 'Medical Desert Gap Score: max(0, 1 - supply_score) * demand_score. Higher = bigger desert.';
ALTER TABLE dais_hackathon_2026.gold.medical_desert_districts
  ALTER COLUMN confidence_label COMMENT 'Dominant evidence label across facilities in the district: strong | partial | suspicious | none.';
ALTER TABLE dais_hackathon_2026.gold.medical_desert_districts
  ALTER COLUMN desert_flag COMMENT 'TRUE when gap_score > 0.6 AND confidence_label is not "suspicious".';
ALTER TABLE dais_hackathon_2026.gold.medical_desert_districts
  ALTER COLUMN top_citations COMMENT 'Up to 5 sample facility excerpts supporting this gap score — carries underlying text into Genie answers.';
