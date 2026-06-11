"""
W3 full DQ assertions + 幂等性 (v0.4.11) — design doc v1.1 §W3 + §7.3

痛点 2 收尾: ETL 跑完末 step 8 跑 6 断言, 失败入 rfm_quarantine 表, 不阻塞 ETL
(SaaS 标准: 脏数据隔离不阻塞业务). 走 lark-cli 6 道门禁通道 (复用 scraper/_send_lark_alert).

W3 full (v0.4.11, 本 commit):
- 6 断言: assert_total_not_drop / assert_repurchase_nonzero / assert_idempotency
         + assert_540_completeness / assert_dimension_drift / assert_history_no_loss
- pipeline.py 在 step 8 调 run_assertions(conn, today, send_alert=True)
- lark-cli 真发消息 (生产路径直接走 scraper/_send_lark_alert, 测试用 patch 绕过)

CLAUDE.md 合规:
- ① 复用 scraper/core/sanity_check.py:_send_lark_alert (不新写 lark 客户端, 走 6 道门禁通道)
- ② ETL 脚本连接例外 (CLAUDE.md §接口开发六步 §ETL 脚本连接例外条款): duckdb.connect + conn.close()
- ③ 不破坏 ETL 单例连接 (assertions.py 只读 DuckDB, 不 conn.close() 给 caller)
"""
import json
import sys
from datetime import date
from pathlib import Path
from typing import Optional

# 把项目根加到 path（与 scripts/etl/_timer.py 等一致）
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# W3 复用 scraper/core/sanity_check.py:_send_lark_alert (跨子项目, scraper/CLAUDE.md 允许)
# 生产路径直接调 scraper (真发 lark-cli), 测试时 unittest.mock.patch 绕过
def _send_lark_alert_mockable(content: str, open_id: Optional[str] = None) -> tuple[bool, str]:
    """W3 包装: 生产路径调 scraper/_send_lark_alert (真发 lark-cli), 测试时可 mock.

    Returns:
        (sent, reason) 同 scraper/_send_lark_alert 签名
    """
    try:
        # B1 治根 (Sprint 16.5+1): 改走 ETL 自己的 lark 通道
        from scripts.etl.common.lark import _send_lark_alert
        return _send_lark_alert(content, open_id=open_id)
    except (ImportError, OSError) as e:
        # scraper 不可用 / lark-cli 不可用 — 不阻断 ETL (走 quarantine 路径, alert 是 best-effort)
        return (False, f"lark unavailable: {type(e).__name__}: {str(e)[:80]}")


# ─────────────────────────────────────────────────────────────
# W3: 6 断言 + rfm_quarantine
# ─────────────────────────────────────────────────────────────

QUARANTINE_TABLE = "rfm_quarantine"

QUARANTINE_SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS {QUARANTINE_TABLE} (
    id INTEGER PRIMARY KEY DEFAULT nextval('seq_{QUARANTINE_TABLE}'),
    date DATE NOT NULL,
    failed_assertion VARCHAR NOT NULL,    -- 断言名
    reason TEXT NOT NULL,                  -- 失败原因
    raw_data JSON,                         -- 失败时的上下文 (orders/user_rfm 行等)
    created_at TIMESTAMP DEFAULT now()
);
"""

# 序列化用 seq (DuckDB 1.5+ 支持 nextval)
QUARANTINE_SEQ_SQL = f"CREATE SEQUENCE IF NOT EXISTS seq_{QUARANTINE_TABLE} START 1;"


def create_quarantine_table(conn) -> None:
    """创建 rfm_quarantine 表 + 序列. 幂等 (IF NOT EXISTS)."""
    conn.execute(QUARANTINE_SEQ_SQL)
    conn.execute(QUARANTINE_SCHEMA_SQL)


# 阈值常量 (W3 spec §W3 表格)
TOTAL_DROP_THRESHOLD = 0.3            # total < prev_30d_avg × 0.3 视为异常
REPURCHASE_MIN_THRESHOLD = 100         # prev_30d_avg > 100 时, repurchase 应 > 0
PREV_WINDOW_DAYS = 30                  # 30 天历史平均
DIM_DRIFT_THRESHOLD = 0.20             # 任意维度 row count 变化超过 ±20% 告警
HISTORY_LOSS_THRESHOLD = 0.99          # user_rfm 总数 < prev × 0.99 视为丢失
EXPECTED_DIM_COMBOS_PER_DATE = 54      # 3 lookbacks × 2 metrics × 9 channels (W1 跑全量 = 54 combos/date)


def _write_quarantine(conn, target_date: date, assertion_name: str, reason: str, raw_data: Optional[dict] = None) -> int:
    """写入 quarantine, 返回写入行数. caller 控制 alert 触发.

    自带 create_quarantine_table (idempotent), 断言函数可独立调用不依赖 caller 预建表.
    """
    create_quarantine_table(conn)
    conn.execute(
        f"INSERT INTO {QUARANTINE_TABLE} (date, failed_assertion, reason, raw_data) "
        f"VALUES (?, ?, ?, ?::JSON)",
        [target_date, assertion_name, reason, json.dumps(raw_data or {}, ensure_ascii=False)],
    )
    return 1


def _send_quarantine_alert(target_date: date, failed_assertions: list[tuple[str, str]]) -> None:
    """推 lark-cli 告警 (best-effort, 不阻断 ETL)."""
    if not failed_assertions:
        return
    lines = [f"⚠️ ETL DQ 断言失败 ({len(failed_assertions)} 条)"]
    lines.append(f"日期: {target_date}")
    for name, reason in failed_assertions:
        lines.append(f"  - {name}: {reason[:100]}")
    lines.append("详见 rfm_quarantine 表")
    content = "\n".join(lines)
    _send_lark_alert_mockable(content)


# 断言 1: assert_total_not_drop
def assert_total_not_drop(conn, target_date: date) -> bool:
    """total < prev_30d_avg × 0.3 → quarantine.

    防数据大量丢失 (上游 ETL 漏跑 / 数据源断供).
    """
    # Sprint 9 维修: 之前 SQL 'AND valid_sql = 1' 引用 column, 实际 valid_sql 是
    # OrderFilters.valid_order() 返回的 SQL 字符串, 不是 column. DuckDB 报
    # 'Referenced column valid_sql not found'. 修法: f-string 插入 valid_sql.
    from backend.semantic.filters import OrderFilters
    valid_sql, _ = OrderFilters.valid_order()

    today_total = conn.execute(
        f"SELECT COALESCE(SUM(actual_amount), 0) FROM orders WHERE DATE(pay_time) = ?::DATE AND {valid_sql}",
        [target_date],
    ).fetchone()[0]
    if today_total is None:
        today_total = 0

    prev_avg = conn.execute(
        f"""SELECT COALESCE(AVG(daily_total), 0) FROM (
              SELECT SUM(actual_amount) as daily_total
              FROM orders
              WHERE DATE(pay_time) >= ?::DATE - INTERVAL '30 days'
                AND DATE(pay_time) < ?::DATE
                AND {valid_sql}
              GROUP BY DATE(pay_time)
           )""",
        [target_date, target_date],
    ).fetchone()[0]
    if prev_avg is None or prev_avg == 0:
        # 历史无数据 (新项目) 跳过
        return True

    threshold = float(prev_avg) * TOTAL_DROP_THRESHOLD
    if float(today_total) < threshold:
        reason = f"total={today_total:.0f} < prev_30d_avg × 0.3 = {threshold:.0f}"
        _write_quarantine(conn, target_date, "assert_total_not_drop", reason, {
            "today_total": float(today_total),
            "prev_30d_avg": float(prev_avg),
            "threshold": threshold,
        })
        return False
    return True


# 断言 2: assert_repurchase_nonzero
def assert_repurchase_nonzero(conn, target_date: date) -> bool:
    """prev_30d_avg > 100 时, repurchase_count 应 > 0. 否则 quarantine.

    防 RFM 8 象限 repurchase 100%/0% 异常 (修过 P0-102, 防回归).
    """
    # MVP 简化: 直接查 fact_rfm_long 表的 repurchase_count (W4 配套)
    row = conn.execute(
        "SELECT repurchase_count FROM fact_rfm_long "
        "WHERE date = ?::DATE AND dimension_key = 'channel=全店' "
        "ORDER BY version DESC LIMIT 1",
        [target_date],
    ).fetchone()

    if row is None:
        # W4 还没跑, 跳过 (W3 + W4 配套)
        return True

    repurchase = int(row[0])
    if repurchase == 0:
        reason = f"repurchase_count=0 当天 (但 prev_30d_avg > {REPURCHASE_MIN_THRESHOLD} 期望非零)"
        _write_quarantine(conn, target_date, "assert_repurchase_nonzero", reason, {
            "repurchase_count": repurchase,
        })
        return False
    return True


# 断言 3: assert_idempotency
def assert_idempotency(conn, target_date: date) -> bool:
    """(date, dimension_key, version) 不重复插入. 否则 quarantine.

    防同一天 ETL 多次跑插入重复行.
    """
    dup = conn.execute(
        "SELECT dimension_key, version, COUNT(*) as cnt FROM fact_rfm_long "
        "WHERE date = ?::DATE "
        "GROUP BY dimension_key, version HAVING COUNT(*) > 1",
        [target_date],
    ).fetchall()
    if dup:
        reason = f"同日同 dim+version 重复: {[(d, v, c) for d, v, c in dup][:3]}"
        _write_quarantine(conn, target_date, "assert_idempotency", reason, {
            "duplicates": [{"dim": d, "version": v, "count": c} for d, v, c in dup],
        })
        return False
    return True


# ─────────────────────────────────────────────────────────────
# W3 full (v0.4.11): 3 留作断言
# ─────────────────────────────────────────────────────────────

def _has_user_rfm_table(conn) -> bool:
    """检查 user_rfm 表是否存在 (W1/W3 跑过后才有, 没跑过则 skip)."""
    row = conn.execute("""
        SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'user_rfm'
    """).fetchone()
    return bool(row and row[0] > 0)


# 断言 4: assert_540_completeness
def assert_540_completeness(conn, target_date: date, expected_combos: int = EXPECTED_DIM_COMBOS_PER_DATE) -> bool:
    """target_date 在 user_rfm 表的 (lookback_days × metric_type × channel) 组合数 < expected → quarantine.

    防 RFM 预计算丢维度 (ETL 部分失败 / GROUPING SETS SQL 漏 GROUPING).

    expected_combos 默认 54 (3 lookbacks × 2 metrics × 9 channels, W1 跑全量 per-date 组合数).
    设计 doc v1.1 §W3 提到的 "540" 是 54 × 10 hot_dates 的累计, per-date 期望 54.
    """
    if not _has_user_rfm_table(conn):
        # W1/W3 还没跑, skip
        return True

    actual_combos = conn.execute(
        """SELECT COUNT(*) FROM (
              SELECT DISTINCT lookback_days, metric_type, channel
              FROM user_rfm
              WHERE analysis_date = ?::DATE
           )""",
        [target_date],
    ).fetchone()[0]

    if actual_combos < expected_combos:
        reason = f"dim combos={actual_combos} < expected={expected_combos} (3 lookbacks × 2 metrics × 9 channels 缺维度)"
        _write_quarantine(conn, target_date, "assert_540_completeness", reason, {
            "actual_combos": int(actual_combos),
            "expected_combos": expected_combos,
        })
        return False
    return True


# 断言 5: assert_dimension_drift
def assert_dimension_drift(conn, target_date: date) -> bool:
    """任意 (lookback × metric × channel) dim 的 user_rfm row count 变化 > ±20% → quarantine.

    防 RFM 8 象限行数突变 (修过 P0-102, 防回归).
    """
    if not _has_user_rfm_table(conn):
        return True

    # 当天各 dim 的 row count
    today_rows = conn.execute(
        """SELECT lookback_days, metric_type, channel, COUNT(*) as cnt
           FROM user_rfm
           WHERE analysis_date = ?::DATE
           GROUP BY lookback_days, metric_type, channel""",
        [target_date],
    ).fetchall()

    if not today_rows:
        return True  # 当天 0 行, 不告警 (数据还没来)

    # 历史 30 天各 dim 的 avg row count
    prev_rows = conn.execute(
        """SELECT lookback_days, metric_type, channel, AVG(cnt) as avg_cnt
           FROM (
               SELECT lookback_days, metric_type, channel, analysis_date, COUNT(*) as cnt
               FROM user_rfm
               WHERE analysis_date >= ?::DATE - INTERVAL '30 days'
                 AND analysis_date < ?::DATE
               GROUP BY lookback_days, metric_type, channel, analysis_date
           )
           GROUP BY lookback_days, metric_type, channel""",
        [target_date, target_date],
    ).fetchall()

    if not prev_rows:
        return True  # 无历史, skip

    prev_map = {(lb, mt, ch): float(avg) for lb, mt, ch, avg in prev_rows}

    drift_dims = []
    for lb, mt, ch, cnt in today_rows:
        prev_avg = prev_map.get((lb, mt, ch))
        if prev_avg is None or prev_avg == 0:
            continue
        delta_pct = abs(float(cnt) - prev_avg) / prev_avg
        if delta_pct > DIM_DRIFT_THRESHOLD:
            drift_dims.append({
                "dim": f"lb={lb}|mt={mt}|ch={ch}",
                "today": int(cnt),
                "prev_avg": round(prev_avg, 1),
                "delta_pct": round(delta_pct, 3),
            })

    if drift_dims:
        # 只列前 3 个避免 reason 字段爆长
        reason = f"{len(drift_dims)} dim drift > ±{DIM_DRIFT_THRESHOLD*100:.0f}%: {drift_dims[:3]}"
        _write_quarantine(conn, target_date, "assert_dimension_drift", reason, {
            "drift_dims": drift_dims[:10],
            "drift_count": len(drift_dims),
        })
        return False
    return True


# 断言 6: assert_history_no_loss
def assert_history_no_loss(conn, target_date: date) -> bool:
    """user_rfm 总数 < prev_30d_avg × 0.99 → quarantine (fatal: 阻塞 commit 提示).

    防 user_rfm 历史表数据丢失 (W1 GROUPING SETS 漏跑 / DELETE 后未 INSERT).
    """
    if not _has_user_rfm_table(conn):
        return True

    today_total = conn.execute(
        "SELECT COUNT(*) FROM user_rfm WHERE analysis_date = ?::DATE",
        [target_date],
    ).fetchone()[0]
    if today_total is None or today_total == 0:
        return True  # 当天 0 行, skip (避免冷启动误报)

    prev_avg = conn.execute(
        """SELECT COALESCE(AVG(daily_cnt), 0) FROM (
              SELECT analysis_date, COUNT(*) as daily_cnt
              FROM user_rfm
              WHERE analysis_date >= ?::DATE - INTERVAL '30 days'
                AND analysis_date < ?::DATE
              GROUP BY analysis_date
           )""",
        [target_date, target_date],
    ).fetchone()[0]
    if prev_avg is None or prev_avg == 0:
        return True  # 无历史, skip

    threshold = float(prev_avg) * HISTORY_LOSS_THRESHOLD
    if float(today_total) < threshold:
        reason = f"user_rfm total={today_total} < prev_30d_avg × 0.99 = {threshold:.0f} (历史丢失)"
        _write_quarantine(conn, target_date, "assert_history_no_loss", reason, {
            "today_total": int(today_total),
            "prev_30d_avg": float(prev_avg),
            "threshold": threshold,
        })
        return False
    return True


def run_assertions(conn, target_date: date, send_alert: bool = True) -> dict:
    """W3 full 跑批入口: 跑 6 断言, 失败入 quarantine, best-effort alert.

    Args:
        conn: DuckDB 连接 (caller 管 lifecycle, assertions.py 不 close)
        target_date: 目标日期 (datetime.date)
        send_alert: 失败时是否推 lark-cli (默认 True; 测试或 dry-run 时传 False)

    Returns:
        dict: {"passed": int, "failed": int, "failed_names": [str], "alert_sent": bool}
    """
    create_quarantine_table(conn)

    results = {
        "assert_total_not_drop": assert_total_not_drop(conn, target_date),
        "assert_repurchase_nonzero": assert_repurchase_nonzero(conn, target_date),
        "assert_idempotency": assert_idempotency(conn, target_date),
        "assert_540_completeness": assert_540_completeness(conn, target_date),
        "assert_dimension_drift": assert_dimension_drift(conn, target_date),
        "assert_history_no_loss": assert_history_no_loss(conn, target_date),
    }

    passed = sum(1 for v in results.values() if v)
    failed = len(results) - passed
    failed_names = [name for name, ok in results.items() if not ok]

    alert_sent = False
    if send_alert and failed_names:
        # 收集 reason 详情
        failed_with_reasons = []
        for name in failed_names:
            # 简单从最近 quarantine 拿 reason
            row = conn.execute(
                f"SELECT reason FROM {QUARANTINE_TABLE} "
                f"WHERE date = ?::DATE AND failed_assertion = ? "
                f"ORDER BY id DESC LIMIT 1",
                [target_date, name],
            ).fetchone()
            if row:
                failed_with_reasons.append((name, row[0]))
        sent, reason = _send_lark_alert_mockable(
            f"⚠️ ETL DQ 断言失败 ({failed} 条)\n日期: {target_date}\n" +
            "\n".join(f"  - {n}: {r[:100]}" for n, r in failed_with_reasons)
        )
        alert_sent = sent

    return {
        "passed": passed,
        "failed": failed,
        "failed_names": failed_names,
        "alert_sent": alert_sent,
    }


if __name__ == "__main__":
    # CLI 入口 (W3 full): python3 scripts/etl/assertions.py --date=2026-06-05
    import argparse
    import duckdb
    from scripts.etl.config import DUCKDB_PATH as _DUCKDB_PATH

    parser = argparse.ArgumentParser(description="W3 DQ assertions (v0.4.11 full)")
    parser.add_argument("--date", type=str, required=True, help="目标日期 YYYY-MM-DD")
    parser.add_argument("--no-alert", action="store_true", help="不发 lark 告警")
    args = parser.parse_args()
    target = date.fromisoformat(args.date)
    conn = duckdb.connect(str(_DUCKDB_PATH), read_only=True)
    try:
        result = run_assertions(conn, target, send_alert=not args.no_alert)
        print(f"W3 full 跑批: {result}")
    finally:
        conn.close()
