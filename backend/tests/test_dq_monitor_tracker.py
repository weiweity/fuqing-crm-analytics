"""DQ monitor read-only 直连与报告/告警回归测试.

安全契约:
  - 禁止复制生产 DuckDB 到 /tmp
  - 只用 ``read_only=True`` 直连生产路径
  - 连接失败明确返回维护窗口建议，不写快照/报告、不发业务 DQ 告警
  - 查询成功或异常时都关闭连接
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class _StubResult:
    """模拟 duckdb query result (有 fetchone/fetchall)."""
    def __init__(self, rows):
        self._rows = rows
    def fetchone(self):
        return self._rows[0] if self._rows else None
    def fetchall(self):
        return list(self._rows)


class _StubConn:
    """模拟 duckdb connection — 不真连 DB."""

    def __init__(self):
        self.closed = False

    def execute(self, sql, params=None):
        if "COUNT(*)" in sql and "orders" in sql and "is_member" not in sql:
            return _StubResult([(100,)])
        if "is_member = TRUE" in sql:
            return _StubResult([(50,)])
        if "DATE(pay_time)" in sql and "SUM" in sql:
            return _StubResult([(5000.0,)])
        if "DATE(pay_time) >=" in sql:
            return _StubResult([(50,)])
        return _StubResult([(0,)])

    def close(self):
        self.closed = True


class TestDqMonitorReadOnlyConnection:
    """DQ monitor 不产生临时整库副本，并正确处理连接生命周期."""

    def test_main_connects_prod_read_only_without_temp_copy(self, tmp_path, monkeypatch):
        """成功路径只直连原库，禁止调用 copy2，并关闭连接."""
        from scripts.etl import dq_monitor

        prod_db = tmp_path / "fake_prod.duckdb"
        prod_db.write_bytes(b"production-sentinel")
        monkeypatch.setattr(dq_monitor, "DUCKDB_PATH", prod_db)
        monkeypatch.setattr(dq_monitor, "SNAPSHOT_PATH", tmp_path / "dq_snapshot.json")
        monkeypatch.setattr(sys, "argv", ["dq_monitor"])

        def forbid_copy(*args, **kwargs):
            raise AssertionError("DQ monitor 禁止复制生产 DuckDB")

        monkeypatch.setattr(dq_monitor.shutil, "copy2", forbid_copy)
        expected_result = {
            "timestamp": "2026-07-26T12:00:00+08:00",
            "checks": {
                "orders_count": {"current": 100, "passed": True, "detail": "正常"},
                "member_ratio": {"current": 0.5, "passed": True, "detail": "正常"},
            },
            "all_passed": True,
        }
        monkeypatch.setattr(dq_monitor, "run_checks", lambda conn: expected_result)

        conn = _StubConn()
        connect_calls = []
        import duckdb

        def fake_connect(path, **kwargs):
            connect_calls.append((path, kwargs))
            return conn

        monkeypatch.setattr(duckdb, "connect", fake_connect)

        assert dq_monitor.main() == 0
        assert connect_calls == [(str(prod_db), {"read_only": True})]
        assert conn.closed is True
        assert prod_db.read_bytes() == b"production-sentinel"
        assert not any(path.name.startswith("fuqing_dq_monitor_") for path in tmp_path.iterdir())

    def test_connection_lock_fails_with_maintenance_advice(
        self, tmp_path, monkeypatch, capsys
    ):
        """写锁冲突时返回结构化失败，不复制、不写报告/快照、不告警."""
        from scripts.etl import dq_monitor

        prod_db = tmp_path / "fake_prod.duckdb"
        prod_db.write_bytes(b"production-sentinel")
        report_dir = tmp_path / "processed"
        monkeypatch.setattr(dq_monitor, "DUCKDB_PATH", prod_db)
        monkeypatch.setattr(dq_monitor, "PROCESSED_DATA_DIR", report_dir)
        monkeypatch.setattr(dq_monitor, "SNAPSHOT_PATH", report_dir / "dq_snapshot.json")
        monkeypatch.setattr(sys, "argv", ["dq_monitor", "--report", "--alert"])

        def forbid_copy(*args, **kwargs):
            raise AssertionError("连接失败时也禁止复制生产 DuckDB")

        monkeypatch.setattr(dq_monitor.shutil, "copy2", forbid_copy)
        alert_calls = []
        monkeypatch.setattr(
            dq_monitor,
            "send_lark_alert",
            lambda content: alert_calls.append(content),
        )
        import duckdb

        def locked_connect(*args, **kwargs):
            raise RuntimeError("Could not set lock on file: conflicting lock is held")

        monkeypatch.setattr(duckdb, "connect", locked_connect)

        assert dq_monitor.main() == 1
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["error"] == "database unavailable"
        assert payload["reason"] == "read_only connection failed"
        assert "维护窗口" in payload["advice"]
        assert "不会复制生产库" in payload["advice"]
        assert alert_calls == []
        assert not (report_dir / "dq_report.json").exists()
        assert not (report_dir / "dq_snapshot.json").exists()
        assert prod_db.read_bytes() == b"production-sentinel"

    def test_connection_closes_when_checks_raise(self, tmp_path, monkeypatch):
        """查询阶段抛错也必须通过 finally 关闭 read-only 连接."""
        from scripts.etl import dq_monitor

        prod_db = tmp_path / "fake_prod.duckdb"
        prod_db.write_bytes(b"production-sentinel")
        monkeypatch.setattr(dq_monitor, "DUCKDB_PATH", prod_db)
        monkeypatch.setattr(sys, "argv", ["dq_monitor"])

        conn = _StubConn()
        import duckdb

        monkeypatch.setattr(duckdb, "connect", lambda *args, **kwargs: conn)

        def failing_checks(_conn):
            raise RuntimeError("simulated query failure")

        monkeypatch.setattr(dq_monitor, "run_checks", failing_checks)

        with pytest.raises(RuntimeError, match="simulated query failure"):
            dq_monitor.main()

        assert conn.closed is True
        assert prod_db.read_bytes() == b"production-sentinel"

    def test_report_and_alert_behavior_is_preserved(self, tmp_path, monkeypatch):
        """成功连接后，失败检查仍写报告、保存快照并触发既有告警流程."""
        from scripts.etl import dq_monitor

        prod_db = tmp_path / "fake_prod.duckdb"
        prod_db.write_bytes(b"production-sentinel")
        report_dir = tmp_path / "processed"
        monkeypatch.setattr(dq_monitor, "DUCKDB_PATH", prod_db)
        monkeypatch.setattr(dq_monitor, "PROCESSED_DATA_DIR", report_dir)
        monkeypatch.setattr(dq_monitor, "SNAPSHOT_PATH", report_dir / "dq_snapshot.json")
        monkeypatch.setattr(sys, "argv", ["dq_monitor", "--report", "--alert"])

        failed_result = {
            "timestamp": "2026-07-26T12:00:00+08:00",
            "checks": {
                "orders_count": {"current": 100, "passed": True, "detail": "正常"},
                "member_ratio": {"current": 0.5, "passed": True, "detail": "正常"},
                "gsv_nonzero": {"current": 0, "passed": False, "detail": "今日 GSV 为 0"},
            },
            "all_passed": False,
        }
        monkeypatch.setattr(dq_monitor, "run_checks", lambda conn: failed_result)

        conn = _StubConn()
        import duckdb

        monkeypatch.setattr(duckdb, "connect", lambda *args, **kwargs: conn)
        alert_calls = []

        def fake_alert(content):
            alert_calls.append(content)
            return True, "test"

        monkeypatch.setattr(dq_monitor, "send_lark_alert", fake_alert)

        assert dq_monitor.main() == 2
        assert conn.closed is True
        assert json.loads((report_dir / "dq_report.json").read_text()) == failed_result
        snapshot = json.loads((report_dir / "dq_snapshot.json").read_text())
        assert snapshot["orders_count"] == 100
        assert snapshot["member_ratio"] == 0.5
        assert len(alert_calls) == 1
        assert "gsv_nonzero" in alert_calls[0]
        assert "今日 GSV 为 0" in alert_calls[0]


class TestDqMonitorDiskAndGrowth:
    """Sprint 51 — Check 5 (磁盘空间) + Check 6 (订单增长) 测试."""

    def test_disk_space_alert_when_low(self, tmp_path, monkeypatch):
        """磁盘可用空间 < 阈值时应告警."""
        from scripts.etl import dq_monitor

        monkeypatch.setattr(dq_monitor, "DUCKDB_PATH", tmp_path / "fake.duckdb")
        (tmp_path / "fake.duckdb").write_bytes(b"x" * 100)

        # mock shutil.disk_usage 返回低可用空间 (100GB free, 阈值 max(0.0001GB*2, 200GB) = 200GB)
        class _LowDisk:
            def __init__(self):
                self.total = 500 * 1024**3
                self.used = 400 * 1024**3
                self.free = 100 * 1024**3  # 100GB free < 200GB threshold
        monkeypatch.setattr(dq_monitor.shutil, "disk_usage", lambda _: _LowDisk())

        result = dq_monitor.run_checks(_StubConn())
        check5 = result["checks"]["disk_space"]
        assert check5["passed"] is False
        assert "磁盘可用空间不足" in check5["detail"]

    def test_disk_space_pass_when_enough(self, tmp_path, monkeypatch):
        """磁盘空间充足时应通过."""
        from scripts.etl import dq_monitor

        monkeypatch.setattr(dq_monitor, "DUCKDB_PATH", tmp_path / "fake.duckdb")
        (tmp_path / "fake.duckdb").write_bytes(b"x" * 100)

        class _EnoughDisk:
            def __init__(self):
                self.total = 1000 * 1024**3
                self.used = 500 * 1024**3
                self.free = 500 * 1024**3  # 500GB > 200GB threshold
        monkeypatch.setattr(dq_monitor.shutil, "disk_usage", lambda _: _EnoughDisk())

        result = dq_monitor.run_checks(_StubConn())
        check5 = result["checks"]["disk_space"]
        assert check5["passed"] is True
        assert "正常" in check5["detail"]

    def test_orders_growth_alert_when_abnormal(self, tmp_path, monkeypatch):
        """订单量增长 >50% 时应告警."""
        from scripts.etl import dq_monitor

        monkeypatch.setattr(dq_monitor, "DUCKDB_PATH", tmp_path / "fake.duckdb")
        (tmp_path / "fake.duckdb").write_bytes(b"x" * 100)

        # mock disk space to pass
        class _EnoughDisk:
            def __init__(self):
                self.total = 1000 * 1024**3
                self.used = 500 * 1024**3
                self.free = 500 * 1024**3
        monkeypatch.setattr(dq_monitor.shutil, "disk_usage", lambda _: _EnoughDisk())

        # 设置快照: 上次 100 条, StubConn 返回 100 条 → 增长 0% (不触发)
        # 需要 mock load_snapshot 返回 50 条 → (100-50)/50 = 100% > 50%
        snapshot = {"orders_count": 50, "member_ratio": 0.5, "timestamp": "2026-06-01"}
        monkeypatch.setattr(dq_monitor, "load_snapshot", lambda: snapshot)

        result = dq_monitor.run_checks(_StubConn())
        check6 = result["checks"]["orders_growth"]
        assert check6["passed"] is False
        assert "异常增长" in check6["detail"]

    def test_orders_growth_pass_when_normal(self, tmp_path, monkeypatch):
        """订单量正常增长时应通过."""
        from scripts.etl import dq_monitor

        monkeypatch.setattr(dq_monitor, "DUCKDB_PATH", tmp_path / "fake.duckdb")
        (tmp_path / "fake.duckdb").write_bytes(b"x" * 100)

        class _EnoughDisk:
            def __init__(self):
                self.total = 1000 * 1024**3
                self.used = 500 * 1024**3
                self.free = 500 * 1024**3
        monkeypatch.setattr(dq_monitor.shutil, "disk_usage", lambda _: _EnoughDisk())

        # 上次 90 条, 当前 100 条 → 增长 11% < 50%
        snapshot = {"orders_count": 90, "member_ratio": 0.5, "timestamp": "2026-06-01"}
        monkeypatch.setattr(dq_monitor, "load_snapshot", lambda: snapshot)

        result = dq_monitor.run_checks(_StubConn())
        check6 = result["checks"]["orders_growth"]
        assert check6["passed"] is True
        assert "正常" in check6["detail"]
