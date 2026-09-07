"""Offline deterministic channel-follow-up compute. No HTTP or native.

The caller must pass an already restricted read-only DuckDB connection and
close it. Shared worker child reuses this on a leased connection. This module
never opens the legacy Web singleton and does not schedule execution. Source
validation is required before the fixed SQL runs.
"""

from __future__ import annotations

from backend.analytics_query_fixture import (
    ChannelFollowupFixture,
    require_restricted_connection,
    verify_sealed_content,
)
from backend.contracts.analytics_query import (
    ChannelFollowupChannelRow,
    ChannelFollowupCounts,
    ChannelFollowupFacts,
    ChannelFollowupQueryRequest,
    ChannelFollowupResult,
    DISPLAY_NAME,
    revalidate_model,
)
from backend.semantic.analytics_channel_followup import (
    LIMITATIONS,
    channel_followup_query,
    channel_followup_query_parameters,
)
from backend.services.analytics.catalog import bind_resolved_filters, require_supported_query


def _count_block(mature: int, immature: int, repeat: int, cross: int, net) -> dict:
    if mature == 0:
        return {
            "channel_mature_cohort_count": mature,
            "channel_immature_count": immature,
            "channel_repeat_count": repeat,
            "channel_cross_channel_count": cross,
            "channel_repeat_ratio": None,
            "channel_cross_channel_ratio": None,
            "channel_window_net_paid_minor": None,
            "channel_empty_reason": "EMPTY_MATURE_COHORT",
        }
    if net is None:
        raise ValueError("non-empty mature cohort net paid is required")
    return {
        "channel_mature_cohort_count": mature,
        "channel_immature_count": immature,
        "channel_repeat_count": repeat,
        "channel_cross_channel_count": cross,
        "channel_repeat_ratio": repeat / mature,
        "channel_cross_channel_ratio": cross / mature,
        "channel_window_net_paid_minor": int(net),
        "channel_empty_reason": None,
    }


def execute_channel_followup_query(
    *,
    request: ChannelFollowupQueryRequest | dict,
    permission_scope: str,
    fixture: ChannelFollowupFixture,
    connection,
) -> ChannelFollowupResult:
    """Execute the sealed snapshot query. Does not close the caller connection."""
    request = revalidate_model(ChannelFollowupQueryRequest, request)
    require_supported_query(request.query_id)
    require_restricted_connection(connection)
    before = fixture.physical_sha256()
    snapshot = verify_sealed_content(connection, fixture)
    resolved = bind_resolved_filters(request, snapshot, permission_scope)
    sql, _order = channel_followup_query()
    rows = connection.execute(sql, channel_followup_query_parameters(resolved)).fetchall()
    if len(rows) != len(resolved.channel_ids):
        raise ValueError("query did not return one row per resolved channel")
    channels = []
    for index, row in enumerate(rows):
        channel_id, mature, immature, repeat, cross, net = row
        if channel_id != resolved.channel_ids[index]:
            raise ValueError("query channel order does not match resolved filters")
        channels.append(ChannelFollowupChannelRow.model_validate({
            "channel_id": channel_id,
            **_count_block(int(mature), int(immature), int(repeat), int(cross), net),
        }))
    mature = sum(row.channel_mature_cohort_count for row in channels)
    immature = sum(row.channel_immature_count for row in channels)
    repeat = sum(row.channel_repeat_count for row in channels)
    cross = sum(row.channel_cross_channel_count for row in channels)
    net = None if mature == 0 else sum(row.channel_window_net_paid_minor or 0 for row in channels)
    totals = ChannelFollowupCounts.model_validate(_count_block(mature, immature, repeat, cross, net))
    result = ChannelFollowupResult.model_validate({
        "schema_version": snapshot.schema_version,
        "answer_mode": "DETERMINISTIC_TOOL",
        "query_id": request.query_id,
        "query_version": request.query_version,
        "metric_id": request.metric_id,
        "metric_version": request.metric_version,
        "data_version": snapshot.data_version,
        "hash_version": resolved.hash_version,
        "contains_real_data": False,
        "data_source": "SYNTHETIC_SNAPSHOT",
        "data_snapshot_ref": snapshot.snapshot_id,
        "as_of": snapshot.as_of,
        "resolved_filters": resolved.model_dump(mode="json"),
        "filter_hash": resolved.filter_hash,
        "facts": ChannelFollowupFacts.model_validate({
            "display_name": DISPLAY_NAME,
            "currency": snapshot.currency,
            "amount_unit": snapshot.amount_unit,
            "amount_precision": snapshot.amount_precision,
            "observation_days": resolved.observation_days,
            "channels": [row.model_dump() for row in channels],
            "totals": totals.model_dump(),
        }),
        "limitations": list(LIMITATIONS),
    })
    after = fixture.physical_sha256()
    if after != before:
        raise ValueError("channel-follow-up database hash changed during query")
    return result
