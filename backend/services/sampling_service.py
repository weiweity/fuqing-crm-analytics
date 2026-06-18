"""
芙清 CRM - 派样看板服务

两个核心 API：
1. get_sampling_roi()   — U先/百补 派样ROI分析（7/30/60天回购，按品类拆分）
2. get_sampling_lock_analysis() — 0.01锁权分析（按大促+年份，同比对比）
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from backend.db.connection import get_connection
from backend.semantic.calculations import yoy_absolute, yoy_ratio, safe_ratio
from backend.semantic.channels import DB_TO_UI, GIFT_SAMPLE_DB, SHELF_DB
from backend.semantic.filters import expand_channels

_logger = logging.getLogger(__name__)

# 派样渠道（DB名）
SAMPLING_CHANNELS = ['U先派样', '百补派样']

# 0.01派样与货架渠道引用语义层常量（channels.py为唯一数据源）
# GIFT_SAMPLE_DB = "赠品&0.01渠道" | SHELF_DB = "货架"

# SPU 字段映射（品类维度）— 白名单，防SQL注入
_SPU_LEVELS = {
    'spu_category': 'spu_category',
    'spu_tier': 'spu_tier',
    'spu_product_class': 'spu_product_class',
}
# 允许的列名集合（用于SQL拼接前校验）
_ALLOWED_SPU_COLUMNS = frozenset(_SPU_LEVELS.values())


def get_sampling_roi(
    start_date: str,
    end_date: str,
    window_days: int = 30,
    level: str = 'spu_category',
    channel: Optional[str] = None,
) -> Dict[str, Any]:
    """
    派样 ROI 分析

    Args:
        start_date: 派样起始日期
        end_date: 派样结束日期
        window_days: 回购窗口天数（7/30/60）
        level: 品类维度
        channel: 筛选特定派样渠道（UI名或DB名）

    Returns:
        {
            summary: { channels: [...] },
            category_breakdown: [...],
            time_range: { start, end, window_days }
        }
    """
    if level not in _SPU_LEVELS:
        _logger.warning("Invalid level '%s', falling back to 'spu_category'", level)
        level = 'spu_category'
    cat_field = _SPU_LEVELS[level]

    # 防注入：校验列名在白名单内
    if cat_field not in _ALLOWED_SPU_COLUMNS:
        raise ValueError(f"Invalid SPU column: {cat_field}")

    # 确定查询渠道（规则3：渠道参数展开）
    if channel:
        db_channels = expand_channels([channel])
    else:
        db_channels = SAMPLING_CHANNELS

    conn = get_connection()
    try:
        # ── Step 1: 派样用户（指定时间窗口内有派样购买的去重用户）──
        # SQL中?出现顺序:
        # sample_users_sql: N(channels) + 2(start_date, end_date)
        ch_placeholders = ','.join(['?'] * len(db_channels))
        sample_users_sql = f"""
            SELECT user_id, channel,
                   MIN(pay_time) as first_sample_time,
                   (ARRAY_AGG(COALESCE(spu_category, '未知') ORDER BY pay_time ASC))[1] as sample_category
            FROM orders
            WHERE channel IN ({ch_placeholders})
              AND pay_time >= ?::TIMESTAMP AND pay_time <= ?::TIMESTAMP + INTERVAL '1' DAY
            GROUP BY user_id, channel
        """
        sample_params = db_channels + [start_date, end_date]

        # ── 渠道汇总（CTE 固定用 <=60，SELECT 中分 7d/30d/60d 计数）──
        # 注意：汇总与品类明细口径不同——汇总始终展示三个窗口（7d/30d/60d），
        # 品类明细按用户选定的 window_days 过滤（钻取场景）
        # params: sample_params（N+2）
        summary_sql = f"""
            WITH sample_users AS ({sample_users_sql}),
            repurchase AS (
                SELECT su.user_id, su.channel, su.first_sample_time,
                       o.pay_time as repurchase_time,
                       o.actual_amount,
                       DATEDIFF('day', su.first_sample_time, o.pay_time) as days_between
                FROM sample_users su
                JOIN orders o ON su.user_id = o.user_id
                WHERE o.pay_time > su.first_sample_time
                  AND DATEDIFF('day', su.first_sample_time, o.pay_time) <= 60
                  AND o.is_refund = FALSE
                  AND o.order_status != '交易关闭'
                  AND o.channel != '购物金'
            )
            SELECT
                su.channel,
                COUNT(DISTINCT su.user_id) as sample_users,
                COUNT(DISTINCT CASE WHEN r.days_between <= 7 THEN r.user_id END) as repurchase_users_7d,
                COUNT(DISTINCT CASE WHEN r.days_between <= 30 THEN r.user_id END) as repurchase_users_30d,
                COUNT(DISTINCT CASE WHEN r.days_between <= 60 THEN r.user_id END) as repurchase_users_60d,
                SUM(CASE WHEN r.days_between <= 7 THEN r.actual_amount ELSE 0 END) as repurchase_gsv_7d,
                SUM(CASE WHEN r.days_between <= 30 THEN r.actual_amount ELSE 0 END) as repurchase_gsv_30d,
                SUM(CASE WHEN r.days_between <= 60 THEN r.actual_amount ELSE 0 END) as repurchase_gsv_60d
            FROM (SELECT DISTINCT user_id, channel FROM sample_users) su
            LEFT JOIN repurchase r ON su.user_id = r.user_id AND su.channel = r.channel
            GROUP BY su.channel
        """
        summary_rows = conn.execute(summary_sql, sample_params).fetchall()

        channels_result = []
        for row in summary_rows:
            ch = row[0]
            sample_users = int(row[1] or 0)
            repurchase_7d = int(row[2] or 0)
            repurchase_30d = int(row[3] or 0)
            repurchase_60d = int(row[4] or 0)
            gsv_7d = float(row[5] or 0)
            gsv_30d = float(row[6] or 0)
            gsv_60d = float(row[7] or 0)

            channels_result.append({
                'channel': DB_TO_UI.get(ch, ch),
                'sample_users': sample_users,
                'repurchase_users_7d': repurchase_7d,
                'repurchase_users_30d': repurchase_30d,
                'repurchase_users_60d': repurchase_60d,
                'repurchase_rate_7d': round(safe_ratio(repurchase_7d, sample_users), 4),
                'repurchase_rate_30d': round(safe_ratio(repurchase_30d, sample_users), 4),
                'repurchase_rate_60d': round(safe_ratio(repurchase_60d, sample_users), 4),
                'repurchase_gsv_7d': round(gsv_7d, 2),
                'repurchase_gsv_30d': round(gsv_30d, 2),
                'repurchase_gsv_60d': round(gsv_60d, 2),
                'repurchase_aus_7d': round(safe_ratio(gsv_7d, repurchase_7d), 2),
                'repurchase_aus_30d': round(safe_ratio(gsv_30d, repurchase_30d), 2),
                'repurchase_aus_60d': round(safe_ratio(gsv_60d, repurchase_60d), 2),
            })

        # ── 品类明细（按用户选定的 window_days 钻取）──
        # cat_field 已通过 _ALLOWED_SPU_COLUMNS 校验，安全用于SQL拼接
        # 同品类判定始终用 spu_category（与 cat_field 无关）
        # params: sample_params(N+2) + [window_days]
        cat_sql = f"""
            WITH sample_users AS ({sample_users_sql}),
            repurchase AS (
                SELECT su.user_id, su.channel, su.first_sample_time,
                       su.sample_category,
                       o.actual_amount,
                       COALESCE(o.{cat_field}, '未知') as repurchase_cat_detail,
                       DATEDIFF('day', su.first_sample_time, o.pay_time) as days_between,
                       CASE WHEN COALESCE(o.spu_category, '未知') = su.sample_category
                            THEN 1 ELSE 0 END as is_same_category
                FROM sample_users su
                JOIN orders o ON su.user_id = o.user_id
                WHERE o.pay_time > su.first_sample_time
                  AND DATEDIFF('day', su.first_sample_time, o.pay_time) <= ?
                  AND o.is_refund = FALSE
                  AND o.order_status != '交易关闭'
                  AND o.channel != '购物金'
            )
            SELECT
                su.channel,
                su.sample_category,
                COUNT(DISTINCT su.user_id) as sample_users,
                COUNT(DISTINCT r.user_id) as repurchase_users,
                COALESCE(SUM(r.actual_amount), 0) as repurchase_gsv,
                SUM(r.is_same_category) as same_cat_users
            FROM (SELECT DISTINCT user_id, channel, sample_category FROM sample_users) su
            LEFT JOIN repurchase r ON su.user_id = r.user_id AND su.channel = r.channel
            GROUP BY su.channel, su.sample_category
            HAVING COUNT(DISTINCT su.user_id) > 0
            ORDER BY su.channel, repurchase_gsv DESC
        """
        cat_params = sample_params + [window_days]
        cat_rows = conn.execute(cat_sql, cat_params).fetchall()

        category_result = []
        for row in cat_rows:
            ch = row[0]
            cat = row[1]
            su = int(row[2] or 0)
            ru = int(row[3] or 0)
            gsv = float(row[4] or 0)
            same = int(row[5] or 0)

            category_result.append({
                'channel': DB_TO_UI.get(ch, ch),
                'category': cat,
                'sample_users': su,
                'repurchase_users': ru,
                'repurchase_rate': round(safe_ratio(ru, su), 4),
                'repurchase_gsv': round(gsv, 2),
                'repurchase_aus': round(safe_ratio(gsv, ru), 2),
                'same_category_repurchase': same,
                'same_category_rate': round(safe_ratio(same, su), 4),
            })

        return {
            'summary': {'channels': channels_result},
            'category_breakdown': category_result,
            'time_range': {
                'start': start_date,
                'end': end_date,
                'window_days': window_days,
            },
        }
    finally:
        pass


def get_sampling_lock_analysis(
    campaign_name: str = 'summer_sale',
    year: int = 2026,
) -> Dict[str, Any]:
    """
    0.01派样锁权分析

    Args:
        campaign_name: 大促名称（summer_sale/double11/spring_festival）
        year: 年份

    Returns:
        {
            campaign_info: { year, campaign_name, lock_start, lock_end, conversion_start, conversion_end },
            current_year: { total_uv, locked_users, lock_rate, ... },
            last_year: { ... },
            yoy: { ... }
        }
    """
    conn = get_connection()
    try:
        # ── 获取活动时间 ──
        current = conn.execute("""
            SELECT year, campaign_name, conversion_start, conversion_end, lock_start, lock_end
            FROM campaign_schedule
            WHERE campaign_name = ? AND year = ?
        """, [campaign_name, year]).fetchone()

        if not current:
            return {
                'campaign_info': {'year': year, 'campaign_name': campaign_name,
                                  'error': f'未找到 {year} {campaign_name} 的活动记录'},
                'current_year': _empty_lock_data(),
                'last_year': _empty_lock_data(),
                'yoy': _empty_lock_data(),
            }

        last_year = conn.execute("""
            SELECT year, campaign_name, conversion_start, conversion_end, lock_start, lock_end
            FROM campaign_schedule
            WHERE campaign_name = ? AND year = ?
        """, [campaign_name, year - 1]).fetchone()

        current_data = _compute_lock_metrics(conn, current)
        last_year_data = _compute_lock_metrics(conn, last_year) if last_year else _empty_lock_data()

        # ── YoY ──
        yoy = _compute_lock_yoy(current_data, last_year_data)

        campaign_info = {
            'year': current[0],
            'campaign_name': current[1],
            'conversion_start': str(current[2]),
            'conversion_end': str(current[3]),
            'lock_start': str(current[4]) if current[4] else None,
            'lock_end': str(current[5]) if current[5] else None,
        }

        return {
            'campaign_info': campaign_info,
            'current_year': current_data,
            'last_year': last_year_data,
            'yoy': yoy,
        }
    finally:
        pass


def _compute_lock_metrics(conn, campaign_row) -> Dict[str, Any]:
    """计算单个大促周期的锁权指标"""
    year, name, conv_start, conv_end, lock_start, lock_end = campaign_row

    if not lock_start or not lock_end:
        return _empty_lock_data()

    lock_start_str = str(lock_start)
    lock_end_str = str(lock_end)
    conv_start_str = str(conv_start)
    conv_end_str = str(conv_end)

    # ── 锁权人数 ──
    # 浮点精确比较：actual_amount 是 DECIMAL(12,2)，使用 ROUND 精确匹配 0.01
    # SQL中?出现顺序: 3(GIFT_SAMPLE_DB, lock_start, lock_end)
    locked = conn.execute("""
        SELECT COUNT(*) as orders, COUNT(DISTINCT user_id) as users
        FROM orders
        WHERE channel = ?
          AND ROUND(actual_amount, 2) = 0.01
          AND pay_time >= ?::DATE AND pay_time <= ?::DATE + INTERVAL '1' DAY
    """, [GIFT_SAMPLE_DB, lock_start_str, lock_end_str]).fetchone()
    locked_users = int(locked[1] or 0)

    # ── 全店访客数 ──
    # SQL中?出现顺序: 2(conv_start, conv_end)
    uv = conn.execute("""
        SELECT COALESCE(SUM(visitors), 0)
        FROM daily_visitors
        WHERE date >= ?::DATE AND date <= ?::DATE
    """, [conv_start_str, conv_end_str]).fetchone()
    total_uv = int(uv[0] or 0)

    # ── 转化人数：锁权用户中，在转化期间有有效订单的去重用户 ──
    # SQL中?出现顺序: 3(GIFT_SAMPLE_DB, lock_start, lock_end) + 2(conv_start, conv_end)
    converted = conn.execute("""
        WITH locked_users AS (
            SELECT DISTINCT user_id
            FROM orders
            WHERE channel = ?
              AND ROUND(actual_amount, 2) = 0.01
              AND pay_time >= ?::DATE AND pay_time <= ?::DATE + INTERVAL '1' DAY
        )
        SELECT COUNT(DISTINCT o.user_id) as converted_users,
               COALESCE(SUM(o.actual_amount), 0) as lock_gsv
        FROM orders o
        JOIN locked_users lu ON o.user_id = lu.user_id
        WHERE o.pay_time >= ?::DATE AND o.pay_time <= ?::DATE + INTERVAL '1' DAY
          AND o.is_refund = FALSE
          AND o.order_status != '交易关闭'
          AND o.channel != '购物金'
    """, [GIFT_SAMPLE_DB, lock_start_str, lock_end_str, conv_start_str, conv_end_str]).fetchone()
    converted_users = int(converted[0] or 0)
    lock_gsv = float(converted[1] or 0)

    # ── 新客判定 ──
    # lock_start_str 在本SQL中出现3次（均为同一个值的重复引用）：
    #   第1-2个: locked_users CTE 的时间范围
    #   第3-5个: first_pay_date 的新客判定阈值
    # SQL中?出现顺序: 3(GIFT_SAMPLE_DB, lock_start, lock_end) + 3(lock_start x3) + 2(conv_start, conv_end)
    new_data = conn.execute("""
        WITH locked_users AS (
            SELECT DISTINCT user_id
            FROM orders
            WHERE channel = ?
              AND ROUND(actual_amount, 2) = 0.01
              AND pay_time >= ?::DATE AND pay_time <= ?::DATE + INTERVAL '1' DAY
        )
        SELECT
            COUNT(DISTINCT lu.user_id) as total_locked,
            COUNT(DISTINCT CASE WHEN ufp.first_pay_date >= ?::DATE THEN lu.user_id END) as new_locked,
            COUNT(DISTINCT CASE WHEN ufp.first_pay_date >= ?::DATE AND o.order_id IS NOT NULL THEN lu.user_id END) as new_converted,
            COALESCE(SUM(CASE WHEN ufp.first_pay_date >= ?::DATE THEN o.actual_amount ELSE 0 END), 0) as new_gsv
        FROM locked_users lu
        LEFT JOIN user_first_purchase ufp ON lu.user_id = ufp.user_id
        LEFT JOIN orders o ON lu.user_id = o.user_id
            AND o.pay_time >= ?::DATE AND o.pay_time <= ?::DATE + INTERVAL '1' DAY
            AND o.is_refund = FALSE AND o.order_status != '交易关闭' AND o.channel != '购物金'
    """, [GIFT_SAMPLE_DB, lock_start_str, lock_end_str, lock_start_str, lock_start_str, lock_start_str, conv_start_str, conv_end_str]).fetchone()

    new_locked = int(new_data[1] or 0)
    new_converted = int(new_data[2] or 0)
    new_gsv = float(new_data[3] or 0)

    lock_rate = safe_ratio(locked_users, total_uv)
    conversion_rate = safe_ratio(converted_users, locked_users)
    lock_aus = safe_ratio(lock_gsv, converted_users)
    new_locked_ratio = safe_ratio(new_locked, locked_users)
    new_conversion_rate = safe_ratio(new_converted, new_locked)
    new_lock_aus = safe_ratio(new_gsv, new_converted)

    return {
        'total_uv': total_uv,
        'locked_users': locked_users,
        'lock_rate': round(lock_rate, 6),
        'converted_users': converted_users,
        'conversion_rate': round(conversion_rate, 4),
        'lock_gsv': round(lock_gsv, 2),
        'lock_aus': round(lock_aus, 2),
        'new_locked_users': new_locked,
        'new_locked_ratio': round(new_locked_ratio, 4),
        'new_converted_users': new_converted,
        'new_conversion_rate': round(new_conversion_rate, 4),
        'new_lock_gsv': round(new_gsv, 2),
        'new_lock_aus': round(new_lock_aus, 2),
    }


def _empty_lock_data() -> Dict[str, Any]:
    return {
        'total_uv': 0, 'locked_users': 0, 'lock_rate': 0,
        'converted_users': 0, 'conversion_rate': 0,
        'lock_gsv': 0, 'lock_aus': 0,
        'new_locked_users': 0, 'new_locked_ratio': 0,
        'new_converted_users': 0, 'new_conversion_rate': 0,
        'new_lock_gsv': 0, 'new_lock_aus': 0,
    }


def _compute_lock_yoy(current: Dict, last: Dict) -> Dict[str, Any]:
    """计算 YoY（绝对值用百分比变化，比率用百分点差）"""
    return {
        'total_uv': yoy_absolute(current['total_uv'], last['total_uv']),
        'locked_users': yoy_absolute(current['locked_users'], last['locked_users']),
        'lock_rate': yoy_ratio(current['lock_rate'], last['lock_rate']),
        'converted_users': yoy_absolute(current['converted_users'], last['converted_users']),
        'conversion_rate': yoy_ratio(current['conversion_rate'], last['conversion_rate']),
        'lock_gsv': yoy_absolute(current['lock_gsv'], last['lock_gsv']),
        'lock_aus': yoy_absolute(current['lock_aus'], last['lock_aus']),
        'new_locked_users': yoy_absolute(current['new_locked_users'], last['new_locked_users']),
        'new_locked_ratio': yoy_ratio(current['new_locked_ratio'], last['new_locked_ratio']),
        'new_converted_users': yoy_absolute(current['new_converted_users'], last['new_converted_users']),
        'new_conversion_rate': yoy_ratio(current['new_conversion_rate'], last['new_conversion_rate']),
        'new_lock_gsv': yoy_absolute(current['new_lock_gsv'], last['new_lock_gsv']),
        'new_lock_aus': yoy_absolute(current['new_lock_aus'], last['new_lock_aus']),
    }


# ============================================================
# 0.01派样滚动同期对比
# ============================================================

def get_rolling_comparison(
    year_a_sample_start: str,
    year_a_sample_end: str,
    year_a_conv_start: str,
    year_b_sample_start: str,
    year_b_sample_end: str,
    year_b_conv_start: str,
    rolling_end: str,
) -> Dict[str, Any]:
    """
    0.01派样滚动同期对比

    以 year_a（当年，如2026）的参数为主，year_b（对比年，如2025）自动T对齐。

    Args:
        year_a_*: 当年的派样期起止 + 转化期起始
        year_b_*: 对比年的派样期起止 + 转化期起始
        rolling_end: 滚动截止日（统一日期）

    Returns:
        {
            year_a: { phase, sample: {...}, conversion: {...} | null },
            year_b: { phase, sample: {...}, conversion: {...} | null },
            yoy: { ... },
            timeline: { T, T_sample_a, T_sample_b, T_conv, ... }
        }
    """
    # ── 解析日期 ──
    dt_a_ss = datetime.strptime(year_a_sample_start, '%Y-%m-%d')
    dt_a_se = datetime.strptime(year_a_sample_end, '%Y-%m-%d')
    dt_a_cs = datetime.strptime(year_a_conv_start, '%Y-%m-%d')
    dt_b_ss = datetime.strptime(year_b_sample_start, '%Y-%m-%d')
    dt_b_se = datetime.strptime(year_b_sample_end, '%Y-%m-%d')
    dt_b_cs = datetime.strptime(year_b_conv_start, '%Y-%m-%d')
    dt_roll = datetime.strptime(rolling_end, '%Y-%m-%d')

    # ── T 计算 ──
    T = (dt_roll - dt_a_ss).days                        # 从 year_a 派样起始的天数偏移
    T_sample_a = (dt_a_se - dt_a_ss).days               # year_a 派样期总天数
    T_sample_b = (dt_b_se - dt_b_ss).days               # year_b 派样期总天数
    T_conv = (dt_roll - dt_a_cs).days                    # 从 year_a 转化起始的天数偏移

    # ── year_a 有效日期 ──
    a_sample_end_eff = min(dt_roll, dt_a_se)
    a_in_conversion = T > T_sample_a and T_conv >= 0

    # ── year_b 自动 T 对齐 ──
    b_equiv_end = dt_b_ss + timedelta(days=T)
    b_sample_end_eff = min(b_equiv_end, dt_b_se)
    b_in_conversion = T > T_sample_b and T_conv >= 0
    b_conv_end = (dt_b_cs + timedelta(days=T_conv)) if (b_in_conversion and T_conv >= 0) else None

    conn = get_connection()
    try:
        year_a_data = _compute_rolling_year_metrics(
            conn,
            sample_start=year_a_sample_start,
            sample_end_eff=str(a_sample_end_eff.date()),
            conv_start=year_a_conv_start,
            conv_end=str(dt_roll.date()) if a_in_conversion else None,
            in_conversion=a_in_conversion,
            new_threshold=year_a_sample_start,
        )

        year_b_data = _compute_rolling_year_metrics(
            conn,
            sample_start=year_b_sample_start,
            sample_end_eff=str(b_sample_end_eff.date()),
            conv_start=year_b_conv_start,
            conv_end=str(b_conv_end.date()) if b_in_conversion and b_conv_end else None,
            in_conversion=b_in_conversion,
            new_threshold=year_b_sample_start,
        )

        yoy = _compute_rolling_yoy(year_a_data, year_b_data)

        return {
            'year_a': year_a_data,
            'year_b': year_b_data,
            'yoy': yoy,
            'timeline': {
                'year_a_sample_start': year_a_sample_start,
                'year_a_sample_end': year_a_sample_end,
                'year_a_conv_start': year_a_conv_start,
                'year_b_sample_start': year_b_sample_start,
                'year_b_sample_end': year_b_sample_end,
                'year_b_conv_start': year_b_conv_start,
                'rolling_end': rolling_end,
                'year_b_equiv_end': str(b_equiv_end.date()),
                'T': T,
                'T_sample_a': T_sample_a,
                'T_sample_b': T_sample_b,
                'T_conv': T_conv,
            },
        }
    finally:
        pass


def _compute_rolling_year_metrics(
    conn,
    sample_start: str,
    sample_end_eff: str,
    conv_start: str,
    conv_end: Optional[str],
    in_conversion: bool,
    new_threshold: str,
) -> Dict[str, Any]:
    """计算单年的滚动指标（派样期 + 可选转化期）"""

    # ── UV ──
    uv_row = conn.execute("""
        SELECT COALESCE(SUM(visitors), 0)
        FROM daily_visitors
        WHERE date >= ?::DATE AND date <= ?::DATE
    """, [sample_start, sample_end_eff]).fetchone()
    total_uv = int(uv_row[0] or 0)

    # ── 锁权人数 ──
    locked_row = conn.execute("""
        SELECT COUNT(DISTINCT user_id) as users
        FROM orders
        WHERE channel = ?
          AND ROUND(actual_amount, 2) = 0.01
          AND pay_time >= ?::DATE AND pay_time <= ?::DATE + INTERVAL '1' DAY
    """, [GIFT_SAMPLE_DB, sample_start, sample_end_eff]).fetchone()
    locked_users = int(locked_row[0] or 0)

    # ── 新客锁权 ──
    new_locked_row = conn.execute("""
        WITH locked_users AS (
            SELECT DISTINCT user_id
            FROM orders
            WHERE channel = ?
              AND ROUND(actual_amount, 2) = 0.01
              AND pay_time >= ?::DATE AND pay_time <= ?::DATE + INTERVAL '1' DAY
        )
        SELECT COUNT(DISTINCT CASE WHEN ufp.first_pay_date >= ?::DATE THEN lu.user_id END)
        FROM locked_users lu
        LEFT JOIN user_first_purchase ufp ON lu.user_id = ufp.user_id
    """, [GIFT_SAMPLE_DB, sample_start, sample_end_eff, new_threshold]).fetchone()
    new_locked_count = int(new_locked_row[0] or 0)

    lock_rate = safe_ratio(locked_users, total_uv)
    new_locked_ratio = safe_ratio(new_locked_count, locked_users)
    old_locked_count = max(0, locked_users - new_locked_count)

    result = {
        'phase': 'conversion' if in_conversion else 'sample',
        'total_uv': total_uv,
        'locked_users': locked_users,
        'lock_rate': round(lock_rate, 6),
        'new_locked_users': new_locked_count,
        'new_locked_ratio': round(new_locked_ratio, 4),
        'old_locked_users': old_locked_count,
        'old_locked_ratio': round(safe_ratio(old_locked_count, locked_users), 4),
        # 转化指标默认 0（派样期不计算）
        'converted_users': 0,
        'conversion_rate': 0.0,
        'conv_gsv': 0.0,
        'conv_aus': 0.0,
        'new_converted_users': 0,
        'new_conversion_rate': 0.0,
        'new_conv_gsv': 0.0,
        'new_conv_aus': 0.0,
        'old_converted_users': 0,
        'old_conversion_rate': 0.0,
    }

    if not in_conversion or not conv_end:
        return result

    # ── 加赠转化人数：货架渠道 + 累计 ≥ 100 ──
    conv_row = conn.execute("""
        WITH locked_users AS (
            SELECT DISTINCT user_id
            FROM orders
            WHERE channel = ?
              AND ROUND(actual_amount, 2) = 0.01
              AND pay_time >= ?::DATE AND pay_time <= ?::DATE + INTERVAL '1' DAY
        ),
        shelf_users AS (
            SELECT o.user_id, SUM(o.actual_amount) as shelf_total
            FROM orders o
            JOIN locked_users lu ON o.user_id = lu.user_id
            WHERE o.channel = ?
              AND o.pay_time >= ?::DATE AND o.pay_time <= ?::DATE + INTERVAL '1' DAY
              AND o.is_refund = FALSE
              AND o.order_status != '交易关闭'
            GROUP BY o.user_id
            HAVING SUM(o.actual_amount) >= 100
        )
        SELECT COUNT(*) as converted, COALESCE(SUM(shelf_total), 0) as gsv
        FROM shelf_users
    """, [GIFT_SAMPLE_DB, sample_start, sample_end_eff, SHELF_DB, conv_start, conv_end]).fetchone()

    converted_users = int(conv_row[0] or 0)
    conv_gsv = float(conv_row[1] or 0)

    # ── 新客转化（货架 + ≥100） ──
    new_conv_row = conn.execute("""
        WITH locked_users AS (
            SELECT DISTINCT user_id
            FROM orders
            WHERE channel = ?
              AND ROUND(actual_amount, 2) = 0.01
              AND pay_time >= ?::DATE AND pay_time <= ?::DATE + INTERVAL '1' DAY
        ),
        shelf_users AS (
            SELECT o.user_id, SUM(o.actual_amount) as shelf_total
            FROM orders o
            JOIN locked_users lu ON o.user_id = lu.user_id
            WHERE o.channel = ?
              AND o.pay_time >= ?::DATE AND o.pay_time <= ?::DATE + INTERVAL '1' DAY
              AND o.is_refund = FALSE
              AND o.order_status != '交易关闭'
            GROUP BY o.user_id
            HAVING SUM(o.actual_amount) >= 100
        )
        SELECT
            COUNT(DISTINCT CASE WHEN ufp.first_pay_date >= ?::DATE THEN su.user_id END) as new_converted,
            COALESCE(SUM(CASE WHEN ufp.first_pay_date >= ?::DATE THEN su.shelf_total ELSE 0 END), 0) as new_gsv
        FROM shelf_users su
        LEFT JOIN user_first_purchase ufp ON su.user_id = ufp.user_id
    """, [GIFT_SAMPLE_DB, sample_start, sample_end_eff, SHELF_DB, conv_start, conv_end, new_threshold, new_threshold]).fetchone()

    new_converted = int(new_conv_row[0] or 0)
    new_conv_gsv = float(new_conv_row[1] or 0)
    old_converted = max(0, converted_users - new_converted)
    old_locked = max(0, locked_users - new_locked_count)

    result.update({
        'converted_users': converted_users,
        'conversion_rate': round(safe_ratio(converted_users, locked_users), 4),
        'conv_gsv': round(conv_gsv, 2),
        'conv_aus': round(safe_ratio(conv_gsv, converted_users), 2),
        'new_converted_users': new_converted,
        'new_conversion_rate': round(safe_ratio(new_converted, new_locked_count), 4),
        'new_conv_gsv': round(new_conv_gsv, 2),
        'new_conv_aus': round(safe_ratio(new_conv_gsv, new_converted), 2),
        'old_converted_users': old_converted,
        'old_conversion_rate': round(safe_ratio(old_converted, old_locked), 4),
    })

    return result


def _compute_rolling_yoy(a: Dict, b: Dict) -> Dict[str, Any]:
    """滚动对比 YoY（绝对值用百分比变化，比率用百分点差）"""
    return {
        'total_uv': yoy_absolute(a['total_uv'], b['total_uv']),
        'locked_users': yoy_absolute(a['locked_users'], b['locked_users']),
        'lock_rate': yoy_ratio(a['lock_rate'], b['lock_rate']),
        'new_locked_users': yoy_absolute(a['new_locked_users'], b['new_locked_users']),
        'new_locked_ratio': yoy_ratio(a['new_locked_ratio'], b['new_locked_ratio']),
        'converted_users': yoy_absolute(a['converted_users'], b['converted_users']),
        'conversion_rate': yoy_ratio(a['conversion_rate'], b['conversion_rate']),
        'conv_gsv': yoy_absolute(a['conv_gsv'], b['conv_gsv']),
        'conv_aus': yoy_absolute(a['conv_aus'], b['conv_aus']),
        'new_converted_users': yoy_absolute(a['new_converted_users'], b['new_converted_users']),
        'new_conversion_rate': yoy_ratio(a['new_conversion_rate'], b['new_conversion_rate']),
        'new_conv_gsv': yoy_absolute(a['new_conv_gsv'], b['new_conv_gsv']),
        'new_conv_aus': yoy_absolute(a['new_conv_aus'], b['new_conv_aus']),
    }
