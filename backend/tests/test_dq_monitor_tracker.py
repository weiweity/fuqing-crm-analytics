"""Sprint 31.1 — dq_monitor tracker integration 测试

Phase 2 行为:
  - tmp_db 切到 fuqing_dq_monitor_<pid>_<ts>.duckdb 命名 (从 mkstemp 改)
  - tracker.register 在 shutil.copy2 之后
  - tracker.remove 在 finally 块 (无论 os.unlink 成功与否)
  - 软失败: tracker 任何错误不阻塞 dq

注: dq_monitor.main() 走 argparse 默认读 sys.argv, 测试需要 monkeypatch
sys.argv 避免 pytest 的 -v 等参数撞到 dq 的 parser.

注 2: dq_monitor 的 tmp_db 路径 hardcoded /tmp/fuqing_dq_monitor_* (生产 /tmp).
测试不验证 tracker DB state (per-test 隔离 DB 跟 production /tmp 不交叉),
只验证核心行为: 路径是 fuqing_* 命名 + 不 crash + finally 块执行.
"""
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
        pass


class TestDqMonitorTracker:
    """dq_monitor 切到 fuqing_* 命名 + tracker 集成."""

    def test_dq_monitor_uses_fuqing_named_path(self, tmp_path, monkeypatch):
        """Sprint 31.1: tmp_db 路径应是 fuqing_dq_monitor_<pid>_<ts>.duckdb 形式."""
        from scripts.etl import dq_monitor

        monkeypatch.setattr(dq_monitor, "DUCKDB_PATH", tmp_path / "fake_prod.duckdb")
        (tmp_path / "fake_prod.duckdb").write_bytes(b"x" * 100)
        # dq_monitor.main() 走 argparse 默认读 sys.argv, pytest -v 会撞到 --alert/--report 之外的 args
        monkeypatch.setattr(sys, "argv", ["dq_monitor"])

        captured_paths = []

        real_copy2 = dq_monitor.shutil.copy2
        real_unlink = dq_monitor.os.unlink

        def fake_copy2(src, dst):
            captured_paths.append(("copy2_dst", dst))
            return real_copy2(src, dst)

        def fake_unlink(path):
            captured_paths.append(("unlink_src", path))
            return real_unlink(path)

        monkeypatch.setattr(dq_monitor.shutil, "copy2", fake_copy2)
        monkeypatch.setattr(dq_monitor.os, "unlink", fake_unlink)
        import duckdb
        monkeypatch.setattr(duckdb, "connect", lambda *a, **kw: _StubConn())

        dq_monitor.main()

        copy2_calls = [p for action, p in captured_paths if action == "copy2_dst"]
        assert len(copy2_calls) == 1
        assert "/fuqing_dq_monitor_" in copy2_calls[0], (
            f"tmp_db 路径应是 fuqing_dq_monitor_*, 实际 {copy2_calls[0]}"
        )
        assert copy2_calls[0].endswith(".duckdb")

    def test_dq_monitor_does_not_crash_on_tracker_error(self, tmp_path, monkeypatch):
        """tracker 不可用 → dq_monitor 仍能正常跑 (软失败不阻塞)."""
        from scripts.etl import dq_monitor
        from scripts.etl.common import tmp_tracker as tmp_tracker_mod

        monkeypatch.setattr(dq_monitor, "DUCKDB_PATH", tmp_path / "fake_prod.duckdb")
        (tmp_path / "fake_prod.duckdb").write_bytes(b"x" * 100)
        monkeypatch.setattr(sys, "argv", ["dq_monitor"])

        # 强制 TrackerDB 不可用
        class _BadTracker:
            def __init__(self, *a, **kw):
                pass
            def is_available(self):
                return False
            def register(self, *a, **kw):
                pass
            def remove(self, *a, **kw):
                pass

        monkeypatch.setattr(tmp_tracker_mod, "TrackerDB", _BadTracker)
        import duckdb
        monkeypatch.setattr(duckdb, "connect", lambda *a, **kw: _StubConn())

        # 必须不 raise
        dq_monitor.main()

    def test_dq_monitor_finally_runs_on_crash(self, tmp_path, monkeypatch):
        """duckdb.connect 失败 → main() raise, 但 finally 块仍应执行 (os.unlink)."""
        from scripts.etl import dq_monitor

        monkeypatch.setattr(dq_monitor, "DUCKDB_PATH", tmp_path / "fake_prod.duckdb")
        (tmp_path / "fake_prod.duckdb").write_bytes(b"x" * 100)
        monkeypatch.setattr(sys, "argv", ["dq_monitor"])

        unlink_called = []

        real_unlink = dq_monitor.os.unlink
        def fake_unlink(path):
            unlink_called.append(path)
            return real_unlink(path)

        monkeypatch.setattr(dq_monitor.os, "unlink", fake_unlink)
        import duckdb
        def failing_connect(*a, **kw):
            raise RuntimeError("simulated crash after copy2")
        monkeypatch.setattr(duckdb, "connect", failing_connect)

        with pytest.raises(RuntimeError, match="simulated crash"):
            dq_monitor.main()

        # finally 块应触发, os.unlink(tmp_db) 被调
        assert any("/fuqing_dq_monitor_" in p for p in unlink_called), (
            f"finally 块应调 unlink(fuqing_dq_monitor_*), 实际 unlinks={unlink_called}"
        )


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
