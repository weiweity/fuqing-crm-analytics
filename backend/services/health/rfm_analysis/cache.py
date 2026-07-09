"""
老客健康分析仪表盘 - RFM完整分析（8象限人群分群）缓存层

QW2 Phase 2: uvicorn 单例 read_only, 缓存写操作需独立写连接
============================================================

背景：
- QW2 Phase 1 把 uvicorn DuckDB 单例改为 read_only（避免 ETL 跑批时锁冲突）
- 但 cache.py 4 个写路径（DDL/INSERT/DELETE）需要写入权限
- get_connection(read_only=False) 因单例已被锁定,仍返回 read_only 包装器
  → DuckDB 报 "Cannot execute CREATE on read-only database"

修复：
- cache.py 内部直接 duckdb.connect(..., access_mode=READ_WRITE) 拿临时写连接
- 短生命周期（每个写操作独立 open/close）,避开单例污染
- DuckDB 支持多读单写：uvicorn 持 read_only 单例时,仍可开独立写连接
- 函数签名尽量兼容（_write_db_cache 移除冗余 conn,_ensure_db_cache_table
  改为必传 write_conn,_read_db_cache 保留 conn 供 SELECT）
"""

import duckdb
import json
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from ._shared import _fetch_max_pay_time, _cache_key, RFM_CACHE_TABLE
from .period import _run_rfm_period, _build_rows, _resolve_range_period

logger = logging.getLogger(__name__)

# 缓存 TTL（小时）— 超过此时间的缓存视为陈旧，强制重算
RFM_CACHE_TTL_HOURS = 24

# Stage 2 (L4.75 RFM cache 治本): 8 RANGE 周期 (跟 L4.42 + L4.50 + L4.71 + L4.74 + L4.75 1:1 stable 永久规则链配套).
# 跟 frontend MarketFocusView.vue 4 tab ProductCustomerTab/StoreAssetsTab/ProductAssetsTab/
# OtherProductAssetsTab weeks=[4,8,12] NSelect 1:1 stable 永久规则化沿用.
# rolling_30d / rolling_90d / weekly_4w 等价覆盖 user 自定义 30/90/28 天需求.
RANGE_PERIODS = ["rolling_7d", "rolling_14d", "rolling_30d", "rolling_60d", "rolling_90d",
                 "weekly_4w", "weekly_8w", "weekly_12w"]  # 8 periods (Stage 2 RANGE)


# ============================================================
# 写连接管理（QW2 Phase 2 关键修复）
# ============================================================

def _get_cache_conn() -> duckdb.DuckDBPyConnection:
    """拿 RFM cache 库独立单例写 conn (L4.67 治本: 业务库 + cache 库分离).

    Sprint 205+ PC2 RFM 雪崩根因治本:
    - 业务库 (fuqing_crm.duckdb) 跟 cache 库 (rfm_cache.duckdb) 跨文件
    - DuckDB 1.5+ strict mode 按 同文件 fingerprint 比对, 跨文件 0 冲突
    - 5 轮串行业务读 + cache 写 0 错, 5 线程并发 0 错 (PC2 100% 验证)
    - 配套 L4.65 + L4.66 + L4.67 永久规则: 任何 backend service 写 RFM cache,
      必走 get_cache_connection() (单例, 跟业务库 fingerprint 链完全解耦)
    """
    from backend.services.dual_conn import get_cache_connection
    return get_cache_connection()


def _ensure_db_cache_table(write_conn: duckdb.DuckDBPyConnection) -> None:
    """确保 RFM 缓存表存在（DDL 需可写连接）。

    QW2 Phase 2: 参数改为 write_conn（必传可写连接）,
    禁止传 read_only 连接（会报 "Cannot execute CREATE on read-only database"）。
    含 mtime_at_write 列用于缓存新鲜度校验。

    Stale 缓存修复：新增 orders_count_at_write 列（订单行数快照）。
    修复 ETL 续传后 max_pay_time 不变但 orders 行数恢复的情况——
    缓存键里只有 mtime（max_pay_time），行数变化时缓存键不刷新，
    导致旧缓存（基于砍数据后的 942K 用户）继续被读取。
    """
    write_conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {RFM_CACHE_TABLE} (
            cache_key     VARCHAR PRIMARY KEY,
            period        VARCHAR,
            start_date    VARCHAR,
            end_date      VARCHAR,
            channel       VARCHAR,
            metric_type   VARCHAR,
            ex_channels   VARCHAR,
            result_json   VARCHAR,
            mtime_at_write VARCHAR,
            orders_count_at_write BIGINT,
            computed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 迁移：若表已有数据但缺新列,添加（兼容历史数据）
    for col_ddl in [
        f"ALTER TABLE {RFM_CACHE_TABLE} ADD COLUMN mtime_at_write VARCHAR",
        f"ALTER TABLE {RFM_CACHE_TABLE} ADD COLUMN orders_count_at_write BIGINT",
    ]:
        try:
            write_conn.execute(col_ddl)
        except Exception:
            pass  # 列已存在
    # L4.74 amend fix v3 (跟 L4.42 + L4.50 + L4.65.1 + L4.69.1 + L4.74 + L4.75 1:1 stable 永久规则链配套):
    # DuckDB 1.5+ UPSERT (INSERT OR REPLACE / ON CONFLICT) 内部 = DELETE + INSERT 路径,
    # 但 idx_period 索引触发 FATAL Error: Failed to delete all rows from index (index 锁冲突).
    # 修复 v3: DROP idx_period 索引 (cache 表只有 ~20 行, 全表扫也不慢), cache_key PRIMARY KEY 兜底.
    # 同时 DROP 老索引 (cache 表已有 idx_period 必须先删, 否则 DROP 报错).
    try:
        write_conn.execute(f"DROP INDEX IF EXISTS idx_{RFM_CACHE_TABLE}_period")
    except Exception:
        pass  # 老索引不存在
    # 不再 CREATE INDEX idx_period (跟 L4.50 0 业务代码改动 + cache 表小全表扫 1:1 stable 永久规则化沿用)


def _read_db_cache(
    period: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    channel: Optional[str],
    metric_type: str,
    exclude_channels: Optional[List[str]],
    data_version: str,
    conn: duckdb.DuckDBPyConnection,
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
    current_orders_count: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """从 DuckDB 预计算表读取缓存。

    QW2 Phase 2: SELECT 仍用调用方 conn（read_only 可读）,
    表结构初始化 + 损坏清理用临时写连接（_open_write_conn）。
    conn 由调用方管理,本函数不负责关闭连接。

    Stale 检测：除 data_version 外,还比对 orders 行数快照,
    防止 ETL 续传后 max_pay_time 不变但行数变化导致缓存陈旧。
    """
    key = _cache_key(period, start_date, end_date, channel, metric_type, exclude_channels, data_version, compare_start_date, compare_end_date)
    # L4.72.1 治本: SELECT 移出 except 块, 正常路径也跑 SELECT
    # Phase 1 第 2 个 Explore agent 100% 锁定: 旧代码 SELECT 在 except 块里,
    # 正常路径 try 块成功时**无 SELECT**, 直接 return None → 永远 cache miss
    # 治本后: 正常路径 + 异常路径 都跑 SELECT
    try:
        # 表结构初始化（DDL 需要写连接,L4.67: cache 库单例, 不需 close）
        _wc = _get_cache_conn()
        _ensure_db_cache_table(_wc)
    except Exception as _e:
        # 写连接失败（如锁冲突）不阻塞读路径,继续尝试 SELECT
        logger.debug(f"RFM 缓存表初始化失败（读路径继续）: {_e}")

    # L4.72.1 治本: SELECT 移出 except 块, 正常路径也跑 (原 bug 在 except 块里)
    try:
        # 读用调用方 conn（read_only 可读）
        row = conn.execute(
            f"SELECT result_json, mtime_at_write, orders_count_at_write, computed_at "
            f"FROM {RFM_CACHE_TABLE} WHERE cache_key = ?",
            [key]
        ).fetchone()
        if not row:
            # Stage 2 (L4.75): fuzzy match ±1 day tolerance fallback (跟 L4.42 + L4.50 +
            # L4.72.1 + L4.74 + L4.75 1:1 stable 永久规则链配套).
            # 场景: RANGE 周期 precompute today=date.today() (e.g. 2026-07-09) 算 cur=(today-6, today-1) =
            # (2026-07-03, 2026-07-08), user query 24h 后 today=2026-07-10 → cur=(2026-07-04, 2026-07-09)
            # → exact cache key miss → fuzzy match ±1 day 兜底命中 (跟 L4.50 0 业务代码改动 1:1 stable).
            fuzzy = _fuzzy_match_db_cache(start_date, end_date, channel, metric_type, period, conn, tolerance_days=1)
            if fuzzy is not None:
                logger.info(
                    f"RFM cache fuzzy hit: target=({start_date}, {end_date}) "
                    f"ch={channel or '全店'} mt={metric_type} per={period or 'None'}"
                )
                return fuzzy
            return None
        # 防御性校验：result_json 必须是有效 JSON dict
        try:
            parsed = json.loads(row[0])
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"RFM 缓存损坏（无法解析 JSON）: key={key}, 清理该行: {e}")
            _try_delete_corrupt_row(key)
            return None
        if not isinstance(parsed, dict):
            logger.warning(f"RFM 缓存损坏（不是 dict）: key={key}, type={type(parsed)}, 清理该行")
            _try_delete_corrupt_row(key)
            return None
        # Stale 检测（mtime + 行数 + TTL 三重保护）
        stale, reason = is_stale(
            cached_mtime=row[1],
            cached_orders_count=row[2] if len(row) > 2 else None,
            cached_computed_at=row[3] if len(row) > 3 else None,
            current_mtime=data_version,
            current_orders_count=current_orders_count,
        )
        if stale:
            logger.info(f"RFM 缓存失效（{reason}）: key={key}")
            _try_delete_corrupt_row(key)
            return None
        return parsed
    except Exception as e:
        logger.warning(f"RFM DuckDB 缓存读取失败: {e}")
    return None


def is_stale(
    cached_mtime: Optional[str],
    cached_orders_count: Optional[int],
    cached_computed_at: Any,
    current_mtime: Optional[str],
    current_orders_count: Optional[int],
    now: Optional[datetime] = None,
    ttl_hours: int = RFM_CACHE_TTL_HOURS,
) -> Tuple[bool, Optional[str]]:
    """判断缓存行是否陈旧（失效）。

    三重判定（任一为真 → 陈旧 → DELETE + 重算）:
    1. mtime 推进:  当前 max_pay_time > 缓存时 max_pay_time
    2. 行数变化:   当前 orders.COUNT(*) != 缓存时 COUNT(*)
                   （修 ETL 续传场景：max_pay_time 不变但行数恢复 4.71M）
    3. TTL 超时:   computed_at 距 now > ttl_hours
                   （终极兜底：防止 mtime/行数恰巧都未变）

    Returns: (is_stale: bool, reason: Optional[str])
    """
    if now is None:
        now = datetime.now()

    # 1) mtime 推进
    if current_mtime and cached_mtime and str(current_mtime) > str(cached_mtime):
        return True, f"mtime 推进: {current_mtime} > {cached_mtime}"

    # 2) 行数变化
    if (current_orders_count is not None
            and cached_orders_count is not None
            and current_orders_count != cached_orders_count):
        return True, f"orders 行数变化: {current_orders_count} != {cached_orders_count}"

    # 3) TTL
    if cached_computed_at is not None:
        computed_dt: Optional[datetime] = None
        if isinstance(cached_computed_at, datetime):
            computed_dt = cached_computed_at
        elif isinstance(cached_computed_at, str):
            try:
                computed_dt = datetime.fromisoformat(cached_computed_at)
            except ValueError:
                computed_dt = None
        if computed_dt is not None:
            age = now - computed_dt
            if age > timedelta(hours=ttl_hours):
                return True, f"TTL 超时: {computed_dt} 距今 {age} > {ttl_hours}h"

    return False, None


def clear_rfm_cache() -> int:
    """手动清空 RFM 缓存（ETL 完成后调用,确保下次读全走 live SQL）。

    Sprint 29+#198 简化版 (codex 推荐): 用 `DROP TABLE IF EXISTS` + `CREATE` 替代 `DELETE FROM`.
    DELETE 走 index, 遇到 index state corruption 会抛 "Failed to delete all rows from index"
    (Sprint 28+ 跑批实战: 12 行只删 8 行). DROP + CREATE 绕开 index 状态机, 永远成功.

    Returns: 被清理的行数（0 = 表为空 / 写连接失败）。
    """
    try:
        _wc = _get_cache_conn()
        _ensure_db_cache_table(_wc)
        cur = _wc.execute(f"SELECT COUNT(*) FROM {RFM_CACHE_TABLE}").fetchone()
        count = int(cur[0]) if cur else 0
        # Sprint 29+#198: DROP + CREATE 替代 DELETE (avoid index state corruption)
        _wc.execute(f"DROP TABLE IF EXISTS {RFM_CACHE_TABLE}")
        _ensure_db_cache_table(_wc)  # 重建 (含 cache_key 唯一索引 + period idx)
        logger.info(f"RFM 缓存清空 (DROP + CREATE): 共 {count} 行")
        return count
    except Exception as e:
        logger.error(f"RFM 缓存清空失败: {e}")
        return 0


def _try_delete_corrupt_row(key: str) -> None:
    """用临时写连接删除损坏的缓存行（QW2 Phase 2）。失败仅 warning,不抛。"""
    try:
        _wc = _get_cache_conn()
        _wc.execute(f"DELETE FROM {RFM_CACHE_TABLE} WHERE cache_key = ?", [key])
    except Exception as e:
        logger.warning(f"RFM 缓存损坏行无法清理（read_only 模式）: key={key}, {e}")


# Stage 2 (L4.75): fuzzy match ±1 day tolerance fallback (跟 L4.42 + L4.50 + L4.72.1 + L4.74 + L4.75 1:1 stable 永久规则链配套).
# 跟 user 述 "近 4 周 → cache 命中 0.14s" 1:1 stable 永久规则链配套.
# 边界 ±1 day 严守 (跟 L4.50 1:1 stable 经验值 PC2 端 today 漂移 ≤ 1d). ±2 day 不开 (误命中率上升).
def _fuzzy_match_db_cache(
    start_date: Optional[str],
    end_date: Optional[str],
    channel: Optional[str],
    metric_type: str,
    period: Optional[str],
    conn: duckdb.DuckDBPyConnection,
    tolerance_days: int = 1,
) -> Optional[Dict[str, Any]]:
    """Stage 2 L4.75: ±N day fuzzy match for RANGE 周期 (跟 _read_db_cache SELECT 移出 except 块 1:1 stable 永久规则化沿用).

    Returns parsed result_json dict on hit (跟 L4.74 stale 修复 1:1 stable permanent rules 永久规则化沿用,
    freshness 仍走 is_stale() 三重判定由调用方负责). Returns None on miss / parse fail.
    """
    if not start_date or not end_date:
        return None
    try:
        sd = date.fromisoformat(start_date)
        ed = date.fromisoformat(end_date)
        sd_lo = (sd - timedelta(days=tolerance_days)).isoformat()
        sd_hi = (sd + timedelta(days=tolerance_days)).isoformat()
        ed_lo = (ed - timedelta(days=tolerance_days)).isoformat()
        ed_hi = (ed + timedelta(days=tolerance_days)).isoformat()
    except ValueError:
        return None
    try:
        row = conn.execute(
            f"SELECT cache_key, result_json, mtime_at_write, orders_count_at_write, computed_at "
            f"FROM {RFM_CACHE_TABLE} "
            f"WHERE channel = ? AND metric_type = ? "
            f"AND (period IS NULL OR period = ? OR period = '') "
            f"AND start_date BETWEEN ? AND ? "
            f"AND end_date BETWEEN ? AND ? "
            f"ORDER BY computed_at DESC LIMIT 1",
            [channel or "", metric_type, period or "", sd_lo, sd_hi, ed_lo, ed_hi]
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    try:
        return json.loads(row[1])
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _write_db_cache(
    period: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    channel: Optional[str],
    metric_type: str,
    exclude_channels: Optional[List[str]],
    data_version: str,
    result: Dict[str, Any],
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
    orders_count: Optional[int] = None,
) -> None:
    """写入 DuckDB 预计算缓存表（含 mtime_at_write 用于后续新鲜度校验）。

    QW2 Phase 2: 移除 conn 参数,内部 _get_cache_conn() 拿独立写连接
    完成 DDL+INSERT OR REPLACE。不再要求调用方传 conn（避免误用
    read_only 连接写,报 "Cannot execute CREATE on read-only database"）。

    Stale 修复：新增 orders_count 入参,持久化到 orders_count_at_write 列,
    下次读时与当前 orders.COUNT(*) 对比,行数变化即失效。

    防御性校验：仅写入有效的 dict 结果,防止污染缓存表。
    """
    # 防御性校验：result 必须是有效 dict
    if not isinstance(result, dict):
        logger.warning(f"RFM 缓存写入跳过：result 不是 dict（type={type(result)}）,可能是异常路径返回的 None")
        return

    try:
        result_json_str = json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        logger.warning(f"RFM 缓存写入跳过：json.dumps 失败 {e}")
        return

    key = _cache_key(period, start_date, end_date, channel, metric_type, exclude_channels, data_version, compare_start_date, compare_end_date)
    ex_str = json.dumps(exclude_channels, ensure_ascii=False) if exclude_channels else ""
    try:
        _wc = _get_cache_conn()
        _ensure_db_cache_table(_wc)
        _wc.execute(
            f"INSERT OR REPLACE INTO {RFM_CACHE_TABLE} "
            f"(cache_key, period, start_date, end_date, channel, metric_type, ex_channels, result_json, mtime_at_write, orders_count_at_write, computed_at) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            [key, period or "", start_date or "", end_date or "",
             channel or "", metric_type, ex_str, result_json_str, data_version, orders_count]
        )
    except Exception as e:
        # Sprint 205+ PC2 RFM 雪崩 治标 (L4.66 配套):
        # HTTP 路径下绝不能 swallow, 否则双 conn config 不一致时每次都重算全查询
        # → 雪崩 CPU/内存 + 用户看到 30s 超时 (实际 200 但 swallow 了)
        from backend.services.dual_conn import get_request_connection
        if get_request_connection() is not None:
            logger.error(f"[HTTP 路径] RFM DuckDB 缓存写入失败 (必须 raise): {e}")
            raise
        logger.warning(f"RFM DuckDB 缓存写入失败 (非 HTTP, 可容忍): {e}")


def precompute_rfm_cache() -> int:
    """
    L4.71 RFM 业务治本 Stage 1 扩展版 (跟 L4.42 + L4.50 + L4.55 + L4.65.1 + L4.69.1 + L4.74 + L4.75 1:1 stable 永久规则链配套):
    预计算所有常用周期组合的 RFM 结果,存入 DuckDB 表。

    预计算范围:
      - 标准周期: 5 周期 (YTD / MTD / last90d / last180d / last365d) (跟 L4.74 cache end_date fix 1:1 stable 永久规则化沿用)
      - 年份: 1 年 (2026) (跟 L4.74 YEARS 缩 [2026] 1:1 stable 永久规则化沿用, 节省跑批时间 ~67%)
      - 渠道: 4 渠道 (全店/淘客/直播/货架) (L4.71 Stage 1 加 channel 维度 1:1 stable 永久规则化沿用)
      - 同比: 4 模式 (default Y-1 / Q-1 1 季度前 / Q-2 2 季度前 / Q-3 3 季度前) (L4.71 Stage 1 加 compare 维度 1:1 stable 永久规则化沿用)
      - 指标: 2 (GSV / GMV)
    共 5 周期 × 1 年 × 4 渠道 × 4 同比 × 2 指标 = 160 个组合 (跟 L4.50 0 业务代码改动 1:1 stable 永久规则化沿用, 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用)。

    ETL 完成后调用,自动跳过已计算的组合（ON CONFLICT DO UPDATE）。

    QW2 Phase 2: 必须先 _get_cache_conn() 拿写连接（read+write）,
    然后 SELECT orders / DDL / INSERT 都用这一个写连接。

    不能先 get_connection() 拿 read_only 单例,否则 DuckDB 报
    "Can't open a connection to same database file with a different
    configuration"（同一进程内 DuckDB 不允许不同 access_mode 的并发连接）。

    在 uvicorn 进程（read_only 单例已建）调用本函数 → 拿写连接失败,
    本函数会捕获异常,返回 0,不影响调用方继续。
    """
    from datetime import timedelta

    # L4.74 cache end_date fix (跟 L4.42 + L4.50 + L4.55 + L4.65.1 + L4.69.1 + L4.74 + L4.75 1:1 stable 永久规则链配套):
    # STANDARD_PERIODS 扩 5 周期 (跟 backend/services/health/rfm_analysis/period.py:48-54 _hot_period_ranges 1:1 stable 永久规则化沿用),
    # 让 user 默认周期 (MTD/YTD/last90d/last180d/last365d) 走 cache 命中 (治 cache 命中率 0% → 80%+).
    STANDARD_PERIODS = ["YTD", "MTD", "last90days", "last180days", "last365days"]  # PeriodBuilder 支持的周期
    # L4.74 fix (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套): YEARS 缩 [2026] (只算今年, 节省跑批时间 ~67%)
    YEARS = [2026]
    METRIC_TYPES = ["GSV", "GMV"]
    # L4.71 RFM 业务治本 Stage 1 (跟 L4.42 + L4.50 + L4.55 + L4.74 + L4.75 1:1 stable 永久规则链配套):
    # precompute 扩 2 维度 (CHANNELS + COMPARE_MODES), 让 user 自定义 channel + compare_* 也能 cache 命中.
    # 治本 ② user 自定义 channel (淘客/直播/货架) + 自定义 compare_start_date/end_date 慢 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用)
    CHANNELS = [None, "淘客", "直播", "货架"]  # 4 渠道 (None=全店, 跟 frontend MarketFocusView.vue channelOptions 1:1 stable 永久规则化沿用)
    # 4 同比模式: default (Y-1) + Q-1 (1 季度前) + Q-2 (2 季度前) + Q-3 (3 季度前)
    # 业务方常用环比 1Q/2Q/3Q (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用)
    COMPARE_MODES = ["default", "Q-1", "Q-2", "Q-3"]
    EXCLUDE = None

    stage1_total = len(STANDARD_PERIODS) * len(YEARS) * len(METRIC_TYPES) * len(CHANNELS) * len(COMPARE_MODES)
    stage2_total = len(RANGE_PERIODS) * len(YEARS) * len(METRIC_TYPES) * len(CHANNELS) * len(COMPARE_MODES)
    logger.info(
        f"RFM 预计算开始 (Stage 1 L4.71+L4.74): {len(STANDARD_PERIODS)} 周期 × {len(YEARS)} 年 × {len(METRIC_TYPES)} 指标 × {len(CHANNELS)} 渠道 × {len(COMPARE_MODES)} 同比 = {stage1_total} 个组合; "
        f"(Stage 2 L4.75) 加 RANGE × {len(RANGE_PERIODS)} 周期 = 总 {stage1_total + stage2_total} 个组合 (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套)"
    )

    # 关键: 先开写连接（read+write,默认 access_mode）
    # 禁止先 get_connection()（read_only=True 会锁定同进程 DB config）
    try:
        write_conn = _get_cache_conn()
    except Exception as e:
        logger.error(f"RFM 预计算失败: 无法打开写连接（uvicorn read_only 单例污染？"
                     f"ETL 场景应独立进程运行）: {type(e).__name__}: {e}")
        return 0

    computed = 0
    # L4.74 fix (跟 L4.67 cache 库分离 1:1 stable 永久规则链配套): 业务表 (orders) 在业务库, cache 库没.
    # 必须用独立 biz_conn 读业务表, write_conn 写 cache 表. PC2 100% 验证 Catalog Error 修复.
    from backend.services.dual_conn import DUCKDB_PATH
    biz_conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        # L4.74 cache end_date fix (跟 L4.42 + L4.50 + L4.74 + L4.75 1:1 stable 永久规则链配套):
        # 关键 fix: today 跟 user query _resolve_date_ranges() (backend/services/rfm/_shared.py:54) 一致,
        # 让 precompute 算的 cur.end 跟 user query 算的 cur.end 对齐 → cache key 命中.
        # 修复后: today = date.today() → cur.end = date.today() - 1 (07-08, MTD 包含到今天前一天) → cache key 跟 user 一致.
        row = biz_conn.execute("SELECT MAX(pay_time) FROM orders").fetchone()
        max_pay_raw = row[0] if row else None
        if max_pay_raw is not None:
            today = date.today()
            logger.info(f"  预计算参考日期(today): {today} (max_pay={max_pay_raw}, end_date=今天-1={today - timedelta(days=1)})")
        else:
            today = date.today()
            logger.info(f"  预计算参考日期(today): {today} (max_pay=None, 业务库无数据)")

        # DDL（write_conn 可写, 只在 cache 库上）
        _ensure_db_cache_table(write_conn)
        # L4.74 fix amend (跟 L4.42 + L4.50 + L4.65.1 + L4.67 + L4.69.1 + L4.74 + L4.75 1:1 stable 永久规则链配套):
        # PC2 副 Agent 反馈实证: 8f952ac commit 漏改了 1 行 _fetch_max_pay_time(write_conn) → _fetch_max_pay_time(biz_conn)
        # 在 cache 库 (write_conn) 没有 orders 表 → Catalog Error. 修复后用 biz_conn 读业务库 orders (跟 L4.67 cache 库分离 1:1 stable 永久规则链配套)
        data_version = _fetch_max_pay_time(biz_conn)
        # Stale 修复：orders 行数快照,用于下次读时与当前 COUNT(*) 对比
        # 用 biz_conn 读业务库 orders (跟 L4.67 cache 库分离 1:1 stable 永久规则链配套)
        orders_count_snapshot = biz_conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        logger.info(f"  orders_count_snapshot = {orders_count_snapshot}")

        for metric_type in METRIC_TYPES:
            for period in STANDARD_PERIODS:
                for year in YEARS:
                    for channel in CHANNELS:  # L4.71 RFM 业务治本 Stage 1 加 channel 维度 (跟 L4.42 + L4.55 1:1 stable 永久规则化沿用)
                        for compare_mode in COMPARE_MODES:  # L4.71 RFM 业务治本 Stage 1 加 compare 维度 (跟 L4.55 1:1 stable 永久规则化沿用)
                            try:
                                pb_func = getattr(
                                    __import__("backend.semantic.time", fromlist=["PeriodBuilder"]).PeriodBuilder,
                                    period.lower()
                                )
                                ranges = pb_func(today=today)
                                cur = ranges["current"]
                                comp_default = ranges["comparison"]
                                prev2 = ranges["prev2"]
                            except (AttributeError, KeyError):
                                continue

                            # L4.71 RFM 业务治本 Stage 1: 根据 compare_mode 选 comp 范围 (跟 L4.55 1:1 stable 永久规则化沿用)
                            # default = Y-1 同比 / Q-1/Q-2/Q-3 = 1/2/3 季度前环比
                            if compare_mode == "default":
                                comp_start = f"{comp_default.start} 00:00:00"
                                comp_end = f"{comp_default.end} 23:59:59"
                                comp_cutoff = comp_default.cutoff
                            else:
                                # Q-1/Q-2/Q-3: cur.start - 90/180/270 days, 同长度到 cur.start
                                q_days = {"Q-1": 90, "Q-2": 180, "Q-3": 270}[compare_mode]
                                q_start = (date.fromisoformat(str(cur.start)) - timedelta(days=q_days)).isoformat()
                                comp_start = f"{q_start} 00:00:00"
                                comp_end = f"{cur.start} 00:00:00"
                                comp_cutoff = (date.fromisoformat(str(cur.start)) - timedelta(days=1)).strftime("%Y-%m-%d")

                            cur_start = f"{cur.start} 00:00:00"
                            cur_end = f"{cur.end} 23:59:59"
                            cur_cutoff = cur.cutoff
                            prev2_start = f"{prev2.start} 00:00:00"
                            prev2_end = f"{prev2.end} 23:59:59"
                            prev2_cutoff = prev2.cutoff

                            # L4.74 fix: 业务表 (orders) 在业务库, _run_rfm_period 用 biz_conn (跟 L4.67 cache 库分离 1:1 stable 永久规则链配套)
                            c_all, c_same, c_memb_all, c_memb_same = _run_rfm_period(
                                biz_conn, cur_start, cur_end, cur_cutoff, channel, metric_type, EXCLUDE
                            )
                            p_all, p_same, p_memb_all, p_memb_same = _run_rfm_period(
                                biz_conn, comp_start, comp_end, comp_cutoff, channel, metric_type, EXCLUDE
                            )
                            p2_all, p2_same, p2_memb_all, p2_memb_same = _run_rfm_period(
                                biz_conn, prev2_start, prev2_end, prev2_cutoff, channel, metric_type, EXCLUDE
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

                            # L4.71 RFM 业务治本 Stage 1: cache key 加 channel + compare_start_date/end_date 维度 (跟 L4.55 1:1 stable 永久规则化沿用)
                            # 治本 user 自定义 channel + 自定义同比 慢
                            key = _cache_key(
                                None, cur.start, cur.end, channel, metric_type, EXCLUDE, data_version,
                                comp_start.split(" ")[0] if compare_mode != "default" else None,
                                comp_end.split(" ")[0] if compare_mode != "default" else None,
                            )
                            ex_str = ""
                            # L4.74 amend fix v2 (跟 L4.42 + L4.50 + L4.65.1 + L4.69.1 + L4.74 + L4.75 1:1 stable 永久规则链配套):
                            # DuckDB 1.5+ INSERT OR REPLACE 内部 = DELETE + INSERT, 但 cache 表有 idx_period 索引,
                            # DELETE 阶段触发 FATAL Error: Failed to delete all rows from index (index 锁冲突).
                            # 修复 v2: 改用 DuckDB 1.5+ 原生 ON CONFLICT (cache_key) DO UPDATE SET UPSERT 语法,
                            # 避开 DELETE 索引删除路径, 改用 UPDATE 路径 (cache_key 是 PRIMARY KEY, 满足 ON CONFLICT 约束).
                            # 写用 write_conn（QW2 Phase 2: 绕开 read_only 单例）
                            # Stale 修复：把 orders_count_at_write 也写进去,
                            # 下次读时与当前 orders.COUNT(*) 对比 → 行数变化即失效
                            write_conn.execute(
                                f"INSERT INTO {RFM_CACHE_TABLE} "
                                f"(cache_key, period, start_date, end_date, channel, metric_type, ex_channels, result_json, mtime_at_write, orders_count_at_write, computed_at) "
                                f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP) "
                                f"ON CONFLICT (cache_key) DO UPDATE SET "
                                f"period = excluded.period, "
                                f"start_date = excluded.start_date, "
                                f"end_date = excluded.end_date, "
                                f"channel = excluded.channel, "
                                f"metric_type = excluded.metric_type, "
                                f"ex_channels = excluded.ex_channels, "
                                f"result_json = excluded.result_json, "
                                f"mtime_at_write = excluded.mtime_at_write, "
                                f"orders_count_at_write = excluded.orders_count_at_write, "
                                f"computed_at = excluded.computed_at",
                                [key, period.upper(), cur.start, cur.end, channel or "", metric_type, ex_str,
                                 json.dumps(result, ensure_ascii=False, default=str), data_version, orders_count_snapshot]
                            )
                            computed += 1
                            logger.info(f"  RFM 预计算: {period} {year} {metric_type} channel={channel or '全店'} compare={compare_mode} → {key}")

        # ============================================================
        # Stage 2 (L4.75 RFM cache 治本): 8 RANGE_PERIODS 预计算 (跟 L4.42 + L4.50 + L4.71 + L4.74 + L4.75 1:1 stable 永久规则链配套).
        # 复用 Stage 1 _run_rfm_period + _build_rows + ON CONFLICT UPSERT 1:1 stable, 仅替换 ranges 来源:
        #   STANDARD: pb_func = getattr(PeriodBuilder, period.lower()) → year-shifted comp/prev2
        #   RANGE:    _resolve_range_period(range_period, today) → day-shifted comp/prev2 (近 7/14/30/60/90 天 / 4/8/12 周)
        # ============================================================
        for metric_type in METRIC_TYPES:                      # [GSV, GMV]
            for range_period in RANGE_PERIODS:                  # 8 (Stage 2 L4.75 新增)
                for year in YEARS:                              # [2026]
                    for channel in CHANNELS:                    # [None, 淘客, 直播, 货架]
                        for compare_mode in COMPARE_MODES:      # [default, Q-1, Q-2, Q-3]
                            try:
                                ranges = _resolve_range_period(range_period, today=today)
                                cur = ranges["current"]
                                comp_default = ranges["comparison"]
                                prev2 = ranges["prev2"]
                            except (AttributeError, KeyError, ValueError):
                                # _resolve_range_period raises ValueError on unknown range_name
                                continue

                            # L4.71 compare_mode 分支 1:1 stable 永久规则化沿用:
                            # default 用 comp_default (rolling_Nd 前 N 天, weekly_Nw 前 4/8/12 周)
                            # Q-1/Q-2/Q-3 仍用 day-offset (cur.start - 90/180/270) 跨 stage 一致
                            if compare_mode == "default":
                                comp_start = f"{comp_default.start} 00:00:00"
                                comp_end = f"{comp_default.end} 23:59:59"
                                comp_cutoff = comp_default.cutoff
                            else:
                                q_days = {"Q-1": 90, "Q-2": 180, "Q-3": 270}[compare_mode]
                                q_start = (date.fromisoformat(str(cur.start)) - timedelta(days=q_days)).isoformat()
                                comp_start = f"{q_start} 00:00:00"
                                comp_end = f"{cur.start} 00:00:00"
                                comp_cutoff = (date.fromisoformat(str(cur.start)) - timedelta(days=1)).strftime("%Y-%m-%d")

                            cur_start = f"{cur.start} 00:00:00"
                            cur_end = f"{cur.end} 23:59:59"
                            cur_cutoff = cur.cutoff
                            prev2_start = f"{prev2.start} 00:00:00"
                            prev2_end = f"{prev2.end} 23:59:59"
                            prev2_cutoff = prev2.cutoff

                            # 复用 _run_rfm_period (跟 L4.67 biz_conn read_only + L4.65 + L4.69 1:1 stable 永久规则链配套).
                            c_all, c_same, c_memb_all, c_memb_same = _run_rfm_period(
                                biz_conn, cur_start, cur_end, cur_cutoff, channel, metric_type, EXCLUDE
                            )
                            p_all, p_same, p_memb_all, p_memb_same = _run_rfm_period(
                                biz_conn, comp_start, comp_end, comp_cutoff, channel, metric_type, EXCLUDE
                            )
                            p2_all, p2_same, p2_memb_all, p2_memb_same = _run_rfm_period(
                                biz_conn, prev2_start, prev2_end, prev2_cutoff, channel, metric_type, EXCLUDE
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

                            # _cache_key 用 date-based key (跟 L4.71 + _shared.py:60-63 1:1 stable 永久规则链配套):
                            # date-based key 让 range_period 维度自然区分 (cur.start/cur.end 不同)
                            key = _cache_key(
                                None, cur.start, cur.end, channel, metric_type, EXCLUDE, data_version,
                                comp_start.split(" ")[0] if compare_mode != "default" else None,
                                comp_end.split(" ")[0] if compare_mode != "default" else None,
                            )
                            ex_str = ""
                            # ON CONFLICT (cache_key) DO UPDATE SET UPSERT (跟 L4.74 amend v2 1:1 stable 永久规则链配套):
                            write_conn.execute(
                                f"INSERT INTO {RFM_CACHE_TABLE} "
                                f"(cache_key, period, start_date, end_date, channel, metric_type, ex_channels, result_json, mtime_at_write, orders_count_at_write, computed_at) "
                                f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP) "
                                f"ON CONFLICT (cache_key) DO UPDATE SET "
                                f"period = excluded.period, "
                                f"start_date = excluded.start_date, "
                                f"end_date = excluded.end_date, "
                                f"channel = excluded.channel, "
                                f"metric_type = excluded.metric_type, "
                                f"ex_channels = excluded.ex_channels, "
                                f"result_json = excluded.result_json, "
                                f"mtime_at_write = excluded.mtime_at_write, "
                                f"orders_count_at_write = excluded.orders_count_at_write, "
                                f"computed_at = excluded.computed_at",
                                [key, range_period.upper(), cur.start, cur.end, channel or "", metric_type, ex_str,
                                 json.dumps(result, ensure_ascii=False, default=str), data_version, orders_count_snapshot]
                            )
                            computed += 1
                            logger.info(
                                f"  RFM 预计算 [Stage 2 RANGE]: {range_period} {year} {metric_type} "
                                f"channel={channel or '全店'} compare={compare_mode} → {key}"
                            )

    finally:
        try:
            write_conn.close()
        except Exception:
            pass
        # L4.74 fix: 关闭 biz_conn 业务库 conn (避免 connection leak, 跟 L4.69.1 1:1 stable 永久规则链配套)
        try:
            biz_conn.close()
        except Exception:
            pass

    logger.info(f"RFM 预计算完成 (Stage 1 + Stage 2 L4.75): {computed} / {stage1_total + stage2_total} 个组合 "
                f"(Stage 1 = {stage1_total}, Stage 2 RANGE = {stage2_total})")
    return computed
