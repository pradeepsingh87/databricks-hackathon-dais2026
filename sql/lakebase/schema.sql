-- Lakebase schema for user-state persistence.
-- Replace __CATALOG__ before execution.
--
-- NOTE: column is `user_name`, not `user`. `user` is a reserved word in
-- Spark SQL (it resolves to the user() function), and unquoted references
-- in INSERT/SELECT statements fail at parse time.

CREATE TABLE IF NOT EXISTS __CATALOG__.lakebase.scenarios (
  id          BIGINT GENERATED ALWAYS AS IDENTITY,
  user_name   STRING NOT NULL,
  name        STRING NOT NULL,
  payload     STRING,
  created_at  TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS __CATALOG__.lakebase.overrides (
  id           BIGINT GENERATED ALWAYS AS IDENTITY,
  user_name    STRING NOT NULL,
  facility_id  STRING NOT NULL,
  capability   STRING NOT NULL,
  note         STRING,
  created_at   TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS __CATALOG__.lakebase.shortlists (
  id           BIGINT GENERATED ALWAYS AS IDENTITY,
  user_name    STRING NOT NULL,
  scenario_id  BIGINT,
  facility_id  STRING NOT NULL,
  rank         INT,
  created_at   TIMESTAMP NOT NULL
) USING DELTA;
