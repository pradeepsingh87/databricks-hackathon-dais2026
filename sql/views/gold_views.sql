-- Convenience views consumed by the Streamlit app and the Genie space.

CREATE OR REPLACE VIEW gold.v_care_gap_by_state AS
SELECT
  capability,
  state,
  AVG(score)       AS avg_score,
  AVG(confidence)  AS avg_confidence,
  SUM(n_facilities) AS n_facilities,
  SUM(CASE WHEN data_deficient THEN 1 ELSE 0 END) AS n_data_deficient_cells
FROM gold.h3_care_score s
JOIN silver.facility_claims f USING (h3_cell)
GROUP BY capability, state;
