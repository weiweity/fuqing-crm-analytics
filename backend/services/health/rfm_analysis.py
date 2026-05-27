"""
老客健康分析仪表盘 - RFM完整分析（8象限人群分群）

基于R/F/M三维评分，将用户划分为8个经典象限，计算各象限回购率。
逻辑同R区间分析，仅将 r_segment 替换为 rfm_segment（8象限+TTL）。
"""

import duckdb
import json
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.config import DATA_DIR
from backend.db.connection import get_connection
from backend.services.rfm_service import _resolve_date_ranges
from backend.semantic.calculations import yoy_absolute, yoy_repurchase_rate
from backend.semantic.segments import RFM_THRESHOLDS
from backend.semantic.rfm_reader import try_read_rfm_segment

# 语义层统一口径：禁止在SQL中硬编码有效订单条件
_VALID_BASE = "is_goujinjin = FALSE AND order_status != '交易关闭'"

logger = logging.getLogger(__name__)

# 缓存目录
CACHE_DIR = DATA_DIR / "cache" / "rfm_flow"

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


def _cache_key(
    period: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    channel: Optional[str],
    metric_type: str,
    exclude_channels: Optional[List[str]],
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
) -> str:
    """
    生成缓存键文件名。

    一律基于实际日期范围构建缓存键（忽略 period 名），
    保证前端请求（含 period+dates）与预计算请求（仅 dates）键完全一致。
    缓存键包含数据版本，ETL刷新后自动失效所有历史缓存。

    对比日期参数（compare_start_date/compare_end_date）也参与缓存键生成，
    确保不同对比模式（YOY/环比/自定义）不会互相污染缓存。
    """
    dv = _data_version()
    parts = [dv]
    if start_date and end_date:
        parts.append(f"{start_date}_{end_date}")
    elif period:
        parts.append(period.upper())
    if channel and channel != "全店":
        safe_ch = channel.replace("'", "''")
        parts.append(f"ch_{safe_ch}")
    parts.append(metric_type)
    if exclude_channels:
        ch_str = ",".join(sorted(exclude_channels))
        ch_hash = hashlib.md5(ch_str.encode()).hexdigest()[:8]
        parts.append(f"ex_{ch_hash}")
    # 自定义对比期参与缓存键，避免不同对比模式共享缓存
    if compare_start_date and compare_end_date:
        parts.append(f"cmp_{compare_start_date}_{compare_end_date}")
    return "_".join(parts) + ".json"


def _is_historical_period(end_date: str) -> bool:
    """判断是否为已结束的历史周期（end_date < 今天）"""
    today = datetime.now().date()
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    return end_dt < today


def _read_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    """读取缓存文件。缓存不存在或解析失败返回 None。"""
    cache_file = CACHE_DIR / cache_key
    if not cache_file.exists():
        return None
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"RFM 缓存读取失败，跳过: {e}")
        return None


def _write_cache(cache_key: str, data: Dict[str, Any]) -> None:
    """写入缓存文件（原子写入：先写.tmp再rename）"""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = CACHE_DIR / cache_key
        tmp_file = cache_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)
        tmp_file.replace(cache_file)
    except IOError as e:
        logger.warning(f"RFM 缓存写入失败，跳过: {e}")

RFM_SEGMENT_ORDER = [
    "重要价值客户",
    "重要保持客户",
    "重要发展客户",
    "重要挽留客户",
    "一般价值客户",
    "一般保持客户",
    "一般发展客户",
    "一般挽留客户",
    "已购客TTL",
]


# ============================================================
# Step 1-3: RFM 预计算表读取（历史 RFM 分群从 user_rfm 读取，回购率仍需实时计算）
# ============================================================

def _get_available_analysis_dates(
    conn: duckdb.DuckDBPyConnection,
    lookback_days: int,
    metric_type: str,
) -> list:
    """返回 user_rfm 中所有可用的 analysis_date 列表（升序）。"""
    try:
        rows = conn.execute("""
            SELECT DISTINCT analysis_date::TEXT
            FROM user_rfm
            WHERE lookback_days = ? AND metric_type = ?
            ORDER BY analysis_date ASC
        """, [lookback_days, metric_type]).fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []


def _try_read_from_rfm_cache(
    conn: duckdb.DuckDBPyConnection,
    period_end_dt: str,
    cutoff_dt: str,
    channel: Optional[str],
    metric_type: str,
    lookback_days: int,
) -> Optional[
    tuple[
        Dict[str, Dict[str, float]],
        Dict[str, Dict[str, float]],
        Optional[Dict[str, Dict[str, float]]],  # member_all: None = fallback needed
        Optional[Dict[str, Dict[str, float]]],  # member_same: None = fallback needed
    ]
]:
    """从 user_rfm 预计算表读取非会员的历史 RFM 分群数据。

    策略：
    - 历史 RFM 分群（hist_users）→ 从 user_rfm 读取（快）
    - 回购指标（repurchase_users/gsv）→ 仍需实时计算，这里只填充 0
    - 会员分群（member_all/member_same）→ user_rfm 目前无 is_member 列，返回 None 触发回退

    参数:
        period_end_dt: 周期结束日期 (YYYY-MM-DD)，用于映射到 user_rfm 的 analysis_date
        cutoff_dt: RFM 截止日期 = period_end_dt（_run_rfm_period 中传入的 cutoff_dt）
        channel: 渠道过滤（None/全店/具体渠道）
        metric_type: GMV/GSV
        lookback_days: 回看天数

    返回:
        None: 预计算数据不命中，调用方应 fallback 到 live SQL
        4-tuple: (all_result, same_result, member_all_result, member_same_result)
        - all_result/same_result 始终有完整数据（含已购客TTL）
        - member_all_result/member_same_result 始终为 None（暂不支持）
    """
    # 1. 找到最接近且不超过 period_end_dt 的 analysis_date
    available_dates = _get_available_analysis_dates(conn, lookback_days, metric_type)
    if not available_dates:
        return None

    # period_end_dt 格式为 "YYYY-MM-DD HH:MM:SS"，提取日期部分
    period_end_date = period_end_dt[:10] if " " in period_end_dt or "-" in period_end_dt else period_end_dt

    # 找 <= period_end_date 的最近 analysis_date
    analysis_date = None
    for d in reversed(available_dates):
        if d <= period_end_date:
            analysis_date = d
            break

    if analysis_date is None:
        # 最老的预计算日期也比查询日期新，无法使用
        return None

    # 2. 构建渠道参数（全店 = channel is None or "全店" → 不过滤渠道）
    db_channel: Optional[str] = None
    if channel and channel != "全店":
        from backend.semantic.filters import expand_channels
        expanded = expand_channels([channel])
        if len(expanded) == 1:
            db_channel = expanded[0]
        else:
            # 多渠道展开 → 暂不支持精确预计算，回退
            return None

    # 3. 读取全店分群（all_result）和同渠道分群（same_result）
    #    user_rfm 目前无 is_member → member 变体返回 None
    all_result: Dict[str, Dict[str, float]] = {}
    same_result: Dict[str, Dict[str, float]] = {}

    # 查询 user_rfm 分群聚合（按 analysis_date/lookback_days/metric_type/channel）
    # 全店: channel = '全店'
    rows_all = try_read_rfm_segment(
        conn, analysis_date, lookback_days, metric_type, "全店"
    )
    if rows_all is None:
        return None

    # 同渠道: channel = db_channel（如果有）
    rows_same: Optional[Dict[str, Dict]] = None
    if db_channel:
        rows_same = try_read_rfm_segment(
            conn, analysis_date, lookback_days, metric_type, db_channel
        )
    elif channel is None or channel == "全店":
        rows_same = rows_all  # 全店查询直接复用

    # 4. 将 rfm_reader 格式转换为 _run_rfm_period 格式
    def _build_result(rows: Dict[str, Dict]) -> Dict[str, Dict[str, float]]:
        result: Dict[str, Dict[str, float]] = {}
        total_hist_users = 0

        # 先填充分群（repurchase 相关字段暂时填充 0，后续由调用方用实时数据填充）
        for seg in RFM_SEGMENT_ORDER:
            if seg == "已购客TTL":
                continue
            if seg in rows:
                uc = int(rows[seg]["user_count"])
                result[seg] = {
                    "hist_users": uc,
                    "repurchase_users": 0,
                    "repurchase_rate": 0.0,
                    "repurchase_gsv": 0.0,
                    "repurchase_gsv_ratio": 0.0,
                }
                total_hist_users += uc
            else:
                result[seg] = {
                    "hist_users": 0,
                    "repurchase_users": 0,
                    "repurchase_rate": 0.0,
                    "repurchase_gsv": 0.0,
                    "repurchase_gsv_ratio": 0.0,
                }

        # 已购客TTL = 各分群 hist_users 之和
        result["已购客TTL"] = {
            "hist_users": total_hist_users,
            "repurchase_users": 0,
            "repurchase_rate": 0.0,
            "repurchase_gsv": 0.0,
            "repurchase_gsv_ratio": 0.0,
        }
        return result

    all_result = _build_result(rows_all)
    same_result = _build_result(rows_same) if rows_same else all_result

    # 5. 会员变体暂不支持（user_rfm 无 is_member 列），返回 None 触发回退
    return all_result, same_result, None, None


def _run_rfm_period(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    channel: Optional[str] = None,
    metric_type: str = "GSV",
    exclude_channels: Optional[List[str]] = None,
) -> tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
    # ── 修复：直接使用全量 live SQL 计算，确保数据一致性 ──
    # 问题：user_rfm 表使用 lookback_days=90 分群，但 RFM 分析需要截至 cutoff_dt 的所有用户
    # 这导致从 user_rfm 读取的历史人数远小于 live 计算的人数（10倍差异）
    # 解决方案：禁用预计算缓存，直接使用 live SQL 计算
    return _run_rfm_period_live(
        conn, start_dt, end_dt, cutoff_dt,
        channel, metric_type, exclude_channels,
    )


# ── 辅助函数：轻量计算 repurchase 指标（复用预计算的 hist_users） ──

def _compute_repurchase_from_cache(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    channel: Optional[str],
    metric_type: str,
    exclude_channels: Optional[List[str]],
    cached_all: Dict[str, Dict[str, float]],
    cached_same: Dict[str, Dict[str, float]],
) -> tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict, Dict]:
    """用预计算的 hist_users（来自 user_rfm） + 轻量 live SQL 计算 repurchase 指标。

    策略：
    - cached_all/cached_same 含预计算的 hist_users，repurchase_* 均为 0
    - 此函数运行轻量 SQL：用 base_orders（当前 period 买家）与 user_rfm 的 segment 分配
      做 JOIN，计算每个分群的 repurchase_users / repurchase_gsv
    - 对于 hist_users：用 cached 中的预计算值（all_channels 来源）或
      按全店比例分配 same_channel 的 hist_users（因为 user_rfm 的 same_channel
      数据已在 cached_same 中有了，这里复用）
    """
    refund_where = "AND is_refund = FALSE" if metric_type == "GSV" else ""

    exclude_where = ""
    if exclude_channels:
        from backend.semantic.filters import expand_channels
        db_ex = expand_channels(exclude_channels)
        safe_ch = [c.replace("'", "''") for c in db_ex]
        quoted = ", ".join([f"'{c}'" for c in safe_ch])
        exclude_where = f" AND o.channel NOT IN ({quoted})"

    # 全店分群的 repurchase：从 base_orders LEFT JOIN user_rfm（channel=全店）得到分群归属
    sql_all = f"""
    WITH
    base_orders AS (
        SELECT user_id, SUM(actual_amount) AS period_gsv
        FROM orders o
        WHERE pay_time >= ?::TIMESTAMP
          AND pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {exclude_where}
        GROUP BY user_id
    ),
    buyer_segments AS (
        SELECT bo.user_id, bo.period_gsv,
               COALESCE(ur.rfm_tier, '一般挽留客户') AS rfm_segment
        FROM base_orders bo
        LEFT JOIN user_rfm ur
          ON bo.user_id = ur.user_id
         AND ur.analysis_date = (
             SELECT MAX(analysis_date)::TEXT
             FROM user_rfm
             WHERE lookback_days = 90 AND metric_type = ?
         )
         AND ur.lookback_days = 90
         AND ur.metric_type = ?
         AND ur.channel = '全店'
    ),
    rep_stats AS (
        SELECT rfm_segment,
               COUNT(DISTINCT user_id) AS repurchase_users,
               SUM(period_gsv) AS repurchase_gsv
        FROM buyer_segments
        GROUP BY rfm_segment
    )
    SELECT rfm_segment, repurchase_users, repurchase_gsv FROM rep_stats
    """
    params_all = [start_dt, end_dt, metric_type, metric_type]
    rows_all = conn.execute(sql_all, params_all).fetchall()
    rep_map_all: Dict[str, tuple[int, float]] = {
        r[0]: (int(r[1]), float(r[2])) for r in rows_all
    }

    # same_channel 分群的 repurchase
    if channel and channel != "全店":
        from backend.semantic.filters import expand_channels
        db_channels = expand_channels([channel])
        ch = db_channels[0] if len(db_channels) == 1 else None
    else:
        ch = None

    if ch:
        sql_same = f"""
        WITH
        base_orders AS (
            SELECT user_id, SUM(actual_amount) AS period_gsv
            FROM orders o
            WHERE pay_time >= ?::TIMESTAMP
              AND pay_time <= ?::TIMESTAMP
              AND {_VALID_BASE}
              {refund_where}
              AND o.channel = ?
              {exclude_where}
            GROUP BY user_id
        ),
        buyer_segments AS (
            SELECT bo.user_id, bo.period_gsv,
                   COALESCE(ur.rfm_tier, '一般挽留客户') AS rfm_segment
            FROM base_orders bo
            LEFT JOIN user_rfm ur
              ON bo.user_id = ur.user_id
             AND ur.analysis_date = (
                 SELECT MAX(analysis_date)::TEXT
                 FROM user_rfm
                 WHERE lookback_days = 90 AND metric_type = ?
             )
             AND ur.lookback_days = 90
             AND ur.metric_type = ?
             AND ur.channel = ?
        ),
        rep_stats AS (
            SELECT rfm_segment,
                   COUNT(DISTINCT user_id) AS repurchase_users,
                   SUM(period_gsv) AS repurchase_gsv
            FROM buyer_segments
            GROUP BY rfm_segment
        )
        SELECT rfm_segment, repurchase_users, repurchase_gsv FROM rep_stats
        """
        params_same = [start_dt, end_dt, ch, metric_type, metric_type, ch]
    else:
        # 全店：same 与 all 相同
        params_same = []
        rep_map_same = rep_map_all

    if ch:
        rows_same = conn.execute(sql_same, params_same).fetchall()
        rep_map_same = {r[0]: (int(r[1]), float(r[2])) for r in rows_same}

    # ── 合并 repurchase 数据入 cached 结果 ──
    def _merge(rep_map: Dict[str, tuple[int, float]],
               cached: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
        result: Dict[str, Dict[str, float]] = {}
        total_repurchase_gsv = 0.0

        for seg in RFM_SEGMENT_ORDER:
            if seg == "已购客TTL":
                continue
            entry = dict(cached.get(seg, {
                "hist_users": 0, "repurchase_users": 0,
                "repurchase_rate": 0.0, "repurchase_gsv": 0.0,
                "repurchase_gsv_ratio": 0.0,
            }))
            if seg in rep_map:
                ru, rg = rep_map[seg]
                entry["repurchase_users"] = ru
                entry["repurchase_gsv"] = rg
                entry["repurchase_rate"] = (
                    round(ru / entry["hist_users"], 4)
                    if entry["hist_users"] else 0.0
                )
            total_repurchase_gsv += entry["repurchase_gsv"]
            result[seg] = entry

        # 已购客TTL
        ttl_hist = sum(cached.get(s, {}).get("hist_users", 0) for s in RFM_SEGMENT_ORDER if s != "已购客TTL")
        ttl_ru = sum(rep_map.get(s, (0, 0.0))[0] for s in RFM_SEGMENT_ORDER if s != "已购客TTL")
        ttl_rg = total_repurchase_gsv
        result["已购客TTL"] = {
            "hist_users": ttl_hist,
            "repurchase_users": ttl_ru,
            "repurchase_rate": round(ttl_ru / ttl_hist, 4) if ttl_hist else 0.0,
            "repurchase_gsv": ttl_rg,
            "repurchase_gsv_ratio": 0.0,
        }

        # repurchase_gsv_ratio（基于各分群占总 GSV 比）
        if total_repurchase_gsv > 0:
            for seg in result:
                result[seg]["repurchase_gsv_ratio"] = (
                    round(result[seg]["repurchase_gsv"] / total_repurchase_gsv, 4)
                    if result[seg]["repurchase_gsv"] else 0.0
                )

        return result

    merged_all = _merge(rep_map_all, cached_all)
    merged_same = _merge(rep_map_same, cached_same) if ch else merged_all

    # member_all / member_same：暂不支持（user_rfm 无 is_member），返回空 dict
    empty_member: Dict[str, Dict[str, float]] = {}
    return merged_all, merged_same, empty_member, empty_member


def _run_rfm_period_member_live(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    channel: Optional[str],
    metric_type: str,
    exclude_channels: Optional[List[str]],
) -> tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
    """只计算会员分群（member_all + member_same），用于预计算命中时回退会员指标。

    运行与 _run_rfm_period 相同的 SQL，但只提取 member_all 和 member_same 结果。
    适用于 user_rfm 无 is_member 列时的过渡方案。
    """
    params: List[Any] = [start_dt, end_dt]
    channel_where_base = ""
    channel_where_hist = ""
    db_channels: List[str] = []
    if channel and channel != "全店":
        from backend.semantic.filters import expand_channels
        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_where_base = " AND o.channel = ?"
            channel_where_hist = " AND o.channel = ?"
            params.append(db_channels[0])
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_where_base = f" AND o.channel IN ({placeholders})"
            channel_where_hist = f" AND o.channel IN ({placeholders})"
            params.extend(db_channels)

    params.append(cutoff_dt)
    params.append(cutoff_dt)
    if db_channels:
        params.extend(db_channels)
    params.extend([cutoff_dt] * 4)
    params.extend([cutoff_dt] * 4)

    exclude_where_base = ""
    exclude_where_hist = ""
    if exclude_channels:
        from backend.semantic.filters import expand_channels
        db_exclude_channels = expand_channels(exclude_channels)
        safe_ch = [ch.replace("'", "''") for ch in db_exclude_channels]
        quoted = ", ".join([f"'{c}'" for c in safe_ch])
        exclude_where_base = f" AND o.channel NOT IN ({quoted})"
        exclude_where_hist = f" AND o.channel NOT IN ({quoted})"

    refund_where = "AND is_refund = FALSE" if metric_type == "GSV" else ""
    _rt = RFM_THRESHOLDS["r"]
    _ft = RFM_THRESHOLDS["f"]
    _mt = RFM_THRESHOLDS["m"]

    sql = f"""
    WITH
    base_orders AS (
        SELECT user_id, actual_amount
        FROM orders o
        WHERE pay_time >= ?::TIMESTAMP
          AND pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {channel_where_base}
          {exclude_where_base}
    ),
    user_stats_all AS (
        SELECT user_id, MAX(pay_time) as last_pay_time,
               COUNT(DISTINCT order_id) as order_count,
               SUM(actual_amount) as gsv,
               BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {exclude_where_hist}
        GROUP BY user_id
    ),
    user_stats_same AS (
        SELECT user_id, MAX(pay_time) as last_pay_time,
               COUNT(DISTINCT order_id) as order_count,
               SUM(actual_amount) as gsv,
               BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {channel_where_hist}
          {exclude_where_hist}
        GROUP BY user_id
    ),
    rfm_scored_all AS (
        SELECT user_id, is_member,
            CASE
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[0]} THEN 5
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[1]} THEN 4
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[2]} THEN 3
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[3]} THEN 2
                ELSE 1
            END as r_score,
            CASE WHEN order_count >= {_ft[3] + 1} THEN 5 WHEN order_count >= {_ft[2] + 1} THEN 4 WHEN order_count = {_ft[2]} THEN 3 WHEN order_count = {_ft[1]} THEN 2 ELSE 1 END as f_score,
            CASE WHEN gsv >= {_mt[3]} THEN 5 WHEN gsv >= {_mt[2]} THEN 4 WHEN gsv >= {_mt[1]} THEN 3 WHEN gsv >= {_mt[0]} THEN 2 ELSE 1 END as m_score
        FROM user_stats_all
    ),
    rfm_scored_same AS (
        SELECT user_id, is_member,
            CASE
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[0]} THEN 5
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[1]} THEN 4
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[2]} THEN 3
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[3]} THEN 2
                ELSE 1
            END as r_score,
            CASE WHEN order_count >= {_ft[3] + 1} THEN 5 WHEN order_count >= {_ft[2] + 1} THEN 4 WHEN order_count = {_ft[2]} THEN 3 WHEN order_count = {_ft[1]} THEN 2 ELSE 1 END as f_score,
            CASE WHEN gsv >= {_mt[3]} THEN 5 WHEN gsv >= {_mt[2]} THEN 4 WHEN gsv >= {_mt[1]} THEN 3 WHEN gsv >= {_mt[0]} THEN 2 ELSE 1 END as m_score
        FROM user_stats_same
    ),
    member_segmented_all AS (
        SELECT user_id,
            CASE
                WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '重要价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN '重要保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN '重要发展客户'
                WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN '重要挽留客户'
                WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN '一般价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN '一般保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN '一般发展客户'
                ELSE '一般挽留客户'
            END as rfm_segment
        FROM rfm_scored_all WHERE is_member = TRUE
    ),
    member_segmented_same AS (
        SELECT user_id,
            CASE
                WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '重要价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN '重要保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN '重要发展客户'
                WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN '重要挽留客户'
                WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN '一般价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN '一般保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN '一般发展客户'
                ELSE '一般挽留客户'
            END as rfm_segment
        FROM rfm_scored_same WHERE is_member = TRUE
    ),
    repurchase_users AS (SELECT DISTINCT user_id FROM base_orders),
    repurchase_amounts AS (
        SELECT bo.user_id, SUM(bo.actual_amount) AS repurchase_gsv
        FROM base_orders bo INNER JOIN repurchase_users rp ON bo.user_id = rp.user_id
        GROUP BY bo.user_id
    ),
    member_stats_all AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT rp.user_id) AS repurchase_users,
               COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented_all r
        LEFT JOIN repurchase_users rp ON r.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON r.user_id = ra.user_id
        GROUP BY r.rfm_segment
    ),
    member_stats_same AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT rp.user_id) AS repurchase_users,
               COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented_same r
        LEFT JOIN repurchase_users rp ON r.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON r.user_id = ra.user_id
        GROUP BY r.rfm_segment
    ),
    member_ttl_all AS (
        SELECT '已购客TTL' AS rfm_segment,
               SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users,
               SUM(repurchase_gsv) AS repurchase_gsv
        FROM member_stats_all
    ),
    member_ttl_same AS (
        SELECT '已购客TTL' AS rfm_segment,
               SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users,
               SUM(repurchase_gsv) AS repurchase_gsv
        FROM member_stats_same
    )
    SELECT 'member_all' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv
    FROM (SELECT * FROM member_stats_all UNION ALL SELECT * FROM member_ttl_all)
    UNION ALL
    SELECT 'member_same' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv
    FROM (SELECT * FROM member_stats_same UNION ALL SELECT * FROM member_ttl_same)
    """

    rows = conn.execute(sql, params).fetchall()
    member_all_result: Dict[str, Dict[str, float]] = {}
    member_same_result: Dict[str, Dict[str, float]] = {}
    total_gsv_all = 0.0
    total_gsv_same = 0.0

    for r in rows:
        mode, segment, hist_users, repurchase_users, repurchase_gsv = r
        entry = {
            "hist_users": int(hist_users or 0),
            "repurchase_users": int(repurchase_users or 0),
            "repurchase_rate": (
                round(float(repurchase_users or 0) / float(hist_users or 1), 4)
                if hist_users else 0.0
            ),
            "repurchase_gsv": float(repurchase_gsv or 0),
            "repurchase_gsv_ratio": 0.0,
        }
        if segment != "已购客TTL":
            if mode == "member_all":
                total_gsv_all += float(repurchase_gsv or 0)
                member_all_result[segment] = entry
            else:
                total_gsv_same += float(repurchase_gsv or 0)
                member_same_result[segment] = entry
        else:
            if mode == "member_all":
                member_all_result[segment] = entry
            else:
                member_same_result[segment] = entry

    # ratio
    for seg in member_all_result:
        gsv = member_all_result[seg]["repurchase_gsv"]
        member_all_result[seg]["repurchase_gsv_ratio"] = (
            round(gsv / total_gsv_all, 4) if total_gsv_all > 0 else 0.0
        )
    for seg in member_same_result:
        gsv = member_same_result[seg]["repurchase_gsv"]
        member_same_result[seg]["repurchase_gsv_ratio"] = (
            round(gsv / total_gsv_same, 4) if total_gsv_same > 0 else 0.0
        )

    # 补零
    for seg in RFM_SEGMENT_ORDER:
        if seg not in member_all_result:
            member_all_result[seg] = {
                "hist_users": 0, "repurchase_users": 0,
                "repurchase_rate": 0.0, "repurchase_gsv": 0.0,
                "repurchase_gsv_ratio": 0.0,
            }
        if seg not in member_same_result:
            member_same_result[seg] = {
                "hist_users": 0, "repurchase_users": 0,
                "repurchase_rate": 0.0, "repurchase_gsv": 0.0,
                "repurchase_gsv_ratio": 0.0,
            }

    return member_all_result, member_same_result


# ── Fallback: 全量 live SQL（预计算未命中时调用）─────────────────────────────

def _run_rfm_period_live(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    channel: Optional[str],
    metric_type: str,
    exclude_channels: Optional[List[str]],
) -> tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
    """全量实时 SQL 计算（预计算表未命中时的 fallback）。

    参数顺序（对应 SQL 占位符）：
    1. base_orders: start_dt, end_dt [, channel]
    2. user_stats_all: cutoff_dt
    3. user_stats_same: cutoff_dt [, channel]
    4. rfm_scored_all: cutoff_dt × 4
    5. rfm_scored_same: cutoff_dt × 4
    """
    params: List[Any] = [start_dt, end_dt]

    channel_where_base = ""
    channel_where_hist = ""
    db_channels: List[str] = []
    if channel and channel != "全店":
        from backend.semantic.filters import expand_channels
        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_where_base = " AND o.channel = ?"
            channel_where_hist = " AND o.channel = ?"
            params.append(db_channels[0])
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_where_base = f" AND o.channel IN ({placeholders})"
            channel_where_hist = f" AND o.channel IN ({placeholders})"
            params.extend(db_channels)

    params.append(cutoff_dt)  # user_stats_all
    params.append(cutoff_dt)  # user_stats_same
    if db_channels:
        params.extend(db_channels)  # user_stats_same channel

    params.extend([cutoff_dt] * 4)  # rfm_scored_all
    params.extend([cutoff_dt] * 4)  # rfm_scored_same

    exclude_where_base = ""
    exclude_where_hist = ""
    if exclude_channels:
        from backend.semantic.filters import expand_channels
        db_exclude_channels = expand_channels(exclude_channels)
        safe_ch = [ch.replace("'", "''") for ch in db_exclude_channels]
        quoted = ", ".join([f"'{c}'" for c in safe_ch])
        exclude_where_base = f" AND o.channel NOT IN ({quoted})"
        exclude_where_hist = f" AND o.channel NOT IN ({quoted})"

    refund_where = "AND is_refund = FALSE" if metric_type == "GSV" else ""
    _rt = RFM_THRESHOLDS["r"]
    _ft = RFM_THRESHOLDS["f"]
    _mt = RFM_THRESHOLDS["m"]

    sql = f"""
    WITH
    base_orders AS (
        SELECT user_id, actual_amount
        FROM orders o
        WHERE pay_time >= ?::TIMESTAMP
          AND pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {channel_where_base}
          {exclude_where_base}
    ),
    user_stats_all AS (
        SELECT user_id, MAX(pay_time) as last_pay_time,
               COUNT(DISTINCT order_id) as order_count,
               SUM(actual_amount) as gsv,
               BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {exclude_where_hist}
        GROUP BY user_id
    ),
    user_stats_same AS (
        SELECT user_id, MAX(pay_time) as last_pay_time,
               COUNT(DISTINCT order_id) as order_count,
               SUM(actual_amount) as gsv,
               BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {channel_where_hist}
          {exclude_where_hist}
        GROUP BY user_id
    ),
    rfm_scored_all AS (
        SELECT user_id, is_member,
            CASE
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[0]} THEN 5
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[1]} THEN 4
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[2]} THEN 3
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[3]} THEN 2
                ELSE 1
            END as r_score,
            CASE WHEN order_count >= {_ft[3] + 1} THEN 5 WHEN order_count >= {_ft[2] + 1} THEN 4 WHEN order_count = {_ft[2]} THEN 3 WHEN order_count = {_ft[1]} THEN 2 ELSE 1 END as f_score,
            CASE WHEN gsv >= {_mt[3]} THEN 5 WHEN gsv >= {_mt[2]} THEN 4 WHEN gsv >= {_mt[1]} THEN 3 WHEN gsv >= {_mt[0]} THEN 2 ELSE 1 END as m_score
        FROM user_stats_all
    ),
    rfm_scored_same AS (
        SELECT user_id, is_member,
            CASE
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[0]} THEN 5
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[1]} THEN 4
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[2]} THEN 3
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[3]} THEN 2
                ELSE 1
            END as r_score,
            CASE WHEN order_count >= {_ft[3] + 1} THEN 5 WHEN order_count >= {_ft[2] + 1} THEN 4 WHEN order_count = {_ft[2]} THEN 3 WHEN order_count = {_ft[1]} THEN 2 ELSE 1 END as f_score,
            CASE WHEN gsv >= {_mt[3]} THEN 5 WHEN gsv >= {_mt[2]} THEN 4 WHEN gsv >= {_mt[1]} THEN 3 WHEN gsv >= {_mt[0]} THEN 2 ELSE 1 END as m_score
        FROM user_stats_same
    ),
    segmented_all AS (
        SELECT user_id, is_member,
            CASE
                WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '重要价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN '重要保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN '重要发展客户'
                WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN '重要挽留客户'
                WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN '一般价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN '一般保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN '一般发展客户'
                ELSE '一般挽留客户'
            END as rfm_segment
        FROM rfm_scored_all
    ),
    segmented_same AS (
        SELECT user_id, is_member,
            CASE
                WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '重要价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN '重要保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN '重要发展客户'
                WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN '重要挽留客户'
                WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN '一般价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN '一般保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN '一般发展客户'
                ELSE '一般挽留客户'
            END as rfm_segment
        FROM rfm_scored_same
    ),
    member_segmented_all AS (SELECT user_id, rfm_segment FROM segmented_all WHERE is_member = TRUE),
    member_segmented_same AS (SELECT user_id, rfm_segment FROM segmented_same WHERE is_member = TRUE),
    repurchase_users AS (SELECT DISTINCT user_id FROM base_orders),
    repurchase_amounts AS (
        SELECT bo.user_id, SUM(bo.actual_amount) AS repurchase_gsv
        FROM base_orders bo INNER JOIN repurchase_users rp ON bo.user_id = rp.user_id
        GROUP BY bo.user_id
    ),
    segment_stats_all AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT rp.user_id) AS repurchase_users,
               COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM segmented_all r
        LEFT JOIN repurchase_users rp ON r.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON r.user_id = ra.user_id
        GROUP BY r.rfm_segment
    ),
    segment_stats_same AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT rp.user_id) AS repurchase_users,
               COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM segmented_same r
        LEFT JOIN repurchase_users rp ON r.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON r.user_id = ra.user_id
        GROUP BY r.rfm_segment
    ),
    member_stats_all AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT rp.user_id) AS repurchase_users,
               COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented_all r
        LEFT JOIN repurchase_users rp ON r.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON r.user_id = ra.user_id
        GROUP BY r.rfm_segment
    ),
    member_stats_same AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT rp.user_id) AS repurchase_users,
               COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented_same r
        LEFT JOIN repurchase_users rp ON r.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON r.user_id = ra.user_id
        GROUP BY r.rfm_segment
    ),
    ttl_stats_all AS (SELECT '已购客TTL' AS rfm_segment, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM segment_stats_all),
    ttl_stats_same AS (SELECT '已购客TTL' AS rfm_segment, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM segment_stats_same),
    member_ttl_stats_all AS (SELECT '已购客TTL' AS rfm_segment, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM member_stats_all),
    member_ttl_stats_same AS (SELECT '已购客TTL' AS rfm_segment, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM member_stats_same)
    SELECT 'all' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM segment_stats_all UNION ALL SELECT * FROM ttl_stats_all
    )
    UNION ALL
    SELECT 'same' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM segment_stats_same UNION ALL SELECT * FROM ttl_stats_same
    )
    UNION ALL
    SELECT 'member_all' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM member_stats_all UNION ALL SELECT * FROM member_ttl_stats_all
    )
    UNION ALL
    SELECT 'member_same' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM member_stats_same UNION ALL SELECT * FROM member_ttl_stats_same
    )
    """

    rows = conn.execute(sql, params).fetchall()
    all_result: Dict[str, Dict[str, float]] = {}
    same_result: Dict[str, Dict[str, float]] = {}
    member_all_result: Dict[str, Dict[str, float]] = {}
    member_same_result: Dict[str, Dict[str, float]] = {}
    total_gsv_all = 0.0
    total_gsv_same = 0.0
    total_gsv_member_all = 0.0
    total_gsv_member_same = 0.0

    for r in rows:
        mode, segment, hist_users, repurchase_users, repurchase_gsv = r
        entry = {
            "hist_users": int(hist_users or 0),
            "repurchase_users": int(repurchase_users or 0),
            "repurchase_rate": (
                round(float(repurchase_users or 0) / float(hist_users or 1), 4)
                if hist_users else 0.0
            ),
            "repurchase_gsv": float(repurchase_gsv or 0),
            "repurchase_gsv_ratio": 0.0,
        }
        if segment != "已购客TTL":
            if mode == "all":
                total_gsv_all += float(repurchase_gsv or 0)
                all_result[segment] = entry
            elif mode == "same":
                total_gsv_same += float(repurchase_gsv or 0)
                same_result[segment] = entry
            elif mode == "member_all":
                total_gsv_member_all += float(repurchase_gsv or 0)
                member_all_result[segment] = entry
            elif mode == "member_same":
                total_gsv_member_same += float(repurchase_gsv or 0)
                member_same_result[segment] = entry
        else:
            if mode == "all":
                all_result[segment] = entry
            elif mode == "same":
                same_result[segment] = entry
            elif mode == "member_all":
                member_all_result[segment] = entry
            elif mode == "member_same":
                member_same_result[segment] = entry

    # repurchase_gsv_ratio
    for seg in all_result:
        gsv = all_result[seg]["repurchase_gsv"]
        all_result[seg]["repurchase_gsv_ratio"] = round(gsv / total_gsv_all, 4) if total_gsv_all > 0 else 0.0
    for seg in same_result:
        gsv = same_result[seg]["repurchase_gsv"]
        same_result[seg]["repurchase_gsv_ratio"] = round(gsv / total_gsv_same, 4) if total_gsv_same > 0 else 0.0
    for seg in member_all_result:
        gsv = member_all_result[seg]["repurchase_gsv"]
        member_all_result[seg]["repurchase_gsv_ratio"] = round(gsv / total_gsv_member_all, 4) if total_gsv_member_all > 0 else 0.0
    for seg in member_same_result:
        gsv = member_same_result[seg]["repurchase_gsv"]
        member_same_result[seg]["repurchase_gsv_ratio"] = round(gsv / total_gsv_member_same, 4) if total_gsv_member_same > 0 else 0.0

    # 补零
    for seg in RFM_SEGMENT_ORDER:
        if seg not in all_result:
            all_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}
        if seg not in same_result:
            same_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}
        if seg not in member_all_result:
            member_all_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}
        if seg not in member_same_result:
            member_same_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}

    return all_result, same_result, member_all_result, member_same_result


def _run_and_build(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    channel: Optional[str],
    metric_type: str,
    exclude_channels: Optional[List[str]],
) -> tuple[
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
]:
    """对单个周期执行 SQL 并返回 4 套原始 dict（不做 YoY 计算）"""
    return _run_rfm_period(conn, start_dt, end_dt, cutoff_dt, channel, metric_type, exclude_channels)


def _build_rows(all_data, comp_data, prev2_data):
    """将3个周期的 dict 数据构建为带 YoY 的行列表"""
    rows = []
    for seg in RFM_SEGMENT_ORDER:
        c = all_data.get(seg, {})
        p = comp_data.get(seg, {})
        p2 = prev2_data.get(seg, {})
        rows.append({
            "rfm_segment": seg,
            "hist_users_current": c.get("hist_users", 0),
            "repurchase_users_current": c.get("repurchase_users", 0),
            "repurchase_rate_current": round(c.get("repurchase_rate", 0.0), 4),
            "repurchase_gsv_current": round(c.get("repurchase_gsv", 0.0), 2),
            "repurchase_gsv_ratio_current": round(c.get("repurchase_gsv_ratio", 0.0), 4),
            "hist_users_comp": p.get("hist_users", 0),
            "repurchase_users_comp": p.get("repurchase_users", 0),
            "repurchase_rate_comp": round(p.get("repurchase_rate", 0.0), 4),
            "repurchase_gsv_comp": round(p.get("repurchase_gsv", 0.0), 2),
            "repurchase_gsv_ratio_comp": round(p.get("repurchase_gsv_ratio", 0.0), 4),
            "hist_users_prev2": p2.get("hist_users", 0),
            "repurchase_users_prev2": p2.get("repurchase_users", 0),
            "repurchase_rate_prev2": round(p2.get("repurchase_rate", 0.0), 4),
            "repurchase_gsv_prev2": round(p2.get("repurchase_gsv", 0.0), 2),
            "repurchase_gsv_ratio_prev2": round(p2.get("repurchase_gsv_ratio", 0.0), 4),
            "yoy_hist_users": yoy_absolute(c.get("hist_users", 0), p.get("hist_users", 0)),
            "yoy_repurchase_users": yoy_absolute(c.get("repurchase_users", 0), p.get("repurchase_users", 0)),
            "yoy_repurchase_rate": yoy_repurchase_rate(c.get("repurchase_rate", 0.0), p.get("repurchase_rate", 0.0)),
            "yoy_repurchase_gsv": yoy_absolute(c.get("repurchase_gsv", 0.0), p.get("repurchase_gsv", 0.0)),
            "yoy_repurchase_gsv_ratio": yoy_repurchase_rate(c.get("repurchase_gsv_ratio", 0.0), p.get("repurchase_gsv_ratio", 0.0)),
        })
    return rows


def _resolve_single_period(
    period: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    year_offset: int = 0,
) -> tuple[str, str, str]:
    """解析单个周期的日期字符串（返回 start, end, cutoff）"""
    if period:
        today = datetime.now().date()
        try:
            pb_func = getattr(__import__(
                "backend.semantic.time", fromlist=["PeriodBuilder"]
            ).PeriodBuilder, period.lower())
            ranges = pb_func(today=today)
            cur_range = ranges["current"]
            return (
                f"{cur_range.start} 00:00:00",
                f"{cur_range.end} 23:59:59",
                cur_range.cutoff,
            )
        except (AttributeError, KeyError):
            pass
    # 自定义日期
    if start_date and end_date:
        sy, sm, sd = map(int, start_date.split("-"))
        ey, em, ed = map(int, end_date.split("-"))
        from calendar import monthrange
        from datetime import date, timedelta
        cutoff_date = date(sy, sm, 1) - timedelta(days=1)
        return (
            f"{start_date} 00:00:00",
            f"{end_date} 23:59:59",
            cutoff_date.strftime("%Y-%m-%d"),
        )
    # 默认 MTD（含 year_offset）
    today = datetime.now().date()
    from calendar import monthrange
    from datetime import timedelta
    y = today.year + year_offset
    m = today.month
    _, last = monthrange(y, m)
    start = f"{y}-{m:02d}-01"
    end = f"{y}-{m:02d}-{last:02d}"
    cutoff = date(y, m, 1) - timedelta(days=1)
    return (
        f"{start} 00:00:00",
        f"{end} 23:59:59",
        cutoff.strftime("%Y-%m-%d"),
    )


def _get_period_label(period: Optional[str], start_date: Optional[str]) -> str:
    """生成年份标签（用于 _build_rows 中取 comp/prev2 的正确偏移）"""
    # 返回当前实际年份数字（用于 _build_rows 识别 comp/prev2）
    # year_offset 由调用方控制，这里只返回基准年
    if start_date:
        return start_date[:4]
    return str(datetime.now().year)


def get_rfm_analysis(
    year: int = 2026,
    metric_type: str = "GSV",
    period: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    RFM 8象限完整分析。

    缓存策略（Plan C）：
    - 历史周期（end_date < 今天）：读缓存 / 写缓存
    - 当前周期：实时计算，不缓存
    """
    ranges = _resolve_date_ranges(period, start_date, end_date, compare_start_date, compare_end_date)
    cur_start_dt, cur_end_dt, cutoff = ranges["current"]
    comp_start_dt, comp_end_dt, comp_cutoff = ranges["comp"]
    prev2_start_dt, prev2_end_dt, prev2_cutoff = ranges["prev2"]
    current_year_label, comp_year_label, prev2_year_label = ranges["labels"]

    # 缓存读取顺序：1) DuckDB预计算表 → 2) 文件缓存 → 3) 实时SQL
    # Plan P1: DuckDB 预计算表（ETL 预热，最优先）
    cached = _read_db_cache(period, start_date, end_date, channel, metric_type, exclude_channels, compare_start_date, compare_end_date)
    if cached is not None:
        return cached
    # Plan C: 文件缓存（自定义日期范围兜底）
    if _is_historical_period(cur_end_dt[:10]):
        cached = _read_cache(_cache_key(period, start_date, end_date, channel, metric_type, exclude_channels, compare_start_date, compare_end_date))
        if cached is not None:
            return cached

    conn = get_connection()
    try:
        cur_all, cur_same, cur_member_all, cur_member_same = _run_rfm_period(
            conn, cur_start_dt, cur_end_dt, cutoff, channel, metric_type, exclude_channels
        )
        comp_all, comp_same, comp_member_all, comp_member_same = _run_rfm_period(
            conn, comp_start_dt, comp_end_dt, comp_cutoff, channel, metric_type, exclude_channels
        )
        prev2_all, prev2_same, prev2_member_all, prev2_member_same = _run_rfm_period(
            conn, prev2_start_dt, prev2_end_dt, prev2_cutoff, channel, metric_type, exclude_channels
        )
    finally:
        conn.close()

    rows = _build_rows(cur_all, comp_all, prev2_all)
    same_channel_rows = _build_rows(cur_same, comp_same, prev2_same)
    member_rows = _build_rows(cur_member_all, comp_member_all, prev2_member_all)
    member_same_channel_rows = _build_rows(cur_member_same, comp_member_same, prev2_member_same)

    result = {
        "year_label": current_year_label,
        "comp_year_label": comp_year_label,
        "prev2_year_label": prev2_year_label,
        "metric_type": metric_type,
        "rows": rows,
        "same_channel_rows": same_channel_rows,
        "member_rows": member_rows,
        "member_same_channel_rows": member_same_channel_rows,
    }

    # Plan C: 历史周期写入文件缓存（DuckDB 预计算已在 ETL 阶段写入）
    if _is_historical_period(cur_end_dt[:10]):
        _write_cache(_cache_key(period, start_date, end_date, channel, metric_type, exclude_channels, compare_start_date, compare_end_date), result)

    return result


# ============================================================
# Plan P1: DuckDB 预计算表（ETL 钩子预热，历史周期直接读表）
# ============================================================

RFM_CACHE_TABLE = "rfm_analysis_cache"


def _ensure_db_cache_table(conn: duckdb.DuckDBPyConnection) -> None:
    """确保预计算缓存表存在"""
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {RFM_CACHE_TABLE} (
            cache_key    VARCHAR PRIMARY KEY,
            period       VARCHAR,
            start_date   VARCHAR,
            end_date     VARCHAR,
            channel      VARCHAR,
            metric_type  VARCHAR,
            ex_channels  VARCHAR,
            result_json  VARCHAR,
            computed_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{RFM_CACHE_TABLE}_period "
                 f"ON {RFM_CACHE_TABLE}(period, start_date, end_date, channel, metric_type)")


def _read_db_cache(
    period: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    channel: Optional[str],
    metric_type: str,
    exclude_channels: Optional[List[str]],
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """从 DuckDB 预计算表读取缓存（优先于文件缓存）"""
    key = _cache_key(period, start_date, end_date, channel, metric_type, exclude_channels, compare_start_date, compare_end_date)
    conn = get_connection()
    try:
        _ensure_db_cache_table(conn)
        row = conn.execute(
            f"SELECT result_json FROM {RFM_CACHE_TABLE} WHERE cache_key = ?",
            [key]
        ).fetchone()
        if row:
            return json.loads(row[0])
    except Exception as e:
        logger.warning(f"RFM DuckDB 缓存读取失败: {e}")
    finally:
        conn.close()
    return None


def _write_db_cache(
    period: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    channel: Optional[str],
    metric_type: str,
    exclude_channels: Optional[List[str]],
    result: Dict[str, Any],
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
) -> None:
    """写入 DuckDB 预计算缓存表"""
    key = _cache_key(period, start_date, end_date, channel, metric_type, exclude_channels, compare_start_date, compare_end_date)
    ex_str = json.dumps(exclude_channels, ensure_ascii=False) if exclude_channels else ""
    conn = get_connection()
    try:
        _ensure_db_cache_table(conn)
        conn.execute(
            f"INSERT OR REPLACE INTO {RFM_CACHE_TABLE} "
            f"(cache_key, period, start_date, end_date, channel, metric_type, ex_channels, result_json, computed_at) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            [key, period or "", start_date or "", end_date or "",
             channel or "", metric_type, ex_str, json.dumps(result, ensure_ascii=False, default=str)]
        )
    except Exception as e:
        logger.warning(f"RFM DuckDB 缓存写入失败: {e}")
    finally:
        conn.close()


def precompute_rfm_cache() -> int:
    """
    Plan P1: 预计算所有常用周期组合的 RFM 结果，存入 DuckDB 表。

    预计算范围：
      - 标准周期：Q1 / Q2 / Q3 / Q4 / YTD / MTD
      - 年份：2024 / 2025 / 2026
      - 渠道：全店
      - 指标：GSV / GMV
    共 6 周期 × 3 年 × 2 指标 = 36 个组合。

    ETL 完成后调用，自动跳过已计算的组合（INSERT OR REPLACE）。
    """
    from datetime import date, timedelta

    STANDARD_PERIODS = ["YTD", "MTD"]  # PeriodBuilder 支持的周期
    YEARS = [2024, 2025, 2026]
    METRIC_TYPES = ["GSV", "GMV"]
    # 目前仅预计算全店
    CHANNEL = None
    EXCLUDE = None

    logger.info(f"RFM 预计算开始: {len(STANDARD_PERIODS)} 周期 × {len(YEARS)} 年 × {len(METRIC_TYPES)} 指标 = "
                f"{len(STANDARD_PERIODS) * len(YEARS) * len(METRIC_TYPES)} 个组合")

    # PeriodBuilder.mtd(today=X) 的语义是"截至 X-1 天"，
    # 所以用 max_pay+1天 → MTD 包含到 max_pay 当天
    _today_conn = get_connection()
    try:
        max_pay_raw = _today_conn.execute("SELECT MAX(pay_time) FROM orders").fetchone()[0]
        if max_pay_raw is not None:
            max_pay_date = max_pay_raw.date() if hasattr(max_pay_raw, 'date') else max_pay_raw
            today = max_pay_date + timedelta(days=1)
        else:
            today = date.today() + timedelta(days=1)
        logger.info(f"  预计算参考日期(today): {today} (max_pay={max_pay_raw})")
    finally:
        _today_conn.close()

    conn = get_connection()
    computed = 0
    try:
        _ensure_db_cache_table(conn)

        for metric_type in METRIC_TYPES:
            for period in STANDARD_PERIODS:
                for year in YEARS:
                    try:
                        pb_func = getattr(
                            __import__("backend.semantic.time", fromlist=["PeriodBuilder"]).PeriodBuilder,
                            period.lower()
                        )
                        ranges = pb_func(today=today)
                        cur = ranges["current"]
                        comp = ranges["comparison"]
                        prev2 = ranges["prev2"]
                    except (AttributeError, KeyError):
                        continue

                    cur_start = f"{cur.start} 00:00:00"
                    cur_end = f"{cur.end} 23:59:59"
                    cur_cutoff = cur.cutoff
                    comp_start = f"{comp.start} 00:00:00"
                    comp_end = f"{comp.end} 23:59:59"
                    comp_cutoff = comp.cutoff
                    prev2_start = f"{prev2.start} 00:00:00"
                    prev2_end = f"{prev2.end} 23:59:59"
                    prev2_cutoff = prev2.cutoff

                    # 执行 3 个周期
                    c_all, c_same, c_memb_all, c_memb_same = _run_rfm_period(
                        conn, cur_start, cur_end, cur_cutoff, CHANNEL, metric_type, EXCLUDE
                    )
                    p_all, p_same, p_memb_all, p_memb_same = _run_rfm_period(
                        conn, comp_start, comp_end, comp_cutoff, CHANNEL, metric_type, EXCLUDE
                    )
                    p2_all, p2_same, p2_memb_all, p2_memb_same = _run_rfm_period(
                        conn, prev2_start, prev2_end, prev2_cutoff, CHANNEL, metric_type, EXCLUDE
                    )

                    rows = _build_rows(c_all, p_all, p2_all)
                    same_rows = _build_rows(c_same, p_same, p2_same)
                    memb_rows = _build_rows(c_memb_all, p_memb_all, p2_memb_all)
                    memb_same_rows = _build_rows(c_memb_same, p_memb_same, p2_memb_same)

                    result = {
                        "year_label": str(year),
                        "comp_year_label": str(year - 1),
                        "prev2_year_label": str(year - 2),
                        "metric_type": metric_type,
                        "rows": rows,
                        "same_channel_rows": same_rows,
                        "member_rows": memb_rows,
                        "member_same_channel_rows": memb_same_rows,
                    }

                    # 注意：前端始终传 start_date/end_date，不用 period 参数
                    # 缓存键必须基于实际日期范围，与前端请求完全一致
                    # 缓存键用实际日期，与前端请求格式完全一致
                    key = _cache_key(None, cur.start, cur.end, CHANNEL, metric_type, EXCLUDE)
                    ex_str = ""
                    conn.execute(
                        f"INSERT OR REPLACE INTO {RFM_CACHE_TABLE} "
                        f"(cache_key, period, start_date, end_date, channel, metric_type, ex_channels, result_json, computed_at) "
                        f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                        [key, period.upper(), cur.start, cur.end, CHANNEL or "", metric_type, ex_str,
                         json.dumps(result, ensure_ascii=False, default=str)]
                    )
                    computed += 1
                    logger.info(f"  RFM 预计算: {period} {year} {metric_type} → {key}")

    finally:
        conn.close()

    logger.info(f"RFM 预计算完成: {computed} / {len(STANDARD_PERIODS) * len(YEARS) * len(METRIC_TYPES)} 个组合")
    return computed
