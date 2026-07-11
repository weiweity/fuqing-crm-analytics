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
import os
import threading
import time
from typing import Dict, Any, Optional

import duckdb
import psutil

from backend.config import DUCKDB_MEMORY_LIMIT

logger = logging.getLogger(__name__)

# 告警阈值：DuckDB 内存使用超过 memory_limit 的百分比
_ALERT_THRESHOLD_PCT = 0.85  # 85%
# 告警阈值：系统进程 RSS 超过此值（字节）
# Sprint 9 维修: 2GB 太低, ETL 跑批正常 RSS 3-4GB 触发误报甚至被 watchdog kill.
# 调到 8GB 跟 DUCKDB_MEMORY_LIMIT=8GB 一致.
_GIB = 1024 * 1024 * 1024
_RSS_ALERT_BYTES = int(float(os.environ.get("FQ_RSS_ALERT_GB", "8")) * _GIB)
# 16GB Mac 的 last-line-of-defense。旧 watchdog 在线程里 sys.exit() 只会
# 杀掉自己，uvicorn 仍可继续涨到 35GB；8GB 时必须终止整个进程交给 launchd 拉起。
_RSS_HARD_LIMIT_BYTES = int(float(os.environ.get("FQ_RSS_HARD_LIMIT_GB", "12")) * _GIB)

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
    """获取当前 RSS，而不是只增不减的 ru_maxrss 历史峰值。"""
    try:
        return int(psutil.Process(os.getpid()).memory_info().rss)
    except Exception:
        return 0


def _terminate_process_for_memory_pressure() -> None:
    """Terminate the whole process from any thread; launchd will restart it."""
    os._exit(1)


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

    超过硬限时使用 ``os._exit(1)`` 结束整个进程。该函数可能由 watchdog
    后台线程调用，``sys.exit``/``SystemExit`` 只会结束线程，不能保护主机。
    """
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
        _terminate_process_for_memory_pressure()

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

    def __init__(self, interval: float = 5.0):
        """
        Args:
            interval: 检查间隔（秒），默认 5 秒
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


def start_memory_watchdog(interval: float = 5.0) -> MemoryWatchdog:
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
