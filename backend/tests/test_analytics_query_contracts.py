"""Contract and hand-golden checks only. SQL / native / real business are NOT RUN."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.contracts.analytics import AnalyticsB0Facts, AnalyticsB0Result
from backend.contracts.analytics_query import (
    B0_RUN_SCHEMA,
    DISPLAY_NAME,
    JS_MAX_SAFE_INTEGER,
    QUERY_SCHEMA,
    ChannelFollowupCounts,
    ChannelFollowupFacts,
    ChannelFollowupQueryRequest,
    ChannelFollowupResult,
    ChannelFollowupSnapshot,
    canonical_rfc3339,
    query_contract_openapi,
    snapshot_digest as contract_snapshot_digest,
)
from backend.contracts.schemas import (
    ChannelFollowupQueryRequest as ExportedRequest,
    ChannelFollowupResult as ExportedResult,
    ChannelFollowupSnapshot as ExportedSnapshot,
)
from backend.semantic.analytics_channel_followup import (
    FAMILY_CANDIDATE_HANDOFF_AUDIENCE,
    FAMILY_FIRST_PURCHASE_PRODUCT_PATH,
    HASH_VERSION,
    LIMITATIONS,
    METRIC_VERSION,
    QUERY_ID,
    QUERY_VERSION,
    QUERY_FAMILY_STATUS,
)
from backend.services.analytics.catalog import (
    QUERY_FAMILIES,
    QueryFamilyStatus,
    UnsupportedQueryError,
    bind_resolved_filters,
    require_supported_query,
    snapshot_digest,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SNAPSHOT_PATH = FIXTURE_DIR / "analytics_channel_followup_v1.json"
EXPECTED_PATH = FIXTURE_DIR / "analytics_channel_followup_v1_expected.json"
B0_OPENAPI = Path(__file__).resolve().parents[1] / "contracts" / "analytics-run.openapi.json"
QUERY_OPENAPI = Path(__file__).resolve().parents[1] / "contracts" / "analytics-query.openapi.json"
B0_OPENAPI_SHA256 = "5d93c3aabf362865e8f24e28c96a8d1f75717c80370f31734407d85b128b9679"
B0_ANALYTICS_PY_SHA256 = "40050e9acd5024a418b07f8add94f93a476b7f422b933eb547e3080ab6dfa72d"
B0_SEMANTIC_SHA256 = "ff4f61933a7fba14511db7e0b33ccdcbf8b3dae790097e444fcf5fa6b03ed9f3"
PERMISSION = "synthetic-demo"

VALID_REQUEST = {
    "schema_version": QUERY_SCHEMA,
    "query_id": QUERY_ID,
    "query_version": QUERY_VERSION,
    "metric_id": "channel_first_observed_n_day_repeat",
    "metric_version": METRIC_VERSION,
    "cohort_window": {"kind": "FIXED", "start_date": "2026-06-01", "end_date": "2026-09-01"},
    "observation_days": 30,
    "data_snapshot_ref": "synthetic-channel-followup-v1",
    "timezone": "Asia/Shanghai",
    "channel_ids": [],
    "cohort_ref": None,
    "product_ids": [],
    "exclude_low_price": False,
    "comparison": None,
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot() -> ChannelFollowupSnapshot:
    return ChannelFollowupSnapshot.model_validate(load_json(SNAPSHOT_PATH))


def request_for(days: int, channel_ids=None) -> ChannelFollowupQueryRequest:
    payload = deepcopy(VALID_REQUEST)
    payload["observation_days"] = days
    if channel_ids is not None:
        payload["channel_ids"] = channel_ids
    return ChannelFollowupQueryRequest.model_validate(payload)


def result_for(days: int, facts: dict, permission: str = PERMISSION) -> ChannelFollowupResult:
    snap = snapshot()
    resolved = bind_resolved_filters(request_for(days), snap, permission)
    return ChannelFollowupResult.model_validate({
        "schema_version": QUERY_SCHEMA,
        "answer_mode": "DETERMINISTIC_TOOL",
        "query_id": QUERY_ID,
        "query_version": QUERY_VERSION,
        "metric_id": "channel_first_observed_n_day_repeat",
        "metric_version": METRIC_VERSION,
        "data_version": snap.data_version,
        "hash_version": HASH_VERSION,
        "contains_real_data": False,
        "data_source": "SYNTHETIC_SNAPSHOT",
        "data_snapshot_ref": snap.snapshot_id,
        "as_of": snap.as_of,
        "resolved_filters": resolved.model_dump(mode="json"),
        "filter_hash": resolved.filter_hash,
        "facts": facts,
        "limitations": list(LIMITATIONS),
    })


def test_fixture_is_the_hand_example_not_a_business_constant():
    snap = snapshot()
    users = {order.synthetic_user_id for order in snap.orders}
    assert len(snap.orders) == 22
    assert len(users) == 11
    assert len(snap.refunds) == 5
    assert "0009007199254740993" in users
    assert all(type(order.order_id) is str and type(order.synthetic_user_id) is str for order in snap.orders)
    keys = [(order.synthetic_user_id, order.order_id) for order in snap.orders]
    assert len(keys) == len(set(keys))


def test_expected_envelope_does_not_claim_query_pass():
    expected = load_json(EXPECTED_PATH)
    assert expected["computation"] == "NOT_RUN"
    assert expected["not_a_query_pass"] is True
    assert expected["method"] == "hand_calculated"
    assert expected["display_name"] == DISPLAY_NAME


@pytest.mark.parametrize("days", [30, 60, 90])
def test_hand_goldens_validate_on_real_models(days: int):
    expected = load_json(EXPECTED_PATH)["windows"][str(days)]
    facts = ChannelFollowupFacts.model_validate(expected)
    built = result_for(days, expected)
    assert built.facts == facts
    assert built.contains_real_data is False
    assert built.facts.display_name == DISPLAY_NAME
    dumped = built.facts.model_dump()
    for banned in ("user_ids", "order_ids", "synthetic_user_ids", "members", "cohort_members"):
        assert banned not in dumped
        assert banned not in dumped["channels"][0]


def test_literal_n30_n60_n90_window_table():
    windows = load_json(EXPECTED_PATH)["windows"]
    n30, n60, n90 = windows["30"], windows["60"], windows["90"]
    assert n30["channels"][0]["channel_mature_cohort_count"] == 7
    assert n30["channels"][0]["channel_immature_count"] == 1
    assert n30["channels"][0]["channel_repeat_count"] == 4
    assert n30["channels"][0]["channel_cross_channel_count"] == 3
    assert n30["channels"][0]["channel_window_net_paid_minor"] == 87000
    assert n30["channels"][1]["channel_mature_cohort_count"] == 2
    assert n30["channels"][1]["channel_repeat_count"] == 1
    assert n30["channels"][1]["channel_cross_channel_count"] == 0
    assert n30["channels"][1]["channel_window_net_paid_minor"] == 23000
    assert n30["totals"]["channel_mature_cohort_count"] == 9
    assert n30["totals"]["channel_immature_count"] == 1
    assert n30["totals"]["channel_repeat_count"] == 5
    assert n30["totals"]["channel_cross_channel_count"] == 3
    assert n30["totals"]["channel_window_net_paid_minor"] == 110000
    assert n30["channels"][0]["channel_repeat_ratio"] == 4 / 7
    assert n30["channels"][0]["channel_cross_channel_ratio"] == 3 / 7
    assert n30["channels"][1]["channel_repeat_ratio"] == 1 / 2
    assert n30["totals"]["channel_repeat_ratio"] == 5 / 9
    assert n30["totals"]["channel_cross_channel_ratio"] == 1 / 3
    assert n60["channels"][0]["channel_repeat_count"] == 5
    assert n60["channels"][0]["channel_cross_channel_count"] == 4
    assert n60["channels"][0]["channel_window_net_paid_minor"] == 92000
    assert n60["totals"]["channel_repeat_count"] == 6
    assert n60["totals"]["channel_cross_channel_count"] == 4
    assert n60["totals"]["channel_window_net_paid_minor"] == 115000
    assert n90["channels"][0]["channel_mature_cohort_count"] == 2
    assert n90["channels"][0]["channel_immature_count"] == 6
    assert n90["channels"][0]["channel_window_net_paid_minor"] == 30000
    assert n90["channels"][1]["channel_mature_cohort_count"] == 0
    assert n90["channels"][1]["channel_immature_count"] == 2
    assert n90["channels"][1]["channel_repeat_ratio"] is None
    assert n90["channels"][1]["channel_window_net_paid_minor"] is None
    assert n90["channels"][1]["channel_empty_reason"] == "EMPTY_MATURE_COHORT"
    assert n90["totals"]["channel_mature_cohort_count"] == 2
    assert n90["totals"]["channel_immature_count"] == 8
    assert n90["totals"]["channel_window_net_paid_minor"] == 30000


def test_empty_mature_cannot_be_zero_ratio_or_zero_net():
    with pytest.raises(ValidationError):
        ChannelFollowupCounts.model_validate({
            "channel_mature_cohort_count": 0,
            "channel_immature_count": 2,
            "channel_repeat_count": 0,
            "channel_cross_channel_count": 0,
            "channel_repeat_ratio": 0.0,
            "channel_cross_channel_ratio": 0.0,
            "channel_window_net_paid_minor": 0,
            "channel_empty_reason": "EMPTY_MATURE_COHORT",
        })


def test_bool_count_nonfinite_ratio_and_extra_fields_are_rejected():
    base = {
        "channel_mature_cohort_count": 2,
        "channel_immature_count": 0,
        "channel_repeat_count": 1,
        "channel_cross_channel_count": 0,
        "channel_repeat_ratio": 0.5,
        "channel_cross_channel_ratio": 0.0,
        "channel_window_net_paid_minor": 100,
        "channel_empty_reason": None,
    }
    with pytest.raises(ValidationError):
        ChannelFollowupCounts.model_validate({**base, "channel_mature_cohort_count": True})
    with pytest.raises(ValidationError):
        ChannelFollowupCounts.model_validate({**base, "channel_repeat_ratio": float("inf")})
    with pytest.raises(ValidationError):
        ChannelFollowupCounts.model_validate({**base, "channel_repeat_ratio": float("nan")})
    with pytest.raises(ValidationError):
        ChannelFollowupCounts.model_validate({**base, "channel_repeat_ratio": 1.1})
    with pytest.raises(ValidationError):
        ChannelFollowupCounts.model_validate({**base, "channel_repeat_count": 3})
    with pytest.raises(ValidationError):
        ChannelFollowupCounts.model_validate({**base, "channel_cross_channel_count": 2})
    with pytest.raises(ValidationError):
        ChannelFollowupCounts.model_validate({**base, "user_ids": ["a"]})


@pytest.mark.parametrize("patch", [
    {"schema_version": "future/v99"},
    {"schema_version": B0_RUN_SCHEMA},
    {"query_id": FAMILY_FIRST_PURCHASE_PRODUCT_PATH},
    {"cohort_window": {"kind": "ROLLING", "window_id": "last_90"}},
    {"cohort_ref": {"id": "aud_1", "version": 1}},
    {"product_ids": ["sku_a"]},
    {"exclude_low_price": True},
    {"comparison": "YOY"},
    {"as_of": "2026-09-01T00:00:00+08:00"},
    {"sql": "SELECT 1"},
    {"observation_days": 45},
    {"channel_ids": ["C"]},
    {"channel_ids": ["A", "A"]},
])
def test_request_rejects_unsupported_or_unknown_inputs(patch: dict):
    payload = {**VALID_REQUEST, **patch}
    with pytest.raises(ValidationError):
        ChannelFollowupQueryRequest.model_validate(payload)


def test_snapshot_rejects_conflicts_fk_negative_and_over_refund():
    raw = load_json(SNAPSHOT_PATH)
    conflict = deepcopy(raw)
    conflict["orders"].append({
        "order_id": "a01", "synthetic_user_id": "a", "paid_at": "2026-06-01T00:00:00+08:00",
        "channel": "B", "gross_paid_minor": 10000, "status": "PAID",
    })
    with pytest.raises(ValidationError):
        ChannelFollowupSnapshot.model_validate(conflict)
    duplicate = deepcopy(raw)
    duplicate["orders"].append(duplicate["orders"][0])
    with pytest.raises(ValidationError):
        ChannelFollowupSnapshot.model_validate(duplicate)
    fk = deepcopy(raw)
    fk["lines"].append({
        "line_id": "orphan-l1", "order_id": "a01", "synthetic_user_id": "b",
        "product_id": "sku_a", "quantity": 1,
    })
    with pytest.raises(ValidationError):
        ChannelFollowupSnapshot.model_validate(fk)
    negative = deepcopy(raw)
    negative["orders"][0]["gross_paid_minor"] = -1
    with pytest.raises(ValidationError):
        ChannelFollowupSnapshot.model_validate(negative)
    over = deepcopy(raw)
    over["refunds"].append({
        "refund_id": "d01-over", "order_id": "d01", "synthetic_user_id": "d",
        "refunded_at": "2026-06-05T00:00:00+08:00", "refund_minor": 1,
    })
    with pytest.raises(ValidationError):
        ChannelFollowupSnapshot.model_validate(over)
    numeric_id = deepcopy(raw)
    numeric_id["orders"][0]["order_id"] = 101
    with pytest.raises(ValidationError):
        ChannelFollowupSnapshot.model_validate(numeric_id)


def test_same_order_id_string_does_not_merge_two_users():
    payload = {
        "schema_version": QUERY_SCHEMA,
        "snapshot_id": "synthetic-channel-followup-v1",
        "data_version": "synthetic-channel-followup-data/v1",
        "as_of": "2026-09-01T00:00:00+08:00",
        "timezone": "Asia/Shanghai",
        "currency": "CNY",
        "amount_unit": "minor",
        "amount_precision": "integer_fen",
        "scope": "synthetic",
        "contains_real_data": False,
        "orders": [
            {"order_id": "shared-1", "synthetic_user_id": "u-1", "paid_at": "2026-06-01T00:00:00+08:00",
             "channel": "A", "gross_paid_minor": 10000, "status": "PAID"},
            {"order_id": "shared-1", "synthetic_user_id": "u-2", "paid_at": "2026-06-02T00:00:00+08:00",
             "channel": "B", "gross_paid_minor": 8000, "status": "PAID"},
        ],
        "lines": [
            {"line_id": "u1-l1", "order_id": "shared-1", "synthetic_user_id": "u-1", "product_id": "sku_a", "quantity": 1},
            {"line_id": "u2-l1", "order_id": "shared-1", "synthetic_user_id": "u-2", "product_id": "sku_b", "quantity": 1},
        ],
        "refunds": [],
    }
    snap = ChannelFollowupSnapshot.model_validate(payload)
    keys = {(order.synthetic_user_id, order.order_id) for order in snap.orders}
    assert keys == {("u-1", "shared-1"), ("u-2", "shared-1")}
    assert snap.orders[0].order_id == "shared-1"
    assert type(snap.orders[0].order_id) is str


def test_filter_hash_is_stable_under_permutation_and_changes_with_permission():
    snap = snapshot()
    shuffled = snap.model_dump(mode="json")
    shuffled["orders"] = list(reversed(shuffled["orders"]))
    shuffled["lines"] = list(reversed(shuffled["lines"]))
    shuffled["refunds"] = list(reversed(shuffled["refunds"]))
    other = ChannelFollowupSnapshot.model_validate(shuffled)
    assert snapshot_digest(snap) == snapshot_digest(other)
    left = bind_resolved_filters(request_for(30, ["B", "A"]), snap, PERMISSION)
    right = bind_resolved_filters(request_for(30, []), other, PERMISSION)
    assert left.filter_hash == right.filter_hash
    other_scope = bind_resolved_filters(request_for(30), snap, "other-scope")
    assert other_scope.filter_hash != left.filter_hash
    n60 = bind_resolved_filters(request_for(60), snap, PERMISSION)
    assert n60.filter_hash != left.filter_hash
    assert left.hash_version == HASH_VERSION
    assert left.as_of == snap.as_of


def test_deferred_families_have_no_success_payload():
    assert QUERY_FAMILY_STATUS[FAMILY_FIRST_PURCHASE_PRODUCT_PATH] == QueryFamilyStatus.SUPPORTED_CONTRACT
    assert QUERY_FAMILIES[FAMILY_FIRST_PURCHASE_PRODUCT_PATH].status is QueryFamilyStatus.SUPPORTED_CONTRACT
    assert QUERY_FAMILIES[FAMILY_CANDIDATE_HANDOFF_AUDIENCE].status is QueryFamilyStatus.DEFERRED
    require_supported_query(FAMILY_FIRST_PURCHASE_PRODUCT_PATH)
    with pytest.raises(UnsupportedQueryError, match="DEFERRED"):
        require_supported_query(FAMILY_CANDIDATE_HANDOFF_AUDIENCE)
    require_supported_query(QUERY_ID)


def test_schemas_reexport_and_semantic_versions_match():
    assert ExportedRequest is ChannelFollowupQueryRequest
    assert ExportedSnapshot is ChannelFollowupSnapshot
    assert ExportedResult is ChannelFollowupResult
    from backend.semantic import analytics_channel_followup as semantic
    assert semantic.QUERY_SCHEMA == QUERY_SCHEMA
    assert semantic.QUERY_VERSION == QUERY_VERSION
    assert semantic.METRIC_VERSION == METRIC_VERSION
    assert not hasattr(semantic, "repeat_query")
    assert not hasattr(semantic, "compute_channel_followup")


def test_openapi_is_components_only_and_matches_artifact_hash():
    schema = query_contract_openapi()
    assert schema["paths"] == {}
    assert schema["x-not-an-http-api"] is True
    assert schema["x-query-schema"] == QUERY_SCHEMA
    assert "ChannelFollowupResult" in schema["components"]["schemas"]
    parsed = json.loads(json.dumps(schema, sort_keys=True, ensure_ascii=False, allow_nan=False))
    digest = hashlib.sha256(json.dumps(parsed, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    artifact = json.loads(QUERY_OPENAPI.read_text(encoding="utf-8"))
    sha = artifact.pop("x-schema-sha256")
    assert sha == digest
    assert artifact["paths"] == {}
    assert artifact["x-not-an-http-api"] is True


def test_b0_fixed_fixture_and_schema_hash_unchanged():
    facts = AnalyticsB0Facts()
    assert facts.customers == 100 and facts.repeat_customers == 25 and facts.repeat_ratio == 0.25
    with pytest.raises(ValidationError):
        AnalyticsB0Facts(customers=101)
    with pytest.raises(ValidationError):
        AnalyticsB0Facts(repeat_ratio=0.5)
    result = AnalyticsB0Result(facts=facts)
    assert result.schema_version == B0_RUN_SCHEMA
    assert result.facts.repeat_ratio == 0.25
    openapi = json.loads(B0_OPENAPI.read_text(encoding="utf-8"))
    assert openapi["x-schema-sha256"] == B0_OPENAPI_SHA256
    contracts = B0_OPENAPI.parent
    analytics_py = hashlib.sha256((contracts / "analytics.py").read_bytes()).hexdigest()
    semantic = hashlib.sha256((contracts.parent / "semantic" / "analytics_b0.py").read_bytes()).hexdigest()
    assert analytics_py == B0_ANALYTICS_PY_SHA256
    assert semantic == B0_SEMANTIC_SHA256


def test_as_of_microsecond_changes_hash_and_equivalent_offset_is_stable():
    snap = snapshot()
    base = bind_resolved_filters(request_for(30), snap, PERMISSION)
    shifted_payload = snap.model_dump(mode="python")
    shifted_payload["as_of"] = snap.as_of + timedelta(microseconds=1)
    shifted = ChannelFollowupSnapshot.model_validate(shifted_payload)
    shifted_bound = bind_resolved_filters(request_for(30), shifted, PERMISSION)
    assert snapshot_digest(shifted) != snapshot_digest(snap)
    assert contract_snapshot_digest(shifted) != contract_snapshot_digest(snap)
    assert shifted_bound.filter_hash != base.filter_hash
    utc_payload = snap.model_dump(mode="python")
    utc_payload["as_of"] = snap.as_of.astimezone(timezone.utc)
    for order in utc_payload["orders"]:
        order["paid_at"] = order["paid_at"].astimezone(timezone.utc)
    for refund in utc_payload["refunds"]:
        refund["refunded_at"] = refund["refunded_at"].astimezone(timezone.utc)
    equivalent = ChannelFollowupSnapshot.model_validate(utc_payload)
    assert snapshot_digest(equivalent) == snapshot_digest(snap)
    assert bind_resolved_filters(request_for(30), equivalent, PERMISSION).filter_hash == base.filter_hash
    assert canonical_rfc3339(snap.as_of).endswith(".000000+00:00")
    assert canonical_rfc3339(snap.as_of + timedelta(microseconds=1)) != canonical_rfc3339(snap.as_of)


def _tamper_result(mutator):
    expected = load_json(EXPECTED_PATH)["windows"]["30"]
    dumped = result_for(30, expected).model_dump(mode="json")
    mutator(dumped)
    ChannelFollowupResult.model_validate(dumped)


def test_self_consistent_hash_rejects_window_scope_digest_asof_days_channels_and_zero_hash():
    expected = load_json(EXPECTED_PATH)["windows"]["30"]
    ChannelFollowupResult.model_validate(result_for(30, expected).model_dump(mode="json"))
    with pytest.raises(ValidationError):
        def reverse(dumped):
            start = dumped["resolved_filters"]["resolved_cohort_start"]
            dumped["resolved_filters"]["resolved_cohort_start"] = dumped["resolved_filters"]["resolved_cohort_end"]
            dumped["resolved_filters"]["resolved_cohort_end"] = start
        _tamper_result(reverse)
    with pytest.raises(ValidationError):
        _tamper_result(lambda dumped: dumped["resolved_filters"].__setitem__("permission_scope", "other-scope"))
    with pytest.raises(ValidationError):
        def zeros(dumped):
            dumped["filter_hash"] = "0" * 64
            dumped["resolved_filters"]["filter_hash"] = "0" * 64
        _tamper_result(zeros)
    with pytest.raises(ValidationError):
        _tamper_result(lambda dumped: dumped["resolved_filters"].__setitem__("data_digest", "ab" * 32))
    with pytest.raises(ValidationError):
        def bump_asof(dumped):
            dumped["resolved_filters"]["as_of"] = "2026-09-01T00:00:00.000001+08:00"
            dumped["as_of"] = dumped["resolved_filters"]["as_of"]
        _tamper_result(bump_asof)
    with pytest.raises(ValidationError):
        def bump_days(dumped):
            dumped["resolved_filters"]["observation_days"] = 60
            dumped["facts"]["observation_days"] = 60
        _tamper_result(bump_days)
    with pytest.raises(ValidationError):
        _tamper_result(lambda dumped: dumped["resolved_filters"].__setitem__("channel_ids", ["A"]))


def test_bind_revalidates_constructed_unsupported_product_filter():
    request = ChannelFollowupQueryRequest.model_construct(
        **{**VALID_REQUEST, "product_ids": ["sku_a"], "cohort_window": request_for(30).cohort_window},
    )
    with pytest.raises(ValidationError):
        bind_resolved_filters(request, snapshot(), PERMISSION)


def test_wire_input_rejects_numeric_bool_float_epoch_and_naive_times():
    with pytest.raises(ValidationError):
        ChannelFollowupQueryRequest.model_validate({**VALID_REQUEST, "exclude_low_price": 0})
    with pytest.raises(ValidationError):
        ChannelFollowupQueryRequest.model_validate({**VALID_REQUEST, "observation_days": 30.0})
    with pytest.raises(ValidationError):
        ChannelFollowupQueryRequest.model_validate({
            **VALID_REQUEST,
            "cohort_window": {"kind": "FIXED", "start_date": 19844, "end_date": "2026-09-01"},
        })
    ChannelFollowupQueryRequest.model_validate({
        **VALID_REQUEST,
        "cohort_window": {"kind": "FIXED", "start_date": date(2026, 6, 1), "end_date": date(2026, 9, 1)},
    })
    raw = load_json(SNAPSHOT_PATH)
    with pytest.raises(ValidationError):
        ChannelFollowupSnapshot.model_validate({**raw, "as_of": 1756684800})
    with pytest.raises(ValidationError):
        mutated = deepcopy(raw)
        mutated["orders"][0]["paid_at"] = 1756684800
        ChannelFollowupSnapshot.model_validate(mutated)
    with pytest.raises(ValidationError):
        mutated = deepcopy(raw)
        mutated["refunds"][0]["refunded_at"] = 1756684800
        ChannelFollowupSnapshot.model_validate(mutated)
    with pytest.raises(ValidationError):
        mutated = snapshot().model_dump(mode="python")
        mutated["as_of"] = datetime(2026, 9, 1)
        ChannelFollowupSnapshot.model_validate(mutated)
    with pytest.raises(ValidationError):
        ChannelFollowupSnapshot.model_validate({**raw, "as_of": "2026-09-01T00:00:00.0000001+08:00"})
    ChannelFollowupSnapshot.model_validate(raw)


def test_js_safe_integer_transport_limit_is_not_a_business_threshold():
    valid = {
        "channel_mature_cohort_count": 1,
        "channel_immature_count": 0,
        "channel_repeat_count": 0,
        "channel_cross_channel_count": 0,
        "channel_repeat_ratio": 0.0,
        "channel_cross_channel_ratio": 0.0,
        "channel_window_net_paid_minor": JS_MAX_SAFE_INTEGER,
        "channel_empty_reason": None,
    }
    ChannelFollowupCounts.model_validate(valid)
    with pytest.raises(ValidationError):
        ChannelFollowupCounts.model_validate({**valid, "channel_window_net_paid_minor": JS_MAX_SAFE_INTEGER + 2})
    with pytest.raises(ValidationError):
        ChannelFollowupFacts.model_validate({
            "display_name": DISPLAY_NAME,
            "currency": "CNY",
            "amount_unit": "minor",
            "amount_precision": "integer_fen",
            "observation_days": 30,
            "channels": [
                {"channel_id": "A", **valid},
                {"channel_id": "B", **valid},
            ],
            "totals": {
                **valid,
                "channel_mature_cohort_count": 2,
                "channel_window_net_paid_minor": JS_MAX_SAFE_INTEGER,
            },
        })
    schema = query_contract_openapi()
    net = schema["components"]["schemas"]["ChannelFollowupCounts"]["properties"]["channel_window_net_paid_minor"]
    maximums = [item.get("maximum") for item in net.get("anyOf", [net]) if isinstance(item, dict)]
    assert JS_MAX_SAFE_INTEGER in maximums
    for name in ("ChannelFollowupQueryRequest", "ChannelFollowupResolvedFilters"):
        product = schema["components"]["schemas"][name]["properties"]["product_ids"]
        assert product["maxItems"] == 0
        assert product["const"] == []
