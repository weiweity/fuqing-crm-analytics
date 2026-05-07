"""
老客健康分析仪表盘 - 模块1: 现状概览（运营日报）

口径统一:
- 有效订单: is_goujinjin=FALSE AND order_status!='交易关闭' AND is_refund=FALSE
- 复购定义: 周期内2+有效订单
- 老客判定: first_pay_date <= cutoff (cutoff = start_date - 1天)
- 渠道排除: 通过 FilterBuilder.with_exclude_channels() 统一处理

健康评分 V1 算法 (Phase 1):
- 各指标先按固定阈值归一化到 0-1，再均匀加权
- 后续根据实际数据分布优化阈值
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import json
import hashlib
import logging
import time
from pathlib import Path

from backend.config import DATA_DIR
from backend.db.connection import get_connection
from backend.semantic.filters import FilterBuilder, OrderFilters, MetricType
from backend.semantic.calculations import yoy_absolute, yoy_ratio, safe_ratio
from . import config as health_config

logger = logging.getLogger(__name__)

# 缓存目录（从统一配置派生，避免硬编码 __file__ 层级）
CACHE_DIR = DATA_DIR / "cache" / "health_overview"

# DuckDB 文件路径（用于数据版本感知）
DB_FILE = DATA_DIR / "processed" / "fuqing_crm.duckdb"


def _data_version() -> str:
    """获取数据版本标识（DuckDB文件 mtime 的日期字符串）。

    ETL 刷新数据库后，文件 mtime 变化 → 数据版本变化 → 旧缓存全部失效。
    """
    if DB_FILE.exists():
        import os
        mtime = os.path.getmtime(DB_FILE)
        return datetime.fromtimestamp(mtime).strftime("%Y%m%d%H%M%S")
    return "unknown"


def _cache_key(analysis_date: str, period_days: int,
               exclude_channels: Optional[List[str]],
               channel: Optional[str]) -> str:
    """生成缓存键（文件名）

    缓存键包含数据版本（DuckDB mtime），ETL刷新后自动失效所有历史缓存。
    """
    dv = _data_version()
    parts = [dv, analysis_date, str(period_days)]
    if channel:
        parts.append(f"ch_{channel}")
    if exclude_channels:
        # 排序后哈希，保证相同集合产生相同键
        ch_str = ",".join(sorted(exclude_channels))
        ch_hash = hashlib.md5(ch_str.encode()).hexdigest()[:8]
        parts.append(f"ex_{ch_hash}")
    return "_".join(parts) + ".json"


_config_hash_cache: tuple[str, float] | None = None  # (hash, timestamp)

def _config_hash() -> str:
    """计算当前配置的哈希（用于缓存失效校验，5s TTL 缓存）"""
    global _config_hash_cache
    now = time.monotonic()
    if _config_hash_cache is not None:
        cached_hash, cached_at = _config_hash_cache
        if now - cached_at < 5.0:
            return cached_hash
    cfg = health_config.get_health_config()
    key_parts = {
        "weights": cfg.get("weights"),
        "targets": cfg.get("targets"),
        "bounds": cfg.get("health_level_bounds"),
    }
    h = hashlib.md5(json.dumps(key_parts, sort_keys=True, default=str).encode()).hexdigest()[:8]
    _config_hash_cache = (h, now)
    return h


def _read_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    """读取缓存文件

    如果缓存缺少必需字段（如 ly_*）或配置已变更，视为缓存未命中，重新计算。
    """
    cache_file = CACHE_DIR / cache_key
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 字段兼容性校验：缺少 ly_* 字段的旧缓存视为无效
            required_fields = ["ly_all_store_repurchase_rate", "ly_same_product_repurchase_rate"]
            if not all(f in data for f in required_fields):
                cache_file.unlink()
                return None
            # 配置变更校验：配置哈希不一致视为无效（确保去年同期评分随配置刷新）
            if data.get("_config_hash") != _config_hash():
                cache_file.unlink()
                return None
            return data
        except (json.JSONDecodeError, IOError):
            return None
    return None


def _write_cache(cache_key: str, data: Dict[str, Any]) -> None:
    """写入缓存文件（附带配置哈希）"""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = CACHE_DIR / cache_key
        cache_data = {**data, "_config_hash": _config_hash()}
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, default=str)
    except IOError as e:
        logger.warning(f"缓存写入失败，跳过: {e}")


def _is_historical_period(analysis_date: str) -> bool:
    """判断是否为已结束的历史周期（analysis_date < 今天）"""
    today = datetime.now().date()
    end_dt = datetime.strptime(analysis_date, "%Y-%m-%d").date()
    return end_dt < today


def _build_filter(
    exclude_channels: Optional[List[str]],
    start_date: str,
    end_date: str,
    channel: Optional[str] = None,
):
    """构建统一 WHERE 过滤条件

    Args:
        exclude_channels: 排除的渠道列表（低价剔除等场景）
        start_date: 开始日期
        end_date: 结束日期
        channel: 指定渠道（include-only），优先级高于 exclude_channels
    """
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_time_range(start_date, end_date)
    if channel and channel != "全店":
        fb.with_channels([channel])
    elif exclude_channels:
        fb.with_exclude_channels(exclude_channels)
    return fb.build()


def _compute_repurchase_rate(conn, where_sql: str, params: list) -> tuple[float, int, int]:
    """计算全店复购率: 2+订单人数 / 总购买人数

    Returns:
        (复购率, 复购人数, 总购买人数)
    """
    row = conn.execute(f"""
        WITH user_orders AS (
            SELECT user_id, COUNT(DISTINCT order_id) as order_count
            FROM orders
            WHERE {where_sql}
            GROUP BY user_id
        )
        SELECT
            COUNT(DISTINCT CASE WHEN order_count >= 2 THEN user_id END) as repurchase_users,
            COUNT(DISTINCT user_id) as total_users
        FROM user_orders
    """, params).fetchone()

    repurchase_users = int(row[0]) if row[0] else 0
    total_users = int(row[1]) if row[1] else 0
    rate = safe_ratio(repurchase_users, total_users, 0.0)
    return rate, repurchase_users, total_users


def _compute_product_repurchase_rate(conn, where_sql: str, params: list) -> float:
    """计算本品复购率（所有品类平均）

    逻辑：每个品类先算自己的复购率（该品类复购人数/该品类购买人数），
          然后对所有品类的复购率求平均。
    避免错误：分子不能用"各品类复购人次之和"除以"全店人数"。
    """
    row = conn.execute(f"""
        WITH product_users AS (
            SELECT spu_product_class, user_id, COUNT(DISTINCT order_id) as order_count
            FROM orders
            WHERE {where_sql}
              AND spu_product_class IS NOT NULL
            GROUP BY spu_product_class, user_id
        ),
        product_rates AS (
            SELECT spu_product_class,
                COUNT(CASE WHEN order_count >= 2 THEN 1 END) * 1.0 / COUNT(*) as repurchase_rate
            FROM product_users
            GROUP BY spu_product_class
        )
        SELECT AVG(repurchase_rate) as avg_product_repurchase_rate
        FROM product_rates
    """, params).fetchone()

    return float(row[0]) if row[0] else 0.0


def _compute_old_customer_metrics(conn, where_sql: str, params: list,
                                   start_date: str) -> Dict[str, float]:
    """计算老客相关指标: GSV、占比、AUS、会员指标"""
    cutoff = (datetime.strptime(start_date, "%Y-%m-%d").date() - timedelta(days=1)).strftime("%Y-%m-%d")

    row = conn.execute(f"""
        WITH period_orders AS (
            SELECT user_id, actual_amount, is_member
            FROM orders
            WHERE {where_sql}
        ),
        enriched AS (
            SELECT
                p.user_id,
                p.actual_amount,
                p.is_member,
                CASE WHEN u.first_pay_date <= ?::DATE THEN 1 ELSE 0 END as is_old
            FROM period_orders p
            JOIN (SELECT DISTINCT user_id, first_pay_date FROM user_first_purchase) u
                ON p.user_id = u.user_id
        )
        SELECT
            SUM(CASE WHEN is_old = 1 THEN actual_amount ELSE 0 END) as old_gsv,
            SUM(actual_amount) as total_gsv,
            COUNT(DISTINCT CASE WHEN is_old = 1 THEN user_id END) as old_users,
            COUNT(DISTINCT user_id) as total_users,
            -- 会员口径
            SUM(CASE WHEN is_old = 1 AND is_member = TRUE THEN actual_amount ELSE 0 END) as member_old_gsv,
            SUM(CASE WHEN is_member = TRUE THEN actual_amount ELSE 0 END) as member_total_gsv,
            COUNT(DISTINCT CASE WHEN is_old = 1 AND is_member = TRUE THEN user_id END) as member_old_users,
            COUNT(DISTINCT CASE WHEN is_member = TRUE THEN user_id END) as member_total_users
        FROM enriched
    """, params + [cutoff]).fetchone()

    old_gsv = float(row[0]) if row[0] else 0.0
    total_gsv = float(row[1]) if row[1] else 0.0
    old_users = int(row[2]) if row[2] else 0
    total_users = int(row[3]) if row[3] else 0
    member_old_gsv = float(row[4]) if row[4] else 0.0
    member_total_gsv = float(row[5]) if row[5] else 0.0
    member_old_users = int(row[6]) if row[6] else 0
    member_total_users = int(row[7]) if row[7] else 0

    return {
        # 老客绝对值
        "old_gsv": old_gsv,
        "old_users": old_users,
        "total_gsv": total_gsv,
        # 老客GSV占比
        "old_customer_gsv_ratio": safe_ratio(old_gsv, total_gsv, 0.0),
        # 老客AUS
        "old_customer_aus": safe_ratio(old_gsv, old_users, 0.0),
        # 会员老客绝对值
        "member_old_gsv": member_old_gsv,
        "member_old_users": member_old_users,
        # 会员老客GSV占比（老客会员GSV / 会员总GSV）
        "member_old_customer_gsv_ratio": safe_ratio(member_old_gsv, member_total_gsv, 0.0),
        # 会员老客AUS
        "member_old_customer_aus": safe_ratio(member_old_gsv, member_old_users, 0.0),
    }


def _compute_period_repurchase_users(conn, where_sql: str, params: list) -> int:
    """计算周期内复购人数（2+有效订单）"""
    row = conn.execute(f"""
        SELECT COUNT(DISTINCT user_id)
        FROM (
            SELECT user_id, COUNT(DISTINCT order_id) as order_count
            FROM orders
            WHERE {where_sql}
            GROUP BY user_id
            HAVING COUNT(DISTINCT order_id) >= 2
        )
    """, params).fetchone()
    return int(row[0]) if row[0] else 0


def _compute_yoy_metrics(conn, analysis_date: str, period_days: int,
                         exclude_channels: Optional[List[str]],
                         channel: Optional[str] = None,
                         targets: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """计算去年同期指标（复用传入的连接，不自己创建）。targets 传入时用于评分基准。"""
    from backend.semantic.calculations import yoy_absolute, yoy_ratio

    end_dt = datetime.strptime(analysis_date, "%Y-%m-%d").date()
    start_dt = end_dt - timedelta(days=period_days - 1)

    # 去年同期（处理闰年2月29日：退化为2月28日）
    def _prev_year(d):
        try:
            return d.replace(year=d.year - 1)
        except ValueError:
            return d.replace(year=d.year - 1, day=28)
    prev_end_dt = _prev_year(end_dt)
    prev_start_dt = _prev_year(start_dt)

    prev_start = prev_start_dt.strftime("%Y-%m-%d")
    prev_end = prev_end_dt.strftime("%Y-%m-%d")

    where_sql, params = _build_filter(exclude_channels, prev_start, prev_end, channel)

    prev_repurchase_rate, prev_repurchase_users, _ = _compute_repurchase_rate(conn, where_sql, params)
    prev_product_rate = _compute_product_repurchase_rate(conn, where_sql, params)
    prev_old_metrics = _compute_old_customer_metrics(conn, where_sql, params, prev_start)

    # 去年同期健康评分（使用同样的动态目标基准）
    prev_health_score, _ = _compute_health_score(
        prev_repurchase_rate,
        prev_product_rate,
        prev_old_metrics["old_customer_gsv_ratio"],
        prev_old_metrics["old_customer_aus"],
        prev_repurchase_users,
        period_days,
        targets=targets,
    )

    return {
        "yoy_all_store_repurchase_rate": prev_repurchase_rate,
        "yoy_same_product_repurchase_rate": prev_product_rate,
        "yoy_old_customer_gsv_ratio": prev_old_metrics["old_customer_gsv_ratio"],
        "yoy_old_customer_aus": prev_old_metrics["old_customer_aus"],
        "yoy_old_gsv": prev_old_metrics["old_gsv"],
        "yoy_old_users": prev_old_metrics["old_users"],
        "yoy_member_old_gsv": prev_old_metrics["member_old_gsv"],
        "yoy_member_old_users": prev_old_metrics["member_old_users"],
        "yoy_member_old_customer_gsv_ratio": prev_old_metrics["member_old_customer_gsv_ratio"],
        "yoy_member_old_customer_aus": prev_old_metrics["member_old_customer_aus"],
        "yoy_period_repurchase_users": prev_repurchase_users,
        "yoy_health_score": prev_health_score,
    }


def _compute_mom_metrics(conn, analysis_date: str, period_days: int,
                         exclude_channels: Optional[List[str]],
                         channel: Optional[str] = None) -> Dict[str, Any]:
    """计算环比指标（上一个等长周期）"""
    end_dt = datetime.strptime(analysis_date, "%Y-%m-%d").date()
    start_dt = end_dt - timedelta(days=period_days - 1)

    # 环比周期 = 往前推 period_days 天
    mom_end_dt = start_dt - timedelta(days=1)
    mom_start_dt = mom_end_dt - timedelta(days=period_days - 1)

    mom_start = mom_start_dt.strftime("%Y-%m-%d")
    mom_end = mom_end_dt.strftime("%Y-%m-%d")

    where_sql, params = _build_filter(exclude_channels, mom_start, mom_end, channel)

    mom_repurchase_rate, mom_repurchase_users, _ = _compute_repurchase_rate(conn, where_sql, params)
    mom_product_rate = _compute_product_repurchase_rate(conn, where_sql, params)
    mom_old_metrics = _compute_old_customer_metrics(conn, where_sql, params, mom_start)

    return {
        "mom_all_store_repurchase_rate": mom_repurchase_rate,
        "mom_same_product_repurchase_rate": mom_product_rate,
        "mom_old_customer_gsv_ratio": mom_old_metrics["old_customer_gsv_ratio"],
        "mom_old_customer_aus": mom_old_metrics["old_customer_aus"],
        "mom_old_gsv": mom_old_metrics["old_gsv"],
        "mom_old_users": mom_old_metrics["old_users"],
        "mom_member_old_gsv": mom_old_metrics["member_old_gsv"],
        "mom_member_old_users": mom_old_metrics["member_old_users"],
        "mom_member_old_customer_gsv_ratio": mom_old_metrics["member_old_customer_gsv_ratio"],
        "mom_member_old_customer_aus": mom_old_metrics["member_old_customer_aus"],
        "mom_period_repurchase_users": mom_repurchase_users,
    }


def _soft_cap(value: float, target: float, max_bonus: float = 0.2) -> float:
    """
    软封顶归一化：线性到1.0，超过后按对数增长（边际递减），最多到 1+max_bonus。
    解决线性封顶"达标即满分、超标无区分"的问题。
    """
    import math
    ratio = value / target if target > 0 else 0.0
    if ratio <= 1.0:
        return ratio
    # 3倍target时达到 max_bonus（ln(3)/ln(4) ≈ 0.792；4倍时达1.0）
    return 1.0 + max_bonus * math.log(1.0 + ratio - 1.0) / math.log(4.0)


def _compute_health_score(
    all_store_repurchase_rate: float,
    same_product_repurchase_rate: float,
    old_customer_gsv_ratio: float,
    old_customer_aus: float,
    period_repurchase_users: int,
    period_days: int,
    targets: Optional[Dict[str, float]] = None,
) -> tuple[float, str]:
    """
    健康评分 V2 算法（非线性封顶）
    - 各指标按软封顶归一化（超标有额外加分但边际递减）
    - 复购人数使用"周均复购人数" = period_repurchase_users / period_days * 7
      保证不同周期长度下评分可比
    - targets: 动态目标值（去年同周期实际值），为 None 时回退到静态配置
    """
    cfg = health_config.get_health_config()
    if targets is None:
        targets = cfg["targets"]
    weights = cfg["weights"]
    bounds = cfg["health_level_bounds"]

    # 周均复购人数（使目标恒定为300/周，跨周期可比）
    weekly_repurchase = period_repurchase_users / period_days * 7 if period_days > 0 else 0

    # 归一化（软封顶）
    norm_repurchase = _soft_cap(all_store_repurchase_rate, targets["all_store_repurchase_rate"])
    norm_product = _soft_cap(same_product_repurchase_rate, targets["same_product_repurchase_rate"])
    norm_ratio = _soft_cap(old_customer_gsv_ratio, targets["old_customer_gsv_ratio"])
    norm_aus = _soft_cap(old_customer_aus, targets["old_customer_aus"])
    norm_recent = _soft_cap(weekly_repurchase, targets["recent_7d_repurchase_users"])

    score = (
        norm_repurchase * weights["all_store_repurchase_rate"] +
        norm_product * weights["same_product_repurchase_rate"] +
        norm_ratio * weights["old_customer_gsv_ratio"] +
        norm_aus * weights["old_customer_aus"] +
        norm_recent * weights["recent_7d_repurchase_users"]
    ) * 100

    score = round(score, 1)

    if score >= bounds["healthy"]:
        level = "healthy"
    elif score >= bounds["warning"]:
        level = "warning"
    else:
        level = "critical"

    return score, level


def _generate_alerts(
    all_store_repurchase_rate: float,
    same_product_repurchase_rate: float,
    old_customer_gsv_ratio: float,
    old_customer_aus: float,
    yoy_metrics: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """生成告警列表"""
    alerts = []
    thresholds = health_config.ALERT_THRESHOLDS

    # 1. 复购率暴跌（本品复购率 YOY 下跌超过阈值）
    yoy_product = yoy_metrics.get("yoy_same_product_repurchase_rate")
    drop_threshold = thresholds["same_product_repurchase_rate_drop"]
    if yoy_product is not None and (same_product_repurchase_rate - yoy_product) < -drop_threshold:
        alerts.append({
            "alert_type": "repurchase_rate_drop",
            "alert_name": "本品复购率暴跌",
            "severity": "high",
            "current_value": round(same_product_repurchase_rate, 4),
            "threshold_value": round(yoy_product - drop_threshold, 4),
            "comparison_basis": "yoy",
            "suggested_action": "检查SKU缺货/竞品促销",
            "target_tab": "repurchase",
        })

    # 2. 老客贡献占比过低
    if old_customer_gsv_ratio < thresholds["old_customer_gsv_ratio_low"]:
        alerts.append({
            "alert_type": "old_customer_ratio_low",
            "alert_name": "老客贡献占比过低",
            "severity": "medium",
            "current_value": round(old_customer_gsv_ratio, 4),
            "threshold_value": thresholds["old_customer_gsv_ratio_low"],
            "comparison_basis": "absolute",
            "suggested_action": "拉新过度，关注老客流失",
            "target_tab": "tiers",
        })

    # 3. 全店复购率过低
    if all_store_repurchase_rate < thresholds["all_store_repurchase_rate_low"]:
        alerts.append({
            "alert_type": "repurchase_rate_low",
            "alert_name": "全店复购率过低",
            "severity": "medium",
            "current_value": round(all_store_repurchase_rate, 4),
            "threshold_value": thresholds["all_store_repurchase_rate_low"],
            "comparison_basis": "absolute",
            "suggested_action": "检查触达策略，推送复购券",
            "target_tab": "repurchase",
        })

    # 4. 老客AUS过低
    if old_customer_aus < thresholds["old_customer_aus_low"]:
        alerts.append({
            "alert_type": "aus_low",
            "alert_name": "老客人均消费过低",
            "severity": "low",
            "current_value": round(old_customer_aus, 2),
            "threshold_value": thresholds["old_customer_aus_low"],
            "comparison_basis": "absolute",
            "suggested_action": "检查低价渠道占比，引导高客单品",
            "target_tab": "overview",
        })

    return alerts


def get_overview(
    analysis_date: str,
    period_days: int = 30,
    exclude_channels: Optional[List[str]] = None,
    channel: Optional[str] = None,
) -> Dict[str, Any]:
    """
    模块1：现状概览（运营日报）

    Args:
        analysis_date: 分析日期 YYYY-MM-DD
        period_days: 分析周期天数（默认30）
        exclude_channels: 排除渠道列表（低价剔除等场景）
        channel: 指定渠道（单渠道过滤，与 exclude_channels 互斥，优先于 exclude_channels）
    """
    from backend.semantic.calculations import yoy_absolute, yoy_ratio, mom_absolute, mom_ratio

    end_dt = datetime.strptime(analysis_date, "%Y-%m-%d").date()
    start_dt = end_dt - timedelta(days=period_days - 1)
    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = analysis_date

    # ── 缓存读取（历史周期）──
    cache_key = _cache_key(analysis_date, period_days, exclude_channels, channel)
    if _is_historical_period(analysis_date):
        cached = _read_cache(cache_key)
        if cached is not None:
            return cached

    conn = get_connection()
    try:
        # 1. 构建统一过滤条件（channel 优先于 exclude_channels）
        where_sql, params = _build_filter(exclude_channels, start_date, end_date, channel)

        # 2. 计算核心指标
        all_store_repurchase_rate, period_repurchase_users, _ = _compute_repurchase_rate(conn, where_sql, params)
        same_product_repurchase_rate = _compute_product_repurchase_rate(conn, where_sql, params)
        old_metrics = _compute_old_customer_metrics(conn, where_sql, params, start_date)

        # 3. 计算同比（去年同期值，同 channel 过滤）
        # 先算动态 targets，供评分和同比共用
        dynamic_targets = _compute_dynamic_targets(conn, analysis_date, period_days, exclude_channels, channel)
        yoy_prev = _compute_yoy_metrics(conn, analysis_date, period_days, exclude_channels, channel, targets=dynamic_targets)

        # 计算YOY变化率
        yoy_all_store = yoy_ratio(all_store_repurchase_rate, yoy_prev.get("yoy_all_store_repurchase_rate"))
        yoy_same_product = yoy_ratio(same_product_repurchase_rate, yoy_prev.get("yoy_same_product_repurchase_rate"))
        yoy_old_ratio = yoy_ratio(old_metrics["old_customer_gsv_ratio"], yoy_prev.get("yoy_old_customer_gsv_ratio"))
        yoy_old_aus = yoy_absolute(old_metrics["old_customer_aus"], yoy_prev.get("yoy_old_customer_aus"))
        yoy_period_repurchase = yoy_absolute(period_repurchase_users, yoy_prev.get("yoy_period_repurchase_users"))
        # 新增指标 YOY
        yoy_old_gsv = yoy_absolute(old_metrics["old_gsv"], yoy_prev.get("yoy_old_gsv"))
        yoy_old_users = yoy_absolute(old_metrics["old_users"], yoy_prev.get("yoy_old_users"))
        yoy_member_old_gsv = yoy_absolute(old_metrics["member_old_gsv"], yoy_prev.get("yoy_member_old_gsv"))
        yoy_member_old_users = yoy_absolute(old_metrics["member_old_users"], yoy_prev.get("yoy_member_old_users"))
        yoy_member_old_ratio = yoy_ratio(old_metrics["member_old_customer_gsv_ratio"], yoy_prev.get("yoy_member_old_customer_gsv_ratio"))
        yoy_member_old_aus = yoy_absolute(old_metrics["member_old_customer_aus"], yoy_prev.get("yoy_member_old_customer_aus"))

        # 4. 计算环比（上一个等长周期）
        mom_prev = _compute_mom_metrics(conn, analysis_date, period_days, exclude_channels, channel)

        mom_period_repurchase = mom_absolute(period_repurchase_users, mom_prev.get("mom_period_repurchase_users"))

        # 5. 计算健康评分（使用去年同周期实际值作为动态目标）
        health_score, health_level = _compute_health_score(
            all_store_repurchase_rate,
            same_product_repurchase_rate,
            old_metrics["old_customer_gsv_ratio"],
            old_metrics["old_customer_aus"],
            period_repurchase_users,
            period_days,
            targets=dynamic_targets,
        )
        # 健康评分YOY（百分点差，如 89.7 - 97.7 = -8.0pp）
        ly_health_score = yoy_prev.get("yoy_health_score")
        health_score_yoy = round(health_score - ly_health_score, 1) if ly_health_score is not None else None

        # 6. 生成告警
        alerts = _generate_alerts(
            all_store_repurchase_rate,
            same_product_repurchase_rate,
            old_metrics["old_customer_gsv_ratio"],
            old_metrics["old_customer_aus"],
            yoy_prev,
        )

        result = {
            "analysis_date": analysis_date,
            "period_days": period_days,
            "all_store_repurchase_rate": round(all_store_repurchase_rate, 4),
            "same_product_repurchase_rate": round(same_product_repurchase_rate, 4),
            # 老客绝对值
            "old_gsv": round(old_metrics["old_gsv"], 2),
            "old_users": old_metrics["old_users"],
            "old_customer_gsv_ratio": round(old_metrics["old_customer_gsv_ratio"], 4),
            "old_customer_aus": round(old_metrics["old_customer_aus"], 2),
            # 会员老客
            "member_old_gsv": round(old_metrics["member_old_gsv"], 2),
            "member_old_users": old_metrics["member_old_users"],
            "member_old_customer_gsv_ratio": round(old_metrics["member_old_customer_gsv_ratio"], 4),
            "member_old_customer_aus": round(old_metrics["member_old_customer_aus"], 2),
            # 周期复购人数
            "period_repurchase_users": period_repurchase_users,
            # 健康评分
            "health_score": health_score,
            "health_level": health_level,
            "ly_health_score": ly_health_score,
            "health_score_yoy": health_score_yoy,
            # 去年同期原始值（雷达图两年对比）
            "ly_all_store_repurchase_rate": yoy_prev.get("yoy_all_store_repurchase_rate"),
            "ly_same_product_repurchase_rate": yoy_prev.get("yoy_same_product_repurchase_rate"),
            "ly_old_customer_gsv_ratio": yoy_prev.get("yoy_old_customer_gsv_ratio"),
            "ly_old_customer_aus": yoy_prev.get("yoy_old_customer_aus"),
            "ly_period_repurchase_users": int(yoy_prev.get("yoy_period_repurchase_users", 0)) if yoy_prev.get("yoy_period_repurchase_users") is not None else None,
            # YOY（比例类）
            "yoy_all_store_repurchase_rate": yoy_all_store,
            "yoy_same_product_repurchase_rate": yoy_same_product,
            "yoy_old_customer_gsv_ratio": yoy_old_ratio,
            "yoy_old_customer_aus": yoy_old_aus,
            "yoy_period_repurchase_users": yoy_period_repurchase,
            # YOY（新增绝对值类）
            "yoy_old_gsv": yoy_old_gsv,
            "yoy_old_users": yoy_old_users,
            "yoy_member_old_gsv": yoy_member_old_gsv,
            "yoy_member_old_users": yoy_member_old_users,
            "yoy_member_old_customer_gsv_ratio": yoy_member_old_ratio,
            "yoy_member_old_customer_aus": yoy_member_old_aus,
            # MoM（环比）
            "mom_period_repurchase_users": mom_period_repurchase,
            "alerts": alerts,
        }

        # ── 缓存写入（历史周期）──
        if _is_historical_period(analysis_date):
            _write_cache(cache_key, result)

        return result

    finally:
        conn.close()


def _compute_dynamic_targets(
    conn,
    analysis_date: str,
    period_days: int,
    exclude_channels: Optional[List[str]] = None,
    channel: Optional[str] = None,
) -> Dict[str, float]:
    """
    计算动态目标值（去年同周期实际值）。

    返回5项指标的目标字典，可直接传给 _compute_health_score(targets=...)。
    复用外部传入的 conn，不自行管理连接。
    """
    end_dt = datetime.strptime(analysis_date, "%Y-%m-%d").date()
    start_dt = end_dt - timedelta(days=period_days - 1)

    def _prev_year(d):
        try:
            return d.replace(year=d.year - 1)
        except ValueError:
            return d.replace(year=d.year - 1, day=28)

    prev_end_dt = _prev_year(end_dt)
    prev_start_dt = _prev_year(start_dt)
    prev_start = prev_start_dt.strftime("%Y-%m-%d")
    prev_end = prev_end_dt.strftime("%Y-%m-%d")

    where_sql, params = _build_filter(exclude_channels, prev_start, prev_end, channel)

    prev_repurchase_rate, prev_repurchase_users, _ = _compute_repurchase_rate(conn, where_sql, params)
    prev_product_rate = _compute_product_repurchase_rate(conn, where_sql, params)
    prev_old_metrics = _compute_old_customer_metrics(conn, where_sql, params, prev_start)

    ly_weekly_repurchase = (
        round(prev_repurchase_users / period_days * 7)
        if period_days > 0 and prev_repurchase_users
        else 0
    )

    return {
        "all_store_repurchase_rate": round(prev_repurchase_rate, 4),
        "same_product_repurchase_rate": round(prev_product_rate, 4),
        "old_customer_gsv_ratio": round(prev_old_metrics["old_customer_gsv_ratio"], 4),
        "old_customer_aus": round(prev_old_metrics["old_customer_aus"], 2),
        "recent_7d_repurchase_users": ly_weekly_repurchase,
    }


def get_health_targets(
    analysis_date: str,
    period_days: int,
    exclude_channels: Optional[List[str]] = None,
    channel: Optional[str] = None,
) -> Dict[str, Any]:
    """
    返回指定周期的健康评分目标（自动沿用去年同周期实际值）。

    用于前端雷达图targets动态化和后端评分计算目标值。
    """
    conn = get_connection()
    try:
        targets = _compute_dynamic_targets(conn, analysis_date, period_days, exclude_channels, channel)
        return {
            "analysis_date": analysis_date,
            "period_days": period_days,
            "channel": channel,
            "exclude_channels": exclude_channels,
            **targets,
        }
    finally:
        conn.close()
