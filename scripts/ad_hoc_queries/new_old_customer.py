"""new-old-customer — 新老客拆分对比。

Sprint 171 防串台硬规则:
- 本文件只走 get_audience_table，不返回 R 区间分布
- 字段前缀 new_*/old_*/member_*/all_*，绝不混用 r_seg_*
- 跟 rfm_repurchase.py 完全独立，绝不复用中间 dict / 变量
- 新文件禁 DuckDB/inline SQL
"""
from __future__ import annotations

from typing import Any, List

from backend.contracts.schemas import AudienceTableResponse
from backend.services.metrics.audience_table import get_audience_table

from scripts.ad_hoc_query_excel_styles import write_table_workbook
from scripts.ad_hoc_queries._utils import clamp_yoy, parse_exclude_channels, validate_date_window
from scripts.ad_hoc_queries.registry import QuerySpec, register

NEW_OLD_HEADERS = [
    "dimension_name",
    "all_gsv_current",
    "all_gsv_comp",
    "all_gsv_yoy_pct",
    "new_gsv_current",
    "new_gsv_comp",
    "new_gsv_yoy_pct",
    "old_gsv_current",
    "old_gsv_comp",
    "old_gsv_yoy_pct",
    "new_user_count_current",
    "new_user_count_comp",
    "new_user_count_yoy_pct",
    "old_user_count_current",
    "old_user_count_comp",
    "old_user_count_yoy_pct",
    "new_aus_current",
    "new_aus_comp",
    "new_aus_yoy_pct",
    "old_aus_current",
    "old_aus_comp",
    "old_aus_yoy_pct",
    "new_gsv_share_current",
    "new_gsv_share_comp",
    "new_gsv_share_yoy_ppt",
    "old_gsv_share_current",
    "old_gsv_share_comp",
    "old_gsv_share_yoy_ppt",
    "member_gsv_current",
    "member_gsv_comp",
    "member_gsv_yoy_pct",
]

_DIMENSION_MAP = {
    "channel": "channel",
    "category": "spu_product_class",
}


def run_new_old_customer(
    start: str,
    end: str,
    exclude_channels: str | None = None,
    dimension: str = "channel",
) -> List[List[Any]]:
    validate_date_window(start, end)
    service_dimension = _DIMENSION_MAP.get(dimension, dimension)
    result = get_audience_table(
        dimension=service_dimension,
        mode="free",
        start_date=start,
        end_date=end,
        metric_type="GSV",
        exclude_channels=parse_exclude_channels(exclude_channels),
    )
    AudienceTableResponse.model_validate(result)
    rows: List[List[Any]] = []
    for item in result.get("rows", []):
        rows.append([
            item.get("dimension"),
            item.get("gsv"),
            item.get("comp_gsv"),
            clamp_yoy(item.get("yoy_gsv")),
            item.get("new_gsv"),
            item.get("comp_new_gsv"),
            clamp_yoy(item.get("yoy_new_gsv")),
            item.get("old_gsv"),
            item.get("comp_old_gsv"),
            clamp_yoy(item.get("yoy_old_gsv")),
            item.get("new_users"),
            item.get("comp_new_users"),
            clamp_yoy(item.get("yoy_new_users")),
            item.get("old_users"),
            item.get("comp_old_users"),
            clamp_yoy(item.get("yoy_old_users")),
            item.get("new_aus"),
            item.get("comp_new_aus"),
            clamp_yoy(item.get("yoy_new_aus")),
            item.get("old_aus"),
            item.get("comp_old_aus"),
            clamp_yoy(item.get("yoy_old_aus")),
            item.get("new_gsv_ratio"),
            item.get("comp_new_gsv_ratio"),
            clamp_yoy(item.get("yoy_new_gsv_ratio_ppt")),
            item.get("old_gsv_ratio"),
            item.get("comp_old_gsv_ratio"),
            clamp_yoy(item.get("yoy_old_gsv_ratio_ppt")),
            item.get("member_gsv"),
            item.get("comp_member_gsv"),
            clamp_yoy(item.get("yoy_member_gsv")),
        ])
    return rows


def write_new_old_xlsx(output_path: str | None = None, **kwargs: Any) -> str:
    rows = run_new_old_customer(**kwargs)
    return write_table_workbook(
        headers=NEW_OLD_HEADERS,
        rows=rows,
        output_path=output_path,
        sheet_name="新老客拆分",
        title="新老客拆分",
    )


register(QuerySpec(
    name="new-old-customer",
    description="新老客拆分对比，字段前缀隔离",
    args=[
        {"flags": ("--start",), "required": True, "help": "起始日期 YYYY-MM-DD"},
        {"flags": ("--end",), "required": True, "help": "结束日期 YYYY-MM-DD"},
        {"flags": ("--exclude-channels",), "required": False, "default": None, "help": "排除渠道, 逗号分隔"},
        {
            "flags": ("--dimension",),
            "required": False,
            "default": "channel",
            "choices": ["channel", "category"],
            "help": "维度",
        },
        {
            "flags": ("--format",),
            "required": False,
            "default": "xlsx",
            "choices": ["table", "csv", "xlsx"],
            "help": "输出格式",
        },
        {"flags": ("--output", "-o"), "required": False, "default": None, "help": "输出路径"},
    ],
    headers=NEW_OLD_HEADERS,
    run=lambda **kw: run_new_old_customer(**kw),
    xlsx_writer=write_new_old_xlsx,
    business_tag="新老客拆分",
    base_year_arg="start",
))
