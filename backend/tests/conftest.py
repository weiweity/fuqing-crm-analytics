"""
Pytest fixtures for backend service tests.
"""
import os
import subprocess
import sys
import tempfile
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


# Shared synthetic credentials are cached per Python process, never rehashed
# for each unrelated test. The application still uses its real cost-12 bcrypt.
from functools import lru_cache
from types import MappingProxyType

_TEST_CREDENTIALS_ENV = "admin:123456,fqsw:fqsw888,testuser:testpass123"
# Set a deterministic collection environment BEFORE any test imports the app.
# This does not inspect user credentials or load a local .env file.
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["HEALTH_API_KEY"] = "pytest-health-api-key"
os.environ["FQ_CRM_PASSWORDS"] = _TEST_CREDENTIALS_ENV
os.environ["FQ_CRM_ADMINS"] = "admin"


@lru_cache(maxsize=1)
def _synthetic_password_hashes():
    import bcrypt
    from backend.routers.auth import BCRYPT_ROUNDS

    return MappingProxyType({
        user: bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()
        for user, password in (pair.split(":", 1) for pair in _TEST_CREDENTIALS_ENV.split(","))
    })


def _clear_loaded_auth_state():
    # Do not import the app for pure Python, tooling or B0 tests. If a test
    # imports it lazily, the teardown still clears that newly loaded module.
    auth = sys.modules.get("backend.routers.auth")
    if auth is not None:
        for name in ("ACTIVE_TOKENS", "_LOGIN_ATTEMPTS", "_IP_LOGIN_ATTEMPTS"):
            getattr(auth, name).clear()
    login_request = sys.modules.get("backend.routers.login_request")
    if login_request is not None:
        login_request._reset_l4_85_state()


@pytest.fixture(autouse=True)
def _isolate_auth_runtime_state():
    _clear_loaded_auth_state()
    yield
    _clear_loaded_auth_state()


@pytest.fixture(autouse=True)
def _reset_fq_crm_credentials_env(monkeypatch):
    monkeypatch.setenv("FQ_CRM_PASSWORDS", _TEST_CREDENTIALS_ENV)
    auth = sys.modules.get("backend.routers.auth")
    original = dict(auth.VALID_CREDENTIALS) if auth is not None else None
    if auth is not None:
        auth.VALID_CREDENTIALS.clear()
        auth.VALID_CREDENTIALS.update(_synthetic_password_hashes())
    try:
        yield
    finally:
        # Restore the state snapshot, never call the production password loader
        # during teardown. Its configuration/hash behavior has dedicated tests.
        if original is not None:
            auth.VALID_CREDENTIALS.clear()
            auth.VALID_CREDENTIALS.update(original)


@pytest.fixture(autouse=True)
def _reset_fq_crm_admins_env(monkeypatch):
    monkeypatch.setenv("FQ_CRM_ADMINS", "admin")


# Compatibility with archived-data tests: availability now means an explicitly
# selected profile, not an automatic probe of backend.config or the real DB.
# Actual schema/lock checks happen only when the fixture is requested.
_PROD_DUCKDB_AVAILABLE = bool(os.environ.get("FQ_TEST_ARCHIVE_DB"))


def _detect_prod_duckdb_available(path: Path | None = None) -> bool:
    selected = str(path) if path is not None else os.environ.get("FQ_TEST_ARCHIVE_DB")
    if not selected:
        return False
    path = Path(selected)
    if not path.is_absolute() or not path.is_file():
        return False
    try:
        with duckdb.connect(str(path), read_only=True) as conn:
            return bool(conn.execute(
                "SELECT count(*) > 0 FROM information_schema.tables WHERE lower(table_name) = 'orders'"
            ).fetchone()[0])
    except duckdb.Error:
        return False


def _duckdb_lock_holder_pid() -> int | None:
    selected = os.environ.get("FQ_TEST_ARCHIVE_DB")
    if not selected:
        return None
    try:
        result = subprocess.run(["lsof", "-t", selected], capture_output=True, text=True, timeout=5)
        return next((int(p) for p in result.stdout.split() if p.isdigit()), None)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


@pytest.fixture(scope="module")
def isolated_duckdb():
    """Explicit archive profile only; normal tests use synthetic fixtures."""
    selected = os.environ.get("FQ_TEST_ARCHIVE_DB")
    if not selected:
        pytest.skip("archived-data acceptance requires separately authorized FQ_TEST_ARCHIVE_DB")
    if not _detect_prod_duckdb_available(Path(selected)):
        pytest.fail("Explicit archive fixture is unavailable or lacks orders; no fallback")
    with tempfile.TemporaryDirectory(prefix="fq-pytest-duckdb-") as tmp_dir:
        conn = duckdb.connect(str(Path(tmp_dir) / "isolated.duckdb"),
                              config={"memory_limit": "2GB"})
        try:
            conn.execute("SET threads = 2")
            quoted = selected.replace("'", "''")
            conn.execute(f"ATTACH '{quoted}' AS prod (READ_ONLY)")
            conn.execute("PRAGMA search_path='main,prod'")
            yield conn
        finally:
            conn.close()


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
    if not os.environ.get("FQ_TEST_ARCHIVE_DB"):
        pytest.skip("archived-data fixture requires explicit authorization/profile")
    holder_pid = _duckdb_lock_holder_pid()
    if holder_pid is not None:
        pytest.skip(
            f"生产 DuckDB 被 PID {holder_pid} 占 fd, 跳过 (避免跨进程锁冲突). "
            "Preserve the owner process; do not stop services for a test."
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


# Cleanup tests opt in explicitly; ordinary tests never import ETL/tracker.
@pytest.fixture
def isolate_tmp_tracker(tmp_path, monkeypatch):
    """Redirect every tracker default and log to this test's owned directory."""
    from scripts.etl import cli
    from scripts.etl.common import tmp_tracker
    import os
    original_cli_path = cli._FQ_TMP_TRACKER_PATH
    original_tracker_default = tmp_tracker.TRACKER_DB_PATH
    test_db = str(tmp_path / "test-tracker.db")
    # The constructor default is bound at definition time, not to the constant.
    monkeypatch.setattr(tmp_tracker.TrackerDB.__init__, "__defaults__", (test_db,))
    monkeypatch.setattr(tmp_tracker, "_LOG_PATH", str(tmp_path / "tracker.log"))
    monkeypatch.setattr(cli, "_FQ_TMP_LOG_PATH", str(tmp_path / "cleanup.log"))
    monkeypatch.setattr(cli, "_FQ_TMP_MARKER_PATH", str(tmp_path / "marker.json"))
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


# Isolate only loaded request buckets; the limit belongs to each test fixture.
@pytest.fixture(autouse=True)
def reset_rate_limit_buckets():
    """隔离每个用例的请求桶；阈值由用例夹具设置并恢复，不覆盖显式环境。"""
    _main = sys.modules.get("backend.main")

    # Reset module-level _rate_limit_buckets 字典 (不强制覆盖 env)
    if hasattr(_main, "_rate_limit_buckets"):
        _main._rate_limit_buckets.clear()

    try:
        yield
    finally:
        loaded = sys.modules.get("backend.main")
        if hasattr(loaded, "_rate_limit_buckets"):
            loaded._rate_limit_buckets.clear()


def pytest_configure(config):
    """Own one scratch directory; do not scan/delete any previous session."""
    selected = os.environ.get("FQ_TEST_ARCHIVE_DB")
    if selected and not Path(selected).is_absolute():
        raise pytest.UsageError("FQ_TEST_ARCHIVE_DB must be an explicitly authorized absolute path")
    scratch = tempfile.TemporaryDirectory(prefix="fq-tests-")
    config.add_cleanup(scratch.cleanup)
    root = Path(scratch.name)
    # Safe defaults before collection; integration tests override only with
    # their own tiny fixtures. No fallback to the checkout's archived DB.
    os.environ["DUCKDB_PATH"] = selected or str(root / "not-configured.duckdb")
    os.environ["FUQING_DB_PATH"] = os.environ["DUCKDB_PATH"]
    os.environ["CACHE_DUCKDB_PATH"] = str(root / "cache.duckdb")
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    for name in ("SHOP_DATA_SOURCE", "MEMBER_DATA_SOURCE", "SPU_MAPPING_SOURCE",
                 "SHOP_STATUS_SOURCE", "VISITOR_DATA_SOURCE", "VISITOR_XLSX_FILE",
                 "CAMPAIGN_SCHEDULE_SOURCE", "CHANNEL_RULES_SOURCE",
                 "TAOKE_DATA_SOURCE", "TAOKE_PRODUCT_SOURCE", "LIVE_DATA_SOURCE", "DMP_DATA_DIR"):
        os.environ[name] = str(root / "inputs" / name.lower())
