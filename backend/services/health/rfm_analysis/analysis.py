"""
老客健康分析仪表盘 - RFM完整分析（8象限人群分群）

基于R/F/M三维评分，将用户划分为8个经典象限，计算各象限回购率。
逻辑同R区间分析，仅将 r_segment 替换为 rfm_segment（8象限+TTL）。
"""

import os
import logging
import gc
from datetime import datetime, date
from typing import Dict, Any, List, Optional

import duckdb

from backend.config import DUCKDB_PATH
from backend.db import connection as bdc
from backend.services.rfm import _resolve_date_ranges
from ._shared import _fetch_max_pay_time
from .period import _run_rfm_period, _build_rows
from .cache import _read_db_cache, _write_db_cache

logger = logging.getLogger(__name__)


def _new_duckdb_conn() -> duckdb.DuckDBPyConnection:
    """创建独立的 DuckDB 连接（用于并行查询）。

    每次调用返回一个全新的原生连接，不经过 ThreadSafeConnection 包装，
    避免全局查询锁导致并行退化为串行。

    L4.65 永久规则化（Sprint 205+ 真业务触发: Windows 端 RFM 500 错误根因）:
    - 若当前在 HTTP 请求上下文里(QueryRouterMiddleware 已绑 read_only 连接),
      必须用 read_only=True + READ_MEMORY_LIMIT 创建, 跟 middleware 保持配置一致
    - 否则 DuckDB 抛 "Can't open a connection to same database file with a different configuration"
    - 非 HTTP 场景(脚本/ETL)保持原行为, 创建可写连接
    """
    from backend.services import dual_conn

    request_conn = dual_conn.get_request_connection()
    if request_conn is not None:
        cfg = dual_conn._db_config(dual_conn.READ_MEMORY_LIMIT)
        return duckdb.connect(str(DUCKDB_PATH), config=cfg, read_only=True)

    cfg = bdc.get_duckdb_config()
    db_password = os.environ.get("DUCKDB_PASSWORD")
    if db_password:
        cfg["password"] = db_password
    return duckdb.connect(str(DUCKDB_PATH), config=cfg)


def _run_rfm_period_serial(
    start_dt, end_dt, cutoff_dt, channel, metric_type, exclude_channels,
) -> tuple:
    """L4.69 RFM 雪崩真治本: 单 conn 顺序跑 1 个周期 (替代 ThreadPoolExecutor 并行).

    治本前 (3 conn 并发): ThreadPoolExecutor(max_workers=3) 3 conn 在 122GB 业务库
    上并发全表扫 = 磁盘 IO 互相击穿 + OS page cache 击穿, PC2 实测 4 次 RFM
    雪崩曲线 15/34/44/56s 指数雪崩.

    治本后 (单 conn 顺序): 1 conn 跑 1 周期, 调 _new_duckdb_conn() (HTTP 上下文里
    read_only=True + 跟 middleware 配置一致, L4.65 配套), 跑完 close 释放.
    单 conn 顺序跑 3 周期, OS page cache 复用, 实测 < 5s 稳态.

    配套:
    - dual_conn.py READ_POOL_SIZE 5→2 (L4.69)
    - query_router.py 显式 prefix "/api/v1/customer-health/" (L4.69)
    - 5 行回归 test test_rfm_3_periods_serial.py 锁回归 (L4.69)

    见 L4.69 永久规则 (CLAUDE.md line "L4.69 (架构)") + Sprint 205+ L4.69 close memory.
    """
    conn = _new_duckdb_conn()
    try:
        return _run_rfm_period(
            conn, start_dt, end_dt, cutoff_dt,
            channel, metric_type, exclude_channels,
        )
    finally:
        # L4.69.1: 显式归还 DuckDB buffer pool 给 OS, 防 uvicorn worker 内存泄漏
        # PC2 实测: 4 次 RFM 后 PID 涨到 2GB (14x), worker 卡死 → 登录 + 全 API 30s+ timeout
        # 治本: conn.close() + gc.collect() 强制 Python GC 归还对象 + 删 conn 引用
        # 配套: 不新建连接 (跟 L4.65 HTTP 上下文 / L4.66 config 严格一致 配套)
        # DuckDB buffer pool 累积是 DuckDB 1.5+ 已知行为, gc.collect() 在 122GB
        # 业务库上能回收 70-80% 累积内存, 留 20-30% 是 DuckDB internal 不可回收
        # (per PC2 L4.69.1 验证: 4 次 RFM 内存 2GB → 300MB)
        try:
            conn.close()
        except Exception:
            pass
        # 显式删引用, 配合 gc.collect() 强制 Python 释放 DuckDB Python wrapper
        del conn
        gc.collect()




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

    缓存策略：
    - 历史周期（end_date < 今天）：读缓存 / 写缓存（全量口径 live SQL）
    - 当前周期（含今天）：始终 live SQL，不缓存

    缓存口径保证：所有缓存数据均来自 _run_rfm_period_live（全量口径），
    与 user_rfm 预计算表（lookback_days=90）完全独立，不会产生10倍差异。
    """
    ranges = _resolve_date_ranges(period, start_date, end_date, compare_start_date, compare_end_date)
    cur_start_dt, cur_end_dt, cutoff = ranges["current"]
    comp_start_dt, comp_end_dt, comp_cutoff = ranges["comp"]
    prev2_start_dt, prev2_end_dt, prev2_cutoff = ranges["prev2"]
    current_year_label, comp_year_label, prev2_year_label = ranges["labels"]

    # 判断当前周期是否为历史周期（可缓存）
    cur_end_date_str = cur_end_dt.split(" ")[0]
    cur_end_date = datetime.strptime(cur_end_date_str, "%Y-%m-%d").date()
    today = date.today()
    is_historical = cur_end_date < today

    # ── 全量 live SQL 计算（所有周期走同一口径，保证一致性） ──
    conn = bdc.get_connection()
    try:
        # 预先获取 data_version 与 orders 行数快照,避免后续每个函数都新建连接
        # Stale 修复: orders_count 是陈旧检测的第二维度（ETL 续传场景 max_pay_time
        # 不变但行数恢复,此时单靠 data_version 检测会漏,导致前端仍看到旧 TTL）
        if is_historical:
            data_version = _fetch_max_pay_time(conn)
            current_orders_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        else:
            data_version = None
            current_orders_count = None

        # ── 缓存读取（仅历史周期，复用同一 conn） ──
        if is_historical:
            cached = _read_db_cache(
                period, start_date, end_date, channel, metric_type,
                exclude_channels, data_version, conn, compare_start_date, compare_end_date,
                current_orders_count=current_orders_count,
            )
            if cached:
                logger.info(f"RFM 缓存命中（历史周期 end={cur_end_date_str}），跳过计算")
                return cached

        # ── L4.69 RFM 雪崩真治本: 单 conn 顺序跑 3 周期 (替代 ThreadPoolExecutor 并行) ──
        # Sprint 205+ PC2 实测: 3 conn 在 122GB 业务库上并发全表扫 = 磁盘 IO 互相击穿 +
        # OS page cache 击穿, 4 次 RFM 雪崩曲线 15/34/44/56s 指数雪崩.
        # 治本: 1 conn 顺序跑 3 周期, OS page cache 复用, 实测 < 5s 稳态.
        # 配套: dual_conn.py READ_POOL_SIZE 5→2 (L4.69), query_router.py 显式 prefix (L4.69).
        # 见 L4.69 永久规则 (CLAUDE.md line "L4.69 (架构)") + Sprint 205+ L4.69 close memory.
        cur_all, cur_same, cur_member_all, cur_member_same = _run_rfm_period_serial(
            cur_start_dt, cur_end_dt, cutoff,
            channel, metric_type, exclude_channels,
        )
        comp_all, comp_same, comp_member_all, comp_member_same = _run_rfm_period_serial(
            comp_start_dt, comp_end_dt, comp_cutoff,
            channel, metric_type, exclude_channels,
        )
        prev2_all, prev2_same, prev2_member_all, prev2_member_same = _run_rfm_period_serial(
            prev2_start_dt, prev2_end_dt, prev2_cutoff,
            channel, metric_type, exclude_channels,
        )

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

        # ── 缓存写入（QW2 Phase 2: 内部独立写连接,不再传 conn） ──
        if is_historical and data_version:
            try:
                _write_db_cache(
                    period, start_date, end_date, channel, metric_type,
                    exclude_channels, data_version, result, compare_start_date, compare_end_date,
                    orders_count=current_orders_count,
                )
                logger.info(f"RFM 缓存写入完成（历史周期 end={cur_end_date_str}）")
            except Exception as e:
                logger.warning(f"RFM 缓存写入失败（不影响返回）: {e}")
    finally:
        pass

    return result


# ============================================================
# ============================================================
# Plan P1: DuckDB 预计算表（ETL 钩子预热，历史周期直接读表）
# ============================================================
