"""two-year-overview — 两年新老客 30 指标对比。

Sprint 171:
- 只走 backend.services.metrics.audience_summary.calculate_audience_summary
- 输出字段使用 all_*/new_*/old_*/member_* 前缀
- 新文件禁 DuckDB/inline SQL
"""
from __future__ import annotations

from typing import Any, List

from backend.contracts.schemas import AudienceSummaryResponse
from backend.services.metrics.audience_summary import calculate_audience_summary

from scripts.ad_hoc_query_excel_styles import write_table_workbook
from scripts.ad_hoc_queries._utils import clamp_yoy, parse_exclude_channels, validate_date_window
from scripts.ad_hoc_queries.registry import QuerySpec, register

TWO_YEAR_HEADERS = [
    "metric_key",
    "metric_label",
    "current_value",
    "comparison_value",
    "yoy_value",
    "yoy_unit",
]

_FIELD_KEYS = {
    "全店GSV": ("all_gsv", "%"),
    "全店人数": ("all_user_count", "%"),
    "AUS": ("all_aus", "%"),
    "老客GSV": ("old_gsv", "%"),
    "老客人数": ("old_user_count", "%"),
    "老客AUS": ("old_aus", "%"),
    "老客GSV占比": ("old_gsv_share", "pp"),
    "老客人数占比": ("old_user_share", "pp"),
    "新客GSV": ("new_gsv", "%"),
    "新客人数": ("new_user_count", "%"),
    "新客AUS": ("new_aus", "%"),
    "新客GSV占比": ("new_gsv_share", "pp"),
    "新客人数占比": ("new_user_share", "pp"),
    "会员GSV": ("member_gsv", "%"),
    "会员人数": ("member_user_count", "%"),
    "会员AUS": ("member_aus", "%"),
    "会员渗透率": ("member_share", "pp"),
    "会员人数占比": ("member_user_share", "pp"),
    "会员老客GSV": ("member_old_gsv", "%"),
    "会员老客人数": ("member_old_user_count", "%"),
    "会员老客AUS": ("member_old_aus", "%"),
    "会员老客GSV占比": ("member_old_gsv_share", "pp"),
    "会员老客人数占比": ("member_old_user_share", "pp"),
    "会员新客GSV": ("member_new_gsv", "%"),
    "会员新客人数": ("member_new_user_count", "%"),
    "会员新客AUS": ("member_new_aus", "%"),
    "会员新客GSV占比": ("member_new_gsv_share", "pp"),
    "会员新客人数占比": ("member_new_user_share", "pp"),
}


def _build_summary(
    year: int = 2026,
    period: str | None = None,
    start: str | None = None,
    end: str | None = None,
    channel: str | None = None,
    exclude_channels: str | None = None,
    order_ids: list[str] | None = None,
) -> dict[str, Any]:
    if not period:
        if not start or not end:
            raise ValueError("period 为空时必须传 --start 和 --end")
        validate_date_window(start, end)
    result = calculate_audience_summary(
        year=year,
        metric_type="GSV",
        start_date=start,
        end_date=end,
        channel=channel,
        period=period,
        exclude_channels=parse_exclude_channels(exclude_channels),
        order_ids=order_ids,
    )
    AudienceSummaryResponse.model_validate(result)
    return result


def run_two_year_overview(
    year: int = 2026,
    period: str | None = None,
    start: str | None = None,
    end: str | None = None,
    channel: str | None = None,
    exclude_channels: str | None = None,
    order_ids: list[str] | None = None,
) -> List[List[Any]]:
    result = _build_summary(
        year=year,
        period=period,
        start=start,
        end=end,
        channel=channel,
        exclude_channels=exclude_channels,
        order_ids=order_ids,
    )
    current_label = result.get("year_label", str(year))
    comp_label = result.get("comp_year_label", str(year - 1))
    rows: List[List[Any]] = []
    for item in result.get("indicators", []):
        label = item.get("field", "")
        metric_key, unit = _FIELD_KEYS.get(label, (f"all_{label}", "%"))
        values = item.get("values_by_year") or {}
        rows.append([
            metric_key,
            label,
            values.get(current_label),
            values.get(comp_label),
            clamp_yoy(item.get("yoy")),
            unit,
        ])
    return rows


def write_two_year_xlsx(output_path: str | None = None, **kwargs: Any) -> str:
    rows = run_two_year_overview(**kwargs)
    return write_table_workbook(
        headers=TWO_YEAR_HEADERS,
        rows=rows,
        output_path=output_path,
        sheet_name="02_新老客30指标",
        title="新老客30指标",
    )


register(QuerySpec(
    name="two-year-overview",
    description="两年新老客/会员核心指标对比",
    args=[
        {"flags": ("--year",), "required": False, "default": 2026, "type": int, "help": "基准年份"},
        {
            "flags": ("--period",),
            "required": False,
            "default": None,
            "choices": ["wtd", "mtd", "ytd", "q1", "q2", "q3", "q4"],
            "help": "周期快捷方式",
        },
        {"flags": ("--start",), "required": False, "default": None, "help": "起始日期 YYYY-MM-DD"},
        {"flags": ("--end",), "required": False, "default": None, "help": "结束日期 YYYY-MM-DD"},
        {"flags": ("--channel",), "required": False, "default": None, "help": "渠道筛选"},
        {"flags": ("--exclude-channels",), "required": False, "default": None, "help": "排除渠道, 逗号分隔"},
        {"flags": ("--order-ids",), "required": False, "default": None, "nargs": "+", "help": "订单号列表"},
        {
            "flags": ("--format",),
            "required": False,
            "default": "xlsx",
            "choices": ["table", "csv", "xlsx"],
            "help": "输出格式",
        },
        {"flags": ("--output", "-o"), "required": False, "default": None, "help": "输出路径"},
    ],
    headers=TWO_YEAR_HEADERS,
    run=lambda **kw: run_two_year_overview(**kw),
    xlsx_writer=write_two_year_xlsx,
    business_tag="新老客30指标",
    base_year_arg="start",
))
