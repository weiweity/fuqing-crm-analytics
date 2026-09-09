"""First-purchase types for the shared kernel, not the retired local ledger."""
from typing import Literal, Annotated
from pydantic import model_validator, Field
from backend.contracts.analytics import AnalyticsRunStatus, OpaqueId
from backend.contracts.analytics_query_run import (
    AnalyticsQueryNativePrompt, AnalyticsQueryRunModel, AnalyticsQueryConversationRequest,
    AnalyticsQueryConversation, AnalyticsQueryRunRequest, AnalyticsQueryRunAccepted,
    AnalyticsQueryRunSnapshot,
)
from backend.contracts.analytics_first_purchase import (
    FirstPurchaseSnapshot, FirstPurchaseResult, snapshot_digest, canonical_rfc3339, Sha256Hex,
)

RUN_SCHEMA = "analytics-run-first-purchase-path/v1"
FIRST_PURCHASE_CONTEXT_SCHEMA = "analytics-first-purchase-runtime-context/v1"
FIRST_PURCHASE_RECEIPT_SCHEMA = "analytics-run-first-purchase-native-receipt/v1"

class FirstPurchaseFixtureDescriptor(AnalyticsQueryRunModel):
    snapshot: FirstPurchaseSnapshot
    data_digest: Sha256Hex

    @model_validator(mode="after")
    def verify_digest(self):
        if self.data_digest != snapshot_digest(self.snapshot):
            raise ValueError("first-purchase snapshot digest mismatch")
        return self

    @property
    def snapshot_id(self):
        return self.snapshot.snapshot_id

    @property
    def data_version(self):
        return self.snapshot.data_version

    @property
    def as_of(self):
        return canonical_rfc3339(self.snapshot.as_of)

    @property
    def timezone(self):
        return self.snapshot.timezone

class FirstPurchaseKernelBinding(AnalyticsQueryRunModel):
    family: Literal["first_purchase"] = "first_purchase"
    method_package_digest: Sha256Hex
    fixture: FirstPurchaseFixtureDescriptor
    permission_scope: Sha256Hex

class FirstPurchaseConversationRequest(AnalyticsQueryConversationRequest):
    title: Annotated[str, Field(min_length=1, max_length=120)] = "首购商品查询"

class FirstPurchaseConversation(AnalyticsQueryConversation):
    schema_version: Literal["analytics-run-first-purchase-path/v1"] = RUN_SCHEMA

class FirstPurchaseKernelRequest(AnalyticsQueryRunRequest):
    schema_version: Literal["analytics-run-first-purchase-path/v1"] = RUN_SCHEMA

class FirstPurchaseAccepted(AnalyticsQueryRunAccepted):
    schema_version: Literal["analytics-run-first-purchase-path/v1"] = RUN_SCHEMA

class FirstPurchaseKernelSnapshot(AnalyticsQueryRunSnapshot):
    schema_version: Literal["analytics-run-first-purchase-path/v1"] = RUN_SCHEMA
    result: FirstPurchaseResult | None


class FirstPurchaseNativePrompt(AnalyticsQueryNativePrompt):
    """Same native prompt wire as channel query; family is chosen by the store."""


class FirstPurchaseNativeReceipt(AnalyticsQueryRunModel):
    schema_version: Literal["analytics-run-first-purchase-native-receipt/v1"] = FIRST_PURCHASE_RECEIPT_SCHEMA
    run_id: OpaqueId
    request_id: OpaqueId
    call_id: OpaqueId
    attempt_id: OpaqueId
    step_id: OpaqueId | None = None
    disposition: Literal["EXECUTE", "REUSE_RESULT", "IN_FLIGHT"]
    run_status: AnalyticsRunStatus
    result: FirstPurchaseResult | None = None

    @model_validator(mode="after")
    def bind_result_to_disposition(self):
        if self.disposition == "IN_FLIGHT":
            if self.result is not None or self.step_id is not None:
                raise ValueError("in-flight native receipt cannot include a result")
            if self.run_status not in {"QUEUED", "RUNNING", "CANCELLING", "UNKNOWN"}:
                raise ValueError("in-flight native receipt requires a non-terminal run")
            return self
        if self.result is None or self.step_id is None:
            raise ValueError("completed native receipt requires a first-purchase result")
        if self.run_status not in {"RUNNING", "SUCCEEDED"}:
            raise ValueError("completed native receipt requires a live or succeeded run")
        return self
