"""Sprint 205 RFM 30s timeout → 502 cache-chain regression tests."""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from backend.semantic.time import PeriodBuilder
from backend.services.health.rfm_analysis import cache
from backend.services.health.rfm_analysis._shared import _cache_key
from backend.services.rfm._shared import _resolve_date_ranges


DATA_VERSION = "2026-07-05 23:59:58"
ORDERS_COUNT = 10_829_767
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def cache_conn(monkeypatch: pytest.MonkeyPatch):
    conn = duckdb.connect(":memory:")
    cache._ensure_db_cache_table(conn)
    monkeypatch.setattr(cache, "_get_cache_conn", lambda: conn)
    try:
        yield conn
    finally:
        conn.close()


def _insert_cache_row(
    conn,
    *,
    start_date: str = "2025-07-13",
    end_date: str = "2026-07-12",
    period: str = "LAST365DAYS",
    result: dict | str = None,
    channel: str | None = None,
    metric_type: str = "GSV",
    exclude_channels: list[str] | None = None,
    compare_start_date: str | None = None,
    compare_end_date: str | None = None,
    key_data_version: str = DATA_VERSION,
    cached_mtime: str = DATA_VERSION,
    cached_orders_count: int = ORDERS_COUNT,
    computed_at: datetime | None = None,
    generation_id: str | None = None,
) -> str:
    key = _cache_key(
        None,
        start_date,
        end_date,
        channel,
        metric_type,
        exclude_channels,
        key_data_version,
        compare_start_date,
        compare_end_date,
    )
    payload = result if isinstance(result, str) else json.dumps(result or {"marker": "cached"})
    params = [
        key,
        period,
        start_date,
        end_date,
        channel or "",
        metric_type,
        json.dumps(exclude_channels, ensure_ascii=False) if exclude_channels else "",
        payload,
        cached_mtime,
        cached_orders_count,
    ]
    if generation_id:
        conn.execute(
            f"""
            INSERT INTO {cache.RFM_CACHE_GENERATION_ROWS_TABLE}
            (cache_key, period, start_date, end_date, channel, metric_type, ex_channels,
             result_json, mtime_at_write, orders_count_at_write, generation_id, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [*params, generation_id, computed_at or datetime.now()],
        )
    else:
        conn.execute(
            f"""
            INSERT INTO {cache.RFM_CACHE_TABLE}
            (cache_key, period, start_date, end_date, channel, metric_type, ex_channels,
             result_json, mtime_at_write, orders_count_at_write, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [*params, computed_at or datetime.now()],
        )
    return key


def _read_shifted_cache(
    conn,
    *,
    exclude_channels: list[str] | None = None,
    compare_start_date: str | None = None,
    compare_end_date: str | None = None,
    current_mtime: str = DATA_VERSION,
    current_orders_count: int = ORDERS_COUNT,
):
    return cache._read_db_cache(
        None,
        "2025-07-14",
        "2026-07-13",
        None,
        "GSV",
        exclude_channels,
        current_mtime,
        conn,
        compare_start_date,
        compare_end_date,
        current_orders_count=current_orders_count,
    )


class TestRFMFuzzyCacheSafety:
    @pytest.mark.parametrize(
        ("drift_days", "expected_hit"),
        [(0, True), (1, True), (2, True), (3, False)],
    )
    def test_active_generation_fuzzy_boundary_0_to_3_days(
        self,
        cache_conn,
        drift_days,
        expected_hit,
    ):
        target_start = date(2025, 7, 14)
        target_end = date(2026, 7, 13)
        generation_id = f"drift-{drift_days}"
        _insert_cache_row(
            cache_conn,
            start_date=(target_start - timedelta(days=drift_days)).isoformat(),
            end_date=(target_end - timedelta(days=drift_days)).isoformat(),
            generation_id=generation_id,
            result={"marker": f"drift-{drift_days}"},
        )
        cache._activate_cache_generation(
            cache_conn,
            generation_id,
            DATA_VERSION,
            ORDERS_COUNT,
        )

        result = _read_shifted_cache(cache_conn)
        if expected_hit:
            assert result == {"marker": f"drift-{drift_days}"}
        else:
            assert result is None

    def test_active_hot_period_remains_available_beyond_fuzzy_window(self, cache_conn):
        generation_id = "ten-days-old"
        target = PeriodBuilder.last365days(today=date.today())["current"]
        cached_start = date.fromisoformat(target.start) - timedelta(days=10)
        cached_end = date.fromisoformat(target.end) - timedelta(days=10)
        _insert_cache_row(
            cache_conn,
            start_date=cached_start.isoformat(),
            end_date=cached_end.isoformat(),
            period="LAST365DAYS",
            generation_id=generation_id,
            result={"marker": "period-last-known-good"},
        )
        cache._activate_cache_generation(
            cache_conn,
            generation_id,
            DATA_VERSION,
            ORDERS_COUNT,
        )

        result = cache._read_db_cache(
            None,
            target.start,
            target.end,
            None,
            "GSV",
            None,
            DATA_VERSION,
            cache_conn,
            current_orders_count=ORDERS_COUNT,
        )

        assert result == {"marker": "period-last-known-good"}

    def test_http_period_none_hits_precomputed_period_row(self, cache_conn):
        _insert_cache_row(cache_conn, result={"marker": "precomputed"})

        assert _read_shifted_cache(cache_conn) == {"marker": "precomputed"}

    def test_service_http_shape_returns_cache_without_live_rfm(self, cache_conn, monkeypatch):
        from backend.services.health.rfm_analysis import analysis

        biz_conn = duckdb.connect(":memory:")
        biz_conn.execute("CREATE TABLE orders(pay_time TIMESTAMP)")
        biz_conn.execute("INSERT INTO orders VALUES (?::TIMESTAMP)", [DATA_VERSION])
        _insert_cache_row(
            cache_conn,
            result={"marker": "service-cache-hit"},
            cached_orders_count=1,
        )
        monkeypatch.setattr(analysis.bdc, "get_connection", lambda: biz_conn)

        def fail_live_query(*_args, **_kwargs):
            raise AssertionError("cache hit must not execute live RFM")

        monkeypatch.setattr(analysis, "_run_rfm_period_serial", fail_live_query)
        try:
            result = analysis.get_rfm_analysis(
                start_date="2025-07-14",
                end_date="2026-07-13",
                metric_type="GSV",
                allow_live_compute=False,
            )
        finally:
            biz_conn.close()

        assert result == {"marker": "service-cache-hit"}

    def test_cache_only_future_quarter_reads_precomputed_key(self, cache_conn, monkeypatch):
        from backend.services.health.rfm_analysis import analysis

        biz_conn = duckdb.connect(":memory:")
        biz_conn.execute("CREATE TABLE orders(pay_time TIMESTAMP)")
        biz_conn.execute("INSERT INTO orders VALUES (?::TIMESTAMP)", [DATA_VERSION])
        _insert_cache_row(
            cache_conn,
            start_date="2026-10-01",
            end_date="2026-12-31",
            period="Q4",
            result={"marker": "future-q4"},
            cached_orders_count=1,
        )
        monkeypatch.setattr(analysis.bdc, "get_connection", lambda: biz_conn)
        monkeypatch.setattr(
            analysis,
            "_run_rfm_period_serial",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("cache-only Q4 must not run live SQL")
            ),
        )
        try:
            result = analysis.get_rfm_analysis(
                start_date="2026-10-01",
                end_date="2026-12-31",
                metric_type="GSV",
                allow_live_compute=False,
            )
        finally:
            biz_conn.close()

        assert result == {"marker": "future-q4"}

    def test_default_request_does_not_take_newer_custom_compare_row(self, cache_conn):
        _insert_cache_row(
            cache_conn,
            result={"marker": "default"},
            computed_at=datetime.now() - timedelta(minutes=1),
        )
        _insert_cache_row(
            cache_conn,
            result={"marker": "Q-3"},
            compare_start_date="2024-10-14",
            compare_end_date="2025-07-13",
            computed_at=datetime.now(),
        )

        assert _read_shifted_cache(cache_conn) == {"marker": "default"}
        assert _read_shifted_cache(
            cache_conn,
            compare_start_date="2024-10-14",
            compare_end_date="2025-07-13",
        ) == {"marker": "Q-3"}

    def test_excluded_channels_do_not_cross_contaminate(self, cache_conn):
        excluded = ["淘客", "直播"]
        _insert_cache_row(cache_conn, result={"marker": "all"})
        _insert_cache_row(
            cache_conn,
            result={"marker": "filtered"},
            exclude_channels=excluded,
            computed_at=datetime.now() + timedelta(seconds=1),
        )

        assert _read_shifted_cache(cache_conn) == {"marker": "all"}
        assert _read_shifted_cache(cache_conn, exclude_channels=excluded) == {"marker": "filtered"}

    @pytest.mark.parametrize(
        ("cached_mtime", "cached_orders", "computed_at", "current_mtime", "current_orders"),
        [
            (DATA_VERSION, ORDERS_COUNT, datetime.now() - timedelta(hours=48), DATA_VERSION, ORDERS_COUNT),
            (DATA_VERSION, ORDERS_COUNT - 1, datetime.now(), DATA_VERSION, ORDERS_COUNT),
            ("2026-07-04 23:59:58", ORDERS_COUNT, datetime.now(), DATA_VERSION, ORDERS_COUNT),
        ],
        ids=["ttl", "orders-count", "mtime"],
    )
    def test_fuzzy_hit_uses_same_freshness_gate_as_exact_hit(
        self,
        cache_conn,
        cached_mtime,
        cached_orders,
        computed_at,
        current_mtime,
        current_orders,
    ):
        key = _insert_cache_row(
            cache_conn,
            cached_mtime=cached_mtime,
            cached_orders_count=cached_orders,
            computed_at=computed_at,
        )

        assert _read_shifted_cache(
            cache_conn,
            current_mtime=current_mtime,
            current_orders_count=current_orders,
        ) is None
        assert cache_conn.execute(
            f"SELECT COUNT(*) FROM {cache.RFM_CACHE_TABLE} WHERE cache_key = ?", [key]
        ).fetchone()[0] == 0

    def test_corrupt_fuzzy_row_deletes_actual_candidate_key(self, cache_conn):
        key = _insert_cache_row(cache_conn, result="not-json")

        assert _read_shifted_cache(cache_conn) is None
        assert cache_conn.execute(
            f"SELECT COUNT(*) FROM {cache.RFM_CACHE_TABLE} WHERE cache_key = ?", [key]
        ).fetchone()[0] == 0

    def test_fuzzy_rejects_opposite_endpoint_drift(self, cache_conn):
        _insert_cache_row(
            cache_conn,
            start_date="2025-07-13",
            end_date="2026-07-14",
            result={"marker": "wider-window"},
        )

        assert _read_shifted_cache(cache_conn) is None

    def test_fuzzy_auto_mom_shifts_compare_window_with_candidate(self, cache_conn):
        target_mom = PeriodBuilder.mom("2025-07-14", "2026-07-13")
        candidate_mom = PeriodBuilder.mom("2025-07-13", "2026-07-12")
        _insert_cache_row(
            cache_conn,
            result={"marker": "auto-mom"},
            compare_start_date=candidate_mom.start,
            compare_end_date=candidate_mom.end,
        )

        assert _read_shifted_cache(
            cache_conn,
            compare_start_date=target_mom.start,
            compare_end_date=target_mom.end,
        ) == {"marker": "auto-mom"}

    def test_compare_and_delete_does_not_remove_concurrently_refreshed_row(self, cache_conn):
        old_computed_at = datetime.now() - timedelta(hours=48)
        key = _insert_cache_row(cache_conn, computed_at=old_computed_at)
        cache_conn.execute(
            f"UPDATE {cache.RFM_CACHE_TABLE} SET result_json = ?, computed_at = ? "
            "WHERE cache_key = ?",
            [json.dumps({"marker": "fresh"}), datetime.now(), key],
        )

        cache._try_delete_corrupt_row(
            key,
            DATA_VERSION,
            ORDERS_COUNT,
            old_computed_at,
        )

        row = cache_conn.execute(
            f"SELECT result_json FROM {cache.RFM_CACHE_TABLE} WHERE cache_key = ?", [key]
        ).fetchone()
        assert json.loads(row[0]) == {"marker": "fresh"}

    def test_cache_read_failure_raises_instead_of_running_live_query(self, monkeypatch):
        class BrokenCacheConnection:
            def execute(self, *_args, **_kwargs):
                raise OSError("cache disk unavailable")

        monkeypatch.setattr(cache, "_get_cache_conn", lambda: BrokenCacheConnection())

        compatibility_conn = duckdb.connect(":memory:")
        try:
            with pytest.raises(cache.RFMCacheUnavailableError, match="初始化失败"):
                cache._read_db_cache(
                    None,
                    "2025-07-14",
                    "2026-07-13",
                    None,
                    "GSV",
                    None,
                    DATA_VERSION,
                    compatibility_conn,
                    current_orders_count=ORDERS_COUNT,
                )
        finally:
            compatibility_conn.close()

    def test_last_complete_generation_serves_during_new_data_precompute(self, cache_conn):
        old_version = "2026-07-04 23:59:58"
        old_generation = "complete-old"
        key = _insert_cache_row(
            cache_conn,
            key_data_version=old_version,
            cached_mtime=old_version,
            generation_id=old_generation,
            result={"marker": "last-complete-generation"},
        )
        _insert_cache_row(
            cache_conn,
            key_data_version=DATA_VERSION,
            cached_mtime=DATA_VERSION,
            cached_orders_count=ORDERS_COUNT + 100,
            generation_id="partial-new",
            result={"marker": "partial-new-generation"},
        )
        cache._activate_cache_generation(
            cache_conn,
            old_generation,
            old_version,
            ORDERS_COUNT,
        )

        assert _read_shifted_cache(
            cache_conn,
            current_mtime=DATA_VERSION,
            current_orders_count=ORDERS_COUNT + 100,
        ) == {"marker": "last-complete-generation"}
        assert cache_conn.execute(
            f"SELECT COUNT(*) FROM {cache.RFM_CACHE_GENERATION_ROWS_TABLE} "
            "WHERE generation_id = ? AND cache_key = ?",
            [old_generation, key],
        ).fetchone()[0] == 1

    def test_same_data_version_failed_run_cannot_shadow_active_generation(self, cache_conn):
        key = _insert_cache_row(
            cache_conn,
            generation_id="complete-run",
            result={"marker": "complete"},
        )
        _insert_cache_row(
            cache_conn,
            generation_id="failed-partial-run",
            result={"marker": "partial"},
            computed_at=datetime.now() + timedelta(seconds=1),
        )
        cache._activate_cache_generation(
            cache_conn,
            "complete-run",
            DATA_VERSION,
            ORDERS_COUNT,
        )

        assert _read_shifted_cache(cache_conn) == {"marker": "complete"}
        assert cache_conn.execute(
            f"SELECT COUNT(*) FROM {cache.RFM_CACHE_GENERATION_ROWS_TABLE} "
            "WHERE cache_key = ?",
            [key],
        ).fetchone()[0] == 2

    def test_custom_on_demand_cache_prefers_current_version_over_old_custom(self, cache_conn):
        old_version = "2026-07-04 23:59:58"
        _insert_cache_row(
            cache_conn,
            key_data_version=old_version,
            cached_mtime=old_version,
            result={"marker": "old-custom"},
        )
        _insert_cache_row(
            cache_conn,
            result={"marker": "current-custom"},
        )
        cache._activate_cache_generation(
            cache_conn,
            "complete-old",
            old_version,
            ORDERS_COUNT,
        )

        assert _read_shifted_cache(cache_conn) == {"marker": "current-custom"}

    def test_corrupt_active_generation_is_deleted_and_current_cache_serves(self, cache_conn):
        old_version = "2026-07-04 23:59:58"
        active_key = _insert_cache_row(
            cache_conn,
            key_data_version=old_version,
            cached_mtime=old_version,
            generation_id="corrupt-active",
            result="not-json",
        )
        _insert_cache_row(
            cache_conn,
            result={"marker": "current-on-demand"},
        )
        cache._activate_cache_generation(
            cache_conn,
            "corrupt-active",
            old_version,
            ORDERS_COUNT,
        )

        assert _read_shifted_cache(cache_conn) == {"marker": "current-on-demand"}
        assert cache_conn.execute(
            f"SELECT COUNT(*) FROM {cache.RFM_CACHE_GENERATION_ROWS_TABLE} "
            "WHERE generation_id = ? AND cache_key = ?",
            ["corrupt-active", active_key],
        ).fetchone()[0] == 0

    def test_stale_active_metadata_deletes_generation_row_then_serves_current_cache(
        self,
        cache_conn,
    ):
        stale_version = "2026-07-04 23:59:58"
        active_key = _insert_cache_row(
            cache_conn,
            key_data_version=DATA_VERSION,
            cached_mtime=stale_version,
            generation_id="metadata-mismatch",
            result={"marker": "stale-active"},
        )
        _insert_cache_row(
            cache_conn,
            result={"marker": "current-on-demand"},
        )
        cache._activate_cache_generation(
            cache_conn,
            "metadata-mismatch",
            DATA_VERSION,
            ORDERS_COUNT,
        )

        assert _read_shifted_cache(cache_conn) == {"marker": "current-on-demand"}
        assert cache_conn.execute(
            f"SELECT COUNT(*) FROM {cache.RFM_CACHE_GENERATION_ROWS_TABLE} "
            "WHERE generation_id = ? AND cache_key = ?",
            ["metadata-mismatch", active_key],
        ).fetchone()[0] == 0
        assert cache_conn.execute(
            f"SELECT COUNT(*) FROM {cache.RFM_CACHE_TABLE} WHERE cache_key = ?",
            [active_key],
        ).fetchone()[0] == 1


class TestRFMPrecomputePlan:
    def test_frontend_fixed_periods_are_precomputed(self):
        today = date(2026, 7, 15)

        assert PeriodBuilder.yesterday(today)["current"].start == "2026-07-14"
        assert PeriodBuilder.wtd(today)["current"].start == "2026-07-13"
        assert PeriodBuilder.q1(today)["current"].end == "2026-03-31"
        assert PeriodBuilder.q2(today)["current"].end == "2026-06-30"
        assert PeriodBuilder.q3(today)["current"].end == "2026-07-14"
        assert PeriodBuilder.q4(today)["current"].end == "2026-12-31"
        jan_first = date(2026, 1, 1)
        assert PeriodBuilder.ytd(jan_first)["current"].start == "2025-01-01"
        assert PeriodBuilder.ytd(jan_first)["current"].end == "2025-12-31"
        assert PeriodBuilder.q1(jan_first)["current"].start == "2025-10-01"
        assert PeriodBuilder.q1(jan_first)["current"].end == "2025-12-31"
        assert {
            "yesterday", "WTD", "Q1", "Q2", "Q3", "Q4",
        }.issubset(cache.STANDARD_PERIODS)
        assert "达播" in cache.PRECOMPUTE_CHANNELS

    def test_last90days_is_public_semantic_resolver(self):
        ranges = PeriodBuilder.last90days(today=date(2026, 7, 15))

        assert ranges["current"].start == "2026-04-16"
        assert ranges["current"].end == "2026-07-14"
        assert (
            date.fromisoformat(ranges["current"].end)
            - date.fromisoformat(ranges["current"].start)
        ).days + 1 == 90

    def test_year_shift_clamps_leap_day_for_semantic_and_http_paths(self):
        semantic_ranges = PeriodBuilder.last90days(today=date(2028, 5, 29))
        ytd_ranges = PeriodBuilder.ytd(today=date(2024, 3, 1))
        mtd_ranges = PeriodBuilder.mtd(today=date(2024, 3, 1))
        http_ranges = _resolve_date_ranges(
            None,
            "2028-02-29",
            "2028-03-31",
            None,
            None,
        )

        assert semantic_ranges["comparison"].start == "2027-02-28"
        assert ytd_ranges["current"].end == "2024-02-29"
        assert ytd_ranges["comparison"].end == "2023-02-28"
        assert mtd_ranges["current"].start == "2024-02-01"
        assert mtd_ranges["current"].end == "2024-02-29"
        assert mtd_ranges["comparison"].end == "2023-02-28"
        assert http_ranges["comp"][0] == "2027-02-28 00:00:00"
        assert http_ranges["prev2"][0] == "2026-02-28 00:00:00"

    def test_precompute_compare_ranges_match_http_ssot(self):
        default, default_start, default_end = cache._resolve_precompute_query_ranges(
            "2026-04-16", "2026-07-14", "default"
        )
        expected_default = _resolve_date_ranges(
            None, "2026-04-16", "2026-07-14", None, None
        )
        custom, custom_start, custom_end = cache._resolve_precompute_query_ranges(
            "2026-04-16", "2026-07-14", "auto_mom"
        )
        expected_custom = _resolve_date_ranges(
            None, "2026-04-16", "2026-07-14", custom_start, custom_end
        )

        assert (default_start, default_end) == (None, None)
        assert default == expected_default
        assert (custom_start, custom_end) == ("2026-01-16", "2026-04-15")
        assert custom == expected_custom

        with pytest.raises(ValueError, match="不支持"):
            cache._resolve_precompute_query_ranges(
                "2026-04-16", "2026-07-14", "Q-1"
            )

    def test_logical_coverage_is_distinct_from_physical_keys(self):
        today = date(2026, 7, 15)
        current_ranges = [
            getattr(PeriodBuilder, name.lower())(today=today)["current"]
            for name in cache.STANDARD_PERIODS
        ] + [cache._resolve_range_period(name, today)["current"] for name in cache.RANGE_PERIODS]
        logical_keys = []
        for metric_type in ("GSV", "GMV"):
            for current in current_ranges:
                for channel in cache.PRECOMPUTE_CHANNELS:
                    for compare_mode in cache.COMPARE_MODES:
                        _, compare_start, compare_end = cache._resolve_precompute_query_ranges(
                            current.start, current.end, compare_mode
                        )
                        logical_keys.append(
                            _cache_key(
                                None,
                                current.start,
                                current.end,
                                channel,
                                metric_type,
                                None,
                                DATA_VERSION,
                                compare_start,
                                compare_end,
                            )
                        )

        assert len(logical_keys) == cache.EXPECTED_LOGICAL_PRECOMPUTE_COMBINATIONS == 380
        assert len(set(logical_keys)) < len(logical_keys)

    def test_precompute_fails_fast_when_cache_connection_cannot_open(self, monkeypatch):
        def fail_connection():
            raise OSError("cache unavailable")

        monkeypatch.setattr(cache, "_get_cache_conn", fail_connection)

        with pytest.raises(RuntimeError, match="无法打开写连接"):
            cache.precompute_rfm_cache()

    def test_precompute_reports_full_logical_coverage_and_dedupes_aliases(self, monkeypatch):
        class FakeBizConnection:
            sql = ""

            def execute(self, sql, _params=None):
                self.sql = sql
                return self

            def fetchone(self):
                if "MAX(pay_time)" in self.sql:
                    return (datetime(2026, 7, 5, 23, 59, 58),)
                if "COUNT(*)" in self.sql:
                    return (ORDERS_COUNT,)
                raise AssertionError(self.sql)

            def close(self):
                return None

        class FakeWriteConnection:
            def __init__(self):
                self.insert_params = []
                self.sql = ""

            def execute(self, sql, params=None):
                self.sql = sql
                if "INSERT INTO" in sql:
                    self.insert_params.append(params)
                return self

            def fetchone(self):
                if "COUNT(*)" in self.sql:
                    return (len(self.insert_params),)
                raise AssertionError(self.sql)

            def close(self):
                return None

        write_conn = FakeWriteConnection()
        monkeypatch.setattr(cache, "_get_cache_conn", lambda: write_conn)
        monkeypatch.setattr(cache.duckdb, "connect", lambda *_args, **_kwargs: FakeBizConnection())
        monkeypatch.setattr(cache, "_ensure_db_cache_table", lambda _conn: None)
        monkeypatch.setattr(cache, "_fetch_max_pay_time", lambda _conn: DATA_VERSION)
        monkeypatch.setattr(cache, "_run_rfm_period", lambda *_args, **_kwargs: ({}, {}, {}, {}))
        monkeypatch.setattr(cache, "_build_rows", lambda *_args, **_kwargs: [])
        prune_calls = []
        activation_calls = []
        monkeypatch.setattr(
            cache,
            "_activate_cache_generation",
            lambda conn, generation, version, count: activation_calls.append(
                (conn, generation, version, count)
            ),
        )
        monkeypatch.setattr(
            cache,
            "_prune_rfm_cache_after_success",
            lambda conn: prune_calls.append(conn) or 0,
        )

        logical_count = cache.precompute_rfm_cache()
        inserted_keys = [params[0] for params in write_conn.insert_params]
        inserted_periods = [params[1] for params in write_conn.insert_params]
        inserted_generations = [params[-1] for params in write_conn.insert_params]
        today = date.today()
        expected_keys = set()
        current_ranges = [
            getattr(PeriodBuilder, name.lower())(today=today)["current"]
            for name in cache.STANDARD_PERIODS
        ] + [
            cache._resolve_range_period(name, today)["current"]
            for name in cache.RANGE_PERIODS
        ]
        for metric_type in ("GSV", "GMV"):
            for current in current_ranges:
                for channel in cache.PRECOMPUTE_CHANNELS:
                    for compare_mode in cache.COMPARE_MODES:
                        _, compare_start, compare_end = cache._resolve_precompute_query_ranges(
                            current.start,
                            current.end,
                            compare_mode,
                        )
                        expected_keys.add(
                            _cache_key(
                                None,
                                current.start,
                                current.end,
                                channel,
                                metric_type,
                                None,
                                DATA_VERSION,
                                compare_start,
                                compare_end,
                            )
                        )

        assert logical_count == cache.EXPECTED_LOGICAL_PRECOMPUTE_COMBINATIONS == 380
        assert len(inserted_keys) == len(set(inserted_keys))
        assert len(inserted_keys) < logical_count
        assert set(inserted_keys) == expected_keys
        assert "LAST90DAYS" in inserted_periods
        assert len(set(inserted_generations)) == 1
        assert activation_calls == [
            (write_conn, inserted_generations[0], DATA_VERSION, ORDERS_COUNT)
        ]
        assert prune_calls == [write_conn]

    def test_retention_prune_removes_only_rows_older_than_48_hours(self, cache_conn):
        old_key = _insert_cache_row(
            cache_conn,
            start_date="2025-01-01",
            end_date="2025-12-31",
            computed_at=datetime.now() - timedelta(hours=72),
        )
        fresh_key = _insert_cache_row(
            cache_conn,
            start_date="2025-01-02",
            end_date="2026-01-01",
            computed_at=datetime.now() - timedelta(hours=12),
        )

        assert cache._prune_rfm_cache_after_success(cache_conn) == 1
        remaining = {
            row[0]
            for row in cache_conn.execute(
                f"SELECT cache_key FROM {cache.RFM_CACHE_TABLE}"
            ).fetchall()
        }
        assert old_key not in remaining
        assert fresh_key in remaining

    def test_retention_prune_never_deletes_active_generation(self, cache_conn):
        active_key = _insert_cache_row(
            cache_conn,
            generation_id="slow-complete-run",
            computed_at=datetime.now() - timedelta(hours=72),
        )
        cache._activate_cache_generation(
            cache_conn,
            "slow-complete-run",
            DATA_VERSION,
            ORDERS_COUNT,
        )

        assert cache._prune_rfm_cache_after_success(cache_conn) == 0
        assert cache_conn.execute(
            f"SELECT COUNT(*) FROM {cache.RFM_CACHE_GENERATION_ROWS_TABLE} "
            "WHERE generation_id = ? AND cache_key = ?",
            ["slow-complete-run", active_key],
        ).fetchone()[0] == 1

    def test_failed_precompute_never_prunes_previous_generation(self, monkeypatch):
        class FakeBizConnection:
            sql = ""

            def execute(self, sql, _params=None):
                self.sql = sql
                return self

            def fetchone(self):
                if "MAX(pay_time)" in self.sql:
                    return (datetime(2026, 7, 5, 23, 59, 58),)
                if "COUNT(*)" in self.sql:
                    return (ORDERS_COUNT,)
                raise AssertionError(self.sql)

            def close(self):
                return None

        class FakeWriteConnection:
            def execute(self, *_args, **_kwargs):
                return self

            def close(self):
                return None

        prune_called = False
        activation_called = False

        def mark_prune(_conn):
            nonlocal prune_called
            prune_called = True
            return 0

        def mark_activation(*_args):
            nonlocal activation_called
            activation_called = True

        monkeypatch.setattr(cache, "_get_cache_conn", lambda: FakeWriteConnection())
        monkeypatch.setattr(cache.duckdb, "connect", lambda *_args, **_kwargs: FakeBizConnection())
        monkeypatch.setattr(cache, "_ensure_db_cache_table", lambda _conn: None)
        monkeypatch.setattr(cache, "_fetch_max_pay_time", lambda _conn: DATA_VERSION)
        monkeypatch.setattr(cache, "_run_rfm_period", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("query failed")))
        monkeypatch.setattr(cache, "_activate_cache_generation", mark_activation)
        monkeypatch.setattr(cache, "_prune_rfm_cache_after_success", mark_prune)

        with pytest.raises(RuntimeError, match="query failed"):
            cache.precompute_rfm_cache()
        assert activation_called is False
        assert prune_called is False

    def test_etl_does_not_clear_working_cache_before_long_precompute(self):
        source = (REPO_ROOT / "scripts/etl/cli.py").read_text(encoding="utf-8")
        step6_start = source.index("# Step 6: 预计算 RFM")
        step6 = source[step6_start:source.index("# Step 7: 创建 user_rfm", step6_start)]

        assert "clear_rfm_cache" not in step6
        assert "EXPECTED_LOGICAL_PRECOMPUTE_COMBINATIONS" in step6

class TestRFMCacheFailureResponse:
    @pytest.mark.parametrize(
        "request_kwargs",
        [
            {"start_date": "2026-01-01", "end_date": "2026-03-31"},
            {"start_date": "2026-07-15", "end_date": "2026-07-15"},
            {
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
                "channel": "达播",
            },
            {
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
                "exclude_channels": ["U先派样", "百补派样", "赠品&0.01", "其他"],
            },
            {
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
                "compare_start_date": "2025-10-01",
                "compare_end_date": "2025-12-31",
            },
        ],
        ids=["q1", "end-today", "channel", "exclude-low-price", "custom-compare"],
    )
    def test_cache_only_http_miss_never_executes_live_sql(
        self,
        cache_conn,
        monkeypatch,
        request_kwargs,
    ):
        from backend.services.health.rfm_analysis import analysis

        biz_conn = duckdb.connect(":memory:")
        biz_conn.execute("CREATE TABLE orders(pay_time TIMESTAMP)")
        biz_conn.execute("INSERT INTO orders VALUES (?::TIMESTAMP)", [DATA_VERSION])
        monkeypatch.setattr(analysis.bdc, "get_connection", lambda: biz_conn)
        live_calls = 0

        def count_live(*_args, **_kwargs):
            nonlocal live_calls
            live_calls += 1
            raise AssertionError("HTTP cache miss must not execute live RFM")

        monkeypatch.setattr(analysis, "_run_rfm_period_serial", count_live)
        try:
            with pytest.raises(cache.RFMCacheMissError, match="尚未预热"):
                analysis.get_rfm_analysis(
                    metric_type="GSV",
                    allow_live_compute=False,
                    **request_kwargs,
                )
        finally:
            biz_conn.close()

        assert live_calls == 0

    def test_old_active_generation_remains_last_known_good(self, cache_conn):
        generation_id = "older-than-48h"
        _insert_cache_row(
            cache_conn,
            generation_id=generation_id,
            result={"marker": "last-known-good"},
            computed_at=datetime.now() - timedelta(hours=72),
        )
        cache._activate_cache_generation(
            cache_conn,
            generation_id,
            DATA_VERSION,
            ORDERS_COUNT,
        )
        cache_conn.execute(
            f"UPDATE {cache.RFM_CACHE_GENERATION_TABLE} "
            "SET completed_at = CURRENT_TIMESTAMP - INTERVAL '72 hours' "
            "WHERE singleton_id = 1"
        )

        assert _read_shifted_cache(cache_conn) == {"marker": "last-known-good"}

    def test_analysis_does_not_swallow_cache_write_outage(self, cache_conn, monkeypatch):
        from backend.services.health.rfm_analysis import analysis

        biz_conn = duckdb.connect(":memory:")
        biz_conn.execute("CREATE TABLE orders(pay_time TIMESTAMP)")
        biz_conn.execute("INSERT INTO orders VALUES (?::TIMESTAMP)", [DATA_VERSION])
        monkeypatch.setattr(analysis.bdc, "get_connection", lambda: biz_conn)
        monkeypatch.setattr(
            analysis,
            "_run_rfm_period_serial",
            lambda *_args, **_kwargs: ({}, {}, {}, {}),
        )
        monkeypatch.setattr(analysis, "_build_rows", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(
            analysis,
            "_write_db_cache",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                cache.RFMCacheUnavailableError("cache write unavailable")
            ),
        )

        try:
            with pytest.raises(cache.RFMCacheUnavailableError, match="write unavailable"):
                analysis.get_rfm_analysis(
                    start_date="2026-01-01",
                    end_date="2026-03-31",
                    metric_type="GSV",
                )
        finally:
            biz_conn.close()

    def test_router_returns_retryable_503_for_cache_outage(self, monkeypatch):
        from fastapi import HTTPException, Response

        from backend.routers import health

        def fail_cache(**_kwargs):
            raise cache.RFMCacheUnavailableError("cache unavailable")

        monkeypatch.setattr(health.rfm_analysis_service, "get_rfm_analysis", fail_cache)

        with pytest.raises(HTTPException) as error:
            health.get_rfm_analysis(
                response=Response(),
                start_date="2025-07-14",
                end_date="2026-07-13",
                metric_type="GSV",
                exclude_channels=None,
                channel=None,
                compare_start_date=None,
                compare_end_date=None,
            )

        assert error.value.status_code == 503
        assert error.value.headers == {"Retry-After": "30"}

    def test_router_marks_cache_miss_and_disables_live_compute(self, monkeypatch):
        from fastapi import HTTPException, Response

        from backend.routers import health

        def miss_cache(**kwargs):
            assert kwargs["allow_live_compute"] is False
            raise cache.RFMCacheMissError("not prewarmed")

        monkeypatch.setattr(health.rfm_analysis_service, "get_rfm_analysis", miss_cache)

        with pytest.raises(HTTPException) as error:
            health.get_rfm_analysis(
                response=Response(),
                start_date="2026-01-01",
                end_date="2026-03-31",
                metric_type="GSV",
                exclude_channels=None,
                channel=None,
                compare_start_date=None,
                compare_end_date=None,
            )

        assert error.value.status_code == 503
        assert error.value.headers == {"Retry-After": "60"}
