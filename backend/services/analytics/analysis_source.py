"""Resolve a SUCCEEDED channel run from RunStore for saved-analysis HTTP.

Not a public register_succeeded_run adapter. Callers never pass client facts.
"""

from __future__ import annotations

from backend.contracts.analytics_query_run import QUERY_RUN_FAMILY
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, require
from backend.services.analytics.jobs import RunStore
from backend.services.analytics.saved_analyses import CAPABILITY_SAVE, DATA_SCOPE


def resolve_trusted_succeeded_run(run_store: RunStore, principal: AnalyticsPrincipal, run_id: str) -> dict:
    require(principal, CAPABILITY_SAVE, data_scope=DATA_SCOPE)
    if run_store.family != QUERY_RUN_FAMILY:
        raise AnalyticsError(409, "FAMILY_MISMATCH", "任务合同与当前实例不一致。")
    trusted = run_store.query_succeeded_source(principal, run_id)
    if trusted.get("owner_id") != principal.actor_id:
        raise AnalyticsError(404, "NOT_FOUND", "任务不存在或当前身份不可见。")
    return trusted
