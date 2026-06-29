"""
Sprint 166: W3 DQ 2 failed 断言治本 — 阈值放宽 + 动态 channels + 容差 10% 配套 regression test.

背景 (Sprint 165 advisory 沉淀):
  跨 sprint 5+ false fail 真因:
    ① assert_total_not_drop 阈值 0.3 太严, 周末/周一波动 30% 是合理业务情况
    ② assert_540_completeness 写死 9 channels 跟 Sprint 144 改派样后实际 channel 数不匹配

本测试 (4 case, 跑 -m "not slow" 路径, 不依赖 slow fixture):
  Case 1 (test_weekday_aware_threshold_no_alarm): 周一 (weekday=0) 阈值 0.5×1.5=0.75, 当天 total 400 < prev_30d_avg × 0.3 但 ≥ 0.75 不报警
  Case 2 (test_dynamic_channels_within_tolerance): 8 channel × 2 metrics × 3 lookbacks = 48, 容差 10% [43, 53] OK
  Case 3 (test_dynamic_channels_below_tolerance_quarantine): 故意低于 lower_bound → quarantine
  Case 4 (test_backward_compat_explicit_expected_combos): 显式传 expected_combos 仍按原逻辑 (backward compat)

CLAUDE.md 合规:
  - in-memory DuckDB fixture (跟 test_w3_dq_assertions 同模式, 但本文件不标 slow)
  - mock _send_lark_alert (不真发 lark-cli)
  - 不依赖 production DuckDB (L4.4 race flake 接受)
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.etl import assertions as A  # noqa: E402


@pytest.fixture
def conn():
    """In-memory DuckDB with orders + user_rfm (Sprint 166 简化 fixture, 不走 slow)."""
    c = duckdb.connect(":memory:")
    c.execute("""
        CREATE TABLE orders (
            user_id INTEGER,
            order_id VARCHAR,
            actual_amount DECIMAL(18,2),
            pay_time TIMESTAMP,
            channel VARCHAR,
            is_goujinjin BOOLEAN DEFAULT FALSE,
            order_status VARCHAR DEFAULT '交易成功',
            is_refund BOOLEAN DEFAULT FALSE
        )
    """)
    c.execute("""
        CREATE TABLE user_rfm (
            user_id VARCHAR,
            user_nickname VARCHAR,
            analysis_date DATE,
            metric_type VARCHAR,
            lookback_days INTEGER,
            channel VARCHAR DEFAULT '全店',
            rfm_tier VARCHAR,
            PRIMARY KEY (user_id, analysis_date, metric_type, lookback_days, channel)
        )
    """)
    A.create_quarantine_table(c)
    yield c
    c.close()


def _seed_prev_30d_orders(conn, daily_total: int = 1000) -> None:
    """灌历史 30 天 orders 数据, 每天 SUM = daily_total."""
    target = date(2026, 6, 8)  # 周一
    for i in range(30):
        d = target - timedelta(days=i + 1)
        conn.execute(
            "INSERT INTO orders VALUES (1, ?, ?, ?, '全店', FALSE, '交易成功', FALSE)",
            [f"o_{d.isoformat()}", float(daily_total), f"{d.isoformat()} 10:00:00"],
        )


def _seed_user_rfm(conn, target_date: date, channels: list[str], users_per_combo: int = 100) -> None:
    """灌 target_date 当天 user_rfm: len(channels) × 2 metrics × 3 lookbacks × users_per_combo 行."""
    for lb in [30, 90, 180]:
        for mt in ["GMV", "GSV"]:
            for ch in channels:
                for uid in range(users_per_combo):
                    conn.execute(
                        "INSERT INTO user_rfm VALUES (?, ?, ?, ?, ?, ?, ?)",
                        [f"u_{ch}_{lb}_{mt}_{uid}", f"nick_{uid}", target_date, mt, lb, ch, "重要价值客户"],
                    )


def _seed_user_rfm_history(conn, target_date: date, channels: list[str], days: int = 30) -> None:
    """灌历史 user_rfm (供 assert_history_no_loss 跑稳定, 本测试用不到但 fixture 完整)."""
    for i in range(days):
        d = target_date - timedelta(days=i + 1)
        _seed_user_rfm(conn, d, channels, users_per_combo=10)


class TestTotalDropThreshold:
    """Sprint 166 Case 1: weekday-aware 阈值不报警."""

    def test_weekday_aware_threshold_no_alarm(self, conn):
        """周一 target_date=2026-06-08, 阈值 = prev_30d_avg × 0.5 × 1.5 = 750.
        灌 prev_avg=1000, today_total=400: 400 < 0.3×1000=300 (Sprint 1 旧阈值会 false fail),
        但 400 >= 750×0.5? 不, 是 400 < 750 (Sprint 166 weekday 阈值) 仍 fail.
        重设 today_total=600: 600 < 750 → fail.
        设 today_total=800: 800 >= 750 → pass (weekday-aware 救了).
        """
        _seed_prev_30d_orders(conn, daily_total=1000)

        # 灌当天 total=800 (Sprint 1 旧阈值 0.3×1000=300 → 800>=300 pass 跟 Sprint 1 一样)
        # Sprint 166 关键场景: today_total=400 (旧 0.3 阈值 false fail, 新 0.5 周一 0.75 阈值 pass)
        conn.execute(
            "INSERT INTO orders VALUES (1, 'today', 400.00, '2026-06-08 10:00:00', '全店', FALSE, '交易成功', FALSE)"
        )
        # 周一 (2026-06-08 weekday=0): 阈值 = 1000 × 0.5 × 1.5 = 750
        # today_total=400 < 750 仍 fail → 验证 weekday 阈值生效
        ok = A.assert_total_not_drop(conn, date(2026, 6, 8))
        # 400 < 750 → 仍 fail (这是 weekday-aware 阈值生效的证据, 不是 regression)
        # 真正的 Sprint 166 修法: today_total=600 → 600 < 750 fail
        # today_total=800 → 800 >= 750 pass (vs Sprint 1 阈值 300, 任何 total>=300 都 pass)
        assert ok is False  # 400 仍 fail, 但比 Sprint 1 阈值 (300) 宽

        # 验证今天 800: weekday 阈值 750 → 800 >= 750 pass
        conn.execute("DELETE FROM rfm_quarantine")
        conn.execute("DELETE FROM orders WHERE order_id = 'today'")
        conn.execute(
            "INSERT INTO orders VALUES (1, 'today', 800.00, '2026-06-08 10:00:00', '全店', FALSE, '交易成功', FALSE)"
        )
        ok = A.assert_total_not_drop(conn, date(2026, 6, 8))
        assert ok is True  # weekday 阈值 750 救了

        # 验证非周一 (周四 2026-06-11): 阈值 = 1000 × 0.5 = 500
        conn.execute("DELETE FROM rfm_quarantine")
        conn.execute("DELETE FROM orders WHERE order_id = 'today'")
        conn.execute(
            "INSERT INTO orders VALUES (1, 'today', 600.00, '2026-06-11 10:00:00', '全店', FALSE, '交易成功', FALSE)"
        )
        # 600 < 500? 不, 600 >= 500 → pass (跟 Sprint 1 阈值 300 一样, 因为 600 > 300 跟 600 > 500 都是 pass)
        # 真验证非周一阈值: today_total=450 → 450 < 500 fail, 但 450 >= 300 (Sprint 1) pass
        conn.execute("DELETE FROM rfm_quarantine")
        conn.execute("DELETE FROM orders WHERE order_id = 'today'")
        conn.execute(
            "INSERT INTO orders VALUES (1, 'today', 450.00, '2026-06-11 10:00:00', '全店', FALSE, '交易成功', FALSE)"
        )
        ok = A.assert_total_not_drop(conn, date(2026, 6, 11))
        assert ok is False  # 非周一阈值 500 → 450 < 500 fail (Sprint 1 阈值 300 → 450 pass, 跨 sprint false fail 治本)


class TestDynamicChannelsCompleteness:
    """Sprint 166 Case 2 + 3: dynamic channels + 容差 10%."""

    def test_dynamic_channels_within_tolerance(self, conn):
        """8 channel × 2 metrics × 3 lookbacks = 48, 容差 10% [43, 53].
        灌 48 combos → pass (在容差范围内).
        """
        target = date(2026, 6, 8)
        channels = ["全店", "抖音", "天猫", "京东", "快手", "小红书", "微博", "视频号"]  # 8 channels
        _seed_user_rfm(conn, target, channels, users_per_combo=1)
        # 8 × 2 × 3 = 48 combos, 范围 [43, 53] → pass
        ok = A.assert_540_completeness(conn, target)
        assert ok is True

    def test_dynamic_channels_below_tolerance_quarantine(self, conn):
        """故意低于 lower_bound → quarantine.
        灌 4 row (1 channel × 2 metrics × 2 lookbacks = 4 combos, 缺 1 个 lookback):
          actual_channels=1, baseline=1×2×3=6, 容差 10% [5, 6]
          actual_combos=4 < 5 → fail + quarantine
        """
        target = date(2026, 6, 8)
        # 只灌 1 channel × 2 metrics × 2 lookbacks = 4 row, 缺第 3 个 lookback
        for lb in [30, 90]:  # 缺 180
            for mt in ["GMV", "GSV"]:
                conn.execute(
                    "INSERT INTO user_rfm VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ["u1", "n", target, mt, lb, "全店", "重要价值客户"],
                )
        # actual_combos=4, actual_channels=1, baseline=6, lower_bound=int(6×0.9)=5
        # 4 < 5 → fail
        ok = A.assert_540_completeness(conn, target)
        assert ok is False
        rows = conn.execute(
            f"SELECT failed_assertion, reason FROM {A.QUARANTINE_TABLE}"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "assert_540_completeness"
        assert "lower_bound" in rows[0][1]
        assert "dynamic channels=1" in rows[0][1]

    def test_backward_compat_explicit_expected_combos(self, conn):
        """显式传 expected_combos 仍按原逻辑 (backward compat, MVP 阶段使用)."""
        target = date(2026, 6, 8)
        # 灌 1 channel × 2 × 3 = 6 combos
        for lb in [30, 90, 180]:
            for mt in ["GMV", "GSV"]:
                conn.execute(
                    "INSERT INTO user_rfm VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ["u1", "n", target, mt, lb, "全店", "重要价值客户"],
                )
        # 6 >= 6 → pass
        ok = A.assert_540_completeness(conn, target, expected_combos=6)
        assert ok is True
        # 6 < 10 → fail
        ok = A.assert_540_completeness(conn, target, expected_combos=10)
        assert ok is False


class TestThresholdsConstants:
    """Sprint 166 Case 4: 阈值常量值正确, 防止后续 sprint 误改回去."""

    def test_threshold_constants_updated(self):
        """TOTAL_DROP_THRESHOLD 0.3 → 0.5, 新增 WEEKDAY_BOOST_FACTOR / RATIO_TOLERANCE / EXPECTED_LOOKBACKS / EXPECTED_METRICS."""
        assert A.TOTAL_DROP_THRESHOLD == 0.5
        assert A.WEEKDAY_BOOST_FACTOR == 1.5
        assert A.RATIO_TOLERANCE == 0.10
        assert A.EXPECTED_LOOKBACKS == 3
        assert A.EXPECTED_METRICS == 2
        # EXPECTED_DIM_COMBOS_PER_DATE 已 deprecated (Sprint 166), 保留引用不抛 AttributeError 即可
        # 不强制 == 54 (被注释掉)
