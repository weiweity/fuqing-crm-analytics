"""Sprint 195 LLM routing evaluation for ad-hoc-query ask().

The tests stay at the deterministic ask router layer: no DuckDB access, no
service mutation, and no MCP protocol changes.
"""
from __future__ import annotations

from typing import Any, TypeAlias

from scripts.ad_hoc_queries.ask import route_ask, run_ask


DAILY_MULTI = "daily-gsv-multi-period"
ExpectedRoute: TypeAlias = str | tuple[str, ...]


def _matches(command: str | None, expected: ExpectedRoute) -> bool:
    if isinstance(expected, tuple):
        return command in expected
    return command == expected


def _assert_route(text: str, expected: ExpectedRoute) -> dict[str, Any]:
    command, params = route_ask(text)
    assert _matches(command, expected), (
        f"text={text!r} expected route {expected!r}, got {command!r}"
    )
    assert command is not None, f"text={text!r} unexpectedly fell back"
    return params


def _assert_daily_multi(text: str) -> dict[str, Any]:
    params = _assert_route(text, DAILY_MULTI)
    assert params["metrics"] is None
    assert len(params["periods"]) == 4
    return params


def _assert_fallback(text: str) -> None:
    command, params = route_ask(text)
    assert command is None, f"text={text!r} should fallback, got {command!r}"
    assert params == {}

    rows = run_ask(text)
    assert rows == [[
        "list-endpoints",
        "fallback",
        "请说更具体点，如 两年新老客对比 或 最近7天渠道GSV",
        0,
    ]]


def _routing_accuracy(scenarios: list[tuple[str, ExpectedRoute]]) -> tuple[int, int, float]:
    hits = 0
    for text, expected in scenarios:
        command, _ = route_ask(text)
        if _matches(command, expected):
            hits += 1
    total = len(scenarios)
    return hits, total, hits / total


class TestSprint195HighFrequencyScenarios:
    """Sprint 194 mock pre-read and Sprint 190 high-frequency scenarios."""

    def test_sample_member_two_periods_daily(self) -> None:
        params = _assert_daily_multi("小样 + 会员 + 多周期对比")
        assert params["periods"][0] <= params["periods"][1]

    def test_new_old_daily_8_metrics(self) -> None:
        _assert_daily_multi("新增用户和复购用户按天看 8 维度周期对比")

    def test_618_yoy_battle(self) -> None:
        _assert_route("今年 618 GSV 同比", "yoy-battle")

    def test_export_excel_full(self) -> None:
        _assert_route("2026 H1 整份 Excel 给我", "export-excel")

    def test_repurchase_cycle(self) -> None:
        _assert_route("看一下复购周期分布", "rfm-repurchase")


class TestSprint195Sprint183190TriggeredCases:
    """Sprint 183/190 triggered daily-gsv-multi-period scenarios."""

    def test_sample_gmv_gsv_multi_period(self) -> None:
        _assert_daily_multi("小样 GMV/GSV 按天多周期")

    def test_sample_member_8_metrics_period_compare(self) -> None:
        _assert_daily_multi("派样和会员的 8 维度周期对比")

    def test_multi_period_sample_member_new_old(self) -> None:
        _assert_daily_multi("多周期对比 sample member new old")

    def test_daily_8_metrics_two_windows(self) -> None:
        _assert_daily_multi("按天 8 维度 两个窗口拆一下")

    def test_period_compare_not_tool_missing(self) -> None:
        _assert_daily_multi("周期对比，不要报工具缺位")


class TestSprint195AskRouterRegression:
    """Task 1 regression: five new keywords route without fallback."""

    def test_keyword_xiaoyang(self) -> None:
        _assert_daily_multi("小样")

    def test_keyword_paiyang(self) -> None:
        _assert_daily_multi("派样")

    def test_keyword_multi_period(self) -> None:
        _assert_daily_multi("多周期")

    def test_keyword_8_dimensions(self) -> None:
        _assert_daily_multi("8 维度")

    def test_keyword_period_compare(self) -> None:
        _assert_daily_multi("周期对比")


class TestSprint195EdgeCases:
    """True tool-missing edge cases should still fallback politely."""

    def test_more_than_8_dimensions_fallback(self) -> None:
        _assert_fallback("第九个指标 UV 和留存 cohort 一起拆")

    def test_detail_rows_fallback(self) -> None:
        _assert_fallback("订单行级原始明细")

    def test_metric_outside_8_enum_fallback(self) -> None:
        _assert_fallback("客单价 AUS 和件单价拆品牌")

    def test_fuzzy_business_question_fallback(self) -> None:
        _assert_fallback("最近整体怎么样")

    def test_unknown_dimension_fallback(self) -> None:
        _assert_fallback("城市分层留存 cohort")


class TestSprint195RoutingAccuracy:
    """Comprehensive routing accuracy must stay above 95%."""

    SCENARIOS: list[tuple[str, ExpectedRoute]] = [
        ("小样 + 会员 + 多周期对比", DAILY_MULTI),
        ("整份 Excel", "export-excel"),
        ("今年 618 GSV 同比", "yoy-battle"),
        ("复购周期", "rfm-repurchase"),
        ("数据排查", "dq-report"),
    ]

    def _assert_accuracy_threshold(self) -> None:
        hits, total, accuracy = _routing_accuracy(self.SCENARIOS)
        assert accuracy >= 0.95, (
            f"Sprint 195 routing accuracy {hits}/{total} = {accuracy:.1%}, "
            "expected >= 95%"
        )

    def test_accuracy_sample_member_multi_period(self) -> None:
        _assert_route("小样 + 会员 + 多周期对比", DAILY_MULTI)
        self._assert_accuracy_threshold()

    def test_accuracy_export_excel(self) -> None:
        _assert_route("整份 Excel", "export-excel")
        self._assert_accuracy_threshold()

    def test_accuracy_yoy_battle(self) -> None:
        _assert_route("今年 618 GSV 同比", "yoy-battle")
        self._assert_accuracy_threshold()

    def test_accuracy_repurchase_cycle(self) -> None:
        _assert_route("复购周期", "rfm-repurchase")
        self._assert_accuracy_threshold()

    def test_accuracy_dq_report(self) -> None:
        _assert_route("数据排查", "dq-report")
        self._assert_accuracy_threshold()
