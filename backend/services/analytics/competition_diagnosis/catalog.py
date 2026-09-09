"""Actor-filtered C0 capability catalog. Backend still re-checks."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from backend.contracts.competition_c0 import SUPPORT_MATRIX, CompetitionCapability, SupportStatus
from backend.services.analytics.access import AnalyticsPrincipal
from backend.services.analytics.competition_diagnosis.chain import (
    STEP_CAPABILITIES,
)
from backend.services.analytics.competition_diagnosis.errors import (
    forbidden,
    unsupported_capability,
)


@lru_cache(maxsize=1)
def support_matrix() -> tuple[CompetitionCapability, ...]:
    return SUPPORT_MATRIX


def capability_by_id(capability_id: str) -> CompetitionCapability | None:
    for item in support_matrix():
        if item.capability_id == capability_id:
            return item
    return None


def actor_allows(principal: AnalyticsPrincipal, required: list[str]) -> bool:
    return all(item in principal.capabilities for item in required)


def visible_capabilities(principal: AnalyticsPrincipal) -> list[dict[str, Any]]:
    rows = []
    for item in support_matrix():
        if not actor_allows(principal, list(item.required_capabilities)):
            continue
        rows.append(item.model_dump(mode="json"))
    return rows


def require_step(principal: AnalyticsPrincipal, capability_id: str, request_id: str) -> CompetitionCapability:
    if capability_id not in STEP_CAPABILITIES:
        raise unsupported_capability(
            "未登记的诊断能力，不能调用旧路由或任意工具。",
            request_id, "capability_id",
        )
    item = capability_by_id(capability_id)
    if item is None:
        raise unsupported_capability("能力目录无此项。", request_id, "capability_id")
    if not actor_allows(principal, list(item.required_capabilities)):
        raise forbidden("当前身份无权调用该能力；后端仍拒绝。", request_id, "capability_id")
    return item


def executable(status: SupportStatus) -> bool:
    return status in {SupportStatus.SUPPORTED, SupportStatus.PARTIAL}
