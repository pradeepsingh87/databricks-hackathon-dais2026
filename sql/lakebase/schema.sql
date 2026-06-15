-- Lakebase schema: PostgreSQL-compatible DDL for Databricks Lakebase.
-- Run via: psql "$LAKEBASE_CONNECTION_STRING" -f sql/lakebase/schema.sql

-- -----------------------------------------------------------------------
-- User-state persistence tables
-- -----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS scenarios (
  id          BIGSERIAL PRIMARY KEY,
  "user"      TEXT NOT NULL,
  name        TEXT NOT NULL,
  payload     TEXT,
  created_at  TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS overrides (
  id           BIGSERIAL PRIMARY KEY,
  "user"       TEXT NOT NULL,
  facility_id  TEXT NOT NULL,
  capability   TEXT NOT NULL,
  note         TEXT,
  created_at   TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS shortlists (
  id           BIGSERIAL PRIMARY KEY,
  "user"       TEXT NOT NULL,
  scenario_id  BIGINT,
  facility_id  TEXT NOT NULL,
  rank         INTEGER,
  created_at   TIMESTAMP NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------
-- Gold mirror tables — populated by pipelines/gold/sync_to_lakebase.py
-- Provide low-latency reads for the Databricks App without hitting the
-- SQL warehouse on every page load.
-- -----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS h3_care_score (
  capability      TEXT    NOT NULL,
  state           TEXT,
  district        TEXT,
  h3_resolution   INTEGER NOT NULL,
  h3_cell         TEXT    NOT NULL,
  n_facilities    INTEGER,
  score           NUMERIC(6, 4),
  confidence      NUMERIC(6, 4),
  data_deficient  BOOLEAN,
  evidence_state  TEXT
);

CREATE INDEX IF NOT EXISTS idx_h3_care_score_cap_res
  ON h3_care_score (capability, h3_resolution);

CREATE INDEX IF NOT EXISTS idx_h3_care_score_state
  ON h3_care_score (state);

CREATE INDEX IF NOT EXISTS idx_h3_care_score_cell
  ON h3_care_score (h3_cell);

CREATE TABLE IF NOT EXISTS care_score_by_state (
  capability            TEXT    NOT NULL,
  state                 TEXT    NOT NULL,
  score                 NUMERIC(6, 4),
  confidence            NUMERIC(6, 4),
  n_facilities          INTEGER,
  n_data_deficient_cells INTEGER
);

CREATE INDEX IF NOT EXISTS idx_care_score_state_cap
  ON care_score_by_state (capability, state);

CREATE TABLE IF NOT EXISTS care_score_by_district (
  capability            TEXT    NOT NULL,
  state                 TEXT    NOT NULL,
  district              TEXT,
  score                 NUMERIC(6, 4),
  confidence            NUMERIC(6, 4),
  n_facilities          INTEGER,
  n_data_deficient_cells INTEGER
);

CREATE INDEX IF NOT EXISTS idx_care_score_district_cap
  ON care_score_by_district (capability, state);
