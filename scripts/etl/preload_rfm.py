"""
RFM 预加载脚本
批量计算热点日期的用户象限分布并写入 user_rfm 表，供 flow_service 等接口加速读取。

用法:
    python scripts/preload_rfm.py --auto          # 自动计算常用周期节点
    python scripts/preload_rfm.py --date 2026-04-01 --lookback 90 --metric GMV
    python scripts/preload_rfm.py --range 2026-01-01 2026-04-16 --step 7       # 每隔7天计算一次
"""

import argparse
import sys
import time
from datetime import date, timedelta
from calendar import monthrange
from typing import List, Tuple
import duckdb
from pathlib import Path

# 把 backend 加入路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import DUCKDB_PATH, DUCKDB_MEMORY_LIMIT
from backend.semantic.segments import get_registry, RFM_THRESHOLDS
from backend.semantic.filters import OrderFilters
from backend.semantic.channels import ACTIVE_UI_CHANNELS

# QW0 埋点：preload_rfm 是 hot spot #1（540 组合串行循环 = 25min）
# 入口/出口各打一次 perf_counter
try:
    from scripts.etl._timer import PerfTimer  # noqa: F401
except ImportError:
    class PerfTimer:  # type: ignore[no-redef]
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None


# ============================================================
# 热点日期生成器
# ============================================================

def get_hot_dates(today: date = None) -> List[date]:
    """
    生成常用分析周期对应的热点日期。
    这些日期是 RFM 流转矩阵/桑基图最常查询的 from_date / to_date。
    """
    if today is None:
        today = date.today()
    yesterday = today - timedelta(days=1)

    # 上周末（周日）
    last_sunday = yesterday - timedelta(days=yesterday.weekday() + 1)

    # 上月末
    if yesterday.month == 1:
        last_month_end = date(yesterday.year - 1, 12, 31)
    else:
        last_month_end = date(yesterday.year, yesterday.month - 1, monthrange(yesterday.year, yesterday.month - 1)[1])

    # 上季度末
    quarter_end_months = [3, 6, 9, 12]
    current_q = (yesterday.month - 1) // 3
    if current_q == 0:
        last_q_end = date(yesterday.year - 1, 12, 31)
    else:
        last_q_end = date(yesterday.year, quarter_end_months[current_q - 1], monthrange(yesterday.year, quarter_end_months[current_q - 1])[1])

    # 今年初 / 去年末
    year_start = date(yesterday.year, 1, 1)
    last_year_end = date(yesterday.year - 1, 12, 31)

    # 最近 4 个周末
    recent_sundays = [yesterday - timedelta(days=yesterday.weekday() + 1 + 7 * i) for i in range(4)]

    # 最近 3 个月末
    recent_month_ends = []
    for i in range(1, 4):
        m = yesterday.month - i
        y = yesterday.year
        if m <= 0:
            m += 12
            y -= 1
        recent_month_ends.append(date(y, m, monthrange(y, m)[1]))

    candidates = [
        yesterday,
        last_sunday,
        last_month_end,
        last_q_end,
        year_start,
        last_year_end,
        *recent_sundays,
        *recent_month_ends,
    ]

    # 去重并过滤掉未来日期
    unique = sorted({d for d in candidates if d <= today})
    return unique


# ============================================================
# RFM 计算与写入
# ============================================================

# R 窗口固定365天（独立于 F/M 的 lookback_days），用于计算 recency_days
R_LOOKBACK_DAYS = 365


def build_rfm_sql(metric_type: str, channel: str = "全店") -> str:
    """构造用于预加载的完整 RFM 计算 SQL（结果可直接插入 user_rfm）。

    R 窗口固定365天（独立计算 recency_days）；
    F/M 窗口复用 lookback_days 参数。
    channel='全店' 时不过滤渠道，为特定渠道时按 channel 过滤。
    """
    registry = get_registry()
    r_score_sql = registry.build_r_score_sql(RFM_THRESHOLDS["r"])
    f_score_sql = registry.build_f_score_sql(RFM_THRESHOLDS["f"])
    m_score_sql = registry.build_m_score_sql(RFM_THRESHOLDS["m"])
    segment_sql = registry.build_segment_case_when_sql()
    valid_sql, _ = OrderFilters.valid_order()
    amount_cond = "actual_amount > 0" if metric_type == "GMV" else "actual_amount >= 0"

    tier_cn_sql = registry.build_segment_name_case_when_sql("cn")
    tier_en_sql = registry.build_segment_name_case_when_sql("en")

    # 渠道过滤：channel='全店' 时不过滤，其他值精确匹配
    channel_cond = "AND o.channel = ?" if channel != "全店" else ""

    sql = f"""
    WITH base_params AS (
        -- lookback_days: F/M 窗口（分析日往回数 N 天）
        -- r_lookback_days: R 窗口（固定365天，独立计算 recency_days）
        SELECT
            DATE(?) AS analysis_date,
            DATE(?) AS start_date,
            DATE(?) - INTERVAL '{R_LOOKBACK_DAYS}' DAY AS r_start_date
    ),
    -- F/M 指标：使用 lookback_days 窗口
    fm_orders AS (
        SELECT
            o.user_id,
            o.actual_amount,
            o.order_id,
            o.pay_time,
            o.is_member
        FROM orders o
        CROSS JOIN base_params p
        WHERE o.pay_time >= p.start_date
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          AND ({amount_cond})
          {channel_cond}
    ),
    fm_metrics AS (
        SELECT
            user_id,
            SUM(actual_amount) AS monetary,
            COUNT(DISTINCT order_id) AS frequency,
            MAX(pay_time) AS last_pay_time,
            MIN(pay_time) AS first_pay_time,
            BOOL_OR(is_member) AS has_member_order
        FROM fm_orders
        GROUP BY user_id
    ),
    -- R 指标：使用固定365天窗口，独立计算 recency_days
    r_orders AS (
        SELECT
            o.user_id,
            MAX(o.pay_time) AS r_last_pay_time
        FROM orders o
        CROSS JOIN base_params p
        WHERE o.pay_time >= p.r_start_date
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          AND ({amount_cond})
          {channel_cond}
        GROUP BY o.user_id
    ),
    user_with_rfm AS (
        SELECT
            fm.user_id,
            fm.monetary,
            fm.frequency,
            fm.first_pay_time::DATE AS first_order_date,
            fm.last_pay_time::DATE AS last_order_date,
            fm.has_member_order,
            -- R: 基于365天窗口计算最近购买距分析日天数
            DATEDIFF('day', COALESCE(r.r_last_pay_time, fm.last_pay_time), DATE(?)) AS recency_days
        FROM fm_metrics fm
        LEFT JOIN r_orders r ON fm.user_id = r.user_id
    ),
    user_with_scores AS (
        SELECT
            user_id,
            monetary,
            frequency,
            first_order_date,
            last_order_date,
            has_member_order,
            recency_days,
            {r_score_sql} AS r_score,
            {f_score_sql} AS f_score,
            {m_score_sql} AS m_score
        FROM user_with_rfm
    ),
    user_with_segment AS (
        SELECT
            user_id,
            monetary,
            frequency,
            first_order_date,
            last_order_date,
            has_member_order,
            recency_days,
            r_score,
            f_score,
            m_score,
            {segment_sql} AS segment_id
        FROM user_with_scores
    )
    SELECT
        user_id,
        NULL AS user_nickname,
        analysis_date AS analysis_date,
        ? AS metric_type,
        ? AS lookback_days,
        ? AS channel,
        recency_days,
        frequency,
        monetary,
        r_score,
        f_score,
        m_score,
        {tier_cn_sql} AS rfm_tier,
        {tier_en_sql} AS rfm_tier_en,
        segment_id,
        first_order_date,
        last_order_date,
        has_member_order AS is_member,
        CURRENT_TIMESTAMP AS created_at
    FROM user_with_segment
    CROSS JOIN base_params
    """
    return sql


def preload_date(
    conn: duckdb.DuckDBPyConnection,
    analysis_date: date,
    lookback_days: int,
    metric_type: str,
    channel: str = "全店",
) -> int:
    """计算指定日期的 RFM 并写入 user_rfm 表，返回写入行数。

    R 窗口固定365天（独立于 lookback_days），确保 recency_days 反映完整购买历史。
    channel='全店' 不过滤渠道，为其他值时精确过滤。
    """
    start_date = analysis_date - timedelta(days=lookback_days)
    date_str = analysis_date.strftime("%Y-%m-%d")
    date_upper = date_str  # 分析日上界（< analysis_date + 1天）

    # 先删除旧数据（同一组合，含渠道）
    conn.execute(
        """
        DELETE FROM user_rfm
        WHERE analysis_date = ?
          AND metric_type = ?
          AND lookback_days = ?
          AND channel = ?
        """,
        [date_str, metric_type, lookback_days, channel],
    )

    sql = build_rfm_sql(metric_type, channel)
    # 参数顺序（channel != '全店' 时多1个 ?）：
    # 1. analysis_date       -> base_params.analysis_date
    # 2. start_date          -> base_params.start_date（FM窗口起点）
    # 3. date_upper          -> base_params（r_start_date 在 SQL 内计算）
    # 4. date_upper          -> fm_orders 上界
    # 5. [channel]           -> fm_orders 渠道过滤（仅 channel != '全店' 时）
    # 6. date_upper          -> r_orders 上界
    # 7. [channel]           -> r_orders 渠道过滤（仅 channel != '全店' 时）
    # 8. analysis_date       -> recency_days 计算
    # 9. metric_type
    # 10. lookback_days
    # 11. channel
    params = [
        date_str,
        start_date.strftime("%Y-%m-%d"),
        date_upper,
        date_upper,
    ]
    if channel != "全店":
        # channel 过滤: fm_orders + r_orders 各多一个 ?
        params.append(channel)
        params.append(date_upper)
        params.append(channel)
    else:
        # 全店不过滤渠道，fm_orders 和 r_orders 各一个 upper bound ?（第5个是 DATEDIFF 的 date_str）
        params.append(date_upper)
    # DATEDIFF 第二个参数始终用 date_str
    params.extend([
        date_str,
        metric_type,
        lookback_days,
        channel,
    ])

    conn.execute(f"""
        INSERT INTO user_rfm (
            user_id, user_nickname, analysis_date, metric_type, lookback_days,
            channel,
            recency_days, frequency, monetary,
            r_score, f_score, m_score,
            rfm_tier, rfm_tier_en, segment_id,
            first_order_date, last_order_date, is_member, created_at
        ) {sql}
    """, params)

    return conn.execute(
        "SELECT COUNT(*) FROM user_rfm WHERE analysis_date = ? AND metric_type = ? AND lookback_days = ? AND channel = ?",
        [date_str, metric_type, lookback_days, channel],
    ).fetchone()[0]


def run_auto_preload(today: date = None) -> List[Tuple[str, int, str, int]]:
    """自动热点预加载，返回执行结果摘要。

    QW0 埋点：plan §A4.1 + plan §2 hot spot #1 — 540 组合串行循环
    入口/出口各打一次 perf_counter（通过 PerfTimer 上下文管理器）。
    """
    # QW0 埋点 — 入口 perf_counter
    _wall_start = time.perf_counter()
    _cpu_start = time.process_time()
    _extra = {"hot_dates": 0, "lookbacks": 0, "metrics": 0, "channels": 0, "total_tasks": 0}

    if today is None:
        today = date.today()

    hot_dates = get_hot_dates(today)
    lookbacks = [30, 90, 180]
    metrics = ["GMV", "GSV"]
    channels = ["全店"] + ACTIVE_UI_CHANNELS
    _extra.update(
        hot_dates=len(hot_dates),
        lookbacks=len(lookbacks),
        metrics=len(metrics),
        channels=len(channels),
    )

    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
    results = []
    try:
        total_tasks = len(hot_dates) * len(lookbacks) * len(metrics) * len(channels)
        _extra["total_tasks"] = total_tasks
        completed = 0
        for ch in channels:
            for d in hot_dates:
                for lb in lookbacks:
                    for mt in metrics:
                        try:
                            rows = preload_date(conn, d, lb, mt, ch)
                            conn.commit()
                            results.append((d.isoformat(), lb, mt, ch, rows))
                            completed += 1
                            print(f"[{completed}/{total_tasks}] {d} | {mt} | {lb}天 | {ch} => {rows:,} 行")
                        except Exception as e:
                            print(f"[ERROR] {d} | {mt} | {lb}天 | {ch} => {e}")
                            results.append((d.isoformat(), lb, mt, ch, -1))
    finally:
        conn.close()

    # QW0 埋点 — 出口 perf_counter（手动写 PerfRecord 以避免在 run_range_preload 也 import 不到时的失败）
    try:
        from scripts.etl._timer import PerfRecord, _RECORDS
        from datetime import datetime as _dt
        import resource as _res
        import platform as _plt
        _rusage = _res.getrusage(_res.RUSAGE_SELF).ru_maxrss
        if _plt.system() == "Darwin":
            _mem_kb = int(_rusage / 1024)
        else:
            _mem_kb = int(_rusage)
        _rec = PerfRecord(
            step_name="preload_rfm",
            timestamp=_dt.now().isoformat(),
            wall_time=time.perf_counter() - _wall_start,
            cpu_time=time.process_time() - _cpu_start,
            memory_peak_kb=_mem_kb,
            extra=_extra,
        )
        _RECORDS.append(_rec)
    except Exception:
        pass

    return results


def run_range_preload(start: date, end: date, step: int) -> List[Tuple[str, int, str, int]]:
    """按日期范围每隔 step 天预加载一次。"""
    lookbacks = [30, 90, 180]
    metrics = ["GMV", "GSV"]
    channels = ["全店"] + ACTIVE_UI_CHANNELS
    dates: List[date] = []
    cur = start
    while cur <= end:
        dates.append(cur)
        cur += timedelta(days=step)

    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
    results = []
    try:
        total = len(dates) * len(lookbacks) * len(metrics) * len(channels)
        completed = 0
        for ch in channels:
            for d in dates:
                for lb in lookbacks:
                    for mt in metrics:
                        try:
                            rows = preload_date(conn, d, lb, mt, ch)
                            conn.commit()
                            results.append((d.isoformat(), lb, mt, ch, rows))
                            completed += 1
                            print(f"[{completed}/{total}] {d} | {mt} | {lb}天 | {ch} => {rows:,} 行")
                        except Exception as e:
                            print(f"[ERROR] {d} | {mt} | {lb}天 | {ch} => {e}")
                            results.append((d.isoformat(), lb, mt, ch, -1))
    finally:
        conn.close()
    return results


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="RFM 热点日期预加载")
    parser.add_argument("--auto", action="store_true", help="自动计算常用周期节点")
    parser.add_argument("--date", type=str, help="指定单个日期 (YYYY-MM-DD)")
    parser.add_argument("--lookback", type=int, default=90, help="lookback_days")
    parser.add_argument("--metric", type=str, default="GMV", choices=["GMV", "GSV"], help="metric_type")
    parser.add_argument("--channel", type=str, default="全店", help="渠道名称（默认'全店'）")
    parser.add_argument("--range", nargs=2, metavar=("START", "END"), help="日期范围 (YYYY-MM-DD YYYY-MM-DD)")
    parser.add_argument("--step", type=int, default=7, help="范围模式下的步长(天)")

    args = parser.parse_args()

    if args.auto:
        print("=== 自动热点预加载开始 ===")
        results = run_auto_preload()
    elif args.date:
        d = date.fromisoformat(args.date)
        conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
        try:
            rows = preload_date(conn, d, args.lookback, args.metric, args.channel)
            conn.commit()
            print(f"{args.date} | {args.metric} | {args.lookback}天 | {args.channel} => {rows:,} 行")
        finally:
            conn.close()
        return
    elif args.range:
        start = date.fromisoformat(args.range[0])
        end = date.fromisoformat(args.range[1])
        print(f"=== 范围预加载: {start} ~ {end}, step={args.step}天 ===")
        results = run_range_preload(start, end, args.step)
    else:
        parser.print_help()
        return

    success = [r for r in results if r[4] > 0]
    failed = [r for r in results if r[4] == -1]
    print(f"\n=== 完成: 成功 {len(success)} 个任务, 失败 {len(failed)} 个任务 ===")


if __name__ == "__main__":
    main()
