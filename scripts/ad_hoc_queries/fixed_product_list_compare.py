"""fixed-product-list-compare — Sprint 196 fixed product list compare tool.

This query replaces the archived one-off script
``scripts/_archive/adhoc_product_new_old.py`` with a registered ad-hoc-query
entry. Metric math stays in ``calculate_audience_summary``; this file only
orchestrates product lists, row layout, and XLSX output.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from typing import Any

from backend.services.metrics.audience_summary import calculate_audience_summary

from scripts.ad_hoc_query_excel_styles import write_table_workbook
from scripts.ad_hoc_queries._utils import build_take_path, validate_date_window
from scripts.ad_hoc_queries.registry import QuerySpec, register

# fmt: off
PRODUCT_IDS = [
    # 妆品
    "803474428381", "870597889980", "683395365107", "660012488593", "803417397714",
    "654390297284", "753548858886", "674944410250", "900975734816", "800903824350",
    "656561260141", "912388775061", "933524395698", "781713844237", "1010458880710",
    "1009707365820", "680535358203", "831602598308", "967971403905", "978994528428",
    # 械品
    "597655781410", "587051744204", "587554886491", "601760206476", "587053192746",
    "612503357090", "781706928918", "871040351635", "684155734133", "836974872996",
    "627423052420", "847821870403",
    # 淘客品
    "621639424901", "773698929360", "789483733628",
]

CATEGORY_GROUPS = {
    "妆品销售TTL": [
        "803474428381", "870597889980", "683395365107", "660012488593", "803417397714",
        "654390297284", "753548858886", "674944410250", "900975734816", "800903824350",
        "656561260141", "912388775061", "933524395698", "781713844237", "1010458880710",
        "1009707365820", "680535358203", "831602598308", "967971403905", "978994528428",
    ],
    "械品销售TTL": [
        "597655781410", "587051744204", "587554886491", "601760206476", "587053192746",
        "612503357090", "781706928918", "871040351635", "684155734133", "836974872996",
        "627423052420", "847821870403",
    ],
    "淘客品销售TTL": [
        "621639424901", "773698929360", "789483733628",
    ],
}
# fmt: on

DEFAULT_MOM_WINDOWS = {
    ("2026-05-06", "2026-06-21"): ("2025-09-29", "2025-11-14"),
}

BUSINESS_TAG = "固定清单单品对比"


def _make_header(start_date: str, end_date: str, mom_start_date: str, mom_end_date: str) -> list[str]:
    current_label = _period_label(start_date, end_date)
    yoy_label = _period_label(_shift_year(start_date, -1), _shift_year(end_date, -1))
    mom_label = _period_label(mom_start_date, mom_end_date)
    header = ["链接归类", "单品归类", "商品ID"]
    sections = [
        (current_label, False),
        ("同比", True),
        ("环比", True),
        (yoy_label, False),
        (mom_label, False),
    ]
    for section_name, _is_delta in sections:
        for metric in ["老客", "老客GSV", "老客客单", "新客", "新客GSV", "新客客单"]:
            header.append(f"{section_name}_{metric}")
    return header


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


def _default_mom_window(start_date: str, end_date: str) -> tuple[str, str]:
    if (start_date, end_date) in DEFAULT_MOM_WINDOWS:
        return DEFAULT_MOM_WINDOWS[(start_date, end_date)]
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    span = end - start
    mom_end = start - timedelta(days=1)
    mom_start = mom_end - span
    return mom_start.isoformat(), mom_end.isoformat()


def _safe_yoy(cur: Any, comp: Any) -> float | None:
    if cur is None or comp is None:
        return None
    cur_f = float(cur)
    comp_f = float(comp)
    if comp_f == 0:
        return None
    return round((cur_f - comp_f) / comp_f * 100, 2)


def _n(value: Any) -> float:
    return float(value) if value is not None else 0.0


def _safe_int(value: Any) -> int:
    return int(value) if value is not None else 0


def _extract_period_metrics(result: dict[str, Any], suffix: str) -> dict[str, float | int]:
    ttl = next(
        (row for row in result.get("channel_all", []) if row.get("channel") == "TTL"),
        {},
    )
    old_users = _safe_int(ttl.get(f"old_users_{suffix}"))
    old_gsv = _n(ttl.get(f"old_gsv_{suffix}"))
    old_aus = _n(ttl.get(f"old_aus_{suffix}"))
    new_users = _safe_int(ttl.get(f"new_users_{suffix}"))
    new_gsv = _n(ttl.get(f"new_gsv_{suffix}"))
    new_aus = _n(ttl.get(f"new_aus_{suffix}"))
    return {
        "old_users": old_users,
        "old_gsv": old_gsv,
        "old_aus": round(old_aus, 2),
        "new_users": new_users,
        "new_gsv": new_gsv,
        "new_aus": round(new_aus, 2),
    }


def _period_metrics(
    product_ids: list[str],
    start_date: str,
    end_date: str,
    compare_start_date: str,
    compare_end_date: str,
) -> tuple[dict[str, float | int], dict[str, float | int]]:
    result = calculate_audience_summary(
        year=int(start_date[:4]),
        metric_type="GSV",
        start_date=start_date,
        end_date=end_date,
        compare_start_date=compare_start_date,
        compare_end_date=compare_end_date,
        product_ids=product_ids,
    )
    return _extract_period_metrics(result, "2026"), _extract_period_metrics(result, "2025")


def _build_row(
    link_category: str,
    product_class: str,
    product_label: str,
    current: dict[str, float | int],
    yoy_comp: dict[str, float | int],
    mom_comp: dict[str, float | int],
) -> list[Any]:
    def values(source: dict[str, float | int]) -> list[Any]:
        return [
            source["old_users"],
            source["old_gsv"],
            source["old_aus"],
            source["new_users"],
            source["new_gsv"],
            source["new_aus"],
        ]

    return [
        link_category,
        product_class,
        product_label,
        *values(current),
        *[_safe_yoy(current[field], yoy_comp[field]) for field in current],
        *[_safe_yoy(current[field], mom_comp[field]) for field in current],
        *values(yoy_comp),
        *values(mom_comp),
    ]


def _clean_product_ids(product_ids: list[str] | None) -> list[str]:
    ids = PRODUCT_IDS if product_ids is None else [str(pid).strip() for pid in product_ids]
    ids = [pid for pid in ids if pid]
    if not ids:
        raise ValueError("产品清单不能为空")
    return ids


def _resolve_groups(product_ids: list[str], category_groups: dict[str, list[str]] | None) -> dict[str, list[str]]:
    if category_groups is not None:
        groups = category_groups
    elif product_ids == PRODUCT_IDS:
        groups = CATEGORY_GROUPS
    else:
        allowed = set(product_ids)
        groups = {
            name: [pid for pid in ids if pid in allowed]
            for name, ids in CATEGORY_GROUPS.items()
        }
        known = {pid for ids in groups.values() for pid in ids}
        extras = [pid for pid in product_ids if pid not in known]
        if extras:
            groups["自定义产品TTL"] = extras
    return {name: ids for name, ids in groups.items() if ids}


def run_fixed_product_list_compare(
    start_date: str,
    end_date: str,
    product_ids: list[str] | None = None,
    category_groups: dict[str, list[str]] | None = None,
    mom_start_date: str | None = None,
    mom_end_date: str | None = None,
) -> list[list[Any]]:
    """Return fixed product list rows using audience_summary SSOT metrics."""
    validate_date_window(start_date, end_date)
    resolved_product_ids = _clean_product_ids(product_ids)
    groups = _resolve_groups(resolved_product_ids, category_groups)
    if not groups:
        raise ValueError("产品清单不能为空")

    yoy_start = _shift_year(start_date, -1)
    yoy_end = _shift_year(end_date, -1)
    resolved_mom_start, resolved_mom_end = (
        (mom_start_date, mom_end_date)
        if mom_start_date and mom_end_date
        else _default_mom_window(start_date, end_date)
    )
    validate_date_window(resolved_mom_start, resolved_mom_end)

    rows: list[list[Any]] = []
    for group_name, ids in groups.items():
        for pid in ids:
            current, yoy_comp = _period_metrics([pid], start_date, end_date, yoy_start, yoy_end)
            _, mom_comp = _period_metrics([pid], start_date, end_date, resolved_mom_start, resolved_mom_end)
            rows.append(_build_row(group_name, "单品", pid, current, yoy_comp, mom_comp))

        current, yoy_comp = _period_metrics(ids, start_date, end_date, yoy_start, yoy_end)
        _, mom_comp = _period_metrics(ids, start_date, end_date, resolved_mom_start, resolved_mom_end)
        rows.append(_build_row(group_name, "TTL", group_name, current, yoy_comp, mom_comp))
    return rows


def write_fixed_product_list_compare(
    start_date: str,
    end_date: str,
    product_ids: list[str] | None = None,
    mom_start_date: str | None = None,
    mom_end_date: str | None = None,
    output_path: str | None = None,
) -> str:
    resolved_mom_start, resolved_mom_end = (
        (mom_start_date, mom_end_date)
        if mom_start_date and mom_end_date
        else _default_mom_window(start_date, end_date)
    )
    rows = run_fixed_product_list_compare(
        start_date=start_date,
        end_date=end_date,
        product_ids=product_ids,
        mom_start_date=resolved_mom_start,
        mom_end_date=resolved_mom_end,
    )
    if not output_path:
        output_path = str(build_take_path(
            BUSINESS_TAG,
            int(start_date[:4]),
            f"{start_date}至{end_date}",
            file_name=f"fixed_product_list_compare_{start_date}_{end_date}.xlsx",
            extension="xlsx",
        ))
    return write_table_workbook(
        headers=_make_header(start_date, end_date, resolved_mom_start, resolved_mom_end),
        rows=rows,
        output_path=output_path,
        sheet_name="商品新老客对比",
        title="商品新老客对比",
    )


def _run_from_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="fixed product list compare")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--product-ids", nargs="+", default=None)
    parser.add_argument("--mom-start-date", default=None)
    parser.add_argument("--mom-end-date", default=None)
    parser.add_argument("--output", "-o", dest="output_path", default=None)
    args = parser.parse_args(argv)
    path = write_fixed_product_list_compare(**vars(args))
    print(path)
    return 0


_fixed_product_list_compare_spec = QuerySpec(
    name="fixed-product-list-compare",
    description="按固定产品清单 + 新老客 + 两年对比 + TTL/单品层级",
    args=[
        {"flags": ("--start-date",), "required": True, "help": "起始日期 YYYY-MM-DD"},
        {"flags": ("--end-date",), "required": True, "help": "结束日期 YYYY-MM-DD"},
        {
            "flags": ("--product-ids",),
            "required": False,
            "nargs": "+",
            "default": None,
            "help": "产品 ID 列表 (默认归档固定清单)",
        },
        {"flags": ("--mom-start-date",), "required": False, "default": None, "help": "环比期起始日期"},
        {"flags": ("--mom-end-date",), "required": False, "default": None, "help": "环比期结束日期"},
        {
            "flags": ("--format",),
            "required": False,
            "default": "table",
            "choices": ["table", "csv", "xlsx"],
        },
        {"flags": ("--output", "-o"), "required": False, "default": None},
    ],
    headers=_make_header("2026-05-06", "2026-06-21", "2025-09-29", "2025-11-14"),
    run=lambda **kw: run_fixed_product_list_compare(**kw),
    xlsx_writer=write_fixed_product_list_compare,
    business_tag=BUSINESS_TAG,
    base_year_arg="start_date",
)
register(_fixed_product_list_compare_spec)


if __name__ == "__main__":
    sys.exit(_run_from_cli())
