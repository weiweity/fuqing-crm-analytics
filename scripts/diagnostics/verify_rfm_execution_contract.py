#!/usr/bin/env python3
"""Offline characterization of the current RFM execution control flow.

Run: python3.14 -B scripts/diagnostics/verify_rfm_execution_contract.py

STANDARD LIBRARY ONLY. Reads only the source files listed below. Selects exact
function AST nodes; never executes source-module imports or top-level config.
Database, cache, date-range and calculation dependencies are injected fakes.
No backend imports, .env loading, database connections, SQL execution, services,
network access or file writes. Source SHA256 hashes bind the report to the code.

This is CHARACTERIZATION, not a benchmark, incident reproduction, SQL/metric
golden test, endpoint integration test or proof of database cancellation. The
three-period test stops with a sentinel at period three: only call order is
asserted. Async tests use events to represent work, not threads or actual SQL.
"""

from __future__ import annotations

import __future__
import ast
import asyncio
import hashlib
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_FUNCTIONS = {
    "backend/services/health/rfm_analysis/analysis.py": ("get_rfm_analysis",),
    "backend/services/rfm/_flow_engine.py": ("get_rfm_flow",),
    "backend/services/rfm/r_flow.py": ("get_rfm_r_flow",),
    "backend/services/rfm/f_flow.py": ("get_rfm_f_flow",),
    "backend/services/rfm/m_flow.py": ("get_rfm_m_flow",),
    "backend/routers/rfm.py": ("_cached_rfm_call",),
    "backend/middleware/query_router.py": ("QueryRouterMiddleware._run_read_app",),
}
SOURCE_BYTES = {
    relative: (REPO_ROOT / relative).read_bytes() for relative in SOURCE_FUNCTIONS
}
SAFE_BUILTINS = {
    "Exception": Exception,
    "BaseException": BaseException,
    "round": round,
}
RANGES = {
    "current": ("2025-06-01 00:00:00", "2025-06-30 23:59:59", "2025-05-31"),
    "comp": ("2024-06-01 00:00:00", "2024-06-30 23:59:59", "2024-05-31"),
    "prev2": ("2023-06-01 00:00:00", "2023-06-30 23:59:59", "2023-05-31"),
    "labels": ("2025", "2024", "2023"),
}
REQUEST = {
    "start_date": "2025-06-01",
    "end_date": "2025-06-30",
    "metric_type": "GSV",
    "channel": "fixture-channel",
    "exclude_channels": ["fixture-excluded"],
}


def extract_function(relative: str, qualified_name: str, dependencies: dict):
    """Compile one allowlisted function, never the containing module/class.

    Annotations are deferred and decorators removed (framework setup is outside
    this characterization). Imports inside selected functions are rejected too.
    Restricted builtins omit open/import/eval/exec; this is not an untrusted-code
    sandbox, but prevents accidental normal I/O from newly added dependencies.
    """
    if qualified_name not in SOURCE_FUNCTIONS.get(relative, ()):
        raise ValueError(f"Function is not allowlisted: {relative}:{qualified_name}")
    container = ast.parse(SOURCE_BYTES[relative], filename=relative)
    for part in qualified_name.split("."):
        matches = [
            node for node in container.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == part
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected one AST node: {relative}:{qualified_name}")
        container = matches[0]
    if not isinstance(container, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ValueError(f"Not a function: {qualified_name}")
    if any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(container)):
        raise ValueError(f"Selected function contains an import: {qualified_name}")
    container.decorator_list = []
    module = ast.fix_missing_locations(ast.Module(body=[container], type_ignores=[]))
    namespace = {"__builtins__": SAFE_BUILTINS.copy(), **dependencies}
    code = compile(
        module, relative, "exec", flags=__future__.annotations.compiler_flag,
        dont_inherit=True,
    )
    exec(code, namespace)
    return namespace[container.name]


class FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 9, 5)


class FakeCacheUnavailable(RuntimeError):
    pass


class FakeCacheMiss(FakeCacheUnavailable):
    pass


class ThirdPeriodReached(RuntimeError):
    """Stops before result-building; explicitly not a numerical assertion."""


class EightQuadrantContractTests(unittest.TestCase):
    def setUp(self):
        self.connection = Mock(name="fake_business_connection")
        self.connection.execute.return_value.fetchone.return_value = (1,)
        self.read_cache = Mock(name="fake_cache_read", return_value=None)
        self.compute = Mock(side_effect=AssertionError("Unexpected period computation"))
        self.write_cache = Mock(side_effect=AssertionError("Unexpected cache write"))
        self.function = extract_function(
            "backend/services/health/rfm_analysis/analysis.py", "get_rfm_analysis",
            {
                "date": FixedDate,
                # strptime lazily imports stdlib helpers via the calling frame.
                # Keep that call in this harness, not the no-import AST namespace.
                "datetime": SimpleNamespace(strptime=lambda value, fmt: datetime.strptime(value, fmt)),
                "logger": Mock(),
                "bdc": SimpleNamespace(get_connection=lambda: self.connection),
                "_resolve_date_ranges": Mock(return_value=RANGES),
                "_fetch_max_pay_time": Mock(return_value="fixture-version"),
                "_read_db_cache": self.read_cache,
                "_run_rfm_period_serial": self.compute,
                "_write_db_cache": self.write_cache,
                "RFMCacheMissError": FakeCacheMiss,
                "RFMCacheUnavailableError": FakeCacheUnavailable,
            },
        )

    def assert_no_compute_or_write(self):
        self.compute.assert_not_called()
        self.write_cache.assert_not_called()
        self.connection.execute.assert_called_once_with("SELECT COUNT(*) FROM orders")

    def test_eight_quadrant_cache_hit_returns_without_three_period_computation(self):
        payload = {"fixture": "cached-eight-quadrant"}
        self.read_cache.return_value = payload
        self.assertIs(self.function(**REQUEST, allow_live_compute=False), payload)
        self.read_cache.assert_called_once()
        self.assert_no_compute_or_write()

    def test_eight_quadrant_cache_only_miss_raises_without_three_period_computation(self):
        with self.assertRaises(FakeCacheMiss):
            self.function(**REQUEST, allow_live_compute=False)
        self.assert_no_compute_or_write()

    def test_eight_quadrant_cache_unavailable_propagates_without_live_fallback(self):
        self.read_cache.side_effect = FakeCacheUnavailable("fixture cache unavailable")
        with self.assertRaises(FakeCacheUnavailable):
            self.function(**REQUEST, allow_live_compute=False)
        self.assert_no_compute_or_write()


class FlowContractTests(unittest.TestCase):
    def make_flow(self, dimension, cached, compute):
        connection = object()
        get_connection = Mock(return_value=connection)
        write_cache = Mock(side_effect=AssertionError("Unexpected cache write"))
        engine = extract_function(
            "backend/services/rfm/_flow_engine.py", "get_rfm_flow",
            {
                "bdc": SimpleNamespace(get_connection=get_connection),
                "_resolve_date_ranges": Mock(return_value=RANGES),
                "_fetch_data_version": Mock(return_value="fixture-version"),
                "_flow_cache_key": Mock(return_value="fixture-key"),
                "_get_cached_flow": Mock(return_value=cached),
                "_set_cached_flow": write_cache,
                "run_flow_period": compute,
            },
        )
        upper = dimension.upper()
        wrapper = extract_function(
            f"backend/services/rfm/{dimension}_flow.py", f"get_rfm_{dimension}_flow",
            {
                "get_rfm_flow": engine,
                f"{upper}_SEGMENT_ORDER": ["fixture-segment"],
                f"_{upper}_SEGMENTATION_CTE": "fixture-cte",
                "_r_hist_filters": Mock(return_value=("fixture-refund", "fixture-exclude")),
                "_build_r_segmentation_cte": Mock(return_value="fixture-cte"),
            },
        )
        return wrapper, connection, get_connection, write_cache

    def test_r_f_m_file_cache_hit_returns_without_period_computation(self):
        for dimension in "rfm":
            with self.subTest(dimension=dimension):
                compute = Mock(side_effect=AssertionError("Unexpected flow computation"))
                payload = {"fixture": dimension}
                function, _, get_connection, write_cache = self.make_flow(dimension, payload, compute)
                self.assertIs(function(**REQUEST), payload)
                compute.assert_not_called()
                get_connection.assert_not_called()
                write_cache.assert_not_called()

    def test_r_f_m_cache_miss_calls_current_comparison_prev2_in_order_control_flow_only(self):
        for dimension in "rfm":
            with self.subTest(dimension=dimension):
                compute = Mock(side_effect=[({}, {}, {}, {}), ({}, {}, {}, {}), ThirdPeriodReached()])
                function, connection, get_connection, write_cache = self.make_flow(dimension, None, compute)
                with self.assertRaises(ThirdPeriodReached):
                    function(**REQUEST)
                self.assertEqual(compute.call_count, 3)
                self.assertEqual(
                    [item.args[1:4] for item in compute.call_args_list],
                    [RANGES["current"], RANGES["comp"], RANGES["prev2"]],
                )
                for item in compute.call_args_list:
                    self.assertIs(item.args[0], connection)
                    self.assertEqual(item.args[4], dimension)
                    self.assertEqual(item.args[8:], (REQUEST["channel"], "GSV", REQUEST["exclude_channels"]))
                get_connection.assert_called_once_with()
                write_cache.assert_not_called()

    def test_r_f_m_second_period_failure_does_not_start_third_or_cache_partial_result(self):
        for dimension in "rfm":
            with self.subTest(dimension=dimension):
                compute = Mock(side_effect=[({}, {}, {}, {}), RuntimeError("fixture period failed")])
                function, _, _, write_cache = self.make_flow(dimension, None, compute)
                with self.assertRaisesRegex(RuntimeError, "fixture period failed"):
                    function(**REQUEST)
                self.assertEqual(compute.call_count, 2)
                write_cache.assert_not_called()

    def test_outer_kv_cache_hit_does_not_invoke_service(self):
        cache = Mock()
        cache.get.return_value = {"fixture": "outer-hit"}
        compute = Mock(side_effect=AssertionError("Unexpected service call"))
        function = extract_function(
            "backend/routers/rfm.py", "_cached_rfm_call", {"_rfm_cache": cache},
        )
        self.assertIs(function("r-flow", REQUEST, compute), cache.get.return_value)
        compute.assert_not_called()
        cache.set.assert_not_called()

    def test_outer_kv_cache_miss_invokes_service_then_cache_set(self):
        events = Mock()
        events.cache.get.return_value = None
        events.compute.return_value = {"fixture": "service-result"}
        function = extract_function(
            "backend/routers/rfm.py", "_cached_rfm_call", {"_rfm_cache": events.cache},
        )
        self.assertIs(function("f-flow", REQUEST, events.compute), events.compute.return_value)
        self.assertEqual(events.mock_calls, [
            call.cache.get("f-flow", REQUEST), call.compute(),
            call.cache.set("f-flow", REQUEST, events.compute.return_value),
        ])


class ReadCancellationContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.logger = Mock()
        self.function = extract_function(
            "backend/middleware/query_router.py", "QueryRouterMiddleware._run_read_app",
            {"asyncio": asyncio, "logger": self.logger},
        )

    async def exercise(self, *, cancel=False, fail=False):
        started, release, finished, app_cancelled = (asyncio.Event() for _ in range(4))
        loop = asyncio.get_running_loop()
        previous_handler = loop.get_exception_handler()
        loop_contexts = []
        loop.set_exception_handler(lambda _loop, context: loop_contexts.append(context))

        async def app(scope, receive, send):
            started.set()
            try:
                await release.wait()
                if fail:
                    raise RuntimeError("fixture work failed")
            except asyncio.CancelledError:
                app_cancelled.set()
                raise
            finally:
                finished.set()

        outer = asyncio.create_task(self.function(SimpleNamespace(app=app), {}, None, None))
        try:
            await asyncio.wait_for(started.wait(), timeout=1)
            if cancel:
                outer.cancel()
                # Event-loop checkpoints only, not a timing/performance assertion.
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                self.assertFalse(outer.done(), "Outer cancellation must still wait for work")
                self.assertFalse(finished.is_set())
                self.assertFalse(app_cancelled.is_set(), "Initial cancel must not cancel shielded work")
            release.set()
            if cancel:
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(outer, timeout=1)
            elif fail:
                with self.assertRaisesRegex(RuntimeError, "fixture work failed"):
                    await asyncio.wait_for(outer, timeout=1)
            else:
                await asyncio.wait_for(outer, timeout=1)
            self.assertTrue(finished.is_set())
            self.assertFalse(app_cancelled.is_set())
        finally:
            release.set()
            # Drain fixture work even when an assertion fails; no background work survives.
            try:
                await asyncio.wait_for(asyncio.gather(outer, return_exceptions=True), timeout=1)
                await asyncio.sleep(0)
            finally:
                loop.set_exception_handler(previous_handler)
        # Python 3.14 may additionally report a cancelled shield's later failure
        # to the event-loop handler. Audit that expected fixture diagnostic;
        # unexpected loop errors must fail, not be silently swallowed.
        for context in loop_contexts:
            self.assertTrue(cancel and fail, context)
            self.assertIn("shielded future", context.get("message", ""))
            self.assertIsInstance(context.get("exception"), RuntimeError)
            self.assertEqual(str(context["exception"]), "fixture work failed")

    async def test_read_app_normal_completion_waits_for_fixture_work(self):
        await self.exercise()

    async def test_read_app_single_cancellation_waits_for_work_before_reraising(self):
        await self.exercise(cancel=True)

    async def test_read_app_failure_without_cancellation_propagates(self):
        await self.exercise(fail=True)

    async def test_read_app_failure_after_cancellation_preserves_cancellation(self):
        await self.exercise(cancel=True, fail=True)
        self.logger.debug.assert_called_once()


def tearDownModule():
    forbidden = [name for name in sys.modules if name == "backend" or name.startswith("backend.")]
    if forbidden:
        raise AssertionError(f"Backend imports violate offline boundary: {forbidden}")


if __name__ == "__main__":
    print("OFFLINE CHARACTERIZATION ONLY; fake dependencies; no DB / .env / backend imports.")
    print("Not performance, metric correctness, real SQL cancellation or full integration evidence.")
    for relative, raw in SOURCE_BYTES.items():
        print(f"SOURCE SHA256 {hashlib.sha256(raw).hexdigest()}  {relative}")
    sys.stdout.flush()
    unittest.main(verbosity=2)
