import importlib.util
import inspect
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

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


def test_unique_display_names_suffixes_collisions():
    from backend.services.category_display import unique_display_names

    mapping = unique_display_names(["经典膜", "水杨酸面膜", "凉茶次抛"])
    assert mapping["凉茶次抛"] == "爆款次抛"
    assert mapping["水杨酸面膜"] != mapping["经典膜"]
    assert mapping["水杨酸面膜"].startswith("爆款面膜")
    assert mapping["经典膜"].startswith("爆款面膜")
    assert mapping["水杨酸面膜"][-1] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    assert mapping["经典膜"][-1] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    assert mapping["水杨酸面膜"] != mapping["经典膜"]


def test_catalog_display_map_stable_for_subset_lookup():
    from backend.services.category_display import catalog_display_map, lookup_display_name

    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE orders (spu_product_class VARCHAR)")
    con.execute(
        "INSERT INTO orders VALUES ('经典膜'), ('水杨酸面膜'), ('积雪草冻干面膜')"
    )
    mapping = catalog_display_map(con, "spu_product_class")
    classic = lookup_display_name(mapping, "经典膜")
    acid = lookup_display_name(mapping, "水杨酸面膜")
    freeze = lookup_display_name(mapping, "积雪草冻干面膜")
    assert len({classic, acid, freeze}) == 3
    assert classic.startswith("爆款面膜")
    assert lookup_display_name(mapping, "经典膜") == classic
    from backend.services.category_display import unique_display_names

    assert unique_display_names(["水杨酸面膜"])["水杨酸面膜"] == "爆款面膜"
    assert acid.startswith("爆款面膜") and acid != "爆款面膜"
    con.close()


def test_catalog_display_map_rejects_non_whitelist_column():
    from backend.services.category_display import catalog_display_map

    class Boom:
        def execute(self, *a, **k):
            raise AssertionError("must not interpolate")

    with pytest.raises(ValueError, match="unsupported category column"):
        catalog_display_map(Boom(), "spu_product_class; DROP TABLE orders")


def test_catalog_cache_uses_inner_connection_id():
    from backend.db.connection import ThreadSafeConnection
    from backend.services import category_display as cd

    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE orders (spu_product_class VARCHAR)")
    con.execute("INSERT INTO orders VALUES ('凉茶次抛')")
    wrap_a = ThreadSafeConnection(con)
    wrap_b = ThreadSafeConnection(con)
    first = cd.catalog_display_map(wrap_a, "spu_product_class")
    second = cd.catalog_display_map(wrap_b, "spu_product_class")
    assert first is second
    con.close()


def test_apply_catalog_display_names_stamps_without_rewriting_query_key():
    from backend.services.category_display import apply_catalog_display_names

    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE orders (spu_product_class VARCHAR)")
    con.execute("INSERT INTO orders VALUES ('经典膜'), ('水杨酸面膜')")
    rows = [
        {"name": "经典膜", "query_key": "经典膜"},
        {"name": "水杨酸面膜", "query_key": "水杨酸面膜"},
    ]
    apply_catalog_display_names(con, rows, "spu_product_class")
    assert rows[0]["query_key"] == "经典膜"
    assert rows[1]["query_key"] == "水杨酸面膜"
    assert rows[0]["display_name"] != rows[1]["display_name"]
    assert str(rows[0]["display_name"]).startswith("爆款面膜")
    con.close()


def test_wool_party_breakdown_ratio_bounds():
    from pydantic import ValidationError
    from backend.contracts.common import WoolPartyBreakdown

    base = dict(
        high_risk_count=1,
        mean_score=0.8,
        never_converted_count=1,
        converted_then_sample_count=0,
        sample_only_window_count=1,
        scored_users=1,
        high_risk_ratio=1.0,
    )
    WoolPartyBreakdown(**base)
    with pytest.raises(ValidationError):
        WoolPartyBreakdown(**{**base, "high_risk_ratio": 1.5})
    with pytest.raises(ValidationError):
        WoolPartyBreakdown(**{**base, "mean_score": 1.2})


def test_unique_display_names_passthrough_and_dedup():
    from backend.services.category_display import unique_display_names

    mapping = unique_display_names(["TTL", "TTL", "合计", None, ""])
    assert mapping["TTL"] == "TTL"
    assert mapping["合计"] == "合计"


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
        CREATE TABLE user_first_purchase (
            user_id VARCHAR,
            first_pay_date DATE
        )
        """
    )
    src.execute(
        """
        INSERT INTO user_first_purchase VALUES
        ('u1', DATE '2023-08-01'),
        ('u2', DATE '2021-01-01')
        """
    )
    src.execute(
        """
        CREATE TABLE user_rfm (
            user_id VARCHAR,
            user_nickname VARCHAR,
            analysis_date DATE,
            metric_type VARCHAR,
            lookback_days INTEGER,
            channel VARCHAR,
            recency_days INTEGER,
            frequency INTEGER,
            monetary DECIMAL(12,2),
            r_score INTEGER,
            f_score INTEGER,
            m_score INTEGER,
            rfm_tier VARCHAR,
            rfm_tier_en VARCHAR,
            segment_id INTEGER,
            first_order_date DATE,
            last_order_date DATE,
            created_at TIMESTAMP,
            is_member BOOLEAN
        )
        """
    )
    src.execute(
        """
        INSERT INTO user_rfm VALUES
        ('u1', 'n', DATE '2023-07-01', 'GMV', 90, '全店', 10, 2, 100,
         4, 3, 3, '重要价值客户', 'champions', 2,
         DATE '2023-07-01', DATE '2023-07-01', TIMESTAMP '2023-07-01', TRUE),
        ('u1', 'n', DATE '2023-08-01', 'GMV', 90, '全店', 10, 2, 100,
         4, 3, 3, '重要价值客户', 'champions', 1,
         DATE '2023-07-01', DATE '2023-08-01', TIMESTAMP '2023-08-01', TRUE),
        ('u1', 'n', DATE '2023-09-20', 'GMV', 90, '全店', 10, 2, 100,
         4, 3, 3, '重要价值客户', 'champions', 4,
         DATE '2023-07-01', DATE '2023-09-20', TIMESTAMP '2023-09-20', TRUE)
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
        (DATE '2025-08-01', 10, 1, 0.1),
        (DATE '2023-08-01', 5, 0, 0.0)
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
        user_id = wrap.execute("SELECT user_id FROM fill_orders").fetchone()[0]
        assert str(user_id).startswith("SYN26-U-")
        assert pay_time.year == 2026
        first_pay = wrap.execute(
            "SELECT first_pay_date FROM fill_user_first_purchase WHERE user_id = ?",
            [user_id],
        ).fetchone()[0]
        assert first_pay.year == 2026
        vis_date = wrap.execute("SELECT date FROM fill_daily_visitors").fetchone()[0]
        assert vis_date.year == 2026
        rfm_rows = wrap.execute(
            "SELECT user_id, analysis_date, segment_id FROM fill_user_rfm"
        ).fetchall()
        assert len(rfm_rows) == 1
        rfm_user, rfm_date, seg = rfm_rows[0]
        assert str(rfm_user).startswith("SYN26-U-")
        assert rfm_date.year == 2026 and rfm_date.month == 8
        assert int(seg) == 1
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


def test_fill_script_computes_gmv90_when_copied_user_rfm_empty(monkeypatch, tmp_path):
    fill = _load_fill_script()
    archive = tmp_path / "archive.duckdb"
    wrapper = tmp_path / "wrapper.duckdb"
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
         TIMESTAMP '2023-08-02 10:00:00', 100, TRUE, FALSE, '交易成功', FALSE, '凉茶次抛')
        """
    )
    src.execute(
        """
        CREATE TABLE user_rfm (
            user_id VARCHAR,
            user_nickname VARCHAR,
            analysis_date DATE,
            metric_type VARCHAR,
            lookback_days INTEGER,
            channel VARCHAR,
            recency_days INTEGER,
            frequency INTEGER,
            monetary DECIMAL(12,2),
            r_score INTEGER,
            f_score INTEGER,
            m_score INTEGER,
            rfm_tier VARCHAR,
            rfm_tier_en VARCHAR,
            segment_id INTEGER,
            first_order_date DATE,
            last_order_date DATE,
            created_at TIMESTAMP,
            is_member BOOLEAN
        )
        """
    )
    src.execute(
        """
        INSERT INTO user_rfm VALUES
        ('u1', 'n', DATE '2026-06-02', 'GMV', 90, '全店', 10, 2, 100,
         4, 3, 3, '重要价值客户', 'champions', 1,
         DATE '2026-06-01', DATE '2026-06-02', TIMESTAMP '2026-06-02', TRUE)
        """
    )
    src.close()
    monkeypatch.setenv("FQ_ARCHIVE_DUCKDB", str(archive))
    monkeypatch.setenv("FQ_DUCKDB_WRAPPER", str(wrapper))
    assert fill.main() == 0

    wrap = duckdb.connect(str(wrapper))
    try:
        wrap.execute(
            f"ATTACH IF NOT EXISTS '{fill.quote_duckdb_literal(str(archive))}' AS src (READ_ONLY)"
        )
        rows = wrap.execute(
            """
            SELECT user_id, analysis_date, metric_type, lookback_days,
                   recency_days, frequency, monetary, r_score, f_score, m_score,
                   segment_id, rfm_tier
            FROM fill_user_rfm
            """
        ).fetchall()
        assert len(rows) == 1
        user_id, analysis_date, metric, lookback, recency, freq, monetary, r, f, m, seg, tier = rows[0]
        assert str(user_id) == "SYN26-U-u1"
        as_of = analysis_date.date() if hasattr(analysis_date, "date") else analysis_date
        assert as_of == date(2026, 9, 15)
        assert metric == "GMV" and int(lookback) == 90
        assert int(recency) == 45
        assert int(freq) == 1
        assert float(monetary) == 100
        assert (int(r), int(f), int(m)) == (4, 1, 2)
        assert int(seg) == 7
        assert tier == "一般发展客户"
        # Must not copy the 2026 archive snapshot onto SYN26 users.
        copied = wrap.execute(
            "SELECT count(*) FROM fill_user_rfm WHERE analysis_date = DATE '2029-06-02'"
        ).fetchone()[0]
        assert copied == 0
    finally:
        wrap.close()


def test_fill_script_overlays_health_precompute_from_source_asof(monkeypatch, tmp_path):
    fill = _load_fill_script()
    archive = tmp_path / "archive.duckdb"
    wrapper = tmp_path / "wrapper.duckdb"
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
         TIMESTAMP '2023-08-02 10:00:00', 100, TRUE, FALSE, '交易成功', FALSE, '凉茶次抛')
        """
    )
    src.execute(
        """
        CREATE TABLE user_rfm (
            user_id VARCHAR, user_nickname VARCHAR, analysis_date DATE,
            metric_type VARCHAR, lookback_days INTEGER, channel VARCHAR,
            recency_days INTEGER, frequency INTEGER, monetary DECIMAL(12,2),
            r_score INTEGER, f_score INTEGER, m_score INTEGER,
            rfm_tier VARCHAR, rfm_tier_en VARCHAR, segment_id INTEGER,
            first_order_date DATE, last_order_date DATE, created_at TIMESTAMP,
            is_member BOOLEAN
        )
        """
    )
    src.execute(
        """
        CREATE TABLE user_rfm_precompute (
            as_of_date DATE,
            lookback_days INTEGER,
            user_id VARCHAR,
            last_pay_time TIMESTAMP,
            order_count BIGINT,
            gsv DOUBLE,
            is_member BOOLEAN,
            r_score INTEGER,
            f_score INTEGER,
            m_score INTEGER,
            r_interval VARCHAR,
            rfm_segment VARCHAR,
            updated_at TIMESTAMP
        )
        """
    )
    src.execute(
        """
        INSERT INTO user_rfm_precompute VALUES
        (DATE '2023-07-09', 3650, 'u1', TIMESTAMP '2023-06-01 10:00:00',
         8, 1200, TRUE, 2, 5, 5, '近4-6月已购客', '重要保持客户', TIMESTAMP '2023-07-09'),
        (DATE '2026-07-01', 3650, 'u1', TIMESTAMP '2026-06-01 10:00:00',
         99, 9999, TRUE, 5, 5, 5, '近1个月已购客', '重要价值客户', TIMESTAMP '2026-07-01')
        """
    )
    src.close()
    monkeypatch.setenv("FQ_ARCHIVE_DUCKDB", str(archive))
    monkeypatch.setenv("FQ_DUCKDB_WRAPPER", str(wrapper))
    assert fill.main() == 0

    wrap = duckdb.connect(str(wrapper))
    try:
        wrap.execute(
            f"ATTACH IF NOT EXISTS '{fill.quote_duckdb_literal(str(archive))}' AS src (READ_ONLY)"
        )
        rows = wrap.execute(
            """
            SELECT as_of_date, user_id, lookback_days, rfm_segment, r_score, order_count
            FROM fill_user_rfm_precompute
            ORDER BY as_of_date
            """
        ).fetchall()
        assert len(rows) == 2
        dates = []
        for as_of, user_id, lookback, segment, r_score, order_count in rows:
            as_of_d = as_of.date() if hasattr(as_of, "date") else as_of
            dates.append(as_of_d)
            assert str(user_id) == "SYN26-U-u1"
            assert int(lookback) == 3650
            assert segment == "重要保持客户"
            assert int(r_score) == 2
            assert int(order_count) == 8
        assert dates == [date(2026, 7, 1), date(2026, 7, 6)]
        # Must not copy the 2026 precompute snapshot onto SYN26 users.
        copied = wrap.execute(
            """
            SELECT count(*) FROM fill_user_rfm_precompute
            WHERE rfm_segment = '重要价值客户' OR order_count = 99
            """
        ).fetchone()[0]
        assert copied == 0
        union_n = wrap.execute(
            """
            SELECT count(*) FROM user_rfm_precompute
            WHERE user_id = 'SYN26-U-u1' AND as_of_date = DATE '2026-07-01'
            """
        ).fetchone()[0]
        assert union_n == 1
    finally:
        wrap.close()


def test_category_payloads_include_display_name():
    dist_src = inspect.getsource(distribution_mod.get_category_distribution)
    over_src = inspect.getsource(overview_mod.get_category_overview)
    assert "apply_catalog_display_names(conn, distribution" in dist_src
    assert "apply_catalog_display_names(conn, all_rows" in over_src


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
