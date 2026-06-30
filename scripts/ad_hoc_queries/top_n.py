"""top-n — TOP N 品类/产品层级两年对比。

Sprint 171:
- 只走 backend service（category_distribution），不写 SQL
- 输出字段使用 top_* 前缀，避免跟新老客/RFM字段串台
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, List

from backend.semantic.calculations import yoy_absolute
from backend.services.category_service import get_category_distribution

from scripts.ad_hoc_query_excel_styles import write_table_workbook
from scripts.ad_hoc_queries._utils import clamp_yoy, parse_exclude_channels, validate_date_window
from scripts.ad_hoc_queries.registry import QuerySpec, register

TOP_N_HEADERS = [
    "top_dimension_name",
    "top_gsv_current",
    "top_gsv_comp",
    "top_gsv_yoy_pct",
    "top_user_count_current",
    "top_user_count_comp",
    "top_user_count_yoy_pct",
    "top_aus_current",
    "top_aus_comp",
    "top_aus_yoy_pct",
]

_LEVEL_MAP = {
    "spu_category": "category",
    "spu_product_subclass": "subclass",
    "spu_product_class": "class",
}


def _shift_year(day: date, delta_years: int) -> date:
    try:
        return day.replace(year=day.year + delta_years)
    except ValueError:
        return day.replace(year=day.year + delta_years, day=28)


def _aus(amount: Any, count: Any) -> float:
    user_count = int(count or 0)
    return round(float(amount or 0) / user_count, 2) if user_count else 0.0


def run_top_n(
    dimension: str = "spu_category",
    start: str | None = None,
    end: str | None = None,
    exclude_channels: str | None = None,
    limit: int = 20,
) -> List[List[Any]]:
    if not start or not end:
        raise ValueError("top-n 必须传 --start 和 --end")
    validate_date_window(start, end)
    end_day = datetime.strptime(end, "%Y-%m-%d").date()
    start_day = datetime.strptime(start, "%Y-%m-%d").date()
    lookback_days = max((end_day - start_day).days, 0)
    comp_end_day = _shift_year(end_day, -1)
    level = _LEVEL_MAP[dimension]
    exclude_list = parse_exclude_channels(exclude_channels)
    current_result = get_category_distribution(
        date=end,
        lookback_days=lookback_days,
        level=level,
        exclude_channels=exclude_list,
    )
    comp_result = get_category_distribution(
        date=comp_end_day.isoformat(),
        lookback_days=lookback_days,
        level=level,
        exclude_channels=exclude_list,
    )
    comp_by_name = {item.get("name"): item for item in comp_result.get("distribution", [])}
    rows: List[List[Any]] = []
    for item in current_result.get("distribution", [])[:limit]:
        name = item.get("name")
        comp = comp_by_name.get(name, {})
        current_amount = item.get("gmv", 0.0)
        comp_amount = comp.get("gmv", 0.0)
        current_users = item.get("user_count", 0)
        comp_users = comp.get("user_count", 0)
        current_aus = _aus(current_amount, current_users)
        comp_aus = _aus(comp_amount, comp_users)
        rows.append([
            name,
            current_amount,
            comp_amount,
            clamp_yoy(yoy_absolute(float(current_amount or 0), float(comp_amount or 0))),
            current_users,
            comp_users,
            clamp_yoy(yoy_absolute(float(current_users or 0), float(comp_users or 0))),
            current_aus,
            comp_aus,
            clamp_yoy(yoy_absolute(current_aus, comp_aus)),
        ])
    return rows


def write_top_n_xlsx(output_path: str | None = None, **kwargs: Any) -> str:
    rows = run_top_n(**kwargs)
    return write_table_workbook(
        headers=TOP_N_HEADERS,
        rows=rows,
        output_path=output_path,
        sheet_name="TOP维度",
        title="TOP维度",
    )


register(QuerySpec(
    name="top-n",
    description="TOP N 品类/产品层级两年对比",
    args=[
        {
            "flags": ("--dimension",),
            "required": False,
            "default": "spu_category",
            "choices": ["spu_category", "spu_product_subclass", "spu_product_class"],
            "help": "TOP 维度",
        },
        {"flags": ("--start",), "required": True, "help": "起始日期 YYYY-MM-DD"},
        {"flags": ("--end",), "required": True, "help": "结束日期 YYYY-MM-DD"},
        {"flags": ("--exclude-channels",), "required": False, "default": None, "help": "排除渠道, 逗号分隔"},
        {"flags": ("--limit",), "required": False, "default": 20, "type": int, "help": "返回行数"},
        {
            "flags": ("--format",),
            "required": False,
            "default": "xlsx",
            "choices": ["table", "csv", "xlsx"],
            "help": "输出格式",
        },
        {"flags": ("--output", "-o"), "required": False, "default": None, "help": "输出路径"},
    ],
    headers=TOP_N_HEADERS,
    run=lambda **kw: run_top_n(**kw),
    xlsx_writer=write_top_n_xlsx,
    business_tag="TOP20维度",
    base_year_arg="start",
))
