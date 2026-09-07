"""Independent channel-follow-up run-kernel contract.

Schema: analytics-run-channel-followup/v1. Not analytics-run-b0/v1.
This module is store/contract only: empty OpenAPI paths, no HTTP, no worker,
no native adapter, and no SQL. Result payloads reuse G2 ChannelFollowupResult.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator
from pydantic.json_schema import models_json_schema

from backend.contracts.analytics import (
    ANALYTICS_RUN_SCHEMA,
    AnalyticsRunDiagnostics,
    AnalyticsRunPhase,
    AnalyticsRunStatus,
    OpaqueId,
)
from backend.contracts.analytics_query import (
    DATA_VERSION,
    QUERY_SCHEMA,
    SNAPSHOT_ID,
    ChannelFollowupResult,
    Sha256Hex,
    _force_empty_product_ids,
    canonical_rfc3339,
    parse_query_datetime,
)

QUERY_RUN_SCHEMA = "analytics-run-channel-followup/v1"
QUERY_CONTEXT_SCHEMA = "analytics-channel-followup-runtime-context/v1"
QUERY_RECEIPT_SCHEMA = "analytics-run-channel-followup-native-receipt/v1"
QUERY_RUN_FAMILY = "channel_followup"
QUERY_DATA_SCOPE = "channel-followup-fixture"
QUERY_TOOL = "analytics_channel_followup_query"


class AnalyticsQueryRunModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class ChannelFollowupFixtureDescriptor(AnalyticsQueryRunModel):
    snapshot_id: Literal["synthetic-channel-followup-v1"] = SNAPSHOT_ID
    data_version: Literal["synthetic-channel-followup-data/v1"] = DATA_VERSION
    data_digest: Sha256Hex
    as_of: str
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    physical_sha256: Sha256Hex

    @field_validator("as_of")
    @classmethod
    def canonical_as_of(cls, value: object) -> str:
        return canonical_rfc3339(parse_query_datetime(value))


class ChannelFollowupRunBinding(AnalyticsQueryRunModel):
    family: Literal["channel_followup"] = QUERY_RUN_FAMILY
    method_package_digest: Sha256Hex
    fixture: ChannelFollowupFixtureDescriptor
    permission_scope: Sha256Hex


class AnalyticsQueryConversationRequest(AnalyticsQueryRunModel):
    title: Annotated[str, Field(min_length=1, max_length=120)] = "渠道后续购买查询"

    @field_validator("title")
    @classmethod
    def nonblank_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be blank")
        return value.strip()


class AnalyticsQueryConversation(AnalyticsQueryRunModel):
    schema_version: Literal["analytics-run-channel-followup/v1"] = QUERY_RUN_SCHEMA
    conversation_id: OpaqueId
    version: Annotated[int, Field(strict=True, ge=1)] = 1
    title: str
    created_at: AwareDatetime
    run_ids: list[OpaqueId] = Field(default_factory=list)


class AnalyticsQueryRunRequest(AnalyticsQueryRunModel):
    schema_version: Literal["analytics-run-channel-followup/v1"] = QUERY_RUN_SCHEMA
    question: Annotated[str, Field(min_length=1, max_length=8000)]
    parent_run_id: OpaqueId | None = None
    condition_patch: None = None

    @field_validator("question")
    @classmethod
    def nonblank_question(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("question must be nonblank text without NUL")
        return value.strip()


class AnalyticsQueryRunAccepted(AnalyticsQueryRunModel):
    schema_version: Literal["analytics-run-channel-followup/v1"] = QUERY_RUN_SCHEMA
    run_id: OpaqueId
    version: Literal[1] = 1
    status: Literal["QUEUED"] = "QUEUED"
    phase: Literal["ACCEPTED"] = "ACCEPTED"
    location: str


class AnalyticsQueryRunSnapshot(AnalyticsQueryRunModel):
    schema_version: Literal["analytics-run-channel-followup/v1"] = QUERY_RUN_SCHEMA
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
    answer_mode: Literal["DETERMINISTIC_TOOL"] = "DETERMINISTIC_TOOL"
    result: ChannelFollowupResult | None
    evidence_digest: str | None
    primary_result_ref: OpaqueId | None
    evidence_refs: list[OpaqueId]
    last_sequence: Annotated[int, Field(strict=True, ge=0)]
    diagnostics: AnalyticsRunDiagnostics
    limitations: list[str] = Field(default_factory=lambda: [
        "synthetic 候选查询任务与冻结绑定；contains_real_data 为 false，不是真实业务数据。",
    ])


class AnalyticsQueryEventPayload(AnalyticsQueryRunModel):
    status: AnalyticsRunStatus
    phase: AnalyticsRunPhase
    version: Annotated[int, Field(strict=True, ge=1)]
    step_id: OpaqueId | None = None


class AnalyticsQueryRunEvent(AnalyticsQueryRunModel):
    event_id: str
    run_id: OpaqueId
    sequence: Annotated[int, Field(strict=True, ge=1)]
    type: Literal[
        "run.updated", "run.started", "tool.started", "tool.completed",
        "run.needs_input", "run.completed", "run.failed", "run.cancelled",
    ]
    occurred_at: AwareDatetime
    payload: AnalyticsQueryEventPayload


class AnalyticsQueryNativeText(AnalyticsQueryRunModel):
    type: Literal["text"]
    text: Annotated[str, Field(min_length=1, max_length=8000)]

    @field_validator("text")
    @classmethod
    def supported_text(cls, value: str) -> str:
        AnalyticsQueryRunRequest(question=value)
        return value


class AnalyticsQueryNativePrompt(AnalyticsQueryRunModel):
    requestId: OpaqueId
    sessionId: OpaqueId
    mode: Literal["queue"]
    content: Annotated[list[AnalyticsQueryNativeText], Field(min_length=1, max_length=1)]
    clientTimeZone: Literal["UTC", "Asia/Shanghai"] = "Asia/Shanghai"


class AnalyticsQueryNativeReceipt(AnalyticsQueryRunModel):
    schema_version: Literal["analytics-run-channel-followup-native-receipt/v1"] = QUERY_RECEIPT_SCHEMA
    run_id: OpaqueId
    attempt_id: OpaqueId
    step_id: OpaqueId
    disposition: Literal["EXECUTE", "REUSE_RESULT"]
    result: ChannelFollowupResult


OPENAPI_MODELS = (
    ChannelFollowupFixtureDescriptor,
    ChannelFollowupRunBinding,
    AnalyticsQueryConversationRequest,
    AnalyticsQueryConversation,
    AnalyticsQueryRunRequest,
    AnalyticsQueryRunAccepted,
    AnalyticsQueryRunSnapshot,
    AnalyticsQueryEventPayload,
    AnalyticsQueryRunEvent,
    AnalyticsQueryNativeReceipt,
    ChannelFollowupResult,
)


def query_run_contract_openapi() -> dict:
    """OpenAPI 3.1 document with components only. Not a callable HTTP API."""
    keyed, document = models_json_schema(
        [(model, "validation") for model in OPENAPI_MODELS],
        ref_template="#/components/schemas/{model}",
    )
    definitions = dict(document.get("$defs", {}))
    for (model, _mode), item in keyed.items():
        definitions.setdefault(model.__name__, item)
    schema = {
        "openapi": "3.1.0",
        "info": {
            "title": "analytics-run-channel-followup/v1 store contract",
            "description": (
                "Offline schema for the synthetic channel-follow-up run store. "
                "paths is empty: this unit does not implement a callable HTTP API. "
                "ChannelFollowupResult keeps the G2 query-contract integer and "
                "timestamp conventions. Run identity, version, sequence, and "
                "shared diagnostics reuse the existing B0 field shapes and are "
                "not a second copy of those G2 wire rules."
            ),
            "version": QUERY_RUN_SCHEMA,
        },
        "paths": {},
        "components": {"schemas": definitions},
        "x-not-an-http-api": True,
        "x-store-only": True,
        "x-query-run-schema": QUERY_RUN_SCHEMA,
        "x-query-result-schema": QUERY_SCHEMA,
        "x-b0-run-schema-untouched": ANALYTICS_RUN_SCHEMA,
    }
    _force_empty_product_ids(schema)
    return schema
