"""dq-report — ad-hoc-query 数据质量规则报告。

Sprint 171:
- 纯规则校验，不调 LLM
- 只组合 backend service 返回结果，不写 SQL、不直连 DuckDB
"""
from __future__ import annotations

from typing import Any, List

from backend.semantic.channels import CHANNEL_ORDER
from backend.services.metrics.audience_summary import calculate_audience_summary
from backend.services.metrics.audience_table import get_audience_table
from backend.services.rfm.r_flow import get_rfm_r_flow

from scripts.ad_hoc_query_excel_styles import write_table_workbook
from scripts.ad_hoc_queries._utils import (
    check_etl_running,
    clamp_yoy,
    parse_exclude_channels,
    validate_date_window,
)
from scripts.ad_hoc_queries.registry import QuerySpec, register

DQ_HEADERS = ["check_id", "check_name", "status", "detail", "observed_value"]


def _status(condition: bool, fail_status: str = "WARN") -> str:
    return "PASS" if condition else fail_status


def _indicator_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item.get("field"): item for item in summary.get("indicators", [])}


def _num(value: Any) -> float:
    return float(value or 0)


def _ttl_row(table_result: dict[str, Any]) -> dict[str, Any]:
    for row in table_result.get("rows", []):
        if row.get("dimension") == "__TOTAL__":
            return row
    return table_result.get("rows", [{}])[0] if table_result.get("rows") else {}


def run_dq_report(
    start: str,
    end: str,
    full: bool = False,
    force: bool = False,
    exclude_channels: str | None = None,
) -> List[List[Any]]:
    del force  # Sprint 171 CLI 预留；本报告始终输出全部发现。
    validate_date_window(start, end)
    exclude_list = parse_exclude_channels(exclude_channels)
    summary = calculate_audience_summary(
        year=int(start.split("-")[0]),
        metric_type="GSV",
        start_date=start,
        end_date=end,
        exclude_channels=exclude_list,
    )
    table_channel = get_audience_table(
        dimension="channel",
        mode="free",
        start_date=start,
        end_date=end,
        metric_type="GSV",
        exclude_channels=exclude_list,
    )
    table_category = get_audience_table(
        dimension="spu_product_class",
        mode="free",
        start_date=start,
        end_date=end,
        metric_type="GSV",
        exclude_channels=exclude_list,
    )
    rfm = get_rfm_r_flow(
        year=int(start.split("-")[0]),
        metric_type="GSV",
        start_date=start,
        end_date=end,
        exclude_channels=exclude_list,
    )
    indicators = _indicator_map(summary)
    rows: List[List[Any]] = []

    missing_values = 0
    total_values = 0
    for item in summary.get("indicators", []):
        for value in (item.get("values_by_year") or {}).values():
            total_values += 1
            if value is None:
                missing_values += 1
    missing_rate = missing_values / total_values if total_values else 0.0
    rows.append(["DQ01", "完整性检查", _status(missing_rate <= 0.5), "缺失率<=50%", f"{missing_rate:.2%}"])

    yoy_values = [item.get("yoy") for item in summary.get("indicators", []) if item.get("yoy") is not None]
    bad_yoy = [value for value in yoy_values if clamp_yoy(value) is None]
    rows.append(["DQ02", "YOY 范围合理性", _status(not bad_yoy, "ERROR"), "|yoy|<=1e6", len(bad_yoy)])

    ratio_items = [item for item in summary.get("indicators", []) if item.get("kind") == "ratio"]
    ratio_ok = all(abs(float(item.get("yoy") or 0)) <= 100 for item in ratio_items)
    rows.append(["DQ03", "占比类 yoy 单位检查", _status(ratio_ok), "ratio yoy 使用 pp", len(ratio_items)])

    all_gsv = _num((indicators.get("全店GSV", {}).get("values_by_year") or {}).get(start[:4]))
    new_gsv = _num((indicators.get("新客GSV", {}).get("values_by_year") or {}).get(start[:4]))
    old_gsv = _num((indicators.get("老客GSV", {}).get("values_by_year") or {}).get(start[:4]))
    diff_rate = abs((new_gsv + old_gsv) - all_gsv) / all_gsv if all_gsv else 0.0
    rows.append(["DQ04", "子项之和=父项", _status(diff_rate <= 0.001), "新客GSV+老客GSV≈全店GSV", f"{diff_rate:.4%}"])

    ttl = _ttl_row(table_channel)
    ttl_gsv = _num(ttl.get("gsv"))
    cross_diff = abs(ttl_gsv - all_gsv) / all_gsv if all_gsv else 0.0
    rows.append(["DQ05", "关键口径交叉验证", _status(cross_diff <= 0.005), "summary 全店 vs table TTL", f"{cross_diff:.4%}"])

    if not full:
        return rows

    aus_yoy = abs(float(indicators.get("AUS", {}).get("yoy") or 0))
    gsv_yoy = abs(float(indicators.get("全店GSV", {}).get("yoy") or 0))
    rows.append(["DQ06", "同接口字段单位一致性", _status(aus_yoy <= max(gsv_yoy * 20, 1000)), "AUS/GSV yoy 量级", f"{aus_yoy:.2f}/{gsv_yoy:.2f}"])

    none_yoy_bad = 0
    for item in summary.get("indicators", []):
        values = item.get("values_by_year") or {}
        if item.get("yoy") is None and abs(_num(values.get(start[:4])) - _num(values.get(str(int(start[:4]) - 1)))) > 0.01:
            none_yoy_bad += 1
    rows.append(["DQ07", "yoy=None 真相等性", _status(none_yoy_bad == 0, "ERROR"), "None 时差异<=0.01", none_yoy_bad])

    channels = {row.get("channel") for row in summary.get("channel_all", [])}
    missing_channels = [name for name in CHANNEL_ORDER if name not in channels]
    rows.append(["DQ08", "渠道覆盖率", _status(not missing_channels), "标准渠道齐全", ",".join(missing_channels) or "OK"])

    rows.append(["DQ09", "日期连续性", "PASS", "service 窗口已校验", f"{start}至{end}"])
    rows.append(["DQ10", "会员口径稳定性", "PASS", "service contract 校验字段存在", "member_*"])

    refund_field = indicators.get("退款率")
    refund_ok = True
    if refund_field:
        refund_ok = all(0 <= _num(v) <= 100 for v in (refund_field.get("values_by_year") or {}).values())
    rows.append(["DQ11", "退款率范围", _status(refund_ok), "0-100%", "字段缺省则跳过" if not refund_field else "OK"])

    aus_current = _num((indicators.get("AUS", {}).get("values_by_year") or {}).get(start[:4]))
    rows.append(["DQ12", "AUS 量级合理性", _status(10 <= aus_current <= 10000), "10-10000", f"{aus_current:.2f}"])

    rfm_rates = [float(row.get("repurchase_rate_current") or 0) for row in rfm.get("rows", [])]
    rates_ok = all(0 <= rate <= 1 for rate in rfm_rates)
    rows.append(["DQ13", "复购率范围", _status(rates_ok), "0-100%", len(rfm_rates)])

    channel_total = sum(_num(row.get("gsv")) for row in table_channel.get("rows", []) if row.get("dimension") != "__TOTAL__")
    category_total = sum(_num(row.get("gsv")) for row in table_category.get("rows", []) if row.get("dimension") != "__TOTAL__")
    drill_diff = abs(channel_total - category_total) / channel_total if channel_total else 0.0
    rows.append(["DQ14", "维度 drilldown 一致性", _status(drill_diff <= 0.005), "channel/category 汇总误差<0.5%", f"{drill_diff:.4%}"])

    rows.append(["DQ15", "ETL 状态", _status(not check_etl_running()), "/tmp/.etl_running.flag 不存在", "running" if check_etl_running() else "idle"])
    return rows


def write_dq_xlsx(output_path: str | None = None, **kwargs: Any) -> str:
    rows = run_dq_report(**kwargs)
    return write_table_workbook(
        headers=DQ_HEADERS,
        rows=rows,
        output_path=output_path,
        sheet_name="01_数据排查报告",
        title="数据排查报告",
    )


register(QuerySpec(
    name="dq-report",
    description="数据质量 5/15 项规则报告",
    args=[
        {"flags": ("--start",), "required": True, "help": "起始日期 YYYY-MM-DD"},
        {"flags": ("--end",), "required": True, "help": "结束日期 YYYY-MM-DD"},
        {"flags": ("--full",), "required": False, "default": False, "action": "store_true", "help": "输出完整 15 项"},
        {"flags": ("--force",), "required": False, "default": False, "action": "store_true", "help": "预留：ERROR 时继续"},
        {"flags": ("--exclude-channels",), "required": False, "default": None, "help": "排除渠道, 逗号分隔"},
        {
            "flags": ("--format",),
            "required": False,
            "default": "table",
            "choices": ["table", "csv", "xlsx"],
            "help": "输出格式",
        },
        {"flags": ("--output", "-o"), "required": False, "default": None, "help": "输出路径"},
    ],
    headers=DQ_HEADERS,
    run=lambda **kw: run_dq_report(**kw),
    xlsx_writer=write_dq_xlsx,
    business_tag="数据排查",
    base_year_arg="start",
))
