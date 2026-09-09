"""C0 RFM as_of：订单粒度 F，日历日 R，不偷看 as_of 之后。

M 按 dated refunds 净额：refunded_at > as_of 的晚到退款不进入该时点。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Optional

from backend.services.metrics.competition_compute import (
    iter_effective_orders,
    normalize_sample_mode,
)

MEMBER_HISTORY_STATUS = "UNKNOWN"


def compute_rfm_as_of(
    conn,
    *,
    as_of: str,
    user_ids: Optional[Iterable[str]] = None,
    sample_mode: Optional[str] = None,
    sample_channel_ids: Optional[list[str]] = None,
    history_channels: Optional[list[str]] = None,
    history_product_ids: Optional[list[str]] = None,
) -> dict[str, dict[str, Any]]:
    """按 as_of 日历日计算 F/M/R。F=DISTINCT order_id；R=DATEDIFF 日历日。"""
    as_of_day = as_of[:10]
    mode, sample_ids = normalize_sample_mode(sample_mode, sample_channel_ids)
    exclude = sample_ids if mode == "EXCLUDE_AND_RECOMPUTE_HISTORY" else None
    ids = [str(uid) for uid in (user_ids or []) if uid] or None
    orders = iter_effective_orders(
        conn,
        as_of=as_of_day,
        pay_end=as_of_day,
        channels=history_channels,
        exclude_channels=exclude,
        product_ids=history_product_ids,
        user_ids=ids,
    )

    grouped: dict[str, dict[str, Any]] = {}
    for rec in orders:
        uid = rec["user_id"]
        bucket = grouped.setdefault(
            uid,
            {"order_ids": set(), "m": 0.0, "last_pay": rec["pay_date"], "first_pay": rec["pay_date"]},
        )
        bucket["order_ids"].add(rec["order_id"])
        bucket["m"] += float(rec["net"])
        if rec["pay_date"] > bucket["last_pay"]:
            bucket["last_pay"] = rec["pay_date"]
        if rec["pay_date"] < bucket["first_pay"]:
            bucket["first_pay"] = rec["pay_date"]

    as_of_date = date.fromisoformat(as_of_day)
    result: dict[str, dict[str, Any]] = {}
    for user_id, bucket in grouped.items():
        last = date.fromisoformat(bucket["last_pay"])
        result[user_id] = {
            "user_id": user_id,
            "as_of": as_of_day,
            "f": len(bucket["order_ids"]),
            "m": round(bucket["m"], 4),
            "r_days": (as_of_date - last).days,
            "last_pay": bucket["last_pay"],
            "first_pay": bucket["first_pay"],
            "member_status_as_of": MEMBER_HISTORY_STATUS,
            "sample_mode_applied": mode,
            "recency_unit": "calendar_day",
            "f_grain": "distinct_order_id",
        }
    return result
