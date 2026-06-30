"""rfm-repurchase — R 区间复购周期分布。

Sprint 171 防串台硬规则:
- 本文件只走 get_rfm_r_flow，不返回新老客分布
- 字段前缀 r_seg_*，绝不混用 new_*/old_*/member_*
- 跟 new_old_customer.py 完全独立，绝不复用中间 dict / 变量
- R 桶直接复用 backend.semantic.segments.R_SEGMENT_ORDER，不写 R1-R6
- 新文件禁 DuckDB/inline SQL
"""
from __future__ import annotations

from typing import Any, List

from backend.semantic.segments import R_SEGMENT_ORDER
from backend.services.rfm.r_flow import get_rfm_r_flow

from scripts.ad_hoc_query_excel_styles import write_table_workbook
from scripts.ad_hoc_queries._utils import clamp_yoy, parse_exclude_channels, validate_date_window
from scripts.ad_hoc_queries.registry import QuerySpec, register

RFM_HEADERS = [
    "r_seg_name",
    "r_seg_user_count_current",
    "r_seg_repurchase_user_count_current",
    "r_seg_repurchase_rate_pct_current",
    "r_seg_gsv_current",
    "r_seg_aus_current",
    "r_seg_share_pct_current",
    "r_seg_user_count_comp",
    "r_seg_gsv_comp",
    "r_seg_gsv_yoy_pct",
    "r_seg_repurchase_rate_yoy_ppt",
]


def _ratio_to_pct(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value) * 100, 2)


def _safe_aus(amount: Any, users: Any) -> float:
    user_count = int(users or 0)
    return round(float(amount or 0) / user_count, 2) if user_count else 0.0


def run_rfm_repurchase(
    start: str,
    end: str,
    channel: str | None = None,
    exclude_channels: str | None = None,
    year: int = 2026,
) -> List[List[Any]]:
    validate_date_window(start, end)
    result = get_rfm_r_flow(
        year=year,
        metric_type="GSV",
        start_date=start,
        end_date=end,
        channel=channel,
        exclude_channels=parse_exclude_channels(exclude_channels),
    )
    by_segment = {item.get("r_segment"): item for item in result.get("rows", [])}
    rows: List[List[Any]] = []
    for segment_name in R_SEGMENT_ORDER:
        item = by_segment.get(segment_name, {})
        r_seg_gsv_current = item.get("repurchase_gsv_current", 0.0)
        r_seg_users_current = item.get("repurchase_users_current", 0)
        rows.append([
            segment_name,
            item.get("hist_users_current", 0),
            r_seg_users_current,
            _ratio_to_pct(item.get("repurchase_rate_current")),
            r_seg_gsv_current,
            _safe_aus(r_seg_gsv_current, r_seg_users_current),
            _ratio_to_pct(item.get("repurchase_gsv_ratio_current")),
            item.get("hist_users_comp", 0),
            item.get("repurchase_gsv_comp", 0.0),
            clamp_yoy(item.get("yoy_repurchase_gsv")),
            clamp_yoy(item.get("yoy_repurchase_rate")),
        ])
    return rows


def write_rfm_xlsx(output_path: str | None = None, **kwargs: Any) -> str:
    rows = run_rfm_repurchase(**kwargs)
    return write_table_workbook(
        headers=RFM_HEADERS,
        rows=rows,
        output_path=output_path,
        sheet_name="R区间复购",
        title="R区间复购",
    )


register(QuerySpec(
    name="rfm-repurchase",
    description="R 区间复购周期分布，复用 get_rfm_r_flow",
    args=[
        {"flags": ("--start",), "required": True, "help": "起始日期 YYYY-MM-DD"},
        {"flags": ("--end",), "required": True, "help": "结束日期 YYYY-MM-DD"},
        {"flags": ("--channel",), "required": False, "default": None, "help": "渠道筛选"},
        {"flags": ("--exclude-channels",), "required": False, "default": None, "help": "排除渠道, 逗号分隔"},
        {"flags": ("--year",), "required": False, "default": 2026, "type": int, "help": "基准年份"},
        {
            "flags": ("--format",),
            "required": False,
            "default": "xlsx",
            "choices": ["table", "csv", "xlsx"],
            "help": "输出格式",
        },
        {"flags": ("--output", "-o"), "required": False, "default": None, "help": "输出路径"},
    ],
    headers=RFM_HEADERS,
    run=lambda **kw: run_rfm_repurchase(**kw),
    xlsx_writer=write_rfm_xlsx,
    business_tag="R区间复购",
    base_year_arg="start",
))
