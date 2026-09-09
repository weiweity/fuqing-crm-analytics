"""Resolve a SUCCEEDED channel run from RunStore for saved-analysis HTTP.

Not a public register_succeeded_run adapter. Callers never pass client facts.
"""

from __future__ import annotations

from pydantic import ValidationError

from backend.contracts.analytics_query_run import QUERY_RUN_FAMILY
from backend.contracts.competition_c0 import EndorsedResultRef
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, require
from backend.services.analytics.jobs import RunStore
from backend.services.analytics.saved_analyses import CAPABILITY_SAVE, DATA_SCOPE, SavedAnalysisStore


def resolve_trusted_succeeded_run(run_store: RunStore, principal: AnalyticsPrincipal, run_id: str) -> dict:
    require(principal, CAPABILITY_SAVE, data_scope=DATA_SCOPE)
    if run_store.family != QUERY_RUN_FAMILY:
        raise AnalyticsError(409, "FAMILY_MISMATCH", "任务合同与当前实例不一致。")
    trusted = run_store.query_succeeded_source(principal, run_id)
    if trusted.get("owner_id") != principal.actor_id:
        raise AnalyticsError(404, "NOT_FOUND", "任务不存在或当前身份不可见。")
    return trusted


def resolve_endorsed_result(
    analysis_store: SavedAnalysisStore, principal: AnalyticsPrincipal, ref: EndorsedResultRef | dict,
) -> dict:
    """Bind a COMPLETE saved SNAPSHOT as a shared result pointer. No recompute."""
    try:
        parsed = ref if isinstance(ref, EndorsedResultRef) else EndorsedResultRef.model_validate(ref)
    except ValidationError:
        raise AnalyticsError(422, "UNPROCESSABLE", "认可结果引用不符合 competition-c0 合同。") from None
    if parsed.analysis_id is not None:
        record = analysis_store.get(principal, parsed.analysis_id)
    else:
        record = analysis_store.find_latest_for_run(principal, parsed.run_id)
        if record is None:
            raise AnalyticsError(404, "NOT_FOUND", "分析不存在或当前身份不可见。")
    snapshot = record.snapshot
    if snapshot.get("run_id") != parsed.run_id:
        raise AnalyticsError(409, "BINDING_CORRUPT", "认可结果与冻结来源 run_id 不一致。")
    if snapshot.get("evidence_digest") != parsed.evidence_digest:
        raise AnalyticsError(409, "BINDING_CORRUPT", "认可结果与冻结 evidence_digest 不一致。")
    if record.created_from_run_id != parsed.run_id:
        raise AnalyticsError(409, "BINDING_CORRUPT", "认可结果与保存分析的 SNAPSHOT 不一致。")
    binding = record.binding()
    binding["result_id"] = parsed.result_id
    binding["completeness"] = parsed.completeness
    binding["snapshot"] = dict(snapshot)
    binding["facts"] = dict(record.facts)
    binding["limitations"] = list(record.limitations)
    return binding
