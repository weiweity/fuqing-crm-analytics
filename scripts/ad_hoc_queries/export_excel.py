"""export-excel — Sprint 171 11 sheet 整份报告。

防串台硬规则:
- Sheet 02 独立调用 two-year/new-old service 转换，不复用 RFM 中间结果
- Sheet 04/08 独立调用 get_rfm_r_flow 转换，不复用 Sheet 02 中间结果
- Sheet 09 输出 channel_* 前缀字段
- 新文件禁 DuckDB/inline SQL
"""
from __future__ import annotations

from typing import Any, List

from openpyxl import Workbook

from backend.services.metrics.audience_summary import calculate_audience_summary

from scripts.ad_hoc_query_excel_styles import save_workbook, write_rows_to_sheet
from scripts.ad_hoc_queries._utils import clamp_yoy, parse_exclude_channels, validate_date_window
from scripts.ad_hoc_queries.registry import QuerySpec, register
# 所有 sibling query 改为 lazy import (write_export_excel 函数内):
# 避免循环 import (export_excel → query module → registry → _load_builtins → export_excel).
# Sprint 202+ Sprint 202 Data Query v2.7 暴露 pre-existing 循环 import (Sprint 183 v2.0 抽象沉淀), 1 行 lazy import 真治本.

SHEET_ORDER = [
    "00_说明",
    "01_数据排查报告",
    "02_新老客30指标",
    "03_单品概览TOP20",
    "04_复购周期RFM",
    "05_回购周期RFM",
    "06_连带TOP20",
    "07_品类流转矩阵",
    "08_R区间回购周期",
    "09_渠道概览",
    "10_同品复购与回购店铺",
]

CHANNEL_HEADERS = [
    "channel_name",
    "channel_gsv_current",
    "channel_gsv_comp",
    "channel_gsv_yoy_pct",
    "channel_user_count_current",
    "channel_user_count_comp",
    "channel_user_count_yoy_pct",
    "channel_aus_current",
    "channel_aus_comp",
    "channel_aus_yoy_pct",
    "channel_share_current",
    "channel_share_comp",
    "channel_share_yoy_ppt",
]


def _build_readme_rows(start: str, end: str, exclude_channels: str | None, year: int) -> List[List[Any]]:
    return [
        ["report_start", start],
        ["report_end", end],
        ["report_year", year],
        ["exclude_channels", exclude_channels or ""],
        ["formula_policy", "0 formulas; all values are written by Python"],
        ["style_policy", "header #1F4E79; positive #D32F2F; negative #2E7D32"],
    ]


def _build_channel_rows(start: str, end: str, exclude_channels: str | None, year: int) -> List[List[Any]]:
    validate_date_window(start, end)
    result = calculate_audience_summary(
        year=year,
        metric_type="GSV",
        start_date=start,
        end_date=end,
        exclude_channels=parse_exclude_channels(exclude_channels),
    )
    rows: List[List[Any]] = []
    for item in result.get("channel_all", []):
        rows.append([
            item.get("channel"),
            item.get("gsv_2026"),
            item.get("gsv_2025"),
            clamp_yoy(item.get("yoy")),
            item.get("users_2026"),
            item.get("users_2025"),
            clamp_yoy(item.get("users_yoy")),
            item.get("aus_2026"),
            item.get("aus_2025"),
            clamp_yoy(item.get("aus_yoy")),
            item.get("ratio_2026"),
            item.get("ratio_2025"),
            clamp_yoy(item.get("ratio_yoy")),
        ])
    return rows


def _placeholder_rows(label: str) -> List[List[Any]]:
    return [[label, "TODO 占位 sheet，Sprint 171 不计算该专题"]]


def write_export_excel(
    start: str,
    end: str,
    exclude_channels: str | None = None,
    year: int = 2026,
    output_path: str | None = None,
) -> str:
    # Lazy import: registry 初始化会加载 export_excel；不能在模块导入期反向导入 query module。
    from scripts.ad_hoc_queries.dq_report import DQ_HEADERS, run_dq_report
    from scripts.ad_hoc_queries.rfm_repurchase import RFM_HEADERS, run_rfm_repurchase
    from scripts.ad_hoc_queries.two_year_overview import TWO_YEAR_HEADERS, run_two_year_overview
    from scripts.ad_hoc_queries.top_n import TOP_N_HEADERS, run_top_n

    validate_date_window(start, end)
    workbook = Workbook()
    workbook.remove(workbook.active)

    sheet_payloads = [
        ("00_说明", ["item", "value"], _build_readme_rows(start, end, exclude_channels, year), "说明"),
        ("01_数据排查报告", DQ_HEADERS, run_dq_report(start=start, end=end, full=True, exclude_channels=exclude_channels), "数据排查报告"),
        ("02_新老客30指标", TWO_YEAR_HEADERS, run_two_year_overview(year=year, start=start, end=end, exclude_channels=exclude_channels), "新老客30指标"),
        ("03_单品概览TOP20", TOP_N_HEADERS, run_top_n(dimension="spu_category", start=start, end=end, exclude_channels=exclude_channels, limit=20), "单品概览TOP20"),
        ("04_复购周期RFM", RFM_HEADERS, run_rfm_repurchase(start=start, end=end, exclude_channels=exclude_channels, year=year), "复购周期RFM"),
        ("05_回购周期RFM", ["placeholder_key", "placeholder_note"], _placeholder_rows("category_repurchase_rfm"), "回购周期RFM"),
        ("06_连带TOP20", TOP_N_HEADERS, run_top_n(dimension="spu_product_subclass", start=start, end=end, exclude_channels=exclude_channels, limit=20), "连带TOP20"),
        ("07_品类流转矩阵", ["placeholder_key", "placeholder_note"], _placeholder_rows("category_flow_matrix"), "品类流转矩阵"),
        ("08_R区间回购周期", RFM_HEADERS, run_rfm_repurchase(start=start, end=end, exclude_channels=exclude_channels, year=year), "R区间回购周期"),
        ("09_渠道概览", CHANNEL_HEADERS, _build_channel_rows(start, end, exclude_channels, year), "渠道概览"),
        ("10_同品复购与回购店铺", ["placeholder_key", "placeholder_note"], _placeholder_rows("same_product_store"), "同品复购与回购店铺"),
    ]
    for sheet_name, headers, rows, title in sheet_payloads:
        ws = workbook.create_sheet(sheet_name)
        write_rows_to_sheet(ws, headers=headers, rows=rows, title=title)
    return save_workbook(workbook, output_path, default_name="ad-hoc-export.xlsx")


def run_export_excel_summary(
    start: str,
    end: str,
    exclude_channels: str | None = None,
    year: int = 2026,
) -> List[List[Any]]:
    validate_date_window(start, end)
    return [[idx + 1, name, start, end, exclude_channels or "", year] for idx, name in enumerate(SHEET_ORDER)]


register(QuerySpec(
    name="export-excel",
    description="导出 11 sheet Excel 整份报告",
    args=[
        {"flags": ("--start",), "required": True, "help": "起始日期 YYYY-MM-DD"},
        {"flags": ("--end",), "required": True, "help": "结束日期 YYYY-MM-DD"},
        {"flags": ("--exclude-channels",), "required": False, "default": None, "help": "排除渠道, 逗号分隔"},
        {"flags": ("--year",), "required": False, "default": 2026, "type": int, "help": "基准年份"},
        {
            "flags": ("--format",),
            "required": False,
            "default": "xlsx",
            "choices": ["xlsx"],
            "help": "强制 xlsx",
        },
        {"flags": ("--output", "-o"), "required": False, "default": None, "help": "输出路径"},
    ],
    headers=["sheet_index", "sheet_name", "start", "end", "exclude_channels", "year"],
    run=lambda **kw: run_export_excel_summary(**kw),
    xlsx_writer=write_export_excel,
    business_tag="整份报告",
    base_year_arg="start",
))
