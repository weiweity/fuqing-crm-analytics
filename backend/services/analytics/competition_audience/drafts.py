"""Action drafts: owner/budget/reviewer/review date/control/stop/unknowns; never auto-send."""

from __future__ import annotations

from datetime import date

from backend.contracts.competition_c0 import (
    CompetitionActionDraft,
    CompetitionCandidateSet,
    DraftStatus,
)

DRAFT_LIMITATIONS = (
    "GSV 下降不等于投放回报低；缺成本时只给试验优先级。",
    "行动草稿不得自动发送；不是 Mission DRAFT_EXPORT。",
)

DEFAULT_UNKNOWNS = (
    "MEMBER_HISTORY",
    "SAMPLE_CHANNEL_SET",
    "incremental_roi",
)


def required_unknowns(payload: dict) -> list[str]:
    unknowns = [str(item) for item in payload.get("unknowns") or []]
    ordered: list[str] = []
    for item in (*DEFAULT_UNKNOWNS, *unknowns):
        if item not in ordered:
            ordered.append(item)
    if payload.get("reviewer_id") in (None, ""):
        _append(ordered, "reviewer_id")
    if payload.get("review_by") in (None, ""):
        _append(ordered, "review_by")
    if payload.get("budget_cap_minor") is None:
        _append(ordered, "budget_cap_minor")
    if payload.get("control_design") in (None, ""):
        _append(ordered, "control_design")
    if payload.get("stop_condition") in (None, ""):
        _append(ordered, "stop_condition")
    return ordered


def _append(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def build_draft(
    *,
    draft_id: str,
    version: int,
    candidates: CompetitionCandidateSet,
    owner_id: str,
    payload: dict,
    status: DraftStatus = DraftStatus.DRAFT,
    expired_reason: str | None = None,
    copy_only_change: bool = False,
) -> CompetitionActionDraft:
    if payload.get("auto_send") not in (None, False):
        raise ValueError("action drafts cannot auto-send")
    review_by = payload.get("review_by")
    if isinstance(review_by, date):
        review_by = review_by.isoformat()
    body = {
        "draft_id": draft_id,
        "version": version,
        "candidate_set_id": candidates.candidate_set_id,
        "source_result_ref": candidates.source_result_ref,
        "status": status.value,
        "owner_id": owner_id,
        "reviewer_id": payload.get("reviewer_id"),
        "review_by": review_by,
        "budget_cap_minor": payload.get("budget_cap_minor"),
        "currency": payload.get("currency") or "CNY",
        "channel": payload.get("channel"),
        "product_id": payload.get("product_id"),
        "control_design": payload.get("control_design"),
        "stop_condition": payload.get("stop_condition"),
        "unknowns": required_unknowns(payload),
        "auto_send": False,
        "expired_reason": expired_reason,
        "copy_only_change": copy_only_change and expired_reason is None,
        "existing_mission_export": "not-mission-draft-export",
        "limitations": list(payload.get("limitations") or DRAFT_LIMITATIONS),
    }
    return CompetitionActionDraft.model_validate(body)


def expire_draft(draft: CompetitionActionDraft, reason: str) -> CompetitionActionDraft:
    return draft.model_copy(update={
        "version": draft.version + 1,
        "status": DraftStatus.EXPIRED,
        "expired_reason": reason,
        "copy_only_change": False,
        "auto_send": False,
    })
