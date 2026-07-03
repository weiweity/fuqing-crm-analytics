"""
Pytest fixtures for backend service tests.
"""
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import duckdb
import pytest

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


@pytest.fixture(scope="session")
def isolated_duckdb():
    """为每个 pytest-xdist worker 提供隔离 DuckDB。

    worker 只写自己的临时数据库，并以只读方式 ATTACH 生产库。search_path
    让业务代码继续用无 schema 前缀的表名读取生产数据。
    """
    if not _PROD_DUCKDB_AVAILABLE:
        pytest.skip("production DuckDB 不可用")

    from backend.config import DUCKDB_MEMORY_LIMIT, DUCKDB_PATH

    tmp = tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    # DuckDB 1.5+ 会拒绝已存在但为空的文件；保留安全生成的路径即可。
    tmp_path.unlink()
    conn = None

    try:
        conn = duckdb.connect(
            str(tmp_path),
            config={"memory_limit": DUCKDB_MEMORY_LIMIT},
        )
        prod_path = str(DUCKDB_PATH).replace("'", "''")
        conn.execute(f"ATTACH '{prod_path}' AS prod (READ_ONLY)")
        conn.execute("PRAGMA search_path='main,prod'")
        yield conn
    finally:
        if conn is not None:
            conn.close()
        tmp_path.unlink(missing_ok=True)


@pytest.fixture
def monkeypatch_connection(isolated_duckdb):
    """让当前 test 的服务层连接使用当前 worker 的隔离 DuckDB。"""
    from backend.db import connection

    class FakeThreadSafeConnection:
        """测试用最小连接包装器；查询结果直接使用 DuckDB 原生 cursor。"""

        def __init__(self, conn):
            self._conn = conn

        def execute(self, query, parameters=None):
            if parameters is not None:
                return self._conn.execute(query, parameters)
            return self._conn.execute(query)

        def close(self):
            pass

        def __getattr__(self, name):
            return getattr(self._conn, name)

    original_conn = connection._conn
    original_get_connection = connection.get_connection

    def _fake_get_connection():
        return FakeThreadSafeConnection(isolated_duckdb)

    # pytest 先收集全部 test module，再创建 fixture。收集期间已经用
    # ``from ... import get_connection`` 绑定的 service 也必须一起替换。
    for module in tuple(sys.modules.values()):
        if (
            module is not None
            and getattr(module, "get_connection", None) is original_get_connection
        ):
            module.get_connection = _fake_get_connection

    connection._conn = None
    connection.get_connection = _fake_get_connection

    try:
        yield isolated_duckdb
    finally:
        # test 执行期间延迟 import 的 service 也可能绑定 fake；一并恢复，避免
        # 当前 worker 后续无关 test 继续使用本 fixture 的隔离连接。
        for module in tuple(sys.modules.values()):
            if module is None:
                continue
            if getattr(module, "get_connection", None) is _fake_get_connection:
                module.get_connection = original_get_connection
        connection.get_connection = original_get_connection
        connection._conn = original_conn


class SyntheticDuckDBHandle:
    """Small wrapper that carries the tmp path while behaving like a DuckDB connection."""

    def __init__(self, path: Path, conn):
        self.path = path
        self._conn = conn

    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def cursor(self):
        return self._conn.cursor()

    def close(self):
        return self._conn.close()

    def cleanup(self) -> None:
        self.close()
        self.path.unlink(missing_ok=True)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _create_tmp_duckdb_with_synthetic_orders() -> SyntheticDuckDBHandle:
    """Create a tmp DuckDB with enough CRM schema to exercise ad-hoc API paths."""
    tmp = tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    tmp_path.unlink()

    conn = duckdb.connect(str(tmp_path), config={"memory_limit": "1GB"})
    conn.execute("""
        CREATE TABLE orders (
            order_id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            pay_time TIMESTAMP NOT NULL,
            actual_amount DOUBLE NOT NULL,
            channel VARCHAR NOT NULL,
            is_member BOOLEAN DEFAULT FALSE,
            is_goujinjin BOOLEAN DEFAULT FALSE,
            is_refund BOOLEAN DEFAULT FALSE,
            order_status VARCHAR NOT NULL,
            product_id VARCHAR DEFAULT '',
            spu_tier VARCHAR DEFAULT '护肤',
            spu_product_class VARCHAR DEFAULT '面霜',
            spu_product_subclass VARCHAR DEFAULT '修护面霜',
            spu_category VARCHAR DEFAULT '护肤'
        )
    """)
    conn.execute("""
        CREATE TABLE user_first_purchase (
            user_id VARCHAR PRIMARY KEY,
            first_pay_date DATE NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE user_rfm (
            user_id VARCHAR,
            user_nickname VARCHAR,
            analysis_date DATE,
            metric_type VARCHAR,
            lookback_days INTEGER,
            channel VARCHAR DEFAULT '全店',
            recency_days INTEGER,
            frequency INTEGER,
            monetary DECIMAL(12, 2),
            r_score INTEGER,
            f_score INTEGER,
            m_score INTEGER,
            rfm_tier VARCHAR,
            rfm_tier_en VARCHAR,
            segment_id INTEGER,
            first_order_date DATE,
            last_order_date DATE,
            is_member BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, analysis_date, metric_type, lookback_days, channel)
        )
    """)

    rows = [
        ("h2024_old", "u2024_old", "2024-05-10 09:00:00", 20.0, "货架", False, False, False, "已付款", "803474428381", "护肤", "面霜", "修护面霜", "护肤"),
        ("h2024_member", "u2024_member", "2024-05-12 09:00:00", 30.0, "货架", True, False, False, "已付款", "597655781410", "护肤", "精华", "修护精华", "护肤"),
        ("o2024_old", "u2024_old", "2024-06-15 10:00:00", 70.0, "货架", False, False, False, "已付款", "803474428381", "护肤", "面霜", "修护面霜", "护肤"),
        ("o2024_member", "u2024_member", "2024-06-15 11:00:00", 140.0, "货架", True, False, False, "已付款", "597655781410", "护肤", "精华", "修护精华", "护肤"),
        ("o2024_sample", "u2024_sample", "2024-06-15 12:00:00", 35.0, "U先派样", False, False, False, "已付款", "621639424901", "试用", "小样", "体验装", "试用"),
        ("h2025_old", "u2025_old", "2025-05-10 09:00:00", 20.0, "货架", False, False, False, "已付款", "803474428381", "护肤", "面霜", "修护面霜", "护肤"),
        ("h2025_member", "u2025_member", "2025-05-12 09:00:00", 30.0, "货架", True, False, False, "已付款", "597655781410", "护肤", "精华", "修护精华", "护肤"),
        ("o2025_old", "u2025_old", "2025-06-15 10:00:00", 80.0, "货架", False, False, False, "已付款", "803474428381", "护肤", "面霜", "修护面霜", "护肤"),
        ("o2025_member", "u2025_member", "2025-06-15 11:00:00", 160.0, "货架", True, False, False, "已付款", "597655781410", "护肤", "精华", "修护精华", "护肤"),
        ("o2025_sample", "u2025_sample", "2025-06-15 12:00:00", 40.0, "U先派样", False, False, False, "已付款", "621639424901", "试用", "小样", "体验装", "试用"),
        ("h2026_old", "u2026_old", "2026-05-10 09:00:00", 20.0, "货架", False, False, False, "已付款", "803474428381", "护肤", "面霜", "修护面霜", "护肤"),
        ("h2026_member", "u2026_member", "2026-05-12 09:00:00", 30.0, "货架", True, False, False, "已付款", "597655781410", "护肤", "精华", "修护精华", "护肤"),
        ("o2026_old", "u2026_old", "2026-06-15 10:00:00", 100.0, "货架", False, False, False, "已付款", "803474428381", "护肤", "面霜", "修护面霜", "护肤"),
        ("o2026_member", "u2026_member", "2026-06-15 11:00:00", 200.0, "货架", True, False, False, "已付款", "597655781410", "护肤", "精华", "修护精华", "护肤"),
        ("o2026_sample", "u2026_sample", "2026-06-15 12:00:00", 50.0, "U先派样", False, False, False, "已付款", "621639424901", "试用", "小样", "体验装", "试用"),
        ("o2026_refund", "u2026_refund", "2026-06-15 13:00:00", 300.0, "货架", False, False, True, "已退款", "803474428381", "护肤", "面霜", "修护面霜", "护肤"),
        ("o2026_goujinjin", "u2026_gjj", "2026-06-15 14:00:00", 150.0, "赠品&0.01", False, True, False, "已付款", "803474428381", "赠品", "赠品", "赠品", "赠品"),
    ]
    conn.executemany("""
        INSERT INTO orders (
            order_id, user_id, pay_time, actual_amount, channel,
            is_member, is_goujinjin, is_refund, order_status,
            product_id, spu_tier, spu_product_class, spu_product_subclass, spu_category
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    first_purchase_rows = [
        ("u2024_old", "2024-05-10"),
        ("u2024_member", "2024-05-12"),
        ("u2024_sample", "2024-06-15"),
        ("u2025_old", "2025-05-10"),
        ("u2025_member", "2025-05-12"),
        ("u2025_sample", "2025-06-15"),
        ("u2026_old", "2026-05-10"),
        ("u2026_member", "2026-05-12"),
        ("u2026_sample", "2026-06-15"),
        ("u2026_refund", "2026-06-15"),
        ("u2026_gjj", "2026-06-15"),
    ]
    conn.executemany(
        "INSERT INTO user_first_purchase VALUES (?, ?::DATE)",
        first_purchase_rows,
    )

    rfm_users = [
        ("u2024_old", "2024 老客", 2, "2024-05-10", "2024-06-15", False, 90.0),
        ("u2024_member", "2024 会员", 1, "2024-05-12", "2024-06-15", True, 170.0),
        ("u2024_sample", "2024 小样", 7, "2024-06-15", "2024-06-15", False, 35.0),
        ("u2025_old", "2025 老客", 2, "2025-05-10", "2025-06-15", False, 100.0),
        ("u2025_member", "2025 会员", 1, "2025-05-12", "2025-06-15", True, 190.0),
        ("u2025_sample", "2025 小样", 7, "2025-06-15", "2025-06-15", False, 40.0),
        ("u2026_old", "2026 老客", 2, "2026-05-10", "2026-06-15", False, 120.0),
        ("u2026_member", "2026 会员", 1, "2026-05-12", "2026-06-15", True, 230.0),
        ("u2026_sample", "2026 小样", 7, "2026-06-15", "2026-06-15", False, 50.0),
    ]
    rfm_rows = [
        (
            user_id,
            nickname,
            analysis_date,
            metric_type,
            90,
            "全店",
            6,
            2,
            monetary,
            5,
            2,
            2,
            "普通客户",
            "Regular",
            segment_id,
            first_order_date,
            last_order_date,
            is_member,
        )
        for analysis_date in ("2024-06-21", "2025-06-21", "2026-06-21")
        for metric_type in ("GMV", "GSV")
        for (
            user_id,
            nickname,
            segment_id,
            first_order_date,
            last_order_date,
            is_member,
            monetary,
        ) in rfm_users
    ]
    conn.executemany(
        """
        INSERT INTO user_rfm (
            user_id, user_nickname, analysis_date, metric_type, lookback_days,
            channel, recency_days, frequency, monetary, r_score, f_score,
            m_score, rfm_tier, rfm_tier_en, segment_id, first_order_date,
            last_order_date, is_member
        )
        VALUES (?, ?, ?::DATE, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::DATE, ?::DATE, ?)
        """,
        rfm_rows,
    )
    return SyntheticDuckDBHandle(tmp_path, conn)


@pytest.fixture
def synthetic_duckdb_factory():
    """Factory for tests that need to assert tmp DB lifecycle explicitly."""
    handles: list[SyntheticDuckDBHandle] = []

    def _factory() -> SyntheticDuckDBHandle:
        handle = _create_tmp_duckdb_with_synthetic_orders()
        handles.append(handle)
        return handle

    try:
        yield _factory
    finally:
        for handle in handles:
            if handle.path.exists():
                handle.cleanup()


@pytest.fixture
def tmp_duckdb_with_synthetic_orders(synthetic_duckdb_factory):
    """CI-safe DuckDB fixture: tmp DB + minimal synthetic orders schema/data."""
    yield synthetic_duckdb_factory()


@pytest.fixture
def monkeypatch_synthetic_ad_hoc_connection(tmp_duckdb_with_synthetic_orders):
    """Patch service and ad-hoc read-only paths to use the synthetic DuckDB."""
    from contextlib import contextmanager
    import os

    from backend.db import connection
    from scripts.ad_hoc_queries import _utils as adhoc_utils

    class FakeThreadSafeConnection:
        def __init__(self, conn):
            self._conn = conn

        def execute(self, query, parameters=None):
            if parameters is not None:
                return self._conn.execute(query, parameters)
            return self._conn.execute(query)

        def close(self):
            pass

        def __getattr__(self, name):
            return getattr(self._conn, name)

    original_conn = connection._conn
    original_get_connection = connection.get_connection
    original_read_only_conn = adhoc_utils.read_only_conn
    original_worker_disabled = os.environ.get("FQ_AI_SANDBOX_WORKER_DISABLED")
    os.environ["FQ_AI_SANDBOX_WORKER_DISABLED"] = "1"

    def _fake_get_connection():
        return FakeThreadSafeConnection(tmp_duckdb_with_synthetic_orders)

    @contextmanager
    def _fake_read_only_conn(db_path=None, memory_limit=None):
        del db_path, memory_limit
        yield tmp_duckdb_with_synthetic_orders

    for module in tuple(sys.modules.values()):
        if module is None:
            continue
        if getattr(module, "get_connection", None) is original_get_connection:
            module.get_connection = _fake_get_connection
        if getattr(module, "read_only_conn", None) is original_read_only_conn:
            module.read_only_conn = _fake_read_only_conn

    connection._conn = None
    connection.get_connection = _fake_get_connection
    adhoc_utils.read_only_conn = _fake_read_only_conn

    try:
        yield tmp_duckdb_with_synthetic_orders
    finally:
        for module in tuple(sys.modules.values()):
            if module is None:
                continue
            if getattr(module, "get_connection", None) is _fake_get_connection:
                module.get_connection = original_get_connection
            if getattr(module, "read_only_conn", None) is _fake_read_only_conn:
                module.read_only_conn = original_read_only_conn
        connection.get_connection = original_get_connection
        connection._conn = original_conn
        adhoc_utils.read_only_conn = original_read_only_conn
        if original_worker_disabled is None:
            os.environ.pop("FQ_AI_SANDBOX_WORKER_DISABLED", None)
        else:
            os.environ["FQ_AI_SANDBOX_WORKER_DISABLED"] = original_worker_disabled


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


# ─────────────────────────────────────────────────────────────
# Sprint 201 R1 CI 爆红修复: rate limit bucket per-test reset (autouse)
#
# 背景: Sprint 200 R1 v2.1 加 rate_limit_middleware (每用户每分钟 N req) + Sprint 201 R1
# 加 dual_conn + query_router. backend/main.py 模块级 _rate_limit_buckets 字典在
# pytest 进程内跨 test 共享, 导致:
#   - test_rate_limit_sprint200.py 把 RATE_LIMIT_PER_MINUTE=5 设到 module scope
#   - 跑 5 次 admin token 触发 429, 写入 _rate_limit_buckets["admin"]
#   - 后续 test 调 synthetic_client (user=testuser) 走相同 rate_limit_middleware
#   - 如果 synthetic fixture 跟 admin 走同一 user_id (实测: 跟 token 解析逻辑), 命中 429
#   - 触发 429 → ad_hoc_query_api test 失败
#
# 修法: autouse fixture 在每个 test 前 reset _rate_limit_buckets + _RATE_LIMIT_PER_MINUTE
# 统一为 60 (跟 production 默认), 不让 test_rate_limit_sprint200.py 的 5 污染其他 test.
# ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_rate_limit_buckets():
    """Sprint 201 R1: per-test reset rate limit bucket (不强制 RATE_LIMIT_PER_MINUTE).

    Sprint 201 R1+ R2 v3 (L4.50 candidate followup): 不强制覆盖 RATE_LIMIT_PER_MINUTE=60, 避免
    覆盖 test_rate_limit_sprint200.py module-scope 设的 5 (跟之前 sprint stable 1:1).
    只清 _rate_limit_buckets 字典, env 留给 test 自己管 (test_rate_limit_sprint200.py:17
    设 5, 其他 test 不设就走 production default 60).
    """
    import backend.main as _main

    # Reset module-level _rate_limit_buckets 字典 (不强制覆盖 env)
    if hasattr(_main, "_rate_limit_buckets"):
        _main._rate_limit_buckets.clear()

    try:
        yield
    finally:
        if hasattr(_main, "_rate_limit_buckets"):
            _main._rate_limit_buckets.clear()


# ─────────────────────────────────────────────────────────────
# Sprint 201 R1+ R2 (L4.50 candidate): pytest-of-hutou 老 session + tracker 副本清理 (autouse)
#
# 真因: pytest 跑 test_layer6_skips_tracked_files + test_w4_t7_integration 等真连 prod DuckDB,
# 创建 fuqing_tracked.duckdb 副本 (~2GB, 跟生产 db 一样大). test 失败时 fixture teardown 不清


# ─────────────────────────────────────────────────────────────
# Sprint 201 R1+ R2 (L4.50 candidate): pytest-of-hutou 老 session + tracker 副本清理 (autouse)
#
# 真因: pytest 跑 test_layer6_skips_tracked_files + test_w4_t7_integration 等真连 prod DuckDB,
# 创建 fuqing_tracked.duckdb 副本 (~2GB, 跟生产 db 一样大). test 失败时 fixture teardown 不清
# tmp_path, 跨 sprint 累积 11+ 个老 session 目录 (20G+), 导致磁盘 99% 满 (Sprint 201 R1 v2.1 紧急排查).
#
# 修法: session-scope autouse fixture 在每次 pytest 启动时清理 24h+ 老 pytest-of-hutou session 目录
# (保留当前 pytest-current). 跟 sprint 178 L4.31 race flake 跨 sprint stable 模式 1:1, 杜绝后续累积.
# 深层治本 (Sprint 201 R1+ R2 8 天): macOS launchd hourly cleanup plist + pytest fixture teardown 强制删 fuqing_tracked.duckdb.
# ─────────────────────────────────────────────────────────────

_PYTEST_ROOT = Path("/private/var/folders/tz/wswl3q3117v437rw68yd90gh0000gn/T/pytest-of-hutou")


@pytest.fixture(scope="session", autouse=True)
def cleanup_old_pytest_sessions():
    """Sprint 201 R1+ R2 L4.50: 清理 24h+ 老 pytest session 目录, 保留 current.

    跨 sprint stable race flake 模式 1:1: 之前 sprint 178 L4.31 治 race flake, 这次治 pytest session
    磁盘累积. autouse session-scope 确保每次 pytest 启动时自动清, 不需要业务方手动跑.

    Sprint 201 R2 CI fix v23: 早 return 之前先 yield, 修复 CI #529+ ValueError 'did not yield a value'.
    pytest 把这个 fixture 当 generator 调用, 任何 return 路径必须在 yield 之前 yield 1 次.
    """
    yield  # 必须先 yield, 即使后面要早 return
    if not _PYTEST_ROOT.exists():
        return
    now = time.time()
    cleaned_count = 0
    cleaned_bytes = 0
    for d in _PYTEST_ROOT.iterdir():
        if not d.is_dir() or d.name == "pytest-current":
            continue
        # 24h+ 老 session 自动清
        try:
            mtime = d.stat().st_mtime
        except OSError:
            continue
        if (now - mtime) > 86400:  # 24h
            try:
                # 算 dir 大小 (粗估)
                size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                # 用 shutil.rmtree 安全删 (Sprint 178 hook 拦 rm -rf /, 但这里是相对路径安全)
                import shutil
                shutil.rmtree(d, ignore_errors=True)
                cleaned_count += 1
                cleaned_bytes += size
            except Exception:
                pass
    if cleaned_count:
        print(f"[L4.50 cleanup_old_pytest_sessions] Cleaned {cleaned_count} old session(s), "
              f"~{cleaned_bytes // (1024**2)} MB freed")


# ─────────────────────────────────────────────────────────────
# Sprint 201 R1+ R2 (L4.50 candidate): pytest_configure hook — 加载时立即清老 session
# (不依赖 autouse fixture 时序, 跟 test module-scope setdefault 1:1 stable)
# ─────────────────────────────────────────────────────────────

def pytest_configure(config):
    """Sprint 201 R1+ R2 L4.50: 加载时清 24h+ 老 pytest session, 跟 test module-scope RATE_LIMIT_PER_MINUTE 1:1."""
    if not _PYTEST_ROOT.exists():
        return
    now = time.time()
    cleaned_count = 0
    cleaned_bytes = 0
    for d in _PYTEST_ROOT.iterdir():
        if not d.is_dir() or d.name == "pytest-current":
            continue
        try:
            mtime = d.stat().st_mtime
        except OSError:
            continue
        if (now - mtime) > 21600:  # 6h (Sprint 201 R1+ R2 v4: 缩短 24h → 6h, 因为 test 写 2GB tracker 太大)
            try:
                size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                shutil.rmtree(d, ignore_errors=True)
                cleaned_count += 1
                cleaned_bytes += size
            except Exception:
                pass

    # Sprint 201 R1+ R2 v4: 删 1GB+ fuqing_tracked.duckdb 残留 (test_layer6_skips_tracked_files 写 2GB tracker 副本)
    # 即便 session < 6h, 残留的 2GB tracker 也得清, 避免单次 pytest 跑 2GB 累积
    for d in _PYTEST_ROOT.iterdir():
        if not d.is_dir():
            continue
        for f in d.rglob("fuqing_tracked.duckdb"):
            try:
                fsize = f.stat().st_size
                if fsize > 1024**3:  # 1GB+
                    f.unlink()
                    cleaned_count += 1
                    cleaned_bytes += fsize
            except OSError:
                pass

    if cleaned_count:
        print(f"[L4.50 pytest_configure] Cleaned {cleaned_count} old session(s) / 1GB+ tracker(s), "
              f"~{cleaned_bytes // (1024**2)} MB freed")
