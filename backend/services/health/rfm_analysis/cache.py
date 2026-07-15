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
import threading
from uuid import uuid4
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from backend.semantic.time import PeriodBuilder
from backend.services.rfm._shared import _resolve_date_ranges

from ._shared import _fetch_max_pay_time, _cache_key, RFM_CACHE_TABLE
from .period import (
    _build_rows,
    _hot_period_ranges,
    _resolve_range_period,
    _run_rfm_period,
)

logger = logging.getLogger(__name__)
_CACHE_OPERATION_LOCK = threading.RLock()

# 缓存 TTL（小时）— 超过此时间的缓存视为陈旧，强制重算
RFM_CACHE_TTL_HOURS = 24
RFM_CACHE_RETENTION_HOURS = 48
RFM_CACHE_FUZZY_TOLERANCE_DAYS = 2
RFM_CACHE_GENERATION_TABLE = "rfm_cache_generation"
RFM_CACHE_GENERATION_ROWS_TABLE = "rfm_analysis_cache_generation_rows"


class RFMCacheUnavailableError(RuntimeError):
    """RFM cache 基础设施不可用；HTTP 层应快速返回 503，禁止回退重查询。"""


class RFMCacheMissError(RFMCacheUnavailableError):
    """HTTP 请求组合尚未预热；必须 503，禁止同步执行三段 live RFM。"""


# Stage 2 (L4.75 RFM cache 治本): 8 个业务别名周期。
# 跟 frontend MarketFocusView.vue 4 tab ProductCustomerTab/StoreAssetsTab/ProductAssetsTab/
# OtherProductAssetsTab weeks=[4,8,12] NSelect 1:1 stable 永久规则化沿用.
# date-based cache key 会把同日期窗口（例如 last90days/rolling_90d，或某天的
# MTD/rolling_Nd）折叠为同一个物理 key；预计算会先按 HTTP SSOT 统一口径，再去重。
RANGE_PERIODS = ["rolling_7d", "rolling_14d", "rolling_30d", "rolling_60d", "rolling_90d",
                 "weekly_4w", "weekly_8w", "weekly_12w"]

STANDARD_PERIODS = [
    "yesterday",
    "WTD",
    "MTD",
    "YTD",
    "Q1",
    "Q2",
    "Q3",
    "Q4",
    "last90days",
    "last180days",
    "last365days",
]
PRECOMPUTE_CHANNELS = [None, "货架", "达播", "直播", "淘客"]
COMPARE_MODES = ["default", "auto_mom"]
EXPECTED_LOGICAL_PRECOMPUTE_COMBINATIONS = (
    (len(STANDARD_PERIODS) + len(RANGE_PERIODS))
    * 2
    * len(PRECOMPUTE_CHANNELS)
    * len(COMPARE_MODES)
)


def _resolve_precompute_query_ranges(
    current_start: str,
    current_end: str,
    compare_mode: str,
) -> Tuple[Dict[str, Any], Optional[str], Optional[str]]:
    """按真实 HTTP 参数语义解析预计算的 current/comp/prev2。

    默认请求不传 compare dates，走 YOY；``auto_mom`` 使用前端实际发送的紧邻
    等长前期。两种模式都交给 ``_resolve_date_ranges``，避免预计算与在线请求的
    end-of-day、cutoff、prev2 口径漂移。
    """
    compare_start_date = None
    compare_end_date = None
    if compare_mode == "auto_mom":
        comparison = PeriodBuilder.mom(current_start, current_end)
        compare_start_date = comparison.start
        compare_end_date = comparison.end
    elif compare_mode != "default":
        raise ValueError(f"不支持的 RFM 预计算比较模式: {compare_mode}")

    ranges = _resolve_date_ranges(
        period=None,
        start_date=current_start,
        end_date=current_end,
        compare_start_date=compare_start_date,
        compare_end_date=compare_end_date,
    )
    return ranges, compare_start_date, compare_end_date


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
    # 预计算结果按唯一 run generation 隔离，不能复用 ``data_version``：当天无
    # 新订单时 data_version/COUNT 不变，失败的半批预热仍必须与上一完整代共存。
    write_conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {RFM_CACHE_GENERATION_ROWS_TABLE} (
            cache_key     VARCHAR NOT NULL,
            period        VARCHAR,
            start_date    VARCHAR,
            end_date      VARCHAR,
            channel       VARCHAR,
            metric_type   VARCHAR,
            ex_channels   VARCHAR,
            result_json   VARCHAR,
            mtime_at_write VARCHAR,
            orders_count_at_write BIGINT,
            generation_id VARCHAR NOT NULL,
            computed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (generation_id, cache_key)
        )
    """)
    write_conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {RFM_CACHE_GENERATION_TABLE} (
            singleton_id        INTEGER PRIMARY KEY,
            active_generation_id VARCHAR NOT NULL,
            active_data_version VARCHAR NOT NULL,
            active_orders_count BIGINT,
            completed_at        TIMESTAMP NOT NULL
        )
    """)
    # 迁移：若表已有数据但缺新列,添加（兼容历史数据）
    for col_ddl in [
        f"ALTER TABLE {RFM_CACHE_TABLE} ADD COLUMN mtime_at_write VARCHAR",
        f"ALTER TABLE {RFM_CACHE_TABLE} ADD COLUMN orders_count_at_write BIGINT",
        # 兼容本修复早期曾创建、但尚未激活唯一 run id 的 marker 草案。
        f"ALTER TABLE {RFM_CACHE_GENERATION_TABLE} ADD COLUMN active_generation_id VARCHAR",
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


def _get_active_cache_generation(
    conn: duckdb.DuckDBPyConnection,
) -> Optional[Tuple[str, str, Optional[int], datetime]]:
    """返回最后一次完整通过 gate 的 generation；部分预热永不激活。"""
    row = conn.execute(
        f"SELECT active_generation_id, active_data_version, active_orders_count, completed_at "
        f"FROM {RFM_CACHE_GENERATION_TABLE} WHERE singleton_id = 1"
    ).fetchone()
    if not row or not row[0]:
        return None
    return str(row[0]), str(row[1]), row[2], row[3]


def _activate_cache_generation(
    conn: duckdb.DuckDBPyConnection,
    generation_id: str,
    data_version: str,
    orders_count: Optional[int],
) -> None:
    """原子切换最后完整代；必须只在完整 logical coverage gate 后调用。"""
    with _CACHE_OPERATION_LOCK:
        conn.execute(
            f"INSERT INTO {RFM_CACHE_GENERATION_TABLE} "
            "(singleton_id, active_generation_id, active_data_version, "
            "active_orders_count, completed_at) "
            "VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT (singleton_id) DO UPDATE SET "
            "active_generation_id = excluded.active_generation_id, "
            "active_data_version = excluded.active_data_version, "
            "active_orders_count = excluded.active_orders_count, "
            "completed_at = excluded.completed_at",
            [generation_id, data_version, orders_count],
        )


def _generation_within_stale_window(
    completed_at: Any,
    now: Optional[datetime] = None,
) -> bool:
    """只要 marker 时间有效，就持续服务最后完整代。

    PC2 尚无可与常驻 uvicorn 并存的自动刷新机制；给 active generation 设置
    48h 硬过期会在第 49 小时把所有热请求重新推向 miss。inactive generation 仍按
    48h retention 回收，active 则服务到下一次用户批准的维护窗成功切代。
    """
    del now  # 保留参数以兼容历史测试/调用方；active generation 不再按墙钟失效。
    if isinstance(completed_at, str):
        try:
            completed_at = datetime.fromisoformat(completed_at)
        except ValueError:
            return False
    return isinstance(completed_at, datetime)


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
    _allow_active_generation: bool = True,
) -> Optional[Dict[str, Any]]:
    """从 DuckDB 预计算表读取缓存。

    ``conn`` 仅为兼容旧调用签名保留；业务库不包含完整 cache SSOT。
    表初始化、精确读取与 fuzzy 读取统一走独立 cache DB 单例，并由
    ``_CACHE_OPERATION_LOCK`` 串行化 raw DuckDB connection 操作。

    Stale 检测：除 data_version 外,还比对 orders 行数快照,
    防止 ETL 续传后 max_pay_time 不变但行数变化导致缓存陈旧。
    """
    # L4.72.1 治本: SELECT 移出 except 块, 正常路径也跑 SELECT
    # Phase 1 第 2 个 Explore agent 100% 锁定: 旧代码 SELECT 在 except 块里,
    # 正常路径 try 块成功时**无 SELECT**, 直接 return None → 永远 cache miss
    # 治本后: 正常路径 + 异常路径 都跑 SELECT
    del conn  # cache storage 与业务查询连接严格分离
    try:
        with _CACHE_OPERATION_LOCK:
            cache_conn = _get_cache_conn()
            try:
                _ensure_db_cache_table(cache_conn)
            except Exception as init_error:
                raise RFMCacheUnavailableError(
                    f"RFM 缓存表初始化失败: {init_error}"
                ) from init_error

            active_generation = _get_active_cache_generation(cache_conn)
            active_usable = bool(
                _allow_active_generation
                and active_generation
                and _generation_within_stale_window(active_generation[3])
            )

            def _lookup(
                version: str,
                generation_id: Optional[str] = None,
            ) -> Tuple[str, Optional[Tuple[Any, ...]], bool]:
                candidate_key = _cache_key(
                    period,
                    start_date,
                    end_date,
                    channel,
                    metric_type,
                    exclude_channels,
                    version,
                    compare_start_date,
                    compare_end_date,
                )
                if generation_id:
                    candidate_row = cache_conn.execute(
                        f"SELECT result_json, mtime_at_write, orders_count_at_write, computed_at "
                        f"FROM {RFM_CACHE_GENERATION_ROWS_TABLE} "
                        "WHERE generation_id = ? AND cache_key = ?",
                        [generation_id, candidate_key],
                    ).fetchone()
                else:
                    candidate_row = cache_conn.execute(
                        f"SELECT result_json, mtime_at_write, orders_count_at_write, computed_at "
                        f"FROM {RFM_CACHE_TABLE} WHERE cache_key = ?",
                        [candidate_key],
                    ).fetchone()
                if candidate_row:
                    return candidate_key, candidate_row, False
                fuzzy = _fuzzy_match_db_cache(
                    start_date,
                    end_date,
                    channel,
                    metric_type,
                    period,
                    cache_conn,
                    tolerance_days=RFM_CACHE_FUZZY_TOLERANCE_DAYS,
                    exclude_channels=exclude_channels,
                    data_version=version,
                    compare_start_date=compare_start_date,
                    compare_end_date=compare_end_date,
                    generation_id=generation_id,
                )
                if fuzzy is None:
                    if generation_id:
                        period_fallback = _match_active_period_db_cache(
                            start_date=start_date,
                            end_date=end_date,
                            channel=channel,
                            metric_type=metric_type,
                            conn=cache_conn,
                            exclude_channels=exclude_channels,
                            data_version=version,
                            compare_start_date=compare_start_date,
                            compare_end_date=compare_end_date,
                            generation_id=generation_id,
                        )
                        if period_fallback is not None:
                            return period_fallback[0], period_fallback[1], True
                    return candidate_key, None, False
                return fuzzy[0], fuzzy[1], True

            lookup_generation_id: Optional[str] = None
            if active_usable and active_generation is not None:
                lookup_generation_id = active_generation[0]
                lookup_version = active_generation[1]
                key, row, fuzzy_hit = _lookup(
                    lookup_version,
                    lookup_generation_id,
                )
                if row is None:
                    # Active generation 只覆盖热周期；任意 custom 请求仍允许读取
                    # 当前 data_version 的 on-demand cache，随后才可能 live 计算。
                    lookup_generation_id = None
                    lookup_version = data_version
                    key, row, fuzzy_hit = _lookup(lookup_version)
            else:
                lookup_version = data_version
                key, row, fuzzy_hit = _lookup(lookup_version)
            if not row:
                return None
            if fuzzy_hit:
                logger.info(
                    f"RFM cache fuzzy hit: target=({start_date}, {end_date}) "
                    f"ch={channel or '全店'} mt={metric_type} per={period or 'None'}"
                )

            matched_active_generation = bool(
                active_usable
                and active_generation is not None
                and lookup_generation_id == active_generation[0]
                and lookup_version == active_generation[1]
                and row[1] == active_generation[1]
                and (
                    active_generation[2] is None
                    or row[2] == active_generation[2]
                )
            )
        # 防御性校验：result_json 必须是有效 JSON dict
        try:
            parsed = json.loads(row[0])
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"RFM 缓存损坏（无法解析 JSON）: key={key}, 清理该行: {e}")
            _try_delete_corrupt_row(
                key,
                row[1],
                row[2],
                row[3],
                generation_id=lookup_generation_id,
            )
            if lookup_generation_id:
                return _read_db_cache(
                    period,
                    start_date,
                    end_date,
                    channel,
                    metric_type,
                    exclude_channels,
                    data_version,
                    cache_conn,
                    compare_start_date,
                    compare_end_date,
                    current_orders_count=current_orders_count,
                    _allow_active_generation=False,
                )
            return None
        if not isinstance(parsed, dict):
            logger.warning(f"RFM 缓存损坏（不是 dict）: key={key}, type={type(parsed)}, 清理该行")
            _try_delete_corrupt_row(
                key,
                row[1],
                row[2],
                row[3],
                generation_id=lookup_generation_id,
            )
            if lookup_generation_id:
                return _read_db_cache(
                    period,
                    start_date,
                    end_date,
                    channel,
                    metric_type,
                    exclude_channels,
                    data_version,
                    cache_conn,
                    compare_start_date,
                    compare_end_date,
                    current_orders_count=current_orders_count,
                    _allow_active_generation=False,
                )
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
            if matched_active_generation:
                logger.info(
                    "RFM cache stale-while-revalidate: active_generation=%s, reason=%s",
                    active_generation[0],
                    reason,
                )
                return parsed
            logger.info(f"RFM 缓存失效（{reason}）: key={key}")
            _try_delete_corrupt_row(
                key,
                row[1],
                row[2],
                row[3],
                generation_id=lookup_generation_id,
            )
            if lookup_generation_id:
                return _read_db_cache(
                    period,
                    start_date,
                    end_date,
                    channel,
                    metric_type,
                    exclude_channels,
                    data_version,
                    cache_conn,
                    compare_start_date,
                    compare_end_date,
                    current_orders_count=current_orders_count,
                    _allow_active_generation=False,
                )
            return None
        return parsed
    except RFMCacheUnavailableError:
        raise
    except Exception as e:
        logger.error(f"RFM DuckDB 缓存读取失败，拒绝回退 live SQL: {e}")
        raise RFMCacheUnavailableError("RFM 缓存暂不可用") from e


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
    """手动维护命令：清空 RFM 缓存并重建表。

    正常 ETL 禁止调用；预计算采用“失败保旧、全量成功后按 retention prune”。

    Sprint 29+#198 简化版 (codex 推荐): 用 `DROP TABLE IF EXISTS` + `CREATE` 替代 `DELETE FROM`.
    DELETE 走 index, 遇到 index state corruption 会抛 "Failed to delete all rows from index"
    (Sprint 28+ 跑批实战: 12 行只删 8 行). DROP + CREATE 绕开 index 状态机, 永远成功.

    Returns: 被清理的行数（0 = 表为空 / 写连接失败）。
    """
    try:
        with _CACHE_OPERATION_LOCK:
            _wc = _get_cache_conn()
            _ensure_db_cache_table(_wc)
            cur = _wc.execute(f"SELECT COUNT(*) FROM {RFM_CACHE_TABLE}").fetchone()
            count = int(cur[0]) if cur else 0
            generation_row = _wc.execute(
                f"SELECT COUNT(*) FROM {RFM_CACHE_GENERATION_ROWS_TABLE}"
            ).fetchone()
            count += int(generation_row[0]) if generation_row else 0
            # Sprint 29+#198: DROP + CREATE 替代 DELETE (avoid index state corruption)
            _wc.execute(f"DROP TABLE IF EXISTS {RFM_CACHE_TABLE}")
            _wc.execute(f"DROP TABLE IF EXISTS {RFM_CACHE_GENERATION_ROWS_TABLE}")
            _wc.execute(f"DROP TABLE IF EXISTS {RFM_CACHE_GENERATION_TABLE}")
            _ensure_db_cache_table(_wc)  # 重建完整 schema；period 二级索引按 L4.74 治本保持禁用
        logger.info(f"RFM 缓存清空 (DROP + CREATE): 共 {count} 行")
        return count
    except Exception as e:
        logger.error(f"RFM 缓存清空失败: {e}")
        return 0


def _try_delete_corrupt_row(
    key: str,
    cached_mtime: Optional[str],
    cached_orders_count: Optional[int],
    cached_computed_at: Any,
    generation_id: Optional[str] = None,
) -> None:
    """仅删除仍与读取快照一致的坏行，避免并发刷新后的 TOCTOU 误删。"""
    try:
        with _CACHE_OPERATION_LOCK:
            _wc = _get_cache_conn()
            if generation_id:
                _wc.execute(
                    f"DELETE FROM {RFM_CACHE_GENERATION_ROWS_TABLE} "
                    "WHERE generation_id = ? AND cache_key = ? "
                    "AND mtime_at_write IS NOT DISTINCT FROM ? "
                    "AND orders_count_at_write IS NOT DISTINCT FROM ? "
                    "AND computed_at IS NOT DISTINCT FROM ?",
                    [
                        generation_id,
                        key,
                        cached_mtime,
                        cached_orders_count,
                        cached_computed_at,
                    ],
                )
            else:
                _wc.execute(
                    f"DELETE FROM {RFM_CACHE_TABLE} WHERE cache_key = ? "
                    "AND mtime_at_write IS NOT DISTINCT FROM ? "
                    "AND orders_count_at_write IS NOT DISTINCT FROM ? "
                    "AND computed_at IS NOT DISTINCT FROM ?",
                    [key, cached_mtime, cached_orders_count, cached_computed_at],
                )
    except Exception as e:
        logger.error(f"RFM 缓存损坏行无法清理: key={key}, {e}")
        raise RFMCacheUnavailableError("RFM 缓存损坏行无法安全清理") from e


# Stage 2 (L4.75/L4.85.10): fuzzy match ±2 day tolerance fallback.
# 跟 user 述 "近 4 周 → cache 命中 0.14s" 1:1 stable 永久规则链配套.
# 容忍 PC2 漏跑一天导致 cache end=today-3、请求 end=today-1；完整 key 重建、
# compare/exclude/channel/data-version 等值与端点同向校验共同限制误命中，±3 不开。
def _fuzzy_match_db_cache(
    start_date: Optional[str],
    end_date: Optional[str],
    channel: Optional[str],
    metric_type: str,
    period: Optional[str],
    conn: duckdb.DuckDBPyConnection,
    tolerance_days: int = RFM_CACHE_FUZZY_TOLERANCE_DAYS,
    exclude_channels: Optional[List[str]] = None,
    data_version: str = "",
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
    generation_id: Optional[str] = None,
) -> Optional[Tuple[str, Tuple[Any, ...]]]:
    """按完整 cache key 做 ±N 天候选匹配。

    fuzzy 只放宽 current start/end 日期，其余维度（数据版本、channel、metric、
    exclude_channels、compare 日期）必须与请求完全一致。返回实际命中的 key 和
    原始缓存 metadata，让调用方与 exact hit 共用 JSON/freshness 校验。
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
        table_name = (
            RFM_CACHE_GENERATION_ROWS_TABLE if generation_id else RFM_CACHE_TABLE
        )
        generation_filter = "AND o.generation_id = ? " if generation_id else ""
        params: List[Any] = [channel or "", metric_type]
        if generation_id:
            params.append(generation_id)
        params.extend([sd_lo, sd_hi, ed_lo, ed_hi])
        rows = conn.execute(
            f"SELECT o.cache_key, o.result_json, o.mtime_at_write, o.orders_count_at_write, "
            f"o.computed_at, o.start_date, o.end_date "
            f"FROM {table_name} o "
            f"WHERE o.channel = ? AND o.metric_type = ? "
            f"{generation_filter}"
            f"AND o.start_date BETWEEN ? AND ? "
            f"AND o.end_date BETWEEN ? AND ? "
            f"ORDER BY o.computed_at DESC",
            params,
        ).fetchall()
    except Exception as e:
        raise RFMCacheUnavailableError("RFM fuzzy cache 查询失败") from e
    if not rows:
        return None

    ranked_rows = []
    for row in rows:
        try:
            candidate_start = date.fromisoformat(str(row[5]))
            candidate_end = date.fromisoformat(str(row[6]))
        except (TypeError, ValueError):
            continue
        start_drift = (candidate_start - sd).days
        end_drift = (candidate_end - ed).days
        # 允许滚动窗口整体平移，或 MTD/YTD 仅一侧边界变化；拒绝窗口向两侧
        # 同时扩张/收缩，避免把不同业务区间误判成“相邻一天”。
        if start_drift * end_drift < 0:
            continue
        drift = abs(start_drift) + abs(end_drift)
        ranked_rows.append((drift, row))

    # SQL 已按 computed_at DESC；stable sort 只把日期更接近的候选提前。
    ranked_rows.sort(key=lambda item: item[0])
    for _, row in ranked_rows:
        compare_candidates = [(compare_start_date, compare_end_date)]
        if compare_start_date and compare_end_date:
            requested_mom = PeriodBuilder.mom(start_date, end_date)
            if (
                requested_mom.start == compare_start_date
                and requested_mom.end == compare_end_date
            ):
                candidate_mom = PeriodBuilder.mom(str(row[5]), str(row[6]))
                compare_candidates.append((candidate_mom.start, candidate_mom.end))

        for candidate_compare_start, candidate_compare_end in compare_candidates:
            candidate_key = _cache_key(
                period,
                str(row[5]),
                str(row[6]),
                channel,
                metric_type,
                exclude_channels,
                data_version,
                candidate_compare_start,
                candidate_compare_end,
            )
            if row[0] == candidate_key:
                return row[0], (row[1], row[2], row[3], row[4])
    return None


def _match_active_period_db_cache(
    *,
    start_date: Optional[str],
    end_date: Optional[str],
    channel: Optional[str],
    metric_type: str,
    conn: duckdb.DuckDBPyConnection,
    exclude_channels: Optional[List[str]],
    data_version: str,
    compare_start_date: Optional[str],
    compare_end_date: Optional[str],
    generation_id: str,
) -> Optional[Tuple[str, Tuple[Any, ...]]]:
    """按可识别前端 period 读取 last-known-good active 行。

    仅当请求日期精确等于“今天”对应的固定/滚动周期时启用；custom 日期不参与。
    default YOY 不带 compare key，auto_mom 则把比较期同步平移到 active 行日期。
    channel/metric/exclude/data-version 仍由完整 cache key 严格校验。
    """
    if not start_date or not end_date:
        return None

    resolved_period = ""
    for period_name, ranges in _hot_period_ranges(date.today()):
        current = ranges["current"]
        if current.start == start_date and current.end == end_date:
            resolved_period = period_name.upper()
            break
    if not resolved_period:
        return None

    requested_auto_mom = False
    if compare_start_date or compare_end_date:
        if not compare_start_date or not compare_end_date:
            return None
        requested_mom = PeriodBuilder.mom(start_date, end_date)
        requested_auto_mom = (
            requested_mom.start == compare_start_date
            and requested_mom.end == compare_end_date
        )
        if not requested_auto_mom:
            return None

    try:
        rows = conn.execute(
            f"SELECT cache_key, result_json, mtime_at_write, orders_count_at_write, "
            f"computed_at, start_date, end_date "
            f"FROM {RFM_CACHE_GENERATION_ROWS_TABLE} AS generation_rows "
            "WHERE generation_rows.generation_id = ? "
            "AND UPPER(generation_rows.period) = ? "
            "AND generation_rows.channel = ? "
            "AND generation_rows.metric_type = ? "
            "ORDER BY generation_rows.computed_at DESC",
            [generation_id, resolved_period, channel or "", metric_type],
        ).fetchall()
    except Exception as e:
        raise RFMCacheUnavailableError("RFM active period cache 查询失败") from e

    for row in rows:
        candidate_compare_start = None
        candidate_compare_end = None
        if requested_auto_mom:
            candidate_mom = PeriodBuilder.mom(str(row[5]), str(row[6]))
            candidate_compare_start = candidate_mom.start
            candidate_compare_end = candidate_mom.end
        candidate_key = _cache_key(
            None,
            str(row[5]),
            str(row[6]),
            channel,
            metric_type,
            exclude_channels,
            data_version,
            candidate_compare_start,
            candidate_compare_end,
        )
        if row[0] == candidate_key:
            logger.info(
                "RFM active period last-known-good hit: period=%s requested=%s..%s "
                "cached=%s..%s generation=%s",
                resolved_period,
                start_date,
                end_date,
                row[5],
                row[6],
                generation_id,
            )
            return row[0], (row[1], row[2], row[3], row[4])
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
        with _CACHE_OPERATION_LOCK:
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
            raise RFMCacheUnavailableError("RFM 缓存写入失败") from e
        logger.warning(f"RFM DuckDB 缓存写入失败 (非 HTTP, 可容忍): {e}")


def _prune_rfm_cache_after_success(
    write_conn: duckdb.DuckDBPyConnection,
    retention_hours: int = RFM_CACHE_RETENTION_HOURS,
) -> int:
    """完整预计算成功后回收旧代；失败/中断路径绝不调用。"""
    removed = 0
    with _CACHE_OPERATION_LOCK:
        for table_name in (RFM_CACHE_TABLE, RFM_CACHE_GENERATION_ROWS_TABLE):
            before_row = write_conn.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()
            if table_name == RFM_CACHE_GENERATION_ROWS_TABLE:
                write_conn.execute(
                    f"DELETE FROM {table_name} "
                    "WHERE computed_at < CURRENT_TIMESTAMP - (? * INTERVAL '1 hour') "
                    "AND generation_id IS DISTINCT FROM ("
                    f"SELECT active_generation_id FROM {RFM_CACHE_GENERATION_TABLE} "
                    "WHERE singleton_id = 1)",
                    [retention_hours],
                )
            else:
                write_conn.execute(
                    f"DELETE FROM {table_name} "
                    "WHERE computed_at < CURRENT_TIMESTAMP - (? * INTERVAL '1 hour')",
                    [retention_hours],
                )
            after_row = write_conn.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()
            before = int(before_row[0]) if before_row else 0
            after = int(after_row[0]) if after_row else 0
            removed += max(before - after, 0)
    return removed


def precompute_rfm_cache() -> int:
    """
    L4.71 RFM 业务治本 Stage 1 扩展版 (跟 L4.42 + L4.50 + L4.55 + L4.65.1 + L4.69.1 + L4.74 + L4.75 1:1 stable 永久规则链配套):
    预计算所有常用周期组合的 RFM 结果,存入 DuckDB 表。

    预计算范围:
      - 固定周期: 11 周期 (昨日/WTD/MTD/YTD/Q1-Q4/last90d/180d/365d)
      - 年份: 1 年 (2026) (跟 L4.74 YEARS 缩 [2026] 1:1 stable 永久规则化沿用, 节省跑批时间 ~67%)
      - 渠道: 5 个核心渠道 (全店/货架/达播/直播/淘客)
      - 对比: 2 模式 (default YOY / auto_mom 紧邻等长前期)，与前端真实请求一致
      - 指标: 2 (GSV / GMV)
      - Range 周期: 8 个业务别名（同日期 key 在物化前去重）
    共 (11 + 8) 周期 × 1 年 × 5 渠道 × 2 对比 × 2 指标 = 380 个逻辑组合；
    物理行数随当天日期别名碰撞而变化，不能用固定表行数验收完整性。

    ETL 完成后调用,自动跳过已计算的组合（ON CONFLICT DO UPDATE）。

    QW2 Phase 2: 必须先 _get_cache_conn() 拿写连接（read+write）,
    然后 SELECT orders / DDL / INSERT 都用这一个写连接。

    不能先 get_connection() 拿 read_only 单例,否则 DuckDB 报
    "Can't open a connection to same database file with a different
    configuration"（同一进程内 DuckDB 不允许不同 access_mode 的并发连接）。

    任一初始化或组合计算失败都会抛错，让 ETL gate 明确失败；禁止返回部分缓存
    却让调度器误判成功。
    """
    from datetime import timedelta

    # L4.74 cache end_date fix (跟 L4.42 + L4.50 + L4.55 + L4.65.1 + L4.69.1 + L4.74 + L4.75 1:1 stable 永久规则链配套):
    # STANDARD_PERIODS 覆盖前端全部固定周期；custom 日期不做无界预热，
    # HTTP miss 会 fail-fast 503，绝不回退同步 live SQL。
    # L4.74 fix (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套): YEARS 缩 [2026] (只算今年, 节省跑批时间 ~67%)
    YEARS = [2026]
    METRIC_TYPES = ["GSV", "GMV"]
    # L4.71 RFM 业务治本 Stage 1 (跟 L4.42 + L4.50 + L4.55 + L4.74 + L4.75 1:1 stable 永久规则链配套):
    # precompute 扩 2 维度 (CHANNELS + COMPARE_MODES), 让真实前端 channel +
    # default/auto_mom compare 请求命中缓存；未预热组合由 HTTP 503 安全拒绝。
    CHANNELS = PRECOMPUTE_CHANNELS
    EXCLUDE = None

    stage1_total = len(STANDARD_PERIODS) * len(YEARS) * len(METRIC_TYPES) * len(CHANNELS) * len(COMPARE_MODES)
    stage2_total = len(RANGE_PERIODS) * len(YEARS) * len(METRIC_TYPES) * len(CHANNELS) * len(COMPARE_MODES)
    logger.info(
        f"RFM 预计算开始 (Stage 1 L4.71+L4.74): {len(STANDARD_PERIODS)} 周期 × {len(YEARS)} 年 × {len(METRIC_TYPES)} 指标 × {len(CHANNELS)} 渠道 × {len(COMPARE_MODES)} 对比 = {stage1_total} 个组合; "
        f"(Stage 2 L4.75) 加 RANGE × {len(RANGE_PERIODS)} 周期 = 总 {stage1_total + stage2_total} 个组合 (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套)"
    )

    # 关键: 先开写连接（read+write,默认 access_mode）
    # 禁止先 get_connection()（read_only=True 会锁定同进程 DB config）
    try:
        write_conn = _get_cache_conn()
    except Exception as e:
        message = (
            "RFM 预计算失败: 无法打开写连接（ETL 场景应独立进程运行）: "
            f"{type(e).__name__}: {e}"
        )
        logger.error(message)
        raise RuntimeError(message) from e

    materialized = 0
    logical_completed = 0
    materialized_keys: set[str] = set()
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
        with _CACHE_OPERATION_LOCK:
            _ensure_db_cache_table(write_conn)
        # L4.74 fix amend (跟 L4.42 + L4.50 + L4.65.1 + L4.67 + L4.69.1 + L4.74 + L4.75 1:1 stable 永久规则链配套):
        # PC2 副 Agent 反馈实证: 8f952ac commit 漏改了 1 行 _fetch_max_pay_time(write_conn) → _fetch_max_pay_time(biz_conn)
        # 在 cache 库 (write_conn) 没有 orders 表 → Catalog Error. 修复后用 biz_conn 读业务库 orders (跟 L4.67 cache 库分离 1:1 stable 永久规则链配套)
        data_version = _fetch_max_pay_time(biz_conn)
        # Stale 修复：orders 行数快照,用于下次读时与当前 COUNT(*) 对比
        # 用 biz_conn 读业务库 orders (跟 L4.67 cache 库分离 1:1 stable 永久规则链配套)
        orders_count_snapshot = biz_conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        logger.info(f"  orders_count_snapshot = {orders_count_snapshot}")
        generation_id = uuid4().hex
        logger.info(f"  generation_id = {generation_id}")

        for metric_type in METRIC_TYPES:
            for period in STANDARD_PERIODS:
                for year in YEARS:
                    for channel in CHANNELS:  # L4.71 RFM 业务治本 Stage 1 加 channel 维度 (跟 L4.42 + L4.55 1:1 stable 永久规则化沿用)
                        for compare_mode in COMPARE_MODES:  # L4.71 RFM 业务治本 Stage 1 加 compare 维度 (跟 L4.55 1:1 stable 永久规则化沿用)
                            pb_func = getattr(PeriodBuilder, period.lower())
                            ranges = pb_func(today=today)
                            cur = ranges["current"]
                            query_ranges, compare_start_date, compare_end_date = _resolve_precompute_query_ranges(
                                str(cur.start), str(cur.end), compare_mode
                            )
                            cur_start, cur_end, cur_cutoff = query_ranges["current"]
                            comp_start, comp_end, comp_cutoff = query_ranges["comp"]
                            prev2_start, prev2_end, prev2_cutoff = query_ranges["prev2"]

                            key = _cache_key(
                                None, cur.start, cur.end, channel, metric_type, EXCLUDE, data_version,
                                compare_start_date, compare_end_date,
                            )
                            logical_completed += 1
                            if key in materialized_keys:
                                logger.debug(
                                    "RFM 预计算 alias skip: period=%s compare=%s key=%s",
                                    period,
                                    compare_mode,
                                    key,
                                )
                                continue

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

                            current_label, comp_label, prev2_label = query_ranges["labels"]
                            result = {
                                "year_label": current_label,
                                "comp_year_label": comp_label,
                                "prev2_year_label": prev2_label,
                                "metric_type": metric_type,
                                "rows": rows,
                                "same_channel_rows": same_rows,
                                "member_rows": memb_rows,
                                "member_same_channel_rows": memb_same_rows,
                            }

                            ex_str = ""
                            # L4.74 amend fix v2 (跟 L4.42 + L4.50 + L4.65.1 + L4.69.1 + L4.74 + L4.75 1:1 stable 永久规则链配套):
                            # DuckDB 1.5+ INSERT OR REPLACE 内部 = DELETE + INSERT, 但 cache 表有 idx_period 索引,
                            # DELETE 阶段触发 FATAL Error: Failed to delete all rows from index (index 锁冲突).
                            # 修复 v2: 改用 DuckDB 1.5+ 原生 ON CONFLICT (cache_key) DO UPDATE SET UPSERT 语法,
                            # 避开 DELETE 索引删除路径, 改用 UPDATE 路径 (cache_key 是 PRIMARY KEY, 满足 ON CONFLICT 约束).
                            # 写用 write_conn（QW2 Phase 2: 绕开 read_only 单例）
                            # Stale 修复：把 orders_count_at_write 也写进去,
                            # 下次读时与当前 orders.COUNT(*) 对比 → 行数变化即失效
                            with _CACHE_OPERATION_LOCK:
                                write_conn.execute(
                                f"INSERT INTO {RFM_CACHE_GENERATION_ROWS_TABLE} "
                                f"(cache_key, period, start_date, end_date, channel, metric_type, ex_channels, result_json, mtime_at_write, orders_count_at_write, generation_id, computed_at) "
                                f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP) "
                                f"ON CONFLICT (generation_id, cache_key) DO UPDATE SET "
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
                                     json.dumps(result, ensure_ascii=False, default=str), data_version,
                                     orders_count_snapshot, generation_id]
                                )
                            materialized_keys.add(key)
                            materialized += 1
                            logger.info(f"  RFM 预计算: {period} {year} {metric_type} channel={channel or '全店'} compare={compare_mode} → {key}")

        # ============================================================
        # Stage 2 (L4.75): 8 RANGE_PERIODS 逻辑覆盖。
        # current 日期来自 range resolver；comp/prev2 一律走 HTTP _resolve_date_ranges SSOT。
        # ============================================================
        for metric_type in METRIC_TYPES:                      # [GSV, GMV]
            for range_period in RANGE_PERIODS:                  # 8 (Stage 2 L4.75 新增)
                for year in YEARS:                              # [2026]
                    for channel in CHANNELS:                    # [None, 淘客, 直播, 货架]
                        for compare_mode in COMPARE_MODES:      # [default, auto_mom]
                            ranges = _resolve_range_period(range_period, today=today)
                            cur = ranges["current"]
                            query_ranges, compare_start_date, compare_end_date = _resolve_precompute_query_ranges(
                                str(cur.start), str(cur.end), compare_mode
                            )
                            cur_start, cur_end, cur_cutoff = query_ranges["current"]
                            comp_start, comp_end, comp_cutoff = query_ranges["comp"]
                            prev2_start, prev2_end, prev2_cutoff = query_ranges["prev2"]

                            key = _cache_key(
                                None, cur.start, cur.end, channel, metric_type, EXCLUDE, data_version,
                                compare_start_date, compare_end_date,
                            )
                            logical_completed += 1
                            if key in materialized_keys:
                                logger.debug(
                                    "RFM 预计算 alias skip: period=%s compare=%s key=%s",
                                    range_period,
                                    compare_mode,
                                    key,
                                )
                                continue

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

                            current_label, comp_label, prev2_label = query_ranges["labels"]
                            result = {
                                "year_label": current_label,
                                "comp_year_label": comp_label,
                                "prev2_year_label": prev2_label,
                                "metric_type": metric_type,
                                "rows": rows,
                                "same_channel_rows": same_rows,
                                "member_rows": memb_rows,
                                "member_same_channel_rows": memb_same_rows,
                            }

                            ex_str = ""
                            # ON CONFLICT (cache_key) DO UPDATE SET UPSERT (跟 L4.74 amend v2 1:1 stable 永久规则链配套):
                            with _CACHE_OPERATION_LOCK:
                                write_conn.execute(
                                f"INSERT INTO {RFM_CACHE_GENERATION_ROWS_TABLE} "
                                f"(cache_key, period, start_date, end_date, channel, metric_type, ex_channels, result_json, mtime_at_write, orders_count_at_write, generation_id, computed_at) "
                                f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP) "
                                f"ON CONFLICT (generation_id, cache_key) DO UPDATE SET "
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
                                     json.dumps(result, ensure_ascii=False, default=str), data_version,
                                     orders_count_snapshot, generation_id]
                                )
                            materialized_keys.add(key)
                            materialized += 1
                            logger.info(
                                f"  RFM 预计算 [Stage 2 RANGE]: {range_period} {year} {metric_type} "
                                f"channel={channel or '全店'} compare={compare_mode} → {key}"
                            )

        expected_total = stage1_total + stage2_total
        if (
            expected_total != EXPECTED_LOGICAL_PRECOMPUTE_COMBINATIONS
            or logical_completed != EXPECTED_LOGICAL_PRECOMPUTE_COMBINATIONS
        ):
            raise RuntimeError(
                "RFM 预计算不完整: "
                f"logical_completed={logical_completed}, "
                f"expected={EXPECTED_LOGICAL_PRECOMPUTE_COMBINATIONS}"
            )

        # 只有全部逻辑组合通过 gate 才原子切换 active generation；HTTP 在长预热
        # 或失败期间持续服务上一完整代，不会因 data_version 提前推进而回退三段
        # live SQL。切换成功后才回收 48h 前的 inactive 旧代。
        _activate_cache_generation(
            write_conn,
            generation_id,
            data_version,
            orders_count_snapshot,
        )
        pruned = _prune_rfm_cache_after_success(write_conn)
        alias_count = logical_completed - materialized
        logger.info(
            "RFM 预计算完成: logical=%s/%s, materialized=%s, aliases=%s, "
            "pruned_older_than_%sh=%s (Stage 1=%s, Stage 2 RANGE=%s)",
            logical_completed,
            expected_total,
            materialized,
            alias_count,
            RFM_CACHE_RETENTION_HOURS,
            pruned,
            stage1_total,
            stage2_total,
        )
        return logical_completed

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
