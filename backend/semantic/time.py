"""
Sample CRM - 时间范围构造器

统一处理 MTD、自由模式、环比、同比、回溯期的时间计算。
所有 Service 中的日期逻辑必须通过本模块生成，禁止自行计算。
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Optional


@dataclass
class DateRange:
    start: str   # YYYY-MM-DD
    end: str     # YYYY-MM-DD
    cutoff: str  # YYYY-MM-DD（新老客判定边界 = start - 1天）

    @property
    def start_dt(self) -> str:
        """带时间的开始字符串（00:00:00）"""
        return f"{self.start} 00:00:00"

    @property
    def end_dt(self) -> str:
        """带时间的结束字符串（23:59:59）"""
        return f"{self.end} 23:59:59"


def shift_year_clamped(value: date, years: int = 1) -> date:
    """按自然年平移日期；目标年没有该日时收敛到当月最后一天。"""
    target_year = value.year - years
    target_day = min(value.day, monthrange(target_year, value.month)[1])
    return date(target_year, value.month, target_day)


class PeriodBuilder:
    """
    周期构造器

    支持模式:
    - wtd:  当周 WTD vs 上周 WTD vs 前年同周（默认模式）
    - mtd:  当年 MTD vs 去年 MTD vs 前年 MTD
    - ytd:  当年 YTD vs 去年 YTD vs 前年 YTD
    - free: 自由时间段 vs 去年同期 vs 前年同期
    """

    @staticmethod
    def wtd(today: Optional[date] = None) -> Dict[str, DateRange]:
        """
        构造 WTD 三周期（当周 / 上周 / 前年同周）
        截止昨天（t-1），不含当天。
        """
        today = today or date.today()
        yesterday = today - timedelta(days=1)
        # 当周周一
        days_since_monday = yesterday.weekday()
        current_monday = yesterday - timedelta(days=days_since_monday)

        # 上周同一周期（7天前的同一"星期位置"）
        last_week_start = current_monday - timedelta(days=7)
        last_week_end = yesterday - timedelta(days=7)

        # 前年同周：用 ISO 周定位（不受 1 月 1 日归属影响）
        # ISO 周：(年, 周数, 周几) — Monday=1
        iso_curr = current_monday.isocalendar()
        prev_year = iso_curr[0] - 1
        prev_week = iso_curr[1]
        # ISO 周 53 在某些年份不存在，换成该年最后一周
        try:
            prev2_monday = date.fromisocalendar(prev_year, prev_week, 1)
        except ValueError:
            # 该年没有这一周，用该年最后一周
            prev2_monday = date.fromisocalendar(prev_year, 52, 1)
        # 结束日 = 去年周一 + (当前结束日 - 当前周一) 的天数差
        prev2_end = prev2_monday + (yesterday - current_monday)

        def _make_range(start_dt: date, end_dt: date) -> DateRange:
            cutoff = start_dt - timedelta(days=1)
            return DateRange(
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
                cutoff=cutoff.strftime("%Y-%m-%d")
            )

        return {
            "current": _make_range(current_monday, yesterday),
            "comparison": _make_range(last_week_start, last_week_end),
            "prev2": _make_range(prev2_monday, prev2_end),
        }

    @staticmethod
    def mtd(today: Optional[date] = None) -> Dict[str, DateRange]:
        """
        构造 MTD 三周期（当年 / 去年 / 前年）
        截止昨天（t-1），不含当天。
        """
        today = today or date.today()
        yesterday = today - timedelta(days=1)
        cur_year, cur_month = yesterday.year, yesterday.month
        end_day = yesterday.day

        def _make_range(year: int, month: int, day: int) -> DateRange:
            start = date(year, month, 1)
            safe_day = min(day, monthrange(year, month)[1])
            end = date(year, month, safe_day)
            cutoff = start - timedelta(days=1)
            return DateRange(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), cutoff=cutoff.strftime("%Y-%m-%d"))

        return {
            "current": _make_range(cur_year, cur_month, end_day),
            "comparison": _make_range(cur_year - 1, cur_month, end_day),
            "prev2": _make_range(cur_year - 2, cur_month, end_day),
        }

    @staticmethod
    def ytd(today: Optional[date] = None) -> Dict[str, DateRange]:
        """
        构造 YTD 三周期（当年 / 去年 / 前年）
        截止昨天（t-1），不含当天。
        """
        today = today or date.today()
        yesterday = today - timedelta(days=1)
        cur_year = yesterday.year

        def _make_range(year: int) -> DateRange:
            start = date(year, 1, 1)
            end = date(
                year,
                yesterday.month,
                min(yesterday.day, monthrange(year, yesterday.month)[1]),
            )
            cutoff = date(year - 1, 12, 31)
            return DateRange(
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                cutoff=cutoff.strftime("%Y-%m-%d")
            )

        return {
            "current": _make_range(cur_year),
            "comparison": _make_range(cur_year - 1),
            "prev2": _make_range(cur_year - 2),
        }

    @staticmethod
    def yesterday(today: Optional[date] = None) -> Dict[str, DateRange]:
        """构造昨日单日范围及其同比范围。"""
        today = today or date.today()
        value = today - timedelta(days=1)
        return PeriodBuilder.free(value.isoformat(), value.isoformat())

    @staticmethod
    def quarter(quarter: int, today: Optional[date] = None) -> Dict[str, DateRange]:
        """按前端 Q1-Q4 规则构造当年季度范围。

        当前季度截止昨天；已结束/尚未开始的季度使用该季度自然末日，严格匹配
        ``frontend-vue3/src/utils/date.ts::getPeriodDateRange`` 的 cache key。
        """
        if quarter not in (1, 2, 3, 4):
            raise ValueError(f"quarter must be 1..4, got {quarter}")
        today = today or date.today()
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        start = date(today.year, start_month, 1)
        if start_month <= today.month <= end_month:
            end = today - timedelta(days=1)
            if start > end:
                # 季度首日尚无本季度完整数据，沿用 MTD/WTD 的“完整才切”规则。
                previous_end = start - timedelta(days=1)
                previous_start_month = previous_end.month - 2
                start = date(previous_end.year, previous_start_month, 1)
        else:
            end = date(today.year, end_month, monthrange(today.year, end_month)[1])
        return PeriodBuilder.free(start.isoformat(), end.isoformat())

    @staticmethod
    def q1(today: Optional[date] = None) -> Dict[str, DateRange]:
        return PeriodBuilder.quarter(1, today)

    @staticmethod
    def q2(today: Optional[date] = None) -> Dict[str, DateRange]:
        return PeriodBuilder.quarter(2, today)

    @staticmethod
    def q3(today: Optional[date] = None) -> Dict[str, DateRange]:
        return PeriodBuilder.quarter(3, today)

    @staticmethod
    def q4(today: Optional[date] = None) -> Dict[str, DateRange]:
        return PeriodBuilder.quarter(4, today)

    @staticmethod
    def last90days(today: Optional[date] = None) -> Dict[str, DateRange]:
        """构造近90天三周期（当期 / 去年同期 / 前年同期）。"""
        today = today or date.today()
        yesterday = today - timedelta(days=1)
        start = yesterday - timedelta(days=89)
        return PeriodBuilder.free(start.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d"))

    @staticmethod
    def last180days(today: Optional[date] = None) -> Dict[str, DateRange]:
        """构造近180天三周期（当期 / 去年同期 / 前年同期）"""
        today = today or date.today()
        yesterday = today - timedelta(days=1)
        start = yesterday - timedelta(days=179)
        return PeriodBuilder.free(start.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d"))

    @staticmethod
    def last365days(today: Optional[date] = None) -> Dict[str, DateRange]:
        """构造近365天三周期（当期 / 去年同期 / 前年同期）"""
        today = today or date.today()
        yesterday = today - timedelta(days=1)
        start = yesterday - timedelta(days=364)
        return PeriodBuilder.free(start.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d"))

    @staticmethod
    def free(start_date: str, end_date: str) -> Dict[str, DateRange]:
        """
        构造自由时间段三周期（当年 / 去年 / 前年）
        """
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

        def _shift_range(s: date, e: date, years: int) -> DateRange:
            ns = shift_year_clamped(s, years)
            ne = shift_year_clamped(e, years)
            cutoff = ns - timedelta(days=1)
            return DateRange(start=ns.strftime("%Y-%m-%d"), end=ne.strftime("%Y-%m-%d"), cutoff=cutoff.strftime("%Y-%m-%d"))

        current = DateRange(
            start=start_date,
            end=end_date,
            cutoff=(start_dt - timedelta(days=1)).strftime("%Y-%m-%d"),
        )

        return {
            "current": current,
            "comparison": _shift_range(start_dt, end_dt, 1),
            "prev2": _shift_range(start_dt, end_dt, 2),
        }

    @staticmethod
    def lookback(date_str: str, lookback_days: int) -> DateRange:
        """
        构造回溯期（end=date_str, start=date_str - lookback_days）
        """
        end_dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        start_dt = end_dt - timedelta(days=lookback_days)
        return DateRange(
            start=start_dt.strftime("%Y-%m-%d"),
            end=end_dt.strftime("%Y-%m-%d"),
            cutoff=(start_dt - timedelta(days=1)).strftime("%Y-%m-%d"),
        )

    @staticmethod
    def mom(start_date: str, end_date: str) -> DateRange:
        """
        构造环比周期（前一个等长周期）
        """
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        period_days = (end_dt - start_dt).days + 1

        prev_start = start_dt - timedelta(days=period_days)
        prev_end = start_dt - timedelta(days=1)
        return DateRange(
            start=prev_start.strftime("%Y-%m-%d"),
            end=prev_end.strftime("%Y-%m-%d"),
            cutoff=(prev_start - timedelta(days=1)).strftime("%Y-%m-%d"),
        )

    @staticmethod
    def yoy(start_date: str, end_date: str) -> DateRange:
        """
        构造同比周期（去年同月同期）
        """
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        previous_start = shift_year_clamped(start_dt)
        previous_end = shift_year_clamped(end_dt)
        return DateRange(
            start=previous_start.strftime("%Y-%m-%d"),
            end=previous_end.strftime("%Y-%m-%d"),
            cutoff=(previous_start - timedelta(days=1)).strftime("%Y-%m-%d"),
        )

    @staticmethod
    def normalize_date_string(date_val) -> str:
        """统一日期格式处理（兼容 date 对象和字符串）"""
        if hasattr(date_val, 'strftime'):
            return date_val.strftime("%Y-%m-%d")
        if isinstance(date_val, str):
            return date_val[:10] if len(date_val) > 10 else date_val
        return str(date_val)


def check_future_date(date_str: str) -> str | None:
    """
    检查日期是否在明天之后（未来日期）。

    返回 None 表示日期正常。
    返回 str 表示警告消息（未来日期，HTTP header safe）。

    AI-开发者友好：明确告知数据范围，避免静默返回全 0 误导决策。
    注意：返回值必须为 ASCII（HTTP header latin-1 限制）。
    """
    if date_str is None:
        return None
    try:
        from datetime import date
        from datetime import datetime as dt
        input_date = dt.strptime(date_str, "%Y-%m-%d").date()
        # 今天不算未来，明天及以后才算
        if input_date > date.today():
            return f"date {date_str} is in the future, data will be all-zero. Use date <= today."
        return None
    except (ValueError, TypeError):
        # 日期格式不对或 None，不触发警告，静待 Pydantic 的格式校验
        return None


def normalize_date(date_val) -> str:
    """统一日期格式处理（兼容 date 对象和字符串）"""
    if hasattr(date_val, 'strftime'):
        return date_val.strftime("%Y-%m-%d")
    if isinstance(date_val, str):
        return date_val[:10] if len(date_val) > 10 else date_val
    return str(date_val)
