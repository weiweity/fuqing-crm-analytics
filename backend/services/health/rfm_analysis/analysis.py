"""
老客健康分析仪表盘 - RFM完整分析（8象限人群分群）

基于R/F/M三维评分，将用户划分为8个经典象限，计算各象限回购率。
逻辑同R区间分析，仅将 r_segment 替换为 rfm_segment（8象限+TTL）。
"""

import os
import logging
import concurrent.futures
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

    测试时通过 monkeypatch 此函数注入 mock 连接。
    """
    cfg = bdc.get_duckdb_config()
    db_password = os.environ.get("DUCKDB_PASSWORD")
    if db_password:
        cfg["password"] = db_password
    return duckdb.connect(str(DUCKDB_PATH), config=cfg)




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

        # ── 并行执行 3 个周期的 RFM 查询（每个线程使用独立连接） ──
        conn_cur = _new_duckdb_conn()
        conn_comp = _new_duckdb_conn()
        conn_prev2 = _new_duckdb_conn()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                future_cur = executor.submit(
                    _run_rfm_period, conn_cur,
                    cur_start_dt, cur_end_dt, cutoff,
                    channel, metric_type, exclude_channels,
                )
                future_comp = executor.submit(
                    _run_rfm_period, conn_comp,
                    comp_start_dt, comp_end_dt, comp_cutoff,
                    channel, metric_type, exclude_channels,
                )
                future_prev2 = executor.submit(
                    _run_rfm_period, conn_prev2,
                    prev2_start_dt, prev2_end_dt, prev2_cutoff,
                    channel, metric_type, exclude_channels,
                )

                cur_all, cur_same, cur_member_all, cur_member_same = future_cur.result()
                comp_all, comp_same, comp_member_all, comp_member_same = future_comp.result()
                prev2_all, prev2_same, prev2_member_all, prev2_member_same = future_prev2.result()
        finally:
            for _conn in (conn_cur, conn_comp, conn_prev2):
                try:
                    _conn.close()
                except Exception:
                    pass

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
