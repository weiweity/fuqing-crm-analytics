"""Actual nested customer computation, source ambiguity and durable board edits."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.contracts.board_spec import BoardDraft, BoardPatchPreview, BoardRollbackPreview, FunnelFacts
from backend.contracts.competition_computed import CompetitionComputedResult, evidence_payload
from backend.services.analytics.access import AnalyticsError
from backend.services.analytics.board_documents import BoardDocumentStore
from backend.services.analytics.board_result_adapter import board_generation_context, computed_board_resolver
from backend.services.analytics.competition_diagnosis.computed import compute_result
from backend.services.analytics.competition_diagnosis.store import ComputedResultStore
from backend.services.analytics.competition_diagnosis.synthetic import materialize_synthetic_source
from backend.services.analytics.resource_profile import content_hash
from backend.tests.test_board_documents import ALICE, private, text_draft, confirm
from backend.tests.test_competition_computed_results import snapshot, condition


def frequency_snapshot():
    payload = snapshot()
    template = payload["orders"][3]
    payload["orders"] = [
        {**template, "order_id": f"{user}-{index}", "sub_order_id": "1", "user_id": user,
         "pay_time": "2026-08-05 12:00:00", "actual_amount": 10}
        for user, count in [("A", 3), ("B", 2), ("C", 1)] for index in range(count)
    ]
    # Another line is not another order. An order before this period is not a stage.
    payload["orders"] += [
        {**payload["orders"][0], "sub_order_id": "2", "actual_amount": 5},
        {**template, "order_id": "old", "user_id": "C", "pay_time": "2025-08-05 12:00:00"},
        {**template, "order_id": "full-refund", "user_id": "D", "actual_amount": 10},
        {**template, "order_id": "closed", "user_id": "E", "order_status": "交易关闭"},
        {**template, "order_id": "deposit", "user_id": "E", "is_goujinjin": True},
    ]
    payload["refunds"] = [{"order_id": "full-refund", "refunded_at": "2026-08-25", "amount": 10},
                          {"order_id": "B-0", "refunded_at": "2026-08-25", "amount": 5}]
    return payload


def calculate(tmp_path, payload=None, request=None):
    source = materialize_synthetic_source(private(tmp_path / "source"), payload or frequency_snapshot())
    return compute_result(source, ALICE, request or condition(), "diag.gsv", session_id="s1", request_id="funnel1")


def counts(result):
    return [stage.customer_count for stage in result.facts.current_purchase_frequency.stages]


def test_nested_distinct_orders_same_day_splits_refunds_and_history(tmp_path):
    result = calculate(tmp_path)
    assert counts(result) == [3, 2, 1]
    assert result.facts.current.order_count == 6
    assert result.facts.current.customer_count == 3
    assert result.facts.money_unit.status == "UNKNOWN", "customer counting does not infer a money unit"
    assert CompetitionComputedResult.model_validate_json(result.model_dump_json()) == result
    assert all(set(stage.model_dump()) == {"minimum_orders", "customer_count"}
               for stage in result.facts.current_purchase_frequency.stages)


def test_refund_cutoff_changes_cohort_without_inventing_conversion(tmp_path):
    result = calculate(tmp_path, request=condition(as_of="2026-08-20T00:00:00+08:00"))
    assert counts(result) == [4, 2, 1]
    assert result.facts.current.order_count == 7


@pytest.mark.parametrize("mode", ["channel", "product", "sample"])
def test_funnel_uses_same_explicit_sales_scope(tmp_path, mode):
    payload = frequency_snapshot()
    payload["orders"][2].update(channel="CH_SAMPLE", product_id="OTHER")
    overrides = ({"sales_scope": {"kind": "CHANNEL_IDS", "channel_ids": ["CH_RETAIL"]}} if mode == "channel" else
                 {"sales_scope": {"kind": "PRODUCT_IDS", "product_ids": ["P-R"]}} if mode == "product" else
                 {"sample_mode": "EXCLUDE_CURRENT_SALES_ONLY", "sample_channel_ids": ["CH_SAMPLE"]})
    result = calculate(tmp_path, payload, condition(**overrides))
    assert counts(result) == [3, 2, 0]
    assert result.facts.current.order_count == 5


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_customer_is_unavailable_not_a_new_person(tmp_path, value):
    payload = frequency_snapshot()
    for row in payload["orders"]:
        if row["order_id"] == "A-0":
            row["user_id"] = value
    result = calculate(tmp_path, payload)
    assert result.facts.current_purchase_frequency.unavailable_reason == "INVALID_CUSTOMER"
    assert result.facts.current.customer_count is None
    assert result.facts.current.customer_count_unavailable_reason == "INVALID_CUSTOMER"
    assert counts(result) == []
    assert result.facts.current.gsv is not None


def test_mixed_identity_on_filtered_out_subline_cannot_be_attributed(tmp_path):
    payload = frequency_snapshot()
    payload["orders"][6].update(user_id="different-person", product_id="OTHER")
    result = calculate(tmp_path, payload, condition(sales_scope={"kind": "PRODUCT_IDS", "product_ids": ["P-R"]}))
    assert result.facts.current_purchase_frequency.unavailable_reason == "AMBIGUOUS_ORDER_CUSTOMER"
    assert result.facts.current.customer_count is None
    assert counts(result) == []


def test_unknown_period_and_known_empty_population_are_different(tmp_path):
    missing = calculate(private(tmp_path / "missing"), request=condition(as_of="2026-08-01T00:00:00+08:00"))
    assert missing.facts.current_purchase_frequency.unavailable_reason == "PERIOD_UNAVAILABLE"
    assert counts(missing) == []
    empty = calculate(private(tmp_path / "empty"), request=condition(sales_scope={"kind": "CHANNEL_IDS", "channel_ids": ["NONE"]}))
    assert empty.facts.current_purchase_frequency.status == "AVAILABLE"
    assert counts(empty) == [0, 0, 0]


def test_invalid_comparison_identity_does_not_poison_current_funnel(tmp_path):
    payload = frequency_snapshot()
    next(row for row in payload["orders"] if row["order_id"] == "old")["user_id"] = None
    result = calculate(tmp_path, payload)
    assert result.facts.comparison.customer_count is None
    assert result.facts.comparison.gsv == 30
    assert counts(result) == [3, 2, 1]


def test_invalid_identity_outside_selected_orders_does_not_poison_counts(tmp_path):
    payload = frequency_snapshot()
    next(row for row in payload["orders"] if row["order_id"] == "closed")["user_id"] = None
    assert counts(calculate(tmp_path, payload)) == [3, 2, 1]


@pytest.mark.parametrize("mutation", [
    lambda f: f["stages"][0].update(customer_count=4),
    lambda f: f["stages"][1].update(customer_count=4),
    lambda f: f["stages"][1].update(customer_count=True),
    lambda f: f["stages"][1].update(minimum_orders=3),
    lambda f: f["stages"].pop(),
    lambda f: f.update(basis="VISITOR_CONVERSION"),
    lambda f: f.update(status="UNAVAILABLE", unavailable_reason=None, stages=[]),
    lambda f: f.update(status="UNAVAILABLE", unavailable_reason="PERIOD_UNAVAILABLE", stages=[]),
    lambda f: f.update(stages=[{"minimum_orders": n, "customer_count": 3} for n in (1, 2, 3)]),
])
def test_invalid_funnel_rejected_even_with_rehashed_evidence(tmp_path, mutation):
    payload = calculate(tmp_path).model_dump(mode="json")
    mutation(payload["facts"]["current_purchase_frequency"])
    payload["evidence_digest"] = content_hash(evidence_payload(payload))
    payload["page"]["checksum"] = payload["evidence_digest"]
    with pytest.raises(ValidationError):
        CompetitionComputedResult.model_validate(payload)


def test_funnel_persistence_scoped_edit_cancel_reopen_rollback(tmp_path):
    result = calculate(tmp_path)
    results = ComputedResultStore(private(tmp_path / "results"))
    results.save(ALICE, "s1", "funnel1", "a" * 64, result)
    assert "FUNNEL" in board_generation_context(results, ALICE, "s1")["results"][0]["supported_components"]
    directory = private(tmp_path / "boards")
    store = BoardDocumentStore(directory, resolve_facts=computed_board_resolver(results))
    draft = text_draft().model_dump(mode="json")
    draft["blocks"].append({"block_id": "funnel", "kind": "FUNNEL", "title": "本期购买频次",
        "source_result_id": result.result_id, "props": {}, "layout": {"x": 0, "y": 8, "w": 12, "h": 8}})
    preview = store.generate(ALICE, BoardDraft.model_validate(draft))
    assert store.list(ALICE) == []
    facts = preview["snapshot"]["facts_by_result_id"][result.result_id]["funnel"]
    assert [stage.count for stage in FunnelFacts.model_validate(facts).stages] == [3, 2, 1]
    v1 = confirm(store, preview)
    board_id = v1["spec"]["board_id"]
    patch = BoardPatchPreview(base_version=1, block_id="funnel", changes={"props": {"rate_basis": "first", "show_values": False}})
    edit = store.patch(ALICE, board_id, patch)
    store.cancel(ALICE, edit["preview_id"])
    assert store.get(ALICE, board_id) == v1
    v2 = confirm(store, store.patch(ALICE, board_id, patch), "funnel-edit")
    assert v2["facts_by_result_id"] == v1["facts_by_result_id"]
    assert v2["spec"]["blocks"][:-1] == v1["spec"]["blocks"][:-1]
    reopened = BoardDocumentStore(directory)
    assert reopened.get(ALICE, board_id) == v2
    v3 = confirm(reopened, reopened.rollback(ALICE, board_id, BoardRollbackPreview(base_version=2, to_version=1)), "restore")
    assert v3["spec"]["blocks"] == v1["spec"]["blocks"]
    assert v3["facts_by_result_id"] == v1["facts_by_result_id"]


def test_legacy_result_cannot_generate_funnel_from_money(tmp_path):
    path = Path(__file__).resolve().parents[2] / "dsh-plugins/analytics-workbench/tests/competition-computed/waterfall-results.json"
    result = CompetitionComputedResult.model_validate(json.loads(path.read_text())["major"])
    results = ComputedResultStore(private(tmp_path / "results"))
    results.save(ALICE, "unit-ui", "major", "a" * 64, result)
    assert "FUNNEL" not in board_generation_context(results, ALICE, "unit-ui")["results"][0]["supported_components"]
    store = BoardDocumentStore(private(tmp_path / "boards"), resolve_facts=computed_board_resolver(results))
    draft = {"title": "拒绝金额漏斗", "session_id": "unit-ui", "blocks": [{"block_id": "f", "kind": "FUNNEL", "title": "漏斗",
        "source_result_id": result.result_id, "props": {}, "layout": {"x": 0, "y": 0, "w": 6, "h": 8}}]}
    with pytest.raises(AnalyticsError, match="COMPONENT_DATA"):
        store.generate(ALICE, BoardDraft.model_validate(draft))
    assert store.list(ALICE) == []


def test_shared_nested_count_contract():
    path = Path(__file__).resolve().parents[2] / "dsh-plugins/shine-funnel/tests/funnel-cases.json"
    for case in json.loads(path.read_text()):
        payload = {"unit": "人", "cohort_label": "合成人群", "counting_rule": "同一人群的嵌套计数",
                   "stages": [{"label": f"阶段{index}", "count": count} for index, count in enumerate(case["counts"])]}
        if case["valid"]:
            assert FunnelFacts.model_validate(payload).model_dump() == payload
        else:
            with pytest.raises(ValidationError):
                FunnelFacts.model_validate(payload)
    payload = {"unit": "人", "cohort_label": "合成人群", "counting_rule": "嵌套计数",
               "stages": [{"label": "阶段", "count": 2}, {"label": "阶段", "count": 1}]}
    with pytest.raises(ValidationError):
        FunnelFacts.model_validate(payload)
