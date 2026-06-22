"""
channel_slice — 按 channel 切片日维度 (Sprint 61+ 第三个 query).

语义: 给定日期, 按 channel 切片, 输出每个 channel 的 GSV + orders + customers + aov + [YOY].

口径复用 (跟 audience_service / audience_table 完全对齐):
- 渠道字段: orders.channel (跟 audience_service._run_period_data 一样)
- GSV: backend/semantic/calculations.GSV_AMOUNT_COL (跟 daily_gsv SSOT)
- 全店 = 所有渠道 sum (row[0])

复用 semantic:
- yoy_absolute (YOY 列)
- safe_ratio (aov 计算)

CLI: python scripts/ad_hoc_query.py channel-slice \
       --date 2026-06-21 \
       [--channel all|online|offline] [--store-id <id>] \
       [--compare yoy|pop|none] \
       [--format csv|table] [--output /tmp/channel.csv]

注: headers 固定 6 列 (channel/gsv/orders/customers/aov/yoy_pct),
    --compare!=yoy 时 yoy_pct 全部 = N/A (保持 spec.headers 静态, 跟 CLI 兼容).
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

# 跟 daily_gsv._GSV_EXPR / yoy_battle._GSV_EXPR 100% 同步
_GSV_EXPR = """
    SUM(CASE WHEN is_goujinjin = FALSE AND order_status != '交易关闭' AND is_refund = FALSE
             THEN actual_amount ELSE 0 END)
""".strip()

_ORDERS_EXPR = "COUNT(*)"
_CUSTOMERS_EXPR = "COUNT(DISTINCT user_id)"

# 渠道排序 SSOT (跟 backend/semantic/channels.CHANNEL_ORDER 同步, 9 个主渠道)
_CHANNEL_ORDER = ("货架", "达播", "直播", "淘客", "微博",
                  "U先派样", "百补派样", "赠品&0.01渠道", "其他")

# 渠道子集映射 (跟 audience_service _expand_channel 同模式)
# online = 货架+达播+直播+淘客+微博 (主站广告流量)
# offline = U先派样+百补派样+赠品&0.01渠道+其他 (派样/低价)
_CHANNEL_SUBSET = {
    "online": ("货架", "达播", "直播", "淘客", "微博"),
    "offline": ("U先派样", "百补派样", "赠品&0.01渠道", "其他"),
}


def _shift_year(d: date, delta_years: int) -> date:
    """跟 daily_gsv / yoy_battle 一致: 闰年 2/29 → 2/28."""
    try:
        return d.replace(year=d.year + delta_years)
    except ValueError:
        return d.replace(year=d.year + delta_years, day=28)


def _run_agg(
    conn,
    start_iso: str,
    end_excl_iso: str,
    where_sql: str,
    where_params: list,
    alias: str,
) -> dict[str, dict]:
    """
    跑单窗口聚合 (按 channel + 全店), 返 {channel: {gsv, orders, customers}}.

    用一个 SQL 同时聚合 4 个 metric × 2 维度 (per-channel + 全店),
    UNION ALL 一次拉完, 避免重复扫表.
    alias: SQL CTE 内部别名 (cur / ly / pop).
    """
    sql = f"""
        WITH by_chan AS (
            SELECT
                channel AS ch,
                {_GSV_EXPR}        AS gsv,
                {_ORDERS_EXPR}     AS orders,
                {_CUSTOMERS_EXPR}  AS customers
            FROM orders
            WHERE pay_time >= ? AND pay_time < ? {where_sql}
            GROUP BY 1
        ),
        total AS (
            SELECT
                '全店' AS ch,
                {_GSV_EXPR}        AS gsv,
                {_ORDERS_EXPR}     AS orders,
                {_CUSTOMERS_EXPR}  AS customers
            FROM orders
            WHERE pay_time >= ? AND pay_time < ? {where_sql}
        )
        SELECT ch, gsv, orders, customers FROM by_chan
        UNION ALL
        SELECT ch, gsv, orders, customers FROM total
    """
    params = [start_iso, end_excl_iso] + list(where_params)
    params += [start_iso, end_excl_iso] + list(where_params)
    assert sql.count("?") == len(params), (
        f"channel_slice SQL placeholder mismatch: {sql.count('?')} ? vs {len(params)} params"
    )
    out: dict[str, dict] = {}
    for ch, gsv, orders, customers in conn.execute(sql, params).fetchall():
        out[ch] = {
            "gsv": float(gsv) if gsv is not None else 0.0,
            "orders": int(orders) if orders is not None else 0,
            "customers": int(customers) if customers is not None else 0,
        }
    return out


def run_channel_slice(
    date: str,
    channel: str = "all",
    store_id: str | None = None,
    compare: str = "none",
) -> List[List[Any]]:
    """
    跑 channel-slice, 返 rows = [[channel, gsv, orders, customers, aov, yoy_pct], ...].

    第 1 行固定 = "全店" (所有 channel sum, 跟 audience_service 模式一致).
    yoy_pct 列: --compare=yoy 时填 +12.34%, 其他情况 = "N/A".
    """
    # 1) 解析日期
    try:
        target_d = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"date '{date}' 必须是 YYYY-MM-DD 格式: {exc}") from exc
    if compare not in ("yoy", "pop", "none"):
        raise ValueError(f"compare '{compare}' 不支持, 可选: yoy|pop|none")

    # 2) channel 解析
    where_parts: list[str] = []
    where_params: list = []
    if channel and channel != "all":
        if channel in _CHANNEL_SUBSET:
            channels_list = _CHANNEL_SUBSET[channel]
            placeholders = ",".join(["?"] * len(channels_list))
            where_parts.append(f"channel IN ({placeholders})")
            where_params.extend(channels_list)
        else:
            where_parts.append("channel = ?")
            where_params.append(channel)
    if store_id:
        where_parts.append("store_id = ?")
        where_params.append(store_id)
    where_sql = f"AND {' AND '.join(where_parts)}" if where_parts else ""

    # 3) 时间窗口
    cur_start = f"{target_d} 00:00:00"
    cur_end_excl = f"{target_d + timedelta(days=1)} 00:00:00"
    ly_d = _shift_year(target_d, -1) if compare == "yoy" else None
    ly_start = f"{ly_d} 00:00:00" if ly_d else None
    ly_end_excl = f"{ly_d + timedelta(days=1)} 00:00:00" if ly_d else None
    prev_d = target_d - timedelta(days=1) if compare == "pop" else None
    pop_start = f"{prev_d} 00:00:00" if prev_d else None
    pop_end_excl = f"{target_d} 00:00:00" if prev_d else None

    # 4) 跑聚合 (3 窗口: cur + ly + pop, 各自独立 read_only_conn 跟 daily_gsv 模式一致)
    with read_only_conn() as conn:
        cur_map = _run_agg(conn, cur_start, cur_end_excl, where_sql, where_params, "cur")
        ly_map = (
            _run_agg(conn, ly_start, ly_end_excl, where_sql, where_params, "ly")
            if ly_d else {}
        )
        pop_map = (
            _run_agg(conn, pop_start, pop_end_excl, where_sql, where_params, "pop")
            if prev_d else {}
        )

    # 5) 组装 rows (全店 排第一, 跟 audience_service 排序一致)
    sorted_channels = ["全店"] + sorted(
        [ch for ch in cur_map if ch != "全店"],
        key=lambda c: (_CHANNEL_ORDER.index(c) if c in _CHANNEL_ORDER else 99, c),
    )

    rows_out: List[List[Any]] = []
    for ch in sorted_channels:
        cu = cur_map[ch]
        aov = _safe_ratio(cu["gsv"], float(cu["orders"]))
        if compare == "yoy":
            ly = ly_map.get(ch, {"gsv": 0.0})
            yoy = _yoy_absolute(cu["gsv"], ly["gsv"])
            if yoy is not None and abs(yoy) > 1e6:
                yoy = None
            yoy_str = f"{yoy:+.2f}%" if yoy is not None else "N/A"
        elif compare == "pop":
            pop = pop_map.get(ch, {"gsv": 0.0})
            yoy = _yoy_absolute(cu["gsv"], pop["gsv"])
            if yoy is not None and abs(yoy) > 1e6:
                yoy = None
            yoy_str = f"{yoy:+.2f}%" if yoy is not None else "N/A"
        else:
            yoy_str = "N/A"
        rows_out.append([
            ch,
            int(cu["gsv"]),
            cu["orders"],
            cu["customers"],
            int(aov),
            yoy_str,
        ])
    return rows_out


# 注册到 registry
_channel_slice_spec = QuerySpec(
    name="channel-slice",
    description="按 channel 切片日维度 (GSV + orders + customers + aov + 可选 YOY), 全店排第一",
    args=[
        {"flags": ("--date",), "required": True, "help": "目标日期 YYYY-MM-DD"},
        {
            "flags": ("--channel",),
            "required": False,
            "default": "all",
            "choices": ["all", "online", "offline", *_CHANNEL_ORDER],
            "help": "渠道筛选: all|online|offline|单渠道 (默认 all)",
        },
        {
            "flags": ("--store-id",),
            "required": False,
            "default": None,
            "help": "店铺 ID 过滤 (可选, 不传 = 全店)",
        },
        {
            "flags": ("--compare",),
            "required": False,
            "default": "none",
            "choices": ["yoy", "pop", "none"],
            "help": "对比口径: yoy (去年同日) | pop (前一天) | none (默认)",
        },
        {
            "flags": ("--format",),
            "required": False,
            "default": "table",
            "choices": ["table", "csv"],
            "help": "输出格式: table 或 csv",
        },
        {
            "flags": ("--output", "-o"),
            "required": False,
            "default": None,
            "help": "csv 输出路径, 不传走默认双层目录规则",
        },
    ],
    headers=["channel", "gsv", "orders", "customers", "aov", "yoy_pct"],
    run=lambda **kw: run_channel_slice(
        date=kw["date"],
        channel=kw.get("channel", "all"),
        store_id=kw.get("store_id"),
        compare=kw.get("compare", "none"),
    ),
    business_tag="渠道切片",
    base_year_arg="date",
)
register(_channel_slice_spec)
