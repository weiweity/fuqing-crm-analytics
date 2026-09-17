"""Deterministic GSV tool computation, independent from the model lifecycle."""
from __future__ import annotations

from datetime import timedelta
from math import fsum
from zoneinfo import ZoneInfo

from backend.contracts.analytics_query import canonical_rfc3339
from backend.contracts.competition_c0 import CompetitionCondition, condition_hash_payload
from backend.contracts.competition_computed import (
    DATA_SCOPE, QUERY_ID, QUERY_VERSION, FUNNEL_FACTS_SCHEMA, MAX_DAILY_POINTS, CompetitionComputedResult,
    CompetitionGsvFactsV5, GsvDailySeries, GsvPeriodFacts, GsvPeriodFactsV5,
    PurchaseFrequencyFunnel, evidence_payload,
)
from backend.semantic.time import resolve_comparison_range
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, require
from backend.services.analytics.resource_profile import content_hash
from backend.services.analytics.competition_diagnosis.synthetic import SyntheticDiagnosisSource
from backend.services.metrics.competition_compute import iter_effective_orders
from backend.services.analytics.waterfall_bridge import channel_bridge as _channel_bridge

CAPABILITIES = {"diag.gsv", "diag.yoy", "diag.last_week_same_weekday", "diag.promo_dual_window"}
COMPARISON_CAPABILITIES = {"diag.yoy": "YOY_SAME_PERIOD", "diag.last_week_same_weekday": "LAST_WEEK_SAME_WEEKDAY",
                           "diag.promo_dual_window": "CUSTOM_DUAL_WINDOW"}
RULE_VERSION = "competition-condition-rule/v1"
LIMITATIONS = ["仅显式小型合成快照，不代表真实经营结论。", "仅 GSV 双期、本期逐日与销售渠道差额分解，不代表完整诊断链完成。",
               "派样渠道全集与会员历史仍为 UNKNOWN。", "GSV 按订单净额计算；商品过滤下退款沿现有订单级规则抵扣。",
               "逐日值按支付日归属，退款按截止日回扣原支付日；不是现金流水。最多 366 日，不截断或改粒度。",
               "渠道贡献是同口径两期净额的加法分解，不是因果归因或投放回报；零差额渠道保留，不合并尾部。",
               "购买频次漏斗仅统计本期同一销售范围内至少1/2/3笔有效订单的去重客户；同日不同订单分别计数，子单合并。"
               "不是访客转化、历史首购或时间间隔分析；全退订单不计，部分退款后净额为正才计。"]


def _invalid(message: str) -> AnalyticsError:
    return AnalyticsError(422, "INVALID_REQUEST", message)


def _daily_series(period: GsvPeriodFacts, orders: list[dict]) -> GsvDailySeries:
    start, end = period.requested_period.start_date, period.requested_period.end_date
    length = (end - start).days + 1
    if length > MAX_DAILY_POINTS:
        return GsvDailySeries(status="UNSUPPORTED_RANGE", unavailable_reason="RANGE_EXCEEDS_366_DAYS", points=[])
    by_day = {}
    for order in orders:
        by_day.setdefault(order["pay_date"], []).append(order["net"])
    points = []
    for index in range(length):
        day = start + timedelta(days=index)
        amounts = by_day.get(day.isoformat(), [])
        covered = period.through_date is not None and day <= period.through_date
        points.append({"date": day, "gsv": round(fsum(amounts), 4) if covered else None,
                       "order_count": len(amounts) if covered else 0})
    return GsvDailySeries(status="AVAILABLE", unavailable_reason=None, points=points)


def _customer_identity_error(connection, orders):
    selected = {order["order_id"] for order in orders}
    identities = {}
    # Validate all source lines for selected orders, including filtered-out lines:
    # the shared order calculator retains the first user ID and cannot establish
    # coherent ownership of a split order. Never expose customer IDs in facts.
    for order_id, user_id in connection.execute("SELECT DISTINCT order_id, user_id FROM orders").fetchall():
        if order_id in selected:
            identities.setdefault(order_id, set()).add(user_id)
    if any(len(users) != 1 for users in identities.values()):
        return "AMBIGUOUS_ORDER_CUSTOMER"
    if any(not isinstance(user, str) or not user.strip() for users in identities.values() for user in users):
        return "INVALID_CUSTOMER"
    return None


def _purchase_frequency(period, orders) -> PurchaseFrequencyFunnel:
    reason = "PERIOD_UNAVAILABLE" if period.through_date is None else period.customer_count_unavailable_reason
    if reason is not None:
        return PurchaseFrequencyFunnel(status="UNAVAILABLE", unavailable_reason=reason, stages=[])
    orders_by_customer = {}
    for order in orders:
        orders_by_customer.setdefault(order["user_id"], set()).add(order["order_id"])
    return PurchaseFrequencyFunnel(status="AVAILABLE", unavailable_reason=None, stages=[
        {"minimum_orders": threshold, "customer_count": sum(len(ids) >= threshold for ids in orders_by_customer.values())}
        for threshold in (1, 2, 3)
    ])


def compute_result(source: SyntheticDiagnosisSource, principal: AnalyticsPrincipal,
                   condition: CompetitionCondition, capability_id: str,
                   *, session_id: str, request_id: str) -> CompetitionComputedResult:
    require(principal, "analysis:read", data_scope=DATA_SCOPE)
    if capability_id not in CAPABILITIES:
        raise AnalyticsError(422, "UNSUPPORTED_CAPABILITY", "此计算源尚未实现所请求的诊断能力。")
    if capability_id in COMPARISON_CAPABILITIES and condition.comparison_mode.value != COMPARISON_CAPABILITIES[capability_id]:
        raise _invalid("比较能力必须与显式 comparison_mode 一致。")
    if condition.data_snapshot_ref not in (None, source.snapshot_id) or condition.rule_version not in (None, RULE_VERSION):
        raise _invalid("请求的数据快照或规则版本与当前计算源不匹配。")
    requested = condition.model_dump(mode="json")
    current, comparison = condition.current_period, condition.comparison_period
    expected = resolve_comparison_range(condition.comparison_mode.value, current.start_date.isoformat(),
                                        current.end_date.isoformat(), comparison.start_date.isoformat(),
                                        comparison.end_date.isoformat())
    if (expected.start, expected.end) != (comparison.start_date.isoformat(), comparison.end_date.isoformat()):
        raise _invalid("显式对比日期与所选比较规则不一致。")
    if min(current.start_date, comparison.start_date) < source.coverage_start:
        raise _invalid("请求超出合成快照声明的数据覆盖起点，不能将未覆盖期间算成零。")
    instant = condition.as_of or source.published_at
    if instant > source.published_at:
        raise _invalid("请求 as_of 晚于快照发布时间，请选择当前可用快照。")
    today = instant.astimezone(ZoneInfo("Asia/Shanghai")).date()
    through = min(source.data_through, today - timedelta(days=1))
    as_of = canonical_rfc3339(instant)
    published = canonical_rfc3339(source.published_at)
    scope = "diag_scope_" + content_hash([principal.actor_id, DATA_SCOPE])[:40]
    resolved = {
        **requested, "cutoff": (current.start_date - timedelta(days=1)).isoformat(),
        "as_of": as_of, "published_at": published, "event_time": published,
        "source_tense": "PUBLISHED_SNAPSHOT", "data_snapshot_ref": source.snapshot_id,
        "data_version": source.data_version, "rule_version": RULE_VERSION,
        "sample_history_recomputed": condition.sample_mode.value == "EXCLUDE_AND_RECOMPUTE_HISTORY",
        "sample_channel_set_status": "UNKNOWN", "warehouse_as_of": published, "feature_as_of": None,
        "permission_scope": scope, "actor_id": principal.actor_id, "ignored_filters": [],
        "unknown_flags": [{"code": "SAMPLE_CHANNEL_SET", "status": "UNKNOWN", "note": "未确认真实派样渠道全集。"},
                          {"code": "MEMBER_HISTORY", "status": "UNKNOWN", "note": "当前合成源不提供会员历史。"}],
        "limitations": LIMITATIONS,
    }
    resolved["filter_hash"] = content_hash(condition_hash_payload(resolved))
    with source.connect() as connection:
        periods = []
        orders_by_period = [[], []]
        for index, window in enumerate((current, comparison)):
            if window.start_date > through:
                periods.append(GsvPeriodFactsV5(requested_period=window, through_date=None, gsv=None,
                                              order_count=0, customer_count=0))
                continue
            orders = iter_effective_orders(
                connection, as_of=through.isoformat(), pay_start=window.start_date.isoformat(),
                pay_end=min(window.end_date, through).isoformat(), channels=condition.sales_scope.channel_ids or None,
                product_ids=condition.sales_scope.product_ids or None,
                exclude_channels=condition.sample_channel_ids if condition.sample_mode.value != "INCLUDE" else None,
            )
            orders_by_period[index] = orders
            identity_error = _customer_identity_error(connection, orders)
            # Reuse the exact net-order SSOT for all views. Unrelated new/old or
            # member sorting must not crash a GSV request when identity is missing.
            periods.append(GsvPeriodFactsV5(requested_period=window, through_date=min(window.end_date, through),
                gsv=round(fsum(row["net"] for row in orders), 4), order_count=len(orders),
                customer_count=None if identity_error else len({row["user_id"] for row in orders}),
                customer_count_unavailable_reason=identity_error))
        channel_bridge = _channel_bridge(connection, periods, orders_by_period, source.money_unit)
        purchase_frequency = _purchase_frequency(periods[0], orders_by_period[0])
    c, p = periods[0].gsv, periods[1].gsv
    unavailable = c is None or p is None
    facts = CompetitionGsvFactsV5(current=periods[0], comparison=periods[1], money_unit=source.money_unit,
        current_daily=_daily_series(periods[0], orders_by_period[0]), channel_bridge=channel_bridge,
        current_purchase_frequency=purchase_frequency,
        difference=None if unavailable else round(c - p, 4),
        change_ratio=None if unavailable or p == 0 else (c - p) / p,
        change_ratio_unavailable_reason="PERIOD_UNAVAILABLE" if unavailable else "ZERO_COMPARISON_GSV" if p == 0 else None)
    execution = content_hash([principal.actor_id, session_id, request_id])[:48]
    result_id = "result_diag_" + execution
    payload = {"result_id": result_id, "run_id": "run_diag_" + execution, "capability_id": capability_id,
               "query_id": QUERY_ID, "query_version": QUERY_VERSION, "metric_version": "competition-gsv-metric/v1",
               "existing_result_schema": FUNNEL_FACTS_SCHEMA,
               "facts_schema_ref": "backend.contracts.competition_computed.CompetitionGsvFactsV5",
               "data_digest": source.data_digest, "resolved_condition": resolved, "facts": facts.model_dump(mode="json")}
    digest = content_hash(evidence_payload(payload))
    payload.update(evidence_digest=digest, primary_result_ref=result_id, limitations=LIMITATIONS,
                   completeness="EMPTY" if unavailable else "COMPLETE",
                   empty_reason=("NO_CURRENT_MONTH_DATA" if current.start_date > through
                                 and (current.start_date.year, current.start_date.month) == (today.year, today.month)
                                 else "PERIOD_AFTER_AS_OF") if unavailable else None, row_count=0 if unavailable else 2,
                   page=None if unavailable else {"offset": 0, "limit": 2, "total": 2, "checksum": digest, "complete": True})
    return CompetitionComputedResult.model_validate(payload)
