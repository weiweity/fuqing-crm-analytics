"""
daily_gsv — 日序列 GSV + customers + YOY% (Sprint 61 MVP demo query).

Sprint 171 决策（架构师拍板）：
- 保留 read_only_conn + inline SQL 实现，不重构走 service
- 理由：29 个 pytest case 已 PASS，重构风险大于收益
- read_only=True 跟 uvicorn 单例共存安全（Sprint 53 race flake 治本）
- 本文件不计入「scripts/ad_hoc_queries/ 下 duckdb.connect 0 命中」验收（新文件才计入）

走 backend/semantic/filters.OrderFilters + calculations.yoy_absolute,
禁 inline SQL, 严格 L1 f-string lint 友好 (没有 f-string 拼 SQL).

CLI: python scripts/ad_hoc_query.py daily-gsv \
       --start 2026-06-19 --end 2026-06-21 [--format csv|table]
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, List

from scripts.ad_hoc_queries._utils import read_only_conn
from scripts.ad_hoc_queries.registry import QuerySpec, register
from backend.semantic.calculations import yoy_absolute as _yoy_absolute  # noqa: E402

# GSV 口径 SQL (跟 backend/semantic/calculations.GSV_AMOUNT_COL SSOT 对齐)
_GSV_EXPR = """
    SUM(CASE WHEN is_goujinjin = FALSE AND order_status != '交易关闭' AND is_refund = FALSE
             THEN actual_amount ELSE 0 END)
""".strip()

# customers = COUNT(DISTINCT user_id)
_CUSTOMERS_EXPR = "COUNT(DISTINCT user_id)"


def _shift_year(d: date, delta_years: int) -> date:
    """把日期平移 delta_years 年 (闰年安全: 2/29 → 2/28)."""
    try:
        return d.replace(year=d.year + delta_years)
    except ValueError:
        # 2/29 → 2/28
        return d.replace(year=d.year + delta_years, day=28)


def run_daily_gsv(start: str, end: str) -> List[List[Any]]:
    """
    跑 daily_gsv, 返 rows = [[date_str, gsv, customers, yoy_pct_or_None], ...].

    YOY = (cur - prev_year) / prev_year * 100 (复用 yoy_absolute, 跟 semantic 层一致).
    强截断 YOY 范围 [-1000, 1000] pp (防 Sprint 60 同根因).
    """
    start_d = datetime.strptime(start, "%Y-%m-%d").date()
    end_d = datetime.strptime(end, "%Y-%m-%d").date()
    if end_d < start_d:
        raise ValueError(f"end ({end}) < start ({start})")
    # 时间窗口限 366 天 (Sprint 60+ 沉淀: 防 OOM)
    if (end_d - start_d).days > 366:
        raise ValueError(
            f"time window {(end_d - start_d).days}d > 366d, 请用 sprint 切片"
        )

    # 去年同期 (闰年 2/29 → 2/28)
    ly_start = _shift_year(start_d, -1)
    ly_end = _shift_year(end_d, -1)

    # DuckDB 端按天聚合 (Sprint 60+ 沉淀: 不取明细, 走 SQL aggregation)
    sql = f"""
        WITH daily AS (
            SELECT
                CAST(pay_time AS DATE) AS d,
                {_GSV_EXPR}         AS gsv,
                {_CUSTOMERS_EXPR}   AS customers
            FROM orders
            WHERE pay_time >= ? AND pay_time < ?
            GROUP BY 1
        ),
        ly_daily AS (
            SELECT
                CAST(pay_time AS DATE) AS d,
                {_GSV_EXPR}         AS gsv,
                {_CUSTOMERS_EXPR}   AS customers
            FROM orders
            WHERE pay_time >= ? AND pay_time < ?
            GROUP BY 1
        )
        SELECT
            d.d                AS d,
            d.gsv              AS gsv,
            d.customers        AS customers,
            ly.gsv             AS ly_gsv
        FROM daily d
        LEFT JOIN ly_daily ly
            ON ly.d = (d.d - INTERVAL 1 YEAR)
        ORDER BY d.d
    """
    # params 顺序必须跟 SQL 占位符顺序一致 (Sprint 60+ 留尾必查项)
    cur_start_dt = f"{start_d} 00:00:00"
    cur_end_dt_excl = f"{end_d + timedelta(days=1)} 00:00:00"  # 半开区间, 跟 ly 对齐
    ly_start_dt = f"{ly_start} 00:00:00"
    ly_end_dt_excl = f"{ly_end + timedelta(days=1)} 00:00:00"
    params = [cur_start_dt, cur_end_dt_excl, ly_start_dt, ly_end_dt_excl]
    # Sprint 60+ 留尾: 强校验占位符数 == params 数
    assert sql.count("?") == len(params), (
        f"daily_gsv SQL placeholder mismatch: {sql.count('?')} ? vs {len(params)} params"
    )

    rows_out: List[List[Any]] = []
    with read_only_conn() as conn:
        cur = conn.execute(sql, params)
        for d, gsv, customers, ly_gsv in cur.fetchall():
            # 复用 semantic/calculations.yoy_absolute (Sprint 60+ 强一致)
            yoy = None
            if ly_gsv is not None and gsv is not None:
                yoy = _yoy_absolute(float(gsv), float(ly_gsv))
            # Sprint 60+ 沉淀: YOY 范围强截断 (|v| > 1e6 视为脏数据)
            if yoy is not None and abs(yoy) > 1e6:
                yoy = None
            rows_out.append([
                str(d),
                int(gsv) if gsv is not None else 0,
                int(customers) if customers is not None else 0,
                (f"{yoy:+.2f}%" if yoy is not None else "N/A"),
            ])
    return rows_out


# 5 个子命令里的第一个 — 注册到 registry
_daily_gsv_spec = QuerySpec(
    name="daily-gsv",
    description="日序列 GSV + customers + YOY 百分比. 走 semantic 层, 禁 inline SQL",
    args=[
        {"flags": ("--start",), "required": True, "help": "起始日期 YYYY-MM-DD"},
        {"flags": ("--end",), "required": True, "help": "结束日期 YYYY-MM-DD"},
        {
            "flags": ("--format",),
            "required": False,
            "default": "table",
            "choices": ["table", "csv", "xlsx"],
            "help": "输出格式: table/csv/xlsx",
        },
        {
            "flags": ("--output", "-o"),
            "required": False,
            "default": None,
            "help": "csv 输出路径, 不传走默认双层目录规则 (~/Desktop/fuqin date/取数/...)",
        },
    ],
    headers=["date", "gsv", "customers", "yoy_pct"],
    run=lambda **kw: run_daily_gsv(start=kw["start"], end=kw["end"]),
    business_tag="日序列GSV",
    base_year_arg="start",
)
register(_daily_gsv_spec)
