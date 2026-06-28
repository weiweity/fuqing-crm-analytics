"""Sprint 143 cohort retention matrix 回归测试."""

import sys

import duckdb
import pytest


@pytest.fixture
def memory_connection(monkeypatch):
    """Sprint 143 新增测试使用隔离 DuckDB，不依赖生产库锁状态."""
    conn = duckdb.connect(":memory:")

    class FakeThreadSafeConnection:
        def __init__(self, raw_conn):
            self._conn = raw_conn

        def execute(self, query, parameters=None):
            if parameters is not None:
                return self._conn.execute(query, parameters)
            return self._conn.execute(query)

        def __getattr__(self, name):
            return getattr(self._conn, name)

    fake = FakeThreadSafeConnection(conn)

    def _fake_get_connection():
        return fake

    from backend.db import connection

    original_get_connection = connection.get_connection
    monkeypatch.setattr(connection, "get_connection", _fake_get_connection)

    for module in tuple(sys.modules.values()):
        if (
            module is not None
            and getattr(module, "__name__", "").startswith("backend.")
            and getattr(module, "get_connection", None) is not None
        ):
            monkeypatch.setattr(module, "get_connection", _fake_get_connection, raising=False)

    try:
        yield conn
    finally:
        for module in tuple(sys.modules.values()):
            if module is not None and getattr(module, "get_connection", None) is _fake_get_connection:
                module.get_connection = original_get_connection
        conn.close()


def _install_orders(conn, rows):
    conn.execute("""
        CREATE OR REPLACE TABLE orders (
            order_id VARCHAR,
            user_id VARCHAR,
            pay_time TIMESTAMP,
            actual_amount DOUBLE,
            is_goujinjin BOOLEAN,
            order_status VARCHAR,
            is_refund BOOLEAN,
            channel VARCHAR
        )
    """)
    if rows:
        conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)


class TestCohortRetentionSprint143:
    """Sprint 143: cohort retention matrix 按月 cohort + 0-12 月留存."""

    def test_cohort_retention_basic(self, memory_connection):
        """cohort retention matrix 返回 cohort 行和 offset 留存率."""
        _install_orders(memory_connection, [
            ("u1-jan", "u1", "2025-01-05 10:00:00", 10.0, False, "交易成功", False, "U先派样"),
            ("u1-feb", "u1", "2025-02-05 10:00:00", 10.0, False, "交易成功", False, "U先派样"),
            ("u1-mar", "u1", "2025-03-05 10:00:00", 10.0, False, "交易成功", False, "U先派样"),
            ("u2-jan", "u2", "2025-01-10 10:00:00", 10.0, False, "交易成功", False, "U先派样"),
            ("u2-feb", "u2", "2025-02-10 10:00:00", 10.0, False, "交易成功", False, "U先派样"),
            ("u3-feb", "u3", "2025-02-01 10:00:00", 10.0, False, "交易成功", False, "U先派样"),
        ])

        from backend.semantic.cohort_retention import compute_cohort_retention

        result = compute_cohort_retention(memory_connection, "2025-01", "2025-02")
        by_month = {row.cohort_month: row for row in result}

        assert set(by_month) == {"2025-01", "2025-02"}
        assert by_month["2025-01"].cohort_size == 2
        assert by_month["2025-01"].retention[0] == pytest.approx(1.0)
        assert by_month["2025-01"].retention[1] == pytest.approx(1.0)
        assert by_month["2025-01"].retention[2] == pytest.approx(0.5)

    def test_cohort_retention_monotonic_decreasing_fixture(self, memory_connection):
        """合成数据中 cohort 留存随 offset 不上升."""
        _install_orders(memory_connection, [
            ("a0", "a", "2025-01-01 10:00:00", 10.0, False, "交易成功", False, "U先派样"),
            ("a1", "a", "2025-02-01 10:00:00", 10.0, False, "交易成功", False, "U先派样"),
            ("b0", "b", "2025-01-02 10:00:00", 10.0, False, "交易成功", False, "U先派样"),
            ("c0", "c", "2025-01-03 10:00:00", 10.0, False, "交易成功", False, "U先派样"),
        ])

        from backend.semantic.cohort_retention import compute_cohort_retention

        result = compute_cohort_retention(memory_connection, "2025-01", "2025-01")
        row = result[0]
        offsets = sorted(row.retention)
        values = [row.retention[offset] for offset in offsets]

        assert values == sorted(values, reverse=True)

    def test_cohort_retention_channel_filter(self, memory_connection):
        """channel 参数正确过滤 cohort 和活跃订单."""
        _install_orders(memory_connection, [
            ("u1-jan", "u1", "2025-01-05 10:00:00", 10.0, False, "交易成功", False, "U先派样"),
            ("u1-feb", "u1", "2025-02-05 10:00:00", 10.0, False, "交易成功", False, "U先派样"),
            ("u2-jan", "u2", "2025-01-05 10:00:00", 10.0, False, "交易成功", False, "百补派样"),
            ("u2-feb", "u2", "2025-02-05 10:00:00", 10.0, False, "交易成功", False, "百补派样"),
        ])

        from backend.semantic.cohort_retention import compute_cohort_retention

        all_rows = compute_cohort_retention(memory_connection, "2025-01", "2025-01", "全店")
        u先_rows = compute_cohort_retention(memory_connection, "2025-01", "2025-01", "U先派样")

        assert all_rows[0].cohort_size == 2
        assert u先_rows[0].cohort_size == 1
        assert u先_rows[0].retention[1] == pytest.approx(1.0)

    def test_cohort_retention_w4_cache(self, memory_connection):
        """W4 cache 24h TTL 验证."""
        _install_orders(memory_connection, [
            ("cache-jan", "cache-user", "2025-01-05 10:00:00", 10.0, False, "交易成功", False, "U先派样"),
        ])

        from backend.services.cohort_retention_service import get_cohort_retention_matrix
        from backend.services.rfm.cache import RfmQueryCache

        RfmQueryCache().invalidate()
        first = get_cohort_retention_matrix("2025-01", "2025-01", use_cache=True)

        _install_orders(memory_connection, [])
        cached = get_cohort_retention_matrix("2025-01", "2025-01", use_cache=True)
        fresh = get_cohort_retention_matrix("2025-01", "2025-01", use_cache=False)

        assert first[0].cohort_size == 1
        assert cached[0].cohort_size == 1
        assert fresh == []
