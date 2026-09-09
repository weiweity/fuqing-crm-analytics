"""Fixed trusted query-family dispatch. Never selects codecs from result payloads."""
from types import SimpleNamespace
from backend.contracts import analytics_query as cq
from backend.contracts import analytics_query_run as cr
from backend.contracts import analytics_first_purchase as fq
from backend.contracts import analytics_first_purchase_kernel as fr
from backend.services.analytics.catalog import bind_resolved_filters_from_metadata

CHANNEL = SimpleNamespace(
    schema=cr.QUERY_RUN_SCHEMA, request=cq.ChannelFollowupQueryRequest,
    result=cq.ChannelFollowupResult, descriptor=cr.ChannelFollowupFixtureDescriptor,
    binding=cr.ChannelFollowupRunBinding, conversation_request=cr.AnalyticsQueryConversationRequest,
    conversation=cr.AnalyticsQueryConversation, run_request=cr.AnalyticsQueryRunRequest,
    accepted=cr.AnalyticsQueryRunAccepted, snapshot=cr.AnalyticsQueryRunSnapshot,
    query_id=cq.QUERY_ID, metric_id=cq.METRIC_ID, query_version=cq.QUERY_VERSION, metric_version=cq.METRIC_VERSION, data_version=cq.DATA_VERSION,
)
FIRST_PURCHASE = SimpleNamespace(
    schema=fr.RUN_SCHEMA, request=fq.FirstPurchaseQueryRequest,
    result=fq.FirstPurchaseResult, descriptor=fr.FirstPurchaseFixtureDescriptor,
    binding=fr.FirstPurchaseKernelBinding, conversation_request=fr.FirstPurchaseConversationRequest,
    conversation=fr.FirstPurchaseConversation, run_request=fr.FirstPurchaseKernelRequest,
    accepted=fr.FirstPurchaseAccepted, snapshot=fr.FirstPurchaseKernelSnapshot,
    query_id=fq.QUERY_ID, metric_id=fq.METRIC_ID, query_version=fq.QUERY_VERSION, metric_version=fq.METRIC_VERSION, data_version=fq.DATA_VERSION,
)
CODECS = {"channel_followup": CHANNEL, "first_purchase": FIRST_PURCHASE}

def resolve_filters(family, request, binding):
    if family == "first_purchase":
        return fq.bind_resolved_filters(request, binding.fixture.snapshot, binding.permission_scope)
    if family != "channel_followup":
        raise ValueError("unsupported query family")
    f = binding.fixture
    return bind_resolved_filters_from_metadata(request, {
        "snapshot_id": f.snapshot_id, "data_version": f.data_version,
        "data_digest": f.data_digest, "as_of": f.as_of, "timezone": f.timezone,
    }, binding.permission_scope)
