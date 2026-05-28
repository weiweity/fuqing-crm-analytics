"""
breakdown_service 共享常量和工具函数
从 v1 单文件拆分时拆分丢失的函数恢复
"""

from datetime import datetime
from typing import List, Dict, Any
from dateutil.relativedelta import relativedelta

from backend.semantic.calculations import safe_ratio

# ── 语义层统一口径 ────────────────────────────────────────────

_VALID_BASE = "is_goujinjin = FALSE AND order_status != '交易关闭'"
_VALID_BASE_T = "o.is_goujinjin = FALSE AND o.order_status != '交易关闭'"

GSV_AMOUNT_COL = """
    CASE WHEN is_refund = FALSE AND order_status != '交易关闭'
         THEN actual_amount ELSE 0 END
""".strip()

# ── 常量 ─────────────────────────────────────────────────────

REPURCHASE_ADJUSTMENT = {
    "大促期": 1.15,
    "日常": 1.0,
    "年货节": 1.10,
    "3.8": 1.08,
    "618": 1.20,
    "双11": 1.25,
}

R_INTERVALS = [
    ("近1个月已购客",    0,   30),
    ("近2-3个月已购客",  31,  90),
    ("近4-6月已购客",    91, 180),
    ("近7-12个月已购客", 181, 365),
    ("近13-24个月已购客",366, 730),
    ("2年外已购客",      731, 99999),
]

F_SEGMENTS = ["F>1", "F=1"]

NEW_CUSTOMER_GROWTH_FACTOR = 1.1
DEFAULT_MEMBER_JOIN_RATE = 0.025
UV_MULTIPLIER = 20

CHANNEL_ORDER = ['货架', '达播', '直播', '淘客', '微博', 'U先派样', '百补派样', '赠品&0.01', '其他']

# ── 工具函数 ─────────────────────────────────────────────────

def _parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")


def _format_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _detect_activity_type(start: str, end: str) -> str:
    """根据日期判断活动类型"""
    start_dt = _parse_date(start)
    month = start_dt.month
    day = start_dt.day
    if month == 11 and day >= 1:
        return "双11"
    elif month == 6:
        return "618"
    elif month == 3 and day >= 1:
        return "3.8"
    elif month == 1:
        return "年货节"
    else:
        return "大促期"


def _get_default_ly_dates(start: str, end: str) -> tuple:
    """自动推算去年同期日期"""
    start_dt = _parse_date(start)
    end_dt = _parse_date(end)
    ly_start = start_dt - relativedelta(years=1)
    ly_end = end_dt - relativedelta(years=1)
    return _format_date(ly_start), _format_date(ly_end)


def _r_interval_sql(date_col: str, cutoff_date: str) -> str:
    """生成R区间CASE WHEN SQL"""
    return f"""
        CASE
            WHEN DATEDIFF('day', {date_col}, DATE '{cutoff_date}') <= 30 THEN '近1个月已购客'
            WHEN DATEDIFF('day', {date_col}, DATE '{cutoff_date}') <= 90 THEN '近2-3个月已购客'
            WHEN DATEDIFF('day', {date_col}, DATE '{cutoff_date}') <= 180 THEN '近4-6月已购客'
            WHEN DATEDIFF('day', {date_col}, DATE '{cutoff_date}') <= 365 THEN '近7-12个月已购客'
            WHEN DATEDIFF('day', {date_col}, DATE '{cutoff_date}') <= 730 THEN '近13-24个月已购客'
            ELSE '2年外已购客'
        END
    """.strip()


# ── R区间老客数据查询 ────────────────────────────────────────

def _get_r_interval_current_distribution(
    conn,
    activity_start: str
) -> List[Dict[str, Any]]:
    """
    获取当前各R区间×F段的老客人数分布
    以 activity_start 为截止日，计算每个用户的 recency，
    按6档R区间 + F>1/F=1 分组统计。
    """
    r_case = _r_interval_sql("cu.last_pay_time", activity_start)

    sql = f"""
    WITH current_users AS (
        SELECT
            user_id,
            MAX(pay_time) AS last_pay_time
        FROM orders
        WHERE pay_time < '{activity_start}'
          AND {_VALID_BASE}
          AND user_id IS NOT NULL
          AND user_id != ''
        GROUP BY user_id
    ),
    user_freq AS (
        SELECT
            user_id,
            COUNT(*) AS f_count
        FROM orders
        WHERE pay_time >= DATE '{activity_start}' - INTERVAL '365 days'
          AND pay_time < DATE '{activity_start}'
          AND {_VALID_BASE}
          AND user_id IS NOT NULL
        GROUP BY user_id
    ),
    current_rf AS (
        SELECT
            cu.user_id,
            ({r_case}) AS r_interval,
            COALESCE(uf.f_count, 0) AS f_count
        FROM current_users cu
        LEFT JOIN user_freq uf ON cu.user_id = uf.user_id
    )
    SELECT
        r_interval,
        CASE WHEN f_count > 1 THEN 'F>1' ELSE 'F=1' END AS f_segment,
        COUNT(*) AS user_count
    FROM current_rf
    GROUP BY r_interval,
             CASE WHEN f_count > 1 THEN 'F>1' ELSE 'F=1' END
    ORDER BY r_interval, f_segment
    """

    result = conn.execute(sql).fetchall()
    columns = [desc[0] for desc in conn.execute(sql).description]
    return [dict(zip(columns, row)) for row in result]


def _get_ly_repurchase_by_r_interval(
    conn,
    ly_start: str,
    ly_end: str
) -> List[Dict[str, Any]]:
    """
    获取去年同期各R区间×F段的回购率和客单价
    以 ly_start 为截止日，计算去年活动期开始时各用户的R区间，
    然后统计这些用户在 ly_start~ly_end 期间的回购情况。
    """
    r_case = _r_interval_sql("lus.last_pay_before_ly", ly_start)

    sql = f"""
    WITH ly_user_status AS (
        SELECT
            user_id,
            MAX(pay_time) AS last_pay_before_ly
        FROM orders
        WHERE pay_time < '{ly_start}'
          AND {_VALID_BASE}
          AND user_id IS NOT NULL
          AND user_id != ''
        GROUP BY user_id
    ),
    ly_user_freq AS (
        SELECT
            user_id,
            COUNT(*) AS f_count_ly
        FROM orders
        WHERE pay_time >= DATE '{ly_start}' - INTERVAL '365 days'
          AND pay_time < DATE '{ly_start}'
          AND {_VALID_BASE}
          AND user_id IS NOT NULL
        GROUP BY user_id
    ),
    ly_rf AS (
        SELECT
            lus.user_id,
            ({r_case}) AS r_interval,
            COALESCE(luf.f_count_ly, 0) AS f_count_ly
        FROM ly_user_status lus
        LEFT JOIN ly_user_freq luf ON lus.user_id = luf.user_id
    ),
    ly_purchased AS (
        SELECT DISTINCT user_id
        FROM orders
        WHERE pay_time BETWEEN '{ly_start}' AND '{ly_end} 23:59:59'
          AND {_VALID_BASE}
          AND user_id IS NOT NULL
    ),
    ly_purchase_amount AS (
        SELECT
            user_id,
            SUM({GSV_AMOUNT_COL})::FLOAT AS total_gsv
        FROM orders
        WHERE pay_time BETWEEN '{ly_start}' AND '{ly_end} 23:59:59'
          AND {_VALID_BASE}
          AND user_id IS NOT NULL
        GROUP BY user_id
    ),
    ly_repurchase_stats AS (
        SELECT
            r.r_interval,
            CASE WHEN r.f_count_ly > 1 THEN 'F>1' ELSE 'F=1' END AS f_segment,
            COUNT(DISTINCT r.user_id) AS total_users,
            COUNT(DISTINCT lp.user_id) AS repurchased_users,
            COALESCE(SUM(lpa.total_gsv), 0)::FLOAT AS total_gsv
        FROM ly_rf r
        LEFT JOIN ly_purchased lp ON r.user_id = lp.user_id
        LEFT JOIN ly_purchase_amount lpa ON r.user_id = lpa.user_id
        GROUP BY r.r_interval,
                 CASE WHEN r.f_count_ly > 1 THEN 'F>1' ELSE 'F=1' END
    )
    SELECT
        r_interval,
        f_segment,
        total_users,
        repurchased_users,
        CASE WHEN total_users > 0
             THEN ROUND(repurchased_users::FLOAT / total_users, 4)
             ELSE 0 END AS repurchase_rate,
        CASE WHEN repurchased_users > 0
             THEN ROUND(total_gsv / repurchased_users, 2)
             ELSE 0 END AS aus
    FROM ly_repurchase_stats
    ORDER BY r_interval, f_segment
    """

    result = conn.execute(sql).fetchall()
    columns = [desc[0] for desc in conn.execute(sql).description]
    return [dict(zip(columns, row)) for row in result]


# ── 新客渠道漏斗查询 ──────────────────────────────────────────

def _get_new_customer_by_channel(
    conn,
    ly_start: str,
    ly_end: str
) -> List[Dict[str, Any]]:
    """
    获取去年同期各渠道新客数据（按芙清8层渠道漏斗）
    新客定义：首次购买在活动期间的用户
    """
    sql = f"""
    WITH new_customers AS (
        SELECT
            o.channel,
            COUNT(DISTINCT o.user_id) AS new_users,
            COALESCE(SUM({GSV_AMOUNT_COL}), 0)::FLOAT AS new_gmv,
            CASE WHEN COUNT(DISTINCT o.user_id) > 0
                 THEN ROUND(SUM({GSV_AMOUNT_COL})::FLOAT / COUNT(DISTINCT o.user_id), 2)
                 ELSE 0 END AS new_aus
        FROM orders o
        INNER JOIN user_first_purchase ufp ON o.user_id = ufp.user_id
        WHERE o.pay_time BETWEEN '{ly_start}' AND '{ly_end} 23:59:59'
          AND {_VALID_BASE_T}
          AND o.user_id IS NOT NULL
          AND ufp.first_pay_date >= DATE '{ly_start}'
          AND ufp.first_pay_date <= DATE '{ly_end}'
        GROUP BY o.channel
    )
    SELECT * FROM new_customers
    WHERE new_users > 0
    ORDER BY new_gmv DESC
    """

    result = conn.execute(sql).fetchall()
    columns = [desc[0] for desc in conn.execute(sql).description]
    return [dict(zip(columns, row)) for row in result]


def _get_uv_reference(
    conn,
    activity_start: str,
    activity_end: str
) -> Dict[str, Any]:
    """
    获取UV和入会率参考数据
    优先从流量xlsx读取真实数据，否则回退到orders估算
    """
    import os
    try:
        import pandas as pd
    except ImportError:
        pd = None

    uv_file = "/Users/hutou/Desktop/fuqin date/芙清CRM数据库/芙清crm原始数据库/店铺流量数据库/24-26年访客数情况0427.xlsx"

    if pd and os.path.exists(uv_file):
        try:
            df = pd.read_excel(uv_file, dtype={"日期": str})
            mask = (df["日期"] >= activity_start) & (df["日期"] <= activity_end)
            period_df = df.loc[mask]
            total_uv = int(period_df["访客数"].sum())
            total_new_members = int(period_df["新增会员数"].sum())
            member_join_rate = safe_ratio(total_new_members, total_uv, DEFAULT_MEMBER_JOIN_RATE)
            return {
                "uv": total_uv,
                "new_members": total_new_members,
                "member_join_rate": round(member_join_rate, 4)
            }
        except Exception:
            pass

    sql = f"""
    SELECT COUNT(DISTINCT user_id) * {UV_MULTIPLIER} AS estimated_uv
    FROM orders
    WHERE pay_time BETWEEN '{activity_start}' AND '{activity_end} 23:59:59'
      AND {_VALID_BASE}
      AND user_id IS NOT NULL
    """
    result = conn.execute(sql).fetchone()
    estimated_uv = result[0] or 0
    return {
        "uv": estimated_uv,
        "new_members": int(estimated_uv * DEFAULT_MEMBER_JOIN_RATE),
        "member_join_rate": DEFAULT_MEMBER_JOIN_RATE
    }
