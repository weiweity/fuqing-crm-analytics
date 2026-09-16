import importlib.util
import inspect
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import duckdb

from backend.services.auth_token_evictor import parse_idle_seconds
from backend.services.category_display import mask_category_name
from backend.services.category_service import distribution as distribution_mod
from backend.services.category_service import overview as overview_mod
from backend.services.dual_conn import quote_duckdb_literal
from backend.services.health.rfm_analysis import prewarm as prewarm_mod
from backend.services.health.rfm_analysis.prewarm import dashboard_windows


def _load_fill_script():
    path = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "fill_2026_q3_overlay.py"
    spec = importlib.util.spec_from_file_location("fill_2026_q3_overlay", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mask_requested_examples():
    assert mask_category_name("凉茶次抛") == "爆款次抛"
    assert mask_category_name("经典膜") == "爆款面膜"
    assert mask_category_name("医用洁面") == "爆款洁面"
    assert mask_category_name("爆款次抛") == "爆款次抛"


def test_mask_passthrough_totals():
    assert mask_category_name("合计") == "合计"
    assert mask_category_name("TTL") == "TTL"
    assert mask_category_name("全部") == "全部"
    assert mask_category_name("全店") == "全店"
    assert mask_category_name("") == ""
    assert mask_category_name(None) == ""


def test_mask_suffix_unknown_and_whitespace():
    assert mask_category_name("  凉茶次抛  ") == "爆款次抛"
    assert mask_category_name("某护理液") == "爆款护理液"
    assert mask_category_name("夜间凝胶") == "爆款凝胶"
    assert mask_category_name("未知小品类") == "爆款品类"
    assert mask_category_name("爆款护理贴") == "爆款护理贴"


def test_dashboard_windows_include_ytd():
    cutoff = date(2026, 7, 5)
    windows = dashboard_windows(cutoff)
    assert (date(2026, 1, 1), date(2026, 7, 5)) in windows
    assert (date(2026, 7, 1), date(2026, 7, 5)) in windows


def test_dashboard_windows_skip_future_and_dedup():
    windows = dashboard_windows(date(2026, 1, 1))
    starts = {start for start, _end in windows}
    assert date(2026, 4, 1) not in starts
    assert date(2026, 7, 1) not in starts
    assert date(2026, 10, 1) not in starts
    assert windows.count((date(2026, 1, 1), date(2026, 1, 1))) == 1
    assert (date(2025, 12, 29), date(2026, 1, 1)) in windows
    assert all(start <= end for start, end in windows)


def test_dashboard_windows_includes_q4():
    windows = dashboard_windows(date(2026, 11, 2))
    assert (date(2026, 10, 1), date(2026, 11, 2)) in windows
    assert (date(2026, 7, 1), date(2026, 9, 30)) in windows
    assert (date(2026, 1, 1), date(2026, 11, 2)) in windows


def test_dashboard_windows_follow_period_builder_cutoff():
    from backend.semantic.time import PeriodBuilder

    cutoff = date(2026, 7, 5)
    today = cutoff + timedelta(days=1)
    windows = dashboard_windows(cutoff)
    ytd = PeriodBuilder.ytd(today=today)["current"]
    mtd = PeriodBuilder.mtd(today=today)["current"]
    assert (date.fromisoformat(ytd.start), date.fromisoformat(ytd.end)) in windows
    assert (date.fromisoformat(mtd.start), date.fromisoformat(mtd.end)) in windows
    assert all(end <= cutoff for _start, end in windows)


def test_quote_duckdb_literal_escapes_quotes():
    fill = _load_fill_script()
    path = "/tmp/o's/archive.duckdb"
    assert quote_duckdb_literal(path) == "/tmp/o''s/archive.duckdb"
    assert fill.quote_duckdb_literal(path) == "/tmp/o''s/archive.duckdb"
    assert fill.quote_ident("orders") == '"orders"'
    assert fill.quote_ident('weird"name') == '"weird""name"'


def test_fill_script_requires_env(monkeypatch):
    fill = _load_fill_script()
    monkeypatch.delenv("FQ_ARCHIVE_DUCKDB", raising=False)
    try:
        fill.required_path("FQ_ARCHIVE_DUCKDB")
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert exc.code == 2


def test_parse_idle_seconds_garbage_and_floor():
    assert parse_idle_seconds(None) == 28800
    assert parse_idle_seconds("") == 28800
    assert parse_idle_seconds("not-an-int") == 28800
    assert parse_idle_seconds("0") == 1
    assert parse_idle_seconds("120") == 120
    assert parse_idle_seconds("-5") == 1
    assert parse_idle_seconds("  90  ") == 90


class _FakeConn:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def execute(self, sql: str, params=None):
        self.calls.append((sql, params))
        return self


def test_ensure_archive_fill_views_noop_and_attach(monkeypatch):
    from backend.services import dual_conn

    monkeypatch.delenv("FQ_ARCHIVE_DUCKDB", raising=False)
    skipped = _FakeConn()
    dual_conn._ensure_archive_fill_views(skipped)
    assert skipped.calls == []

    monkeypatch.setenv("FQ_ARCHIVE_DUCKDB", "/tmp/o'reilly/archive.duckdb")
    attached = _FakeConn()
    dual_conn._ensure_archive_fill_views(attached)
    assert len(attached.calls) == 1
    sql, params = attached.calls[0]
    assert params is None
    assert "ATTACH IF NOT EXISTS" in sql
    assert "READ_ONLY" in sql
    assert "/tmp/o''reilly/archive.duckdb" in sql


def test_apply_runtime_settings_attaches_archive(monkeypatch):
    from backend.services import dual_conn

    monkeypatch.setenv("FQ_ARCHIVE_DUCKDB", "/tmp/a.duckdb")
    conn = _FakeConn()
    dual_conn._apply_runtime_settings(conn, "1GB")
    sqls = [sql for sql, _params in conn.calls]
    assert any("SET memory_limit" in sql for sql in sqls)
    assert any("SET threads" in sql for sql in sqls)
    assert any("ATTACH IF NOT EXISTS" in sql for sql in sqls)


def test_fill_required_path_ok(monkeypatch, tmp_path):
    fill = _load_fill_script()
    target = tmp_path / "x.duckdb"
    monkeypatch.setenv("FQ_ARCHIVE_DUCKDB", str(target))
    assert fill.required_path("FQ_ARCHIVE_DUCKDB") == target


def test_fill_script_missing_archive_file(monkeypatch, tmp_path):
    fill = _load_fill_script()
    monkeypatch.setenv("FQ_ARCHIVE_DUCKDB", str(tmp_path / "missing.duckdb"))
    monkeypatch.setenv("FQ_DUCKDB_WRAPPER", str(tmp_path / "wrapper.duckdb"))
    assert fill.main() == 1


def test_fill_script_builds_tiny_overlay(monkeypatch, tmp_path):
    fill = _load_fill_script()
    archive = tmp_path / "archive.duckdb"
    wrapper = tmp_path / "already.duckdb"
    wrapper.write_text("stale", encoding="utf-8")
    src = duckdb.connect(str(archive))
    src.execute(
        """
        CREATE TABLE orders (
            order_id VARCHAR,
            user_id VARCHAR,
            order_time TIMESTAMP,
            pay_time TIMESTAMP,
            ship_time TIMESTAMP,
            actual_amount DOUBLE,
            is_member BOOLEAN,
            is_goujinjin BOOLEAN,
            order_status VARCHAR,
            is_refund BOOLEAN,
            spu_product_subclass VARCHAR
        )
        """
    )
    src.execute(
        """
        INSERT INTO orders VALUES
        ('o1', 'u1', TIMESTAMP '2023-08-01 10:00:00', TIMESTAMP '2023-08-01 10:00:00',
         TIMESTAMP '2023-08-02 10:00:00', 100, TRUE, FALSE, '交易成功', FALSE, '凉茶次抛'),
        ('o2', 'u2', TIMESTAMP '2023-01-01 10:00:00', TIMESTAMP '2023-01-01 10:00:00',
         TIMESTAMP '2023-01-02 10:00:00', 50, FALSE, FALSE, '交易成功', FALSE, '经典膜')
        """
    )
    src.execute(
        """
        CREATE TABLE daily_visitors (
            date DATE, visitors INTEGER, new_members INTEGER, member_join_rate DOUBLE
        )
        """
    )
    src.execute(
        """
        INSERT INTO daily_visitors VALUES
        (DATE '2023-08-01', 10, 1, 0.1),
        (DATE '2023-01-01', 5, 0, 0.0)
        """
    )
    src.execute("CREATE TABLE extra (id INTEGER)")
    src.execute("INSERT INTO extra VALUES (7)")
    src.close()
    monkeypatch.setenv("FQ_ARCHIVE_DUCKDB", str(archive))
    monkeypatch.setenv("FQ_DUCKDB_WRAPPER", str(wrapper))
    assert fill.main() == 0

    wrap = duckdb.connect(str(wrapper))
    try:
        wrap.execute(
            f"ATTACH IF NOT EXISTS '{fill.quote_duckdb_literal(str(archive))}' AS src (READ_ONLY)"
        )
        assert wrap.execute("SELECT count(*) FROM fill_orders").fetchone()[0] == 1
        order_id, pay_time = wrap.execute(
            "SELECT order_id, pay_time FROM fill_orders"
        ).fetchone()
        assert str(order_id).startswith("SYN26-")
        assert pay_time.year == 2026
        assert wrap.execute("SELECT count(*) FROM fill_daily_visitors").fetchone()[0] == 1
        assert wrap.execute("SELECT count(*) FROM orders").fetchone()[0] == 3
        assert wrap.execute("SELECT id FROM extra").fetchone()[0] == 7
        years = {
            row[0].year
            for row in wrap.execute("SELECT pay_time FROM orders").fetchall()
        }
        assert years == {2023, 2026}
    finally:
        wrap.close()


def test_category_payloads_include_display_name():
    dist_src = inspect.getsource(distribution_mod.get_category_distribution)
    over_src = inspect.getsource(overview_mod.get_category_overview)
    assert '"display_name": mask_category_name(category_name)' in dist_src
    assert '"display_name": mask_category_name(name)' in over_src


def test_prewarm_skips_empty_cutoff(monkeypatch):
    @contextmanager
    def _ctx(*_args, **_kwargs):
        yield SimpleNamespace()

    called = []
    monkeypatch.setattr("backend.services.dual_conn.read_request_context", _ctx)
    monkeypatch.setattr(prewarm_mod, "warehouse_cutoff_date", lambda: None)
    monkeypatch.setattr(
        "backend.services.health.rfm_analysis.get_rfm_analysis",
        lambda **kwargs: called.append(kwargs),
    )
    prewarm_mod.prewarm_common_windows()
    assert called == []


def test_prewarm_continues_after_window_failure(monkeypatch):
    @contextmanager
    def _ctx(*_args, **_kwargs):
        yield SimpleNamespace()

    calls: list[tuple[str, str]] = []

    def _rfm(**kwargs):
        pair = (kwargs["start_date"], kwargs["end_date"])
        calls.append(pair)
        if kwargs["start_date"] == "2026-07-01":
            raise RuntimeError("cache miss")
        return {"ok": True}

    monkeypatch.setattr("backend.services.dual_conn.read_request_context", _ctx)
    monkeypatch.setattr(prewarm_mod, "warehouse_cutoff_date", lambda: date(2026, 7, 5))
    monkeypatch.setattr(
        prewarm_mod,
        "dashboard_windows",
        lambda _cutoff: [
            (date(2026, 7, 1), date(2026, 7, 5)),
            (date(2026, 1, 1), date(2026, 7, 5)),
        ],
    )
    monkeypatch.setattr("backend.services.health.rfm_analysis.get_rfm_analysis", _rfm)
    prewarm_mod.prewarm_common_windows()
    assert calls == [("2026-07-01", "2026-07-05"), ("2026-01-01", "2026-07-05")]


def test_maybe_start_prewarm_respects_env(monkeypatch):
    started: list[str] = []

    class _FakeThread:
        def __init__(self, target=None, name=None, daemon=None):
            started.append(name or "")

        def start(self):
            started.append("start")

    monkeypatch.setattr(prewarm_mod.threading, "Thread", _FakeThread)
    monkeypatch.setenv("FQ_DB_MODE", "schema_test")
    monkeypatch.setenv("FQ_RFM_PREWARM", "1")
    prewarm_mod.maybe_start_prewarm_thread()
    assert started == []

    monkeypatch.setenv("FQ_DB_MODE", "production")
    monkeypatch.setenv("FQ_RFM_PREWARM", "0")
    prewarm_mod.maybe_start_prewarm_thread()
    assert started == []

    monkeypatch.setenv("FQ_RFM_PREWARM", "1")
    prewarm_mod.maybe_start_prewarm_thread()
    assert started == ["rfm-prewarm", "start"]
