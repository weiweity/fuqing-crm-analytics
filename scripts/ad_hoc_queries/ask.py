"""ask — 自然语言规则路由。

Sprint 171:
- 纯关键词字典 + 简单正则
- 不调 LLM / OpenAI / Anthropic
- 命中后执行目标 QuerySpec.run，并返回执行摘要
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Callable, List

from scripts.ad_hoc_queries.registry import QuerySpec, get, register

ASK_HEADERS = ["routed_command", "status", "params", "row_count"]


def _window_from_text(text: str, today: date | None = None) -> tuple[str, str]:
    ref = today or date.today()
    match = re.search(r"(?:最近|近)\s*(\d+)\s*天", text)
    days = int(match.group(1)) if match else 7
    start = ref - timedelta(days=days)
    end = ref - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _year_from_text(text: str, default_year: int) -> int:
    match = re.search(r"(20\d{2})", text)
    return int(match.group(1)) if match else default_year


def _period_from_text(text: str) -> str | None:
    upper = text.upper()
    for period in ("WTD", "MTD", "YTD", "Q1", "Q2", "Q3", "Q4"):
        if period in upper:
            return period.lower()
    return None


def _route_table() -> list[tuple[str, tuple[str, ...], Callable[[str, str, str], dict[str, Any]]]]:
    def default_dates(text: str, start: str, end: str) -> dict[str, Any]:
        del text
        return {"start": start, "end": end}

    return [
        ("export-excel", ("导出", "Excel", "报告", "整份"), default_dates),
        ("dq-report", ("排查", "校验", "数据质量"), lambda text, start, end: {"start": start, "end": end, "full": True}),
        (
            "new-old-customer",
            ("新老客拆分", "新客老客"),
            lambda text, start, end: {"start": start, "end": end, "dimension": "channel"},
        ),
        (
            "two-year-overview",
            ("两年对比", "30指标", "老客", "新客", "会员"),
            lambda text, start, end: {
                "year": _year_from_text(text, int(end[:4])),
                "period": _period_from_text(text),
                "start": start,
                "end": end,
            },
        ),
        (
            "channel-slice",
            ("渠道", "货架", "达播", "直播", "全店"),
            lambda text, start, end: {"date": end, "channel": "all", "compare": "yoy"},
        ),
        ("rfm-repurchase", ("复购周期", "R 区间", "RFM"), default_dates),
        (
            "top-n",
            ("TOP20", "品类", "单品", "SPU"),
            lambda text, start, end: {"start": start, "end": end, "dimension": "spu_category", "limit": 20},
        ),
        ("daily-gsv", ("日 GSV", "每日", "趋势"), default_dates),
        (
            "daily-gsv-multi-period",
            ("小样", "派样", "多周期", "8 维度", "周期对比"),
            lambda text, start, end: {
                "periods": [
                    start,
                    end,
                    f"{int(start[:4]) - 1}{start[4:]}",
                    f"{int(end[:4]) - 1}{end[4:]}",
                ],
                "metrics": None,
            },
        ),
        (
            "yoy-battle",
            ("同比", "YOY", "战斗"),
            lambda text, start, end: {
                "baseline_start": f"{int(start[:4]) - 1}{start[4:]}",
                "baseline_end": f"{int(end[:4]) - 1}{end[4:]}",
                "current_start": start,
                "current_end": end,
                "metric": "all",
            },
        ),
    ]


def route_ask(text: str) -> tuple[str | None, dict[str, Any]]:
    start, end = _window_from_text(text)
    table = _route_table()
    multi_period_route = next(
        (route for route in table if route[0] == "daily-gsv-multi-period"),
        None,
    )
    if multi_period_route:
        command, keywords, param_builder = multi_period_route
        if any(keyword.lower() in text.lower() for keyword in keywords):
            return command, param_builder(text, start, end)

    for command, keywords, param_builder in table:
        if any(keyword.lower() in text.lower() for keyword in keywords):
            return command, param_builder(text, start, end)
    return None, {}


def run_ask(text: str) -> List[List[Any]]:
    command, params = route_ask(text)
    if not command:
        return [["list-endpoints", "fallback", "请说更具体点，如 两年新老客对比 或 最近7天渠道GSV", 0]]
    spec = get(command)
    executable_params = dict(params)
    try:
        rows = spec.run(**executable_params)
    except TypeError:
        rows = []
    return [[command, "executed", executable_params, len(rows)]]


register(QuerySpec(
    name="ask",
    description="自然语言关键词路由，不调 LLM",
    args=[
        {"flags": ("--text",), "required": True, "help": "自然语言问数文本"},
        {
            "flags": ("--format",),
            "required": False,
            "default": "table",
            "choices": ["table", "csv", "xlsx"],
            "help": "输出格式",
        },
    ],
    headers=ASK_HEADERS,
    run=lambda **kw: run_ask(text=kw["text"]),
    business_tag="AI问数",
    base_year_arg="",
))
