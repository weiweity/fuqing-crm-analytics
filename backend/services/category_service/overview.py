"""
品类分析服务
Sample CRM 客户分析系统 - 品类分析服务
Week 4 品类分布、品类象限矩阵、品类用户画像
"""
import duckdb
import time
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional, List, Tuple

from backend.db.connection import get_connection
from backend.services.category_display import (
    apply_catalog_display_names,
    mask_category_name,
)
from backend.services.category_service._shared import rfm_asof_cte
from backend.semantic.filters import FilterBuilder, MetricType, expand_channels
from backend.semantic.calculations import yoy_absolute, yoy_ratio

# L4.75 market-focus 性能治本 (跟 L4.74 cache end_date fix + L4.71 RFM 业务治本 1:1 stable 永久规则化沿用):
# 内存 cache 24h TTL 避免 96 次 HTTP 调用触发 429 Too Many Requests (跟 L4.36 graceful retry + L4.74 1:1 stable 永久规则化沿用)
# Sprint 205+ L4.75 PC2 10 业务分析师 0 雪崩 1:1 stable permanent rule 链配套
_CACHE_TTL_SECONDS = 86400  # 24h TTL (跟 L4.74 cache precompute 1:1 stable 永久规则化沿用)
_overview_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}  # {cache_key: (mtime, result)}


def _overview_cache_key(
    start_date: str, end_date: str, level: str, metric_type: str,
    channel: Optional[str], exclude_channels: Optional[List[str]],
    compare_start_date: Optional[str], compare_end_date: Optional[str],
) -> str:
    """算 cache key (跟 L4.74 cache end_date fix 1:1 stable 永久规则化沿用, 跟 L4.71 RFM 业务治本 1:1 stable 永久规则化沿用)"""
    return f"{start_date}_{end_date}_{level}_{metric_type}_{channel}_{','.join(sorted(exclude_channels or []))}_{compare_start_date}_{compare_end_date}"


def get_category_overview_cached(
    start_date: str, end_date: str,
    level: str = "class",
    metric_type: str = "GSV",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """get_category_overview wrapper + 内存 cache 24h TTL (跟 L4.74 cache end_date fix 1:1 stable 永久规则化沿用)

    性能治本: 第二次同 cache_key 查询 < 100ms (避免 96 次 HTTP 调用触发 429, 跟 L4.36 graceful retry 1:1 stable 永久规则化沿用)
    """
    cache_key = _overview_cache_key(
        start_date, end_date, level, metric_type,
        channel, exclude_channels, compare_start_date, compare_end_date,
    )
    cached = _overview_cache.get(cache_key)
    if cached is not None:
        mtime, result = cached
        if time.time() - mtime < _CACHE_TTL_SECONDS:
            return result  # cache 命中, 返回 cached result

    # cache miss 跑实时 SQL
    result = get_category_overview(
        start_date, end_date, level, metric_type, channel, exclude_channels,
        compare_start_date, compare_end_date,
    )
    _overview_cache[cache_key] = (time.time(), result)
    return result


def get_category_overview_batch(
    ranges: List[Dict[str, str]],
    level: str = "class",
    metric_type: str = "GSV",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """批量调用 get_category_overview (跟 L4.74 cache end_date fix 1:1 stable 永久规则化沿用, 跟 L4.36 graceful retry 1:1 stable 永久规则化沿用)

    性能治本: 1 次 HTTP 调用替换 96 次 N 次 (市场对焦核心单品新老客切 weeks=12 触发 daily 84 + weekly 12 = 96 次, 触发 429)
    """
    return [
        get_category_overview_cached(
            start_date=r["start_date"],
            end_date=r["end_date"],
            level=level,
            metric_type=metric_type,
            channel=channel,
            exclude_channels=exclude_channels,
        )
        for r in ranges
    ]


SPU_LEVELS = {
    "category": "spu_category",      # 一级品类
    "type": "spu_type",               # 二级品类
    "tier": "spu_tier",              # 层级
    "class": "spu_product_class",    # 产品类
    "subclass": "spu_product_subclass",  # 产品子类
    "cosmetic": "spu_cosmetic",      # 功效
    "spec": "spu_spec",              # 规格
}

# 非产品品类（营销赠品、虚拟商品、物料等），从品类看板中排除
EXCLUDED_PRODUCT_CATEGORIES = (
    '购物金', '0.01', '邮费补差链接', '明星小卡', '刮刮卡',
    '有价优惠劵', '盲盒', '手持镜', '帆布袋', '帆布包',
    '加湿器', '起泡网', '吸油纸', '硅胶刷', '湿敷棉',
    '洗脸巾', 'PR礼盒', '多品类集合链',
)


def _cat_expr(field: str) -> str:
    """品类字段表达式：TRIM + COALESCE，修复尾部空格问题"""
    return f"COALESCE(TRIM(o.{field}), '未知')"


def _excluded_cat_filter(field: str) -> str:
    """生成排除非产品品类的 SQL 片段"""
    placeholders = ",".join(["?"] * len(EXCLUDED_PRODUCT_CATEGORIES))
    return f"AND TRIM(COALESCE(o.{field}, '未知')) NOT IN ({placeholders})"


# ─────────────────────────────────────────────────────────────
# Sprint 54 Lane A L3 FilterBuilder helpers
#
# 三个 helper 把 overview.py 4 处 SQL 字符串内嵌统一收到 `?` DB-API 参数化.
# 设计原则 (跟 Sprint 53.5 churn.py 一致):
#   1. 所有用户输入 (channel / exclude_channels / level) 走 `?` 占位符.
#   2. metric_type 动态 (GMV/GSV) → fb.with_metric_type(MetricType.GMV/GSV).
#   3. excluded_cat 用 add_extra 收编 (level_col 是 SPU_LEVELS 白名单).
#   4. amount_cond / SAMPLE_CHANNELS 等受控值保留字面量拼接 (白名单安全).
# ─────────────────────────────────────────────────────────────


def _build_category_period_filter(
    start_date: str,
    end_date: str,
    metric_type: str,
    channel: Optional[str],
    exclude_channels: Optional[List[str]],
) -> Tuple[str, List[Any]]:
    """_compute_category_period 过滤器 (动态 metric_type GMV/GSV).

    Returns:
        (where_sql, params) — 含 time range + metric_type base (gmv_base/valid_order)
        + channel IN + exclude_channels NOT IN.
    """
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GMV if metric_type == "GMV" else MetricType.GSV)
    fb.with_time_range(start_date, end_date)
    if channel and channel != "全店":
        db_channels = [c for c in expand_channels([channel]) if c]
        if not db_channels:
            raise ValueError(f"渠道'{channel}'未在channels.py中注册，请检查UI_TO_DB映射")
        fb.with_channels(db_channels)
    if exclude_channels:
        db_ex = [c for c in expand_channels(exclude_channels) if c]
        if db_ex:
            fb.with_exclude_channels(db_ex)
    return fb.build()


def _build_wool_party_filter(
    start_date: str,
    end_date: str,
    channel: Optional[str],
) -> Tuple[str, List[Any]]:
    """窗口订单过滤器 (GSV 口径, 不应用 exclude_channels).

    NOTE: 羊毛党证据依赖低价渠道订单, exclude_channels 通常就是低价渠道列表,
    若应用则窗口小样占比永远为 0.
    """
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_time_range(start_date, end_date)
    if channel and channel != "全店":
        db_channels = [c for c in expand_channels([channel]) if c]
        if not db_channels:
            raise ValueError(f"渠道'{channel}'未在channels.py中注册，请检查UI_TO_DB映射")
        fb.with_channels(db_channels)
    return fb.build()


def _build_wool_lifetime_filter(end_date: str) -> Tuple[str, List[Any]]:
    """终身正装证据：GSV 有效单，截止到窗口末日，无时间窗起点、无渠道剔除."""
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.add_extra("pay_time <= ?", [f"{end_date} 23:59:59.999999"])
    return fb.build()


def _build_value_tier_filter(
    start_date: str,
    end_date: str,
    channel: Optional[str],
    exclude_channels: Optional[List[str]],
) -> Tuple[str, List[Any]]:
    """_compute_value_tier_base 过滤器 (GSV 口径).

    Sprint 60.1 fix: channel/exclude 改走手写 `o.channel IN/NOT IN`,
    避免 FilterBuilder 输出无表别名跟 `LEFT JOIN user_rfm r` 冲突触发 DuckDB Binder 错.
    """
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_time_range(start_date, end_date)
    base_sql, base_params = fb.build()
    # channel/exclude 走手写 (有 o. 前缀, 配 LEFT JOIN user_rfm r 兼容)
    extra_parts: List[str] = []
    extra_params: List[Any] = []
    if channel and channel != "全店":
        db_channels = [c for c in expand_channels([channel]) if c]
        if not db_channels:
            raise ValueError(f"渠道'{channel}'未在channels.py中注册，请检查UI_TO_DB映射")
        placeholders = ",".join(["?"] * len(db_channels))
        extra_parts.append(f"AND o.channel IN ({placeholders})")
        extra_params.extend(db_channels)
    if exclude_channels:
        db_ex = [c for c in expand_channels(exclude_channels) if c]
        if db_ex:
            placeholders = ",".join(["?"] * len(db_ex))
            extra_parts.append(f"AND o.channel NOT IN ({placeholders})")
            extra_params.extend(db_ex)
    final_sql = base_sql + " " + " ".join(extra_parts) if extra_parts else base_sql
    return final_sql, base_params + extra_params


def _compute_category_period(
    conn: duckdb.DuckDBPyConnection,
    start_date: str,
    end_date: str,
    cutoff: str,
    level: str,
    metric_type: str,
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    计算单个周期的品类聚合数据（含TTL合计行 + 会员专属指标）

    使用 GROUPING SETS 一次查询同时返回：
    - 各品类明细行  (GROUPING(category_name) = 0)
    - TTL 合计行    (GROUPING(category_name) = 1, category_name = 'TTL')

    会员指标通过条件聚合在同一条 SQL 中完成，不再需要 member_only 参数。

    Returns:
        {
            "__ttl__": { ... },            # TTL 合计行
            "品类A": { ... },              # 品类明细行
            "品类B": { ... },
            ...
        }
    """
    level_col = SPU_LEVELS.get(level, "spu_type")
    amount_cond = "o.actual_amount > 0" if metric_type == "GMV" else "o.actual_amount >= 0"
    excluded_cat_sql = _excluded_cat_filter(level_col)

    # Sprint 54 Lane A L3: 用 _build_category_period_filter 替代 f-string 拼接
    # (time range + metric_type base + channel + exclude_channels 全走 ? 占位).
    where_sql, where_params = _build_category_period_filter(
        start_date, end_date, metric_type, channel, exclude_channels,
    )
    # params 顺序: SQL `?` 占位符位置一一对应.
    # SQL 顺序 (按 SQL 文本出现位置):
    #   1) DATE(?) cutoff (line 174 `ufp.first_pay_date >= DATE(?)`)
    #   2-3) pay_time >= ? AND pay_time <= ? (where_sql time range, line 177)
    #   4-21) NOT IN (?,?,...×18) EXCLUDED_PRODUCT_CATEGORIES (line 179)
    # Sprint 60 治本: 之前 `[cutoff, start_date, end_date] + EXCLUDED + where_params` 把
    # start_date/end_date 错位插在 EXCLUDED 之前 → 多了 2 个 params → DuckDB InvalidInputException
    # "excess parameters: 22, 23" → API 500. 正确顺序: cutoff + where_params + EXCLUDED.
    params = [cutoff] + list(where_params) + list(EXCLUDED_PRODUCT_CATEGORIES)

    sql = f"""
    WITH period_orders AS (
        SELECT
            {_cat_expr(level_col)} AS category_name,
            o.user_id,
            o.actual_amount,
            o.is_member,
            CASE WHEN ufp.first_pay_date >= DATE(?) THEN 1 ELSE 0 END AS is_new
        FROM orders o
        LEFT JOIN user_first_purchase ufp ON o.user_id = ufp.user_id
        WHERE {where_sql}
          AND ({amount_cond})
          {excluded_cat_sql}
    )
    SELECT
        CASE WHEN GROUPING(category_name) = 1 THEN 'TTL' ELSE category_name END AS category_name,
        GROUPING(category_name) AS is_ttl,
        SUM(actual_amount) AS total_gsv,
        COUNT(DISTINCT user_id) AS total_users,
        SUM(CASE WHEN is_member THEN actual_amount ELSE 0 END) AS member_gsv,
        COUNT(DISTINCT CASE WHEN is_member THEN user_id END) AS member_users,
        SUM(CASE WHEN is_new = 0 THEN actual_amount ELSE 0 END) AS old_gsv,
        COUNT(DISTINCT CASE WHEN is_new = 0 THEN user_id END) AS old_users,
        SUM(CASE WHEN is_new = 1 THEN actual_amount ELSE 0 END) AS new_gsv,
        COUNT(DISTINCT CASE WHEN is_new = 1 THEN user_id END) AS new_users,
        SUM(CASE WHEN is_member AND is_new = 0 THEN actual_amount ELSE 0 END) AS member_old_gsv,
        COUNT(DISTINCT CASE WHEN is_member AND is_new = 0 THEN user_id END) AS member_old_users,
        SUM(CASE WHEN is_member AND is_new = 1 THEN actual_amount ELSE 0 END) AS member_new_gsv,
        COUNT(DISTINCT CASE WHEN is_member AND is_new = 1 THEN user_id END) AS member_new_users
    FROM period_orders
    GROUP BY GROUPING SETS (category_name, ())
    ORDER BY is_ttl, total_gsv DESC
    """

    # Sprint 90 L4.7 ground-truth-lint: 防 params 顺序错位回归 (Sprint 60+60.1.1 实战 fix 模式).
    # SQL `?` 占位符数 vs params 列表长度 必一一对应, 不等 → AssertionError 立刻爆, 不再让 DuckDB
    # InvalidInputException 透传到 API 500. 错误信息含两者具体数字, 便于定位.
    assert sql.count('?') == len(params), (
        f"_compute_category_period params mismatch: SQL has {sql.count('?')} ? placeholders "
        f"but params list has {len(params)} items. Check params order vs SQL `?` positions."
    )
    result = conn.execute(sql, params).fetchall()
    data: Dict[str, Dict[str, Any]] = {}
    for row in result:
        name = row[0]
        is_ttl = int(row[1])
        total_gsv = float(row[2] or 0)
        total_users = int(row[3] or 0)
        member_gsv = float(row[4] or 0)
        member_users = int(row[5] or 0)
        old_gsv = float(row[6] or 0)
        old_users = int(row[7] or 0)
        new_gsv = float(row[8] or 0)
        new_users = int(row[9] or 0)
        member_old_gsv = float(row[10] or 0)
        member_old_users = int(row[11] or 0)
        member_new_gsv = float(row[12] or 0)
        member_new_users = int(row[13] or 0)

        # 全店口径指标
        all_metrics = {
            "gsv": total_gsv,
            "users": total_users,
            "aus": total_gsv / total_users if total_users > 0 else 0.0,
            "member_gsv": member_gsv,
            "member_ratio": member_gsv / total_gsv if total_gsv > 0 else 0.0,
            "old_gsv": old_gsv,
            "old_users": old_users,
            "old_aus": old_gsv / old_users if old_users > 0 else 0.0,
            "old_ratio": old_gsv / total_gsv if total_gsv > 0 else 0.0,
            "new_gsv": new_gsv,
            "new_users": new_users,
            "new_aus": new_gsv / new_users if new_users > 0 else 0.0,
            "new_ratio": new_gsv / total_gsv if total_gsv > 0 else 0.0,
        }
        # 会员专属口径指标（is_member=TRUE 过滤后的数据）
        member_metrics = {
            "gsv": member_gsv,
            "users": member_users,
            "aus": member_gsv / member_users if member_users > 0 else 0.0,
            "member_gsv": member_gsv,
            "member_ratio": member_gsv / total_gsv if total_gsv > 0 else 0.0,
            "old_gsv": member_old_gsv,
            "old_users": member_old_users,
            "old_aus": member_old_gsv / member_old_users if member_old_users > 0 else 0.0,
            "old_ratio": member_old_gsv / member_gsv if member_gsv > 0 else 0.0,
            "new_gsv": member_new_gsv,
            "new_users": member_new_users,
            "new_aus": member_new_gsv / member_new_users if member_new_users > 0 else 0.0,
            "new_ratio": member_new_gsv / member_gsv if member_gsv > 0 else 0.0,
        }

        entry = {
            **all_metrics,
            "is_ttl": is_ttl == 1,
            "member_data": member_metrics,
        }
        key = "__ttl__" if is_ttl == 1 else name
        data[key] = entry

    return data

def get_category_overview(
    start_date: str,
    end_date: str,
    level: str = "class",
    metric_type: str = "GSV",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    品类概览(按Excel格式)
    返回全店和会员两张表,含新老客拆分及同比
    """

    conn = get_connection()

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    cutoff = (date(start_dt.year, start_dt.month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

    ly_start = (start_dt - timedelta(days=365)).strftime("%Y-%m-%d")
    ly_end = (end_dt - timedelta(days=365)).strftime("%Y-%m-%d")
    ly_start_dt_obj = datetime.strptime(ly_start, "%Y-%m-%d")
    ly_cutoff = (date(ly_start_dt_obj.year, ly_start_dt_obj.month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

    # ── 自定义对比期覆盖 ─────────────────────────────────────
    if compare_start_date and compare_end_date:
        ly_start = compare_start_date
        ly_end = compare_end_date
        comp_start_y, comp_start_m, comp_start_d = map(int, compare_start_date.split('-'))
        ly_cutoff = (date(comp_start_y, comp_start_m, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

    # 仅需 2 次 SQL 查询（原来是 4 次），每次含 GROUPING SETS 返回品类行 + TTL 行 + 会员指标
    cur = _compute_category_period(conn, start_date, end_date, cutoff, level, metric_type, channel, exclude_channels)
    comp = _compute_category_period(conn, ly_start, ly_end, ly_cutoff, level, metric_type, channel, exclude_channels)


    def _clamp_yoy(v):
        """L4.79 + L4.81 治本: 钳到 ±99.9999 raw ratio (frontend *100 = ±9999.99% display, Excel 0.00 格式上限), 避免 previous≈0 时爆炸.

        真业务触发 (user 7/10): 凉茶次抛 全店-GSV=¥105,861 YOY=-7296%, 未知 全店-AUS=¥111 YOY=+5503482857%.
        真因: previous 接近 0 (新分类/小基数), yoy_absolute = (curr-prev)/prev 爆炸.
        L4.81 治本契约: backend yoy_absolute 返回 raw ratio (no *100, e.g. 0.25 = +25% / 100), 钳到 ±99.9999 raw (frontend *100 = ±9999.99%).
        治本 (留尾): 当 previous < 阈值 (¥10 / 10 人) 时, YOY = None ("新分类" 占位).
        配套: Pydantic PercentageField (L4.81 ge=-1e10, le=1e10) 不会 422, 前端 YOYBadge |v|>1e6 raw (1e8%) 守卫 ("数据异常") 兜底.
        """
        if v is None:
            return None
        if v > 99.9999:
            return 99.9999
        if v < -99.9999:
            return -99.9999
        return v

    def _build_row(name: str, c: Dict[str, Any], p: Dict[str, Any]) -> Dict[str, Any]:
        # 老客/新客人数占比
        users = c.get("users", 0)
        old_users = c.get("old_users", 0)
        new_users = c.get("new_users", 0)
        old_users_ratio = round(old_users / users, 4) if users > 0 else 0.0
        new_users_ratio = round(new_users / users, 4) if users > 0 else 0.0

        comp_users = p.get("users", 0)
        comp_old_users = p.get("old_users", 0)
        comp_new_users = p.get("new_users", 0)
        comp_old_users_ratio = round(comp_old_users / comp_users, 4) if comp_users > 0 else 0.0
        comp_new_users_ratio = round(comp_new_users / comp_users, 4) if comp_users > 0 else 0.0

        return {
            "name": name,
            "display_name": mask_category_name(name),
            "gsv": round(c.get("gsv", 0), 2),
            "gsv_yoy": _clamp_yoy(yoy_absolute(c.get("gsv", 0), p.get("gsv", 0))),
            "users": c.get("users", 0),
            "users_yoy": _clamp_yoy(yoy_absolute(c.get("users", 0), p.get("users", 0))),
            "aus": round(c.get("aus", 0), 2),
            "aus_yoy": _clamp_yoy(yoy_absolute(c.get("aus", 0), p.get("aus", 0))),
            "old_gsv": round(c.get("old_gsv", 0), 2),
            "old_gsv_yoy": _clamp_yoy(yoy_absolute(c.get("old_gsv", 0), p.get("old_gsv", 0))),
            "old_ratio": round(c.get("old_ratio", 0), 4),
            "old_ratio_yoy": yoy_ratio(c.get("old_ratio", 0), p.get("old_ratio", 0)),
            "old_users": c.get("old_users", 0),
            "old_users_yoy": _clamp_yoy(yoy_absolute(c.get("old_users", 0), p.get("old_users", 0))),
            "old_aus": round(c.get("old_aus", 0), 2),
            "old_aus_yoy": _clamp_yoy(yoy_absolute(c.get("old_aus", 0), p.get("old_aus", 0))),
            "new_gsv": round(c.get("new_gsv", 0), 2),
            "new_gsv_yoy": _clamp_yoy(yoy_absolute(c.get("new_gsv", 0), p.get("new_gsv", 0))),
            "new_ratio": round(c.get("new_ratio", 0), 4),
            "new_ratio_yoy": yoy_ratio(c.get("new_ratio", 0), p.get("new_ratio", 0)),
            "new_users": c.get("new_users", 0),
            "new_users_yoy": _clamp_yoy(yoy_absolute(c.get("new_users", 0), p.get("new_users", 0))),
            "new_aus": round(c.get("new_aus", 0), 2),
            "new_aus_yoy": _clamp_yoy(yoy_absolute(c.get("new_aus", 0), p.get("new_aus", 0))),
            "old_users_ratio": old_users_ratio,
            "old_users_ratio_yoy": yoy_ratio(old_users_ratio, comp_old_users_ratio),
            "new_users_ratio": new_users_ratio,
            "new_users_ratio_yoy": yoy_ratio(new_users_ratio, comp_new_users_ratio),
            "member_ratio": round(c.get("member_ratio", 0), 4),
            "member_ratio_yoy": yoy_ratio(c.get("member_ratio", 0), p.get("member_ratio", 0)),
            # L4.79 治本: 品类看板-单品概览 Excel 导出 5 个会员字段 (跟 frontend allCompactXlsxColumns 1:1 stable)
            "member_gsv": round(c.get("member_gsv", 0), 2),
            "member_gsv_yoy": _clamp_yoy(yoy_absolute(c.get("member_gsv", 0), p.get("member_gsv", 0))),
            "member_users": c.get("member_data", {}).get("users", 0),
            "member_users_yoy": _clamp_yoy(yoy_absolute(
                c.get("member_data", {}).get("users", 0),
                p.get("member_data", {}).get("users", 0),
            )),
            "member_aus": round(c.get("member_data", {}).get("aus", 0), 2),
            "member_aus_yoy": _clamp_yoy(yoy_absolute(
                c.get("member_data", {}).get("aus", 0),
                p.get("member_data", {}).get("aus", 0),
            )),
            "member_penetration": round(
                c.get("member_data", {}).get("users", 0) / c.get("users", 0), 4
            ) if c.get("users", 0) > 0 else 0.0,
        }

    # 分离 TTL 行和品类明细行；TTL 行由 SQL GROUPING SETS 直接返回
    cur_ttl = cur.pop("__ttl__", {})
    comp_ttl = comp.pop("__ttl__", {})
    cur_mem_ttl_data = cur_ttl.get("member_data", {})
    comp_mem_ttl_data = comp_ttl.get("member_data", {})

    all_names = sorted(set(cur.keys()) | set(comp.keys()), key=lambda x: (cur.get(x, {}).get("gsv", 0) + comp.get(x, {}).get("gsv", 0)), reverse=True)

    all_rows = []
    member_rows = []
    for name in all_names:
        c = cur.get(name, {})
        p = comp.get(name, {})
        all_rows.append(_build_row(name, c, p))
        # P0-001: member_rows 使用会员专属口径（member_data 子字典）
        c_m = c.get("member_data", {})
        p_m = p.get("member_data", {})
        m_row = _build_row(name, c_m, p_m)
        # FIX: member_ratio 分母应为全店总GSV，而非会员专属口径的GSV
        total_gsv_all = c.get("gsv", 0)
        member_gsv_all = c.get("member_gsv", 0)
        comp_total_gsv_all = p.get("gsv", 0)
        comp_member_gsv_all = p.get("member_gsv", 0)
        if total_gsv_all > 0:
            m_row["member_ratio"] = round(member_gsv_all / total_gsv_all, 4)
        if comp_total_gsv_all > 0:
            m_row["member_ratio_yoy"] = yoy_ratio(
                member_gsv_all / total_gsv_all if total_gsv_all > 0 else 0,
                comp_member_gsv_all / comp_total_gsv_all
            )
        member_rows.append(m_row)

    # ─── TTL 行：直接从 SQL GROUPING SETS 结果中提取（不再 Python 求和） ────
    all_ttl = _build_row("TTL", cur_ttl, comp_ttl)

    # P0-002: 会员 TTL（使用 SQL 返回的会员专属指标）
    member_ttl = _build_row("TTL", cur_mem_ttl_data, comp_mem_ttl_data)
    # 覆盖 member_ratio: 全店会员GSV / 全店总GSV
    total_gsv = cur_ttl.get("gsv", 0)
    total_member_gsv = cur_ttl.get("member_gsv", 0)
    comp_total_gsv = comp_ttl.get("gsv", 0)
    comp_total_member_gsv = comp_ttl.get("member_gsv", 0)
    if total_gsv > 0:
        member_ttl["member_ratio"] = round(total_member_gsv / total_gsv, 4)
    if comp_total_gsv > 0:
        member_ttl["member_ratio_yoy"] = yoy_ratio(
            total_member_gsv / total_gsv if total_gsv > 0 else 0,
            comp_total_member_gsv / comp_total_gsv
        )

    level_col = SPU_LEVELS.get(level, "spu_product_class")
    apply_catalog_display_names(conn, all_rows, level_col)
    apply_catalog_display_names(conn, member_rows, level_col)
    apply_catalog_display_names(conn, [all_ttl, member_ttl], level_col)

    return {
        "date_start": start_date,
        "date_end": end_date,
        "level": level,
        "channel": channel,
        "metric_type": metric_type,
        "all_rows": all_rows,
        "member_rows": member_rows,
        "all_ttl": all_ttl,
        "member_ttl": member_ttl,
    }

def _build_value_score(
    high_val_ratio: float, wool_ratio: float, member_ratio: float, aus: float,
    rank_high_val: int, rank_wool: int, rank_member: int, rank_aus: int,
    total_count: int
) -> tuple[float, str]:
    """
    计算价值评分和等级(辅助函数)
    评分 = 高价值占比排名*0.4 + (100-羊毛党占比排名)*0.3 + 会员占比排名*0.2 + AUS排名*0.1
    """
    # 百分位排名转0-100分数(排名1=n/2*100/n,排名越靠前分数越高)
    score_high_val = (total_count - rank_high_val + 1) / total_count * 100
    score_wool = (total_count - rank_wool + 1) / total_count * 100  # 羊毛党占比低=高分
    score_member = (total_count - rank_member + 1) / total_count * 100
    score_aus = (total_count - rank_aus + 1) / total_count * 100

    total_score = (
        score_high_val * 0.4 +
        score_wool * 0.3 +
        score_member * 0.2 +
        score_aus * 0.1
    )

    if total_score >= 80:
        grade = "A"
    elif total_score >= 65:
        grade = "B"
    elif total_score >= 50:
        grade = "C"
    elif total_score >= 35:
        grade = "D"
    else:
        grade = "E"

    return round(total_score, 1), grade

_EMPTY_WOOL = {
    "high_risk_count": 0,
    "mean_score": 0.0,
    "never_converted_count": 0,
    "converted_then_sample_count": 0,
    "sample_only_window_count": 0,
    "scored_users": 0,
    "high_risk_ratio": 0.0,
}


def _compute_wool_party_breakdown(
    conn: "duckdb.DuckDBPyConnection",
    start_date: str, end_date: str,
    level: str, channel: Optional[str], exclude_channels: Optional[List[str]]
) -> Dict[str, Dict[str, Any]]:
    """按品类聚合用户级羊毛风险分。

    证据（用户级，不是窗口 100% 小样布尔）:
    - 窗口小样订单占比
    - 截止窗口末日是否从未买过正装
    - 曾转正、窗口内仍 100% 小样

    分数 0-1；high_risk = score >= 0.70。不应用 exclude_channels。
    """
    del exclude_channels  # 羊毛证据必须看见低价渠道
    level_col = SPU_LEVELS.get(level, "spu_product_class")
    excluded_cat_sql = _excluded_cat_filter(level_col)
    SAMPLE_CHANNELS = ('U先派样', '百补派样', '赠品&0.01渠道', '其他')

    where_sql, where_params = _build_wool_party_filter(
        start_date, end_date, channel,
    )
    life_sql, life_params = _build_wool_lifetime_filter(end_date)
    params = list(where_params) + list(EXCLUDED_PRODUCT_CATEGORIES) + list(life_params)

    sql = f"""
    WITH window_orders AS (
        SELECT
            {_cat_expr(level_col)} AS category_name,
            o.user_id,
            o.channel
        FROM orders o
        WHERE {where_sql}
          {excluded_cat_sql}
    ),
    user_window_summary AS (
        SELECT
            category_name,
            user_id,
            COUNT(*) AS total_orders,
            COUNT(CASE WHEN channel IN {SAMPLE_CHANNELS} THEN 1 END) AS sample_orders
        FROM window_orders
        GROUP BY category_name, user_id
    ),
    window_users AS (
        SELECT DISTINCT user_id FROM window_orders
    ),
    lifetime_formal AS (
        SELECT
            o.user_id,
            COUNT(CASE WHEN o.channel NOT IN {SAMPLE_CHANNELS} THEN 1 END) AS formal_orders
        FROM orders o
        INNER JOIN window_users w ON o.user_id = w.user_id
        WHERE {life_sql}
        GROUP BY o.user_id
    ),
    scored AS (
        SELECT
            ws.category_name,
            ws.user_id,
            CASE WHEN ws.total_orders > 0
                 THEN ws.sample_orders * 1.0 / ws.total_orders ELSE 0 END AS window_sample_ratio,
            CASE WHEN COALESCE(lf.formal_orders, 0) = 0 THEN 1 ELSE 0 END AS never_converted,
            CASE WHEN COALESCE(lf.formal_orders, 0) > 0
                  AND ws.sample_orders = ws.total_orders AND ws.total_orders > 0
                 THEN 1 ELSE 0 END AS converted_then_sample,
            CASE WHEN ws.sample_orders = ws.total_orders AND ws.total_orders > 0
                 THEN 1 ELSE 0 END AS sample_only_window
        FROM user_window_summary ws
        LEFT JOIN lifetime_formal lf ON ws.user_id = lf.user_id
        WHERE ws.total_orders > 0
    ),
    with_score AS (
        SELECT
            category_name,
            user_id,
            never_converted,
            converted_then_sample,
            sample_only_window,
            LEAST(1.0,
                0.55 * window_sample_ratio
                + 0.25 * never_converted
                + 0.20 * converted_then_sample
            ) AS score
        FROM scored
    )
    SELECT
        category_name,
        COUNT(DISTINCT CASE WHEN score >= 0.70 THEN user_id END) AS high_risk_count,
        AVG(score) AS mean_score,
        COUNT(DISTINCT CASE WHEN never_converted = 1 THEN user_id END) AS never_converted_count,
        COUNT(DISTINCT CASE WHEN converted_then_sample = 1 THEN user_id END) AS converted_then_sample_count,
        COUNT(DISTINCT CASE WHEN sample_only_window = 1 THEN user_id END) AS sample_only_window_count,
        COUNT(DISTINCT user_id) AS scored_users
    FROM with_score
    GROUP BY category_name
    """
    assert sql.count('?') == len(params), (
        f"_compute_wool_party_breakdown params mismatch: SQL has {sql.count('?')} ? placeholders "
        f"but params list has {len(params)} items. Check params order vs SQL `?` positions."
    )
    result = conn.execute(sql, params).fetchall()
    out: Dict[str, Dict[str, Any]] = {}
    for row in result:
        scored_users = int(row[6] or 0)
        high_risk = int(row[1] or 0)
        out[row[0]] = {
            "high_risk_count": high_risk,
            "mean_score": round(float(row[2] or 0), 4),
            "never_converted_count": int(row[3] or 0),
            "converted_then_sample_count": int(row[4] or 0),
            "sample_only_window_count": int(row[5] or 0),
            "scored_users": scored_users,
            "high_risk_ratio": round(high_risk / scored_users, 4) if scored_users > 0 else 0.0,
        }
    return out

def _compute_value_tier_base(
    conn: "duckdb.DuckDBPyConnection",
    start_date: str, end_date: str, cutoff: str,
    level: str, channel: Optional[str], exclude_channels: Optional[List[str]]
) -> tuple:
    """计算价值分层基础数据（高价值人数 + 总用户 + 总GMV + 会员GMV）"""
    level_col = SPU_LEVELS.get(level, "spu_product_class")
    excluded_cat_sql = _excluded_cat_filter(level_col)

    where_sql, where_params = _build_value_tier_filter(
        start_date, end_date, channel, exclude_channels,
    )
    rfm_cte, rfm_params = rfm_asof_cte(end_date, "period_orders")
    params = list(where_params) + list(EXCLUDED_PRODUCT_CATEGORIES) + list(rfm_params)

    sql = f"""
    WITH period_orders AS (
        SELECT {_cat_expr(level_col)} AS category_name,
               o.user_id, o.actual_amount, o.is_member
        FROM orders o
        WHERE {where_sql}
          {excluded_cat_sql}
    ),
    {rfm_cte}
    SELECT p.category_name,
           COUNT(DISTINCT p.user_id) AS total_users,
           SUM(p.actual_amount) AS total_gsv,
           COUNT(DISTINCT CASE WHEN COALESCE(r.segment_id, 9) IN (1, 2) THEN p.user_id END) AS high_value_users,
           SUM(CASE WHEN p.is_member THEN p.actual_amount ELSE 0 END) AS member_gsv
    FROM period_orders p
    LEFT JOIN rfm_asof r ON p.user_id = r.user_id
    GROUP BY p.category_name
    """
    # Sprint 90 L4.7 ground-truth-lint: 防 params 顺序错位回归 (Sprint 60+60.1.1 实战 fix 模式).
    assert sql.count('?') == len(params), (
        f"_compute_value_tier_base params mismatch: SQL has {sql.count('?')} ? placeholders "
        f"but params list has {len(params)} items. Check params order vs SQL `?` positions."
    )
    result = conn.execute(sql, params).fetchall()

    # 计算羊毛党细分
    wool_breakdown = _compute_wool_party_breakdown(
        conn, start_date, end_date, level, channel, exclude_channels)

    return result, wool_breakdown

def get_category_value_tier(
    start_date: str,
    end_date: str,
    level: str = "class",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """价值分层 - 各品类羊毛党指数 + 高价值占比 + 价值评分

    多时间窗口羊毛党统计:
    - default: 使用传入的 start_date~end_date 作为默认窗口
    - 30d: end_date 往前推 30 天
    - 90d: end_date 往前推 90 天
    - all: 全部历史(2000-01-01 ~ end_date)
    """

    conn = get_connection()
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    cutoff = (date(start_dt.year, start_dt.month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

    # ---- 默认窗口(用户选择的时间范围) ----
    result, wool_breakdown = _compute_value_tier_base(
        conn, start_date, end_date, cutoff, level, channel, exclude_channels)

    # ---- 多窗口羊毛党计算 ----
    # 30天窗口
    start_30d = (end_dt - timedelta(days=30)).strftime("%Y-%m-%d")
    wool_30d = _compute_wool_party_breakdown(
        conn, start_30d, end_date, level, channel, exclude_channels)
    # 90天窗口
    start_90d = (end_dt - timedelta(days=90)).strftime("%Y-%m-%d")
    wool_90d = _compute_wool_party_breakdown(
        conn, start_90d, end_date, level, channel, exclude_channels)
    # 全部历史
    wool_all = _compute_wool_party_breakdown(
        conn, "2000-01-01", end_date, level, channel, exclude_channels)

    # 构建品类数据
    MIN_USERS_FOR_SCORING = 100  # 用户基数门槛: 低于此数不参与评分排名
    cat_data = []
    for row in result:
        total_users = int(row[1] or 0)
        if total_users == 0:
            continue
        total_gsv = float(row[2] or 0)
        high_value_users = int(row[3] or 0)
        member_gsv = float(row[4] or 0)
        wool = {**_EMPTY_WOOL, **wool_breakdown.get(row[0], {})}
        high_risk_ratio = min(
            round(wool["high_risk_count"] / total_users, 4) if total_users > 0 else 0.0,
            1.0,
        )
        wool["high_risk_ratio"] = high_risk_ratio
        cat_data.append({
            "category_name": row[0],
            "total_users": total_users,
            "total_gsv": total_gsv,
            "high_value_users": high_value_users,
            "high_value_ratio": high_value_users / total_users,
            "wool_party": wool,
            "member_ratio": member_gsv / total_gsv if total_gsv > 0 else 0,
            "avg_aus": total_gsv / total_users,
            "is_sample_insufficient": total_users < MIN_USERS_FOR_SCORING,
        })

    # 分离符合门槛的品类和样本不足的品类
    qualifying = [c for c in cat_data if not c["is_sample_insufficient"]]
    insufficient = [c for c in cat_data if c["is_sample_insufficient"]]

    # 计算排名(仅对符合门槛的品类)
    total_count = len(qualifying)
    if total_count > 0:
        rank_map = {c["category_name"]: {"high_val": i+1, "wool": i+1, "member": i+1, "aus": i+1}
                    for i, c in enumerate(sorted(qualifying, key=lambda x: x["high_value_ratio"], reverse=True))}
        for i, c in enumerate(sorted(qualifying, key=lambda x: x["wool_party"]["high_risk_ratio"], reverse=True)):
            rank_map[c["category_name"]]["wool"] = i + 1
        for i, c in enumerate(sorted(qualifying, key=lambda x: x["member_ratio"], reverse=True)):
            rank_map[c["category_name"]]["member"] = i + 1
        for i, c in enumerate(sorted(qualifying, key=lambda x: x["avg_aus"], reverse=True)):
            rank_map[c["category_name"]]["aus"] = i + 1

        for c in qualifying:
            ranks = rank_map[c["category_name"]]
            score, grade = _build_value_score(
                c["high_value_ratio"],
                c["wool_party"]["high_risk_ratio"],
                c["member_ratio"], c["avg_aus"],
                ranks["high_val"], ranks["wool"], ranks["member"], ranks["aus"], total_count)
            c["value_score"] = score
            c["value_grade"] = grade

    # 样本不足的品类: 不参与排名, 标记为"样本不足"
    for c in insufficient:
        c["value_score"] = 0
        c["value_grade"] = "样本不足"

    # 合并后按用户数降序排列(符合门槛的在前, 样本不足的在后)
    qualifying.sort(key=lambda x: x["total_users"], reverse=True)
    insufficient.sort(key=lambda x: x["total_users"], reverse=True)
    cat_data = qualifying + insufficient
    apply_catalog_display_names(
        conn, cat_data, SPU_LEVELS.get(level, "spu_product_class"), name_key="category_name",
    )

    dual_axis = {
        "categories": [c.get("display_name") or c["category_name"] for c in cat_data],
        # Sprint 60.1.1 fix: wool_party.total_count 是"100% 小样用户" (不应用 exclude_channels),
        # 但 total_users 应用了 exclude_channels, 羊毛党用户 100% 在低价 → 排除低价后
        # total_users 缩水, ratio 数学上可能 > 1. 强截断到 1.0 保持 contract 0-1 范围
        # (跟 Sprint 27 YOYBadge |v|>1e6 异常值守卫模式一致).
        # 注: cat_data 在 line 664 已经过滤 total_users == 0, 这里不需要重复.
        "wool_party_ratios": [c["wool_party"]["high_risk_ratio"] for c in cat_data],
        "high_value_ratios": [round(c["high_value_ratio"], 4) for c in cat_data],
    }
    table = [{"category_name": c["category_name"],
              "display_name": c.get("display_name") or c["category_name"],
              "total_users": c["total_users"],
              "high_value_users": c["high_value_users"],
              "high_value_ratio": round(c["high_value_ratio"], 4),
              "wool_party": c["wool_party"],
              "member_ratio": round(c["member_ratio"], 4),
              "avg_aus": round(c["avg_aus"], 2),
              "value_score": c["value_score"], "value_grade": c["value_grade"]}
             for c in cat_data]

    # ---- 多窗口羊毛党数据组装 ----
    def _build_window_table(wool_map: Dict[str, Dict[str, Any]], window_label: str) -> List[Dict[str, Any]]:
        rows = []
        for c in cat_data:
            cat = c["category_name"]
            w = {**_EMPTY_WOOL, **wool_map.get(cat, {})}
            tu = c["total_users"]
            packed = dict(w)
            packed["high_risk_ratio"] = min(
                round(packed["high_risk_count"] / tu, 4) if tu > 0 else 0.0,
                1.0,
            )
            rows.append({
                "category_name": cat,
                "display_name": c.get("display_name") or cat,
                "total_users": tu,
                "high_value_users": c["high_value_users"],
                "high_value_ratio": round(c["high_value_ratio"], 4),
                "wool_party": packed,
                "member_ratio": round(c["member_ratio"], 4),
                "avg_aus": round(c["avg_aus"], 2),
                "value_score": c["value_score"],
                "value_grade": c["value_grade"],
            })
        return rows

    wool_party_by_window = {
        "default": table,
        "30d": _build_window_table(wool_30d, "30d"),
        "90d": _build_window_table(wool_90d, "90d"),
        "all": _build_window_table(wool_all, "all"),
    }

    suggestions = []
    high_wool = [c for c in cat_data if c["wool_party"]["high_risk_ratio"] > 0.4]
    if high_wool:
        suggestions.append(
            f"高风险羊毛分占比 > 40%: {high_wool[0].get('display_name') or high_wool[0]['category_name']} 建议重新评估该品类渠道ROI"
        )

    return {
        "dual_axis_line": dual_axis,
        "table": table,
        "operation_suggestions": suggestions,
        "data_quality_note": (
            f"基于 {sum(c['total_users'] for c in cat_data)} 名用户 / {start_date}~{end_date} 计算。"
            f"排名仅统计用户数 ≥ {MIN_USERS_FOR_SCORING} 的品类，共 {len(qualifying)} 个。"
            f"样本不足(<{MIN_USERS_FOR_SCORING}人)的 {len(insufficient)} 个品类不参与评分排名。"
            f"羊毛风险=窗口小样占比×0.55+从未转正×0.25+转正后窗口仍全小样×0.20；"
            f"正装证据截止窗口末日、不套窗口时间。不受'剔除低价'筛选影响。"
        ),
        "wool_party_by_window": wool_party_by_window,
    }
