"""Static synthetic query catalog and canonical binding helpers.

No database connection, HTTP, SQL, or worker is created here.
Deferred families must not emit a placeholder success payload.
Hash helpers live in the query contract so models can self-check without
importing this service module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from enum import StrEnum
from zoneinfo import ZoneInfo

from backend.contracts.analytics_query import (
    METRIC_VERSION,
    QUERY_VERSION,
    REGISTERED_CHANNELS,
    ChannelFollowupQueryRequest,
    ChannelFollowupResolvedFilters,
    ChannelFollowupSnapshot,
    compute_filter_hash,
    filter_hash_payload,
    revalidate_model,
    snapshot_digest,
)
from backend.semantic.analytics_channel_followup import (
    FAMILY_CANDIDATE_HANDOFF_AUDIENCE,
    FAMILY_CHANNEL_FOLLOWUP,
    FAMILY_FIRST_PURCHASE_PRODUCT_PATH,
    FAMILY_STATUS_DEFERRED,
    FAMILY_STATUS_SUPPORTED_CONTRACT,
)


class QueryFamilyStatus(StrEnum):
    SUPPORTED_CONTRACT = FAMILY_STATUS_SUPPORTED_CONTRACT
    DEFERRED = FAMILY_STATUS_DEFERRED


@dataclass(frozen=True)
class QueryFamily:
    query_id: str
    status: QueryFamilyStatus
    title: str
    notes: str


QUERY_FAMILIES: dict[str, QueryFamily] = {
    FAMILY_CHANNEL_FOLLOWUP: QueryFamily(
        query_id=FAMILY_CHANNEL_FOLLOWUP,
        status=QueryFamilyStatus.SUPPORTED_CONTRACT,
        title="首次观察到的渠道 / N日二单率",
        notes="Offline deterministic SQL compute exists; worker/HTTP/native are not in G3a.",
    ),
    FAMILY_FIRST_PURCHASE_PRODUCT_PATH: QueryFamily(
        query_id=FAMILY_FIRST_PURCHASE_PRODUCT_PATH,
        status=QueryFamilyStatus.DEFERRED,
        title="首购商品路径",
        notes="Deferred. Shares FilterSpec-shaped inputs (FIXED window, N, snapshot, channels) but has no success payload, HTTP route, or golden in G2a.",
    ),
    FAMILY_CANDIDATE_HANDOFF_AUDIENCE: QueryFamily(
        query_id=FAMILY_CANDIDATE_HANDOFF_AUDIENCE,
        status=QueryFamilyStatus.DEFERRED,
        title="候选承接人群",
        notes="Deferred. Would reuse the same snapshot identity grain later; G2a is not three-family contract completion.",
    ),
}


class UnsupportedQueryError(ValueError):
    """Raised when a deferred or unknown family would otherwise look successful."""


def require_supported_query(query_id: str) -> QueryFamily:
    family = QUERY_FAMILIES.get(query_id)
    if family is None:
        raise UnsupportedQueryError(f"unknown query family: {query_id}")
    if family.status is not QueryFamilyStatus.SUPPORTED_CONTRACT:
        raise UnsupportedQueryError(
            f"{query_id} is {family.status.value}; this subset does not emit a success payload"
        )
    return family


def bind_resolved_filters(
    request: ChannelFollowupQueryRequest | dict,
    snapshot: ChannelFollowupSnapshot | dict,
    permission_scope: str,
) -> ChannelFollowupResolvedFilters:
    request = revalidate_model(ChannelFollowupQueryRequest, request)
    snapshot = revalidate_model(ChannelFollowupSnapshot, snapshot)
    require_supported_query(request.query_id)
    if request.data_snapshot_ref != snapshot.snapshot_id:
        raise ValueError("data_snapshot_ref does not match the snapshot")
    if request.timezone != snapshot.timezone:
        raise ValueError("timezone must match the registered snapshot")
    if request.query_version != QUERY_VERSION or request.metric_version != METRIC_VERSION:
        raise ValueError("unsupported query or metric version")
    zone = ZoneInfo(request.timezone)
    start = datetime.combine(request.cohort_window.start_date, time.min, tzinfo=zone)
    end = datetime.combine(request.cohort_window.end_date, time.min, tzinfo=zone)
    channels = tuple(sorted(request.channel_ids)) if request.channel_ids else REGISTERED_CHANNELS
    digest = snapshot_digest(snapshot)
    payload = filter_hash_payload(
        as_of=snapshot.as_of,
        channel_ids=channels,
        data_digest=digest,
        data_snapshot_ref=snapshot.snapshot_id,
        data_version=snapshot.data_version,
        observation_days=request.observation_days,
        permission_scope=permission_scope,
        resolved_cohort_end=end,
        resolved_cohort_start=start,
        timezone_name=request.timezone,
    )
    return ChannelFollowupResolvedFilters(
        resolved_cohort_start=start,
        resolved_cohort_end=end,
        observation_days=request.observation_days,
        as_of=snapshot.as_of,
        channel_ids=channels,
        permission_scope=permission_scope,
        data_digest=digest,
        filter_hash=compute_filter_hash(payload),
    )
