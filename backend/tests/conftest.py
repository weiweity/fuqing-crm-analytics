"""
Pytest fixtures for backend service tests.
"""
import subprocess
import pytest
import sys
from pathlib import Path

# Add backend/ to path for imports
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests in slow modules with @pytest.mark.slow if not already marked."""
    slow_modules = {
        "test_is_member_mark_sync",
        "test_w3_dq_assertions",
        "test_w3w4_pipeline_integration",
        "test_w3w4_pipeline_smoke",
    }
    for item in items:
        module_name = item.module.__name__.rsplit(".", 1)[-1]
        if module_name in slow_modules and "slow" not in item.keywords:
            item.add_marker(pytest.mark.slow)


# ─────────────────────────────────────────────────────────────
# Sprint 22 #25: skip-if-DuckDB-locked fixture
#
# 背景: scripts/etl/rfm_recompute_window.py 跟生产 uvicorn 共享 DuckDB 文件,
# 跨进程开 read-write 连接会失败 (_duckdb.IOException: Conflicting lock).
# 之前 test_rfm_recompute_window_dry_run 在 uvicorn PID 18827 运行时假 fail.
#
# 修法: 用 lsof 探测 DuckDB 文件被哪个进程占 fd, 如果被占则 pytest.skip() 整 test.
# 不仅是 uvicorn — 任何进程占 DuckDB 都 skip, 防假 fail.
# ─────────────────────────────────────────────────────────────

# 生产 DuckDB 路径 (跟 backend/db/connection.py 一致)
_PROD_DUCKDB_PATH = Path("/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb")


def _duckdb_lock_holder_pid() -> int | None:
    """lsof 探测 DuckDB 文件被哪个 PID 占 fd (write lock). 返 PID 或 None (没进程占)."""
    if not _PROD_DUCKDB_PATH.exists():
        return None
    try:
        result = subprocess.run(
            ["lsof", "-t", str(_PROD_DUCKDB_PATH)],
            capture_output=True, text=True, timeout=5,
        )
        pids = [int(p) for p in result.stdout.strip().split() if p.strip().isdigit()]
        return pids[0] if pids else None
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        return None


# ─────────────────────────────────────────────────────────────
# Sprint 39 CI 爆红修复: 动态检测 production DuckDB 可用性
#
# 背景: Sprint 38 race flake 治标加 _IN_XDIST_PARALLEL skipif 只在 pytest-xdist
# 模式生效. CI 跑 serial mode (-n 0) → _IN_XDIST_PARALLEL=False → skipif 不生效.
# 然后 CI 上 production DuckDB 不存在 (103GB 不在 repo) → test 真连空 DuckDB
# → CatalogException: Table 'orders' does not exist → CI fail.
#
# 修法: 加 _PROD_DUCKDB_AVAILABLE module-level 常量, 跨多个 test 用作 skipif
# 条件. CI 没数据 → test skip, 本地有数据 → test 跑 (xdist 模式 race flake skip).
# ─────────────────────────────────────────────────────────────

def _detect_prod_duckdb_available() -> bool:
    """动态检测 production DuckDB 是否可访问: 文件存在 + duckdb.connect() 不抛异常.

    Sprint 39: 替代 hardcoded _PROD_DUCKDB_PATH (Sprint 22 #25 那个). 跨工作树/clone/CI
    友好. 只 check 文件存在 + 可连接 (read_only=True 不抢 write lock), 不 check 表存在
    (避免 sprint 期间 schema 变动引发 false negative).

    Returns:
        True if production DuckDB 可访问 (本地开发 / 用户 clone + 自己跑 ETL 跑批后)
        False if 不可访问 (fresh checkout / CI runner / data/processed/ 不存在)
    """
    try:
        from backend.config import DUCKDB_PATH
        path = Path(str(DUCKDB_PATH))
    except Exception:
        # backend.config 不可 import (CI 早期失败) → 不可访问
        return False

    if not path.exists():
        return False

    # 文件存在, 进一步 check 可连接 (read_only 不抢 write lock, 不会跟 uvicorn 冲突)
    try:
        import duckdb
        conn = duckdb.connect(str(path), read_only=True)
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return True
    except Exception:
        return False


# Module-level 常量: 跨多个 test 共享 skipif 条件
_PROD_DUCKDB_AVAILABLE = _detect_prod_duckdb_available()


@pytest.fixture
def skip_if_duckdb_locked():
    """test fixture: 如果生产 DuckDB 被任何进程占 (含本 pytest 进程), pytest.skip 整 test.

    背景: backend/db/connection.py 单例连接会在首次 get_connection() 后一直占住生产
    DuckDB 文件。此时再调 subprocess 跑 scripts/etl/*.py 去 duckdb.connect 同一文件会
    触发 IO Error: Could not set lock。因此只要 lsof 探测到任何 PID 占 fd, 就跳过。

    适用: 调 subprocess 跑 scripts/etl/*.py 而该脚本会 duckdb.connect(_PROD_DUCKDB_PATH).
    """
    holder_pid = _duckdb_lock_holder_pid()
    if holder_pid is not None:
        pytest.skip(
            f"生产 DuckDB 被 PID {holder_pid} 占 fd, 跳过 (避免跨进程锁冲突). "
            f"如需跑, 先 kill {holder_pid} 或用 --no-uvicorn 起测试环境."
        )


@pytest.fixture
def sample_rfm_record():
    """Sample RFM record for testing."""
    return {
        "user_id": "u001",
        "monetary": 500.0,
        "frequency": 3,
        "recency_days": 15,
        "r_score": 4,
        "f_score": 2,
        "m_score": 3,
    }


@pytest.fixture
def segment_ids():
    """All valid segment IDs (1-11, excluding 9)."""
    return [1, 2, 3, 4, 5, 6, 7, 8, 10, 11]


@pytest.fixture
def rfm_thresholds():
    """Standard RFM thresholds (from semantic/segments.py RFM_THRESHOLDS)."""
    from backend.semantic.segments import RFM_THRESHOLDS
    return RFM_THRESHOLDS


# ─────────────────────────────────────────────────────────────
# Sprint 31.1: tmp tracker DB per-test 隔离 fixture (autouse)
#
# 背景: scripts/etl/cli.py:_collect_fq_tmp_orphans 在 Sprint 31.1 后用
# TrackerDB 作为 source of truth. TrackerDB 默认 db_path = /tmp/fuqing-tmp-tracker.db
# (production 路径). 多个 test 共享同一 db 会造成 row 残留 (例如 test_lsof_layer1
# skip 删除 → tracker row 残留 → 下个 test list_expired 拾起 → candidate 数量
# 偏离 test 预期).
#
# 修法: autouse fixture 把 cli._FQ_TMP_TRACKER_PATH 临时指向 tmp_path/test-tracker.db,
# test 结束清 WAL/SHM/journal 残留. 现有 17 个 test 不需改 (行为跟 Phase 1 之前一致).
# 只影响 cli._FQ_TMP_TRACKER_PATH 单一变量, 不污染其它模块.
# ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolate_tmp_tracker(tmp_path):
    """Sprint 31.1: per-test 隔离 tmp tracker DB. autouse 确保每个 test 干净.

    patch 两处:
      - cli._FQ_TMP_TRACKER_PATH (Layer 1 读这个)
      - tmp_tracker.TRACKER_DB_PATH (TrackerDB() 默认参数读这个)
    """
    from scripts.etl import cli
    from scripts.etl.common import tmp_tracker
    import os
    original_cli_path = cli._FQ_TMP_TRACKER_PATH
    original_tracker_default = tmp_tracker.TRACKER_DB_PATH
    test_db = str(tmp_path / "test-tracker.db")
    cli._FQ_TMP_TRACKER_PATH = test_db
    tmp_tracker.TRACKER_DB_PATH = test_db
    try:
        yield test_db
    finally:
        cli._FQ_TMP_TRACKER_PATH = original_cli_path
        tmp_tracker.TRACKER_DB_PATH = original_tracker_default
        # 清理 WAL/SHM/journal 副作用文件
        for suffix in ("", "-shm", "-wal", "-journal"):
            try:
                os.unlink(test_db + suffix)
            except OSError:
                pass
