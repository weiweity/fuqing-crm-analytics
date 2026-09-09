"""Resolve an authorized frozen first-purchase source through shared RunStore."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


from backend.contracts.analytics_first_purchase import (
    DATA_VERSION,
    METRIC_ID,
    METRIC_VERSION,
    QUERY_ID,
    QUERY_VERSION,
    FirstPurchaseResult,
)
from backend.contracts.analytics_first_purchase_run import FIRST_PURCHASE_DATA_SCOPE, FIRST_PURCHASE_RUN_FAMILY
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, require
from backend.services.analytics.jobs import RunStore

CAPABILITY_SAVE = "analysis:save"
SOURCE_LAYER_LOCAL = "runstore_get_local"
SOURCE_LAYER_SHARED = "runstore_succeeded_source"


@dataclass(frozen=True)
class FirstPurchaseTrustedSource:
    run_id: str
    status: Literal["SUCCEEDED"]
    query_id: str
    query_version: str
    metric_id: str
    metric_version: str
    data_version: str
    filter_hash: str
    evidence_digest: str
    request: dict[str, Any]
    result: dict[str, Any]
    owner_id: str
    primary_result_ref: str | None
    method_package_digest: str | None
    source_layer: Literal["runstore_get_local", "runstore_succeeded_source"]

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "query_id": self.query_id,
            "query_version": self.query_version,
            "metric_id": self.metric_id,
            "metric_version": self.metric_version,
            "data_version": self.data_version,
            "filter_hash": self.filter_hash,
            "evidence_digest": self.evidence_digest,
            "request": dict(self.request),
            "result": dict(self.result),
            "owner_id": self.owner_id,
            "primary_result_ref": self.primary_result_ref,
            "method_package_digest": self.method_package_digest,
            "source_layer": self.source_layer,
        }


def _unprocessable(message: str) -> AnalyticsError:
    return AnalyticsError(422, "UNPROCESSABLE", message)


def _validate_operating_result(result: FirstPurchaseResult) -> None:
    if result.query_id != QUERY_ID or result.query_version != QUERY_VERSION:
        raise _unprocessable("本波只允许 first_purchase_product_path / first-purchase-path-query/v1。")
    if result.metric_id != METRIC_ID or result.metric_version != METRIC_VERSION:
        raise _unprocessable("指标版本与本波合同不一致。")
    if result.data_version != DATA_VERSION:
        raise _unprocessable("数据版本与本波合同不一致。")
    if result.status != "OK" or result.facts is None:
        raise _unprocessable("SUCCEEDED 但结果 REJECTED 或 facts 为空，不能保存为有效经营分析。")


def resolve_trusted_first_purchase_source(
    run_store: RunStore, principal: AnalyticsPrincipal, run_id: str,
) -> FirstPurchaseTrustedSource:
    """Read the authorized frozen step, result and method from the shared kernel."""
    require(principal, CAPABILITY_SAVE, data_scope=FIRST_PURCHASE_DATA_SCOPE)
    if run_store.family != FIRST_PURCHASE_RUN_FAMILY:
        raise AnalyticsError(409, "FAMILY_MISMATCH", "任务合同与当前实例不一致。")
    source = run_store.succeeded_operating_source(principal, run_id)
    if source["owner_id"] != principal.actor_id:
        raise AnalyticsError(404, "NOT_FOUND", "任务不存在或当前身份不可见。")
    _validate_operating_result(FirstPurchaseResult.model_validate(source["result"]))
    return FirstPurchaseTrustedSource(**source, source_layer=SOURCE_LAYER_SHARED)
