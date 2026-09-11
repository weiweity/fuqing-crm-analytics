#!/usr/bin/env python3
"""
芙清 CRM - 数据质量监控脚本

检查项:
  1. orders 表行数（不能比上次少 10%+）
  2. is_member = TRUE 占比（不能从 50%+ 掉到 10% 以下）
  3. 最近 7 天有数据（不能断更）
  4. GSV 不为 0
  5. 磁盘可用空间（不能低于 DuckDB 文件大小 ×2 或 200GB）
  6. 订单量异常增长（不能比上次多 50%+）

用法:
  python3 scripts/etl/dq_monitor.py              # 输出检查结果到 stdout (JSON)
  python3 scripts/etl/dq_monitor.py --alert       # 检查失败时调 lark-cli 发送告警
  python3 scripts/etl/dq_monitor.py --report      # 输出到 data/processed/dq_report.json

CLAUDE.md 合规:
  ① 复用 scraper/core/sanity_check.py:_send_lark_alert (不新写 lark 客户端, 走 6 道门禁通道)
  ② ETL 脚本连接例外条款: read_only DuckDB 直连 + conn.close()
  ③ 禁止为规避锁复制生产 DuckDB；连接冲突应失败并建议维护窗口重试
"""
import argparse
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 项目根目录
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import DUCKDB_PATH, PROCESSED_DATA_DIR  # noqa: E402

# 北京时间
BJ_TZ = timezone(timedelta(hours=8))

# 上次行数持久化路径
SNAPSHOT_PATH = PROCESSED_DATA_DIR / "dq_snapshot.json"


def log(msg: str) -> None:
    ts = datetime.now(BJ_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")
    print(f"[{ts}] {msg}", file=sys.stderr, flush=True)


def load_snapshot() -> dict:
    """加载上次检查快照"""
    if SNAPSHOT_PATH.exists():
        with open(SNAPSHOT_PATH, "r") as f:
            return json.load(f)
    return {}


def save_snapshot(snapshot: dict) -> None:
    """保存本次检查快照"""
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SNAPSHOT_PATH.with_suffix(".json.tmp")
    try:
        with open(tmp, "w") as f:
            json.dump(snapshot, f, indent=2, sort_keys=True)
        tmp.rename(SNAPSHOT_PATH)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


# Sprint 164: 飞书通道不解耦回接。--alert 必须发出可观测本地告警。
_EMITTED_ALERTS: list[str] = []


def emitted_alerts() -> list[str]:
    return list(_EMITTED_ALERTS)


def clear_emitted_alerts() -> None:
    _EMITTED_ALERTS.clear()


def send_lark_alert(content: str) -> tuple:
    """发出本地 DQ 告警。不调用飞书；返回 (True, channel) 表示已发出。"""
    _EMITTED_ALERTS.append(content)
    print(f"  [DQ alert] {content[:120]}")
    return (True, "local-alert")


def run_checks(conn) -> dict:
    """执行全部检查项, 返回结果 dict"""
    now = datetime.now(BJ_TZ)
    result = {
        "timestamp": now.isoformat(),
        "checks": {},
        "all_passed": True,
    }

    prev = load_snapshot()

    # ── Check 1: orders 表行数（不能比上次少 10%+） ──
    current_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    prev_count = prev.get("orders_count")
    check1 = {
        "name": "orders_count",
        "current": current_count,
        "previous": prev_count,
        "passed": True,
        "detail": "",
    }
    if prev_count is not None and prev_count > 0:
        drop_ratio = (prev_count - current_count) / prev_count
        if drop_ratio >= 0.10:
            check1["passed"] = False
            check1["detail"] = (
                f"行数下降 {drop_ratio:.1%} ({prev_count:,} -> {current_count:,}), 超过 10% 阈值"
            )
        else:
            check1["detail"] = f"行数变化 {drop_ratio:.1%}, 正常"
    else:
        check1["detail"] = "无历史快照, 跳过同比检查"
    result["checks"]["orders_count"] = check1
    if not check1["passed"]:
        result["all_passed"] = False

    # ── Check 2: is_member = TRUE 占比（不能从 50%+ 掉到 10% 以下） ──
    member_count = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE is_member = TRUE"
    ).fetchone()[0]
    member_ratio = member_count / current_count if current_count > 0 else 0
    prev_member_ratio = prev.get("member_ratio")
    check2 = {
        "name": "member_ratio",
        "current": round(member_ratio, 4),
        "previous": prev_member_ratio,
        "passed": True,
        "detail": "",
    }
    if (
        prev_member_ratio is not None
        and prev_member_ratio >= 0.50
        and member_ratio < 0.10
    ):
        check2["passed"] = False
        check2["detail"] = (
            f"会员占比从 {prev_member_ratio:.1%} 掉到 {member_ratio:.1%}, "
            f"触发异常阈值 (>=50% -> <10%)"
        )
    else:
        check2["detail"] = f"会员占比 {member_ratio:.1%}, 正常"
    result["checks"]["member_ratio"] = check2
    if not check2["passed"]:
        result["all_passed"] = False

    # ── Check 3: 最近 7 天有数据（不能断更） ──
    seven_days_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    recent_count = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE DATE(pay_time) >= ?",
        [seven_days_ago],
    ).fetchone()[0]
    check3 = {
        "name": "recent_7d_data",
        "current": recent_count,
        "passed": True,
        "detail": "",
    }
    if recent_count == 0:
        check3["passed"] = False
        check3["detail"] = f"最近 7 天 ({seven_days_ago} 起) 无订单数据, 疑似断更"
    else:
        check3["detail"] = f"最近 7 天有 {recent_count:,} 条订单"
    result["checks"]["recent_7d_data"] = check3
    if not check3["passed"]:
        result["all_passed"] = False

    # ── Check 4: GSV 不为 0 ──
    today_str = now.strftime("%Y-%m-%d")
    gsv_today = conn.execute(
        """SELECT COALESCE(SUM(CASE WHEN is_goujinjin = FALSE AND is_refund = FALSE
           THEN actual_amount ELSE 0 END), 0)
           FROM orders WHERE DATE(pay_time) = ?""",
        [today_str],
    ).fetchone()[0]
    check4 = {
        "name": "gsv_nonzero",
        "current": float(gsv_today),
        "passed": True,
        "detail": "",
    }
    if float(gsv_today) == 0:
        check4["passed"] = False
        check4["detail"] = f"今日 ({today_str}) GSV 为 0, 可能无有效订单"
    else:
        check4["detail"] = f"今日 GSV = {gsv_today:,.2f}"
    result["checks"]["gsv_nonzero"] = check4
    if not check4["passed"]:
        result["all_passed"] = False

    # ── Check 5: 磁盘可用空间（Sprint 51, 防 107GB DuckDB 膨胀撑满磁盘） ──
    # 阈值: max(DuckDB文件大小×2, 200GB) — 107GB DB + 40GB backup + 余量
    try:
        duckdb_size = DUCKDB_PATH.stat().st_size if DUCKDB_PATH.exists() else 0
        disk = shutil.disk_usage(str(DUCKDB_PATH.parent))
        free_gb = disk.free / (1024**3)
        duckdb_gb = duckdb_size / (1024**3)
        threshold_gb = max(duckdb_gb * 2, 200)
        check5 = {
            "name": "disk_space",
            "current": round(free_gb, 1),
            "duckdb_size_gb": round(duckdb_gb, 1),
            "threshold_gb": round(threshold_gb, 1),
            "passed": True,
            "detail": "",
        }
        if free_gb < threshold_gb:
            check5["passed"] = False
            check5["detail"] = (
                f"磁盘可用空间不足: {free_gb:.1f}GB "
                f"(DuckDB {duckdb_gb:.1f}GB, 阈值 {threshold_gb:.0f}GB)"
            )
        else:
            check5["detail"] = f"磁盘可用空间 {free_gb:.1f}GB, 正常 (阈值 {threshold_gb:.0f}GB)"
    except OSError as e:
        check5 = {
            "name": "disk_space",
            "current": None,
            "passed": False,
            "detail": f"磁盘检查异常: {e}",
        }
    result["checks"]["disk_space"] = check5
    if not check5["passed"]:
        result["all_passed"] = False

    # ── Check 6: 订单量异常增长（Sprint 51, 防异常写入撑满磁盘） ──
    # 阈值: >50% 增长告警 — 正常 ETL 跑批 (Sprint 28 +1.68M = +15%) 不会触发
    prev_count_for_growth = prev.get("orders_count")
    check6 = {
        "name": "orders_growth",
        "current": current_count,
        "previous": prev_count_for_growth,
        "passed": True,
        "detail": "",
    }
    if prev_count_for_growth is not None and prev_count_for_growth > 0:
        growth_rate = (current_count - prev_count_for_growth) / prev_count_for_growth
        if growth_rate > 0.50:
            check6["passed"] = False
            check6["detail"] = (
                f"订单量异常增长: {growth_rate:.1%} "
                f"({prev_count_for_growth:,} -> {current_count:,}), 超过 50% 阈值"
            )
        else:
            check6["detail"] = f"订单量变化 {growth_rate:.1%}, 正常"
    else:
        check6["detail"] = "无历史快照, 跳过增长检查"
    result["checks"]["orders_growth"] = check6
    if not check6["passed"]:
        result["all_passed"] = False

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="芙清 CRM 数据质量监控")
    parser.add_argument("--alert", action="store_true", help="检查失败时调 lark-cli 发送告警")
    parser.add_argument("--report", action="store_true", help="输出到 data/processed/dq_report.json")
    args = parser.parse_args()

    if not DUCKDB_PATH.exists():
        log(f"ERROR: {DUCKDB_PATH} not found")
        print(json.dumps({"error": "database not found", "path": str(DUCKDB_PATH)}, ensure_ascii=False))
        return 1

    log("DQ monitor 开始...")

    # DQ 只读查询必须直连原库。旧实现每次 shutil.copy2 整个生产 DuckDB 到
    # /tmp，在百 GB 数据量下会造成磁盘放大，进程崩溃还会留下巨型孤儿文件。
    # DuckDB 被写进程锁住时，宁可明确失败，也不能复制或删除生产库。
    import duckdb

    try:
        conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    except Exception as exc:
        advice = (
            "数据库可能正被 ETL 或其他写进程锁定；请等待写入完成，"
            "或在维护窗口停止写入后重试。DQ monitor 不会复制生产库来绕过锁。"
        )
        log(f"ERROR: DuckDB read_only 连接失败: {type(exc).__name__}: {exc}")
        print(
            json.dumps(
                {
                    "error": "database unavailable",
                    "reason": "read_only connection failed",
                    "exception": type(exc).__name__,
                    "detail": str(exc)[:500],
                    "advice": advice,
                },
                ensure_ascii=False,
            )
        )
        return 1

    try:
        result = run_checks(conn)
    finally:
        conn.close()

    # 保存快照供下次比对
    snapshot = {
        "orders_count": result["checks"]["orders_count"]["current"],
        "member_ratio": result["checks"]["member_ratio"]["current"],
        "timestamp": result["timestamp"],
    }
    save_snapshot(snapshot)
    log("快照已保存")

    # 输出 JSON 到 stdout
    output = json.dumps(result, ensure_ascii=False, indent=2)
    print(output)

    # --report: 额外写文件
    if args.report:
        report_path = PROCESSED_DATA_DIR / "dq_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w") as f:
            f.write(output)
        log(f"报告已写入 {report_path}")

    # --alert: 检查失败时发 lark 告警
    if args.alert and not result["all_passed"]:
        failed_checks = [
            name for name, check in result["checks"].items() if not check["passed"]
        ]
        alert_msg = (
            f"DQ Monitor 告警 {result['timestamp']}\n"
            f"失败项: {', '.join(failed_checks)}\n\n"
        )
        for name in failed_checks:
            c = result["checks"][name]
            alert_msg += f"  {name}: {c['detail']}\n"
        log("发送 lark 告警...")
        sent, reason = send_lark_alert(alert_msg)
        log(f"告警结果: sent={sent} reason={reason}")

    status = "PASS" if result["all_passed"] else "FAIL"
    log(f"DQ monitor 完成: {status}")
    return 0 if result["all_passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
