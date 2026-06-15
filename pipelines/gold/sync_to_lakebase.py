# Databricks notebook source
"""Gold → Lakebase sync.

Reads the three Gold care-score Delta tables and writes them into the
Databricks Lakebase (PostgreSQL-compatible managed DB).

Strategy: collect each table to pandas on the driver, then write via
psycopg2 using batch INSERT. This avoids spark.write.jdbc() which is
blocked on serverless compute.

Connection config from the 'lakebase' Databricks secret scope:
  lakebase/host      — Lakebase read-write hostname
  lakebase/port      — port (default 5432)
  lakebase/database  — database name

Authentication uses a short-lived OAuth token generated at runtime.
"""

# COMMAND ----------
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path.cwd().parents[1]))

# COMMAND ----------
import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402
from databricks.sdk import WorkspaceClient  # noqa: E402

from pipelines.common.config import fq_schema, get_catalog  # noqa: E402

# COMMAND ----------
# -- Config ---------------------------------------------------------------
SECRET_SCOPE  = "lakebase"
INSTANCE_NAME = "care-gap-lakebase"
BATCH_SIZE    = 10_000  # rows per INSERT batch

lakebase_host = dbutils.secrets.get(SECRET_SCOPE, "host")      # noqa: F821
lakebase_port = dbutils.secrets.get(SECRET_SCOPE, "port")      # noqa: F821
lakebase_db   = dbutils.secrets.get(SECRET_SCOPE, "database")  # noqa: F821

catalog     = get_catalog()
gold_schema = fq_schema("gold", catalog)

GOLD_TABLES = [
    (f"{gold_schema}.h3_care_score",          "h3_care_score"),
    (f"{gold_schema}.care_score_by_state",    "care_score_by_state"),
    (f"{gold_schema}.care_score_by_district", "care_score_by_district"),
]


# -- Helper ---------------------------------------------------------------
def _lakebase_conn(host, port, db):
    """Open a psycopg2 connection using a fresh OAuth token.

    Lakebase OAuth auth: username = Databricks user email, password = token.
    """
    wc = WorkspaceClient()
    username = wc.current_user.me().user_name
    cred = wc.database.generate_database_credential(
        instance_names=[INSTANCE_NAME],
        request_id=str(uuid.uuid4()),
    )
    return psycopg2.connect(
        host=host,
        port=int(port),
        dbname=db,
        user=username,
        password=cred.token,
        sslmode="require",
        connect_timeout=30,
    )


# COMMAND ----------
# -- Sync loop ------------------------------------------------------------
for delta_table, pg_table in GOLD_TABLES:
    print(f"[sync] reading {delta_table} ...")
    pdf = spark.read.table(delta_table).toPandas()  # noqa: F821
    row_count = len(pdf)
    print(f"[sync] {row_count:,} rows read — connecting to Lakebase ...")

    # Replace NaN/NaT with None so psycopg2 writes proper NULLs
    pdf = pdf.where(pdf.notna(), other=None)

    cols     = list(pdf.columns)
    col_sql  = ", ".join(f'"{c}"' for c in cols)
    rows     = [tuple(r) for r in pdf.itertuples(index=False, name=None)]

    conn = _lakebase_conn(lakebase_host, lakebase_port, lakebase_db)
    try:
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE {pg_table}")

        with conn.cursor() as cur:
            for i in range(0, len(rows), BATCH_SIZE):
                chunk = rows[i : i + BATCH_SIZE]
                psycopg2.extras.execute_values(
                    cur,
                    f'INSERT INTO {pg_table} ({col_sql}) VALUES %s',
                    chunk,
                )
                print(f"[sync]   {pg_table}: {min(i + BATCH_SIZE, row_count):,}/{row_count:,}")

        conn.commit()
        print(f"[sync] done: {pg_table}")
    finally:
        conn.close()

print("[sync] all Gold tables synced to Lakebase successfully.")
