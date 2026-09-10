"""Offline diagnosis orchestration. Does not recompute RFM/GSV or open HTTP."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from backend.contracts.competition_c0 import (
    CompetitionCondition,
    CompetitionResultRef,
    SupportStatus,
)
from backend.services.analytics.access import AnalyticsPrincipal
from backend.services.analytics.competition_diagnosis.catalog import (
    executable,
    require_step,
    visible_capabilities,
)
from backend.services.analytics.competition_diagnosis.chain import (
    COMPARISON_BY_MODE,
    DEFAULT_BUDGET,
    DIAGNOSIS_CHAIN,
    FORBIDDEN_EXPANSIONS,
    INHERITABLE_FIELDS,
    LIVE_TRANSPORT,
    REGISTERED_TOOLS,
    REQUIRED_FOR_COMPLETE_CHAIN,
    SAMPLE_BY_MODE,
    SCHEMA_VERSION,
    STUB_PLANNER,
)
from backend.services.analytics.competition_diagnosis.condition import resolve_condition
from backend.services.analytics.competition_diagnosis.errors import (
    DiagnosisFault,
    budget_exhausted,
    busy,
    cancelled,
    forbidden,
    injection_refused,
    not_connected,
    unauthenticated,
    unsupported_capability,
)
from backend.services.analytics.competition_diagnosis.fixtures import (
    failed_result,
    fixture_result,
    is_empty_mtd,
    unsupported_result,
)
from backend.services.analytics.competition_diagnosis.patch import plan_patch
from backend.contracts.competition_computed import CompetitionComputedResult


@dataclass
class Budget:
    max_tool_calls: int = DEFAULT_BUDGET["max_tool_calls"]
    max_deadline_ms: int = DEFAULT_BUDGET["max_deadline_ms"]
    max_concurrent: int = DEFAULT_BUDGET["max_concurrent"]
    max_retries: int = DEFAULT_BUDGET["max_retries"]
    used_calls: int = 0
    cancelled: bool = False

    def remaining(self) -> int:
        return max(0, self.max_tool_calls - self.used_calls)


@dataclass
class StepRecord:
    capability_id: str
    support_status: str
    completeness: str | None
    result_id: str | None
    run_id: str | None
    evidence_digest: str | None
    filter_hash: str | None
    inherited_fields: list[str]
    changed_fields: list[str]
    queries: bool
    chain_role: str


@dataclass
class DiagnosisSession:
    session_id: str
    principal: AnalyticsPrincipal
    budget: Budget = field(default_factory=Budget)
    prior_condition: dict[str, Any] | None = None
    last_result: CompetitionResultRef | CompetitionComputedResult | None = None
    steps: list[StepRecord] = field(default_factory=list)
    in_flight_patch: dict[str, Any] | None = None
    faults: frozenset[str] = field(default_factory=frozenset)
    chain_status: Literal["COMPLETE", "PARTIAL", "EMPTY", "FAILED", "CANCELLED"] = "PARTIAL"


class DiagnosisAdapter:
    """Single-loop adapter. live_transport stays NOT_CONNECTED in this track."""

    def __init__(
        self,
        principal: AnalyticsPrincipal | None,
        *,
        session_id: str = "session_c0_offline",
        budget: Budget | None = None,
        faults: frozenset[str] | None = None,
    ):
        self.session = DiagnosisSession(
            session_id=session_id,
            principal=principal or AnalyticsPrincipal(actor_id="", capabilities=frozenset(), data_scopes=frozenset()),
            budget=budget or Budget(),
            faults=faults or frozenset(),
        )

    def _charge(self, request_id: str) -> None:
        session = self.session
        if not session.principal.actor_id:
            raise unauthenticated(request_id)
        if session.budget.cancelled:
            raise cancelled(request_id)
        if "busy" in session.faults:
            raise busy(request_id)
        if session.budget.used_calls >= session.budget.max_tool_calls:
            session.chain_status = "PARTIAL"
            raise budget_exhausted(request_id)
        session.budget.used_calls += 1

    def cancel(self, request_id: str) -> dict[str, Any]:
        self.session.budget.cancelled = True
        self.session.chain_status = "CANCELLED"
        fault = cancelled(request_id)
        return {
            "schema_version": SCHEMA_VERSION,
            "chain_status": "CANCELLED",
            "analysis_complete": False,
            "error": fault.error.model_dump(mode="json"),
            "completed_steps": [item.__dict__ for item in self.session.steps],
        }

    def list_capabilities(self, request_id: str) -> dict[str, Any]:
        self._charge(request_id)
        rows = visible_capabilities(self.session.principal)
        return {
            "schema_version": SCHEMA_VERSION,
            "planner": STUB_PLANNER,
            "live_transport": LIVE_TRANSPORT,
            "registered_tools": list(REGISTERED_TOOLS),
            "forbidden_expansions": list(FORBIDDEN_EXPANSIONS),
            "capability_ids": [item["capability_id"] for item in rows],
            "capabilities": rows,
            "actor_id": self.session.principal.actor_id,
            "budget": {
                "used_calls": self.session.budget.used_calls,
                "max_tool_calls": self.session.budget.max_tool_calls,
                "remaining": self.session.budget.remaining(),
            },
        }

    def read_resource(self, resource: str, request_id: str, allowed: tuple[str, ...]) -> dict[str, Any]:
        self._charge(request_id)
        if resource not in allowed:
            raise injection_refused(request_id, "resource")
        return {"resource": resource, "registered": True}

    def _bind_condition(
        self,
        *,
        condition_mode: str,
        condition: dict[str, Any] | None,
        condition_patch: dict[str, Any] | None,
        request_id: str,
    ) -> tuple[CompetitionCondition, dict[str, Any]]:
        parsed, trace = resolve_condition(
            prior=self.session.prior_condition,
            mode=condition_mode,
            condition=condition,
            condition_patch=condition_patch,
            request_id=request_id,
        )
        resolved = parsed.model_dump(mode="json")
        if self.session.prior_condition is not None and self.session.prior_condition != resolved:
            self.session.steps.clear()
            self.session.last_result = None
            self.session.chain_status = "PARTIAL"
        self.session.prior_condition = resolved
        return parsed, trace

    def run_step(
        self,
        *,
        capability_id: str,
        condition_mode: str,
        request_id: str,
        condition: dict[str, Any] | None = None,
        condition_patch: dict[str, Any] | None = None,
        execute: Callable[[str, CompetitionCondition], CompetitionResultRef | CompetitionComputedResult] | None = None,
    ) -> dict[str, Any]:
        self._charge(request_id)
        if capability_id in FORBIDDEN_EXPANSIONS or capability_id.startswith("/"):
            raise injection_refused(request_id, "capability_id")
        cap = require_step(self.session.principal, capability_id, request_id)
        parsed, trace = self._bind_condition(
            condition_mode=condition_mode, condition=condition,
            condition_patch=condition_patch, request_id=request_id,
        )
        if "tool_failure" in self.session.faults:
            result = failed_result(capability_id, parsed, "注入的工具失败：不得写成完整成功。")
            return self._step_payload(cap.support_status.value, result, trace, capability_id, queries=True)
        if cap.support_status is SupportStatus.NOT_CONNECTED:
            raise not_connected(cap.notes, request_id, capability_id)
        if cap.support_status is SupportStatus.UNSUPPORTED:
            result = unsupported_result(capability_id, parsed, cap.notes)
            return self._step_payload(cap.support_status.value, result, trace, capability_id, queries=False)
        if not executable(cap.support_status):
            raise unsupported_capability(cap.notes, request_id, capability_id)
        result = execute(capability_id, parsed) if execute is not None else fixture_result(capability_id, parsed, cap.support_status)
        if result.completeness.value == "EMPTY":
            self.session.chain_status = "EMPTY"
        return self._step_payload(cap.support_status.value, result, trace, capability_id, queries=True)

    def _step_payload(
        self,
        support_status: str,
        result: CompetitionResultRef | CompetitionComputedResult,
        trace: dict[str, Any],
        capability_id: str,
        *,
        queries: bool,
    ) -> dict[str, Any]:
        record = StepRecord(
            capability_id=capability_id,
            support_status=support_status,
            completeness=result.completeness.value,
            result_id=result.result_id,
            run_id=result.run_id,
            evidence_digest=result.evidence_digest,
            filter_hash=result.resolved_condition.filter_hash,
            inherited_fields=list(trace.get("inherited_fields") or []),
            changed_fields=list(trace.get("changed_fields") or []),
            queries=queries,
            chain_role=capability_id,
        )
        self.session.steps.append(record)
        self.session.last_result = result
        if result.completeness.value == "FAILED":
            self.session.chain_status = "FAILED"
        elif self.session.chain_status not in {"EMPTY", "FAILED", "CANCELLED"}:
            self.session.chain_status = self._chain_status()
        return {
            "schema_version": SCHEMA_VERSION,
            "planner": STUB_PLANNER,
            "live_transport": LIVE_TRANSPORT,
            "support_status": support_status,
            "condition_trace": trace,
            "resolved_condition": result.resolved_condition.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
            "evidence": {
                "result_id": result.result_id,
                "run_id": result.run_id,
                "evidence_digest": result.evidence_digest,
                "filter_hash": result.resolved_condition.filter_hash,
                "completeness": result.completeness.value,
            },
            "chain_status": self.session.chain_status,
            "analysis_complete": self.session.chain_status == "COMPLETE",
            "budget": {
                "used_calls": self.session.budget.used_calls,
                "max_tool_calls": self.session.budget.max_tool_calls,
                "remaining": self.session.budget.remaining(),
            },
            "limitations": list(result.limitations),
        }

    def _planned_capability(self, role: str, condition: CompetitionCondition) -> str | None:
        if role == "diag.comparison":
            return COMPARISON_BY_MODE[condition.comparison_mode.value]
        if role == "diag.sample":
            return SAMPLE_BY_MODE[condition.sample_mode.value]
        return role

    def run_chain(
        self,
        *,
        request_id: str,
        condition: dict[str, Any],
        stop_on_empty: bool = True,
    ) -> dict[str, Any]:
        first = self.run_step(
            capability_id="diag.gsv", condition_mode="EXPLICIT",
            condition=condition, request_id=f"{request_id}:diag.gsv",
        )
        parsed = CompetitionCondition.model_validate(self.session.prior_condition)
        if stop_on_empty and is_empty_mtd(parsed):
            return self._chain_summary(first)
        for role in DIAGNOSIS_CHAIN[1:]:
            cap_id = self._planned_capability(role, parsed)
            if cap_id is None:
                continue
            try:
                self.run_step(
                    capability_id=cap_id, condition_mode="INHERIT",
                    request_id=f"{request_id}:{cap_id}",
                )
            except DiagnosisFault as fault:
                if fault.error.code in {"UNSUPPORTED_CAPABILITY", "NOT_CONNECTED", "FORBIDDEN"}:
                    self.session.steps.append(StepRecord(
                        capability_id=cap_id,
                        support_status="REFUSED",
                        completeness=None,
                        result_id=None,
                        run_id=None,
                        evidence_digest=None,
                        filter_hash=None,
                        inherited_fields=list(INHERITABLE_FIELDS),
                        changed_fields=[],
                        queries=False,
                        chain_role=role,
                    ))
                    continue
                raise
        self.session.chain_status = self._chain_status()
        return self._chain_summary(first)

    def _chain_status(self) -> Literal["COMPLETE", "PARTIAL", "EMPTY", "FAILED", "CANCELLED"]:
        if self.session.budget.cancelled:
            return "CANCELLED"
        if any(item.completeness == "FAILED" for item in self.session.steps):
            return "FAILED"
        if any(item.completeness == "EMPTY" and item.capability_id == "diag.gsv" for item in self.session.steps):
            return "EMPTY"
        succeeded = {
            item.capability_id for item in self.session.steps
            if item.completeness == "COMPLETE"
        }
        comparison_ok = bool(succeeded & set(COMPARISON_BY_MODE.values()))
        required_ok = True
        for role in REQUIRED_FOR_COMPLETE_CHAIN:
            if role == "diag.comparison":
                required_ok = required_ok and comparison_ok
            elif role not in succeeded:
                required_ok = False
        if required_ok:
            return "COMPLETE"
        return "PARTIAL"

    def _chain_summary(self, first: dict[str, Any]) -> dict[str, Any]:
        status = self._chain_status()
        self.session.chain_status = status
        return {
            "schema_version": SCHEMA_VERSION,
            "planner": STUB_PLANNER,
            "live_transport": LIVE_TRANSPORT,
            "chain_status": status,
            "analysis_complete": status == "COMPLETE",
            "completed_steps": [item.__dict__ for item in self.session.steps],
            "first_step": first,
            "budget": {
                "used_calls": self.session.budget.used_calls,
                "max_tool_calls": self.session.budget.max_tool_calls,
                "remaining": self.session.budget.remaining(),
            },
            "limitations": [
                "完整链需要固定 cohort 与未回购计算；C0 中二者为 UNSUPPORTED，因此离线链为 PARTIAL。",
                "不得把部分完成写成完整诊断。",
            ],
        }

    def plan_selected_patch(
        self,
        *,
        intent: str,
        payload: dict[str, Any],
        selection: dict[str, Any],
        request_id: str,
    ) -> dict[str, Any]:
        self._charge(request_id)
        if "dashboard:update" not in self.session.principal.capabilities:
            raise forbidden("当前身份无权生成驾驶舱补丁。", request_id, "intent")
        planned = plan_patch(
            intent=intent,
            payload=payload,
            selection=selection,
            in_flight=self.session.in_flight_patch,
            request_id=request_id,
        )
        if self.session.in_flight_patch is None:
            self.session.in_flight_patch = dict(planned["in_flight_target"])
            self.session.in_flight_patch["attempt_id"] = planned["patch"]["attempt_id"]
        return planned
