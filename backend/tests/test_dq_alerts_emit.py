"""DQ 告警必须真正发出。不打开 131GB 生产库，不用飞书。"""
from datetime import date
import sys

import duckdb

from scripts.etl import assertions, dq_monitor


def test_assertions_alert_function_records_and_returns_sent():
    assertions.clear_emitted_alerts()
    sent, reason = assertions._send_lark_alert_mockable("ETL DQ 断言失败 (1 条)")
    assert sent is True
    assert reason == "local-alert"
    assert assertions.emitted_alerts() == ["ETL DQ 断言失败 (1 条)"]


def test_run_assertions_emits_without_patching_the_sender(monkeypatch):
    assertions.clear_emitted_alerts()
    conn = duckdb.connect(":memory:")
    assertions.create_quarantine_table(conn)
    monkeypatch.setattr(assertions, "assert_total_not_drop", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(assertions, "assert_repurchase_nonzero", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(assertions, "assert_idempotency", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(assertions, "assert_540_completeness", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(assertions, "assert_dimension_drift", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(assertions, "assert_history_no_loss", lambda *_args, **_kwargs: True)
    result = assertions.run_assertions(conn, date(2026, 6, 5), send_alert=True)
    conn.close()
    assert result["failed"] == 1
    assert result["alert_sent"] is True
    assert len(assertions.emitted_alerts()) == 1
    assert "ETL DQ 断言失败" in assertions.emitted_alerts()[0]


def test_run_assertions_send_alert_false_does_not_emit(monkeypatch):
    assertions.clear_emitted_alerts()
    conn = duckdb.connect(":memory:")
    assertions.create_quarantine_table(conn)
    monkeypatch.setattr(assertions, "assert_total_not_drop", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(assertions, "assert_repurchase_nonzero", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(assertions, "assert_idempotency", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(assertions, "assert_540_completeness", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(assertions, "assert_dimension_drift", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(assertions, "assert_history_no_loss", lambda *_args, **_kwargs: True)
    result = assertions.run_assertions(conn, date(2026, 6, 5), send_alert=False)
    conn.close()
    assert result["alert_sent"] is False
    assert assertions.emitted_alerts() == []


def test_dq_monitor_alert_function_records_and_returns_sent():
    dq_monitor.clear_emitted_alerts()
    sent, reason = dq_monitor.send_lark_alert("DQ Monitor 告警\n失败项: gsv_nonzero")
    assert sent is True
    assert reason == "local-alert"
    assert "gsv_nonzero" in dq_monitor.emitted_alerts()[0]


def test_dq_monitor_alert_flag_emits_without_stubbing_sender(tmp_path, monkeypatch):
    dq_monitor.clear_emitted_alerts()
    prod_db = tmp_path / "fake_prod.duckdb"
    prod_db.write_bytes(b"production-sentinel")
    report_dir = tmp_path / "processed"
    monkeypatch.setattr(dq_monitor, "DUCKDB_PATH", prod_db)
    monkeypatch.setattr(dq_monitor, "PROCESSED_DATA_DIR", report_dir)
    monkeypatch.setattr(dq_monitor, "SNAPSHOT_PATH", report_dir / "dq_snapshot.json")
    monkeypatch.setattr(sys, "argv", ["dq_monitor", "--report", "--alert"])
    monkeypatch.setattr(dq_monitor, "run_checks", lambda _conn: {
        "timestamp": "2026-07-26T12:00:00+08:00",
        "checks": {
            "orders_count": {"current": 100, "passed": True, "detail": "正常"},
            "member_ratio": {"current": 0.5, "passed": True, "detail": "正常"},
            "gsv_nonzero": {"current": 0, "passed": False, "detail": "今日 GSV 为 0"},
        },
        "all_passed": False,
    })

    class _Conn:
        def close(self):
            self.closed = True

        closed = False

    import duckdb
    monkeypatch.setattr(duckdb, "connect", lambda *args, **kwargs: _Conn())
    assert dq_monitor.main() == 2
    assert len(dq_monitor.emitted_alerts()) == 1
    assert "gsv_nonzero" in dq_monitor.emitted_alerts()[0]
    assert "今日 GSV 为 0" in dq_monitor.emitted_alerts()[0]
