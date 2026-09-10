"""C0 人群/新老/小样口径的可注入计算入口。

不读生产 DuckDB：调用方必须传入合成 conn。HTTP 接线归 A3。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Optional

from backend.semantic.time import (
    analysis_cutoff,
    resolve_comparison_range,
    tplus1_yesterday,
    window_has_no_current_month_data,
)

SAMPLE_MODES = (
    "INCLUDE",
    "EXCLUDE_CURRENT_SALES_ONLY",
    "EXCLUDE_AND_RECOMPUTE_HISTORY",
)
MEMBER_HISTORY_STATUS = "UNKNOWN"
SAMPLE_CHANNEL_SET_STATUS = "UNKNOWN"


def _require_gsv(metric_type: str) -> str:
    normalized = (metric_type or "").upper()
    if normalized != "GSV":
        raise ValueError("competition metrics require explicit metric_type=GSV; ignoring a received type is a failure")
    return normalized


def normalize_sample_mode(
    sample_mode: Optional[str],
    sample_channel_ids: Optional[Iterable[str]],
) -> tuple[str, list[str] | None]:
    mode = (sample_mode or "INCLUDE").upper()
    if mode not in SAMPLE_MODES:
        raise ValueError(f"unsupported sample_mode: {sample_mode}")
    channels = list(sample_channel_ids) if sample_channel_ids is not None else None
    if mode == "INCLUDE":
        if channels is not None:
            raise ValueError("INCLUDE sample_mode must set sample_channel_ids to null")
        return mode, None
    if not channels:
        raise ValueError("excluding sample_mode requires explicit sample_channel_ids; channel set is UNKNOWN")
    return mode, channels


def _member_mark(value: Any) -> str:
    if value is True:
        return "MEMBER"
    if value is False:
        return "NON_MEMBER"
    return "UNKNOWN"


def _in_list_sql(column: str, values: list[str]) -> tuple[str, list[str]]:
    placeholders = ",".join(["?"] * len(values))
    return f"{column} IN ({placeholders})", list(values)


def _not_in_list_sql(column: str, values: list[str]) -> tuple[str, list[str]]:
    placeholders = ",".join(["?"] * len(values))
    return f"{column} NOT IN ({placeholders})", list(values)


def _as_day(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _refunds_table_present(conn) -> bool:
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE lower(table_name) = 'refunds'
            """
        ).fetchone()
        if not row:
            return False
        cols = {
            str(name).lower()
            for (name,) in conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE lower(table_name) = 'refunds'
                """
            ).fetchall()
        }
        return "refunded_at" in cols and "amount" in cols
    except Exception:
        return False


def has_dated_refunds(conn) -> bool:
    """True when conn has a dated `refunds(order_id, refunded_at, amount)` path."""
    return _refunds_table_present(conn)


def _valid_line_sql(alias: str, *, dated_refunds: bool) -> str:
    # Dated refunds isolate late refunds after as_of; boolean is_refund peeks at current row state.
    parts = [
        f"{alias}.is_goujinjin = FALSE",
        f"{alias}.order_status != '交易关闭'",
    ]
    if not dated_refunds:
        parts.append(f"{alias}.is_refund = FALSE")
    return " AND ".join(parts)


def refunds_as_of(conn, as_of: str) -> dict[str, float]:
    """Sum refund amount per order_id with refunded_at <= as_of. Missing table → {}."""
    as_of_day = _as_day(as_of)
    if not has_dated_refunds(conn):
        return {}
    rows = conn.execute(
        """
        SELECT order_id, COALESCE(SUM(amount), 0)
        FROM refunds
        WHERE CAST(refunded_at AS DATE) <= ?::DATE
        GROUP BY order_id
        """,
        [as_of_day],
    ).fetchall()
    return {row[0]: float(row[1] or 0) for row in rows}


def iter_effective_orders(
    conn,
    *,
    as_of: str,
    pay_start: Optional[str] = None,
    pay_end: Optional[str] = None,
    channels: Optional[list[str]] = None,
    exclude_channels: Optional[list[str]] = None,
    product_ids: Optional[list[str]] = None,
    user_ids: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Order-grain net GSV as of as_of. Partial refunds use dated refunds, not line gross."""
    as_of_day = _as_day(as_of)
    dated = has_dated_refunds(conn)
    where = [
        "o.pay_time IS NOT NULL",
        _valid_line_sql("o", dated_refunds=dated),
        "CAST(o.pay_time AS DATE) <= ?::DATE",
    ]
    params: list[Any] = [as_of_day]
    if pay_start:
        where.append("CAST(o.pay_time AS DATE) >= ?::DATE")
        params.append(_as_day(pay_start))
    if pay_end:
        where.append("CAST(o.pay_time AS DATE) <= ?::DATE")
        params.append(_as_day(pay_end))
    if channels:
        clause, extra = _in_list_sql("o.channel", channels)
        where.append(clause)
        params.extend(extra)
    if exclude_channels:
        clause, extra = _not_in_list_sql("o.channel", exclude_channels)
        where.append(clause)
        params.extend(extra)
    if product_ids:
        clause, extra = _in_list_sql("o.product_id", product_ids)
        where.append(clause)
        params.extend(extra)
    if user_ids:
        ids = [str(uid) for uid in user_ids if uid]
        if ids:
            clause, extra = _in_list_sql("o.user_id", ids)
            where.append(clause)
            params.extend(extra)

    lines = conn.execute(
        f"""
        SELECT o.order_id, o.user_id, o.actual_amount, o.is_member, o.channel,
               o.product_id, CAST(o.pay_time AS DATE)::VARCHAR
        FROM orders o
        WHERE {" AND ".join(where)}
        """,
        params,
    ).fetchall()

    refund_map = refunds_as_of(conn, as_of_day) if dated else {}
    orders: dict[str, dict[str, Any]] = {}
    for order_id, user_id, amount, is_member, channel, product_id, pay_date in lines:
        rec = orders.get(order_id)
        mark = _member_mark(is_member)
        if rec is None:
            orders[order_id] = {
                "order_id": order_id,
                "user_id": user_id,
                "gross": float(amount or 0),
                "pay_date": str(pay_date)[:10],
                "is_member": is_member,
                "member_mark": mark,
                "channel": channel,
                "product_id": product_id,
            }
            continue
        rec["gross"] += float(amount or 0)
        if str(pay_date)[:10] < rec["pay_date"]:
            rec["pay_date"] = str(pay_date)[:10]
        if rec["member_mark"] != mark:
            rec["member_mark"] = "UNKNOWN"
            rec["is_member"] = None

    effective: list[dict[str, Any]] = []
    for rec in orders.values():
        net = rec["gross"] - float(refund_map.get(rec["order_id"], 0.0))
        if net <= 1e-9:
            continue
        rec["net"] = round(net, 4)
        effective.append(rec)
    return effective


def _first_pay_map(
    conn,
    *,
    cutoff: str,
    as_of: Optional[str],
    sample_mode: str,
    sample_channel_ids: list[str] | None,
    history_channels: Optional[list[str]],
    history_product_ids: Optional[list[str]],
    user_ids: Optional[list[str]] = None,
) -> dict[str, str]:
    as_of_day = _as_day(as_of or cutoff)
    exclude = sample_channel_ids if sample_mode == "EXCLUDE_AND_RECOMPUTE_HISTORY" else None
    orders = iter_effective_orders(
        conn,
        as_of=as_of_day,
        pay_end=min(cutoff, as_of_day),
        channels=history_channels,
        exclude_channels=exclude,
        product_ids=history_product_ids,
        user_ids=user_ids,
    )
    first: dict[str, str] = {}
    for rec in orders:
        uid = rec["user_id"]
        prev = first.get(uid)
        if prev is None or rec["pay_date"] < prev:
            first[uid] = rec["pay_date"]
    return first


def _empty_metrics(
    *,
    metric_type: str,
    empty_reason: str,
    executed: dict[str, Any],
) -> dict[str, Any]:
    executed = dict(executed)
    executed["current_period"] = None
    executed["empty_reason"] = empty_reason
    return {
        "completeness": "EMPTY",
        "empty_reason": empty_reason,
        "metric_type": metric_type,
        "gsv": 0.0,
        "users": [],
        "old_users": [],
        "new_users": [],
        "old_gsv": 0.0,
        "new_gsv": 0.0,
        "member": {
            "MEMBER": {"users": [], "gsv": 0.0},
            "NON_MEMBER": {"users": [], "gsv": 0.0},
            "UNKNOWN": {"users": [], "gsv": 0.0},
        },
        "member_history_status": MEMBER_HISTORY_STATUS,
        "executed": executed,
    }


def compute_competition_metrics(
    conn,
    *,
    start_date: str,
    end_date: str,
    metric_type: str = "GSV",
    comparison_mode: str = "YOY_SAME_PERIOD",
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
    sample_mode: Optional[str] = None,
    sample_channel_ids: Optional[list[str]] = None,
    sales_channels: Optional[list[str]] = None,
    sales_product_ids: Optional[list[str]] = None,
    history_channels: Optional[list[str]] = None,
    history_product_ids: Optional[list[str]] = None,
    today: Optional[date] = None,
    as_of: Optional[str] = None,
) -> dict[str, Any]:
    """按 C0 口径计算一期 GSV / 新老 / 会员三桶，并回显实际执行条件。"""
    metric_type = _require_gsv(metric_type)
    if start_date > end_date:
        raise ValueError("period start_date must be <= end_date")
    mode, sample_ids = normalize_sample_mode(sample_mode, sample_channel_ids)
    today = today or date.today()
    as_of_day = (as_of or end_date)[:10]
    # Empty month first: do not echo a future full month (09-01..09-30) as current_period.
    if window_has_no_current_month_data(start_date, end_date, today=today):
        return _empty_metrics(
            metric_type=metric_type,
            empty_reason="NO_CURRENT_MONTH_DATA",
            executed={
                "timezone": "Asia/Shanghai",
                "metric_type": "GSV",
                "current_period": None,
                "comparison_period": None,
                "empty_reason": "NO_CURRENT_MONTH_DATA",
                "data_cutoff_policy": "T_PLUS_1_YESTERDAY",
                "as_of": tplus1_yesterday(today).isoformat(),
                "sample_mode": mode,
                "sample_channel_ids": sample_ids,
                "unknown_flags": ["SAMPLE_CHANNEL_SET", "MEMBER_HISTORY"],
                "ignored_filters": [],
            },
        )
    executed = _executed(
        start_date, end_date, comparison_mode, compare_start_date, compare_end_date,
        mode, sample_ids, sales_channels, sales_product_ids,
        history_channels, history_product_ids, as_of_day,
    )
    if start_date > as_of_day:
        return _empty_metrics(
            metric_type=metric_type,
            empty_reason="PERIOD_AFTER_AS_OF",
            executed=executed,
        )

    cutoff = analysis_cutoff(start_date).strftime("%Y-%m-%d")
    period_exclude = sample_ids if mode != "INCLUDE" else None
    period_orders = iter_effective_orders(
        conn,
        as_of=as_of_day,
        pay_start=start_date,
        pay_end=min(end_date, as_of_day),
        channels=sales_channels,
        exclude_channels=period_exclude,
        product_ids=sales_product_ids,
    )

    first_map = _first_pay_map(
        conn,
        cutoff=cutoff,
        as_of=as_of_day,
        sample_mode=mode,
        sample_channel_ids=sample_ids,
        history_channels=history_channels,
        history_product_ids=history_product_ids,
    )

    gsv = 0.0
    users: set[str] = set()
    user_gsv: dict[str, float] = {}
    user_member: dict[str, str] = {}
    for rec in period_orders:
        uid = rec["user_id"]
        net = float(rec["net"])
        gsv += net
        users.add(uid)
        user_gsv[uid] = user_gsv.get(uid, 0.0) + net
        mark = rec["member_mark"]
        prev = user_member.get(uid)
        if prev is None:
            user_member[uid] = mark
        elif prev != mark:
            user_member[uid] = "UNKNOWN"

    # Zero period-GSV old customers (e.g. U-SEP5 9/5 first buy, window 9/15–21)
    # stay in old_users: identity set includes same-month pre-window effective buyers.
    month_start = f"{start_date[:8]}01"
    if month_start < start_date:
        history_exclude = sample_ids if mode == "EXCLUDE_AND_RECOMPUTE_HISTORY" else None
        prewindow = iter_effective_orders(
            conn,
            as_of=as_of_day,
            pay_start=month_start,
            pay_end=cutoff if cutoff < as_of_day else as_of_day,
            channels=sales_channels,
            exclude_channels=history_exclude,
            product_ids=sales_product_ids,
        )
        for rec in prewindow:
            if rec["pay_date"] >= start_date:
                continue
            uid = rec["user_id"]
            if uid in users:
                continue
            users.add(uid)
            user_gsv.setdefault(uid, 0.0)
            user_member.setdefault(uid, rec["member_mark"])

    old_users = sorted(uid for uid in users if first_map.get(uid, "9999-12-31") <= cutoff)
    new_users = sorted(uid for uid in users if uid not in set(old_users))
    member_buckets = {
        "MEMBER": {"users": [], "gsv": 0.0},
        "NON_MEMBER": {"users": [], "gsv": 0.0},
        "UNKNOWN": {"users": [], "gsv": 0.0},
    }
    for uid in users:
        bucket = user_member.get(uid, "UNKNOWN")
        member_buckets[bucket]["users"].append(uid)
        member_buckets[bucket]["gsv"] += user_gsv.get(uid, 0.0)
    for bucket in member_buckets.values():
        bucket["users"].sort()
        bucket["gsv"] = round(bucket["gsv"], 4)

    return {
        "completeness": "COMPLETE",
        "empty_reason": None,
        "metric_type": metric_type,
        "gsv": round(gsv, 4),
        "users": sorted(users),
        "old_users": old_users,
        "new_users": new_users,
        "old_gsv": round(sum(user_gsv.get(uid, 0.0) for uid in old_users), 4),
        "new_gsv": round(sum(user_gsv.get(uid, 0.0) for uid in new_users), 4),
        "member": member_buckets,
        "member_history_status": MEMBER_HISTORY_STATUS,
        "executed": executed,
    }


def _executed(
    start_date: str,
    end_date: str,
    comparison_mode: str,
    compare_start_date: Optional[str],
    compare_end_date: Optional[str],
    sample_mode: str,
    sample_ids: list[str] | None,
    sales_channels: Optional[list[str]],
    sales_product_ids: Optional[list[str]],
    history_channels: Optional[list[str]],
    history_product_ids: Optional[list[str]],
    as_of_day: str,
) -> dict[str, Any]:
    comparison = resolve_comparison_range(
        comparison_mode,
        start_date,
        end_date,
        compare_start_date,
        compare_end_date,
    )
    return {
        "timezone": "Asia/Shanghai",
        "metric_type": "GSV",
        "current_period": {
            "start": start_date,
            "end": end_date,
            "cutoff": analysis_cutoff(start_date).strftime("%Y-%m-%d"),
        },
        "comparison_mode": (comparison_mode or "YOY_SAME_PERIOD").upper(),
        "comparison_period": {
            "start": comparison.start,
            "end": comparison.end,
            "cutoff": comparison.cutoff,
        },
        "cutoff": analysis_cutoff(start_date).strftime("%Y-%m-%d"),
        "as_of": as_of_day,
        "sample_mode": sample_mode,
        "sample_channel_ids": sample_ids,
        "sample_history_recomputed": sample_mode == "EXCLUDE_AND_RECOMPUTE_HISTORY",
        "sample_channel_set_status": SAMPLE_CHANNEL_SET_STATUS,
        "sales_scope": {
            "channels": list(sales_channels or []),
            "product_ids": list(sales_product_ids or []),
        },
        "history_scope": {
            "channels": list(history_channels or []),
            "product_ids": list(history_product_ids or []),
        },
        "unknown_flags": ["SAMPLE_CHANNEL_SET", "MEMBER_HISTORY"],
        "limitations": [
            "sample channel business-complete set is UNKNOWN; only caller-supplied sample_channel_ids are applied",
            "member history as_of is UNKNOWN; current-order is_member NULL is UNKNOWN, not non-member",
        ],
        "ignored_filters": [],
    }


def empty_mtd_summary(*, today: date, metric_type: str = "GSV") -> dict[str, Any]:
    """默认 MTD 在月初 T+1 无本月数据时的空态，不造未来完整月。"""
    _require_gsv(metric_type)
    return {
        "completeness": "EMPTY",
        "empty_reason": "NO_CURRENT_MONTH_DATA",
        "year_label": str(today.year),
        "comp_year_label": str(today.year - 1),
        "prev2_year_label": str(today.year - 2),
        "metric_type": "GSV",
        "indicators": [],
        "channel_all": [],
        "channel_member": [],
        "current_period": None,
        "available_days": 0,
        "executed": {
            "timezone": "Asia/Shanghai",
            "data_cutoff_policy": "T_PLUS_1_YESTERDAY",
            "empty_reason": "NO_CURRENT_MONTH_DATA",
            "as_of": tplus1_yesterday(today).isoformat(),
            "current_period": None,
        },
    }
