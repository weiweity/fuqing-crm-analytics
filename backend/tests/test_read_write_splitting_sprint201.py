"""Sprint 201 R1 read/write splitting regression tests."""
from __future__ import annotations

import concurrent.futures
import glob
from pathlib import Path
import time

import duckdb
import pytest

VALID_SANDBOX_SQL = """
SELECT
    COUNT(DISTINCT o.user_id) AS users,
    SUM(o.actual_amount) AS gsv
FROM orders o
WHERE o.is_goujinjin = FALSE
  AND o.order_status != '交易关闭'
  AND o.is_refund = FALSE
"""


@pytest.fixture(autouse=True)
def close_dual_connections():
    from backend.db import connection
    from backend.services.dual_conn import close_all_connections

    close_all_connections()
    connection._conn = None
    try:
        yield
    finally:
        close_all_connections()
        connection._conn = None


@pytest.fixture
def worker_duckdb_path(tmp_path: Path) -> Path:
    path = tmp_path / "worker.duckdb"
    conn = duckdb.connect(str(path), config={"memory_limit": "1GB"})
    conn.execute(
        """
        CREATE TABLE orders (
            order_id VARCHAR,
            user_id VARCHAR,
            actual_amount DOUBLE,
            is_goujinjin BOOLEAN,
            order_status VARCHAR,
            is_refund BOOLEAN
        )
        """
    )
    conn.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("o1", "u1", 10.0, False, "已付款", False),
            ("o2", "u2", 20.0, False, "已付款", False),
            ("o3", "u3", 30.0, False, "交易关闭", False),
            ("o4", "u4", 40.0, False, "已付款", True),
            ("o5", "u5", 50.0, True, "已付款", False),
        ],
    )
    conn.close()
    return path


class TestDualConnectionRouting:
    def test_read_connection_is_readonly(self, monkeypatch, worker_duckdb_path):
        from backend.services import dual_conn

        monkeypatch.setattr(dual_conn, "DUCKDB_PATH", worker_duckdb_path)
        conn = dual_conn.get_read_connection()
        try:
            assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 5
            with pytest.raises(Exception):
                conn.execute("INSERT INTO orders VALUES ('x', 'u', 1, FALSE, '已付款', FALSE)")
        finally:
            dual_conn.return_read_connection(conn)

    def test_get_connection_uses_read_request_context(self, monkeypatch, worker_duckdb_path):
        from backend.db.connection import get_connection
        from backend.services import dual_conn

        monkeypatch.setattr(dual_conn, "DUCKDB_PATH", worker_duckdb_path)
        with dual_conn.read_request_context():
            conn = get_connection()
            assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 5
            with pytest.raises(Exception):
                conn.execute("INSERT INTO orders VALUES ('x', 'u', 1, FALSE, '已付款', FALSE)")

    def test_write_connection_is_singleton_for_non_http_jobs(self, monkeypatch, worker_duckdb_path):
        from backend.services import dual_conn

        monkeypatch.setattr(dual_conn, "DUCKDB_PATH", worker_duckdb_path)
        c1 = dual_conn.get_write_connection()
        c2 = dual_conn.get_write_connection()
        assert c1 is c2

    def test_query_router_classifies_read_worker_and_default(self):
        from backend.middleware.query_router import QueryRouterMiddleware

        router = QueryRouterMiddleware(lambda scope, receive, send: None)
        assert router.classify("/api/v1/audience/summary", "GET") == "read"
        assert router.classify("/api/v1/ad-hoc/ai-sandbox-execute", "POST") == "worker"
        assert router.classify("/api/v1/auth/login", "POST") == "default"
        assert router.classify("/api/v1/health", "GET") == "default"

    def test_w5_cache_writes_degrade_in_readonly_request(self, monkeypatch, worker_duckdb_path):
        from backend.services import dual_conn
        from backend.services.rfm.cache import RfmQueryCache

        monkeypatch.setattr(dual_conn, "DUCKDB_PATH", worker_duckdb_path)
        cache = RfmQueryCache()

        with dual_conn.read_request_context():
            assert cache.get("endpoint", {"a": 1}) is None
            cache.set("endpoint", {"a": 1}, {"ok": True})
            assert cache.invalidate() == 0
            assert cache.cleanup_expired() == 0
            assert cache.list_keys() == []
            assert cache.stats() == {"total": 0, "valid": 0, "expired": 0}


class TestQueryWorkerIsolation:
    def test_query_worker_valid_order_query(self, worker_duckdb_path):
        from backend.services.query_worker_client import execute_via_query_worker

        result = execute_via_query_worker(VALID_SANDBOX_SQL, duckdb_path=worker_duckdb_path)

        assert result["success"] is True
        assert result["headers"] == ["users", "gsv"]
        assert result["rows"] == [[2, 30.0]]

    def test_query_worker_invalid_sql_rejected(self, worker_duckdb_path):
        from backend.services.query_worker_client import execute_via_query_worker

        result = execute_via_query_worker("DROP TABLE orders", duckdb_path=worker_duckdb_path)

        assert result["success"] is False
        assert "DROP" in result["error"]

    def test_query_worker_missing_valid_order_rejected(self, worker_duckdb_path):
        from backend.services.query_worker_client import execute_via_query_worker

        result = execute_via_query_worker("SELECT COUNT(*) FROM orders", duckdb_path=worker_duckdb_path)

        assert result["success"] is False
        assert "valid_order" in result["error"]

    def test_ai_sandbox_execute_uses_worker(self, worker_duckdb_path, monkeypatch):
        from backend.services.ai_sandbox import ai_sandbox_execute

        monkeypatch.delenv("FQ_AI_SANDBOX_WORKER_DISABLED", raising=False)
        result = ai_sandbox_execute(
            VALID_SANDBOX_SQL,
            audit_id="sprint201-worker",
            duckdb_path=str(worker_duckdb_path),
        )

        assert result["headers"] == ["users", "gsv"]
        assert result["rows"] == [[2, 30.0]]
        assert result["row_count"] == 1

    def test_query_worker_creates_no_tmp_py_files(self, worker_duckdb_path):
        from backend.services.query_worker_client import execute_via_query_worker

        before = set(glob.glob("/tmp/*.py"))
        result = execute_via_query_worker(VALID_SANDBOX_SQL, duckdb_path=worker_duckdb_path)
        after = set(glob.glob("/tmp/*.py"))

        assert result["success"] is True
        assert after - before == set()


class TestConcurrentReadOnlyAccess:
    def test_many_readers_and_workers_can_run_concurrently(self, worker_duckdb_path):
        from backend.services.query_worker_client import execute_via_query_worker

        def read_direct(_idx: int) -> int:
            conn = duckdb.connect(str(worker_duckdb_path), read_only=True)
            try:
                return conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            finally:
                conn.close()

        def read_worker(_idx: int) -> dict:
            return execute_via_query_worker(VALID_SANDBOX_SQL, duckdb_path=worker_duckdb_path)

        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            direct = [executor.submit(read_direct, i) for i in range(20)]
            workers = [executor.submit(read_worker, i) for i in range(5)]
            direct_results = [future.result(timeout=20) for future in direct]
            worker_results = [future.result(timeout=20) for future in workers]

        assert direct_results == [5] * 20
        assert all(result["success"] is True for result in worker_results)
        assert {tuple(result["rows"][0]) for result in worker_results} == {(2, 30.0)}


class TestSnapshotAndMetrics:
    # Sprint 201 R2 L2 (L4.53 永久规则): snapshot 机制已根除, 整类 skip
    # 跟 Sprint 178 L4.31 + Sprint 184 L4.38 + Sprint 200 R1 L4.50 跨 sprint stable 1:1
    # Read-Write Splitting 已够 (L4.51 配套)
    @pytest.mark.skip(
        reason="L4.53: snapshot 机制 Sprint 201 R2 已根除 (Read-Write Splitting 已够, ATTACH read_only 替代)"
    )
    def test_snapshot_creation_is_atomic_and_cleans_old_files(self, tmp_path):
        from scripts.dump_duckdb_snapshot import cleanup_old_snapshots, create_snapshot

        source = tmp_path / "source.duckdb"
        snapshot_dir = tmp_path / "snapshots"
        source.write_bytes(b"duckdb-bytes")
        old = snapshot_dir / "fuqing_crm_1.duckdb"
        snapshot_dir.mkdir()
        old.write_bytes(b"old")
        old_mtime = time.time() - 31 * 86400
        old.touch()
        old.chmod(0o600)
        import os

        os.utime(old, (old_mtime, old_mtime))

        snapshot = create_snapshot(source, snapshot_dir, timestamp=2)
        deleted = cleanup_old_snapshots(snapshot_dir, retention_days=30)

        assert snapshot.read_bytes() == b"duckdb-bytes"
        assert not snapshot.with_suffix(".duckdb.tmp").exists()
        assert deleted == 1
        assert not old.exists()

    def test_prometheus_metrics_render_query_labels(self):
        from backend.services.query_metrics import record_query, render_prometheus, reset_query_metrics

        reset_query_metrics()
        record_query("/api/v1/audience/summary", "read", 0.12)
        text = render_prometheus()

        assert "fq_query_total" in text
        assert 'endpoint="/api/v1/audience/summary",query_type="read"' in text
        assert "fq_query_duration_seconds_bucket" in text

    def test_metrics_endpoint_bypasses_auth_and_db(self):
        from fastapi.testclient import TestClient

        from backend.main import app
        from backend.services.query_metrics import record_query, reset_query_metrics

        reset_query_metrics()
        record_query("/api/v1/audience/summary", "read", 0.12)
        response = TestClient(app).get("/metrics")

        assert response.status_code == 200
        assert "fq_query_total" in response.text
