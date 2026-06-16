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

-- NACHC-style Root Cause Analysis records. Each row categorises one cell or
-- district as a Data Gap, Service Delivery Gap, or Engagement Gap, with an
-- optional planner note. Multi-team collaboration: rows are user-tagged but
-- visible workspace-wide for cross-team handoffs.
CREATE TABLE IF NOT EXISTS __CATALOG__.lakebase.gap_categorizations (
  id            BIGINT GENERATED ALWAYS AS IDENTITY,
  user_name     STRING NOT NULL,
  capability    STRING NOT NULL,
  state         STRING,
  district      STRING,
  h3_cell       STRING,                  -- nullable when categorising at district grain
  category      STRING NOT NULL,         -- 'data' | 'service' | 'engagement'
  severity      STRING,                  -- 'low' | 'medium' | 'high'
  note          STRING,
  created_at    TIMESTAMP NOT NULL
) USING DELTA;

-- Filter-state bookmarks for multi-team collaboration. A bookmark is a JSON
-- snapshot of the current sidebar filters + selected cell; teammates can
-- load a bookmark to land on the same view their colleague was looking at.
CREATE TABLE IF NOT EXISTS __CATALOG__.lakebase.bookmarks (
  id            BIGINT GENERATED ALWAYS AS IDENTITY,
  user_name     STRING NOT NULL,
  name          STRING NOT NULL,
  filters_json  STRING,
  -- shared: TRUE = visible to all teammates. Apps pass an explicit value
  -- (no DEFAULT — that requires the delta.feature.allowColumnDefaults flag).
  shared        BOOLEAN,
  created_at    TIMESTAMP NOT NULL
) USING DELTA;
