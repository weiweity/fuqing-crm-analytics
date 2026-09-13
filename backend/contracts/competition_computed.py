"""Computed GSV extension. Frozen competition-result/v1 remains unchanged."""
from __future__ import annotations

import math
import hashlib
from datetime import date, timedelta
from typing import Annotated, Literal

from pydantic import Field, FiniteFloat, model_validator

from backend.contracts.analytics import OpaqueId
from backend.contracts.analytics_query import Sha256Hex, canonical_json
from backend.contracts.competition_c0 import (
    Completeness, CompetitionModel, CompetitionResolvedCondition, InclusiveDateRange,
    ResultPage, StrictCount,
)

QUERY_ID = "competition_gsv_comparison"
QUERY_VERSION = "competition-gsv-query/v1"
METRIC_VERSION = "competition-gsv-metric/v1"
RESULT_SCHEMA = "competition-computed-result/v1"
FACTS_SCHEMA = "competition-gsv-facts/v1"
UNIT_FACTS_SCHEMA = "competition-gsv-facts/v2"
DAILY_FACTS_SCHEMA = "competition-gsv-facts/v3"
BRIDGE_FACTS_SCHEMA = "competition-gsv-facts/v4"
FUNNEL_FACTS_SCHEMA = "competition-gsv-facts/v5"
MAX_DAILY_POINTS = 366
MAX_CHANNEL_CONTRIBUTIONS = 200
DATA_SCOPE = "competition-diagnosis-fixture"


def evidence_payload(result: dict) -> dict:
    return {key: result[key] for key in ("query_id", "query_version", "capability_id", "metric_version",
                                         "resolved_condition", "data_digest", "facts")}


_FLOAT_SLACK = 2.0 ** -50


def reconciles(parts: list[float], total: float, *, operands: tuple[float, ...] = ()) -> bool:
    """Reconcile a four-decimal decomposition with its four-decimal parent total.

    Parts and total are rounded to four decimals independently and then held as binary
    floats, so each carries a representation error of at most half an ULP of its own
    magnitude; summing the parts can therefore differ from the total by a few ULPs of
    the largest magnitudes involved, never by a fixed amount. A difference of two large
    totals amplifies that error further, so the delta decomposition passes its operands:
    the bound must scale with the magnitudes that produced the differences, not with the
    (possibly tiny) reconciled result itself.
    """
    scale = math.fsum([abs(part) for part in parts] + [abs(value) for value in operands])
    return abs(math.fsum(parts) - total) <= max(abs(total), scale, 1.0) * _FLOAT_SLACK


class GsvPeriodFacts(CompetitionModel):
    requested_period: InclusiveDateRange
    through_date: date | None
    gsv: Annotated[FiniteFloat, Field(strict=True, ge=0)] | None
    order_count: StrictCount
    customer_count: StrictCount

    @model_validator(mode="after")
    def period_shape(self):
        if self.through_date is None:
            if self.gsv is not None or self.order_count or self.customer_count:
                raise ValueError("an unavailable period cannot contain amounts or counts")
        elif not self.requested_period.start_date <= self.through_date <= self.requested_period.end_date:
            raise ValueError("through_date must be within the requested period")
        elif self.gsv is None:
            raise ValueError("an available period must contain a numeric GSV, including zero")
        if self.customer_count is not None and self.customer_count > self.order_count:
            raise ValueError("purchasing customers cannot exceed effective orders")
        return self


class CompetitionGsvFacts(CompetitionModel):
    schema_version: Literal["competition-gsv-facts/v1"] = FACTS_SCHEMA
    metric_type: Literal["GSV"] = "GSV"
    current: GsvPeriodFacts
    comparison: GsvPeriodFacts
    difference: Annotated[FiniteFloat, Field(strict=True)] | None
    change_ratio: Annotated[FiniteFloat, Field(strict=True)] | None
    change_ratio_unavailable_reason: Literal["PERIOD_UNAVAILABLE", "ZERO_COMPARISON_GSV"] | None

    @model_validator(mode="after")
    def arithmetic(self):
        current, comparison = self.current.gsv, self.comparison.gsv
        if current is None or comparison is None:
            if (self.difference is not None or self.change_ratio is not None
                    or self.change_ratio_unavailable_reason != "PERIOD_UNAVAILABLE"):
                raise ValueError("unavailable periods cannot yield a change")
            return self
        if self.difference != round(current - comparison, 4):
            raise ValueError("difference must match period GSV")
        if comparison == 0:
            if self.change_ratio is not None or self.change_ratio_unavailable_reason != "ZERO_COMPARISON_GSV":
                raise ValueError("zero comparison GSV must yield an unavailable ratio")
        elif (self.change_ratio is None or self.change_ratio_unavailable_reason is not None
              or not math.isclose(self.change_ratio, (current - comparison) / comparison, rel_tol=1e-12, abs_tol=1e-12)):
            raise ValueError("change_ratio must be the raw ratio, not a percent")
        return self


class CompetitionMoneyUnit(CompetitionModel):
    """Source-declared raw amount unit, never inferred from another catalogue."""

    status: Literal["KNOWN", "UNKNOWN"] = "UNKNOWN"
    currency: Literal["CNY"] | None = None
    amount_unit: Literal["major", "minor"] | None = None

    @model_validator(mode="after")
    def declared_unit(self):
        if self.status == "KNOWN":
            if self.currency is None or self.amount_unit is None:
                raise ValueError("a known amount unit requires currency and denomination")
        elif self.currency is not None or self.amount_unit is not None:
            raise ValueError("an unknown amount unit cannot assert a currency or denomination")
        return self


class CompetitionGsvFactsV2(CompetitionGsvFacts):
    schema_version: Literal["competition-gsv-facts/v2"] = UNIT_FACTS_SCHEMA
    money_unit: CompetitionMoneyUnit


class GsvDailyPoint(CompetitionModel):
    date: date
    gsv: Annotated[FiniteFloat, Field(strict=True, ge=0)] | None
    order_count: StrictCount


class GsvDailySeries(CompetitionModel):
    """Payment-day net GSV at the parent result's cutoff, not refund-day cashflow."""

    grain: Literal["DAY"] = "DAY"
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    status: Literal["AVAILABLE", "UNSUPPORTED_RANGE"]
    unavailable_reason: Literal["RANGE_EXCEEDS_366_DAYS"] | None
    points: Annotated[list[GsvDailyPoint], Field(max_length=MAX_DAILY_POINTS)]


class CompetitionGsvFactsV3(CompetitionGsvFactsV2):
    schema_version: Literal["competition-gsv-facts/v3"] = DAILY_FACTS_SCHEMA
    current_daily: GsvDailySeries

    @model_validator(mode="after")
    def daily_matches_period(self):
        period, series = self.current, self.current_daily
        start, end = period.requested_period.start_date, period.requested_period.end_date
        length = (end - start).days + 1
        if length > MAX_DAILY_POINTS:
            if (series.status != "UNSUPPORTED_RANGE" or series.unavailable_reason != "RANGE_EXCEEDS_366_DAYS"
                    or series.points):
                raise ValueError("daily series outside the bound must explicitly refuse without truncation")
            return self
        if series.status != "AVAILABLE" or series.unavailable_reason is not None or len(series.points) != length:
            raise ValueError("daily series must cover every requested calendar day")
        for index, point in enumerate(series.points):
            if point.date != start + timedelta(days=index):
                raise ValueError("daily dates must be contiguous, ordered and match the requested period")
            covered = period.through_date is not None and point.date <= period.through_date
            if not covered and (point.gsv is not None or point.order_count != 0):
                raise ValueError("uncovered daily points must remain null, not zero")
            if covered and (point.gsv is None or (point.order_count == 0 and point.gsv != 0)):
                raise ValueError("covered daily points require amounts; no effective orders means zero")
        if sum(point.order_count for point in series.points) != period.order_count:
            raise ValueError("daily order counts must match the period")
        if period.gsv is not None and not reconciles(
                [point.gsv for point in series.points if point.gsv is not None], period.gsv):
            raise ValueError("daily GSV must sum to the period GSV")
        return self


class GsvChannelContribution(CompetitionModel):
    channel: Annotated[str, Field(strict=True, min_length=1, max_length=160)]
    current_gsv: Annotated[FiniteFloat, Field(strict=True, ge=0)]
    comparison_gsv: Annotated[FiniteFloat, Field(strict=True, ge=0)]
    delta: Annotated[FiniteFloat, Field(strict=True)]


class GsvChannelBridge(CompetitionModel):
    """Additive sales-channel comparison, not causal marketing attribution."""

    dimension: Literal["SALES_CHANNEL"] = "SALES_CHANNEL"
    status: Literal["AVAILABLE", "UNAVAILABLE"]
    unavailable_reason: Literal["PERIOD_UNAVAILABLE", "MONEY_UNIT_UNKNOWN", "AMBIGUOUS_ORDER_CHANNEL",
                                "INVALID_CHANNEL", "CHANNEL_LIMIT_EXCEEDED"] | None
    contributions: Annotated[list[GsvChannelContribution], Field(max_length=MAX_CHANNEL_CONTRIBUTIONS)]


class CompetitionGsvFactsV4(CompetitionGsvFactsV3):
    schema_version: Literal["competition-gsv-facts/v4"] = BRIDGE_FACTS_SCHEMA
    channel_bridge: GsvChannelBridge

    @model_validator(mode="after")
    def channel_bridge_matches_periods(self):
        bridge = self.channel_bridge
        unavailable_period = self.current.gsv is None or self.comparison.gsv is None
        expected_reason = ("PERIOD_UNAVAILABLE" if unavailable_period else
                           "MONEY_UNIT_UNKNOWN" if self.money_unit.status != "KNOWN" else None)
        if bridge.status == "UNAVAILABLE":
            if bridge.unavailable_reason is None or bridge.contributions:
                raise ValueError("unavailable bridge must state a reason and contain no invented contributions")
            if expected_reason is not None and bridge.unavailable_reason != expected_reason:
                raise ValueError("bridge unavailability must match its parent facts")
            if expected_reason is None and bridge.unavailable_reason in {"PERIOD_UNAVAILABLE", "MONEY_UNIT_UNKNOWN"}:
                raise ValueError("bridge unavailability contradicts its parent facts")
            return self
        if expected_reason is not None or bridge.unavailable_reason is not None:
            raise ValueError("available bridge requires both periods and a declared common money unit")
        names = [item.channel for item in bridge.contributions]
        if any(not name.strip() for name in names) or names != sorted(set(names)):
            raise ValueError("bridge channels must be distinct, nonblank and in stable channel order")
        for item in bridge.contributions:
            if item.delta != round(item.current_gsv - item.comparison_gsv, 4):
                raise ValueError("channel contribution must be its computed period difference")
        operands = tuple(value for item in bridge.contributions for value in (item.current_gsv, item.comparison_gsv))
        if (not reconciles([item.current_gsv for item in bridge.contributions], self.current.gsv)
                or not reconciles([item.comparison_gsv for item in bridge.contributions], self.comparison.gsv)
                or not reconciles([item.delta for item in bridge.contributions], self.difference, operands=operands)):
            raise ValueError("channel contributions must reconcile both totals and their difference")
        return self


class GsvPeriodFactsV5(GsvPeriodFacts):
    customer_count: StrictCount | None
    customer_count_unavailable_reason: Literal["AMBIGUOUS_ORDER_CUSTOMER", "INVALID_CUSTOMER"] | None = None

    @model_validator(mode="after")
    def customer_availability(self):
        if (self.customer_count is None) != (self.customer_count_unavailable_reason is not None):
            raise ValueError("unknown customer count requires an explicit identity reason, never a fake zero")
        if self.through_date is None and (self.customer_count != 0 or self.customer_count_unavailable_reason is not None):
            raise ValueError("an unavailable period cannot report a purchasing cohort")
        return self


class PurchaseFrequencyStage(CompetitionModel):
    minimum_orders: Annotated[int, Field(strict=True, ge=1, le=3)]
    customer_count: StrictCount


class PurchaseFrequencyFunnel(CompetitionModel):
    """Nested customer sets by distinct effective orders within the current window.

    Not a visitor/event conversion funnel, lifetime first purchase, or elapsed-time
    analysis. Same-day orders count separately; split order lines do not.
    """
    basis: Literal["CURRENT_PERIOD_EFFECTIVE_ORDERS"] = "CURRENT_PERIOD_EFFECTIVE_ORDERS"
    entity: Literal["USER_ID"] = "USER_ID"
    status: Literal["AVAILABLE", "UNAVAILABLE"]
    unavailable_reason: Literal["PERIOD_UNAVAILABLE", "AMBIGUOUS_ORDER_CUSTOMER", "INVALID_CUSTOMER"] | None
    stages: Annotated[list[PurchaseFrequencyStage], Field(max_length=3)]


class CompetitionGsvFactsV5(CompetitionGsvFactsV4):
    schema_version: Literal["competition-gsv-facts/v5"] = FUNNEL_FACTS_SCHEMA
    current: GsvPeriodFactsV5
    comparison: GsvPeriodFactsV5
    current_purchase_frequency: PurchaseFrequencyFunnel

    @model_validator(mode="after")
    def purchase_frequency_matches_period(self):
        funnel = self.current_purchase_frequency
        unavailable = self.current.through_date is None
        expected_reason = "PERIOD_UNAVAILABLE" if unavailable else self.current.customer_count_unavailable_reason
        if funnel.status == "UNAVAILABLE":
            if funnel.unavailable_reason is None or funnel.stages:
                raise ValueError("unavailable funnel requires a reason and no invented counts")
            if funnel.unavailable_reason != expected_reason:
                raise ValueError("funnel period availability contradicts current facts")
            return self
        if expected_reason is not None or funnel.unavailable_reason is not None:
            raise ValueError("available funnel requires a covered current period")
        if [stage.minimum_orders for stage in funnel.stages] != [1, 2, 3]:
            raise ValueError("purchase frequency stages must be exactly one, two, three orders")
        counts = [stage.customer_count for stage in funnel.stages]
        if counts[0] != self.current.customer_count or counts != sorted(counts, reverse=True):
            raise ValueError("funnel must be nested and start with the current purchasing cohort")
        if sum(counts) > self.current.order_count:
            raise ValueError("funnel cannot imply more orders than the current period contains")
        return self


class CompetitionComputedResult(CompetitionModel):
    schema_version: Literal["competition-computed-result/v1"] = RESULT_SCHEMA
    execution_kind: Literal["TOOL_COMPUTATION"] = "TOOL_COMPUTATION"
    result_id: OpaqueId
    run_id: OpaqueId
    analysis_id: OpaqueId | None = None
    query_id: Literal["competition_gsv_comparison"] = QUERY_ID
    query_version: Literal["competition-gsv-query/v1"] = QUERY_VERSION
    capability_id: Literal["diag.gsv", "diag.yoy", "diag.last_week_same_weekday", "diag.promo_dual_window"]
    metric_id: Literal["gsv"] = "gsv"
    metric_version: Literal["competition-gsv-metric/v1"] = METRIC_VERSION
    facts_schema_ref: Literal["backend.contracts.competition_computed.CompetitionGsvFacts", "backend.contracts.competition_computed.CompetitionGsvFactsV2", "backend.contracts.competition_computed.CompetitionGsvFactsV3", "backend.contracts.competition_computed.CompetitionGsvFactsV4", "backend.contracts.competition_computed.CompetitionGsvFactsV5"] = "backend.contracts.competition_computed.CompetitionGsvFacts"
    existing_result_schema: Literal["competition-gsv-facts/v1", "competition-gsv-facts/v2", "competition-gsv-facts/v3", "competition-gsv-facts/v4", "competition-gsv-facts/v5"] = FACTS_SCHEMA
    completeness: Completeness
    empty_reason: Literal["NO_CURRENT_MONTH_DATA", "PERIOD_AFTER_AS_OF"] | None
    row_count: StrictCount
    page: ResultPage | None
    resolved_condition: CompetitionResolvedCondition
    data_digest: Sha256Hex
    evidence_digest: Sha256Hex
    primary_result_ref: OpaqueId
    data_mode: Literal["SNAPSHOT"] = "SNAPSHOT"
    contains_real_data: Literal[False] = False
    limitations: Annotated[list[str], Field(min_length=1)]
    facts: Annotated[CompetitionGsvFacts | CompetitionGsvFactsV2 | CompetitionGsvFactsV3 | CompetitionGsvFactsV4 | CompetitionGsvFactsV5, Field(discriminator="schema_version")]

    @model_validator(mode="after")
    def bound_facts(self):
        expected_ref = ("backend.contracts.competition_computed.CompetitionGsvFactsV5"
                        if self.facts.schema_version == FUNNEL_FACTS_SCHEMA
                        else "backend.contracts.competition_computed.CompetitionGsvFactsV4"
                        if self.facts.schema_version == BRIDGE_FACTS_SCHEMA
                        else "backend.contracts.competition_computed.CompetitionGsvFactsV3"
                        if self.facts.schema_version == DAILY_FACTS_SCHEMA
                        else "backend.contracts.competition_computed.CompetitionGsvFactsV2"
                        if self.facts.schema_version == UNIT_FACTS_SCHEMA
                        else "backend.contracts.competition_computed.CompetitionGsvFacts")
        if self.existing_result_schema != self.facts.schema_version or self.facts_schema_ref != expected_ref:
            raise ValueError("facts schema references must match the actual facts version")
        if self.primary_result_ref != self.result_id:
            raise ValueError("primary result must reference this result")
        if (self.facts.current.requested_period != self.resolved_condition.current_period
                or self.facts.comparison.requested_period != self.resolved_condition.comparison_period):
            raise ValueError("facts must use the resolved windows")
        unavailable = self.facts.current.gsv is None or self.facts.comparison.gsv is None
        if unavailable:
            if self.completeness != Completeness.EMPTY or self.empty_reason is None or self.row_count != 0 or self.page is not None:
                raise ValueError("unavailable periods must remain EMPTY and cannot be endorsed")
        elif (self.completeness != Completeness.COMPLETE or self.empty_reason is not None or self.row_count != 2
              or self.page is None or self.page.total != 2 or not self.page.complete
              or self.page.checksum != self.evidence_digest):
            raise ValueError("completed comparisons must expose both rows and their evidence checksum")
        digest = hashlib.sha256(canonical_json(evidence_payload(self.model_dump(mode="json"))).encode()).hexdigest()
        if digest != self.evidence_digest:
            raise ValueError("evidence digest does not match computed facts and resolved conditions")
        return self


def computed_openapi() -> dict:
    schema = CompetitionComputedResult.model_json_schema(ref_template="#/components/schemas/{model}")
    definitions = schema.pop("$defs", {})
    return {"openapi": "3.1.0", "info": {"title": "Computed competition GSV", "version": "1"},
            "paths": {}, "x-runtime-extension": RESULT_SCHEMA,
            "components": {"schemas": {**definitions, "CompetitionComputedResult": schema}}}
