"""Actual synthetic arithmetic -> immutable result -> editable/persistent waterfall."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.contracts.board_spec import BoardDraft, BoardPatchPreview, BoardRollbackPreview, WaterfallFacts
from backend.contracts.competition_computed import CompetitionComputedResult
from backend.services.analytics.access import AnalyticsError
from backend.services.analytics.board_documents import BoardDocumentStore
from backend.services.analytics.board_result_adapter import board_generation_context, computed_board_resolver
from backend.services.analytics.competition_diagnosis.computed import compute_result
from backend.services.analytics.competition_diagnosis.store import ComputedResultStore
from backend.services.analytics.competition_diagnosis.synthetic import materialize_synthetic_source
from backend.tests.test_board_documents import ALICE, private, confirm, text_draft
from backend.tests.test_competition_computed_results import snapshot, condition


def calculate(tmp_path, payload=None, request=None):
    payload = deepcopy(payload or snapshot())
    payload.setdefault("money_unit", {"status": "KNOWN", "currency": "CNY", "amount_unit": "major"})
    source = materialize_synthetic_source(private(tmp_path / "source"), payload)
    return compute_result(source, ALICE, request or condition(), "diag.gsv", session_id="s1", request_id="wf1")


def test_channel_bridge_uses_order_net_and_retains_zero(tmp_path):
    result = calculate(tmp_path)
    bridge = result.facts.channel_bridge
    assert bridge.status == "AVAILABLE"
    assert [row.model_dump() for row in bridge.contributions] == [
        {"channel": "CH_RETAIL", "current_gsv": 130, "comparison_gsv": 130, "delta": 0},
        {"channel": "CH_SAMPLE", "current_gsv": 10, "comparison_gsv": 5, "delta": 5}]
    assert sum(row.delta for row in bridge.contributions) == result.facts.difference == 5
    assert result.facts.current_daily.points[9].gsv == 40  # Partial refund at the same cutoff.
    assert CompetitionComputedResult.model_validate_json(result.model_dump_json()) == result


def test_new_and_lost_channels_have_signed_contributions(tmp_path):
    payload = snapshot()
    payload["orders"][0]["channel"] = "CH_LOST"
    payload["orders"][3]["channel"] = payload["orders"][4]["channel"] = "CH_NEW"
    result = calculate(tmp_path, payload)
    values = {row.channel: row.delta for row in result.facts.channel_bridge.contributions}
    assert values == {"CH_LOST": -100, "CH_NEW": 90, "CH_RETAIL": 10, "CH_SAMPLE": 5}
    assert sum(values.values()) == 5


@pytest.mark.parametrize("scope", [{"kind": "CHANNEL_IDS", "channel_ids": ["CH_RETAIL"]},
                                 {"kind": "PRODUCT_IDS", "product_ids": ["P-R"]}])
def test_bridge_respects_explicit_scope_without_new_queries(tmp_path, scope):
    result = calculate(tmp_path, request=condition(sales_scope=scope))
    assert [item.channel for item in result.facts.channel_bridge.contributions] == ["CH_RETAIL"]
    assert result.facts.channel_bridge.contributions[0].delta == 0


@pytest.mark.parametrize("mutation,reason", [
    (lambda p: p.update(money_unit={"status": "UNKNOWN"}), "MONEY_UNIT_UNKNOWN"),
    (lambda p: p["orders"][4].update(channel="MIXED"), "AMBIGUOUS_ORDER_CHANNEL"),
    (lambda p: p["orders"][0].update(channel=None), "INVALID_CHANNEL"),
    (lambda p: p["orders"][0].update(channel=" "), "INVALID_CHANNEL"),
])
def test_unknown_units_and_ambiguous_channels_do_not_invent_attribution(tmp_path, mutation, reason):
    payload = snapshot()
    mutation(payload)
    result = calculate(tmp_path, payload)
    assert result.facts.channel_bridge.status == "UNAVAILABLE"
    assert result.facts.channel_bridge.unavailable_reason == reason
    assert result.facts.channel_bridge.contributions == []
    assert result.facts.current.gsv == 140  # Other valid representations remain usable.


def test_uncovered_period_is_not_an_all_zero_waterfall(tmp_path):
    result = calculate(tmp_path, request=condition(as_of="2026-08-01T00:00:00+08:00"))
    assert result.facts.channel_bridge.unavailable_reason == "PERIOD_UNAVAILABLE"
    assert result.facts.current.gsv is None


def test_channel_limit_refuses_without_truncation(tmp_path):
    payload = snapshot()
    row = payload["orders"][0]
    payload["orders"] = [{**row, "order_id": f"p{i}", "channel": f"CH_{i:03d}"} for i in range(201)]
    payload["refunds"] = []
    result = calculate(tmp_path, payload)
    assert result.facts.channel_bridge.unavailable_reason == "CHANNEL_LIMIT_EXCEEDED"
    assert result.facts.comparison.gsv == 20100


@pytest.mark.parametrize("mutation", [
    lambda x: x["facts"]["channel_bridge"]["contributions"][0].update(delta=1),
    lambda x: x["facts"]["channel_bridge"]["contributions"].pop(),
    lambda x: x["facts"]["channel_bridge"]["contributions"].reverse(),
    lambda x: x["facts"]["channel_bridge"]["contributions"][1].update(channel="CH_RETAIL"),
    lambda x: x["facts"]["channel_bridge"].update(status="UNAVAILABLE", unavailable_reason=None),
    lambda x: x["facts"]["channel_bridge"]["contributions"][0].update(delta=True),
])
def test_malformed_or_unreconciled_computation_cannot_be_saved(tmp_path, mutation):
    payload = calculate(tmp_path).model_dump(mode="json")
    mutation(payload)
    with pytest.raises(ValidationError):
        CompetitionComputedResult.model_validate(payload)


def test_waterfall_actual_result_preview_cancel_edit_reopen_and_rollback(tmp_path):
    result = calculate(tmp_path)
    results = ComputedResultStore(private(tmp_path / "results"))
    results.save(ALICE, "s1", "wf1", "a" * 64, result)
    context = board_generation_context(results, ALICE, "s1")
    assert "WATERFALL" in context["results"][0]["supported_components"]
    directory = private(tmp_path / "boards")
    store = BoardDocumentStore(directory, resolve_facts=computed_board_resolver(results))
    draft = text_draft().model_dump(mode="json")
    draft["blocks"].append({"block_id": "waterfall", "kind": "WATERFALL", "title": "渠道净额变化",
        "source_result_id": result.result_id, "props": {}, "layout": {"x": 0, "y": 8, "w": 12, "h": 8}})
    preview = store.generate(ALICE, BoardDraft.model_validate(draft))
    assert store.list(ALICE) == []
    facts = preview["snapshot"]["facts_by_result_id"][result.result_id]["waterfall"]
    assert WaterfallFacts.model_validate(facts).start.value == 135
    v1 = confirm(store, preview)
    board_id = v1["spec"]["board_id"]
    patch = BoardPatchPreview(base_version=1, block_id="waterfall", changes={"props": {"show_values": False}})
    edit = store.patch(ALICE, board_id, patch)
    store.cancel(ALICE, edit["preview_id"])
    assert store.get(ALICE, board_id) == v1
    v2 = confirm(store, store.patch(ALICE, board_id, patch), "waterfall-edit")
    assert v2["facts_by_result_id"] == v1["facts_by_result_id"]
    assert v2["spec"]["blocks"][:-1] == v1["spec"]["blocks"][:-1]
    reopened = BoardDocumentStore(directory)  # No model or result source required to read saved data.
    assert reopened.get(ALICE, board_id) == v2
    v3 = confirm(reopened, reopened.rollback(ALICE, board_id, BoardRollbackPreview(base_version=2, to_version=1)), "restore")
    assert v3["spec"]["blocks"] == v1["spec"]["blocks"]
    assert v3["facts_by_result_id"] == v1["facts_by_result_id"]


def test_unknown_unit_or_legacy_result_does_not_offer_waterfall(tmp_path):
    result = calculate(tmp_path, {**snapshot(), "money_unit": {"status": "UNKNOWN"}})
    results = ComputedResultStore(private(tmp_path / "results"))
    results.save(ALICE, "s1", "wf1", "a" * 64, result)
    assert "WATERFALL" not in board_generation_context(results, ALICE, "s1")["results"][0]["supported_components"]
    store = BoardDocumentStore(private(tmp_path / "boards"), resolve_facts=computed_board_resolver(results))
    draft = {"title": "拒绝假分解", "session_id": "s1", "blocks": [{"block_id": "w", "kind": "WATERFALL",
        "title": "瀑布", "source_result_id": result.result_id, "props": {}, "layout": {"x": 0, "y": 0, "w": 6, "h": 8}}]}
    with pytest.raises(AnalyticsError, match="COMPONENT_DATA"):
        store.generate(ALICE, BoardDraft.model_validate(draft))
    assert store.list(ALICE) == []


def test_shared_numeric_geometry_contract():
    cases = json.loads((Path(__file__).resolve().parents[2] /
        "dsh-plugins/shine-waterfall/tests/waterfall-cases.json").read_text())
    for case in cases:
        if case["valid"]:
            WaterfallFacts.model_validate(case["data"])
        else:
            with pytest.raises(ValidationError):
                WaterfallFacts.model_validate(case["data"])
