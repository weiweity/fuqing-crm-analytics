"""Computed GSV extension. Frozen competition-result/v1 remains unchanged."""
from __future__ import annotations

import math
import hashlib
from datetime import date
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
DATA_SCOPE = "competition-diagnosis-fixture"


def evidence_payload(result: dict) -> dict:
    return {key: result[key] for key in ("query_id", "query_version", "capability_id", "metric_version",
                                         "resolved_condition", "data_digest", "facts")}


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
        if self.customer_count > self.order_count:
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
    facts_schema_ref: Literal["backend.contracts.competition_computed.CompetitionGsvFacts"] = "backend.contracts.competition_computed.CompetitionGsvFacts"
    existing_result_schema: Literal["competition-gsv-facts/v1"] = FACTS_SCHEMA
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
    facts: CompetitionGsvFacts

    @model_validator(mode="after")
    def bound_facts(self):
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
