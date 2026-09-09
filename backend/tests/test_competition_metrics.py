"""A2 比赛口径手算金标准 + 第二批实现对接（合成 DuckDB，不读真实库）。

金标准表仍是手算；COMPUTATION=NOT_RUN 只描述表本身。
实现断言走 in-memory conn，对照 C0 cutoff/GSV/新老/小样/F/R/会员。
"""

from __future__ import annotations

import inspect
import json
from datetime import date, timedelta
from typing import Any

import duckdb
import pytest

from backend.semantic.calculations import safe_ratio
from backend.semantic.time import (
    PeriodBuilder,
    analysis_cutoff,
    current_month_available,
    shift_year_clamped,
    window_has_no_current_month_data,
)
from backend.services.metrics.audience_summary import calculate_audience_summary
from backend.services.metrics import competition_compute as competition_compute_mod
from backend.services.metrics.competition_compute import (
    compute_competition_metrics,
    empty_mtd_summary,
)
from backend.services.rfm.as_of import compute_rfm_as_of
from backend.services.rfm.extended import get_user_rfm_extended
from backend.services.rfm.f_flow import _run_f_flow_period

FIXTURE_ID = "competition-metrics-gold/v1"
COMPUTATION = "NOT_RUN"
HAND_CALCULATED = True
TIMEZONE_DESIRED = "Asia/Shanghai"
TIMEZONE_CURRENT = "UNSPECIFIED_NAIVE"
CONTRACT_HASH = "PENDING_C0"

# 源码已写明的派样渠道；不是业务全集，禁止外推。
SOURCE_SAMPLING_CHANNELS = ("U先派样", "百补派样")
SOURCE_GIFT_SAMPLE_DB = "赠品&0.01渠道"
SOURCE_SAMPLE_GROUP = {"纯派样": ("U先派样", "百补派样")}

# ---------------------------------------------------------------------------
# 合成订单（行粒度 = order_id + sub_order_id，与 backend/database.py 一致）
# ---------------------------------------------------------------------------

GOLDEN_ORDER_LINES: tuple[dict[str, Any], ...] = (
    {
        "line_id": "L_LEAP",
        "order_id": "O_LEAP",
        "sub_order_id": "S1",
        "user_id": "C_LEAP",
        "pay_date": "2024-02-29",
        "channel": "货架",
        "actual_amount": 100.0,
        "is_member": False,
        "is_refund": False,
        "is_goujinjin": False,
        "order_status": "交易成功",
        "product_id": "P_FULL",
        "spu_type": "正装",
    },
    {
        "line_id": "L_SEP5",
        "order_id": "O_SEP5",
        "sub_order_id": "S1",
        "user_id": "C_SEP5",
        "pay_date": "2026-09-05",
        "channel": "货架",
        "actual_amount": 200.0,
        "is_member": True,
        "is_refund": False,
        "is_goujinjin": False,
        "order_status": "交易成功",
        "product_id": "P_FULL",
        "spu_type": "正装",
    },
    {
        "line_id": "L_SEP5R",
        "order_id": "O_SEP5R",
        "sub_order_id": "S1",
        "user_id": "C_SEP5",
        "pay_date": "2026-09-16",
        "channel": "货架",
        "actual_amount": 300.0,
        "is_member": True,
        "is_refund": False,
        "is_goujinjin": False,
        "order_status": "交易成功",
        "product_id": "P_FULL",
        "spu_type": "正装",
    },
    {
        "line_id": "L_MULTI_1",
        "order_id": "O_MULTI",
        "sub_order_id": "S1",
        "user_id": "C_MULTI",
        "pay_date": "2026-09-16",
        "channel": "货架",
        "actual_amount": 100.0,
        "is_member": False,
        "is_refund": False,
        "is_goujinjin": False,
        "order_status": "交易成功",
        "product_id": "P_A",
        "spu_type": "正装",
    },
    {
        "line_id": "L_MULTI_2",
        "order_id": "O_MULTI",
        "sub_order_id": "S2",
        "user_id": "C_MULTI",
        "pay_date": "2026-09-16",
        "channel": "货架",
        "actual_amount": 100.0,
        "is_member": False,
        "is_refund": False,
        "is_goujinjin": False,
        "order_status": "交易成功",
        "product_id": "P_B",
        "spu_type": "正装",
    },
    {
        "line_id": "L_MULTI_3",
        "order_id": "O_MULTI",
        "sub_order_id": "S3",
        "user_id": "C_MULTI",
        "pay_date": "2026-09-16",
        "channel": "货架",
        "actual_amount": 100.0,
        "is_member": False,
        "is_refund": False,
        "is_goujinjin": False,
        "order_status": "交易成功",
        "product_id": "P_C",
        "spu_type": "正装",
    },
    {
        "line_id": "L_XCH1",
        "order_id": "O_XCH1",
        "sub_order_id": "S1",
        "user_id": "C_XCH",
        "pay_date": "2025-09-16",
        "channel": "货架",
        "actual_amount": 400.0,
        "is_member": True,
        "is_refund": False,
        "is_goujinjin": False,
        "order_status": "交易成功",
        "product_id": "P_FULL",
        "spu_type": "正装",
    },
    {
        "line_id": "L_XCH2",
        "order_id": "O_XCH2",
        "sub_order_id": "S1",
        "user_id": "C_XCH",
        "pay_date": "2026-09-16",
        "channel": "直播",
        "actual_amount": 500.0,
        "is_member": True,
        "is_refund": False,
        "is_goujinjin": False,
        "order_status": "交易成功",
        "product_id": "P_FULL",
        "spu_type": "正装",
    },
    {
        "line_id": "L_UNK",
        "order_id": "O_UNK",
        "sub_order_id": "S1",
        "user_id": "C_UNK",
        "pay_date": "2026-09-16",
        "channel": "货架",
        "actual_amount": 150.0,
        "is_member": None,
        "is_refund": False,
        "is_goujinjin": False,
        "order_status": "交易成功",
        "product_id": "P_FULL",
        "spu_type": "正装",
    },
    {
        "line_id": "L_SAMP",
        "order_id": "O_SAMP",
        "sub_order_id": "S1",
        "user_id": "C_SAMP",
        "pay_date": "2026-08-01",
        "channel": "U先派样",
        "actual_amount": 1.0,
        "is_member": False,
        "is_refund": False,
        "is_goujinjin": False,
        "order_status": "交易成功",
        "product_id": "P_SAMPLE",
        "spu_type": "小样-U先",
    },
    {
        "line_id": "L_SAMPF",
        "order_id": "O_SAMPF",
        "sub_order_id": "S1",
        "user_id": "C_SAMP",
        "pay_date": "2026-09-16",
        "channel": "货架",
        "actual_amount": 600.0,
        "is_member": False,
        "is_refund": False,
        "is_goujinjin": False,
        "order_status": "交易成功",
        "product_id": "P_FULL",
        "spu_type": "正装",
    },
    {
        "line_id": "L_NEWSAMP",
        "order_id": "O_NEWSAMP",
        "sub_order_id": "S1",
        "user_id": "C_NEWSAMP",
        "pay_date": "2026-09-16",
        "channel": "U先派样",
        "actual_amount": 2.0,
        "is_member": False,
        "is_refund": False,
        "is_goujinjin": False,
        "order_status": "交易成功",
        "product_id": "P_SAMPLE",
        "spu_type": "小样-U先",
    },
    {
        "line_id": "L_REF",
        "order_id": "O_REF",
        "sub_order_id": "S1",
        "user_id": "C_REF",
        "pay_date": "2026-09-16",
        "channel": "货架",
        "actual_amount": 700.0,
        "is_member": False,
        "is_refund": True,
        "is_goujinjin": False,
        "order_status": "交易成功",
        "product_id": "P_FULL",
        "spu_type": "正装",
    },
    {
        "line_id": "L_HIST",
        "order_id": "O_HIST",
        "sub_order_id": "S1",
        "user_id": "C_HIST",
        "pay_date": "2026-08-20",
        "channel": "货架",
        "actual_amount": 80.0,
        "is_member": False,
        "is_refund": False,
        "is_goujinjin": False,
        "order_status": "交易成功",
        "product_id": "P_FULL",
        "spu_type": "正装",
    },
    {
        "line_id": "L_SEP10",
        "order_id": "O_SEP10",
        "sub_order_id": "S1",
        "user_id": "C_SEP10",
        "pay_date": "2026-09-10",
        "channel": "货架",
        "actual_amount": 90.0,
        "is_member": False,
        "is_refund": False,
        "is_goujinjin": False,
        "order_status": "交易成功",
        "product_id": "P_FULL",
        "spu_type": "正装",
    },
    {
        "line_id": "L_SEP10R",
        "order_id": "O_SEP10R",
        "sub_order_id": "S1",
        "user_id": "C_SEP10",
        "pay_date": "2026-09-16",
        "channel": "货架",
        "actual_amount": 110.0,
        "is_member": False,
        "is_refund": False,
        "order_status": "交易成功",
        "is_goujinjin": False,
        "product_id": "P_FULL",
        "spu_type": "正装",
    },
)


def _is_gsv(line: dict[str, Any]) -> bool:
    return (
        line["is_goujinjin"] is False
        and line["order_status"] != "交易关闭"
        and line["is_refund"] is False
    )


def _is_gmv(line: dict[str, Any]) -> bool:
    return line["is_goujinjin"] is False and line["order_status"] != "交易关闭"


def _in_window(line: dict[str, Any], start: str, end: str) -> bool:
    return start <= line["pay_date"] <= end


def _first_pay_dates(*, exclude_channels: tuple[str, ...] = ()) -> dict[str, str]:
    """ETL 口径：有效行 MIN(pay_date)；exclude 只用于历史重算路径。"""
    first: dict[str, str] = {}
    for line in GOLDEN_ORDER_LINES:
        if not _is_gsv(line):
            continue
        if line["channel"] in exclude_channels:
            continue
        uid = line["user_id"]
        prev = first.get(uid)
        if prev is None or line["pay_date"] < prev:
            first[uid] = line["pay_date"]
    return first


GOLDEN_FIRST_PURCHASE_INCLUDE_SAMPLE = _first_pay_dates()
GOLDEN_FIRST_PURCHASE_EXCLUDE_SAMPLE = _first_pay_dates(
    exclude_channels=SOURCE_SAMPLING_CHANNELS
)

WINDOW_SEP = {"start": "2026-09-15", "end": "2026-09-21"}
DESIRED_CUTOFF_SEP = "2026-09-14"
MONTH_START_CUTOFF_SEP = "2026-08-31"


def _window_gsv(start: str, end: str, *, exclude_channels: tuple[str, ...] = ()) -> float:
    total = 0.0
    for line in GOLDEN_ORDER_LINES:
        if not _is_gsv(line) or not _in_window(line, start, end):
            continue
        if line["channel"] in exclude_channels:
            continue
        total += float(line["actual_amount"])
    return total


def _window_gmv(start: str, end: str) -> float:
    return sum(
        float(line["actual_amount"])
        for line in GOLDEN_ORDER_LINES
        if _is_gmv(line) and _in_window(line, start, end)
    )


def _users_in_window(
    start: str,
    end: str,
    *,
    exclude_channels: tuple[str, ...] = (),
) -> set[str]:
    users: set[str] = set()
    for line in GOLDEN_ORDER_LINES:
        if not _is_gsv(line) or not _in_window(line, start, end):
            continue
        if line["channel"] in exclude_channels:
            continue
        users.add(line["user_id"])
    return users


def _classify(
    users: set[str],
    cutoff: str,
    first_map: dict[str, str],
) -> dict[str, set[str]]:
    old: set[str] = set()
    new: set[str] = set()
    for uid in users:
        first = first_map[uid]
        if first <= cutoff:
            old.add(uid)
        else:
            new.add(uid)
    return {"old": old, "new": new}


def _user_gsv(
    uid: str,
    start: str,
    end: str,
    *,
    exclude_channels: tuple[str, ...] = (),
) -> float:
    total = 0.0
    for line in GOLDEN_ORDER_LINES:
        if line["user_id"] != uid:
            continue
        if not _is_gsv(line) or not _in_window(line, start, end):
            continue
        if line["channel"] in exclude_channels:
            continue
        total += float(line["actual_amount"])
    return total


def _distinct_orders(uid: str, *, before: str | None = None, as_of: str | None = None) -> set[str]:
    orders: set[str] = set()
    for line in GOLDEN_ORDER_LINES:
        if line["user_id"] != uid or not _is_gsv(line):
            continue
        if before is not None and not (line["pay_date"] < before):
            continue
        if as_of is not None and not (line["pay_date"] <= as_of):
            continue
        orders.add(line["order_id"])
    return orders


def _line_count(uid: str, *, as_of: str) -> int:
    return sum(
        1
        for line in GOLDEN_ORDER_LINES
        if line["user_id"] == uid and _is_gsv(line) and line["pay_date"] <= as_of
    )


# ---------------------------------------------------------------------------
# 手算预期表（比赛口径，不是当前实现输出）
# ---------------------------------------------------------------------------

EXPECTED_DATE_WINDOWS = {
    "t01_mtd_2026_09_01": {
        "today": "2026-09-01",
        "yesterday": "2026-08-31",
        "period_builder_mtd": {
            "current": {"start": "2026-09-01", "end": "2026-09-01", "cutoff": "2026-08-31", "empty": True},
            "comparison": {"start": "2025-09-01", "end": "2025-09-01", "cutoff": "2025-08-31", "empty": True},
            "note": "T+1 月初 EMPTY：不回落 8 月，不造 09-01..09-30",
        },
        "audience_table_or_summary_default_mtd": {
            "current": None,
            "note": "empty_mtd_summary / executed.current_period is None",
        },
        "desired": {
            "current_month_status": "EMPTY",
            "current": None,
            "reason": "T+1 9/1 无本月可用数据，应空态，不比较未来完整 9 月",
        },
        "august_gsv_in_fixture": 81.0,
        "september_gsv_as_of_aug31": 0.0,
    },
    "t01_leap_2024_03_01": {
        "today": "2024-03-01",
        "period_builder_mtd": {
            "current": {"start": "2024-03-01", "end": "2024-03-01", "cutoff": "2024-02-29", "empty": True},
            "comparison": {"start": "2023-03-01", "end": "2023-03-01", "cutoff": "2023-02-28", "empty": True},
            "note": "3/1 T+1 空三月，闰日钳制走 yoy/free 不是 mtd 回落 2 月",
        },
        "desired_yoy_alignment": {
            "rule": "clamp_to_month_end",
            "from": "2024-02-29",
            "to": "2023-02-28",
        },
        "audience_summary_custom_start_2024_02_29": {
            "behavior": "ValueError",
            "code": "date(cur_start_y - 1, cur_start_m, cur_start_d)",
            "path": "backend/services/metrics/audience_summary.py",
        },
        "audience_table_free_2024_02_29": {
            "behavior": "ValueError",
            "code": "datetime(start_dt.year - 1, start_dt.month, start_dt.day)",
            "path": "backend/services/metrics/audience_table.py",
        },
        "leap_gsv": 100.0,
    },
    "t01_wtd_2026_09_16": {
        "today": "2026-09-16",
        "period_builder_wtd": {
            "current": {"start": "2026-09-14", "end": "2026-09-15", "cutoff": "2026-09-13"},
            "comparison": {"start": "2026-09-07", "end": "2026-09-08", "cutoff": "2026-09-06"},
            "note": "comparison = 上周同星期；HTTP /audience/summary 先把 period 折成 start/end 再走自定义 cutoff=月初-1",
        },
    },
    "t01_custom_dual_window": {
        "current": {"start": "2026-09-15", "end": "2026-09-21"},
        "compare_custom": {"start": "2025-11-01", "end": "2025-11-11"},
        "desired_current_cutoff": DESIRED_CUTOFF_SEP,
        "summary_custom_cutoff": MONTH_START_CUTOFF_SEP,
        "http_table_compare_params": "NOT_EXPOSED",
    },
    "t01_end_before_start": {
        "start": "2026-09-21",
        "end": "2026-09-15",
        "audience_summary_validation": "NONE",
        "ad_hoc_validation": "validate_date_window",
    },
}

EXPECTED_NEW_OLD = {
    "window": WINDOW_SEP,
    "desired_cutoff_rule": "analysis_start_minus_1_day",
    "desired_cutoff": DESIRED_CUTOFF_SEP,
    "source_summary_custom_cutoff": MONTH_START_CUTOFF_SEP,
    "source_table_free_cutoff": DESIRED_CUTOFF_SEP,
    "source_overview_cutoff": DESIRED_CUTOFF_SEP,
    "include_sample_first_purchase": GOLDEN_FIRST_PURCHASE_INCLUDE_SAMPLE,
    "users": {
        "C_SEP5": {"first": "2026-09-05", "desired": "old", "summary_month_cutoff": "new"},
        "C_SEP10": {"first": "2026-09-10", "desired": "old", "summary_month_cutoff": "new"},
        "C_MULTI": {"first": "2026-09-16", "desired": "new", "summary_month_cutoff": "new"},
        "C_XCH": {"first": "2025-09-16", "desired": "old", "summary_month_cutoff": "old"},
        "C_UNK": {"first": "2026-09-16", "desired": "new", "summary_month_cutoff": "new"},
        "C_SAMP": {"first": "2026-08-01", "desired": "old", "summary_month_cutoff": "old"},
        "C_NEWSAMP": {"first": "2026-09-16", "desired": "new", "summary_month_cutoff": "new"},
    },
    "desired_old_users": frozenset({"C_SEP5", "C_SEP10", "C_XCH", "C_SAMP"}),
    "desired_new_users": frozenset({"C_MULTI", "C_UNK", "C_NEWSAMP"}),
    "summary_month_old_users": frozenset({"C_XCH", "C_SAMP"}),
}

EXPECTED_GSV = {
    "window": WINDOW_SEP,
    "gsv": 1962.0,
    "gmv": 2662.0,
    "refund_amount_excluded_from_gsv": 700.0,
    "users": 7,
    "member_true_gsv": 800.0,
    "member_false_gsv": 1012.0,
    "member_unknown_gsv": 150.0,
    "desired_old_gsv": 1510.0,
    "desired_new_gsv": 452.0,
    "summary_month_old_gsv": 1100.0,
    "summary_month_new_gsv": 862.0,
    "zero_denominator_ratio": None,
}

EXPECTED_F_GRAIN = {
    "C_MULTI_as_of_2026_09_21": {
        "line_count": 3,
        "distinct_order_id": 1,
        "desired_f": 1,
        "f_flow_hist_extra_cols": "COUNT(*) AS frequency",
        "f_flow_from": "orders grouped by user_id (line grain)",
        "extended_sql": "COUNT(DISTINCT o.order_id)",
        "w4_sql": "COUNT(*) FROM fact_order_header (header grain)",
        "risk": "f_flow COUNT(*) 在明细行上会计成 3，不能未追 CTE 就改；本批不改实现",
    }
}

EXPECTED_R_AS_OF = {
    "C_HIST": {
        "last_pay": "2026-08-20",
        "as_of_2026_09_21_calendar_days": 32,
        "as_of_2026_09_22_no_new_order_calendar_days": 33,
        "f_unchanged": 1,
        "m_unchanged": 80.0,
        "flow_hist_bound": "pay_time < start_dt",
        "flow_r_bucket_as_of": "cutoff = start-1",
        "extended_peek": "pay_time <= as_of_date + INTERVAL '1' DAY",
        "w4_recency": "floor(seconds/86400), not calendar DATEDIFF",
    }
}

EXPECTED_SCOPES = {
    "channel_live_window": {
        "sales_scope": "直播",
        "sales_gsv": 500.0,
        "sales_users": frozenset({"C_XCH"}),
        "history_identity_global": {"C_XCH": "old"},
        "same_channel_history_before_start": {"C_XCH_live_orders": 0},
        "independent_history_scope_param": "NOT_PRESENT",
    }
}

EXPECTED_SAMPLE_PATHS = {
    "channels_used_in_this_fixture_only": SOURCE_SAMPLING_CHANNELS,
    "gift_channel_in_source_not_in_sampling_channels": SOURCE_GIFT_SAMPLE_DB,
    "business_complete_sample_set": "FACT_GAP",
    "include_default": {
        "gsv": 1962.0,
        "old_users": frozenset({"C_SEP5", "C_SEP10", "C_XCH", "C_SAMP"}),
        "new_users": frozenset({"C_MULTI", "C_UNK", "C_NEWSAMP"}),
        "C_SAMP_identity": "old",
        "C_SAMP_f": 2,
    },
    "exclude_current_sales_only": {
        "exclude_from": "period sales",
        "recompute_identity": False,
        "gsv": 1960.0,
        "old_users": frozenset({"C_SEP5", "C_SEP10", "C_XCH", "C_SAMP"}),
        "new_users": frozenset({"C_MULTI", "C_UNK"}),
        "C_SAMP_identity": "old",
        "C_SAMP_f": 2,
        "C_NEWSAMP_in_period": False,
        "source_approx": "audience exclude_channels on base CTE only; user_first_purchase unchanged",
    },
    "exclude_history_recompute": {
        "exclude_from": "period sales + history first/RFM",
        "recompute_identity": True,
        "condition_label": "历史口径已重算",
        "gsv": 1960.0,
        "old_users": frozenset({"C_SEP5", "C_SEP10", "C_XCH"}),
        "new_users": frozenset({"C_MULTI", "C_UNK", "C_SAMP"}),
        "C_SAMP_identity": "new",
        "C_SAMP_f": 1,
        "source_approx": "rfm exclude_channels on hist_customers AND base_orders; not an explicit mode",
    },
    "explicit_sample_mode_param": "NOT_PRESENT",
}

EXPECTED_MEMBER = {
    "schema": "orders.is_member BOOLEAN; no UNKNOWN enum",
    "sql": "is_member = TRUE else not member",
    "C_UNK": {
        "stored": None,
        "current_bucket": "non_member",
        "desired_bucket": "unknown",
    },
    "member_plus_new_old_not_additive": True,
    "historical_member_as_of": "UNSUPPORTED",
    "member_source": "membership_mark + _mark_user_id_history_member overlay; not as_of",
}

SUPPORT_MATRIX = {
    "mtd_month_start_tplus1": "partial",
    "leap_day": "partial",
    "yoy": "partial",
    "wtd_same_weekday": "partial",
    "custom_dual_window": "partial",
    "timezone": "unsupported",
    "data_cutoff_param": "unsupported",
    "empty_current_month": "unsupported",
    "executed_condition_echo": "partial",
    "gsv_explicit": "partial",
    "new_old_start_minus_1": "partial",
    "f_order_grain": "partial",
    "r_as_of": "partial",
    "sales_vs_history_scope": "partial",
    "sample_two_paths": "unsupported",
    "sample_channel_set": "unknown",
    "member_unknown": "unsupported",
    "member_history_as_of": "unknown",
    "product_ids_http": "unsupported",
    "period_passthrough_http_summary": "unsupported",
}

SERVICE_BUT_NOT_HTTP = (
    {
        "param": "product_ids",
        "service": "calculate_audience_summary",
        "http": "/api/v1/audience/summary GET+POST 未暴露",
    },
    {
        "param": "period",
        "service": "calculate_audience_summary(period=)",
        "http": "GET/POST /summary 用 PeriodBuilder 解析后只传 start/end，不传 period",
    },
    {
        "param": "member_only",
        "service": "get_audience_table",
        "http": "/api/v1/audience/table 未暴露",
    },
    {
        "param": "compare_start_date/compare_end_date",
        "service": "get_audience_table 无; calculate_audience_summary 有",
        "http": "/table 无; /summary 有",
    },
    {
        "param": "as_of_date",
        "service": "get_user_rfm_extended",
        "http": "RFM r/f/m-flow 无独立 as_of；extended POST 有",
    },
    {
        "param": "timezone / data_cutoff / sample_mode / history_scope",
        "service": "均不存在",
        "http": "均不存在",
    },
    {
        "param": "exclude_low_price",
        "service": "get_sampling_roi 无此参数",
        "http": "GET /api/v1/sampling/roi 接收但不传入 service",
    },
)

COUNT_STAR_RISKS = (
    {
        "query": "hist_customers ... COUNT(*) AS frequency",
        "files": (
            "backend/services/rfm/f_flow.py",
            "backend/services/rfm/_flow_engine.py",
        ),
        "grain": "FROM orders GROUP BY user_id; orders 唯一键 (order_id, sub_order_id)",
        "verdict": "RISK_LINE_ITEM_F",
        "action_this_batch": "record only",
    },
    {
        "query": "ttl_users_* SELECT COUNT(*) FROM ttl_users_*",
        "files": ("backend/services/rfm/_flow_engine.py",),
        "grain": "ttl_users already GROUP BY user_id",
        "verdict": "USER_GRAIN_OK",
        "action_this_batch": "record only",
    },
    {
        "query": "COUNT(*) AS valid_order_count FROM fact_order_header",
        "files": ("backend/services/analytics/customer_features/compute.py",),
        "grain": "header (synthetic_user_id, order_id)",
        "verdict": "ORDER_GRAIN_OK",
        "action_this_batch": "record only",
    },
    {
        "query": "COUNT(DISTINCT o.order_id) AS order_count",
        "files": ("backend/services/rfm/extended.py",),
        "grain": "distinct order_id",
        "verdict": "ORDER_GRAIN_OK",
        "action_this_batch": "record only",
    },
)


REQUIRED_TABLES = (
    "GOLDEN_ORDER_LINES",
    "GOLDEN_FIRST_PURCHASE_INCLUDE_SAMPLE",
    "EXPECTED_DATE_WINDOWS",
    "EXPECTED_NEW_OLD",
    "EXPECTED_GSV",
    "EXPECTED_F_GRAIN",
    "EXPECTED_R_AS_OF",
    "EXPECTED_SCOPES",
    "EXPECTED_SAMPLE_PATHS",
    "EXPECTED_MEMBER",
    "SUPPORT_MATRIX",
    "SERVICE_BUT_NOT_HTTP",
    "COUNT_STAR_RISKS",
)


class TestCompetitionMetricsFixtureContract:
    def test_not_run_flags(self) -> None:
        assert FIXTURE_ID == "competition-metrics-gold/v1"
        assert COMPUTATION == "NOT_RUN"
        assert HAND_CALCULATED is True
        assert CONTRACT_HASH == "PENDING_C0"

    def test_required_tables_exist(self) -> None:
        namespace = globals()
        for name in REQUIRED_TABLES:
            assert name in namespace
            assert namespace[name]

    def test_source_sample_channels_are_quoted_not_guessed(self) -> None:
        assert SOURCE_SAMPLING_CHANNELS == ("U先派样", "百补派样")
        assert SOURCE_GIFT_SAMPLE_DB == "赠品&0.01渠道"
        assert EXPECTED_SAMPLE_PATHS["business_complete_sample_set"] == "FACT_GAP"
        assert SUPPORT_MATRIX["sample_channel_set"] == "unknown"

    def test_line_grain_unique_key(self) -> None:
        keys = {(row["order_id"], row["sub_order_id"]) for row in GOLDEN_ORDER_LINES}
        assert len(keys) == len(GOLDEN_ORDER_LINES)
        multi = [row for row in GOLDEN_ORDER_LINES if row["order_id"] == "O_MULTI"]
        assert len(multi) == 3


class TestCompetitionMetricsHandGoldens:
    def test_window_gsv_gmv_refund(self) -> None:
        start, end = WINDOW_SEP["start"], WINDOW_SEP["end"]
        assert _window_gsv(start, end) == EXPECTED_GSV["gsv"]
        assert _window_gmv(start, end) == EXPECTED_GSV["gmv"]
        assert EXPECTED_GSV["gmv"] - EXPECTED_GSV["gsv"] == EXPECTED_GSV[
            "refund_amount_excluded_from_gsv"
        ]

    def test_member_unknown_is_third_bucket_in_gold(self) -> None:
        start, end = WINDOW_SEP["start"], WINDOW_SEP["end"]
        member = unknown = non_member = 0.0
        seen: dict[str, Any] = {}
        for line in GOLDEN_ORDER_LINES:
            if not _is_gsv(line) or not _in_window(line, start, end):
                continue
            flag = line["is_member"]
            seen[line["user_id"]] = flag
            if flag is True:
                member += float(line["actual_amount"])
            elif flag is False:
                non_member += float(line["actual_amount"])
            else:
                unknown += float(line["actual_amount"])
        assert member == EXPECTED_GSV["member_true_gsv"]
        assert non_member == EXPECTED_GSV["member_false_gsv"]
        assert unknown == EXPECTED_GSV["member_unknown_gsv"]
        assert seen["C_UNK"] is None
        assert member + non_member + unknown == EXPECTED_GSV["gsv"]
        assert EXPECTED_MEMBER["C_UNK"]["desired_bucket"] == "unknown"
        assert EXPECTED_MEMBER["C_UNK"]["current_bucket"] == "non_member"

    def test_sep5_and_sep10_are_old_under_start_minus_one(self) -> None:
        start, end = WINDOW_SEP["start"], WINDOW_SEP["end"]
        users = _users_in_window(start, end)
        desired = _classify(
            users, DESIRED_CUTOFF_SEP, GOLDEN_FIRST_PURCHASE_INCLUDE_SAMPLE
        )
        month = _classify(
            users, MONTH_START_CUTOFF_SEP, GOLDEN_FIRST_PURCHASE_INCLUDE_SAMPLE
        )
        assert desired["old"] == EXPECTED_NEW_OLD["desired_old_users"]
        assert desired["new"] == EXPECTED_NEW_OLD["desired_new_users"]
        assert month["old"] == EXPECTED_NEW_OLD["summary_month_old_users"]
        assert "C_SEP5" in desired["old"]
        assert "C_SEP5" in month["new"]
        assert "C_SEP10" in desired["old"]
        assert "C_SEP10" in month["new"]
        old_gsv = sum(_user_gsv(uid, start, end) for uid in desired["old"])
        new_gsv = sum(_user_gsv(uid, start, end) for uid in desired["new"])
        assert old_gsv == EXPECTED_GSV["desired_old_gsv"]
        assert new_gsv == EXPECTED_GSV["desired_new_gsv"]
        assert old_gsv + new_gsv == EXPECTED_GSV["gsv"]

    def test_one_order_three_lines_f_is_one(self) -> None:
        as_of = "2026-09-21"
        assert _line_count("C_MULTI", as_of=as_of) == 3
        assert len(_distinct_orders("C_MULTI", as_of=as_of)) == 1
        assert EXPECTED_F_GRAIN["C_MULTI_as_of_2026_09_21"]["desired_f"] == 1

    def test_cross_channel_repurchase(self) -> None:
        start, end = WINDOW_SEP["start"], WINDOW_SEP["end"]
        live = [
            line
            for line in GOLDEN_ORDER_LINES
            if line["user_id"] == "C_XCH"
            and _is_gsv(line)
            and _in_window(line, start, end)
            and line["channel"] == "直播"
        ]
        shelf = [
            line
            for line in GOLDEN_ORDER_LINES
            if line["user_id"] == "C_XCH"
            and _is_gsv(line)
            and _in_window(line, start, end)
            and line["channel"] == "货架"
        ]
        assert len(live) == 1
        assert shelf == []
        assert GOLDEN_FIRST_PURCHASE_INCLUDE_SAMPLE["C_XCH"] == "2025-09-16"
        assert EXPECTED_SCOPES["channel_live_window"]["sales_gsv"] == 500.0

    def test_sample_paths_diverge_on_identity_and_gsv(self) -> None:
        start, end = WINDOW_SEP["start"], WINDOW_SEP["end"]
        include_users = _users_in_window(start, end)
        current_only_users = _users_in_window(
            start, end, exclude_channels=SOURCE_SAMPLING_CHANNELS
        )
        include = _classify(
            include_users, DESIRED_CUTOFF_SEP, GOLDEN_FIRST_PURCHASE_INCLUDE_SAMPLE
        )
        current_only = _classify(
            current_only_users, DESIRED_CUTOFF_SEP, GOLDEN_FIRST_PURCHASE_INCLUDE_SAMPLE
        )
        history = _classify(
            current_only_users,
            DESIRED_CUTOFF_SEP,
            GOLDEN_FIRST_PURCHASE_EXCLUDE_SAMPLE,
        )
        assert include["old"] == EXPECTED_SAMPLE_PATHS["include_default"]["old_users"]
        assert current_only["old"] == EXPECTED_SAMPLE_PATHS[
            "exclude_current_sales_only"
        ]["old_users"]
        assert history["old"] == EXPECTED_SAMPLE_PATHS["exclude_history_recompute"][
            "old_users"
        ]
        assert "C_SAMP" in current_only["old"]
        assert "C_SAMP" in history["new"]
        assert "C_NEWSAMP" in include["new"]
        assert "C_NEWSAMP" not in current_only["new"]
        assert _window_gsv(start, end) == 1962.0
        assert _window_gsv(start, end, exclude_channels=SOURCE_SAMPLING_CHANNELS) == 1960.0
        assert len(_distinct_orders("C_SAMP", as_of="2026-09-21")) == 2
        assert len(
            {
                line["order_id"]
                for line in GOLDEN_ORDER_LINES
                if line["user_id"] == "C_SAMP"
                and _is_gsv(line)
                and line["channel"] not in SOURCE_SAMPLING_CHANNELS
            }
        ) == 1

    def test_r_advances_without_new_orders(self) -> None:
        last = date.fromisoformat("2026-08-20")
        as_of = date.fromisoformat("2026-09-21")
        nxt = date.fromisoformat("2026-09-22")
        assert (as_of - last).days == 32
        assert (nxt - last).days == 33
        assert len(_distinct_orders("C_HIST", as_of="2026-09-22")) == 1

    def test_zero_denominator_is_none_not_zero_percent(self) -> None:
        assert EXPECTED_GSV["zero_denominator_ratio"] is None

    def test_september_first_has_no_month_to_date_sales(self) -> None:
        assert _window_gsv("2026-09-01", "2026-09-01") == 0.0
        assert _window_gsv("2026-08-01", "2026-08-31") == 81.0


class TestCompetitionMetricsPeriodBuilderSnapshot:
    """只读核验语义层日期，不调用 audience SQL。"""

    def test_mtd_september_first_is_empty_not_august(self) -> None:
        ranges = PeriodBuilder.mtd(today=date(2026, 9, 1))
        assert ranges["current"].start == "2026-09-01"
        assert ranges["current"].end == "2026-09-01"
        assert ranges["current"].cutoff == "2026-08-31"
        assert ranges["current"].empty is True
        assert ranges["current"].end != "2026-09-30"
        assert ranges["comparison"].start == "2025-09-01"

    def test_mtd_leap_day_clamps_comparison(self) -> None:
        ranges = PeriodBuilder.mtd(today=date(2024, 3, 1))
        assert ranges["current"].start == "2024-03-01"
        assert ranges["current"].empty is True
        yoy = PeriodBuilder.yoy("2024-02-29", "2024-02-29")
        assert yoy.start == "2023-02-28"
        assert yoy.end == "2023-02-28"
        assert shift_year_clamped(date(2024, 2, 29)) == date(2023, 2, 28)

    def test_wtd_comparison_is_last_week_same_weekday(self) -> None:
        ranges = PeriodBuilder.wtd(today=date(2026, 9, 16))
        current_start = date.fromisoformat(ranges["current"].start)
        compare_start = date.fromisoformat(ranges["comparison"].start)
        assert (current_start - compare_start).days == 7
        assert ranges["current"].start == "2026-09-14"
        assert ranges["comparison"].start == "2026-09-07"

    def test_free_cutoff_is_start_minus_one(self) -> None:
        ranges = PeriodBuilder.free("2026-09-15", "2026-09-21")
        assert ranges["current"].cutoff == DESIRED_CUTOFF_SEP
        assert ranges["comparison"].start == "2025-09-15"

    def test_analysis_cutoff_is_start_minus_one_not_month_start(self) -> None:
        assert analysis_cutoff("2026-09-15").isoformat() == DESIRED_CUTOFF_SEP
        assert analysis_cutoff(date(2026, 9, 15)).isoformat() == DESIRED_CUTOFF_SEP
        month_cutoff = date(2026, 9, 1) - timedelta(days=1)
        assert month_cutoff.isoformat() == MONTH_START_CUTOFF_SEP
        assert analysis_cutoff("2026-09-15") != month_cutoff

    def test_last_week_same_weekday_shifts_closed_window(self) -> None:
        prev = PeriodBuilder.last_week_same_weekday("2026-09-15", "2026-09-21")
        assert prev.start == "2026-09-08"
        assert prev.end == "2026-09-14"
        assert prev.cutoff == "2026-09-07"

    def test_leap_day_free_comparison_clamps(self) -> None:
        ranges = PeriodBuilder.free("2024-02-29", "2024-02-29")
        assert ranges["comparison"].start == "2023-02-28"
        assert ranges["comparison"].end == "2023-02-28"

    def test_september_first_has_no_current_month_data(self) -> None:
        today = date(2026, 9, 1)
        assert current_month_available(today) is False
        assert window_has_no_current_month_data("2026-09-01", "2026-09-30", today=today)
        assert not window_has_no_current_month_data("2026-08-01", "2026-08-31", today=today)


def _seed_golden(conn) -> None:
    conn.execute(
        """
        CREATE TABLE orders (
            order_id VARCHAR,
            sub_order_id VARCHAR,
            user_id VARCHAR,
            pay_time TIMESTAMP,
            channel VARCHAR,
            actual_amount DOUBLE,
            is_member BOOLEAN,
            is_refund BOOLEAN,
            is_goujinjin BOOLEAN,
            order_status VARCHAR,
            product_id VARCHAR,
            spu_type VARCHAR
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE user_first_purchase (
            user_id VARCHAR PRIMARY KEY,
            first_pay_date DATE NOT NULL
        )
        """
    )
    for line in GOLDEN_ORDER_LINES:
        conn.execute(
            """
            INSERT INTO orders VALUES (?, ?, ?, ?::TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                line["order_id"],
                line["sub_order_id"],
                line["user_id"],
                f"{line['pay_date']} 12:00:00",
                line["channel"],
                line["actual_amount"],
                line["is_member"],
                line["is_refund"],
                line["is_goujinjin"],
                line["order_status"],
                line["product_id"],
                line["spu_type"],
            ],
        )
    for user_id, first in GOLDEN_FIRST_PURCHASE_INCLUDE_SAMPLE.items():
        conn.execute(
            "INSERT INTO user_first_purchase VALUES (?, ?::DATE)",
            [user_id, first],
        )


@pytest.fixture
def golden_conn():
    conn = duckdb.connect(":memory:")
    _seed_golden(conn)
    try:
        yield conn
    finally:
        conn.close()


class TestCompetitionMetricsImplementation:
    def test_explicit_gsv_rejects_gmv(self, golden_conn) -> None:
        with pytest.raises(ValueError, match="GSV"):
            compute_competition_metrics(
                golden_conn,
                start_date=WINDOW_SEP["start"],
                end_date=WINDOW_SEP["end"],
                metric_type="GMV",
            )
        with pytest.raises(ValueError, match="GSV"):
            calculate_audience_summary(
                metric_type="GMV",
                start_date=WINDOW_SEP["start"],
                end_date=WINDOW_SEP["end"],
                conn=golden_conn,
            )

    def test_empty_month_on_september_first(self, golden_conn) -> None:
        empty = compute_competition_metrics(
            golden_conn,
            start_date="2026-09-01",
            end_date="2026-09-30",
            today=date(2026, 9, 1),
            as_of="2026-08-31",
        )
        assert empty["completeness"] == "EMPTY"
        assert empty["empty_reason"] == "NO_CURRENT_MONTH_DATA"
        assert empty["executed"]["current_period"] is None
        blob = json.dumps(empty, ensure_ascii=False, default=str)
        assert "2026-08-01" not in blob
        assert "2026-09-30" not in blob
        summary = calculate_audience_summary(today=date(2026, 9, 1), conn=golden_conn)
        assert summary["completeness"] == "EMPTY"
        assert summary["empty_reason"] == "NO_CURRENT_MONTH_DATA"
        assert summary["indicators"] == []
        assert summary["current_period"] is None
        summary_blob = json.dumps(summary, ensure_ascii=False, default=str)
        assert "2026-08-01" not in summary_blob
        assert "2026-09-30" not in summary_blob
        mtd_empty = empty_mtd_summary(today=date(2026, 9, 1), metric_type="GSV")
        mtd_blob = json.dumps(mtd_empty, ensure_ascii=False, default=str)
        assert mtd_empty["current_period"] is None
        assert "2026-09-30" not in mtd_blob
        assert "2026-08-01" not in mtd_blob

    def test_audience_summary_classifies_sep5_as_old(self, golden_conn) -> None:
        computed = compute_competition_metrics(
            golden_conn,
            start_date=WINDOW_SEP["start"],
            end_date=WINDOW_SEP["end"],
        )
        assert computed["executed"]["cutoff"] == DESIRED_CUTOFF_SEP
        assert "C_SEP5" in computed["old_users"]
        assert "C_SEP10" in computed["old_users"]
        assert set(computed["old_users"]) == set(EXPECTED_NEW_OLD["desired_old_users"])
        assert set(computed["new_users"]) == set(EXPECTED_NEW_OLD["desired_new_users"])
        assert computed["gsv"] == EXPECTED_GSV["gsv"]
        assert computed["old_gsv"] == EXPECTED_GSV["desired_old_gsv"]
        assert computed["new_gsv"] == EXPECTED_GSV["desired_new_gsv"]

        summary = calculate_audience_summary(
            start_date=WINDOW_SEP["start"],
            end_date=WINDOW_SEP["end"],
            conn=golden_conn,
        )
        assert summary["executed"]["cutoff"] == DESIRED_CUTOFF_SEP
        assert summary["current_period"]["cutoff"] == DESIRED_CUTOFF_SEP
        assert summary["old_users"] == 4
        assert summary["new_users"] == 3
        assert summary["gsv"] == EXPECTED_GSV["gsv"]

    def test_member_unknown_is_third_bucket(self, golden_conn) -> None:
        computed = compute_competition_metrics(
            golden_conn,
            start_date=WINDOW_SEP["start"],
            end_date=WINDOW_SEP["end"],
        )
        assert computed["member"]["UNKNOWN"]["users"] == ["C_UNK"]
        assert computed["member"]["UNKNOWN"]["gsv"] == EXPECTED_GSV["member_unknown_gsv"]
        assert computed["member"]["MEMBER"]["gsv"] == EXPECTED_GSV["member_true_gsv"]
        assert computed["member"]["NON_MEMBER"]["gsv"] == EXPECTED_GSV["member_false_gsv"]
        assert computed["member_history_status"] == "UNKNOWN"
        summary = calculate_audience_summary(
            start_date=WINDOW_SEP["start"],
            end_date=WINDOW_SEP["end"],
            conn=golden_conn,
        )
        assert summary["unknown_gsv"] == EXPECTED_GSV["member_unknown_gsv"]
        assert summary["unknown_users"] == 1

    def test_sample_mode_three_paths(self, golden_conn) -> None:
        include = compute_competition_metrics(
            golden_conn,
            start_date=WINDOW_SEP["start"],
            end_date=WINDOW_SEP["end"],
            sample_mode="INCLUDE",
        )
        current_only = compute_competition_metrics(
            golden_conn,
            start_date=WINDOW_SEP["start"],
            end_date=WINDOW_SEP["end"],
            sample_mode="EXCLUDE_CURRENT_SALES_ONLY",
            sample_channel_ids=list(SOURCE_SAMPLING_CHANNELS),
        )
        recompute = compute_competition_metrics(
            golden_conn,
            start_date=WINDOW_SEP["start"],
            end_date=WINDOW_SEP["end"],
            sample_mode="EXCLUDE_AND_RECOMPUTE_HISTORY",
            sample_channel_ids=list(SOURCE_SAMPLING_CHANNELS),
        )
        assert include["gsv"] == 1962.0
        assert current_only["gsv"] == 1960.0
        assert recompute["gsv"] == 1960.0
        assert "C_SAMP" in current_only["old_users"]
        assert "C_SAMP" in recompute["new_users"]
        assert "C_NEWSAMP" in include["new_users"]
        assert "C_NEWSAMP" not in current_only["users"]
        assert recompute["executed"]["sample_history_recomputed"] is True
        assert current_only["executed"]["sample_history_recomputed"] is False
        assert include["executed"]["sample_channel_set_status"] == "UNKNOWN"
        with pytest.raises(ValueError, match="sample_channel_ids"):
            compute_competition_metrics(
                golden_conn,
                start_date=WINDOW_SEP["start"],
                end_date=WINDOW_SEP["end"],
                sample_mode="EXCLUDE_CURRENT_SALES_ONLY",
            )

    def test_sales_and_history_scope_are_independent(self, golden_conn) -> None:
        live = compute_competition_metrics(
            golden_conn,
            start_date=WINDOW_SEP["start"],
            end_date=WINDOW_SEP["end"],
            sales_channels=["直播"],
        )
        assert live["gsv"] == 500.0
        assert live["users"] == ["C_XCH"]
        assert live["old_users"] == ["C_XCH"]
        live_hist = compute_competition_metrics(
            golden_conn,
            start_date=WINDOW_SEP["start"],
            end_date=WINDOW_SEP["end"],
            sales_channels=["直播"],
            history_channels=["直播"],
        )
        assert live_hist["users"] == ["C_XCH"]
        assert live_hist["new_users"] == ["C_XCH"]
        assert live_hist["executed"]["sales_scope"]["channels"] == ["直播"]
        assert live_hist["executed"]["history_scope"]["channels"] == ["直播"]

    def test_f_order_grain_and_r_as_of(self, golden_conn) -> None:
        source = inspect.getsource(_run_f_flow_period)
        assert "COUNT(DISTINCT order_id)" in source
        assert "COUNT(*) AS frequency" not in source
        values = compute_rfm_as_of(golden_conn, as_of="2026-09-21")
        assert values["C_MULTI"]["f"] == 1
        assert values["C_MULTI"]["m"] == 300.0
        assert values["C_SAMP"]["f"] == 2
        hist = compute_rfm_as_of(golden_conn, as_of="2026-09-21", user_ids=["C_HIST"])
        assert hist["C_HIST"]["f"] == 1
        assert hist["C_HIST"]["m"] == 80.0
        assert hist["C_HIST"]["r_days"] == 32
        nxt = compute_rfm_as_of(golden_conn, as_of="2026-09-22", user_ids=["C_HIST"])
        assert nxt["C_HIST"]["r_days"] == 33
        assert nxt["C_HIST"]["f"] == 1
        recomputed = compute_rfm_as_of(
            golden_conn,
            as_of="2026-09-21",
            user_ids=["C_SAMP"],
            sample_mode="EXCLUDE_AND_RECOMPUTE_HISTORY",
            sample_channel_ids=list(SOURCE_SAMPLING_CHANNELS),
        )
        assert recomputed["C_SAMP"]["f"] == 1

    def test_extended_as_of_does_not_peek_next_day(self, golden_conn) -> None:
        golden_conn.execute(
            """
            INSERT INTO orders VALUES (
                'O_FUTURE', 'S1', 'C_FUTURE', '2026-09-22 00:00:00', '货架',
                999.0, FALSE, FALSE, FALSE, '交易成功', 'P_FULL', '正装'
            )
            """
        )
        values = compute_rfm_as_of(golden_conn, as_of="2026-09-21", user_ids=["C_FUTURE"])
        assert "C_FUTURE" not in values
        extended = get_user_rfm_extended(golden_conn, ["C_FUTURE"], as_of_date="2026-09-21")
        assert "C_FUTURE" not in extended
        later = compute_rfm_as_of(golden_conn, as_of="2026-09-22", user_ids=["C_FUTURE"])
        assert later["C_FUTURE"]["f"] == 1

    def test_summary_sample_recompute_matches_gold(self, golden_conn) -> None:
        include = calculate_audience_summary(
            start_date=WINDOW_SEP["start"],
            end_date=WINDOW_SEP["end"],
            conn=golden_conn,
        )
        current_only = calculate_audience_summary(
            start_date=WINDOW_SEP["start"],
            end_date=WINDOW_SEP["end"],
            sample_mode="EXCLUDE_CURRENT_SALES_ONLY",
            sample_channel_ids=list(SOURCE_SAMPLING_CHANNELS),
            conn=golden_conn,
        )
        recompute = calculate_audience_summary(
            start_date=WINDOW_SEP["start"],
            end_date=WINDOW_SEP["end"],
            sample_mode="EXCLUDE_AND_RECOMPUTE_HISTORY",
            sample_channel_ids=list(SOURCE_SAMPLING_CHANNELS),
            conn=golden_conn,
        )
        assert include["gsv"] == 1962.0
        assert current_only["gsv"] == 1960.0
        assert recompute["gsv"] == 1960.0
        assert current_only["old_users"] == 4
        assert recompute["old_users"] == 3
        assert recompute["new_users"] == 3
        assert include["executed"]["sample_mode"] == "INCLUDE"


def _seed_a9_path(conn) -> None:
    """A9 T02/T03/T14 手算路径：行额 + dated refunds 表，不读 A9 文件。"""
    conn.execute(
        """
        CREATE TABLE orders (
            order_id VARCHAR,
            sub_order_id VARCHAR,
            user_id VARCHAR,
            pay_time TIMESTAMP,
            channel VARCHAR,
            actual_amount DOUBLE,
            is_member BOOLEAN,
            is_refund BOOLEAN,
            is_goujinjin BOOLEAN,
            order_status VARCHAR,
            product_id VARCHAR,
            spu_type VARCHAR
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE refunds (
            order_id VARCHAR,
            refunded_at DATE,
            amount DOUBLE
        )
        """
    )
    orders = (
        ("O-SEP5", "S1", "U-SEP5", "2026-09-05", "CH_RETAIL", 64.0, None, False, "交易成功", "SKU-R"),
        ("O-TRI", "S1", "U-TRI-LINE", "2026-09-16", "CH_RETAIL", 17.5, None, False, "交易成功", "SKU-A"),
        ("O-TRI", "S2", "U-TRI-LINE", "2026-09-16", "CH_RETAIL", 22.0, None, False, "交易成功", "SKU-B"),
        ("O-TRI", "S3", "U-TRI-LINE", "2026-09-16", "CH_RETAIL", 10.5, None, False, "交易成功", "SKU-C"),
        ("O-S0", "S1", "U-SAMPLE", "2026-08-20", "CH_SAMPLE", 3.0, None, False, "交易成功", "SKU-S"),
        ("O-S1", "S1", "U-SAMPLE", "2026-09-16", "CH_SAMPLE", 3.0, None, False, "交易成功", "SKU-S"),
        ("O-R1", "S1", "U-SAMPLE", "2026-09-18", "CH_RETAIL", 188.0, None, False, "交易成功", "SKU-F"),
        ("O-N1", "S1", "U-NEW", "2026-09-19", "CH_RETAIL", 41.0, None, False, "交易成功", "SKU-N"),
        ("O-D1", "S1", "U-TWO", "2026-09-17", "CH_RETAIL", 12.0, None, False, "交易成功", "SKU-D1"),
        ("O-D2", "S1", "U-TWO", "2026-09-17", "CH_RETAIL", 13.0, None, False, "交易成功", "SKU-D2"),
        ("O-RF", "S1", "U-FULL", "2026-09-16", "CH_RETAIL", 77.0, None, True, "交易关闭", "SKU-RF"),
        ("O-PR", "S1", "U-PART", "2026-09-16", "CH_RETAIL", 90.0, None, False, "交易成功", "SKU-PR"),
        ("O-TR", "S1", "U-TRUNC", "2026-09-16", "CH_RETAIL", 8.0, None, False, "交易成功", "SKU-T"),
    )
    for row in orders:
        conn.execute(
            """
            INSERT INTO orders VALUES (?, ?, ?, ?::TIMESTAMP, ?, ?, ?, ?, FALSE, ?, ?, '正装')
            """,
            [
                row[0], row[1], row[2], f"{row[3]} 12:00:00",
                row[4], row[5], row[6], row[7], row[8], row[9],
            ],
        )
    conn.execute("INSERT INTO refunds VALUES ('O-RF', DATE '2026-09-18', 77.0)")
    conn.execute("INSERT INTO refunds VALUES ('O-PR', DATE '2026-09-18', 27.0)")


@pytest.fixture
def a9_path_conn():
    conn = duckdb.connect(":memory:")
    _seed_a9_path(conn)
    try:
        yield conn
    finally:
        conn.close()


class TestCompetitionMetricsG4Fixes:
    def test_safe_ratio_zero_over_zero_is_null(self) -> None:
        assert safe_ratio(2, 8) == 0.25
        assert safe_ratio(0, 0) is None
        assert safe_ratio(10, 0) == 0.0
        assert safe_ratio(0, 0, default=0.0) == 0.0

    def test_dated_refund_path_exists_in_compute_source(self) -> None:
        source = inspect.getsource(competition_compute_mod)
        assert "refunded_at" in source
        assert "refunds" in source

    def test_u_sep5_zero_period_gsv_stays_old(self, a9_path_conn) -> None:
        metrics = compute_competition_metrics(
            a9_path_conn,
            start_date="2026-09-15",
            end_date="2026-09-21",
            today=date(2026, 9, 22),
            as_of="2026-09-21",
        )
        assert "U-SEP5" in metrics["old_users"]
        assert metrics["old_users"].count("U-SEP5") == 1
        assert len(metrics["old_users"]) == 2
        assert len(metrics["new_users"]) == 5
        assert round(metrics["gsv"], 2) == 378.0

    def test_partial_refund_nets_sixty_three_and_paths(self, a9_path_conn) -> None:
        include = compute_competition_metrics(
            a9_path_conn,
            start_date="2026-09-15",
            end_date="2026-09-21",
            today=date(2026, 9, 22),
            as_of="2026-09-21",
            sample_mode="INCLUDE",
        )
        current_only = compute_competition_metrics(
            a9_path_conn,
            start_date="2026-09-15",
            end_date="2026-09-21",
            today=date(2026, 9, 22),
            as_of="2026-09-21",
            sample_mode="EXCLUDE_CURRENT_SALES_ONLY",
            sample_channel_ids=["CH_SAMPLE"],
        )
        recompute = compute_competition_metrics(
            a9_path_conn,
            start_date="2026-09-15",
            end_date="2026-09-21",
            today=date(2026, 9, 22),
            as_of="2026-09-21",
            sample_mode="EXCLUDE_AND_RECOMPUTE_HISTORY",
            sample_channel_ids=["CH_SAMPLE"],
        )
        retail = compute_competition_metrics(
            a9_path_conn,
            start_date="2026-09-15",
            end_date="2026-09-21",
            today=date(2026, 9, 22),
            as_of="2026-09-21",
            sample_mode="INCLUDE",
            sales_channels=["CH_RETAIL"],
        )
        rfm = compute_rfm_as_of(a9_path_conn, as_of="2026-09-21")
        assert round(rfm["U-PART"]["m"], 2) == 63.0
        assert "U-FULL" not in rfm
        assert int(rfm["U-TRI-LINE"]["f"]) == 1
        assert int(rfm["U-TWO"]["f"]) == 2
        assert round(include["gsv"], 2) == 378.0
        assert round(current_only["gsv"], 2) == 375.0
        assert round(recompute["gsv"], 2) == 375.0
        assert round(retail["gsv"], 2) == 375.0
        assert "U-SEP5" in include["old_users"]
        assert "U-SAMPLE" in current_only["old_users"]
        assert "U-SAMPLE" in recompute["new_users"]
        assert current_only["executed"]["sample_history_recomputed"] is False
        assert recompute["executed"]["sample_history_recomputed"] is True

    def test_t14_late_refund_does_not_peek(self, a9_path_conn) -> None:
        a9_path_conn.execute(
            """
            INSERT INTO orders VALUES (
                'O-LATE', 'S1', 'U-LATE', '2026-09-16 12:00:00', 'CH_RETAIL',
                40.0, NULL, FALSE, FALSE, '交易成功', 'SKU-L', '正装'
            )
            """
        )
        a9_path_conn.execute("INSERT INTO refunds VALUES ('O-LATE', DATE '2026-09-22', 40.0)")
        before = compute_rfm_as_of(a9_path_conn, as_of="2026-09-21", user_ids=["U-LATE"])
        after = compute_rfm_as_of(a9_path_conn, as_of="2026-09-22", user_ids=["U-LATE"])
        assert before["U-LATE"]["f"] == 1
        assert round(before["U-LATE"]["m"], 2) == 40.0
        assert "U-LATE" not in after
        sep5_a = compute_rfm_as_of(a9_path_conn, as_of="2026-09-21", user_ids=["U-SEP5"])
        sep5_b = compute_rfm_as_of(a9_path_conn, as_of="2026-09-22", user_ids=["U-SEP5"])
        assert sep5_a["U-SEP5"]["f"] == sep5_b["U-SEP5"]["f"] == 1
        assert round(sep5_a["U-SEP5"]["m"], 2) == round(sep5_b["U-SEP5"]["m"], 2)
        assert int(sep5_b["U-SEP5"]["r_days"]) == int(sep5_a["U-SEP5"]["r_days"]) + 1
        assert sep5_a["U-SEP5"]["member_status_as_of"] == "UNKNOWN"
        future = compute_rfm_as_of(a9_path_conn, as_of="2026-09-04", user_ids=["U-SEP5"])
        assert "U-SEP5" not in future
        part_before_refund = compute_rfm_as_of(
            a9_path_conn, as_of="2026-09-17", user_ids=["U-PART"]
        )
        assert round(part_before_refund["U-PART"]["m"], 2) == 90.0
        part_after = compute_rfm_as_of(a9_path_conn, as_of="2026-09-18", user_ids=["U-PART"])
        assert round(part_after["U-PART"]["m"], 2) == 63.0


def test_flow_cache_separates_historical_scope():
    from backend.services.rfm._shared import _flow_cache_key

    args = ("f", "2026-08-01", "2026-08-31", None, "GSV", None, None, None, "synthetic")
    baseline = _flow_cache_key(*args)
    channel = _flow_cache_key(*args, history_channels=["one"])
    product = _flow_cache_key(*args, history_product_ids=["one"])
    assert len({baseline, channel, product}) == 3
    assert _flow_cache_key(*args, history_channels=["one", "two"]) == _flow_cache_key(
        *args, history_channels=["two", "one"],
    )
