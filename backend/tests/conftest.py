"""
Pytest fixtures for backend service tests.
"""
import os
import subprocess
import pytest
import sys
from pathlib import Path

# Add backend/ to path for imports
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))


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


@pytest.fixture
def skip_if_uvicorn_alive():
    """test fixture: 如果生产 DuckDB 被其他进程占, pytest.skip 整 test.

    适用: 调 subprocess 跑 scripts/etl/*.py 而该脚本会 duckdb.connect(_PROD_DUCKDB_PATH).
    """
    holder_pid = _duckdb_lock_holder_pid()
    if holder_pid is not None and holder_pid != os.getpid():
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
