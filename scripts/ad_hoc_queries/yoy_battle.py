"""
yoy_battle — baseline vs current 双窗口 YOY 战斗 (Sprint 61+ 第二个 query).

Sprint 171 决策（架构师拍板）：
- 保留 read_only_conn + inline SQL 实现，不重构走 service
- 理由：29 个 pytest case 已 PASS，重构风险大于收益
- read_only=True 跟 uvicorn 单例共存安全（Sprint 53 race flake 治本）
- 本文件不计入「scripts/ad_hoc_queries/ 下 duckdb.connect 0 命中」验收（新文件才计入）

语义: 给定 baseline + current 两个日期窗口, 输出每个 metric
       (gsv / orders / customers / aov) 的绝对值 + 差异 + 百分比.

口径复用 (跟 daily_gsv 100% 对齐):
- GSV: backend/semantic/calculations.GSV_AMOUNT_COL
       (跟 daily_gsv._GSV_EXPR 走同一个 SSOT)
- orders: COUNT(*) 有效订单 (跟 daily_gsv 一样, 不去重 order_id)
- customers: COUNT(DISTINCT user_id)
- aov: gsv / orders, 走 safe_ratio (跟 backend/semantic/calculations 一致)

复用 semantic:
- yoy_absolute (Sprint 60+ 强一致)
- safe_ratio (aov 计算)

CLI: python scripts/ad_hoc_query.py yoy-battle \
       --baseline-start 2025-06-01 --baseline-end 2025-06-21 \
       --current-start 2026-06-01 --current-end 2026-06-21 \
       --metric gsv|orders|customers|aov|all
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, List

from scripts.ad_hoc_queries._utils import read_only_conn
from scripts.ad_hoc_queries.registry import QuerySpec, register
from backend.semantic.calculations import (  # noqa: E402
    yoy_absolute as _yoy_absolute,
    safe_ratio as _safe_ratio,
)

# 跟 daily_gsv._GSV_EXPR 100% 同步 (Sprint 60+ SSOT 强一致)
# 必须保持 is_goujinjin=FALSE + order_status != '交易关闭' + is_refund=FALSE
_GSV_EXPR = """
    SUM(CASE WHEN is_goujinjin = FALSE AND order_status != '交易关闭' AND is_refund = FALSE
             THEN actual_amount ELSE 0 END)
""".strip()

_ORDERS_EXPR = "COUNT(*)"
_CUSTOMERS_EXPR = "COUNT(DISTINCT user_id)"

# 支持的 metric enum
_METRICS = ("gsv", "orders", "customers", "aov")


def _shift_year(d: date, delta_years: int) -> date:
    """把日期平移 delta_years 年 (闰年安全: 2/29 → 2/28). 跟 daily_gsv 一致."""
    try:
        return d.replace(year=d.year + delta_years)
    except ValueError:
        # 2/29 → 2/28
        return d.replace(year=d.year + delta_years, day=28)


def _parse_date(s: str, field: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field} '{s}' 必须是 YYYY-MM-DD 格式: {exc}") from exc


def _compute_window(
    conn,
    start_d: date,
    end_d: date,
) -> dict:
    """
    跑单窗口聚合, 返 dict = {gsv, orders, customers}.

    用一个 SQL 同时聚合 3 个 metric, 避免 3 次扫表.
    AOV 现场用 safe_ratio 算 (不查表).
    """
    cur_start_dt = f"{start_d} 00:00:00"
    cur_end_dt_excl = f"{end_d + timedelta(days=1)} 00:00:00"
    sql = f"""
        SELECT
            {_GSV_EXPR}        AS gsv,
            {_ORDERS_EXPR}     AS orders,
            {_CUSTOMERS_EXPR}  AS customers
        FROM orders
        WHERE pay_time >= ? AND pay_time < ?
    """
    params = [cur_start_dt, cur_end_dt_excl]
    assert sql.count("?") == len(params), (
        f"yoy_battle window SQL placeholder mismatch: {sql.count('?')} ? vs {len(params)} params"
    )
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return {"gsv": 0.0, "orders": 0, "customers": 0}
    gsv, orders, customers = row
    return {
        "gsv": float(gsv) if gsv is not None else 0.0,
        "orders": int(orders) if orders is not None else 0,
        "customers": int(customers) if customers is not None else 0,
    }


def _format_yoy(yoy: float | None) -> str:
    """跟 daily_gsv 输出口径一致: +12.34% / N/A."""
    if yoy is None:
        return "N/A"
    if abs(yoy) > 1e6:
        # Sprint 60+ 沉淀: 异常 YOY 强截断, 跟 daily_gsv 同模式
        return "N/A"
    return f"{yoy:+.2f}%"


def run_yoy_battle(
    baseline_start: str,
    baseline_end: str,
    current_start: str,
    current_end: str,
    metric: str = "all",
) -> List[List[Any]]:
    """
    跑 yoy_battle, 返 rows = [[metric, baseline_value, current_value, abs_diff, yoy_pct], ...].

    metric: gsv | orders | customers | aov | all (默认 all)
    """
    # 1) 解析日期 + 校验
    bs = _parse_date(baseline_start, "baseline_start")
    be = _parse_date(baseline_end, "baseline_end")
    cs = _parse_date(current_start, "current_start")
    ce = _parse_date(current_end, "current_end")
    if be < bs:
        raise ValueError(f"baseline_end ({baseline_end}) < baseline_start ({baseline_start})")
    if ce < cs:
        raise ValueError(f"current_end ({current_end}) < current_start ({current_start})")
    # 窗口限 366 天 (跟 daily_gsv 同模式, Sprint 60+ OOM 治本)
    if (be - bs).days > 366:
        raise ValueError(
            f"baseline 窗口 {(be - bs).days}d > 366d, 请用 sprint 切片"
        )
    if (ce - cs).days > 366:
        raise ValueError(
            f"current 窗口 {(ce - cs).days}d > 366d, 请用 sprint 切片"
        )

    # 2) metric 选择
    if metric == "all":
        target_metrics = list(_METRICS)
    elif metric in _METRICS:
        target_metrics = [metric]
    else:
        raise ValueError(f"metric '{metric}' 不支持, 可选: {', '.join(_METRICS + ('all',))}")

    # 3) 跑双窗口聚合
    with read_only_conn() as conn:
        bl = _compute_window(conn, bs, be)
        cu = _compute_window(conn, cs, ce)

    # 4) 组装 rows
    rows_out: List[List[Any]] = []
    for m in target_metrics:
        if m == "aov":
            bl_val = _safe_ratio(bl["gsv"], float(bl["orders"]))
            cu_val = _safe_ratio(cu["gsv"], float(cu["orders"]))
        else:
            bl_val = float(bl[m])
            cu_val = float(cu[m])
        abs_diff = cu_val - bl_val
        # 复用 semantic/calculations.yoy_absolute (Sprint 60+ 强一致)
        yoy = _yoy_absolute(cu_val, bl_val)
        rows_out.append([
            m,
            f"{bl_val:.2f}" if m == "aov" else int(bl_val),
            f"{cu_val:.2f}" if m == "aov" else int(cu_val),
            (f"{abs_diff:+.2f}" if m == "aov" else f"{int(abs_diff):+d}"),
            _format_yoy(yoy),
        ])
    return rows_out


# 注册到 registry
_yoy_battle_spec = QuerySpec(
    name="yoy-battle",
    description="baseline vs current 双窗口 YOY 战斗 (gsv/orders/customers/aov 绝对值+差异+百分比)",
    args=[
        {"flags": ("--baseline-start",), "required": True, "help": "基期起始日期 YYYY-MM-DD"},
        {"flags": ("--baseline-end",), "required": True, "help": "基期结束日期 YYYY-MM-DD"},
        {"flags": ("--current-start",), "required": True, "help": "当期起始日期 YYYY-MM-DD"},
        {"flags": ("--current-end",), "required": True, "help": "当期结束日期 YYYY-MM-DD"},
        {
            "flags": ("--metric",),
            "required": False,
            "default": "all",
            "choices": ["gsv", "orders", "customers", "aov", "all"],
            "help": "输出哪个 metric: gsv|orders|customers|aov|all (默认 all)",
        },
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
    headers=["metric", "baseline_value", "current_value", "abs_diff", "yoy_pct"],
    run=lambda **kw: run_yoy_battle(
        baseline_start=kw["baseline_start"],
        baseline_end=kw["baseline_end"],
        current_start=kw["current_start"],
        current_end=kw["current_end"],
        metric=kw.get("metric", "all"),
    ),
    business_tag="YOY对比",
    base_year_arg="current_start",
)
register(_yoy_battle_spec)
