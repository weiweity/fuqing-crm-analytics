# -*- coding: utf-8 -*-
"""
test_ad_hoc_query_sprint61plus.py — Sprint 61+ (yoy-battle + channel-slice) regression test.

设计:
- 复用 Sprint 61 tmp_duckdb fixture 模式 (production data 隔离)
- 5 case 业务 + 1 case 端到端 CLI
- 跟 test_ad_hoc_query.py 同模式, pytest 收口一并跑

Cases:
  1: yoy_battle basic — 双窗口 4 metric (all) 输出对齐 headers
  2: yoy_battle metric=single — 只输出 gsv 行
  3: yoy_battle window 校验 — 窗口 > 366d → ValueError
  4: channel_slice basic — 多 channel + 全店 第一行
  5: channel_slice compare=yoy — 加 yoy_pct 列
  6: 端到端 CLI — 跑真 subprocess 验 argparse + table 输出
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AD_HOC_PY = PROJECT_ROOT / "scripts" / "ad_hoc_query.py"


# ─────────────────────────────────────────────────────────────
# fixture: 临时 DuckDB (跟 test_ad_hoc_query.py 同步 + 加 channel 多样性)
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def tmp_duckdb_rich(tmp_path, monkeypatch):
    """
    造一个最小 DuckDB, 写 5 天 2026 + 5 天 2025 + 多个 channel 数据,
    覆盖 yoy_battle (双窗口) + channel_slice (多 channel) 的测试场景.
    """
    db_path = tmp_path / "test_crm_rich.duckdb"
    c = duckdb.connect(str(db_path))
    c.execute("""
        CREATE TABLE orders (
            pay_time TIMESTAMP,
            actual_amount DOUBLE,
            is_goujinjin BOOLEAN,
            is_refund BOOLEAN,
            order_status VARCHAR,
            user_id VARCHAR,
            store_id VARCHAR,
            channel VARCHAR
        )
    """)
    # 2026-06-01 ~ 06-05 (5 天, 多个 channel)
    # 跟 yoy_battle baseline 比的 cur 段
    rows_2026 = [
        # 2026-06-01 — 货架/达播/直播/淘客/微博
        (datetime(2026, 6, 1, 10, 0, 0), 10_000_000.0, "u1", "货架"),
        (datetime(2026, 6, 1, 11, 0, 0), 5_000_000.0, "u2", "达播"),
        (datetime(2026, 6, 1, 12, 0, 0), 3_000_000.0, "u3", "直播"),
        (datetime(2026, 6, 1, 13, 0, 0), 2_000_000.0, "u4", "淘客"),
        (datetime(2026, 6, 1, 14, 0, 0), 1_000_000.0, "u5", "微博"),
        # 2026-06-02 — 加 U先派样
        (datetime(2026, 6, 2, 10, 0, 0), 8_000_000.0, "u1", "货架"),
        (datetime(2026, 6, 2, 11, 0, 0), 4_000_000.0, "u2", "达播"),
        (datetime(2026, 6, 2, 12, 0, 0), 500_000.0, "u6", "U先派样"),
    ]
    # 2025-06-01 ~ 06-05 (5 天, 去年同期, YOY 验证用)
    # 比 2026 小 30%, 验证 +30% YOY
    rows_2025 = [
        (datetime(2025, 6, 1, 10, 0, 0), 7_000_000.0, "u1", "货架"),
        (datetime(2025, 6, 1, 11, 0, 0), 3_500_000.0, "u2", "达播"),
        (datetime(2025, 6, 1, 12, 0, 0), 2_500_000.0, "u3", "直播"),
        (datetime(2025, 6, 2, 10, 0, 0), 6_000_000.0, "u1", "货架"),
        (datetime(2025, 6, 2, 11, 0, 0), 3_000_000.0, "u2", "达播"),
    ]
    for pt, amt, uid, ch in rows_2026 + rows_2025:
        c.execute(
            "INSERT INTO orders VALUES (?, ?, FALSE, FALSE, '交易成功', ?, 's1', ?)",
            [pt, amt, uid, ch],
        )
    c.close()
    # 关键: 把 DUCKDB_PATH 指向 tmp
    from backend import config as _config
    monkeypatch.setattr(_config, "DUCKDB_PATH", db_path)
    from scripts.ad_hoc_queries import _utils
    monkeypatch.setattr(_utils, "DUCKDB_PATH", db_path)
    return db_path


# ─────────────────────────────────────────────────────────────
# Case 1: yoy_battle basic — 双窗口 4 metric (all)
# ─────────────────────────────────────────────────────────────
def test_yoy_battle_all_metrics(tmp_duckdb_rich):
    """
    baseline 2025-06-01~02 vs current 2026-06-01~02:
    - 2025 段: 2025-06-01 + 2025-06-02
        gsv: 7M + 3.5M + 2.5M + 6M + 3M = 22M
        orders: 5
        customers: u1, u2, u3 = 3 distinct
    - 2026 段: 2026-06-01 + 2026-06-02
        gsv: 10M + 5M + 3M + 2M + 1M + 8M + 4M + 0.5M = 33.5M
        orders: 8
        customers: u1, u2, u3, u4, u5, u6 = 6 distinct
    - aov = gsv / orders
    """
    from scripts.ad_hoc_queries.yoy_battle import run_yoy_battle

    rows = run_yoy_battle(
        baseline_start="2025-06-01",
        baseline_end="2025-06-02",
        current_start="2026-06-01",
        current_end="2026-06-02",
    )
    assert len(rows) == 4
    by_metric = {r[0]: r for r in rows}

    # gsv: 22M → 33.5M, diff = +11.5M, yoy = +52.27%
    assert by_metric["gsv"][1] == 22_000_000
    assert by_metric["gsv"][2] == 33_500_000
    assert by_metric["gsv"][3] == "+11500000"
    assert by_metric["gsv"][4] == "+52.27%"

    # orders: 5 → 8
    assert by_metric["orders"][1] == 5
    assert by_metric["orders"][2] == 8
    assert by_metric["orders"][3] == "+3"
    assert by_metric["orders"][4] == "+60.00%"

    # customers: 3 → 6
    assert by_metric["customers"][1] == 3
    assert by_metric["customers"][2] == 6
    assert by_metric["customers"][3] == "+3"
    assert by_metric["customers"][4] == "+100.00%"

    # aov: 22M/5=4.4M, 33.5M/8=4.1875M, diff=-0.2125M, yoy=-4.83%
    # safe_ratio 默认 0.0, 实际计算: 22000000/5 = 4400000.0
    aov_bl = float(by_metric["aov"][1])
    aov_cu = float(by_metric["aov"][2])
    assert abs(aov_bl - 4_400_000.0) < 0.01
    assert abs(aov_cu - 4_187_500.0) < 0.01


# ─────────────────────────────────────────────────────────────
# Case 2: yoy_battle single metric
# ─────────────────────────────────────────────────────────────
def test_yoy_battle_single_metric(tmp_duckdb_rich):
    """只输出 gsv 1 行."""
    from scripts.ad_hoc_queries.yoy_battle import run_yoy_battle

    rows = run_yoy_battle(
        baseline_start="2025-06-01",
        baseline_end="2025-06-01",
        current_start="2026-06-01",
        current_end="2026-06-01",
        metric="gsv",
    )
    assert len(rows) == 1
    assert rows[0][0] == "gsv"
    # 2025-06-01: 7M + 3.5M + 2.5M = 13M
    # 2026-06-01: 10M + 5M + 3M + 2M + 1M = 21M
    assert rows[0][1] == 13_000_000
    assert rows[0][2] == 21_000_000
    # yoy = (21-13)/13 = 61.54%
    assert rows[0][4] == "+61.54%"


# ─────────────────────────────────────────────────────────────
# Case 3: yoy_battle 窗口校验
# ─────────────────────────────────────────────────────────────
def test_yoy_battle_invalid_window(tmp_duckdb_rich):
    """current 窗口 > 366d → ValueError."""
    from scripts.ad_hoc_queries.yoy_battle import run_yoy_battle

    with pytest.raises(ValueError, match="current 窗口.*366d"):
        run_yoy_battle(
            baseline_start="2024-01-01",
            baseline_end="2024-12-31",
            current_start="2025-01-01",
            current_end="2026-12-31",
        )


# ─────────────────────────────────────────────────────────────
# Case 4: channel_slice basic — 多 channel + 全店 第一行
# ─────────────────────────────────────────────────────────────
def test_channel_slice_basic(tmp_duckdb_rich):
    """2026-06-01 全店 + 5 个 channel, 全店排第一."""
    from scripts.ad_hoc_queries.channel_slice import run_channel_slice

    rows = run_channel_slice(date="2026-06-01", channel="all", compare="none")
    # 全店 + 5 channel (货架/达播/直播/淘客/微博) = 6 行
    assert len(rows) == 6
    # 全店 第一行
    assert rows[0][0] == "全店"
    # 全店 GSV = 10+5+3+2+1 = 21M
    assert rows[0][1] == 21_000_000
    assert rows[0][2] == 5  # 5 orders
    assert rows[0][3] == 5  # 5 distinct user
    # aov = 21M/5 = 4.2M
    assert rows[0][4] == 4_200_000
    assert rows[0][5] == "N/A"  # compare=none
    # 5 个 channel 都出现 (顺序按 _CHANNEL_ORDER)
    channels = [r[0] for r in rows[1:]]
    assert channels == ["货架", "达播", "直播", "淘客", "微博"]


# ─────────────────────────────────────────────────────────────
# Case 5: channel_slice compare=yoy — 加 yoy_pct 列
# ─────────────────────────────────────────────────────────────
def test_channel_slice_yoy(tmp_duckdb_rich):
    """2026-06-01 vs 2025-06-01, YOY 列填充."""
    from scripts.ad_hoc_queries.channel_slice import run_channel_slice

    rows = run_channel_slice(date="2026-06-01", channel="all", compare="yoy")
    assert len(rows) == 6
    # 全店: 2025-06-01 = 7+3.5+2.5 = 13M, 2026-06-01 = 21M
    # YOY = (21-13)/13 = +61.54%
    assert rows[0][0] == "全店"
    assert rows[0][5] == "+61.54%"

    # 货架: 2025-06-01 = 7M, 2026-06-01 = 10M, YOY = +42.86%
    # 找 货架 行
    huojia = next(r for r in rows if r[0] == "货架")
    assert huojia[1] == 10_000_000
    assert huojia[5] == "+42.86%"

    # 微博: 2025-06-01 没数据, 2026-06-01 = 1M
    # YOY = (1M - 0) / 0 → N/A (分母为 0)
    weibo = next(r for r in rows if r[0] == "微博")
    assert weibo[1] == 1_000_000
    assert weibo[5] == "N/A"


# ─────────────────────────────────────────────────────────────
# Case 6: 端到端 CLI — 跑真 subprocess 验 argparse + table
# ─────────────────────────────────────────────────────────────
def test_cli_yoy_battle_table(tmp_duckdb_rich):
    """起真 subprocess 跑 yoy-battle, 验 stdout 表格 + headers + 4 行 metric."""
    result = subprocess.run(
        [
            sys.executable, str(AD_HOC_PY),
            "yoy-battle",
            "--baseline-start", "2025-06-01",
            "--baseline-end", "2025-06-02",
            "--current-start", "2026-06-01",
            "--current-end", "2026-06-02",
            "--format", "table",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True, text=True, timeout=30,
        env={
            **os.environ,
            "DUCKDB_PATH": str(tmp_duckdb_rich),
        },
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    # 验 stdout 表格包含关键列名
    assert "metric" in result.stdout
    assert "baseline_value" in result.stdout
    assert "current_value" in result.stdout
    assert "yoy_pct" in result.stdout
    # 验 4 行 metric (gsv/orders/customers/aov) + header + sep = 6 行
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    assert len(lines) >= 6  # header + sep + 4 metrics
