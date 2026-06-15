-- Convenience views consumed by ad hoc SQL and Genie.
-- Replace __CATALOG__ before execution.

CREATE OR REPLACE VIEW __CATALOG__.gold.v_care_gap_by_state AS
SELECT
  capability,
  state,
  score,
  confidence,
  n_facilities,
  n_data_deficient_cells
FROM __CATALOG__.gold.care_score_by_state;

CREATE OR REPLACE VIEW __CATALOG__.gold.v_care_gap_by_district AS
SELECT
  capability,
  state,
  district,
  score,
  confidence,
  n_facilities,
  n_data_deficient_cells
FROM __CATALOG__.gold.care_score_by_district;
