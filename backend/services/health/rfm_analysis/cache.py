"""
老客健康分析仪表盘 - RFM完整分析（8象限人群分群）

基于R/F/M三维评分，将用户划分为8个经典象限，计算各象限回购率。
逻辑同R区间分析，仅将 r_segment 替换为 rfm_segment（8象限+TTL）。
"""

import duckdb
import json
import logging
from datetime import date
from typing import Dict, Any, List, Optional

from backend.config import DUCKDB_PATH
from backend.db.connection import get_connection
from ._shared import _fetch_max_pay_time, _cache_key, DB_FILE, RFM_CACHE_TABLE
from .period import _run_rfm_period, _build_rows

logger = logging.getLogger(__name__)



def _ensure_db_cache_table(conn: duckdb.DuckDBPyConnection) -> None:
    """确保预计算缓存表存在（含 mtime_at_write 列用于缓存新鲜度校验）"""
    conn.execute(f"""
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
            computed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 迁移：若表已有数据但无 mtime_at_write 列，添加该列
    try:
        conn.execute(f"ALTER TABLE {RFM_CACHE_TABLE} ADD COLUMN mtime_at_write VARCHAR")
    except Exception:
        pass  # 列已存在
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{RFM_CACHE_TABLE}_period "
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
) -> Optional[Dict[str, Any]]:
    """从 DuckDB 预计算表读取缓存。

    缓存新鲜度校验：对比 orders 表最大支付时间（data_version）。
    data_version 在调用方通过同一 conn 获取，保证读缓存与写缓存用同一数据版本。
    注意：conn 由调用方管理，本函数不负责关闭连接。
    """
    key = _cache_key(period, start_date, end_date, channel, metric_type, exclude_channels, data_version, compare_start_date, compare_end_date)
    try:
        _ensure_db_cache_table(conn)
        row = conn.execute(
            f"SELECT result_json, mtime_at_write FROM {RFM_CACHE_TABLE} WHERE cache_key = ?",
            [key]
        ).fetchone()
        if not row:
            return None
        # 防御性校验：result_json 必须是有效 JSON dict
        try:
            parsed = json.loads(row[0])
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"RFM 缓存损坏（无法解析 JSON）: key={key}, 清理该行: {e}")
            conn.execute(f"DELETE FROM {RFM_CACHE_TABLE} WHERE cache_key = ?", [key])
            return None
        if not isinstance(parsed, dict):
            logger.warning(f"RFM 缓存损坏（不是 dict）: key={key}, type={type(parsed)}, 清理该行")
            conn.execute(f"DELETE FROM {RFM_CACHE_TABLE} WHERE cache_key = ?", [key])
            return None
        # 用 data_version 判断数据是否已更新（data_version = orders.max_pay_time）
        if data_version and row[1] and data_version > row[1]:
            logger.info(f"RFM 缓存失效（数据已更新 version={data_version} > stored={row[1]}）")
            return None
        return parsed
    except Exception as e:
        logger.warning(f"RFM DuckDB 缓存读取失败: {e}")
    return None


def _write_db_cache(
    period: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    channel: Optional[str],
    metric_type: str,
    exclude_channels: Optional[List[str]],
    conn: duckdb.DuckDBPyConnection,
    data_version: str,
    result: Dict[str, Any],
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
) -> None:
    """写入 DuckDB 预计算缓存表（含 mtime_at_write 用于后续新鲜度校验）。

    防御性校验：仅写入有效的 dict 结果，防止污染缓存表。
    conn 由调用方传入（避免多连接冲突），data_version 同理。
    """
    # 防御性校验：result 必须是有效 dict
    if not isinstance(result, dict):
        logger.warning(f"RFM 缓存写入跳过：result 不是 dict（type={type(result)}），可能是异常路径返回的 None")
        return

    try:
        result_json_str = json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        logger.warning(f"RFM 缓存写入跳过：json.dumps 失败 {e}")
        return

    key = _cache_key(period, start_date, end_date, channel, metric_type, exclude_channels, data_version, compare_start_date, compare_end_date)
    ex_str = json.dumps(exclude_channels, ensure_ascii=False) if exclude_channels else ""
    _ensure_db_cache_table(conn)
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO {RFM_CACHE_TABLE} "
            f"(cache_key, period, start_date, end_date, channel, metric_type, ex_channels, result_json, mtime_at_write, computed_at) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            [key, period or "", start_date or "", end_date or "",
             channel or "", metric_type, ex_str, result_json_str, data_version]
        )
    except Exception as e:
        logger.warning(f"RFM DuckDB 缓存写入失败（不影响返回）: {e}")


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
    from datetime import timedelta

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
        data_version = _fetch_max_pay_time(conn)

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
                    key = _cache_key(None, cur.start, cur.end, CHANNEL, metric_type, EXCLUDE, data_version)
                    ex_str = ""
                    conn.execute(
                        f"INSERT OR REPLACE INTO {RFM_CACHE_TABLE} "
                        f"(cache_key, period, start_date, end_date, channel, metric_type, ex_channels, result_json, mtime_at_write, computed_at) "
                        f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                        [key, period.upper(), cur.start, cur.end, CHANNEL or "", metric_type, ex_str,
                         json.dumps(result, ensure_ascii=False, default=str), data_version]
                    )
                    computed += 1
                    logger.info(f"  RFM 预计算: {period} {year} {metric_type} → {key}")

    finally:
        conn.close()

    logger.info(f"RFM 预计算完成: {computed} / {len(STANDARD_PERIODS) * len(YEARS) * len(METRIC_TYPES)} 个组合")
    return computed
