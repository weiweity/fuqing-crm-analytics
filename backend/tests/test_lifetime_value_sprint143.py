"""Sprint 143 LTV 90/180/365d 回归测试."""

from pathlib import Path
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


class TestLifetimeValueSprint143:
    """Sprint 143: LTV 90/180/365d 累计 GSV 计算."""

    def test_ltv_3_windows_monotonic(self, memory_connection):
        """LTV 90d <= LTV 180d <= LTV 365d."""
        _install_orders(memory_connection, [
            ("o1", "u1", "2026-01-11 10:00:00", 100.0, False, "交易成功", False, "U先派样"),
            ("o2", "u1", "2026-04-11 10:00:00", 200.0, False, "交易成功", False, "U先派样"),
            ("o3", "u1", "2026-10-28 10:00:00", 300.0, False, "交易成功", False, "U先派样"),
        ])

        from backend.semantic.lifetime_value import compute_ltv_for_user

        result = compute_ltv_for_user(memory_connection, "u1", "2026-01-01")

        assert result.gsv_90d == pytest.approx(100.0)
        assert result.gsv_180d == pytest.approx(300.0)
        assert result.gsv_365d == pytest.approx(600.0)
        assert result.gsv_90d <= result.gsv_180d <= result.gsv_365d
        assert (result.order_count_90d, result.order_count_180d, result.order_count_365d) == (1, 2, 3)

    def test_ltv_excludes_refund_closed_and_goujinjin(self, memory_connection):
        """LTV 计算排除退款单、关闭单和购物金订单."""
        _install_orders(memory_connection, [
            ("valid", "u2", "2026-01-10 10:00:00", 100.0, False, "交易成功", False, "U先派样"),
            ("refund", "u2", "2026-01-11 10:00:00", 900.0, False, "交易成功", True, "U先派样"),
            ("closed", "u2", "2026-01-12 10:00:00", 800.0, False, "交易关闭", False, "U先派样"),
            ("goujinjin", "u2", "2026-01-13 10:00:00", 700.0, True, "交易成功", False, "购物金"),
        ])

        from backend.semantic.lifetime_value import compute_ltv_for_user

        result = compute_ltv_for_user(memory_connection, "u2", "2026-01-01")

        assert result.gsv_90d == pytest.approx(100.0)
        assert result.order_count_90d == 1

    def test_ltv_w4_cache_24h_ttl(self, memory_connection):
        """W4 cache 命中时返回旧值，绕过 cache 后看到新表数据."""
        _install_orders(memory_connection, [
            ("cache-1", "cache-user", "2026-01-10 10:00:00", 123.0, False, "交易成功", False, "U先派样"),
        ])

        from backend.services.lifetime_value_service import get_user_ltv
        from backend.services.rfm.cache import RfmQueryCache

        RfmQueryCache().invalidate()
        first = get_user_ltv("cache-user", "2026-01-01", use_cache=True)

        _install_orders(memory_connection, [])
        cached = get_user_ltv("cache-user", "2026-01-01", use_cache=True)
        fresh = get_user_ltv("cache-user", "2026-01-01", use_cache=False)

        assert first.gsv_90d == pytest.approx(123.0)
        assert cached.gsv_90d == pytest.approx(123.0)
        assert fresh.gsv_90d == pytest.approx(0.0)


def test_lifetime_value_contract_file_exists():
    """新增 contract 文件随 Sprint 143 落地."""
    repo_root = Path(__file__).resolve().parents[2]
    assert (repo_root / "backend/contracts/lifetime_value.py").exists()
