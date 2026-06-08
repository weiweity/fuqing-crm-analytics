"""DuckDB 内存监控与告警

提供进程级和 DuckDB 引擎级的内存监控能力：
- check_memory(): 检查当前内存使用，超过阈值时发出告警
- get_memory_stats(): 获取内存使用统计（供 API 和健康检查使用）
- start_memory_watchdog(): 启动后台守护线程，周期性检查内存

使用方式：
    from backend.db.memory_monitor import check_memory, get_memory_stats
    # 在关键操作前后调用
    check_memory(label="ETL full load")
    stats = get_memory_stats()
"""

import logging
import threading
import time
from typing import Dict, Any, Optional

import duckdb

from backend.config import DUCKDB_MEMORY_LIMIT

logger = logging.getLogger(__name__)

# 告警阈值：DuckDB 内存使用超过 memory_limit 的百分比
_ALERT_THRESHOLD_PCT = 0.85  # 85%
# 告警阈值：系统进程 RSS 超过此值（字节）
# Sprint 9 维修: 2GB 太低, ETL 跑批正常 RSS 3-4GB 触发误报甚至被 watchdog kill.
# 调到 8GB 跟 DUCKDB_MEMORY_LIMIT=8GB 一致.
_RSS_ALERT_BYTES = 8 * 1024 * 1024 * 1024  # 8GB
# 硬限阈值：超过即 sys.exit(1)，防 OOM 把整个 Mac 拖崩
# Sprint 10 preflight B1: 8GB 告警只是 logger.warning, 跑批继续. 加 12GB 硬限做
# last-line-of-defense, 跑批如果 RSS > 12GB 立即 sys.exit(1) 让 launchd 检测到
# 失败 exit code 并告警. 阈值定 12GB (8GB DuckDB + 4GB pandas/其他 Python 对象).
_RSS_HARD_LIMIT_BYTES = 12 * 1024 * 1024 * 1024  # 12GB

# 内存统计缓存（避免频繁查询 DuckDB）
_stats_cache: Dict[str, Any] = {}
_stats_cache_lock = threading.Lock()
_stats_cache_ts: float = 0
_CACHE_TTL: float = 5.0  # 缓存 5 秒


def _parse_memory_limit_bytes() -> int:
    """将 DUCKDB_MEMORY_LIMIT（如 '8GB'）解析为字节数"""
    val = str(DUCKDB_MEMORY_LIMIT).strip().upper()
    try:
        if val.endswith("GB"):
            return int(float(val[:-2]) * 1024 * 1024 * 1024)
        elif val.endswith("MB"):
            return int(float(val[:-2]) * 1024 * 1024)
        elif val.endswith("KB"):
            return int(float(val[:-2]) * 1024)
        else:
            return int(val)
    except (ValueError, TypeError):
        return 8 * 1024 * 1024 * 1024  # 默认 8GB


def _get_process_rss_bytes() -> int:
    """获取当前进程的 RSS（驻留内存）"""
    try:
        import resource
        # macOS: ru_maxrss 单位是字节；Linux: 单位是 KB
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if rss < 1024 * 1024:
            # 可能是 KB 单位（Linux）
            return rss * 1024
        return rss
    except Exception:
        return 0


def get_memory_stats(conn: Optional[duckdb.DuckDBPyConnection] = None) -> Dict[str, Any]:
    """获取内存使用统计。

    Args:
        conn: 可选的 DuckDB 连接。不传时返回系统级统计（不含 DuckDB 引擎统计）。

    Returns:
        dict: 包含内存使用信息的字典
    """
    global _stats_cache, _stats_cache_ts

    now = time.time()
    with _stats_cache_lock:
        if _stats_cache and (now - _stats_cache_ts) < _CACHE_TTL:
            return _stats_cache.copy()

    limit_bytes = _parse_memory_limit_bytes()
    rss_bytes = _get_process_rss_bytes()
    stats = {
        "memory_limit": DUCKDB_MEMORY_LIMIT,
        "memory_limit_bytes": limit_bytes,
        "process_rss_bytes": rss_bytes,
        "process_rss_mb": round(rss_bytes / (1024 * 1024), 1),
        "duckdb_alloc_bytes": 0,
        "duckdb_temp_bytes": 0,
        "duckdb_usage_pct": 0.0,
        "alert": False,
        "alert_reason": "",
    }

    if conn is not None:
        try:
            mem_rows = conn.execute("SELECT * FROM duckdb_memory()").fetchall()
            desc = conn.execute("SELECT * FROM duckdb_memory()").description
            cols = [d[0] for d in desc]
            total_alloc = 0
            total_temp = 0
            for row in mem_rows:
                entry = dict(zip(cols, row))
                total_alloc += entry.get("allocator_memory_usage", 0)
                total_temp += entry.get("temporary_memory_usage", 0)
            stats["duckdb_alloc_bytes"] = total_alloc
            stats["duckdb_temp_bytes"] = total_temp
            if limit_bytes > 0:
                stats["duckdb_usage_pct"] = round(total_alloc / limit_bytes * 100, 1)
        except Exception as e:
            logger.debug("获取 DuckDB 内存统计失败: %s", e)

    # 告警判断
    if stats["duckdb_usage_pct"] > _ALERT_THRESHOLD_PCT * 100:
        stats["alert"] = True
        stats["alert_reason"] = (
            f"DuckDB 内存使用 {stats['duckdb_usage_pct']:.1f}% "
            f"超过阈值 {_ALERT_THRESHOLD_PCT * 100:.0f}%"
        )
    elif rss_bytes > _RSS_ALERT_BYTES:
        stats["alert"] = True
        stats["alert_reason"] = (
            f"进程 RSS {stats['process_rss_mb']:.1f}MB "
            f"超过阈值 {_RSS_ALERT_BYTES // (1024*1024)}MB"
        )

    with _stats_cache_lock:
        _stats_cache = stats
        _stats_cache_ts = now

    return stats.copy()


def check_memory(label: str = "", conn: Optional[duckdb.DuckDBPyConnection] = None) -> bool:
    """检查内存使用，超阈值时记录告警日志。

    Args:
        label: 日志标签（如 'ETL full load'）
        conn: 可选的 DuckDB 连接

    Returns:
        bool: True 表示正常，False 表示触发告警

    Raises:
        SystemExit: 如果 RSS 超过硬限 (_RSS_HARD_LIMIT_BYTES = 12GB),
            立即 sys.exit(1). Sprint 10 preflight B1 加的 last-line-of-defense,
            防 ETL 跑批 RSS 持续增长把 Mac 拖崩.
    """
    import sys
    rss_bytes = _get_process_rss_bytes()
    if rss_bytes > _RSS_HARD_LIMIT_BYTES:
        rss_mb = rss_bytes / (1024 * 1024)
        hard_limit_mb = _RSS_HARD_LIMIT_BYTES // (1024 * 1024)
        msg = (
            f"[内存监控] {label or ''} FATAL: RSS {rss_mb:.1f}MB 超过硬限 "
            f"{hard_limit_mb}MB, 立即退出 (防 OOM 把 Mac 拖崩). "
            f"建议: 调小 _memory_limit, 或检查是否有内存泄漏."
        )
        logger.critical(msg)
        # Sprint 10 preflight B1: launchd 检测 exit code != 0 会发告警邮件
        sys.exit(1)

    stats = get_memory_stats(conn)
    prefix = f"[内存监控] {label} " if label else "[内存监控] "

    logger.info(
        "%sRSS=%sMB, DuckDB=%sMB (%.1f%% of %s)",
        prefix,
        stats["process_rss_mb"],
        round(stats["duckdb_alloc_bytes"] / (1024 * 1024), 1),
        stats["duckdb_usage_pct"],
        stats["memory_limit"],
    )

    if stats["alert"]:
        logger.warning("%s告警: %s", prefix, stats["alert_reason"])
        return False
    return True


class MemoryWatchdog:
    """后台内存监控守护线程。

    定期检查进程内存使用，超阈值时记录告警。
    """

    def __init__(self, interval: float = 60.0):
        """
        Args:
            interval: 检查间隔（秒），默认 60 秒
        """
        self._interval = interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _run(self):
        while not self._stop_event.is_set():
            try:
                check_memory(label="watchdog")
            except Exception as e:
                logger.debug("内存监控异常: %s", e)
            self._stop_event.wait(self._interval)

    def start(self):
        """启动守护线程"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="mem-watchdog")
        self._thread.start()
        logger.info("内存监控守护线程已启动 (间隔=%ss)", self._interval)

    def stop(self):
        """停止守护线程"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            logger.info("内存监控守护线程已停止")


# 全局单例
_watchdog: Optional[MemoryWatchdog] = None


def start_memory_watchdog(interval: float = 60.0) -> MemoryWatchdog:
    """启动全局内存监控守护线程（幂等）"""
    global _watchdog
    if _watchdog is None:
        _watchdog = MemoryWatchdog(interval=interval)
    _watchdog.start()
    return _watchdog


def stop_memory_watchdog():
    """停止全局内存监控守护线程"""
    global _watchdog
    if _watchdog:
        _watchdog.stop()
