"""fixed-product-list-compare-http — Sprint 197 HTTP wrapper.

This CLI/MCP query calls the backend ad-hoc HTTP API instead of opening a
DuckDB read_only connection in a child process.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import requests

from scripts.ad_hoc_queries.registry import QuerySpec, register

UVICORN_BASE_URL = os.environ.get("FQ_CRM_BASE_URL", "http://localhost:8000")
AUTH_TOKEN_ENV = "FQ_CRM_AUTH_TOKEN"


def _auth_headers(auth_token: str | None = None) -> dict[str, str]:
    token = auth_token or os.environ.get(AUTH_TOKEN_ENV)
    return {"Authorization": f"Bearer {token}"} if token else {}


def _period_label(start_date: str, end_date: str) -> str:
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    return f"Y{start.year % 100:02d} {start.month}/{start.day}-{end.month}/{end.day}"


def _shift_year(value: str, offset: int) -> str:
    parsed = datetime.strptime(value, "%Y-%m-%d").date()
    try:
        return parsed.replace(year=parsed.year + offset).isoformat()
    except ValueError:
        return parsed.replace(year=parsed.year + offset, day=28).isoformat()


def _make_header(start_date: str, end_date: str, mom_start_date: str, mom_end_date: str) -> list[str]:
    current_label = _period_label(start_date, end_date)
    yoy_label = _period_label(_shift_year(start_date, -1), _shift_year(end_date, -1))
    mom_label = _period_label(mom_start_date, mom_end_date)
    header = ["链接归类", "单品归类", "商品ID"]
    for section_name in [current_label, "同比", "环比", yoy_label, mom_label]:
        for metric in ["老客", "老客GSV", "老客客单", "新客", "新客GSV", "新客客单"]:
            header.append(f"{section_name}_{metric}")
    return header


def run_fixed_product_list_compare_http(
    start_date: str,
    end_date: str,
    product_ids: list[str] | None = None,
    mom_start_date: str | None = None,
    mom_end_date: str | None = None,
    auth_token: str | None = None,
    base_url: str = UVICORN_BASE_URL,
) -> list[list[Any]]:
    """Call backend HTTP API; never uses scripts.ad_hoc_queries._utils.read_only_conn."""
    payload: dict[str, Any] = {
        "start_date": start_date,
        "end_date": end_date,
        "product_ids": product_ids,
        "mom_start_date": mom_start_date,
        "mom_end_date": mom_end_date,
    }
    response = requests.post(
        f"{base_url.rstrip('/')}/api/v1/ad-hoc/fixed-product-list-compare",
        json=payload,
        headers=_auth_headers(auth_token),
        timeout=300,
    )
    response.raise_for_status()
    data = response.json()
    return data["rows"]


_fixed_product_list_compare_http_spec = QuerySpec(
    name="fixed-product-list-compare-http",
    description=(
        "固定 product_id 清单 + 新老客 + 两年对比 + TTL/单品层级 "
        "(HTTP API, 0 DuckDB 子进程锁冲突, Sprint 197)"
    ),
    args=[
        {"flags": ("--start-date",), "required": True, "help": "起始日期 YYYY-MM-DD"},
        {"flags": ("--end-date",), "required": True, "help": "结束日期 YYYY-MM-DD"},
        {
            "flags": ("--product-ids",),
            "required": False,
            "nargs": "+",
            "default": None,
            "help": "产品 ID 列表; 不传则用归档固定清单",
        },
        {"flags": ("--mom-start-date",), "required": False, "default": None, "help": "环比期起始日期"},
        {"flags": ("--mom-end-date",), "required": False, "default": None, "help": "环比期结束日期"},
        {
            "flags": ("--format",),
            "required": False,
            "default": "table",
            "choices": ["table", "csv", "xlsx"],
        },
        {"flags": ("--auth-token",), "required": False, "default": None, "help": "Bearer token; 默认读 FQ_CRM_AUTH_TOKEN"},
        {"flags": ("--output", "-o"), "required": False, "default": None},
    ],
    headers=_make_header("2026-05-06", "2026-06-21", "2025-09-29", "2025-11-14"),
    run=lambda **kw: run_fixed_product_list_compare_http(**kw),
    business_tag="固定清单单品对比 HTTP",
    base_year_arg="start_date",
)
register(_fixed_product_list_compare_http_spec)
