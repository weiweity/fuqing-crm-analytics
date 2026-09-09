"""Shared synthetic C0 projection of a trusted saved analysis version."""

import re
from typing import Any


def competition_result_item(record) -> dict[str, Any]:
    """C0 endorsable pointer from a saved SNAPSHOT. Not a B0 /b0/assets document."""
    if record.schema_version == "competition-computed-analysis/v1":
        from backend.contracts.competition_computed import CompetitionComputedResult
        return CompetitionComputedResult.model_validate(record.snapshot["computed_result"]).model_dump(mode="json")
    binding = record.binding()
    snapshot = record.snapshot if isinstance(record.snapshot, dict) else {}
    as_of = snapshot.get("as_of") or "2026-08-31T16:00:00.000000+00:00"
    run_id = binding.get("run_id") or snapshot.get("run_id")
    analysis_id = binding.get("analysis_id")
    digest = binding.get("evidence_digest") or snapshot.get("evidence_digest")
    result_id = f"result_{str(run_id or analysis_id or 'synth')[4:]}"
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", result_id or ""):
        result_id = f"result_{str(analysis_id or 'synth')}"
    return {
        "schema_version": "competition-result/v1",
        "result_id": result_id,
        "run_id": run_id,
        "analysis_id": analysis_id,
        "evidence_digest": digest,
        "completeness": "COMPLETE",
        "contains_real_data": False,
        "data_mode": "SNAPSHOT",
        "query_id": record.query_ref.get("query_id") if isinstance(record.query_ref, dict) else "channel_first_observed_followup",
        "query_version": record.query_ref.get("query_version") if isinstance(record.query_ref, dict) else "channel-followup-query/v1",
        "metric_id": "gsv",
        "metric_version": "competition-metrics/v1",
        "existing_result_schema": "analytics-channel-followup/v1",
        "facts_schema_ref": "backend.contracts.analytics_query.ChannelFollowupResult",
        "primary_result_ref": result_id,
        "empty_reason": None,
        "limitations": list(record.limitations) or ["合成 SNAPSHOT，不是真实经营结论。"],
        "row_count": 1,
        "page": {
            "checksum": digest,
            "complete": True,
            "limit": 50,
            "offset": 0,
            "total": 1,
        },
        "resolved_condition": {
            "metric_type": "GSV",
            "timezone": "Asia/Shanghai",
            "as_of": as_of,
            "comparison_mode": "YOY_SAME_PERIOD",
            "current_period": {"start_date": "2026-08-01", "end_date": "2026-08-31", "end_bound": "INCLUSIVE_CALENDAR_DAY"},
            "comparison_period": {"start_date": "2025-08-01", "end_date": "2025-08-31", "end_bound": "INCLUSIVE_CALENDAR_DAY"},
            "cutoff": "2026-07-31",
            "sample_mode": "EXCLUDE_CURRENT_SALES_ONLY",
            "data_version": "synthetic-c0-demo-data/v1",
            "rule_version": "competition-condition-rule/v1",
            "source_tense": "PUBLISHED_SNAPSHOT",
            "history_scope": {"channel_ids": [], "kind": "ALL", "product_ids": []},
            "sales_scope": {"channel_ids": [], "kind": "ALL", "product_ids": []},
            "unknown_flags": [],
        },
        "http_api": "CONNECTED",
        "finite_mock": True,
    }
