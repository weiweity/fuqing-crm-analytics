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

import os
import duckdb
import json
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from backend.config import DUCKDB_PATH
from backend.db import connection as bdc
from ._shared import _fetch_max_pay_time, _cache_key, RFM_CACHE_TABLE
from .period import _run_rfm_period, _build_rows

logger = logging.getLogger(__name__)

# 缓存 TTL（小时）— 超过此时间的缓存视为陈旧，强制重算
RFM_CACHE_TTL_HOURS = 24


# ============================================================
# 写连接管理（QW2 Phase 2 关键修复）
# ============================================================

def _open_write_conn() -> duckdb.DuckDBPyConnection:
    """打开一个独立的 DuckDB 写连接（RFM 缓存专用）。

    L4.65 永久规则化 (Sprint 205+ 真业务触发: PC2 RFM 500 根因治本):
    - HTTP 上下文里 middleware 持有 read_only 连接, 必须用 bdc 写单例
      (bdc.get_write_connection_raw()) 跟 read_only 池共存
    - 非 HTTP 场景 (脚本/ETL) 走 bdc.get_duckdb_config() + duckdb.connect()
    - 不遵循导致: DuckDB 抛 "Can't open a connection to same database file
      with a different configuration" -> RFM 500 雪崩

    Sprint 28+ (#197) 治根: 删 cfg 字典里多传的 access_mode 字段赋值行.
    QW2 Phase 2 老注释说 "uvicorn 永远 read_only",但 Sprint 24+ P3
    (v0.4.14.95) 已经把 cli.py 4 处 sibling read_only=True 全删,
    uvicorn 现在是默认 READ_WRITE. 本函数之前显式加 access_mode
    字段 → DuckDB 1.5+ strict mode 判定本 conn config ({memory_limit,
    access_mode}) ≠ cli.py._c0 config ({memory_limit}) → 抛
    "Can't open a connection to same database file with a different
    configuration" → RFM 缓存清空 + 预计算全失败.

    修复: 跟 cli.py._c0 (Sprint 24+ P3) 严格一致, 只传 memory_limit,
    不显式传 access_mode (默认值 = READ_WRITE, 跟 cli.py._c0 默认一致).

    Sprint 11 S11-3 + Sprint 24+ P3 同根因 (3 处治根):
    - Sprint 11: config dict 缺省 (memory_limit 不一致)
    - Sprint 24+ P3: access_mode 不一致 (read_only=True)
    - Sprint 28+ (#197): access_mode 字段多传 (即使值都是 READ_WRITE, strict mode
      按 config dict 严格匹配)

    db_password 仍保留 (Sprint 24 P3 同期, 加 password 字段时跟其他 sibling 比对
    通过 DUCKDB_PASSWORD env var 一致性保证; 实际生产不设 password).
    """
    from backend.services.dual_conn import get_request_connection
    from backend.services.dual_conn import _db_config, READ_MEMORY_LIMIT
    from backend.config import DUCKDB_PATH
    import duckdb

    request_conn = get_request_connection()
    if request_conn is not None:
        # L4.66 治本: mirror middleware read_only conn 的 duckdb_settings
        # (12 项关键 fingerprint), 避免 DuckDB 1.5+ strict mode 雪崩
        cfg = _db_config(READ_MEMORY_LIMIT).copy()
        try:
            settings_rows = request_conn.execute(
                "SELECT name, value FROM duckdb_settings() "
                "WHERE name IN ("
                "'memory_limit','threads','TimeZone','search_path',"
                "'default_order','default_null_order','enable_progress_bar',"
                "'enable_object_cache','wal_autocheckpoint','max_memory',"
                "'temp_directory','preserve_insertion_order'"
                ")"
            ).fetchall()
            for name, value in settings_rows:
                cfg[name] = str(value)
        except Exception:
            pass
        return duckdb.connect(str(DUCKDB_PATH), config=cfg, read_only=False)

    # 非 HTTP 场景: 脚本/ETL 直接 duckdb.connect (READ_WRITE, 跟 cli.py._c0 一致)
    cfg = bdc.get_duckdb_config()
    db_password = os.environ.get("DUCKDB_PASSWORD")
    if db_password:
        cfg["password"] = db_password
    return duckdb.connect(
        str(DUCKDB_PATH),
        config=_db_config(READ_MEMORY_LIMIT),
        read_only=False,
    )


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
    write_conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{RFM_CACHE_TABLE}_period "
                       f"ON {RFM_CACHE_TABLE}(period, start_date, end_date, channel, metric_type)")


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
    try:
        # 表结构初始化（DDL 需要写连接,用临时写连接）
        try:
            _wc = _open_write_conn()
            try:
                _ensure_db_cache_table(_wc)
            finally:
                _wc.close()
        except Exception as _e:
            # 写连接失败（如锁冲突）不阻塞读路径,继续尝试 SELECT
            logger.debug(f"RFM 缓存表初始化失败（读路径继续）: {_e}")

        # 读用调用方 conn（read_only 可读）
        row = conn.execute(
            f"SELECT result_json, mtime_at_write, orders_count_at_write, computed_at "
            f"FROM {RFM_CACHE_TABLE} WHERE cache_key = ?",
            [key]
        ).fetchone()
        if not row:
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
        _wc = _open_write_conn()
        try:
            _ensure_db_cache_table(_wc)
            cur = _wc.execute(f"SELECT COUNT(*) FROM {RFM_CACHE_TABLE}").fetchone()
            count = int(cur[0]) if cur else 0
            # Sprint 29+#198: DROP + CREATE 替代 DELETE (avoid index state corruption)
            _wc.execute(f"DROP TABLE IF EXISTS {RFM_CACHE_TABLE}")
            _ensure_db_cache_table(_wc)  # 重建 (含 cache_key 唯一索引 + period idx)
            logger.info(f"RFM 缓存清空 (DROP + CREATE): 共 {count} 行")
            return count
        finally:
            _wc.close()
    except Exception as e:
        logger.error(f"RFM 缓存清空失败: {e}")
        return 0


def _try_delete_corrupt_row(key: str) -> None:
    """用临时写连接删除损坏的缓存行（QW2 Phase 2）。失败仅 warning,不抛。"""
    try:
        _wc = _open_write_conn()
        try:
            _wc.execute(f"DELETE FROM {RFM_CACHE_TABLE} WHERE cache_key = ?", [key])
        finally:
            _wc.close()
    except Exception as e:
        logger.warning(f"RFM 缓存损坏行无法清理（read_only 模式）: key={key}, {e}")


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

    QW2 Phase 2: 移除 conn 参数,内部 _open_write_conn() 拿独立写连接
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
        _wc = _open_write_conn()
        try:
            _ensure_db_cache_table(_wc)
            _wc.execute(
                f"INSERT OR REPLACE INTO {RFM_CACHE_TABLE} "
                f"(cache_key, period, start_date, end_date, channel, metric_type, ex_channels, result_json, mtime_at_write, orders_count_at_write, computed_at) "
                f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                [key, period or "", start_date or "", end_date or "",
                 channel or "", metric_type, ex_str, result_json_str, data_version, orders_count]
            )
        finally:
            _wc.close()
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
    Plan P1: 预计算所有常用周期组合的 RFM 结果,存入 DuckDB 表。

    预计算范围：
      - 标准周期：YTD / MTD
      - 年份：2024 / 2025 / 2026
      - 渠道：全店
      - 指标：GSV / GMV
    共 2 周期 × 3 年 × 2 指标 = 12 个组合。

    ETL 完成后调用,自动跳过已计算的组合（INSERT OR REPLACE）。

    QW2 Phase 2: 必须先 _open_write_conn() 拿写连接（read+write）,
    然后 SELECT orders / DDL / INSERT 都用这一个写连接。

    不能先 get_connection() 拿 read_only 单例,否则 DuckDB 报
    "Can't open a connection to same database file with a different
    configuration"（同一进程内 DuckDB 不允许不同 access_mode 的并发连接）。

    在 uvicorn 进程（read_only 单例已建）调用本函数 → 拿写连接失败,
    本函数会捕获异常,返回 0,不影响调用方继续。
    """
    from datetime import timedelta

    STANDARD_PERIODS = ["YTD", "MTD"]  # PeriodBuilder 支持的周期
    YEARS = [2024, 2025, 2026]
    METRIC_TYPES = ["GSV", "GMV"]
    # 目前仅预计算全店
    CHANNEL = None
    EXCLUDE = None

    logger.info(f"RFM 预计算开始: {len(STANDARD_PERIODS)} 周期 × {len(YEARS)} 年 × {len(METRIC_TYPES)} 指标 = "
                f"{len(STANDARD_PERIODS) * len(YEARS) * len(METRIC_TYPES)} 个组合")

    # 关键: 先开写连接（read+write,默认 access_mode）
    # 禁止先 get_connection()（read_only=True 会锁定同进程 DB config）
    try:
        write_conn = _open_write_conn()
    except Exception as e:
        logger.error(f"RFM 预计算失败: 无法打开写连接（uvicorn read_only 单例污染？"
                     f"ETL 场景应独立进程运行）: {type(e).__name__}: {e}")
        return 0

    computed = 0
    try:
        # PeriodBuilder.mtd(today=X) 的语义是"截至 X-1 天",
        # 所以用 max_pay+1天 → MTD 包含到 max_pay 当天
        row = write_conn.execute("SELECT MAX(pay_time) FROM orders").fetchone()
        max_pay_raw = row[0] if row else None
        if max_pay_raw is not None:
            max_pay_date = max_pay_raw.date() if hasattr(max_pay_raw, 'date') else max_pay_raw
            today = max_pay_date + timedelta(days=1)
        else:
            today = date.today() + timedelta(days=1)
        logger.info(f"  预计算参考日期(today): {today} (max_pay={max_pay_raw})")

        # DDL（write_conn 可写）
        _ensure_db_cache_table(write_conn)
        data_version = _fetch_max_pay_time(write_conn)
        # Stale 修复：orders 行数快照,用于下次读时与当前 COUNT(*) 对比
        orders_count_snapshot = write_conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        logger.info(f"  orders_count_snapshot = {orders_count_snapshot}")

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

                    # 执行 3 个周期（读 orders 用 write_conn,write_conn 既可读也可写）
                    c_all, c_same, c_memb_all, c_memb_same = _run_rfm_period(
                        write_conn, cur_start, cur_end, cur_cutoff, CHANNEL, metric_type, EXCLUDE
                    )
                    p_all, p_same, p_memb_all, p_memb_same = _run_rfm_period(
                        write_conn, comp_start, comp_end, comp_cutoff, CHANNEL, metric_type, EXCLUDE
                    )
                    p2_all, p2_same, p2_memb_all, p2_memb_same = _run_rfm_period(
                        write_conn, prev2_start, prev2_end, prev2_cutoff, CHANNEL, metric_type, EXCLUDE
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

                    # 注意：前端始终传 start_date/end_date,不用 period 参数
                    # 缓存键必须基于实际日期范围,与前端请求完全一致
                    # 缓存键用实际日期,与前端请求格式完全一致
                    key = _cache_key(None, cur.start, cur.end, CHANNEL, metric_type, EXCLUDE, data_version)
                    ex_str = ""
                    # 写用 write_conn（QW2 Phase 2: 绕开 read_only 单例）
                    # Stale 修复：把 orders_count_at_write 也写进去,
                    # 下次读时与当前 orders.COUNT(*) 对比 → 行数变化即失效
                    write_conn.execute(
                        f"INSERT OR REPLACE INTO {RFM_CACHE_TABLE} "
                        f"(cache_key, period, start_date, end_date, channel, metric_type, ex_channels, result_json, mtime_at_write, orders_count_at_write, computed_at) "
                        f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                        [key, period.upper(), cur.start, cur.end, CHANNEL or "", metric_type, ex_str,
                         json.dumps(result, ensure_ascii=False, default=str), data_version, orders_count_snapshot]
                    )
                    computed += 1
                    logger.info(f"  RFM 预计算: {period} {year} {metric_type} → {key}")

    finally:
        try:
            write_conn.close()
        except Exception:
            pass

    logger.info(f"RFM 预计算完成: {computed} / {len(STANDARD_PERIODS) * len(YEARS) * len(METRIC_TYPES)} 个组合")
    return computed
