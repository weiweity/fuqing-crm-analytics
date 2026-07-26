"""Sprint 203 R4 ClickHouse POC monitor b/c 件真接入锁回归 (L4.59 + L4.40 + L4.60 + L4.61 永久规则化)

- 验证 _check_trigger_a/b/c 3 件启动条件阈值判断 (a 走 Path.stat, b/c 走 admin Bearer health endpoint)
- 验证 urllib HTTP fetch + 3s timeout fail-open (跟 L4.40 post-merge hook 1:1 stable)
- 验证 Prometheus bucket parse 推 P95 正确 (跨 endpoint/query_type 维度加总)
- 验证管理员凭据缺失/401/403 明确 fail-closed，且日志不泄露密码/token
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

AUTHORIZATION = "Bearer unit-test-token"


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
        msg = cpm._check_trigger_b(AUTHORIZATION)
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
        msg = cpm._check_trigger_b(AUTHORIZATION)
    assert msg is None


def test_check_trigger_b_http_fail_open() -> None:
    """R4: HTTP fetch fail → None (L4.40 fail-open)."""
    with patch.object(cpm, "_fetch_url_text", return_value=None):
        msg = cpm._check_trigger_b(AUTHORIZATION)
    assert msg is None


def test_check_trigger_b_no_histogram_data() -> None:
    """R4: /metrics 没 histogram → None."""
    with patch.object(cpm, "_fetch_url_text", return_value="# no metric data\n"):
        msg = cpm._check_trigger_b(AUTHORIZATION)
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
    with patch.object(cpm, "_fetch_url_text", return_value=fake_metrics) as fetch:
        p95 = cpm._parse_query_p95(AUTHORIZATION)
    # total = 100, 0.95*100 = 95
    # cumulative per le (跨 A+B 加总): 0.5=15, 1.0=30, 10.0=50, 30.0=90, 60.0=100
    # 找 cumulative >= 95 → 60.0
    assert p95 == 60.0
    fetch.assert_called_once_with(
        f"{cpm.BACKEND_URL}/api/v1/health/metrics",
        authorization=AUTHORIZATION,
        require_admin=True,
    )


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
        msg = cpm._check_trigger_c(AUTHORIZATION)
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
        msg = cpm._check_trigger_c(AUTHORIZATION)
    assert msg is None


def test_check_trigger_c_pool_http_fail_open() -> None:
    """R4: HTTP fetch fail → None (L4.40 fail-open)."""
    with patch.object(cpm, "_fetch_url_json", return_value=None):
        msg = cpm._check_trigger_c(AUTHORIZATION)
    assert msg is None


def test_get_pool_in_use_parse_correctly() -> None:
    """R4: _get_pool_in_use 正确 parse semaphore_in_use 字段."""
    fake_pool = {"status": "ok", "semaphore_in_use": 4}
    with patch.object(cpm, "_fetch_url_json", return_value=fake_pool) as fetch:
        result = cpm._get_pool_in_use(AUTHORIZATION)
    assert result == 4
    fetch.assert_called_once_with(
        f"{cpm.BACKEND_URL}/api/v1/health/pool",
        authorization=AUTHORIZATION,
        require_admin=True,
    )


def test_get_pool_in_use_missing_key() -> None:
    """R4: response 缺 semaphore_in_use 字段 → 视作 0 (default)."""
    fake_pool = {"status": "ok"}
    with patch.object(cpm, "_fetch_url_json", return_value=fake_pool):
        result = cpm._get_pool_in_use(AUTHORIZATION)
    assert result == 0


# === 管理员鉴权回归 ===

def test_select_dedicated_admin_credentials() -> None:
    config = {
        "FQ_CRM_ADMINS": "admin,monitor",
        "FQ_CRM_PASSWORDS": "admin:shared-password,monitor:monitor-password",
        "FQ_POC_MONITOR_ADMIN_USERNAME": "monitor",
        "FQ_POC_MONITOR_DEDICATED_ACCOUNT": "monitor",
    }
    with patch.object(cpm, "_runtime_config", return_value=config):
        assert cpm._select_monitor_admin_credentials() == (
            "monitor",
            "monitor-password",
        )


def test_select_admin_credentials_requires_explicit_dedicated_user(capsys) -> None:
    config = {
        "FQ_CRM_ADMINS": "admin",
        "FQ_CRM_PASSWORDS": "admin:shared-password",
    }
    with patch.object(cpm, "_runtime_config", return_value=config):
        assert cpm._select_monitor_admin_credentials() is None
    assert "AUTH_CONFIG_ERROR" in capsys.readouterr().err


def test_select_admin_credentials_requires_dedicated_confirmation(capsys) -> None:
    config = {
        "FQ_CRM_ADMINS": "admin",
        "FQ_CRM_PASSWORDS": "admin:shared-password",
        "FQ_POC_MONITOR_ADMIN_USERNAME": "admin",
    }
    with patch.object(cpm, "_runtime_config", return_value=config):
        assert cpm._select_monitor_admin_credentials() is None
    assert "FQ_POC_MONITOR_DEDICATED_ACCOUNT" in capsys.readouterr().err


def test_dedicated_confirmation_is_bound_to_selected_username(capsys) -> None:
    config = {
        "FQ_CRM_ADMINS": "admin,monitor",
        "FQ_CRM_PASSWORDS": "admin:shared-password,monitor:monitor-password",
        "FQ_POC_MONITOR_ADMIN_USERNAME": "admin",
        "FQ_POC_MONITOR_DEDICATED_ACCOUNT": "monitor",
    }
    with patch.object(cpm, "_runtime_config", return_value=config):
        assert cpm._select_monitor_admin_credentials() is None
    assert "same username" in capsys.readouterr().err


def test_admin_login_uses_post_body_and_returns_bearer() -> None:
    with (
        patch.object(
            cpm,
            "_select_monitor_admin_credentials",
            return_value=("monitor", "monitor-password"),
        ),
        patch.object(
            cpm,
            "_fetch_url_text",
            return_value='{"token":"fresh-token","username":"monitor","is_admin":true}',
        ) as fetch,
    ):
        authorization = cpm._get_monitor_authorization()

    assert authorization == "Bearer fresh-token"
    args, kwargs = fetch.call_args
    assert args == (f"{cpm.BACKEND_URL}/api/v1/auth/login",)
    assert kwargs["method"] == "POST"
    assert b"monitor-password" in kwargs["body"]
    assert "monitor-password" not in args[0]


def test_admin_login_failure_does_not_log_secret(capsys) -> None:
    secret = "do-not-log-this-password"
    with (
        patch.object(
            cpm,
            "_select_monitor_admin_credentials",
            return_value=("monitor", secret),
        ),
        patch.object(cpm, "_fetch_url_text", return_value=None),
    ):
        assert cpm._get_monitor_authorization() is None
    assert secret not in capsys.readouterr().err


def test_logout_uses_bearer_without_invalid_empty_json_body() -> None:
    with patch.object(cpm, "_fetch_url_text") as fetch:
        cpm._logout_monitor_token(AUTHORIZATION)

    fetch.assert_called_once_with(
        f"{cpm.BACKEND_URL}/api/v1/auth/logout",
        authorization=AUTHORIZATION,
        method="POST",
    )


def test_admin_endpoint_rejection_fails_closed() -> None:
    error = cpm.urllib.error.HTTPError(
        url=f"{cpm.BACKEND_URL}/api/v1/health/metrics",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=None,
    )
    with patch("urllib.request.urlopen", side_effect=error):
        try:
            cpm._fetch_url_text(
                f"{cpm.BACKEND_URL}/api/v1/health/metrics",
                authorization=AUTHORIZATION,
                require_admin=True,
            )
        except cpm.MonitorAuthError:
            pass
        else:
            raise AssertionError("401 admin endpoint response must fail closed")


def test_main_missing_admin_credentials_fails_closed(tmp_path, capsys) -> None:
    with (
        patch.object(cpm.sys, "platform", "darwin"),
        patch.object(cpm, "LOG_FILE", tmp_path / "monitor.log"),
        patch.object(cpm, "_duckdb_size_gb", return_value=100.0),
        patch.object(cpm, "_get_monitor_authorization", return_value=None),
    ):
        result = cpm.main()

    captured = capsys.readouterr()
    assert result == 2
    assert "AUTH_FAILURE" in captured.err
    assert "CLICKHOUSE_POC_MONITOR_PASS" not in captured.out


def test_main_records_size_trigger_before_auth_failure(
    tmp_path, capsys
) -> None:
    with (
        patch.object(cpm.sys, "platform", "darwin"),
        patch.object(cpm, "LOG_FILE", tmp_path / "monitor.log"),
        patch.object(cpm, "_duckdb_size_gb", return_value=201.0),
        patch.object(cpm, "_get_monitor_authorization", return_value=None),
        patch.object(cpm, "append_tech_debt") as append_debt,
    ):
        result = cpm.main()

    captured = capsys.readouterr()
    assert result == 2
    assert "TRIGGER HIT" in captured.out
    assert "(a)" in captured.out
    assert "AUTH_FAILURE" in captured.err
    append_debt.assert_called_once()


def test_main_records_size_trigger_before_generic_exception(
    tmp_path, capsys
) -> None:
    with (
        patch.object(cpm.sys, "platform", "darwin"),
        patch.object(cpm, "LOG_FILE", tmp_path / "monitor.log"),
        patch.object(cpm, "_duckdb_size_gb", return_value=201.0),
        patch.object(
            cpm,
            "_get_monitor_authorization",
            side_effect=ValueError("sensitive malformed config"),
        ),
        patch.object(cpm, "append_tech_debt") as append_debt,
    ):
        result = cpm.main()

    captured = capsys.readouterr()
    assert result == 0
    assert "TRIGGER HIT" in captured.out
    assert "(a)" in captured.out
    assert "EXCEPTION (fail-open): ValueError" in captured.err
    assert "sensitive malformed config" not in captured.err
    append_debt.assert_called_once()


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
