"""Sprint 203 R4 ClickHouse POC monitor b/c 件真接入锁回归 (L4.59 + L4.40 + L4.60 + L4.61 永久规则化)

- 验证 _check_trigger_a/b/c 3 件启动条件阈值判断 (a 走 Path.stat, b 走 /metrics parse, c 走 /api/v1/health/pool)
- 验证 urllib HTTP fetch + 3s timeout fail-open (跟 L4.40 post-merge hook 1:1 stable)
- 验证 Prometheus bucket parse 推 P95 正确 (跨 endpoint/query_type 维度加总)
- 验证 Linux CI runner skip (跟 L4.61 跨 sprint 监控 1:1 stable)

L4.60 跨平台: REPO_ROOT = Path(__file__).resolve().parents[2]
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parents[2]  # L4.60 跨平台
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import scripts.ops.clickhouse_poc_monitor as cpm  # noqa: E402


# === (a) DuckDB size trigger tests (跟 Sprint 203 R2 1:1 stable) ===

def test_check_trigger_a_above_threshold() -> None:
    """Sprint 203 R2: DuckDB size > 200GB → trigger."""
    msg = cpm._check_trigger_a(201.0)
    assert msg is not None
    assert "(a)" in msg
    assert "201.0GB" in msg


def test_check_trigger_a_below_threshold() -> None:
    """Sprint 203 R2: DuckDB size < 200GB → None."""
    assert cpm._check_trigger_a(118.4) is None


def test_check_trigger_a_none_input() -> None:
    """Sprint 203 R2: DuckDB file missing → None (fail-open)."""
    assert cpm._check_trigger_a(None) is None


# === (b) Query P95 trigger tests (Sprint 203 R4 真接入) ===

def test_check_trigger_b_p95_above_threshold() -> None:
    """R4: 模拟 /metrics 含 P95 > 30s → trigger."""
    # 构造 fake /metrics: 100 个 query, P95 = 35s (75 queries ≤ 30s + 25 queries 在 60s bucket)
    fake_metrics = (
        'fq_query_total{endpoint="/api/v1/test",query_type="type_a"} 100\n'
        'fq_query_duration_seconds_bucket{endpoint="/api/v1/test",query_type="type_a",le="0.05"} 5\n'
        'fq_query_duration_seconds_bucket{endpoint="/api/v1/test",query_type="type_a",le="0.1"} 10\n'
        'fq_query_duration_seconds_bucket{endpoint="/api/v1/test",query_type="type_a",le="0.5"} 30\n'
        'fq_query_duration_seconds_bucket{endpoint="/api/v1/test",query_type="type_a",le="1.0"} 40\n'
        'fq_query_duration_seconds_bucket{endpoint="/api/v1/test",query_type="type_a",le="5.0"} 55\n'
        'fq_query_duration_seconds_bucket{endpoint="/api/v1/test",query_type="type_a",le="10.0"} 65\n'
        'fq_query_duration_seconds_bucket{endpoint="/api/v1/test",query_type="type_a",le="30.0"} 75\n'
        'fq_query_duration_seconds_bucket{endpoint="/api/v1/test",query_type="type_a",le="60.0"} 100\n'
        'fq_query_duration_seconds_bucket{endpoint="/api/v1/test",query_type="type_a",le="+Inf"} 100\n'
        'fq_query_duration_seconds_count{endpoint="/api/v1/test",query_type="type_a"} 100\n'
    )
    with patch.object(cpm, "_fetch_url_text", return_value=fake_metrics):
        msg = cpm._check_trigger_b()
    assert msg is not None
    assert "(b)" in msg
    assert "P95" in msg


def test_check_trigger_b_p95_below_threshold() -> None:
    """R4: 模拟 /metrics P95 < 30s → None."""
    fake_metrics = (
        'fq_query_total{endpoint="/api/v1/test",query_type="type_a"} 100\n'
        'fq_query_duration_seconds_bucket{endpoint="/api/v1/test",query_type="type_a",le="0.05"} 5\n'
        'fq_query_duration_seconds_bucket{endpoint="/api/v1/test",query_type="type_a",le="0.1"} 10\n'
        'fq_query_duration_seconds_bucket{endpoint="/api/v1/test",query_type="type_a",le="0.5"} 30\n'
        'fq_query_duration_seconds_bucket{endpoint="/api/v1/test",query_type="type_a",le="1.0"} 80\n'
        'fq_query_duration_seconds_bucket{endpoint="/api/v1/test",query_type="type_a",le="5.0"} 95\n'
        'fq_query_duration_seconds_bucket{endpoint="/api/v1/test",query_type="type_a",le="10.0"} 100\n'
        'fq_query_duration_seconds_bucket{endpoint="/api/v1/test",query_type="type_a",le="+Inf"} 100\n'
        'fq_query_duration_seconds_count{endpoint="/api/v1/test",query_type="type_a"} 100\n'
    )
    with patch.object(cpm, "_fetch_url_text", return_value=fake_metrics):
        msg = cpm._check_trigger_b()
    assert msg is None


def test_check_trigger_b_http_fail_open() -> None:
    """R4: HTTP fetch fail → None (L4.40 fail-open)."""
    with patch.object(cpm, "_fetch_url_text", return_value=None):
        msg = cpm._check_trigger_b()
    assert msg is None


def test_check_trigger_b_no_histogram_data() -> None:
    """R4: /metrics 没 histogram → None."""
    with patch.object(cpm, "_fetch_url_text", return_value="# no metric data\n"):
        msg = cpm._check_trigger_b()
    assert msg is None


def test_parse_query_p95_aggregate_multi_dimension() -> None:
    """R4: 跨 endpoint × query_type 维度累计 histogram bucket 推 P95."""
    fake_metrics = (
        # 50 queries in endpoint A
        'fq_query_duration_seconds_count{endpoint="A",query_type="t1"} 50\n'
        'fq_query_duration_seconds_bucket{endpoint="A",query_type="t1",le="0.5"} 10\n'
        'fq_query_duration_seconds_bucket{endpoint="A",query_type="t1",le="1.0"} 20\n'
        'fq_query_duration_seconds_bucket{endpoint="A",query_type="t1",le="10.0"} 30\n'
        'fq_query_duration_seconds_bucket{endpoint="A",query_type="t1",le="30.0"} 40\n'
        'fq_query_duration_seconds_bucket{endpoint="A",query_type="t1",le="60.0"} 50\n'
        'fq_query_duration_seconds_bucket{endpoint="A",query_type="t1",le="+Inf"} 50\n'
        # 50 queries in endpoint B
        'fq_query_duration_seconds_count{endpoint="B",query_type="t2"} 50\n'
        'fq_query_duration_seconds_bucket{endpoint="B",query_type="t2",le="0.5"} 5\n'
        'fq_query_duration_seconds_bucket{endpoint="B",query_type="t2",le="1.0"} 10\n'
        'fq_query_duration_seconds_bucket{endpoint="B",query_type="t2",le="10.0"} 20\n'
        'fq_query_duration_seconds_bucket{endpoint="B",query_type="t2",le="30.0"} 50\n'
        'fq_query_duration_seconds_bucket{endpoint="B",query_type="t2",le="+Inf"} 50\n'
    )
    with patch.object(cpm, "_fetch_url_text", return_value=fake_metrics):
        p95 = cpm._parse_query_p95()
    # total = 100, 0.95*100 = 95
    # cumulative per le (跨 A+B 加总): 0.5=15, 1.0=30, 10.0=50, 30.0=90, 60.0=100
    # 找 cumulative >= 95 → 60.0
    assert p95 == 60.0


# === (c) Pool semaphore trigger tests (Sprint 203 R4 真接入) ===

def test_check_trigger_c_pool_above_threshold() -> None:
    """R4: semaphore_in_use > 5 → trigger."""
    fake_pool = {
        "status": "ok",
        "semaphore_in_use": 7,
        "semaphore_max": 10,
        "utilization_pct": 70.0,
    }
    with patch.object(cpm, "_fetch_url_json", return_value=fake_pool):
        msg = cpm._check_trigger_c()
    assert msg is not None
    assert "(c)" in msg
    assert "Read pool in use 7" in msg


def test_check_trigger_c_pool_below_threshold() -> None:
    """R4: semaphore_in_use <= 5 → None."""
    fake_pool = {
        "status": "ok",
        "semaphore_in_use": 3,
        "semaphore_max": 10,
        "utilization_pct": 30.0,
    }
    with patch.object(cpm, "_fetch_url_json", return_value=fake_pool):
        msg = cpm._check_trigger_c()
    assert msg is None


def test_check_trigger_c_pool_http_fail_open() -> None:
    """R4: HTTP fetch fail → None (L4.40 fail-open)."""
    with patch.object(cpm, "_fetch_url_json", return_value=None):
        msg = cpm._check_trigger_c()
    assert msg is None


def test_get_pool_in_use_parse_correctly() -> None:
    """R4: _get_pool_in_use 正确 parse semaphore_in_use 字段."""
    fake_pool = {"status": "ok", "semaphore_in_use": 4}
    with patch.object(cpm, "_fetch_url_json", return_value=fake_pool):
        result = cpm._get_pool_in_use()
    assert result == 4


def test_get_pool_in_use_missing_key() -> None:
    """R4: response 缺 semaphore_in_use 字段 → 视作 0 (default)."""
    fake_pool = {"status": "ok"}
    with patch.object(cpm, "_fetch_url_json", return_value=fake_pool):
        result = cpm._get_pool_in_use()
    assert result == 0


# === L4.61 跨 CI runner 适配 ===

def test_main_linux_ci_runner_skip() -> None:
    """L4.61: Linux CI runner → return 0 (跟 Sprint 202+ CI fix #2 1:1 stable)."""
    with patch.object(cpm.sys, "platform", "linux"):
        result = cpm.main()
    assert result == 0


# === _fetch_url_text fail-open 验证 ===

def test_fetch_url_text_timeout_fail_open() -> None:
    """L4.40: urllib timeout → None (fail-open 不阻 commit)."""
    with patch("urllib.request.urlopen", side_effect=TimeoutError("test timeout")):
        result = cpm._fetch_url_text("http://test.example.com/metrics")
    assert result is None


def test_fetch_url_text_urlerror_fail_open() -> None:
    """L4.40: URLError → None (fail-open)."""
    with patch("urllib.request.urlopen", side_effect=cpm.urllib.error.URLError("test url error")):
        result = cpm._fetch_url_text("http://test.example.com/metrics")
    assert result is None