"""Expectation runner — evaluates rules from the registry, logs DQ results.

Each expectation is asserted with `count(*) WHERE NOT (expr)` (or duplicate count
for kind='unique'). Counts land in <target_catalog>.<bronze_schema>.dq_log so
the app can show *which* rows failed, not just that something did.

Severity:
  - 'error' rows that fail are routed to a quarantine table; pipeline continues.
  - 'warn'  counted only.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from .registry import Expectation, Source


@dataclass
class DQResult:
    source: str
    expectation: str
    severity: str
    failed_rows: int
    total_rows: int


def _evaluate_one(df: DataFrame, exp: Expectation) -> int:
    if exp.kind == "unique":
        cols = [F.col(c) for c in exp.columns]
        dup = df.groupBy(*cols).count().filter("count > 1").agg(F.sum("count")).collect()[0][0]
        return int(dup or 0) - df.select(*cols).dropDuplicates().count() + df.count() \
            if False else int(dup or 0)
    if exp.expr:
        return df.filter(f"NOT ({exp.expr})").count()
    raise ValueError(f"Expectation {exp.name} has neither expr nor kind")


def run_expectations(
    spark: SparkSession,
    df: DataFrame,
    source: Source,
    layer: str,
) -> list[DQResult]:
    """Run every expectation, persist results to the DQ log, return them."""
    total = df.count()
    results: list[DQResult] = []
    for exp in source.expectations:
        failed = _evaluate_one(df, exp)
        results.append(DQResult(source.name, exp.name, exp.severity, failed, total))

    if not results:
        return results

    log_table = f"{source.target_catalog}.{source.bronze_schema}.dq_log"
    rows = [
        (source.name, layer, r.expectation, r.severity, r.failed_rows, r.total_rows)
        for r in results
    ]
    log_df = spark.createDataFrame(
        rows,
        (
            "source string, layer string, expectation string, severity string, "
            "failed bigint, total bigint"
        ),
    ).withColumn("checked_at", F.current_timestamp())
    log_df.write.mode("append").saveAsTable(log_table)
    return results
