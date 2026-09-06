"""Public-demo Mission API contracts.

These contracts deliberately expose decisions and evidence, never arbitrary SQL or
private CRM fields.  Every response is labelled with synthetic-data provenance.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


MissionStatus = Literal["AWAITING_APPROVAL", "APPROVED", "WAITING_MEASUREMENT"]


class DiagnoseRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=300)


class ApprovalRequest(BaseModel):
    decision: Literal["APPROVE"] = "APPROVE"
    note: str | None = Field(default=None, max_length=500)


class ExportResponse(BaseModel):
    mission_id: str
    mission_status: Literal["WAITING_MEASUREMENT"]
    mission_version: int
    export_id: str
    export_status: Literal["DRAFT_EXPORT_READY"]
    row_count: int
    experiment_count: int
    holdout_count: int
    sha256: str
    download_url: str
    expires_at: None = None
    data_provenance: dict[str, Any]


class MissionResponse(BaseModel):
    mission_id: str
    status: MissionStatus
    version: int
    title: str
    executive_summary: str
    recommendation: str
    decision: dict[str, Any]
    channel_metrics: list[dict[str, Any]]
    target_audience: dict[str, Any]
    economics: dict[str, Any]
    evidence: list[dict[str, Any]]
    state_timeline: list[dict[str, Any]]
    approval: dict[str, Any] | None = None
    latest_export: ExportResponse | None = None
    demo_controls: dict[str, bool] = Field(
        default_factory=lambda: {"reset_enabled": False}
    )
    data_provenance: dict[str, Any]


class DiagnoseResponse(BaseModel):
    question: str
    intent: str
    answer_mode: Literal["DETERMINISTIC_TOOL"]
    answer: str
    evidence: list[dict[str, Any]]
    limitations: list[str]
    data_provenance: dict[str, Any]
