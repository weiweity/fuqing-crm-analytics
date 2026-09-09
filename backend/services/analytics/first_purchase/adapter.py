"""Bound first-purchase execution adapter.

Calls the shipped JSON compute. Does not open DuckDB, catalog, RunStore, or a
native product loop. Offline OK/REJECTED is a compute outcome, not a native pass.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from backend.contracts.analytics_first_purchase import (
    SNAPSHOT_ID,
    FirstPurchaseQueryRequest,
    FirstPurchaseResult,
    FirstPurchaseSnapshot,
    bind_resolved_filters,
    revalidate_model,
    result_to_json,
)
from backend.services.analytics.access import AnalyticsError
from backend.services.analytics.first_purchase.compute import execute_first_purchase_path_query


def frozen_snapshot(snapshot: FirstPurchaseSnapshot | dict[str, Any]) -> FirstPurchaseSnapshot:
    try:
        return revalidate_model(FirstPurchaseSnapshot, snapshot)
    except (ValidationError, ValueError) as error:
        raise AnalyticsError(422, "INVALID_REQUEST", "请求与当前查询合同不匹配，请检查版本、字段和取值。") from error


def frozen_request(request: FirstPurchaseQueryRequest | dict[str, Any]) -> FirstPurchaseQueryRequest:
    try:
        parsed = revalidate_model(FirstPurchaseQueryRequest, request)
    except (ValidationError, ValueError) as error:
        raise AnalyticsError(422, "INVALID_REQUEST", "请求与当前查询合同不匹配，请检查版本、字段和取值。") from error
    if parsed.data_snapshot_ref != SNAPSHOT_ID:
        raise AnalyticsError(422, "INVALID_REQUEST", "请求与当前查询合同不匹配，请检查版本、字段和取值。")
    return parsed


def bound_first_purchase_result(
    *,
    request: FirstPurchaseQueryRequest | dict[str, Any],
    snapshot: FirstPurchaseSnapshot | dict[str, Any],
    permission_scope: str,
) -> dict[str, Any]:
    """Execute the gold JSON transform and re-bind identity. Never invents口径."""
    parsed_request = frozen_request(request)
    parsed_snapshot = frozen_snapshot(snapshot)
    try:
        expected = bind_resolved_filters(parsed_request, parsed_snapshot, permission_scope)
    except (ValidationError, ValueError) as error:
        raise AnalyticsError(422, "INVALID_REQUEST", "请求与当前查询合同不匹配，请检查版本、字段和取值。") from error
    payload = execute_first_purchase_path_query(
        request=parsed_request.model_dump(mode="json"),
        snapshot=parsed_snapshot.model_dump(mode="json"),
        permission_scope=permission_scope,
    )
    try:
        result = FirstPurchaseResult.model_validate(payload)
    except (ValidationError, ValueError) as error:
        raise AnalyticsError(409, "BINDING_CORRUPT", "查询结果绑定已损坏，不能继续。") from error
    if result.filter_hash != expected.filter_hash:
        raise AnalyticsError(409, "BINDING_MISMATCH", "查询结果与冻结条件不一致，不能提交。")
    if result.resolved_filters.model_dump(mode="json") != expected.model_dump(mode="json"):
        raise AnalyticsError(409, "BINDING_MISMATCH", "查询结果与冻结条件不一致，不能提交。")
    if result.resolved_filters.data_digest != expected.data_digest:
        raise AnalyticsError(409, "BINDING_MISMATCH", "查询结果与冻结条件不一致，不能提交。")
    return result_to_json(result)
