"""
order_set_30_indicators.py — 按 Excel 订单号集合匹配订单，输出两年 30 指标对比。

支持两种场景：
- 2026-05-06 ~ 2026-06-21 / 2025-05-06 ~ 2025-06-21（UDS 618 订单明细）
- 2026-01-01 ~ 2026-06-30 / 2025-01-01 ~ 2025-06-30（订单报表）

用法：
  /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/.venv/bin/python \
    scripts/adhoc_order_set_30_indicators.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from backend.db.connection import get_connection
from backend.semantic.filters import OrderFilters
from backend.semantic.calculations import yoy_ratio, yoy_absolute

from scripts.ad_hoc_queries._utils import clamp_yoy, build_take_path
from scripts.ad_hoc_query_excel_styles import write_table_workbook


# ── 场景配置 ─────────────────────────────────────────────────────────
SCENARIO = "h1_report"  # 切换: "uds_618" | "h1_report"

SCENARIOS = {
    "uds_618": {
        "file_2026": Path("/Users/hutou/Desktop/fuqin date/推广临时数据/新老客-26年618uds订单明细.xlsx"),
        "file_2025": Path("/Users/hutou/Desktop/fuqin date/推广临时数据/新老客-25年618uds订单明细.xlsx"),
        "window_2026": (date(2026, 5, 6), date(2026, 6, 21)),
        "window_2025": (date(2025, 5, 6), date(2025, 6, 21)),
        "sheet_name": "UDS订单集合_30指标",
        "title": "UDS订单集合 30指标对比",
        "business_tag": "UDS订单集合30指标",
    },
    "h1_report": {
        "file_2026": Path("/Users/hutou/Downloads/副本订单报表_2026-01-01--2026-06-30.xlsx"),
        "file_2025": Path("/Users/hutou/Downloads/副本订单报表_2025-01-01--2025-06-30_9c3448be783c4b2daec8e83ee602a05b.xlsx"),
        "window_2026": (date(2026, 1, 1), date(2026, 6, 30)),
        "window_2025": (date(2025, 1, 1), date(2025, 6, 30)),
        "sheet_name": "H1订单集合_30指标",
        "title": "H1订单集合 30指标对比",
        "business_tag": "H1订单集合30指标",
    },
}


def load_order_ids(excel_path: Path) -> set[str]:
    """读取 Excel J 列（订单号），去重并清洗。"""
    df = pd.read_excel(excel_path, engine="openpyxl", usecols=[9], dtype=str)
    df.columns = ["order_id"]
    raw = df["order_id"].dropna().astype(str).str.strip()
    raw = raw.str.replace(r"^\t+", "", regex=True)
    return set(raw) - {"", "null", "nan", "None"}


def _safe_int(v):
    return int(v) if v is not None else 0


def _n(v):
    return float(v) if v is not None else 0.0


def _run_period_data(start_dt: str, end_dt: str, cutoff_dt: str, order_ids: set[str]):
    """按订单号集合执行一个周期的查询，复用 audience_summary 的 SQL 结构。"""
    conn = get_connection()
    params = [start_dt, end_dt]
    valid_sql, _ = OrderFilters.valid_order()
    valid_sql = valid_sql.replace("is_goujinjin", "o.is_goujinjin").replace("order_status", "o.order_status").replace("is_refund", "o.is_refund")
    where_parts = ["o.pay_time >= ?::TIMESTAMP", "o.pay_time <= ?::TIMESTAMP", valid_sql]

    order_id_list = sorted(order_ids)
    placeholders = ",".join(["?"] * len(order_id_list))
    where_parts.append(f"o.order_id IN ({placeholders})")
    params.extend(order_id_list)

    where_sql = " AND ".join(where_parts)
    full_params = params + [cutoff_dt]

    sql = f"""
    WITH
    base AS (
        SELECT * FROM orders o
        WHERE {where_sql}
    ),
    old_customers AS (
        SELECT DISTINCT u.user_id
        FROM user_first_purchase u
        WHERE u.first_pay_date <= ?::DATE
    ),
    enriched AS (
        SELECT
            o.channel AS dim_key,
            o.user_id,
            o.actual_amount AS amount,
            o.is_member,
            CASE WHEN oc.user_id IS NOT NULL THEN 1 ELSE 0 END AS is_old
        FROM base o
        LEFT JOIN old_customers oc ON o.user_id = oc.user_id
    ),
    grouped AS (
        SELECT
            COUNT(DISTINCT user_id) AS gsv_users,
            SUM(amount) AS gsv,
            SUM(amount) / NULLIF(COUNT(DISTINCT user_id), 0) AS aus,
            COUNT(DISTINCT CASE WHEN is_old = 1 THEN user_id END) AS old_users,
            SUM(amount * CASE WHEN is_old = 1 THEN 1 ELSE 0 END) AS old_gsv,
            SUM(amount * CASE WHEN is_old = 1 THEN 1 ELSE 0 END) /
                NULLIF(COUNT(DISTINCT CASE WHEN is_old = 1 THEN user_id END), 0) AS old_aus,
            COUNT(DISTINCT CASE WHEN is_member = TRUE THEN user_id END) AS member_users,
            SUM(amount * CASE WHEN is_member = TRUE THEN 1 ELSE 0 END) AS member_gsv,
            SUM(amount * CASE WHEN is_member = TRUE THEN 1 ELSE 0 END) /
                NULLIF(COUNT(DISTINCT CASE WHEN is_member = TRUE THEN user_id END), 0) AS member_aus,
            COUNT(DISTINCT CASE WHEN is_member = TRUE AND is_old = 1 THEN user_id END) AS member_old_users,
            SUM(amount * CASE WHEN is_member = TRUE AND is_old = 1 THEN 1 ELSE 0 END) AS member_old_gsv
        FROM enriched
    )
    SELECT
        gsv_users, gsv, aus,
        old_users, old_gsv, old_aus,
        member_users, member_gsv, member_aus,
        member_old_users, member_old_gsv
    FROM grouped
    """
    raw = conn.execute(sql, full_params).fetchall()
    return raw[0] if raw else (0,) * 11


def _extract_metrics(row):
    """从聚合行提取指标，与 audience_summary._extract_metrics 保持一致。"""
    gsv_users = _safe_int(row[0])
    gsv = _n(row[1])
    aus = _n(row[2])
    old_users = _safe_int(row[3])
    old_gsv = _n(row[4])
    old_aus = _n(row[5])
    member_users = _safe_int(row[6])
    member_gsv = _n(row[7])
    member_aus = _n(row[8])
    member_old_users = _safe_int(row[9])
    member_old_gsv = _n(row[10])

    new_users = max(0, gsv_users - old_users)
    new_gsv = max(0, gsv - old_gsv)
    new_aus = new_gsv / new_users if new_users > 0 else 0.0
    member_new_gsv = max(0, member_gsv - member_old_gsv)
    member_new_users = max(0, member_users - member_old_users)

    return {
        "gsv": gsv, "users": gsv_users, "aus": aus,
        "old_gsv": old_gsv, "old_users": old_users, "old_aus": old_aus,
        "old_gsv_ratio": round(old_gsv / gsv, 4) if gsv > 0 else 0.0,
        "old_users_ratio": round(old_users / gsv_users, 4) if gsv_users > 0 else 0.0,
        "new_gsv": new_gsv, "new_users": new_users, "new_aus": new_aus,
        "new_gsv_ratio": round(new_gsv / gsv, 4) if gsv > 0 else 0.0,
        "new_users_ratio": round(new_users / gsv_users, 4) if gsv_users > 0 else 0.0,
        "member_gsv": member_gsv, "member_users": member_users, "member_aus": member_aus,
        "member_penetration": round(member_users / gsv_users, 4) if gsv_users > 0 else 0.0,
        "member_users_ratio": round(member_users / gsv_users, 4) if gsv_users > 0 else 0.0,
        "member_old_gsv": member_old_gsv, "member_old_users": member_old_users,
        "member_old_aus": member_old_gsv / member_old_users if member_old_users > 0 else 0.0,
        "member_old_gsv_ratio": round(member_old_gsv / member_gsv, 4) if member_gsv > 0 else 0.0,
        "member_old_users_ratio": round(member_old_users / member_users, 4) if member_users > 0 else 0.0,
        "member_new_gsv": member_new_gsv,
        "member_new_users": member_new_users,
        "member_new_aus": member_new_gsv / member_new_users if member_new_users > 0 else 0.0,
        "member_new_gsv_ratio": round(member_new_gsv / member_gsv, 4) if member_gsv > 0 else 0.0,
        "member_new_users_ratio": round(member_new_users / member_users, 4) if member_users > 0 else 0.0,
    }


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


_INDICATOR_SPECS = [
    ("全店GSV", "money", yoy_absolute),
    ("全店人数", "count", yoy_absolute),
    ("AUS", "aus", yoy_absolute),
    ("老客GSV", "money", yoy_absolute),
    ("老客人数", "count", yoy_absolute),
    ("老客AUS", "aus", yoy_absolute),
    ("老客GSV占比", "ratio", yoy_ratio),
    ("老客人数占比", "ratio", yoy_ratio),
    ("新客GSV", "money", yoy_absolute),
    ("新客人数", "count", yoy_absolute),
    ("新客AUS", "aus", yoy_absolute),
    ("新客GSV占比", "ratio", yoy_ratio),
    ("新客人数占比", "ratio", yoy_ratio),
    ("会员GSV", "money", yoy_absolute),
    ("会员人数", "count", yoy_absolute),
    ("会员AUS", "aus", yoy_absolute),
    ("会员渗透率", "ratio", yoy_ratio),
    ("会员人数占比", "ratio", yoy_ratio),
    ("会员老客GSV", "money", yoy_absolute),
    ("会员老客人数", "count", yoy_absolute),
    ("会员老客AUS", "aus", yoy_absolute),
    ("会员老客GSV占比", "ratio", yoy_ratio),
    ("会员老客人数占比", "ratio", yoy_ratio),
    ("会员新客GSV", "money", yoy_absolute),
    ("会员新客人数", "count", yoy_absolute),
    ("会员新客AUS", "aus", yoy_absolute),
    ("会员新客GSV占比", "ratio", yoy_ratio),
    ("会员新客人数占比", "ratio", yoy_ratio),
]


def _field_value(m: dict, label: str):
    mapping = {
        "全店GSV": "gsv", "全店人数": "users", "AUS": "aus",
        "老客GSV": "old_gsv", "老客人数": "old_users", "老客AUS": "old_aus",
        "老客GSV占比": "old_gsv_ratio", "老客人数占比": "old_users_ratio",
        "新客GSV": "new_gsv", "新客人数": "new_users", "新客AUS": "new_aus",
        "新客GSV占比": "new_gsv_ratio", "新客人数占比": "new_users_ratio",
        "会员GSV": "member_gsv", "会员人数": "member_users", "会员AUS": "member_aus",
        "会员渗透率": "member_penetration", "会员人数占比": "member_users_ratio",
        "会员老客GSV": "member_old_gsv", "会员老客人数": "member_old_users", "会员老客AUS": "member_old_aus",
        "会员老客GSV占比": "member_old_gsv_ratio", "会员老客人数占比": "member_old_users_ratio",
        "会员新客GSV": "member_new_gsv", "会员新客人数": "member_new_users", "会员新客AUS": "member_new_aus",
        "会员新客GSV占比": "member_new_gsv_ratio", "会员新客人数占比": "member_new_users_ratio",
    }
    return m.get(mapping[label], 0)


def _build_indicators(cur_m: dict, comp_m: dict) -> list[dict]:
    indicators = []
    for label, kind, yoy_fn in _INDICATOR_SPECS:
        cur_v = _field_value(cur_m, label)
        comp_v = _field_value(comp_m, label)
        indicators.append({
            "field": label,
            "kind": kind,
            "values_by_year": {"2026": cur_v, "2025": comp_v},
            "yoy": clamp_yoy(yoy_fn(cur_v, comp_v)),
        })
    return indicators


def _cutoff_for(start_date: date) -> date:
    return start_date - timedelta(days=1)


def main(scenario_key: str = SCENARIO) -> str:
    cfg = SCENARIOS[scenario_key]
    file_2026 = cfg["file_2026"]
    file_2025 = cfg["file_2025"]
    window_2026 = cfg["window_2026"]
    window_2025 = cfg["window_2025"]
    sheet_name = cfg["sheet_name"]
    title = cfg["title"]
    business_tag = cfg["business_tag"]

    print(f"[INFO] Scenario: {scenario_key}", file=sys.stderr)
    print("[INFO] Loading 2026 order IDs...", file=sys.stderr)
    orders_2026 = load_order_ids(file_2026)
    print(f"[INFO] 2026 unique orders: {len(orders_2026)}", file=sys.stderr)

    print("[INFO] Loading 2025 order IDs...", file=sys.stderr)
    orders_2025 = load_order_ids(file_2025)
    print(f"[INFO] 2025 unique orders: {len(orders_2025)}", file=sys.stderr)

    s26, e26 = window_2026
    s25, e25 = window_2025
    cutoff_26 = _cutoff_for(s26)
    cutoff_25 = _cutoff_for(s25)

    print("[INFO] Querying 2026 window...", file=sys.stderr)
    row_2026 = _run_period_data(
        f"{s26} 00:00:00", f"{e26} 23:59:59", cutoff_26.strftime("%Y-%m-%d"), orders_2026
    )
    cur_m = _extract_metrics(row_2026)

    print("[INFO] Querying 2025 window...", file=sys.stderr)
    row_2025 = _run_period_data(
        f"{s25} 00:00:00", f"{e25} 23:59:59", cutoff_25.strftime("%Y-%m-%d"), orders_2025
    )
    comp_m = _extract_metrics(row_2025)

    indicators = _build_indicators(cur_m, comp_m)

    headers = ["指标", "2026年", "2025年", "同比", "单位"]
    rows = []
    for item in indicators:
        label = item["field"]
        metric_key, unit = _FIELD_KEYS.get(label, (f"all_{label}", "%"))
        rows.append([
            label,
            item["values_by_year"]["2026"],
            item["values_by_year"]["2025"],
            item["yoy"],
            unit,
        ])

    date_range = f"{s26}至{e26}"
    out_path = build_take_path(
        business_tag=business_tag,
        base_year=2026,
        date_range=date_range,
        file_name=None,
        extension="xlsx",
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    path = write_table_workbook(
        headers=headers,
        rows=rows,
        output_path=str(out_path),
        sheet_name=sheet_name,
        title=title,
    )
    print(f"[OK] XLSX written to {path}", file=sys.stderr)
    return path


if __name__ == "__main__":
    main("h1_report")
