"""
芙清 CRM - 派样看板服务

两个核心 API：
1. get_sampling_roi()   — U先/百补 派样ROI分析（1-90天自由窗口回购，按品类拆分）
2. get_sampling_lock_analysis() — 0.01锁权分析（按大促+年份，同比对比）
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
import duckdb
from backend.db.connection import get_connection
from backend.contracts.sampling import SamplingLevelSummary
from backend.semantic.calculations import yoy_absolute, yoy_ratio, safe_ratio
from backend.semantic.channels import DB_TO_UI, GIFT_SAMPLE_DB, SHELF_DB
from backend.semantic.filters import expand_channels

logger = logging.getLogger(__name__)

_logger = logging.getLogger(__name__)

# 派样渠道（DB名）
SAMPLING_CHANNELS = ['U先派样', '百补派样']
TTL_SAMPLING_CHANNEL = 'TTL派样'

# 0.01派样与货架渠道引用语义层常量（channels.py为唯一数据源）
# GIFT_SAMPLE_DB = "赠品&0.01渠道" | SHELF_DB = "货架"

# SPU 字段映射（品类维度）— 白名单，防SQL注入
_SPU_LEVELS = {
    'spu_category': 'spu_category',
    'spu_tier': 'spu_tier',
    'spu_product_class': 'spu_product_class',
    'spu_product_subclass': 'spu_product_subclass',
    'spu_cosmetic': 'spu_cosmetic',
}
# 允许的列名集合（用于SQL拼接前校验）
_ALLOWED_SPU_COLUMNS = frozenset(_SPU_LEVELS.values())


def _shift_date_range_year(start_date: str, end_date: str) -> Tuple[str, str]:
    """默认同比窗口：当前日期范围整体回退一年。"""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    try:
        yoy_start = start.replace(year=start.year - 1)
    except ValueError:
        yoy_start = start.replace(year=start.year - 1, day=28)
    try:
        yoy_end = end.replace(year=end.year - 1)
    except ValueError:
        yoy_end = end.replace(year=end.year - 1, day=28)
    return yoy_start.strftime("%Y-%m-%d"), yoy_end.strftime("%Y-%m-%d")


def _empty_channel_metrics(channel: str) -> Dict[str, Any]:
    """空指标模板，用于没有派样数据的窗口。"""
    return {
        'channel': channel,
        'sample_users': 0,
        'repurchase_users': 0,
        'repurchase_rate': 0.0,
        'repurchase_gsv': 0.0,
        'repurchase_aus': 0.0,
        'full_repurchase_users': 0,
        'full_repurchase_rate': 0.0,
        'full_repurchase_gsv': 0.0,
        'full_repurchase_aus': 0.0,
        'nonfull_repurchase_users': 0,
        'nonfull_repurchase_gsv': 0.0,
        'nonfull_repurchase_aus': 0.0,
    }


def _build_channel_metrics(channel: str, row: Tuple[Any, ...]) -> Dict[str, Any]:
    sample_users = int(row[1] or 0)
    repurchase_users = int(row[2] or 0)
    repurchase_gsv = float(row[3] or 0)
    full_users = int(row[4] or 0)
    full_gsv = float(row[5] or 0)
    nonfull_users = int(row[6] or 0)
    nonfull_gsv = float(row[7] or 0)

    return {
        'channel': channel,
        'sample_users': sample_users,
        'repurchase_users': repurchase_users,
        'repurchase_rate': round(safe_ratio(repurchase_users, sample_users), 4),
        'repurchase_gsv': round(repurchase_gsv, 2),
        'repurchase_aus': round(safe_ratio(repurchase_gsv, repurchase_users), 2),
        'full_repurchase_users': full_users,
        'full_repurchase_rate': round(safe_ratio(full_users, sample_users), 4),
        'full_repurchase_gsv': round(full_gsv, 2),
        'full_repurchase_aus': round(safe_ratio(full_gsv, full_users), 2),
        'nonfull_repurchase_users': nonfull_users,
        'nonfull_repurchase_gsv': round(nonfull_gsv, 2),
        'nonfull_repurchase_aus': round(safe_ratio(nonfull_gsv, nonfull_users), 2),
    }


def _add_compare_metrics(
    current: Dict[str, Any],
    compare: Optional[Dict[str, Any]],
    prefix: str,
) -> None:
    """给当前渠道行追加 yoy_* 或 mom_* 字段。"""
    if compare is None:
        return

    current[f'repurchase_users_{prefix}_pct'] = yoy_absolute(
        current.get('repurchase_users'),
        compare.get('repurchase_users'),
    )
    current[f'repurchase_gsv_{prefix}_pct'] = yoy_absolute(
        current.get('repurchase_gsv'),
        compare.get('repurchase_gsv'),
    )
    current[f'repurchase_rate_{prefix}_pp'] = yoy_ratio(
        current.get('repurchase_rate'),
        compare.get('repurchase_rate'),
    )
    current[f'full_repurchase_users_{prefix}_pct'] = yoy_absolute(
        current.get('full_repurchase_users'),
        compare.get('full_repurchase_users'),
    )
    current[f'full_repurchase_gsv_{prefix}_pct'] = yoy_absolute(
        current.get('full_repurchase_gsv'),
        compare.get('full_repurchase_gsv'),
    )
    current[f'full_repurchase_rate_{prefix}_pp'] = yoy_ratio(
        current.get('full_repurchase_rate'),
        compare.get('full_repurchase_rate'),
    )
    current[f'repurchase_aus_{prefix}_pct'] = yoy_absolute(
        current.get('repurchase_aus'),
        compare.get('repurchase_aus'),
    )
    current[f'full_repurchase_aus_{prefix}_pct'] = yoy_absolute(
        current.get('full_repurchase_aus'),
        compare.get('full_repurchase_aus'),
    )
    current[f'nonfull_repurchase_gsv_{prefix}_pct'] = yoy_absolute(
        current.get('nonfull_repurchase_gsv'),
        compare.get('nonfull_repurchase_gsv'),
    )


def _compute_ttl_metrics(
    start_date: str,
    end_date: str,
    window_days: int = 30,
) -> Dict[str, Any]:
    """
    TTL 派样 = U先派样 ∪ 百补派样，人数按 user_id 去重。

    TTL 不是新的 channel 值；GSV/AUS 保持交易汇总口径，不按用户去重。
    """
    conn = get_connection()
    ttl_sql = """
        WITH sample_users AS (
            SELECT o.user_id, MIN(o.pay_time) as first_sample_time
            FROM orders o
            WHERE o.channel IN (?, ?)
              AND o.pay_time >= ?::TIMESTAMP
              AND o.pay_time <= ?::TIMESTAMP + INTERVAL '1' DAY
            GROUP BY o.user_id
        ),
        repurchase AS (
            SELECT su.user_id,
                   su.first_sample_time,
                   o.actual_amount,
                   COALESCE(o.spu_type, '未知') as spu_type,
                   DATEDIFF('day', su.first_sample_time, o.pay_time) as days_between
            FROM sample_users su
            JOIN orders o ON su.user_id = o.user_id
            WHERE o.pay_time > su.first_sample_time
              AND DATEDIFF('day', su.first_sample_time, o.pay_time) <= ?
              AND o.is_refund = FALSE
              AND o.order_status != '交易关闭'
              AND o.channel != '购物金'
        )
        SELECT
            ? as channel,
            COUNT(DISTINCT su.user_id) as sample_users,
            COUNT(DISTINCT CASE WHEN r.days_between <= ? THEN r.user_id END) as repurchase_users,
            SUM(CASE WHEN r.days_between <= ? THEN r.actual_amount ELSE 0 END) as repurchase_gsv,
            COUNT(DISTINCT CASE WHEN r.days_between <= ? AND r.spu_type = '正装' THEN r.user_id END) as full_repurchase_users,
            SUM(CASE WHEN r.days_between <= ? AND r.spu_type = '正装' THEN r.actual_amount ELSE 0 END) as full_repurchase_gsv,
            COUNT(DISTINCT CASE WHEN r.days_between <= ? AND r.spu_type != '正装' THEN r.user_id END) as nonfull_repurchase_users,
            SUM(CASE WHEN r.days_between <= ? AND r.spu_type != '正装' THEN r.actual_amount ELSE 0 END) as nonfull_repurchase_gsv
        FROM sample_users su
        LEFT JOIN repurchase r ON su.user_id = r.user_id
    """
    params = (
        SAMPLING_CHANNELS
        + [start_date, end_date, window_days, TTL_SAMPLING_CHANNEL]
        + [window_days] * 6
    )
    row = conn.execute(ttl_sql, params).fetchone()
    if not row:
        return _empty_channel_metrics(TTL_SAMPLING_CHANNEL)
    return _build_channel_metrics(TTL_SAMPLING_CHANNEL, row)


def _compute_single_channel_metrics(
    conn,
    summary_sql: str,
    db_channels: List[str],
    start_date: str,
    end_date: str,
    window_days: int,
) -> List[Dict[str, Any]]:
    summary_params = db_channels + [start_date, end_date, window_days] + [window_days] * 6
    summary_rows = conn.execute(summary_sql, summary_params).fetchall()

    result = []
    for row in summary_rows:
        ch = row[0]
        result.append(_build_channel_metrics(DB_TO_UI.get(ch, ch), row))
    order = {channel: idx for idx, channel in enumerate(SAMPLING_CHANNELS)}
    result.sort(key=lambda item: order.get(item['channel'], len(order)))
    return result


def get_sampling_roi(
    start_date: str,
    end_date: str,
    window_days: int = 30,
    level: str = 'spu_category',
    channel: Optional[str] = None,
    compare_date_range: Optional[Tuple[str, str]] = None,
) -> Dict[str, Any]:
    """
    派样 ROI 分析

    Args:
        start_date: 派样起始日期
        end_date: 派样结束日期
        window_days: 回购窗口天数（1-90）
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

    window_days = max(1, min(int(window_days), 90))
    _max_window_days = window_days  # noqa: F841 (保留作 docstring 引用, Sprint 154 之前已有)

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
            SELECT o.user_id, o.channel,
                   MIN(o.pay_time) as first_sample_time,
                   MIN(COALESCE(s.sample_received_at, o.pay_time)) as first_sample_received_at,
                   (ARRAY_AGG(COALESCE(o.spu_category, '未知') ORDER BY o.pay_time ASC))[1] as sample_category,
                   (ARRAY_AGG(COALESCE(o.{cat_field}, '未知') ORDER BY o.pay_time ASC))[1] as sample_level_value
            FROM orders o
            LEFT JOIN orders s ON s.order_id = o.sub_order_id
                AND s.channel = '{GIFT_SAMPLE_DB}'
            WHERE o.channel IN ({ch_placeholders})
              AND o.pay_time >= ?::TIMESTAMP AND o.pay_time <= ?::TIMESTAMP + INTERVAL '1' DAY
            GROUP BY o.user_id, o.channel
        """
        sample_params = db_channels + [start_date, end_date]

        # ── 渠道汇总（按 window_days 单窗口计算）──
        # params: sample_params（N+2） + [max_window_days] + [window_days] * 6
        summary_sql = f"""
            WITH sample_users AS ({sample_users_sql}),
            repurchase AS (
                SELECT su.user_id, su.channel, su.first_sample_time,
                       o.pay_time as repurchase_time,
                       o.actual_amount,
                       COALESCE(o.spu_type, '未知') as spu_type,
                       DATEDIFF('day', su.first_sample_time, o.pay_time) as days_between
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
                COUNT(DISTINCT su.user_id) as sample_users,
                COUNT(DISTINCT CASE WHEN r.days_between <= ? THEN r.user_id END) as repurchase_users,
                SUM(CASE WHEN r.days_between <= ? THEN r.actual_amount ELSE 0 END) as repurchase_gsv,
                COUNT(DISTINCT CASE WHEN r.days_between <= ? AND r.spu_type = '正装' THEN r.user_id END) as full_repurchase_users,
                SUM(CASE WHEN r.days_between <= ? AND r.spu_type = '正装' THEN r.actual_amount ELSE 0 END) as full_repurchase_gsv,
                COUNT(DISTINCT CASE WHEN r.days_between <= ? AND r.spu_type != '正装' THEN r.user_id END) as nonfull_repurchase_users,
                SUM(CASE WHEN r.days_between <= ? AND r.spu_type != '正装' THEN r.actual_amount ELSE 0 END) as nonfull_repurchase_gsv
            FROM (SELECT DISTINCT user_id, channel FROM sample_users) su
            LEFT JOIN repurchase r ON su.user_id = r.user_id AND su.channel = r.channel
            GROUP BY su.channel
        """
        single_channel_result = _compute_single_channel_metrics(
            conn,
            summary_sql,
            db_channels,
            start_date,
            end_date,
            window_days,
        )
        ttl_row = _compute_ttl_metrics(start_date, end_date, window_days)
        channels_result = [ttl_row] + single_channel_result

        if compare_date_range:
            cmp_start, cmp_end = compare_date_range
            compare_single = _compute_single_channel_metrics(
                conn,
                summary_sql,
                db_channels,
                cmp_start,
                cmp_end,
                window_days,
            )
            compare_by_channel = {row['channel']: row for row in compare_single}
            compare_by_channel[TTL_SAMPLING_CHANNEL] = _compute_ttl_metrics(
                cmp_start,
                cmp_end,
                window_days,
            )
            # compare_date_range 真值 → MOM/custom 模式 (auto_yoy 已在上方 else 分支处理)
            compare_prefix = 'mom'
            for row in channels_result:
                _add_compare_metrics(
                    row,
                    compare_by_channel.get(row['channel']),
                    compare_prefix,
                )
        else:
            yoy_start, yoy_end = _shift_date_range_year(start_date, end_date)
            compare_single = _compute_single_channel_metrics(
                conn,
                summary_sql,
                db_channels,
                yoy_start,
                yoy_end,
                window_days,
            )
            compare_by_channel = {row['channel']: row for row in compare_single}
            compare_by_channel[TTL_SAMPLING_CHANNEL] = _compute_ttl_metrics(
                yoy_start,
                yoy_end,
                window_days,
            )
            for row in channels_result:
                _add_compare_metrics(
                    row,
                    compare_by_channel.get(row['channel']),
                    'yoy',
                )

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
                       COALESCE(o.spu_type, '未知') as spu_type,
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
                su.sample_level_value,
                COUNT(DISTINCT su.user_id) as sample_users,
                COUNT(DISTINCT r.user_id) as repurchase_users,
                COALESCE(SUM(r.actual_amount), 0) as repurchase_gsv,
                SUM(r.is_same_category) as same_cat_users,
                COUNT(DISTINCT CASE WHEN r.spu_type = '正装' THEN r.user_id END) as full_repurchase_users,
                COALESCE(SUM(CASE WHEN r.spu_type = '正装' THEN r.actual_amount ELSE 0 END), 0) as full_repurchase_gsv,
                COUNT(DISTINCT CASE WHEN r.spu_type != '正装' THEN r.user_id END) as nonfull_repurchase_users,
                COALESCE(SUM(CASE WHEN r.spu_type != '正装' THEN r.actual_amount ELSE 0 END), 0) as nonfull_repurchase_gsv
            FROM (SELECT DISTINCT user_id, channel, sample_category, sample_level_value FROM sample_users) su
            LEFT JOIN repurchase r ON su.user_id = r.user_id AND su.channel = r.channel
            GROUP BY su.channel, su.sample_level_value
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
            full_users = int(row[6] or 0)
            full_gsv = float(row[7] or 0)
            nonfull_users = int(row[8] or 0)
            nonfull_gsv = float(row[9] or 0)

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
                'full_repurchase_users': full_users,
                'full_repurchase_rate': round(safe_ratio(full_users, su), 4),
                'full_repurchase_gsv': round(full_gsv, 2),
                'full_repurchase_aus': round(safe_ratio(full_gsv, full_users), 2),
                'nonfull_repurchase_users': nonfull_users,
                'nonfull_repurchase_gsv': round(nonfull_gsv, 2),
                'nonfull_repurchase_aus': round(safe_ratio(nonfull_gsv, nonfull_users), 2),
            })

        # Sprint 154: 02 板块新增 YOY/MOM - 复用同 cat_sql 但跑 compare date range
        # compare_date_range 真值 → MOM/custom; else → YOY (auto_yoy 已在 channels_result 分支处理)
        if compare_date_range:
            cmp_start, cmp_end = compare_date_range
            compare_prefix = 'mom'
        else:
            cmp_start, cmp_end = _shift_date_range_year(start_date, end_date)
            compare_prefix = 'yoy'
        compare_cat_sql = cat_sql
        compare_cat_params = list(db_channels) + [cmp_start, cmp_end, window_days]
        compare_cat_rows = conn.execute(compare_cat_sql, compare_cat_params).fetchall()
        compare_cat_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for row in compare_cat_rows:
            ch_db = row[0]
            cat = row[1]
            su_c = int(row[2] or 0)
            ru_c = int(row[3] or 0)
            gsv_c = float(row[4] or 0)
            full_users_c = int(row[6] or 0)
            full_gsv_c = float(row[7] or 0)
            nonfull_gsv_c = float(row[9] or 0)
            compare_cat_by_key[(DB_TO_UI.get(ch_db, ch_db), cat)] = {
                'repurchase_users': ru_c,
                'repurchase_rate': round(safe_ratio(ru_c, su_c), 4),
                'repurchase_gsv': round(gsv_c, 2),
                'repurchase_aus': round(safe_ratio(gsv_c, ru_c), 2),
                'full_repurchase_users': full_users_c,
                'full_repurchase_rate': round(safe_ratio(full_users_c, su_c), 4),
                'full_repurchase_gsv': round(full_gsv_c, 2),
                'full_repurchase_aus': round(safe_ratio(full_gsv_c, full_users_c), 2),
                'nonfull_repurchase_gsv': round(nonfull_gsv_c, 2),
            }

        # Sprint 139: DQM 守卫 — 正装 GSV 占比偏低时返回 warnings, 不阻断 API
        total_posize_gsv = sum(c.get('full_repurchase_gsv', 0) for c in channels_result)
        total_gsv = sum(c.get('repurchase_gsv', 0) for c in channels_result)
        posize_ratio = safe_ratio(total_posize_gsv, total_gsv)
        quality_flags = []
        if total_gsv > 0 and posize_ratio < 0.30:
            quality_flags.append({
                'code': 'POSIZE_RATIO_LOW',
                'severity': 'warning',
                'message': f'派样人群 {window_days} 天正装 GSV 占比仅 {posize_ratio:.1%} (< 30%), 可能是业务表现差或数据缺失',
                'posize_ratio': round(posize_ratio, 4),
                'total_posize_gsv': round(total_posize_gsv, 2),
                'total_gsv': round(total_gsv, 2),
            })
        if quality_flags:
            _logger.warning("[Sprint 139 DQM] %s", quality_flags[0]['message'])

        return {
            'summary': {'channels': channels_result},
            'category_breakdown': category_result,
            'time_range': {
                'start': start_date,
                'end': end_date,
                'window_days': window_days,
            },
            'quality_flags': quality_flags,
            'summary_by_level': _group_by_level(
                category_result,
                level,
                compare_by_key=compare_cat_by_key,
                compare_prefix=compare_prefix,
            ),
        }
    finally:
        pass


def _group_by_level(
    cat_rows: List[Dict[str, Any]],
    level: str,
    compare_by_key: Optional[Dict[Tuple[str, str], Dict[str, Any]]] = None,
    compare_prefix: str = 'yoy',
) -> Dict[str, List[SamplingLevelSummary]]:
    """把既有 category_result 按当前 level 值分组，避免新增 SQL 查询.

    Sprint 154: 可选传 compare_by_key (按 (channel_ui, level_value) 索引) + compare_prefix
    ('yoy' | 'mom') 给每行加 9 个对比字段 (repurchase_users/gsv/rate 等).
    """
    grouped: Dict[str, List[SamplingLevelSummary]] = {}
    for row in cat_rows:
        level_value = row.get('category') or '未知'
        # base kwargs (跟 SamplingLevelSummary schema 字段对齐)
        base_kwargs: Dict[str, Any] = dict(
            channel=row['channel'],
            level=level,
            level_value=level_value,
            sample_users=row['sample_users'],
            repurchase_users=row['repurchase_users'],
            repurchase_rate=row['repurchase_rate'],
            repurchase_gsv=row['repurchase_gsv'],
            repurchase_aus=row['repurchase_aus'],
            full_repurchase_users=row['full_repurchase_users'],
            full_repurchase_rate=row['full_repurchase_rate'],
            full_repurchase_gsv=row['full_repurchase_gsv'],
            full_repurchase_aus=row['full_repurchase_aus'],
            nonfull_repurchase_users=row['nonfull_repurchase_users'],
            nonfull_repurchase_gsv=row['nonfull_repurchase_gsv'],
            nonfull_repurchase_aus=row['nonfull_repurchase_aus'],
        )
        # Sprint 154: YOY/MOM 合并 (跟 _add_compare_metrics 同模式, 但走副本避免污染 cat_rows)
        if compare_by_key is not None:
            cmp_dict = compare_by_key.get((row['channel'], level_value))
            if cmp_dict is not None:
                tmp = dict(base_kwargs)
                _add_compare_metrics(tmp, cmp_dict, compare_prefix)
                # 提取 yoy/mom 后缀字段到 base_kwargs
                for k, v in tmp.items():
                    if k.endswith(f'_{compare_prefix}_pct') or k.endswith(f'_{compare_prefix}_pp'):
                        base_kwargs[k] = v
        grouped.setdefault(level_value, []).append(SamplingLevelSummary(**base_kwargs))
    return grouped


def get_sampling_repurchase_buckets(
    start_date: str,
    end_date: str,
    window_days: int = 90,
    channel: Optional[str] = None,
    only_full: bool = False,
) -> Dict[str, Any]:
    """
    回购周期分布：0-7d / 8-30d / 31-60d / 61-90d。

    channel 为空或 TTL派样 时按 U先∪百补聚合；单渠道时仍走 channel 展开和参数化。
    only_full=True 时只统计 spu_type='正装' 的回购, 用于 02 板块"回购周期分布率"。
    """
    window_days = max(1, min(int(window_days), 90))
    conn = get_connection()

    if channel is None or channel == TTL_SAMPLING_CHANNEL:
        sample_users_sql = """
            SELECT o.user_id, MIN(o.pay_time) as first_sample_time
            FROM orders o
            WHERE o.channel IN (?, ?)
              AND o.pay_time >= ?::TIMESTAMP
              AND o.pay_time <= ?::TIMESTAMP + INTERVAL '1' DAY
            GROUP BY o.user_id
        """
        sample_params = SAMPLING_CHANNELS + [start_date, end_date]
    else:
        db_channels = expand_channels([channel])
        ch_placeholders = ','.join(['?'] * len(db_channels))
        sample_users_sql = f"""
            SELECT o.user_id, MIN(o.pay_time) as first_sample_time
            FROM orders o
            WHERE o.channel IN ({ch_placeholders})
              AND o.pay_time >= ?::TIMESTAMP
              AND o.pay_time <= ?::TIMESTAMP + INTERVAL '1' DAY
            GROUP BY o.user_id
        """
        sample_params = db_channels + [start_date, end_date]

    full_filter = "AND o.spu_type = '正装'" if only_full else ""

    bucket_sql = f"""
        WITH sample_users AS ({sample_users_sql}),
        sample_count AS (SELECT COUNT(DISTINCT user_id) as cnt FROM sample_users),
        repurchase AS (
            SELECT su.user_id,
                   o.actual_amount,
                   DATEDIFF('day', su.first_sample_time, o.pay_time) as days_between
            FROM sample_users su
            JOIN orders o ON su.user_id = o.user_id
            WHERE o.pay_time > su.first_sample_time
              AND DATEDIFF('day', su.first_sample_time, o.pay_time) <= ?
              AND o.is_refund = FALSE
              AND o.order_status != '交易关闭'
              AND o.channel != '购物金'
              {full_filter}
        )
        SELECT
            CASE
                WHEN days_between <= 7 THEN '0-7d'
                WHEN days_between <= 30 THEN '8-30d'
                WHEN days_between <= 60 THEN '31-60d'
                ELSE '61-90d'
            END as bucket,
            COUNT(DISTINCT user_id) as users,
            SUM(actual_amount) as gsv,
            (SELECT cnt FROM sample_count) as sample_users_count
        FROM repurchase
        GROUP BY bucket
    """
    rows = conn.execute(bucket_sql, sample_params + [window_days]).fetchall()
    bucket_map = {
        row[0]: (int(row[1] or 0), float(row[2] or 0))
        for row in rows
    }
    sample_users_count = int(rows[0][3]) if rows else 0

    buckets = []
    for bucket in ['0-7d', '8-30d', '31-60d', '61-90d']:
        users, gsv = bucket_map.get(bucket, (0, 0.0))
        buckets.append({
            'bucket': bucket,
            'users': users,
            'gsv': round(gsv, 2),
            'aus': round(safe_ratio(gsv, users), 2),
        })

    return {
        'buckets': buckets,
        'window_days': window_days,
        'sample_users_count': sample_users_count,
    }


def _shift_year(date_str: str, years: int) -> str:
    """YYYY-MM-DD 平移指定年数; 处理闰年 2/29 → 2/28.

    复用 health/repurchase.py:_shift_date_year 的闰年处理逻辑, 但本函数仅 YYYY-MM-DD.
    """
    d = datetime.strptime(date_str, "%Y-%m-%d")
    try:
        d = d.replace(year=d.year + years)
    except ValueError:
        d = d.replace(year=d.year + years, day=28)
    return d.strftime("%Y-%m-%d")


def get_sampling_repurchase_tracking(
    start_date: str,
    end_date: str,
    window_days: int = 90,
    channel: Optional[str] = None,
) -> Dict[str, Any]:
    """Sprint 169 回购周期跟踪 (3 年对比).

    对当前期间 / 上一年同期 / 前年同期 各自跑一次 get_sampling_repurchase_buckets,
    拼出 3 年 × 4 桶 的扁平 bucket 列表, 供前端 ECharts grouped bar 渲染.

    期间算法:
      - cur  = [start_date, end_date]
      - ly   = [_shift_year(start_date, -1), _shift_year(end_date, -1)]
      - prev2 = [_shift_year(start_date, -2), _shift_year(end_date, -2)]

    注意 (L4.20 SSOT): 3 年桶人数不可加总 (cur 是 2026 已派样老客, prev2 是 2024 派样老客,
    业务上不是同一群人), 仅用作同桶跨年趋势对比 (Sprint 169 02 板块柱状图).
    """
    window_days = max(1, min(int(window_days), 90))
    # 动态推算当前年份 (治根: 硬编码 2026/2025/2024 在 2027+ 会全错 1 年, adversarial review P0)
    current_year = datetime.strptime(end_date, "%Y-%m-%d").year
    year_ranges = [
        (f"{current_year}年", start_date, end_date),
        (f"{current_year - 1}年", _shift_year(start_date, -1), _shift_year(end_date, -1)),
        (f"{current_year - 2}年", _shift_year(start_date, -2), _shift_year(end_date, -2)),
    ]

    flat_buckets: List[Dict[str, Any]] = []
    year_labels: List[str] = []
    for year_label, yr_start, yr_end in year_ranges:
        year_labels.append(year_label)
        try:
            result = get_sampling_repurchase_buckets(
                start_date=yr_start,
                end_date=yr_end,
                window_days=window_days,
                channel=channel,
                only_full=True,
            )
            bucket_map = {b['bucket']: b['users'] for b in result['buckets']}
            sample_users_count = int(result.get('sample_users_count') or 0)
        except (duckdb.Error, ValueError, KeyError) as e:
            # 早期年份订单表可能尚未覆盖, 回落 0 + 记 warning (adversarial review P1:
            # 静默吞 Exception 会让真 SQL bug 看起来像 0 数据, 不可观测)
            logger.warning(
                "repurchase_tracking year=%s period=%s~%s failed: %s",
                year_label, yr_start, yr_end, e,
            )
            bucket_map = {}
            sample_users_count = 0

        for bucket_name in ['0-7d', '8-30d', '31-60d', '61-90d']:
            users = int(bucket_map.get(bucket_name, 0))
            rate = round(safe_ratio(users, sample_users_count), 4)
            flat_buckets.append({
                'bucket': bucket_name,
                'year_label': year_label,
                'rate': rate,
                'year_range_start': yr_start,
                'year_range_end': yr_end,
            })

    return {
        'buckets': flat_buckets,
        'year_labels': year_labels,
        'time_range': {
            'start': start_date,
            'end': end_date,
            'window_days': window_days,
        },
        'window_days': window_days,
    }


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
    """计算单个大促周期的锁权指标（Sprint 142 单 SQL 合并）."""
    _year, _name, conv_start, conv_end, lock_start, lock_end = campaign_row

    if not lock_start or not lock_end:
        return _empty_lock_data()

    lock_start_str = str(lock_start)
    lock_end_str = str(lock_end)
    conv_start_str = str(conv_start)
    conv_end_str = str(conv_end)

    sql = """
        WITH locked_users AS (
            SELECT DISTINCT user_id
            FROM orders o
            WHERE o.channel = ?
              AND ROUND(o.actual_amount, 2) = 0.01
              AND o.pay_time >= ?::DATE AND o.pay_time <= ?::DATE + INTERVAL '1' DAY
        ),
        locked_with_first AS (
            SELECT lu.user_id, ufp.first_pay_date
            FROM locked_users lu
            LEFT JOIN user_first_purchase ufp ON lu.user_id = ufp.user_id
        ),
        converted_by_user AS (
            SELECT o.user_id, SUM(o.actual_amount) AS lock_gsv
            FROM orders o
            JOIN locked_users lu ON o.user_id = lu.user_id
            WHERE o.pay_time >= ?::DATE AND o.pay_time <= ?::DATE + INTERVAL '1' DAY
              AND o.is_refund = FALSE
              AND o.order_status != '交易关闭'
              AND o.channel != '购物金'
            GROUP BY o.user_id
        ),
        uv AS (
            SELECT COALESCE(SUM(visitors), 0) AS total_uv
            FROM daily_visitors
            WHERE date >= ?::DATE AND date <= ?::DATE
        )
        SELECT
            COUNT(*) AS locked_users,
            (SELECT total_uv FROM uv) AS total_uv,
            COUNT(c.user_id) AS converted_users,
            COALESCE(SUM(c.lock_gsv), 0) AS lock_gsv,
            COUNT(CASE WHEN lwf.first_pay_date >= ?::DATE THEN 1 END) AS new_locked,
            COUNT(CASE WHEN lwf.first_pay_date >= ?::DATE AND c.user_id IS NOT NULL THEN 1 END) AS new_converted,
            COALESCE(SUM(CASE WHEN lwf.first_pay_date >= ?::DATE THEN c.lock_gsv ELSE 0 END), 0) AS new_gsv
        FROM locked_with_first lwf
        LEFT JOIN converted_by_user c ON lwf.user_id = c.user_id
    """
    params = [
        GIFT_SAMPLE_DB,
        lock_start_str,
        lock_end_str,
        conv_start_str,
        conv_end_str,
        conv_start_str,
        conv_end_str,
        lock_start_str,
        lock_start_str,
        lock_start_str,
    ]
    _assert_sql_param_count(sql, params, "_compute_lock_metrics")
    row = conn.execute(sql, params).fetchone()

    locked_users = int(row[0] or 0)
    total_uv = int(row[1] or 0)
    converted_users = int(row[2] or 0)
    lock_gsv = float(row[3] or 0)
    new_locked = int(row[4] or 0)
    new_converted = int(row[5] or 0)
    new_gsv = float(row[6] or 0)

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


def _assert_sql_param_count(sql: str, params: List[Any], context: str) -> None:
    """L4.7 防御：SQL 占位符数量必须与 params 数量一致."""
    assert sql.count("?") == len(params), (
        f"{context} params mismatch: SQL has {sql.count('?')} ? but {len(params)} params"
    )


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
        FROM orders o
        WHERE o.channel = ?
          AND ROUND(o.actual_amount, 2) = 0.01
          AND o.pay_time >= ?::DATE AND o.pay_time <= ?::DATE + INTERVAL '1' DAY
    """, [GIFT_SAMPLE_DB, sample_start, sample_end_eff]).fetchone()
    locked_users = int(locked_row[0] or 0)

    # ── 新客锁权 ──
    new_locked_row = conn.execute("""
        WITH locked_users AS (
            SELECT DISTINCT user_id
            FROM orders o
            WHERE o.channel = ?
              AND ROUND(o.actual_amount, 2) = 0.01
              AND o.pay_time >= ?::DATE AND o.pay_time <= ?::DATE + INTERVAL '1' DAY
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
            FROM orders o
            WHERE o.channel = ?
              AND ROUND(o.actual_amount, 2) = 0.01
              AND o.pay_time >= ?::DATE AND o.pay_time <= ?::DATE + INTERVAL '1' DAY
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
            FROM orders o
            WHERE o.channel = ?
              AND ROUND(o.actual_amount, 2) = 0.01
              AND o.pay_time >= ?::DATE AND o.pay_time <= ?::DATE + INTERVAL '1' DAY
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
