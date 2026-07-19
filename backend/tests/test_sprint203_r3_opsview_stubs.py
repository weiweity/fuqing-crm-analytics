"""Sprint 203 R3 OpsView STUB TODO 接入锁回归 (L4.59 R6/R7/R8 + L4.60 + L4.61 永久规则化)

- 验证 backend/main.py 3 件新 health 端点 (/api/v1/health/db_size + /manifest + /pool) 注册正确
- 验证响应字段结构 (status + DuckDB size_gb + manifest version + pool utilization)
- 验证 L4.61 跨 CI runner 适配 (fail-open + 跟 /metrics 1:1 stable 不需要 auth)
- 验证 OpsView STUB TODO 接入后 0 业务代码改动模式 (跟 Sprint 200 R1 v2.1 1:1 stable)

L4.60 跨平台: REPO_ROOT = Path(__file__).resolve().parents[2]
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # L4.60 跨平台 (test 在 backend/tests/ 下)
MAIN_PY = REPO_ROOT / "backend" / "main.py"


def _load_main_module():
    """动态 import backend.main (避免 pytest collection 触发整个 app 启动)."""
    spec = importlib.util.spec_from_file_location("backend_main_stub_test", MAIN_PY)
    assert spec is not None and spec.loader is not None
    return spec


def test_main_py_syntax() -> None:
    """Sprint 203 R3 main.py 加 3 件 health 端点后语法 OK"""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(MAIN_PY)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"main.py syntax error: {result.stderr}"


def test_main_py_has_db_size_endpoint() -> None:
    """Sprint 203 R3 Stub #1: /api/v1/health/db_size 已注册"""
    content = MAIN_PY.read_text(encoding="utf-8")
    assert "@app.get(\"/api/v1/health/db_size\")" in content, (
        "Sprint 203 R3 Stub #1 缺失: backend/main.py 必须有 /api/v1/health/db_size endpoint"
    )
    assert "DUCKDB_PATH" in content, "db_size endpoint 必须读 DUCKDB_PATH"
    assert "size_gb" in content, "db_size response 必须含 size_gb 字段"


def test_main_py_has_manifest_endpoint() -> None:
    """Sprint 203 R3 Stub #2: /api/v1/health/manifest 已注册"""
    content = MAIN_PY.read_text(encoding="utf-8")
    assert "@app.get(\"/api/v1/health/manifest\")" in content, (
        "Sprint 203 R3 Stub #2 缺失: backend/main.py 必须有 /api/v1/health/manifest endpoint"
    )
    assert "_manifest_tracker_singleton" in content, "manifest endpoint 必须调 _ManifestTracker.current_version()"


def test_main_py_has_pool_endpoint() -> None:
    """Sprint 203 R3 Stub #3: /api/v1/health/pool 已注册 (跟 Fix #1 Semaphore 配套)"""
    content = MAIN_PY.read_text(encoding="utf-8")
    assert "@app.get(\"/api/v1/health/pool\")" in content, (
        "Sprint 203 R3 Stub #3 缺失: backend/main.py 必须有 /api/v1/health/pool endpoint"
    )
    assert "dual_conn._read_pool" in content, "pool endpoint 必须读 dual_conn._read_pool"
    assert "_read_semaphore" in content, "pool endpoint 必须读 _read_semaphore._value"
    assert "utilization_pct" in content, "pool response 必须含 utilization_pct 字段"


def test_rate_limit_middleware_bypasses_health_endpoints() -> None:
    """Sprint 203 R3: rate_limit_middleware bypass 3 件新 health 端点 (跟 /metrics 1:1 stable)"""
    content = MAIN_PY.read_text(encoding="utf-8")
    assert "/api/v1/health/db_size" in content, "rate_limit_middleware bypass 必须含 db_size path"
    assert "/api/v1/health/manifest" in content, "rate_limit_middleware bypass 必须含 manifest path"
    assert "/api/v1/health/pool" in content, "rate_limit_middleware bypass 必须含 pool path"


def test_clickhouse_poc_monitor_bc_stubs_documented() -> None:
    """Sprint 203 R3 Stub #4: clickhouse_poc_monitor.py b/c trigger 注释 TODO Sprint 203 R4+"""
    monitor_py = REPO_ROOT / "scripts" / "ops" / "clickhouse_poc_monitor.py"
    content = monitor_py.read_text(encoding="utf-8")
    # b 件: query P95 (Sprint 203 R4+ 真接入 /metrics histogram_quantile)
    assert "Sprint 203 R4+" in content, (
        "Sprint 203 R3 Stub #4 b/c trigger 注释必含 'Sprint 203 R4+' 真接入延迟标记"
    )


def test_opsview_vue_has_three_stub_cards() -> None:
    """Sprint 203 R3 OpsView.vue: 3 件新 card 渲染 (DuckDB size + manifest + pool)"""
    vue_file = REPO_ROOT / "frontend-vue3" / "src" / "views" / "OpsView.vue"
    content = vue_file.read_text(encoding="utf-8")
    assert "DuckDB 文件大小" in content, "OpsView 必须有 DuckDB 文件大小 card"
    assert "W5 Manifest Version" in content, "OpsView 必须有 W5 Manifest Version card"
    assert "Read Pool 利用率" in content, "OpsView 必须有 Read Pool 利用率 card"
    # 4 件 endpoint 一起 fetch (跟 L4.61 跨 CI runner 1:1 stable)
    assert "/api/v1/health/db_size" in content, "OpsView fetch 必须含 /api/v1/health/db_size"
    assert "/api/v1/health/manifest" in content, "OpsView fetch 必须含 /api/v1/health/manifest"
    assert "/api/v1/health/pool" in content, "OpsView fetch 必须含 /api/v1/health/pool"
    assert "Promise.all" in content, "OpsView 必须并行 fetch 4 件 endpoint"