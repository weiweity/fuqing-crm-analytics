"""Run Sprint N+2 10-scenario benchmark against Trino and/or DuckDB."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

import duckdb

from scripts.trino_poc.trino_client import TrinoRestClient


ORDERS_TABLE = "orders"
TRINO_ORDERS_TABLE = "hive.crm.orders"

VALID_ORDER = "o.is_goujinjin = FALSE AND o.order_status != '交易关闭' AND o.is_refund = FALSE"
CURRENT_START = "TIMESTAMP '2026-01-01 00:00:00'"
CURRENT_END = "TIMESTAMP '2027-01-01 00:00:00'"
PREV_START = "TIMESTAMP '2025-01-01 00:00:00'"
PREV_END = "TIMESTAMP '2026-01-01 00:00:00'"
REFERENCE_DATE = "DATE '2026-12-31'"


@dataclass(frozen=True)
class QueryScenario:
    scenario_id: str
    title: str
    description: str
    sql: str


@dataclass(frozen=True)
class ScenarioBenchmark:
    engine: str
    scenario_id: str
    title: str
    runs: int
    rows: int
    p50_s: float
    p95_s: float
    p99_s: float
    timings_s: list[float]


class QueryEngine(Protocol):
    name: str

    def execute(self, sql: str) -> list[list]:
        ...


class DuckDbEngine:
    name = "duckdb"

    def __init__(self, db_path: str, table: str = ORDERS_TABLE) -> None:
        self.conn = duckdb.connect(db_path, read_only=True)
        self.table = table

    def execute(self, sql: str) -> list[list]:
        return self.conn.execute(sql.replace(TRINO_ORDERS_TABLE, self.table)).fetchall()

    def close(self) -> None:
        self.conn.close()


class TrinoEngine:
    name = "trino"

    def __init__(self, base_url: str) -> None:
        self.client = TrinoRestClient(base_url=base_url)

    def execute(self, sql: str) -> list[list]:
        return self.client.execute(sql).rows


SCENARIOS: tuple[QueryScenario, ...] = (
    QueryScenario(
        "s01_monthly_gmv",
        "GMV 月度聚合",
        "12 月 GSV / orders / customers",
        f"""
SELECT
    o.year,
    o.month,
    ROUND(SUM(o.actual_amount), 2) AS gsv,
    COUNT(DISTINCT o.order_id) AS orders,
    COUNT(DISTINCT o.user_id) AS customers
FROM {TRINO_ORDERS_TABLE} o
WHERE o.pay_time >= {CURRENT_START}
  AND o.pay_time < {CURRENT_END}
  AND {VALID_ORDER}
GROUP BY o.year, o.month
ORDER BY o.year, o.month
""",
    ),
    QueryScenario(
        "s02_rfm_lifecycle_value_potential",
        "RFM 生命周期×价值×潜力",
        "lifecycle_stage × value_tier × potential_tier",
        f"""
WITH user_metrics AS (
    SELECT
        o.user_id,
        MIN(CAST(o.pay_time AS DATE)) AS first_active,
        MAX(CAST(o.pay_time AS DATE)) AS last_active,
        COUNT(DISTINCT o.order_id) AS order_count,
        SUM(o.actual_amount) AS gsv_sum,
        SUM(CASE WHEN o.pay_time >= {CURRENT_START} AND o.pay_time < {CURRENT_END} THEN o.actual_amount ELSE 0 END)
          - SUM(CASE WHEN o.pay_time >= {PREV_START} AND o.pay_time < {PREV_END} THEN o.actual_amount ELSE 0 END) AS gsv_growth
    FROM {TRINO_ORDERS_TABLE} o
    WHERE {VALID_ORDER}
    GROUP BY o.user_id
),
segmented AS (
    SELECT
        CASE
            WHEN date_diff('day', first_active, {REFERENCE_DATE}) < 30 THEN '新客'
            WHEN date_diff('day', last_active, {REFERENCE_DATE}) < 30 THEN '活跃客'
            WHEN date_diff('day', last_active, {REFERENCE_DATE}) <= 180 THEN '沉睡客'
            ELSE '流失客'
        END AS lifecycle_stage,
        CASE
            WHEN gsv_sum >= 5000 OR order_count >= 10 THEN '高价值'
            WHEN gsv_sum >= 1000 THEN '中价值'
            ELSE '低价值'
        END AS value_tier,
        CASE
            WHEN date_diff('day', last_active, {REFERENCE_DATE}) < 30 AND gsv_growth > 0 THEN '高潜力'
            WHEN date_diff('day', last_active, {REFERENCE_DATE}) < 30 THEN '中潜力'
            ELSE '低潜力'
        END AS potential_tier,
        gsv_sum
    FROM user_metrics
)
SELECT lifecycle_stage, value_tier, potential_tier, COUNT(*) AS users, ROUND(SUM(gsv_sum), 2) AS gsv
FROM segmented
GROUP BY lifecycle_stage, value_tier, potential_tier
ORDER BY gsv DESC
""",
    ),
    QueryScenario(
        "s03_channel_distribution_yoy",
        "Channel 渠道分布",
        "channel + count + sum + YOY",
        f"""
WITH channel_year AS (
    SELECT
        o.channel,
        CASE WHEN o.pay_time >= {CURRENT_START} AND o.pay_time < {CURRENT_END} THEN 'current' ELSE 'previous' END AS period,
        SUM(o.actual_amount) AS gsv,
        COUNT(DISTINCT o.order_id) AS orders,
        COUNT(DISTINCT o.user_id) AS customers
    FROM {TRINO_ORDERS_TABLE} o
    WHERE o.pay_time >= {PREV_START}
      AND o.pay_time < {CURRENT_END}
      AND {VALID_ORDER}
    GROUP BY o.channel, CASE WHEN o.pay_time >= {CURRENT_START} AND o.pay_time < {CURRENT_END} THEN 'current' ELSE 'previous' END
)
SELECT
    channel,
    SUM(CASE WHEN period = 'current' THEN gsv ELSE 0 END) AS current_gsv,
    SUM(CASE WHEN period = 'previous' THEN gsv ELSE 0 END) AS previous_gsv,
    SUM(CASE WHEN period = 'current' THEN orders ELSE 0 END) AS current_orders,
    SUM(CASE WHEN period = 'current' THEN customers ELSE 0 END) AS current_customers
FROM channel_year
GROUP BY channel
ORDER BY current_gsv DESC
""",
    ),
    QueryScenario(
        "s04_category_transition",
        "品类流转",
        "cross-period spu_category transition",
        f"""
WITH prev_ranked AS (
    SELECT
        o.user_id,
        o.spu_category,
        ROW_NUMBER() OVER (PARTITION BY o.user_id ORDER BY SUM(o.actual_amount) DESC) AS rn
    FROM {TRINO_ORDERS_TABLE} o
    WHERE o.pay_time >= {PREV_START}
      AND o.pay_time < {PREV_END}
      AND {VALID_ORDER}
    GROUP BY o.user_id, o.spu_category
),
curr_ranked AS (
    SELECT
        o.user_id,
        o.spu_category,
        ROW_NUMBER() OVER (PARTITION BY o.user_id ORDER BY SUM(o.actual_amount) DESC) AS rn
    FROM {TRINO_ORDERS_TABLE} o
    WHERE o.pay_time >= {CURRENT_START}
      AND o.pay_time < {CURRENT_END}
      AND {VALID_ORDER}
    GROUP BY o.user_id, o.spu_category
)
SELECT
    p.spu_category AS previous_category,
    c.spu_category AS current_category,
    COUNT(*) AS users
FROM prev_ranked p
JOIN curr_ranked c ON p.user_id = c.user_id
WHERE p.rn = 1 AND c.rn = 1
GROUP BY p.spu_category, c.spu_category
ORDER BY users DESC
LIMIT 50
""",
    ),
    QueryScenario(
        "s05_refund_rate",
        "退款率分析",
        "is_refund + refund_rate + refund_gsv",
        f"""
SELECT
    o.year,
    o.month,
    COUNT(DISTINCT o.order_id) AS orders,
    ROUND(SUM(o.refund_amount), 2) AS refund_gsv,
    ROUND(SUM(o.amount), 2) AS gross_gmv,
    ROUND(SUM(o.refund_amount) / NULLIF(SUM(o.amount), 0), 4) AS refund_rate
FROM {TRINO_ORDERS_TABLE} o
WHERE o.pay_time >= {CURRENT_START}
  AND o.pay_time < {CURRENT_END}
  AND o.is_goujinjin = FALSE
  AND o.order_status != '交易关闭'
GROUP BY o.year, o.month
ORDER BY o.year, o.month
""",
    ),
    QueryScenario(
        "s06_member_repurchase",
        "老客复购率",
        "member + repurchase_users / total_users × GSV",
        f"""
WITH user_period AS (
    SELECT
        o.user_id,
        SUM(CASE WHEN o.is_member THEN 1 ELSE 0 END) > 0 AS is_member,
        MIN(CAST(o.pay_time AS DATE)) AS first_pay_date,
        COUNT(DISTINCT o.order_id) AS orders,
        SUM(o.actual_amount) AS gsv
    FROM {TRINO_ORDERS_TABLE} o
    WHERE o.pay_time >= {CURRENT_START}
      AND o.pay_time < {CURRENT_END}
      AND {VALID_ORDER}
    GROUP BY o.user_id
)
SELECT
    is_member,
    COUNT(*) AS total_users,
    SUM(CASE WHEN orders >= 2 THEN 1 ELSE 0 END) AS repurchase_users,
    ROUND(SUM(CASE WHEN orders >= 2 THEN 1 ELSE 0 END) * 1.0 / NULLIF(COUNT(*), 0), 4) AS repurchase_rate,
    ROUND(SUM(gsv), 2) AS gsv
FROM user_period
GROUP BY is_member
ORDER BY gsv DESC
""",
    ),
    QueryScenario(
        "s07_member_lifecycle_distribution",
        "会员分布",
        "is_member + lifecycle × 12 月 cohort",
        f"""
WITH user_month AS (
    SELECT
        o.user_id,
        SUM(CASE WHEN o.is_member THEN 1 ELSE 0 END) > 0 AS is_member,
        MIN(CAST(o.pay_time AS DATE)) AS first_active,
        MAX(CAST(o.pay_time AS DATE)) AS last_active,
        o.year,
        o.month,
        SUM(o.actual_amount) AS gsv
    FROM {TRINO_ORDERS_TABLE} o
    WHERE o.pay_time >= {CURRENT_START}
      AND o.pay_time < {CURRENT_END}
      AND {VALID_ORDER}
    GROUP BY o.user_id, o.year, o.month
)
SELECT
    year,
    month,
    is_member,
    CASE
        WHEN date_diff('day', first_active, {REFERENCE_DATE}) < 30 THEN '新客'
        WHEN date_diff('day', last_active, {REFERENCE_DATE}) < 30 THEN '活跃客'
        WHEN date_diff('day', last_active, {REFERENCE_DATE}) <= 180 THEN '沉睡客'
        ELSE '流失客'
    END AS lifecycle_stage,
    COUNT(*) AS users,
    ROUND(SUM(gsv), 2) AS gsv
FROM user_month
GROUP BY year, month, is_member,
    CASE
        WHEN date_diff('day', first_active, {REFERENCE_DATE}) < 30 THEN '新客'
        WHEN date_diff('day', last_active, {REFERENCE_DATE}) < 30 THEN '活跃客'
        WHEN date_diff('day', last_active, {REFERENCE_DATE}) <= 180 THEN '沉睡客'
        ELSE '流失客'
    END
ORDER BY year, month, gsv DESC
""",
    ),
    QueryScenario(
        "s08_channel_share",
        "渠道占比",
        "channel + percent of total GSV",
        f"""
WITH by_channel AS (
    SELECT
        o.channel,
        SUM(o.actual_amount) AS gsv,
        COUNT(DISTINCT o.order_id) AS orders
    FROM {TRINO_ORDERS_TABLE} o
    WHERE o.pay_time >= {CURRENT_START}
      AND o.pay_time < {CURRENT_END}
      AND {VALID_ORDER}
    GROUP BY o.channel
),
total AS (
    SELECT SUM(gsv) AS total_gsv FROM by_channel
)
SELECT
    b.channel,
    ROUND(b.gsv, 2) AS gsv,
    b.orders,
    ROUND(b.gsv / NULLIF(t.total_gsv, 0), 4) AS gsv_share
FROM by_channel b
CROSS JOIN total t
ORDER BY b.gsv DESC
""",
    ),
    QueryScenario(
        "s09_r_bucket_repurchase",
        "R 区间复购",
        "recency + R1-R6 bucket + ratio",
        f"""
WITH history AS (
    SELECT
        o.user_id,
        MAX(CAST(o.pay_time AS DATE)) AS last_pay_date
    FROM {TRINO_ORDERS_TABLE} o
    WHERE o.pay_time < {CURRENT_START}
      AND {VALID_ORDER}
    GROUP BY o.user_id
),
current_users AS (
    SELECT DISTINCT o.user_id
    FROM {TRINO_ORDERS_TABLE} o
    WHERE o.pay_time >= {CURRENT_START}
      AND o.pay_time < {CURRENT_END}
      AND {VALID_ORDER}
),
bucketed AS (
    SELECT
        h.user_id,
        CASE
            WHEN date_diff('day', h.last_pay_date, DATE '2025-12-31') BETWEEN 0 AND 30 THEN '近1个月已购客'
            WHEN date_diff('day', h.last_pay_date, DATE '2025-12-31') BETWEEN 31 AND 90 THEN '近2-3个月已购客'
            WHEN date_diff('day', h.last_pay_date, DATE '2025-12-31') BETWEEN 91 AND 180 THEN '近4-6月已购客'
            WHEN date_diff('day', h.last_pay_date, DATE '2025-12-31') BETWEEN 181 AND 365 THEN '近7-12个月已购客'
            WHEN date_diff('day', h.last_pay_date, DATE '2025-12-31') BETWEEN 366 AND 730 THEN '近13个月-近24个月已购客'
            ELSE '2年外已购客'
        END AS r_bucket
    FROM history h
)
SELECT
    r_bucket,
    COUNT(*) AS hist_users,
    SUM(CASE WHEN c.user_id IS NOT NULL THEN 1 ELSE 0 END) AS repurchase_users,
    ROUND(SUM(CASE WHEN c.user_id IS NOT NULL THEN 1 ELSE 0 END) * 1.0 / NULLIF(COUNT(*), 0), 4) AS repurchase_rate
FROM bucketed b
LEFT JOIN current_users c ON b.user_id = c.user_id
GROUP BY r_bucket
ORDER BY repurchase_rate DESC
""",
    ),
    QueryScenario(
        "s10_top20_category_growth",
        "增速最快的 20 个品类",
        "top-N by GSV growth YOY",
        f"""
WITH current_cat AS (
    SELECT o.spu_category, SUM(o.actual_amount) AS gsv
    FROM {TRINO_ORDERS_TABLE} o
    WHERE o.pay_time >= {CURRENT_START}
      AND o.pay_time < {CURRENT_END}
      AND {VALID_ORDER}
    GROUP BY o.spu_category
),
previous_cat AS (
    SELECT o.spu_category, SUM(o.actual_amount) AS gsv
    FROM {TRINO_ORDERS_TABLE} o
    WHERE o.pay_time >= {PREV_START}
      AND o.pay_time < {PREV_END}
      AND {VALID_ORDER}
    GROUP BY o.spu_category
)
SELECT
    COALESCE(c.spu_category, p.spu_category) AS spu_category,
    ROUND(COALESCE(c.gsv, 0), 2) AS current_gsv,
    ROUND(COALESCE(p.gsv, 0), 2) AS previous_gsv,
    ROUND((COALESCE(c.gsv, 0) - COALESCE(p.gsv, 0)) / NULLIF(p.gsv, 0), 4) AS yoy_growth
FROM current_cat c
FULL OUTER JOIN previous_cat p ON c.spu_category = p.spu_category
ORDER BY yoy_growth DESC NULLS LAST
LIMIT 20
""",
    ),
)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def run_one(engine: QueryEngine, scenario: QueryScenario, runs: int, warmup: int) -> ScenarioBenchmark:
    for _ in range(warmup):
        engine.execute(scenario.sql)

    timings: list[float] = []
    rows = 0
    for _ in range(runs):
        start = time.perf_counter()
        result_rows = engine.execute(scenario.sql)
        timings.append(time.perf_counter() - start)
        rows = len(result_rows)

    return ScenarioBenchmark(
        engine=engine.name,
        scenario_id=scenario.scenario_id,
        title=scenario.title,
        runs=runs,
        rows=rows,
        p50_s=percentile(timings, 0.50),
        p95_s=percentile(timings, 0.95),
        p99_s=percentile(timings, 0.99),
        timings_s=timings,
    )


def write_reports(results: list[ScenarioBenchmark], output_json: Path, output_md: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Sprint N+2 Trino Benchmark",
        "",
        "| Engine | Scenario | Runs | Rows | P50(s) | P95(s) | P99(s) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.engine} | {result.scenario_id} {result.title} | {result.runs} | "
            f"{result.rows} | {result.p50_s:.4f} | {result.p95_s:.4f} | {result.p99_s:.4f} |"
        )
    lines.append("")
    if results:
        grouped = {}
        for result in results:
            grouped.setdefault(result.engine, []).append(result.p95_s)
        for engine, values in grouped.items():
            lines.append(f"- {engine} median P95: {statistics.median(values):.4f}s")
    output_md.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=["trino", "duckdb", "both"], default="trino")
    parser.add_argument("--trino-url", default="http://127.0.0.1:18080")
    parser.add_argument("--duckdb-path", default="data/processed/fuqing_crm.duckdb")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--output-json", default="data/processed/trino_poc/benchmark_results.json")
    parser.add_argument("--output-md", default="docs/sprints/SPRINT-N+2-TRINO-BENCHMARK.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    engines: list[QueryEngine] = []
    duck_engine: DuckDbEngine | None = None
    if args.engine in {"duckdb", "both"}:
        duck_engine = DuckDbEngine(args.duckdb_path)
        engines.append(duck_engine)
    if args.engine in {"trino", "both"}:
        trino_engine = TrinoEngine(args.trino_url)
        trino_engine.client.wait_until_ready()
        engines.append(trino_engine)

    results: list[ScenarioBenchmark] = []
    try:
        for engine in engines:
            for scenario in SCENARIOS:
                results.append(run_one(engine, scenario, args.runs, args.warmup))
    finally:
        if duck_engine is not None:
            duck_engine.close()

    write_reports(results, Path(args.output_json), Path(args.output_md))
    print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
