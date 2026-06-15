-- Lakebase schema for user-state persistence.
-- Notes, overrides, and saved planning scenarios.

CREATE TABLE IF NOT EXISTS lakebase.scenarios (
  id          BIGINT GENERATED ALWAYS AS IDENTITY,
  user        STRING NOT NULL,
  name        STRING NOT NULL,
  payload     STRING,           -- JSON: capability, geography, what-if adds
  created_at  TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS lakebase.overrides (
  id           BIGINT GENERATED ALWAYS AS IDENTITY,
  user         STRING NOT NULL,
  facility_id  STRING NOT NULL,
  capability   STRING NOT NULL,
  note         STRING,
  created_at   TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS lakebase.shortlists (
  id           BIGINT GENERATED ALWAYS AS IDENTITY,
  user         STRING NOT NULL,
  scenario_id  BIGINT,
  facility_id  STRING NOT NULL,
  rank         INT,
  created_at   TIMESTAMP NOT NULL
) USING DELTA;
