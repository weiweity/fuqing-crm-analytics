"""FUNNEL pack off: catalog and 422 offer disappear; purchase-frequency facts remain."""
import pytest

from backend.contracts.board_spec import BoardDraft
from backend.services.analytics.access import AnalyticsError
from backend.services.analytics.board_documents import BoardDocumentStore
from backend.services.analytics.board_result_adapter import board_generation_context, computed_board_resolver
from backend.services.analytics.competition_diagnosis.store import ComputedResultStore
from backend.services.analytics.funnel_pack import funnel_pack_enabled
from backend.tests.test_board_documents import ALICE, private
from backend.tests.test_board_funnel import calculate


def test_pack_defaults_on():
    assert funnel_pack_enabled() is True


def test_pack_off_drops_catalog_and_supported_components(tmp_path, monkeypatch):
    monkeypatch.setenv("SHINE_FUNNEL", "off")
    result = calculate(tmp_path)
    assert result.facts.current_purchase_frequency.status == "AVAILABLE"
    store = ComputedResultStore(private(tmp_path / "results"))
    store.save(ALICE, "s1", "funnel1", "a" * 64, result)
    context = board_generation_context(store, ALICE, "s1")
    assert all(item["kind"] != "FUNNEL" for item in context["catalog"]["components"])
    assert "FUNNEL" not in context["results"][0]["supported_components"]
    facts = computed_board_resolver(store)(ALICE, "s1", result.result_id).facts
    assert "funnel" not in facts


def test_pack_off_rejects_funnel_block(tmp_path, monkeypatch):
    monkeypatch.setenv("SHINE_FUNNEL", "off")
    result = calculate(tmp_path)
    store = ComputedResultStore(private(tmp_path / "results"))
    store.save(ALICE, "s1", "funnel1", "a" * 64, result)
    boards = BoardDocumentStore(private(tmp_path / "boards"), resolve_facts=computed_board_resolver(store))
    draft = {"title": "无漏斗包", "session_id": "s1", "blocks": [{"block_id": "f", "kind": "FUNNEL",
        "title": "漏斗", "source_result_id": result.result_id, "props": {}, "layout": {"x": 0, "y": 0, "w": 6, "h": 8}}]}
    with pytest.raises(AnalyticsError, match="COMPONENT_UNSUPPORTED"):
        boards.generate(ALICE, BoardDraft.model_validate(draft))
    assert boards.list(ALICE) == []
