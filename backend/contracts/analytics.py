"""Versioned B0 run-kernel contracts, not the complete analytics product API.

Only a code-generated STUB result is supported by this checkpoint. Business
filters, saved assets, arbitrary SQL and model-supplied facts are not accepted.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

ANALYTICS_RUN_SCHEMA = "analytics-run-b0/v1"
OpaqueId = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")]


class AnalyticsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class AnalyticsRunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    NEEDS_INPUT = "NEEDS_INPUT"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class AnalyticsRunPhase(StrEnum):
    ACCEPTED = "ACCEPTED"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    FINALIZING = "FINALIZING"


class AnalyticsConversationRequest(AnalyticsModel):
    title: Annotated[str, Field(min_length=1, max_length=120)] = "B0 合成任务"

    @field_validator("title")
    @classmethod
    def nonblank_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be blank")
        return value.strip()


class AnalyticsConversation(AnalyticsModel):
    schema_version: Literal["analytics-run-b0/v1"] = ANALYTICS_RUN_SCHEMA
    conversation_id: OpaqueId
    version: Annotated[int, Field(strict=True, ge=1)] = 1
    title: str
    created_at: AwareDatetime
    run_ids: list[OpaqueId] = Field(default_factory=list)


class AnalyticsRunRequest(AnalyticsModel):
    schema_version: Literal["analytics-run-b0/v1"] = ANALYTICS_RUN_SCHEMA
    question: Annotated[str, Field(min_length=1, max_length=8000)]
    parent_run_id: OpaqueId | None = None
    # Reject unsupported filtering rather than silently dropping it. The full
    # FilterSpec remains a separate, unimplemented B1 contract.
    condition_patch: None = None

    @field_validator("question")
    @classmethod
    def nonblank_question(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("question must be nonblank text without NUL")
        return value.strip()


class AnalyticsCancelRequest(AnalyticsModel):
    reason: Literal["USER_REQUEST"] = "USER_REQUEST"


class AnalyticsRunAccepted(AnalyticsModel):
    schema_version: Literal["analytics-run-b0/v1"] = ANALYTICS_RUN_SCHEMA
    run_id: OpaqueId
    version: Literal[1] = 1
    status: Literal["QUEUED"] = "QUEUED"
    phase: Literal["ACCEPTED"] = "ACCEPTED"
    location: str


class AnalyticsB0Facts(AnalyticsModel):
    customers: Literal[100] = 100
    repeat_customers: Literal[25] = 25
    repeat_ratio: Annotated[float, Field(strict=True, ge=0, le=1, json_schema_extra={"const": 0.25})] = 0.25

    @field_validator("customers", "repeat_customers", mode="before")
    @classmethod
    def integer_fixture_count(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("fixture counts must be integers")
        return value

    @field_validator("repeat_ratio")
    @classmethod
    def fixed_fixture_ratio(cls, value: float) -> float:
        if value != 0.25:
            raise ValueError("B0 only accepts the registered fixture")
        return value


class AnalyticsB0Result(AnalyticsModel):
    schema_version: Literal["analytics-run-b0/v1"] = ANALYTICS_RUN_SCHEMA
    answer_mode: Literal["STUB"] = "STUB"
    fixture_id: Literal["b0-channel-repeat-2026-09-01"] = "b0-channel-repeat-2026-09-01"
    contains_real_data: Literal[False] = False
    data_source: Literal["SYNTHETIC_FIXTURE"] = "SYNTHETIC_FIXTURE"
    data_as_of: Literal["2026-09-01"] = "2026-09-01"
    facts: AnalyticsB0Facts

    @field_validator("contains_real_data", mode="before")
    @classmethod
    def explicit_synthetic_flag(cls, value: object) -> object:
        if value is not False:
            raise ValueError("B0 requires an explicit false real-data flag")
        return value


class AnalyticsRunDiagnostics(AnalyticsModel):
    attempt_id: OpaqueId
    runtime_status: Literal["PENDING", "DISPATCHING", "ACCEPTED", "UNKNOWN", "EXITED"]
    execution_active: bool
    tool_steps_used: Annotated[int, Field(strict=True, ge=0, le=8)]
    dispatch_attempts: Annotated[int, Field(strict=True, ge=0, le=3)]
    profile_version: str
    profile_hash: str
    error_code: str | None = None


class AnalyticsRunSnapshot(AnalyticsModel):
    schema_version: Literal["analytics-run-b0/v1"] = ANALYTICS_RUN_SCHEMA
    run_id: OpaqueId
    version: Annotated[int, Field(strict=True, ge=1)]
    source_kind: Literal["CHAT"] = "CHAT"
    source_ref: OpaqueId
    conversation_id: OpaqueId
    parent_run_id: OpaqueId | None
    status: AnalyticsRunStatus
    phase: AnalyticsRunPhase
    created_at: AwareDatetime
    updated_at: AwareDatetime
    deadline: AwareDatetime
    answer_mode: Literal["STUB"] = "STUB"
    result: AnalyticsB0Result | None
    evidence_digest: str | None
    primary_result_ref: OpaqueId | None
    evidence_refs: list[OpaqueId]
    last_sequence: Annotated[int, Field(strict=True, ge=0)]
    diagnostics: AnalyticsRunDiagnostics
    limitations: list[str] = Field(default_factory=lambda: [
        "仅 B0 任务合同与固定合成 fixture；不是业务问数、真实模型或完整 B0 验收。",
    ])


class AnalyticsEventPayload(AnalyticsModel):
    status: AnalyticsRunStatus
    phase: AnalyticsRunPhase
    version: Annotated[int, Field(strict=True, ge=1)]
    step_id: OpaqueId | None = None


class AnalyticsRunEvent(AnalyticsModel):
    event_id: str
    run_id: OpaqueId
    sequence: Annotated[int, Field(strict=True, ge=1)]
    type: Literal[
        "run.updated", "run.started", "tool.started", "tool.completed",
        "run.needs_input", "run.completed", "run.failed", "run.cancelled",
    ]
    occurred_at: AwareDatetime
    payload: AnalyticsEventPayload


class AnalyticsErrorDetail(AnalyticsModel):
    code: str
    message: str
    retryable: bool
    request_id: str
    recovery_url: str | None = None


class AnalyticsErrorResponse(AnalyticsModel):
    error: AnalyticsErrorDetail
