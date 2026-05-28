"""
芙清 CRM - RFM 专项服务（共享模块）

常量、口径定义、日期解析工具。
"""

from typing import Optional
from datetime import date, timedelta, datetime
from calendar import monthrange
from backend.semantic.time import PeriodBuilder

# 语义层统一口径
_VALID_BASE = "is_goujinjin = FALSE AND order_status != '交易关闭'"
_VALID_BASE_T = "o.is_goujinjin = FALSE AND o.order_status != '交易关闭'"

R_SEGMENT_ORDER = [
    "近1个月已购客",
    "近2-3个月已购客",
    "近4-6月已购客",
    "近7-12个月已购客",
    "近13个月-近24个月已购客",
    "2年外已购客",
    "已购客TTL",
]

F_SEGMENT_ORDER = [
    "1次购买",
    "2次购买",
    "3次购买",
    "4次购买",
    "5次及以上",
    "已购客TTL",
]

M_SEGMENT_ORDER = [
    "0-100元",
    "100-300元",
    "300-500元",
    "500-1000元",
    "1000元以上",
    "已购客TTL",
]


def _resolve_date_ranges(
    period: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
):
    """
    解析当前期 / 对比期 / 前年期 的日期范围。
    与 calculate_audience_summary 保持一致。

    当传入 compare_start_date/compare_end_date 时，对比期使用自定义日期
    而不是自动计算的去年同期（支持环比 / 自定义对比）。
    """
    today = date.today()
    current_year_label = str(today.year)
    comp_year_label = str(today.year - 1)
    prev2_year_label = str(today.year - 2)

    if period:
        try:
            pb_func = getattr(PeriodBuilder, period.lower())
            ranges = pb_func(today=today)
            cur_range = ranges["current"]
            comp_range = ranges["comparison"]
            prev2_range = ranges["prev2"]
            cur_start_dt = f"{cur_range.start} 00:00:00"
            cur_end_dt = f"{cur_range.end} 23:59:59"
            ly_start_dt = f"{comp_range.start} 00:00:00"
            ly_end_dt = f"{comp_range.end} 23:59:59"
            y2_start_dt = f"{prev2_range.start} 00:00:00"
            y2_end_dt = f"{prev2_range.end} 23:59:59"
            cutoff = cur_range.cutoff
            ly_cutoff_str = comp_range.cutoff
            y2_cutoff_str = prev2_range.cutoff
            return {
                "current": (cur_start_dt, cur_end_dt, cutoff),
                "comp": (ly_start_dt, ly_end_dt, ly_cutoff_str),
                "prev2": (y2_start_dt, y2_end_dt, y2_cutoff_str),
                "labels": (current_year_label, comp_year_label, prev2_year_label),
            }
        except (AttributeError, KeyError):
            period = None

    if start_date and end_date:
        cur_start_dt = f"{start_date} 00:00:00"
        cur_end_dt = f"{end_date} 23:59:59"
        cur_start_y, cur_start_m, cur_start_d = map(int, start_date.split("-"))
        cur_end_y, cur_end_m, cur_end_d = map(int, end_date.split("-"))
        cutoff_date = date(cur_start_y, cur_start_m, 1) - timedelta(days=1)
        cutoff = cutoff_date.strftime("%Y-%m-%d")

        # ── 对比期：优先使用自定义对比日期（环比 / 自定义）──
        if compare_start_date and compare_end_date:
            comp_start_y, comp_start_m, comp_start_d = map(int, compare_start_date.split("-"))
            ly_start_dt = f"{compare_start_date} 00:00:00"
            ly_end_dt = f"{compare_end_date} 23:59:59"
            ly_cutoff = date(comp_start_y, comp_start_m, 1) - timedelta(days=1)
            ly_cutoff_str = ly_cutoff.strftime("%Y-%m-%d")
            comp_year_label = str(comp_start_y)
        else:
            # 默认：去年同期
            ly_date = date(cur_start_y - 1, cur_start_m, cur_start_d)
            ly_start_dt = f"{ly_date.year}-{ly_date.month:02d}-{ly_date.day:02d} 00:00:00"
            ly_end_year, ly_end_month = cur_end_y - 1, cur_end_m
            ly_end_day = min(cur_end_d, monthrange(ly_end_year, ly_end_month)[1])
            ly_end_dt = f"{ly_end_year}-{ly_end_month:02d}-{ly_end_day:02d} 23:59:59"
            ly_cutoff = date(ly_date.year, ly_date.month, 1) - timedelta(days=1)
            ly_cutoff_str = ly_cutoff.strftime("%Y-%m-%d")
            comp_year_label = str(cur_start_y - 1)

        # prev2 始终为前年同期（固定基准）
        y2_date = date(cur_start_y - 2, cur_start_m, cur_start_d)
        y2_start_dt = f"{y2_date.year}-{y2_date.month:02d}-{y2_date.day:02d} 00:00:00"
        y2_end_year, y2_end_month = cur_end_y - 2, cur_end_m
        y2_end_day = min(cur_end_d, monthrange(y2_end_year, y2_end_month)[1])
        y2_end_dt = f"{y2_end_year}-{y2_end_month:02d}-{y2_end_day:02d} 23:59:59"
        y2_cutoff = date(y2_date.year, y2_date.month, 1) - timedelta(days=1)
        y2_cutoff_str = y2_cutoff.strftime("%Y-%m-%d")

        current_year_label = str(cur_start_y)
        prev2_year_label = str(cur_start_y - 2)

        return {
            "current": (cur_start_dt, cur_end_dt, cutoff),
            "comp": (ly_start_dt, ly_end_dt, ly_cutoff_str),
            "prev2": (y2_start_dt, y2_end_dt, y2_cutoff_str),
            "labels": (current_year_label, comp_year_label, prev2_year_label),
        }

    # 默认 MTD
    yesterday = today - timedelta(days=1)
    cur_month = today.month
    _, last_day_cur = monthrange(today.year, cur_month)
    cur_start = f"{today.year}-{cur_month:02d}-01"
    cur_end = f"{today.year}-{cur_month:02d}-{min(yesterday.day, last_day_cur):02d}"
    cur_start_dt = f"{cur_start} 00:00:00"
    cur_end_dt = f"{cur_end} 23:59:59"
    cutoff = (datetime(today.year, cur_month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

    comp_year = today.year - 1
    _, last_day_comp = monthrange(comp_year, cur_month)
    comp_start = f"{comp_year}-{cur_month:02d}-01"
    comp_end = f"{comp_year}-{cur_month:02d}-{min(yesterday.day, last_day_comp):02d}"
    ly_start_dt = f"{comp_start} 00:00:00"
    ly_end_dt = f"{comp_end} 23:59:59"
    ly_cutoff_str = (datetime(comp_year, cur_month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

    prev2_year = today.year - 2
    _, last_day_prev2 = monthrange(prev2_year, cur_month)
    prev2_start = f"{prev2_year}-{cur_month:02d}-01"
    prev2_end = f"{prev2_year}-{cur_month:02d}-{min(yesterday.day, last_day_prev2):02d}"
    y2_start_dt = f"{prev2_start} 00:00:00"
    y2_end_dt = f"{prev2_end} 23:59:59"
    y2_cutoff_str = (datetime(prev2_year, cur_month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

    return {
        "current": (cur_start_dt, cur_end_dt, cutoff),
        "comp": (ly_start_dt, ly_end_dt, ly_cutoff_str),
        "prev2": (y2_start_dt, y2_end_dt, y2_cutoff_str),
        "labels": (str(today.year), str(comp_year), str(prev2_year)),
    }
