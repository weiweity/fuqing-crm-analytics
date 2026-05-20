"""
一键拆解服务 v2

基于历史数据自动完成大促拆解：
- 老客：按R区间（6档）× F段（F>1/F=1）逐层预估
- 新客：按渠道漏斗逐渠道预估
- 支持顺拆（现状→预估）和倒拆（目标→反推）两种模式
- 仅GSV口径

参考：[PROCEDURE] 芙清老客拆解四步法、[PROCEDURE] 芙清新客拆解、[PROCEDURE] 老客RFM分析四步法
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dateutil.relativedelta import relativedelta

from backend.db.connection import get_connection
from backend.semantic.calculations import safe_ratio
from backend.semantic.filters import OrderFilters

# 语义层统一口径
_VALID_BASE = "is_goujinjin = FALSE"
_VALID_BASE_T = "o.is_goujinjin = FALSE"


# ── 常量 ─────────────────────────────────────────────────────

# 老客回购率调整系数（基于经验，大促期回购率更高）
REPURCHASE_ADJUSTMENT = {
    "大促期": 1.15,
    "日常": 1.0,
    "年货节": 1.10,
    "3.8": 1.08,
    "618": 1.20,
    "双11": 1.25,
}

# R区间定义（与老客健康分析 RIntervalTab 一致）
# cutoff = 活动开始日 - 1天
R_INTERVALS = [
    ("近1个月已购客",    0,   30),
    ("近2-3个月已购客",  31,  90),
    ("近4-6月已购客",    91, 180),
    ("近7-12个月已购客", 181, 365),
    ("近13-24个月已购客",366, 730),
    ("2年外已购客",      731, 99999),
]

# F分段
F_SEGMENTS = ["F>1", "F=1"]

# 新客相关常量
NEW_CUSTOMER_GROWTH_FACTOR = 1.1       # 新客同比增长系数
DEFAULT_MEMBER_JOIN_RATE = 0.025       # 默认入会率 2.5%
UV_MULTIPLIER = 20                     # UV估算倍数（购买人数×20）

# 渠道固定排序（芙清8层漏斗）
CHANNEL_ORDER = ['货架', '达播', '直播', '淘客', '微博', 'U先派样', '百补派样', '赠品&0.01', '其他']

# GSV口径（硬编码，不支持GMV切换）
GSV_AMOUNT_COL = """
    CASE WHEN is_refund = FALSE AND order_status != '交易关闭'
         THEN actual_amount ELSE 0 END
""".strip()


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

    # 回退：从orders估算UV
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


# ── 主服务：顺拆 ──────────────────────────────────────────────

def _forward_breakdown(
    conn,
    target_gmv: float,
    activity_start: str,
    activity_end: str,
    ly_start: str,
    ly_end: str,
    old_customer_ratio_target: float,
    activity_type: str,
    adjustment: float
) -> Dict[str, Any]:
    """顺拆：从现状数据预估，计算目标gap"""

    # 1. 获取数据
    current_rf = _get_r_interval_current_distribution(conn, activity_start)
    ly_repurchase = _get_ly_repurchase_by_r_interval(conn, ly_start, ly_end)
    new_channel_data = _get_new_customer_by_channel(conn, ly_start, ly_end)
    uv_data = _get_uv_reference(conn, activity_start, activity_end)
    # 顺拆时：若当前活动期无UV数据，回退到去年同期UV作为参考
    if uv_data["uv"] == 0 and ly_start and ly_end:
        uv_data = _get_uv_reference(conn, ly_start, ly_end)

    # 2. 构建去年回购率/客单价查询字典
    ly_dict = {}
    for row in ly_repurchase:
        key = (row["r_interval"], row["f_segment"])
        ly_dict[key] = {
            "repurchase_rate": row["repurchase_rate"],
            "aus": row["aus"],
            "total_users": row["total_users"],
            "repurchased_users": row["repurchased_users"],
        }

    # 3. 老客预估：按R区间×F段逐层计算
    r_interval_breakdown = []
    old_total_estimate = 0.0
    total_old_users = 0

    for row in current_rf:
        r_interval = row["r_interval"]
        f_segment = row["f_segment"]
        user_count = row["user_count"]

        total_old_users += user_count

        ly = ly_dict.get((r_interval, f_segment), {
            "repurchase_rate": 0.03,
            "aus": 0,
            "total_users": 0,
            "repurchased_users": 0
        })

        # 预估回购率 = 去年回购率 × 活动调整系数（上限95%）
        est_rate = min(ly["repurchase_rate"] * adjustment, 0.95)
        # 预估客单价 = 去年客单价（有回购才有客单价参考）
        est_aus = ly["aus"] if ly["aus"] > 0 else 50.0

        est_gmv = user_count * est_rate * est_aus
        old_total_estimate += est_gmv

        r_interval_breakdown.append({
            "r_interval": r_interval,
            "f_segment": f_segment,
            "user_count": user_count,
            "ly_repurchase_rate": round(ly["repurchase_rate"], 4),
            "est_repurchase_rate": round(est_rate, 4),
            "est_aus": round(est_aus, 2),
            "est_gmv": round(est_gmv, 2),
            "ly_total_users": ly["total_users"],
            "ly_repurchased_users": ly["repurchased_users"],
        })

    old_target = target_gmv * old_customer_ratio_target
    old_gap = old_target - old_total_estimate

    # 4. 新客预估：按渠道漏斗
    new_channel_breakdown = []
    new_total_estimate = 0.0
    total_new_users = 0

    for ch in new_channel_data:
        channel = ch["channel"]
        ly_new_users = ch["new_users"] or 0
        ly_new_aus = ch["new_aus"] or 0

        est_new_users = int(ly_new_users * NEW_CUSTOMER_GROWTH_FACTOR)
        est_new_aus = ly_new_aus  # 新客客单价通常相对稳定
        est_new_gmv = est_new_users * est_new_aus

        new_total_estimate += est_new_gmv
        total_new_users += est_new_users

        new_channel_breakdown.append({
            "channel": channel,
            "ly_new_users": ly_new_users,
            "est_new_users": est_new_users,
            "ly_new_aus": round(ly_new_aus, 2),
            "est_new_aus": round(est_new_aus, 2),
            "est_new_gmv": round(est_new_gmv, 2),
        })

    new_target = target_gmv * (1 - old_customer_ratio_target)
    new_gap = new_target - new_total_estimate

    # 5. 总计
    total_estimate = old_total_estimate + new_total_estimate
    total_gap = target_gmv - total_estimate
    gap_ratio = safe_ratio(total_gap, target_gmv, 0)

    # 6. 补gap建议
    suggestions = _generate_suggestions(
        old_gap, old_target, new_gap, new_target, total_gap, target_gmv
    )

    return {
        "mode": "forward",
        "mode_label": "顺拆（从现状预估）",
        "target_gmv": round(target_gmv, 2),
        "total_estimate": round(total_estimate, 2),
        "total_gap": round(total_gap, 2),
        "gap_ratio": round(gap_ratio, 4),
        "old_customer": {
            "old_users_total": total_old_users,
            "old_gmv_estimate": round(old_total_estimate, 2),
            "old_gmv_target": round(old_target, 2),
            "old_gmv_gap": round(old_gap, 2),
            "r_interval_breakdown": r_interval_breakdown,
        },
        "new_customer": {
            "new_users_total": total_new_users,
            "new_gmv_estimate": round(new_total_estimate, 2),
            "new_gmv_target": round(new_target, 2),
            "new_gmv_gap": round(new_gap, 2),
            "channel_breakdown": new_channel_breakdown,
            "uv_reference": uv_data["uv"],
            "member_join_rate": uv_data["member_join_rate"],
        },
        "suggestions": suggestions,
        "activity_period": {"start": activity_start, "end": activity_end},
        "reference_period": {"start": ly_start, "end": ly_end},
        "meta": {
            "activity_type": activity_type,
            "repurchase_adjustment": adjustment,
            "metric_type": "GSV",
        },
        "breakdown_logic": {
            "old_customer_formula": "老客GMV = Σ(各R区间各F段人数 × 该区间去年回购率×活动系数 × 该区间去年客单价)",
            "old_customer_source": "参见 [PROCEDURE] 芙清老客拆解四步法、[PROCEDURE] 老客RFM分析四步法",
            "new_customer_formula": "新客GMV = Σ(各渠道去年新客人数×1.1 × 去年新客客单价)",
            "new_customer_source": "参见 [PROCEDURE] 芙清新客拆解、[PROCEDURE] 新客预估三步走",
        },
    }


# ── 主服务：倒拆 ──────────────────────────────────────────────

def _reverse_breakdown(
    conn,
    target_gmv: float,
    activity_start: str,
    activity_end: str,
    ly_start: str,
    ly_end: str,
    old_customer_ratio_target: float,
    activity_type: str,
    adjustment: float
) -> Dict[str, Any]:
    """倒拆：从目标反推各R区间所需人数/UV/派样量"""

    # 1. 获取数据
    current_rf = _get_r_interval_current_distribution(conn, activity_start)
    ly_repurchase = _get_ly_repurchase_by_r_interval(conn, ly_start, ly_end)
    new_channel_data = _get_new_customer_by_channel(conn, ly_start, ly_end)
    uv_data = _get_uv_reference(conn, activity_start, activity_end)

    # 2. 构建字典
    ly_dict = {}
    for row in ly_repurchase:
        key = (row["r_interval"], row["f_segment"])
        ly_dict[key] = {
            "repurchase_rate": row["repurchase_rate"],
            "aus": row["aus"],
            "total_users": row["total_users"],
        }

    # 3. 老客倒拆：先计算去年老客GMV各区间占比，按占比拆分目标
    # 先跑一遍顺推算去年GMV结构
    ly_old_gmv_by_interval = {}
    ly_old_gmv_total = 0.0

    for row in current_rf:
        key = (row["r_interval"], row["f_segment"])
        ly = ly_dict.get(key, {"repurchase_rate": 0.03, "aus": 0, "total_users": 0})
        interval_gmv = row["user_count"] * ly["repurchase_rate"] * (ly["aus"] if ly["aus"] > 0 else 50.0)
        ly_old_gmv_by_interval[key] = interval_gmv
        ly_old_gmv_total += interval_gmv

    old_target = target_gmv * old_customer_ratio_target

    r_interval_breakdown = []
    total_old_users = 0

    for row in current_rf:
        r_interval = row["r_interval"]
        f_segment = row["f_segment"]
        user_count = row["user_count"]
        total_old_users += user_count

        key = (r_interval, f_segment)
        ly = ly_dict.get(key, {"repurchase_rate": 0.03, "aus": 0, "total_users": 0})
        est_rate = min(ly["repurchase_rate"] * adjustment, 0.95)
        est_aus = ly["aus"] if ly["aus"] > 0 else 50.0

        # 按去年GMV占比拆分老客目标
        if ly_old_gmv_total > 0:
            interval_share = ly_old_gmv_by_interval.get(key, 0) / ly_old_gmv_total
        else:
            interval_share = 1.0 / len(current_rf) if current_rf else 0

        interval_target = old_target * interval_share
        # 反推所需人数 = 目标GMV / (回购率 × 客单价)
        needed_users = int(interval_target / (est_rate * est_aus)) if (est_rate * est_aus) > 0 else 0
        user_gap = needed_users - user_count

        r_interval_breakdown.append({
            "r_interval": r_interval,
            "f_segment": f_segment,
            "current_users": user_count,
            "est_repurchase_rate": round(est_rate, 4),
            "est_aus": round(est_aus, 2),
            "interval_target_gmv": round(interval_target, 2),
            "needed_users": needed_users,
            "user_gap": user_gap,
            "ly_repurchase_rate": round(ly["repurchase_rate"], 4),
            "ly_total_users": ly["total_users"],
        })

    # 4. 新客倒拆：按渠道漏斗占比拆分新客目标
    new_target = target_gmv * (1 - old_customer_ratio_target)
    ly_new_gmv_total = sum(ch["new_gmv"] or 0 for ch in new_channel_data)

    new_channel_breakdown = []
    total_new_users = 0

    for ch in new_channel_data:
        channel = ch["channel"]
        ly_new_gmv = ch["new_gmv"] or 0
        ly_new_aus = ch["new_aus"] or 50.0
        ly_new_users = ch["new_users"] or 0

        if ly_new_gmv_total > 0:
            channel_share = ly_new_gmv / ly_new_gmv_total
        else:
            channel_share = 1.0 / len(new_channel_data) if new_channel_data else 0

        channel_target = new_target * channel_share
        needed_users = int(channel_target / ly_new_aus) if ly_new_aus > 0 else 0
        user_gap = needed_users - int(ly_new_users * NEW_CUSTOMER_GROWTH_FACTOR)

        total_new_users += needed_users
        new_channel_breakdown.append({
            "channel": channel,
            "ly_new_users": ly_new_users,
            "ly_new_aus": round(ly_new_aus, 2),
            "channel_target_gmv": round(channel_target, 2),
            "needed_users": needed_users,
            "user_gap": user_gap,
        })

    # 5. 新客倒推到UV：所需UV = 新客目标 / (客单价 × 入会率 × 首单转化率)
    # 简化：所需新客人数 / 入会率 ≈ 所需UV
    estimated_conversion = 0.4  # 新客首单转化率参考
    needed_uv = int(total_new_users / (uv_data["member_join_rate"] * estimated_conversion)) if uv_data["member_join_rate"] > 0 else 0
    uv_gap = needed_uv - uv_data["uv"]

    # 6. 补gap建议
    suggestions = []
    # 老客缺口建议
    old_total_gap = sum(item["user_gap"] for item in r_interval_breakdown if item["user_gap"] > 0)
    if old_total_gap > 0:
        old_suggestions = ["建议加大老客触达力度，提升回购率"]
        for item in r_interval_breakdown:
            if item["user_gap"] > 0 and item["user_gap"] > item["current_users"] * 0.3:
                old_suggestions.append(f"{item['r_interval']}({item['f_segment']})缺口较大，建议针对性加深offer或增加触达轮次")
            elif item["r_interval"] in ("近7-12个月已购客", "近13-24个月已购客", "2年外已购客") and item["user_gap"] > 0:
                old_suggestions.append(f"{item['r_interval']}沉睡人群缺口，建议发送唤醒券")
        suggestions.append({
            "dimension": "老客",
            "gap_users": old_total_gap,
            "suggestions": old_suggestions,
            "priority": "P0" if old_total_gap > total_old_users * 0.2 else "P1"
        })

    # 新客缺口建议
    new_total_gap_users = sum(item["user_gap"] for item in new_channel_breakdown if item["user_gap"] > 0)
    if new_total_gap_users > 0 or uv_gap > 0:
        new_suggestions = []
        if uv_gap > 0:
            new_suggestions.append(f"UV缺口{uv_gap:,}，建议加大派样力度（U先/小美盒）或增加付费推广")
        new_suggestions.append("提升入会率：优化入会引导、增加0.01特权钩子")
        suggestions.append({
            "dimension": "新客",
            "gap_users": new_total_gap_users,
            "uv_gap": uv_gap,
            "suggestions": new_suggestions,
            "priority": "P0" if uv_gap > uv_data["uv"] * 0.3 else "P1"
        })

    return {
        "mode": "reverse",
        "mode_label": "倒拆（从目标反推）",
        "target_gmv": round(target_gmv, 2),
        "total_estimate": None,  # 倒拆不输出预估，直接给所需
        "total_gap": None,
        "gap_ratio": None,
        "old_customer": {
            "old_users_total": total_old_users,
            "old_gmv_target": round(old_target, 2),
            "r_interval_breakdown": r_interval_breakdown,
        },
        "new_customer": {
            "new_gmv_target": round(new_target, 2),
            "channel_breakdown": new_channel_breakdown,
            "uv_reference": uv_data["uv"],
            "member_join_rate": uv_data["member_join_rate"],
            "needed_uv": needed_uv,
            "uv_gap": uv_gap,
        },
        "suggestions": suggestions,
        "activity_period": {"start": activity_start, "end": activity_end},
        "reference_period": {"start": ly_start, "end": ly_end},
        "meta": {
            "activity_type": activity_type,
            "repurchase_adjustment": adjustment,
            "metric_type": "GSV",
        },
        "breakdown_logic": {
            "old_customer_formula": "老客目标 → 按去年各R区间GMV占比拆分 → 反推各区所需人数 = 目标GMV/(回购率×客单价) → gap = 所需-现状",
            "old_customer_source": "参见 [PROCEDURE] 芙清老客拆解四步法、[PROCEDURE] 老客RFM分析四步法",
            "new_customer_formula": "新客目标 → 按去年各渠道GMV占比拆分 → 反推所需UV = 新客目标/(客单价×入会率×转化率)",
            "new_customer_source": "参见 [PROCEDURE] 芙清新客拆解、[PROCEDURE] 新客预估三步走、[PROCEDURE] 会员招募量预估三方法",
        },
    }


# ── 补gap建议生成 ─────────────────────────────────────────────

def _generate_suggestions(
    old_gap: float,
    old_target: float,
    new_gap: float,
    new_target: float,
    total_gap: float,
    target_gmv: float
) -> List[Dict[str, Any]]:
    """生成补gap建议"""
    suggestions = []

    if old_gap > 0:
        old_suggestions = []
        if old_gap / old_target > 0.2:
            old_suggestions.append("老客gap较大（>20%），建议加大老客offer力度（复购礼/老客专享券）")
            old_suggestions.append("增加老客触达轮次，短信+客服+群聊组合触达")
        else:
            old_suggestions.append("适当加深老客offer力度")

        old_suggestions.append("唤醒近7-12个月及更久沉睡客户，发送大额回归券")
        old_suggestions.append("针对近1个月高活跃老客，推复购礼/套装提升客单价")

        suggestions.append({
            "dimension": "老客",
            "gap_amount": round(old_gap, 2),
            "suggestions": old_suggestions,
            "priority": "P0" if old_gap / max(old_target, 1) > 0.2 else "P1"
        })

    if new_gap > 0:
        new_suggestions = []
        if new_gap / max(new_target, 1) > 0.2:
            new_suggestions.append("新客gap较大（>20%），建议加大派样力度（U先/小美盒）")
            new_suggestions.append("提升入会率：优化入会引导、增加0.01特权钩子")
        else:
            new_suggestions.append("适当增加新客招募渠道")

        new_suggestions.append("优化钩子商品，提升首单转化率")
        new_suggestions.append("加大达播投入，达播新客是重要新客来源")

        suggestions.append({
            "dimension": "新客",
            "gap_amount": round(new_gap, 2),
            "suggestions": new_suggestions,
            "priority": "P0" if new_gap / max(new_target, 1) > 0.2 else "P1"
        })

    if total_gap > 0 and total_gap / max(target_gmv, 1) > 0.3:
        suggestions.append({
            "dimension": "总店",
            "gap_amount": round(total_gap, 2),
            "suggestions": [
                "总gap较大（>30%），建议重新评估目标合理性",
                "考虑降低目标或延长活动周期",
                "紧急加大达播/店播投入，快速提升GMV"
            ],
            "priority": "P0"
        })

    return suggestions


# ── 主入口 ───────────────────────────────────────────────────

def calculate_one_click_breakdown(
    target_gmv: float,
    activity_start: str,
    activity_end: str,
    last_year_start: Optional[str] = None,
    last_year_end: Optional[str] = None,
    old_customer_ratio_target: Optional[float] = 0.6,
    breakdown_mode: str = "forward",
) -> Dict[str, Any]:
    """
    一键拆解主函数

    Args:
        target_gmv: 全店GSV目标（元）
        activity_start: 活动开始日期 YYYY-MM-DD
        activity_end: 活动结束日期 YYYY-MM-DD
        last_year_start: 去年同期开始（可选，不传则自动推算）
        last_year_end: 去年同期结束（可选）
        old_customer_ratio_target: 老客占比目标（默认60%）
        breakdown_mode: 拆解模式 "forward"（顺拆）或 "reverse"（倒拆）

    Returns:
        拆解结果字典

    Note:
        仅支持GSV口径（is_refund=FALSE AND order_status!='交易关闭', 剔除购物金）
    """
    # 参数校验
    if breakdown_mode not in ("forward", "reverse"):
        raise ValueError(f"breakdown_mode must be 'forward' or 'reverse', got '{breakdown_mode}'")

    conn = get_connection()
    try:
        # 1. 自动推算去年同期
        if not last_year_start or not last_year_end:
            ly_start, ly_end = _get_default_ly_dates(activity_start, activity_end)
        else:
            ly_start, ly_end = last_year_start, last_year_end

        activity_type = _detect_activity_type(activity_start, activity_end)
        adjustment = REPURCHASE_ADJUSTMENT.get(activity_type, 1.1)

        if breakdown_mode == "forward":
            result = _forward_breakdown(
                conn, target_gmv, activity_start, activity_end,
                ly_start, ly_end, old_customer_ratio_target,
                activity_type, adjustment
            )
        else:
            result = _reverse_breakdown(
                conn, target_gmv, activity_start, activity_end,
                ly_start, ly_end, old_customer_ratio_target,
                activity_type, adjustment
            )

        return result

    finally:
        conn.close()
