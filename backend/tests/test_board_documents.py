"""Library canvas persistence with real isolated SQLite, not an in-memory UI mock."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from threading import Barrier

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from backend.analytics_competition_app import create_competition_app
from backend.contracts.board_spec import (
    BoardDraft, BoardLayoutPreview, BoardPatchPreview, BoardRollbackPreview, CATALOG,
    board_spec_openapi,
    BoardEditSelection, BoardEditProposal,
)
from backend.contracts.competition_computed import DATA_SCOPE, CompetitionComputedResult, evidence_payload
from backend.services.analytics.resource_profile import content_hash
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, B0IdentityRegistry
from backend.services.analytics.board_documents import BoardDocumentStore, ResolvedBoardFacts
from backend.services.analytics.board_result_adapter import computed_board_resolver
from backend.services.analytics.competition_diagnosis.computed import compute_result
from backend.services.analytics.competition_diagnosis.store import ComputedResultStore
from backend.tests.test_competition_computed_results import condition, source as computed_source

source = computed_source
ROOT = Path(__file__).resolve().parents[2]
CAPS = frozenset({"analysis:read", "analysis:save", "dashboard:read", "dashboard:update"})
ALICE = AnalyticsPrincipal("alice", CAPS, frozenset({DATA_SCOPE, "brand-a"}))
BOB = AnalyticsPrincipal("bob", CAPS, ALICE.data_scopes)
TOKEN = "library-board-isolated-test-token-32chars"
PREFIX = "/api/v1/analytics/board-spec"


def private(path):
    path.mkdir(mode=0o700)
    return path


def text_draft():
    return BoardDraft.model_validate({"title": "经营看板", "session_id": "s1", "blocks": [
        {"block_id": "note", "kind": "TEXT", "title": "说明", "props": {"content": "旧内容"},
         "layout": {"x": 0, "y": 0, "w": 6, "h": 5}},
        {"block_id": "other", "kind": "TEXT", "title": "其他", "layout": {"x": 6, "y": 0, "w": 6, "h": 5}},
    ]})


def patch(version, **changes):
    return BoardPatchPreview.model_validate({"base_version": version, "block_id": "note", "changes": changes})


def confirm(store, preview, key="confirm"):
    return store.confirm(ALICE, preview["preview_id"], key)


def test_preview_cancel_save_restart_patch_and_monotonic_rollback(tmp_path):
    directory = private(tmp_path / "boards")
    store = BoardDocumentStore(directory)
    initial = store.generate(ALICE, text_draft())
    assert store.list(ALICE) == []  # A preview is not a saved board.
    v1 = confirm(store, initial)
    board_id = v1["spec"]["board_id"]
    edit = store.patch(ALICE, board_id, patch(1, props={"content": "新内容"}, title="新标题"))
    assert edit["snapshot"]["spec"]["blocks"][1] == v1["spec"]["blocks"][1]
    assert store.get(ALICE, board_id) == v1
    store.cancel(ALICE, edit["preview_id"])
    store.cancel(ALICE, edit["preview_id"])
    with pytest.raises(AnalyticsError, match="PREVIEW_CANCELLED"):
        confirm(store, edit, "cancelled")
    assert store.get(ALICE, board_id) == v1
    edit = store.patch(ALICE, board_id, patch(1, props={"content": "新内容"}, title="新标题"))
    v2 = confirm(store, edit, "apply")
    # A process with no result resolver/model can reopen saved snapshots.
    script = """
import json, sys
from pathlib import Path
from backend.services.analytics.access import AnalyticsPrincipal
from backend.services.analytics.board_documents import BoardDocumentStore
actor=AnalyticsPrincipal('alice',frozenset({'dashboard:read'}),frozenset({'competition-diagnosis-fixture'}))
print(json.dumps(BoardDocumentStore(Path(sys.argv[1])).get(actor,sys.argv[2])))
"""
    process = subprocess.run([sys.executable, "-c", script, str(directory), board_id], cwd=tmp_path,
        env={"PATH": str(Path(sys.executable).parent) + ":/usr/bin:/bin", "PYTHONPATH": str(ROOT),
             "PYTHONNOUSERSITE": "1", "PYTHON_DOTENV_DISABLED": "1"},
        capture_output=True, text=True, timeout=30, check=True)
    assert json.loads(process.stdout) == v2
    reopened = BoardDocumentStore(directory)
    rollback = reopened.rollback(ALICE, board_id, BoardRollbackPreview(base_version=2, to_version=1))
    assert reopened.get(ALICE, board_id) == v2
    v3 = confirm(reopened, rollback, "rollback")
    assert v3["spec"]["blocks"] == v1["spec"]["blocks"] and v3["spec"]["version"] == 3
    assert reopened.get(ALICE, board_id, 2) == v2
    assert [item["version"] for item in reopened.history(ALICE, board_id)] == [3, 2, 1]
    assert confirm(reopened, initial) == v1  # Reply-loss retry cannot revert the newer head.
    assert reopened.get(ALICE, board_id) == v3
    assert directory.stat().st_mode & 0o077 == 0
    assert reopened.path.stat().st_mode & 0o077 == 0


def test_parallel_confirm_exactly_one_wins_and_retry_is_idempotent(tmp_path):
    directory = private(tmp_path / "boards")
    store = BoardDocumentStore(directory)
    v1 = confirm(store, store.generate(ALICE, text_draft()))
    board_id = v1["spec"]["board_id"]
    drafts = [store.patch(ALICE, board_id, patch(1, title=title)) for title in ("A", "B")]
    clients = [BoardDocumentStore(directory), BoardDocumentStore(directory)]
    barrier = Barrier(2)
    def attempt(index):
        barrier.wait(timeout=10)
        try:
            return confirm(clients[index], drafts[index], f"key-{index}")
        except AnalyticsError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [0, 1]))
    assert len([result for result in results if isinstance(result, dict)]) == 1
    assert results.count("VERSION_CONFLICT") == 1
    winner = next(index for index, result in enumerate(results) if isinstance(result, dict))
    assert confirm(store, drafts[winner], f"key-{winner}") == results[winner]
    assert confirm(store, drafts[winner], "a-new-key") == results[winner]
    assert len(store.history(ALICE, board_id)) == 2
    with pytest.raises(AnalyticsError, match="IDEMPOTENCY_CONFLICT"):
        confirm(store, drafts[1-winner], f"key-{winner}")


def test_expiry_locked_sqlite_and_midtransaction_failure_preserve_head(tmp_path):
    instant = [100]
    store = BoardDocumentStore(private(tmp_path / "boards"), clock=lambda: instant[0])
    initial = store.generate(ALICE, text_draft())
    v1 = confirm(store, initial)
    board_id = v1["spec"]["board_id"]
    edit = store.patch(ALICE, board_id, patch(1, title="不会丢失旧版"))
    instant[0] = edit["expires_at_ms"]
    with pytest.raises(AnalyticsError, match="PREVIEW_EXPIRED"):
        confirm(store, edit, "expired")
    edit = store.patch(ALICE, board_id, patch(1, title="可重试"))
    with closing(sqlite3.connect(store.path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        with pytest.raises(AnalyticsError, match="STATE_UNAVAILABLE") as error:
            confirm(store, edit, "locked")
        assert error.value.retryable
        conn.rollback()
        # Fail after the head UPDATE. The entire transaction, including head, must roll back.
        conn.execute("CREATE TRIGGER fail_revision BEFORE INSERT ON revisions BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
        conn.commit()
        with pytest.raises(AnalyticsError, match="STATE_UNAVAILABLE"):
            confirm(store, edit, "locked")
        assert store.get(ALICE, board_id) == v1
        assert store.preview(ALICE, edit["preview_id"])["status"] == "PENDING"
        conn.execute("DROP TRIGGER fail_revision")
        conn.commit()
    assert confirm(store, edit, "locked")["spec"]["version"] == 2


def test_ownership_permission_revocation_and_payload_integrity(tmp_path):
    def resolver(actor, session_id, result_id):
        return ResolvedBoardFacts({"schema_version": "board-component-facts/v1", "scalar": {"value": 42, "unit": None}}, frozenset({"brand-a"}))
    store = BoardDocumentStore(private(tmp_path / "boards"), resolve_facts=resolver)
    body = text_draft().model_dump(mode="json")
    body["blocks"][0].update(kind="METRIC", source_result_id="r1", props={})
    draft = store.generate(ALICE, BoardDraft.model_validate(body))
    v1 = confirm(store, draft)
    board_id = v1["spec"]["board_id"]
    assert store.list(BOB) == []
    for operation in (lambda: store.get(BOB, board_id), lambda: store.preview(BOB, draft["preview_id"]),
                      lambda: store.confirm(BOB, draft["preview_id"], "key")):
        with pytest.raises(AnalyticsError) as error:
            operation()
        assert error.value.status == 404
    revoked = AnalyticsPrincipal("alice", CAPS, frozenset({DATA_SCOPE}))
    assert store.list(revoked) == []
    for operation in (lambda: store.get(revoked, board_id), lambda: store.confirm(revoked, draft["preview_id"], "confirm")):
        with pytest.raises(AnalyticsError) as error:
            operation()
        assert error.value.status == 403
    readonly = AnalyticsPrincipal("alice", frozenset({"dashboard:read"}), ALICE.data_scopes)
    assert store.get(readonly, board_id) == v1
    with pytest.raises(AnalyticsError) as error:
        store.confirm(readonly, draft["preview_id"], "confirm")
    assert error.value.status == 403
    with closing(sqlite3.connect(store.path)) as conn:
        conn.execute("UPDATE revisions SET payload='{}'")
        conn.commit()
    with pytest.raises(AnalyticsError, match="BINDING_CORRUPT"):
        store.get(ALICE, board_id)


def test_layout_is_exact_and_validated_before_publication(tmp_path):
    store = BoardDocumentStore(private(tmp_path / "boards"))
    v1 = confirm(store, store.generate(ALICE, text_draft()))
    board_id = v1["spec"]["board_id"]
    change = {"base_version": 1, "layouts": [{"block_id": "note", "layout": {"x": 1, "y": 6, "w": 5, "h": 8}}]}
    preview = store.layout(ALICE, board_id, BoardLayoutPreview.model_validate(change))
    assert preview["snapshot"]["spec"]["blocks"][0]["layout"] == change["layouts"][0]["layout"]
    assert preview["snapshot"]["spec"]["blocks"][1] == v1["spec"]["blocks"][1]
    assert store.get(ALICE, board_id) == v1
    bad = deepcopy(change)
    bad["layouts"][0]["layout"] = {"x": 5, "y": 0, "w": 6, "h": 5}
    with pytest.raises(AnalyticsError, match="INVALID_BOARD"):
        store.layout(ALICE, board_id, BoardLayoutPreview.model_validate(bad))
    assert confirm(store, preview, "layout")["spec"]["blocks"][0]["layout"] == change["layouts"][0]["layout"]


@pytest.mark.parametrize("mutate", [
    lambda body: body.update(owner="alice"),
    lambda body: body.update(facts_by_result_id={"r1": {"value": 999}}),
    lambda body: body["blocks"][0]["props"].update(script="alert(1)"),
    lambda body: body["blocks"][0]["props"].update(tone="custom-purple"),
    lambda body: body["blocks"][0]["layout"].update(x=True),
    lambda body: body["blocks"][0]["layout"].update(w=2),
    lambda body: body["blocks"][0].update(kind="arbitrary-html"),
    lambda body: body["blocks"][0].update(library_version="future/v2"),
    lambda body: body["blocks"][1].update(block_id="note"),
])
def test_contract_rejects_untrusted_fields_and_invalid_values(mutate):
    body = text_draft().model_dump(mode="json")
    mutate(body)
    with pytest.raises(ValidationError):
        BoardDraft.model_validate(body)


@pytest.mark.parametrize("facts_version", [1, 2, 3, 4, 5])
def test_actual_http_computed_binding_permissions_and_reopen(tmp_path, source, facts_version):
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, ALICE)
    diagnosis = private(tmp_path / "diagnosis")
    boards = private(tmp_path / "boards")
    computed = ComputedResultStore(diagnosis)
    result = compute_result(source, ALICE, condition(), "diag.gsv", session_id="s1", request_id="r1")
    if facts_version < 5:
        # Valid legacy wire schemas remain readable; never infer daily points from their totals.
        payload = result.model_dump(mode="json")
        payload["facts"].pop("current_purchase_frequency")
        payload["facts"]["current"].pop("customer_count_unavailable_reason")
        payload["facts"]["comparison"].pop("customer_count_unavailable_reason")
        if facts_version < 4:
            payload["facts"].pop("channel_bridge")
        if facts_version < 3:
            payload["facts"].pop("current_daily")
        if facts_version == 1:
            payload["facts"].pop("money_unit")
        payload["existing_result_schema"] = payload["facts"]["schema_version"] = f"competition-gsv-facts/v{facts_version}"
        payload["facts_schema_ref"] = "backend.contracts.competition_computed.CompetitionGsvFacts" + (f"V{facts_version}" if facts_version > 1 else "")
        payload["evidence_digest"] = content_hash(evidence_payload(payload))
        payload["page"]["checksum"] = payload["evidence_digest"]
        result = CompetitionComputedResult.model_validate(payload)
    saved = computed.save(ALICE, "s1", "r1", "a" * 64, result)
    app = create_competition_app(identities=registry, diagnosis_source=source, diagnosis_state_dir=diagnosis, board_state_dir=boards)
    headers = {"Authorization": "Bearer " + TOKEN}
    body = text_draft().model_dump(mode="json")
    body["blocks"][0].update(kind="METRIC", source_result_id=saved.result_id, props={})
    with TestClient(app) as client:
        assert client.get(PREFIX + "/boards").status_code == 401
        assert client.get(PREFIX + "/context?session_id=s1").status_code == 401
        context = client.get(PREFIX + "/context?session_id=s1", headers=headers)
        assert context.status_code == 200 and context.headers["cache-control"] == "no-store"
        assert context.json()["session_id"] == "s1"
        assert [row["result_id"] for row in context.json()["results"]] == [saved.result_id]
        assert context.json()["results"][0]["supported_components"] == (["METRIC", "BAR", "TABLE", "EVIDENCE"]
            + (["LINE"] if facts_version >= 3 else []) + (["FUNNEL"] if facts_version >= 5 else []))
        assert client.get(PREFIX + "/context?session_id=s2", headers=headers).json()["results"] == []
        bad = deepcopy(body)
        bad["session_id"] = "s2"
        assert client.post(PREFIX + "/previews", headers=headers, json=bad).status_code == 404
        response = client.post(PREFIX + "/previews", headers=headers, json=body)
        assert response.status_code == 201, response.text
        assert response.headers["cache-control"] == "no-store"
        preview = response.json()
        endpoint = PREFIX + "/previews/" + preview["preview_id"]
        assert client.get(PREFIX + "/boards", headers=headers).json() == {"items": []}
        assert client.post(endpoint + "/confirm", headers=headers).status_code == 428
        response = client.post(endpoint + "/confirm", headers={**headers, "Idempotency-Key": "save"})
        assert response.status_code == 200, response.text
        snapshot = response.json()
        facts = snapshot["facts_by_result_id"][saved.result_id]
        assert facts["scalar"]["value"] == saved.facts.current.gsv
        assert facts["scalar"]["unit"] is None and facts["series"]["ordered"] is False
        if facts_version >= 3:
            assert facts["time_series"]["ordered"] is True and len(facts["time_series"]["points"]) == 31
        else:
            assert "time_series" not in facts
        assert facts["evidence"]["items"][1]["value"] == saved.evidence_digest
        board_id = snapshot["spec"]["board_id"]
        request = {"base_version": 1, "block_id": "note", "changes": {"title": "仅改标题"}}
        response = client.post(PREFIX + f"/boards/{board_id}/patch-preview", headers=headers, json=request)
        assert response.status_code == 201, response.text
        assert response.json()["snapshot"]["facts_by_result_id"] == snapshot["facts_by_result_id"]
        request["changes"] = {"kind": "LINE", "layout": {"x": 0, "y": 0, "w": 6, "h": 7}, "props": {}}
        response = client.post(PREFIX + f"/boards/{board_id}/patch-preview", headers=headers, json=request)
        if facts_version >= 3:
            assert response.status_code == 201, response.text
            assert response.json()["snapshot"]["facts_by_result_id"] == snapshot["facts_by_result_id"]
        else:
            assert response.status_code == 422 and response.json()["error"]["code"] == "COMPONENT_DATA"
        registry.revoke(TOKEN)
        assert client.get(PREFIX + f"/boards/{board_id}", headers=headers).status_code == 401
    registry.grant(TOKEN, ALICE)
    # Recreate HTTP app without computation source: durable reads remain operational.
    with TestClient(create_competition_app(identities=registry, board_state_dir=boards)) as client:
        assert client.get(PREFIX + f"/boards/{board_id}", headers=headers).json() == snapshot


def test_oversized_daily_range_excludes_line_without_losing_summary_or_requery(tmp_path, source):
    from backend.services.analytics.board_result_adapter import board_generation_context
    query = condition(comparison_mode="CUSTOM_DUAL_WINDOW", current_period={
        "start_date": "2025-01-01", "end_date": "2026-08-31", "end_bound": "INCLUSIVE_CALENDAR_DAY"})
    computed = ComputedResultStore(private(tmp_path / "diagnosis"))
    result = compute_result(source, ALICE, query, "diag.gsv", session_id="s1", request_id="r1")
    saved = computed.save(ALICE, "s1", "r1", "a" * 64, result)
    before = computed.path.read_bytes()
    context = board_generation_context(computed, ALICE, "s1")
    assert context["results"][0]["facts"]["current_daily"]["status"] == "UNSUPPORTED_RANGE"
    assert "LINE" not in context["results"][0]["supported_components"]
    store = BoardDocumentStore(private(tmp_path / "boards"), resolve_facts=computed_board_resolver(computed))
    draft = text_draft().model_dump(mode="json")
    draft["blocks"][0].update(kind="METRIC", props={}, source_result_id=saved.result_id)
    preview = store.generate(ALICE, BoardDraft.model_validate(draft))
    assert preview["snapshot"]["facts_by_result_id"][saved.result_id]["scalar"]["value"] == saved.facts.current.gsv
    draft["blocks"][0].update(kind="LINE", layout={"x": 0, "y": 0, "w": 6, "h": 7})
    with pytest.raises(AnalyticsError) as error:
        store.generate(ALICE, BoardDraft.model_validate(draft))
    assert error.value.code == "COMPONENT_DATA"
    assert computed.path.read_bytes() == before


def test_catalogue_is_session_owner_scoped_paginated_and_read_only(tmp_path, source):
    from backend.services.analytics.board_result_adapter import board_generation_context
    computed = ComputedResultStore(private(tmp_path / "diagnosis"))
    expected = set()
    for index in range(22):
        request_id = f"request-{index}"
        result = compute_result(source, ALICE, condition(), "diag.gsv", session_id="s1", request_id=request_id)
        expected.add(computed.save(ALICE, "s1", request_id, "a" * 64, result).result_id)
    before = computed.path.read_bytes()
    first = board_generation_context(computed, ALICE, "s1")
    assert len(first["results"]) == 20 and first["has_more"] is True and first["next_offset"] == 20
    second = board_generation_context(computed, ALICE, "s1", offset=first["next_offset"])
    assert len(second["results"]) == 2 and second["has_more"] is False and second["next_offset"] is None
    assert {row["result_id"] for row in first["results"] + second["results"]} == expected
    assert board_generation_context(computed, BOB, "s1")["results"] == []
    assert board_generation_context(computed, ALICE, "s2")["results"] == []
    first["catalog"]["components"].clear()
    assert board_generation_context(computed, ALICE, "s1")["catalog"] == CATALOG
    assert computed.path.read_bytes() == before  # Listing neither queries nor writes.
    for actor in (AnalyticsPrincipal("alice", frozenset({"analysis:read"}), ALICE.data_scopes),
                  AnalyticsPrincipal("alice", CAPS, frozenset())):
        with pytest.raises(AnalyticsError) as error:
            board_generation_context(computed, actor, "s1")
        assert error.value.status == 403
    for offset in (-1, True, 1000001):
        with pytest.raises(AnalyticsError):
            board_generation_context(computed, ALICE, "s1", offset=offset)


def test_each_component_catalogue_matches_backend_defaults_and_source_rules(tmp_path):
    store = BoardDocumentStore(private(tmp_path / "boards"))
    for definition in CATALOG["components"]:
        kind = definition["kind"]
        body = {"title": kind, "session_id": "s1", "blocks": [{"block_id": "block", "kind": kind,
            "title": kind, "layout": {"x": 0, "y": 0, **definition["default_size"]}}]}
        if definition["requires_result"]:
            with pytest.raises(ValidationError):
                BoardDraft.model_validate(body)
            body["blocks"][0]["source_result_id"] = "r1"
        draft = BoardDraft.model_validate(body)
        expected = {key: rule["default"] for key, rule in {**CATALOG["common_properties"], **definition["properties"]}.items()}
        assert draft.blocks[0].props.model_dump() == expected
        if definition["requires_result"]:
            with pytest.raises(AnalyticsError, match="RESULT_UNAVAILABLE"):
                store.generate(ALICE, draft)
        else:
            assert store.generate(ALICE, draft)["snapshot"]["facts_by_result_id"] == {}


STRUCTURED_CASES = json.loads((ROOT / "dsh-plugins/analytics-workbench/tests/structured-component-cases.json").read_text())


@pytest.mark.parametrize("case", STRUCTURED_CASES, ids=lambda case: case["name"])
def test_structured_components_share_the_javascript_validation_cases(case):
    body = text_draft().model_dump(mode="json")
    body["blocks"][0].update(kind=case["kind"], props=case["props"])
    if case["valid"]:
        assert BoardDraft.model_validate(body).blocks[0].kind == case["kind"]
    else:
        with pytest.raises(ValidationError):
            BoardDraft.model_validate(body)


@pytest.mark.parametrize("kind,props,changes", [
    ("PROCESS", {"nodes": [{"id": "a", "label": "核对"}, {"id": "b", "label": "确认"}],
                 "edges": [{"from": "a", "to": "b", "label": "通过"}]},
                {"nodes": [{"id": "a", "label": "核对口径", "owner": "分析师"}, {"id": "b", "label": "确认"}]}),
    ("TIMELINE", {"events": [{"id": "a", "date": "2026-09-13", "label": "讨论"}]},
                 {"events": [{"id": "a", "date": "2026-09-14", "label": "调整讨论日期"},
                             {"id": "b", "date": "2026-09-14", "label": "同日评审"}]}),
])
def test_structured_edit_cancel_confirm_process_reopen_and_rollback(tmp_path, kind, props, changes):
    body = text_draft().model_dump(mode="json")
    body["blocks"][0].update(kind=kind, props=props)
    directory = private(tmp_path / "boards")
    def never_resolve(*args):
        pytest.fail("planning edits must not query or borrow facts")
    store = BoardDocumentStore(directory, resolve_facts=never_resolve)
    v1 = confirm(store, store.generate(ALICE, BoardDraft.model_validate(body)))
    board_id = v1["spec"]["board_id"]
    # Shared authenticated-edit service, not a second planning-only persistence path.
    def propose(current):
        context = store.select_edit(ALICE, board_id, BoardEditSelection(base_version=current, block_id="note"))
        return store.propose_edit(ALICE, context["edit_context_id"], BoardEditProposal.model_validate({
            "session_id": "s1", "changes": {"props": changes}}))
    pending = propose(1)
    assert store.get(ALICE, board_id) == v1
    store.cancel(ALICE, pending["preview_id"])
    assert store.get(ALICE, board_id) == v1
    v2 = confirm(store, propose(1), "apply-structured")
    assert v2["spec"]["blocks"][0]["props"] != v1["spec"]["blocks"][0]["props"]
    assert v2["spec"]["blocks"][1] == v1["spec"]["blocks"][1]
    assert v2["facts_by_result_id"] == {}
    script = """
import json, sys
from pathlib import Path
from backend.services.analytics.access import AnalyticsPrincipal
from backend.services.analytics.board_documents import BoardDocumentStore
actor=AnalyticsPrincipal('alice',frozenset({'dashboard:read'}),frozenset({'competition-diagnosis-fixture'}))
print(json.dumps(BoardDocumentStore(Path(sys.argv[1])).get(actor,sys.argv[2])))
"""
    result = subprocess.run([sys.executable, "-c", script, str(directory), board_id], cwd=tmp_path,
        env={"PATH": str(Path(sys.executable).parent) + ":/usr/bin:/bin", "PYTHONPATH": str(ROOT),
             "PYTHONNOUSERSITE": "1", "PYTHON_DOTENV_DISABLED": "1"},
        capture_output=True, text=True, timeout=30, check=True)
    assert json.loads(result.stdout) == v2
    reopened = BoardDocumentStore(directory)
    preview = reopened.rollback(ALICE, board_id, BoardRollbackPreview(base_version=2, to_version=1))
    v3 = confirm(reopened, preview, "restore-structured")
    assert v3["spec"]["blocks"] == v1["spec"]["blocks"] and v3["spec"]["version"] == 3
    assert [entry["version"] for entry in reopened.history(ALICE, board_id)] == [3, 2, 1]


def test_structured_patch_revalidates_retained_edges_and_rejects_borrowed_results(tmp_path):
    body = text_draft().model_dump(mode="json")
    body["blocks"][0].update(kind="PROCESS", props={"nodes": [{"id": "a", "label": "甲"}, {"id": "b", "label": "乙"}],
                                                 "edges": [{"from": "a", "to": "b"}]})
    store = BoardDocumentStore(private(tmp_path / "boards"))
    saved = confirm(store, store.generate(ALICE, BoardDraft.model_validate(body)))
    board_id = saved["spec"]["board_id"]
    for changes in ({"props": {"nodes": [{"id": "a", "label": "甲"}]}}, {"source_result_id": "borrowed"},
                    {"props": {"edges": [{"from": "a", "to": "b", "script": "run()"}]}}):
        with pytest.raises(AnalyticsError, match="INVALID_BOARD"):
            store.patch(ALICE, board_id, patch(1, **changes))
        assert store.get(ALICE, board_id) == saved
    for kind in ("PROCESS", "TIMELINE"):
        body["blocks"][0].update(kind=kind, props={}, source_result_id="borrowed")
        with pytest.raises(ValidationError):
            BoardDraft.model_validate(body)


def test_foreign_or_linked_state_is_never_reinitialized(tmp_path):
    directory = private(tmp_path / "boards")
    path = directory / "board_documents.sqlite3"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE valuable(value TEXT)")
        conn.execute("INSERT INTO valuable VALUES ('keep')")
        conn.commit()
    before = path.read_bytes()
    with pytest.raises(ValueError):
        BoardDocumentStore(directory)
    assert path.read_bytes() == before
    linked = private(tmp_path / "linked")
    os.symlink(path, linked / "board_documents.sqlite3")
    with pytest.raises(ValueError):
        BoardDocumentStore(linked)
    assert path.read_bytes() == before


def test_computed_adapter_does_not_query_or_invent_currency():
    class Missing:
        def get_result(self, *args):
            raise AnalyticsError(404, "NOT_FOUND", "不可见")
    with pytest.raises(AnalyticsError, match="NOT_FOUND"):
        computed_board_resolver(Missing())(ALICE, "s1", "r1")


def test_http_uses_the_offline_contract_and_unicode_limits():
    schema = create_competition_app().openapi()
    offline = board_spec_openapi()["components"]["schemas"]
    for name in ("BoardDraft", "BoardPatchPreview", "BoardLayoutPreview", "BoardRollbackPreview",
                 "BoardEditSelection", "BoardEditProposal", "BoardEditContext", "BoardCurrentEdit"):
        assert schema["components"]["schemas"][name] == offline[name]
    paths = schema["paths"]
    for path, model in (("/previews", "BoardDraft"), ("/boards/{board_id}/patch-preview", "BoardPatchPreview"),
                        ("/boards/{board_id}/layout-preview", "BoardLayoutPreview"),
                        ("/boards/{board_id}/edit-context", "BoardEditSelection"),
                        ("/edit-contexts/{context_id}/propose", "BoardEditProposal"),
                        ("/boards/{board_id}/rollback-preview", "BoardRollbackPreview")):
        assert paths[PREFIX + path]["post"]["requestBody"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/" + model}
    body = text_draft().model_dump(mode="json")
    body["blocks"][0]["props"]["content"] = "🌱" * 4000
    assert BoardDraft.model_validate(body).blocks[0].props.content == "🌱" * 4000
    body["blocks"][0]["props"]["content"] += "🌱"
    with pytest.raises(ValidationError):
        BoardDraft.model_validate(body)


@pytest.mark.parametrize("kind,changes", [
    ("METRIC", {"value_format": "compact", "show_comparison": False}),
    ("LINE", {"line_style": "dashed", "show_points": False}),
    ("BAR", {"orientation": "vertical", "show_values": False}),
    ("TABLE", {"columns": ["value"], "page_size": 5, "sort_field": "value", "sort_direction": "desc"}),
    ("TEXT", {"content": "只更新选中的说明", "align": "center"}),
    ("EVIDENCE", {"summary": "核对时间范围", "expanded": True}),
])
def test_selected_edit_six_kinds_reuse_facts_and_preserve_every_other_component(tmp_path, kind, changes):
    calls = []
    def resolver(actor, session_id, result_id):
        calls.append((actor.actor_id, session_id, result_id))
        return ResolvedBoardFacts({"schema_version": "board-component-facts/v1",
            "scalar": {"value": 42, "unit": None},
            "series": {"ordered": True, "points": [{"label": "2026-08-01", "value": 42}], "unit": None},
            "table": {"columns": [{"key": "value", "label": "金额"}], "rows": [{"value": 42}]},
            "evidence": {"source": "synthetic", "items": []}}, frozenset({"brand-a"}))
    directory = private(tmp_path / "boards")
    store = BoardDocumentStore(directory, resolve_facts=resolver)
    body = text_draft().model_dump(mode="json")
    definition = next(item for item in CATALOG["components"] if item["kind"] == kind)
    body["blocks"][0].update(kind=kind, props={}, layout={"x": 0, "y": 0, **definition["default_size"]})
    body["blocks"][1]["layout"]["y"] = 10
    if kind != "TEXT":
        body["blocks"][0]["source_result_id"] = "result_old"
    saved = confirm(store, store.generate(ALICE, BoardDraft.model_validate(body)))
    calls.clear()
    board_id = saved["spec"]["board_id"]
    context = store.select_edit(ALICE, board_id, BoardEditSelection(base_version=1, block_id="note"))
    context_id = context["edit_context_id"]
    assert context["block"] == saved["spec"]["blocks"][0]
    assert context["session_id"] == "s1" and context["status"] == "OPEN"
    # Context remains valid after reopening the service, with no result resolver.
    reopened = BoardDocumentStore(directory)
    assert reopened.edit_context(ALICE, context_id, session_id="s1") == context
    proposed = reopened.propose_edit(ALICE, context_id, BoardEditProposal.model_validate({
        "session_id": "s1", "changes": {"props": changes}}))
    assert proposed["operation"] == "PATCH" and store.get(ALICE, board_id) == saved
    assert proposed["snapshot"]["spec"]["blocks"][1] == saved["spec"]["blocks"][1]
    assert proposed["snapshot"]["facts_by_result_id"] == saved["facts_by_result_id"] and calls == []
    updated = confirm(reopened, proposed, "apply-edit")
    assert updated["spec"]["blocks"][0]["props"].items() >= changes.items()
    assert store.get(ALICE, board_id) == updated
    assert confirm(store, proposed, "apply-edit") == updated
    assert len(store.history(ALICE, board_id)) == 2


def test_edit_cancel_expiry_session_permissions_and_no_silent_switch(tmp_path):
    instant = [100]
    store = BoardDocumentStore(private(tmp_path / "boards"), clock=lambda: instant[0])
    saved = confirm(store, store.generate(ALICE, text_draft()))
    board_id = saved["spec"]["board_id"]
    selection = BoardEditSelection(base_version=1, block_id="note")
    context = store.select_edit(ALICE, board_id, selection)
    eid = context["edit_context_id"]
    proposal = BoardEditProposal.model_validate({"session_id": "s1", "changes": {"title": "修改"}})
    with pytest.raises(AnalyticsError, match="EDIT_PENDING"):
        store.select_edit(ALICE, board_id, BoardEditSelection(base_version=1, block_id="other"))
    for who, session in ((BOB, "s1"), (ALICE, "another-session")):
        with pytest.raises(AnalyticsError) as error:
            store.propose_edit(who, eid, proposal.model_copy(update={"session_id": session}))
        assert error.value.status == 404
    readonly = AnalyticsPrincipal("alice", frozenset({"dashboard:read"}), ALICE.data_scopes)
    for action in (lambda: store.edit_context(readonly, eid, session_id="s1"),
                   lambda: store.propose_edit(readonly, eid, proposal), lambda: store.cancel_edit(readonly, eid)):
        with pytest.raises(AnalyticsError) as error:
            action()
        assert error.value.status == 403
    preview = store.propose_edit(ALICE, eid, proposal)
    with pytest.raises(AnalyticsError, match="EDIT_PROPOSED"):
        store.propose_edit(ALICE, eid, proposal)
    store.cancel_edit(ALICE, eid)
    store.cancel_edit(ALICE, eid)
    with pytest.raises(AnalyticsError, match="EDIT_CANCELLED"):
        store.propose_edit(ALICE, eid, proposal)
    with pytest.raises(AnalyticsError, match="PREVIEW_CANCELLED"):
        confirm(store, preview, "late-save")
    next_context = store.select_edit(ALICE, board_id, selection)
    instant[0] = next_context["expires_at_ms"]
    with pytest.raises(AnalyticsError, match="EDIT_EXPIRED"):
        store.propose_edit(ALICE, next_context["edit_context_id"], proposal)
    next_context = store.select_edit(ALICE, board_id, selection)
    changed = confirm(store, store.patch(ALICE, board_id, patch(1, title="另一标签保存")), "other-tab")
    with pytest.raises(AnalyticsError, match="VERSION_CONFLICT"):
        store.propose_edit(ALICE, next_context["edit_context_id"], proposal)
    assert store.get(ALICE, board_id) == changed


def test_cancel_during_new_result_resolution_cannot_publish_late_edit(tmp_path):
    calls = []
    store = BoardDocumentStore(private(tmp_path / "boards"))
    saved = confirm(store, store.generate(ALICE, text_draft()))
    context = store.select_edit(ALICE, saved["spec"]["board_id"], BoardEditSelection(base_version=1, block_id="note"))
    def resolver(actor, session_id, result_id):
        calls.append((session_id, result_id))
        store.cancel_edit(ALICE, context["edit_context_id"])
        return ResolvedBoardFacts({"scalar": {"value": 99}}, frozenset())
    store.resolve_facts = resolver
    with pytest.raises(AnalyticsError, match="EDIT_CANCELLED"):
        store.propose_edit(ALICE, context["edit_context_id"], BoardEditProposal.model_validate({"session_id": "s1",
            "changes": {"kind": "METRIC", "source_result_id": "new_result", "props": {}}}))
    assert calls == [("s1", "new_result")]
    assert store.get(ALICE, saved["spec"]["board_id"]) == saved
    with closing(sqlite3.connect(store.path)) as conn:
        assert conn.execute("SELECT count(*) FROM previews").fetchone()[0] == 1


def test_selected_edit_http_binding_unknown_fields_and_cancel(tmp_path):
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, ALICE)
    directory = private(tmp_path / "boards")
    store = BoardDocumentStore(directory)
    saved = confirm(store, store.generate(ALICE, text_draft()))
    bid = saved["spec"]["board_id"]
    headers = {"Authorization": "Bearer " + TOKEN}
    with TestClient(create_competition_app(identities=registry, board_state_dir=directory)) as client:
        url = PREFIX + f"/boards/{bid}/edit-context"
        selection = {"base_version": 1, "block_id": "note"}
        assert client.post(url, json=selection).status_code == 401
        assert client.get(url).status_code == 401
        assert client.get(url, headers=headers).json() == {"context": None}
        assert client.post(url, headers=headers, json={**selection, "session_id": "forged"}).status_code == 422
        response = client.post(url, headers=headers, json=selection)
        assert response.status_code == 201 and response.headers["cache-control"] == "no-store"
        eid = response.json()["edit_context_id"]
        assert client.get(url, headers=headers).json()["context"]["edit_context_id"] == eid
        endpoint = PREFIX + f"/edit-contexts/{eid}"
        assert client.get(endpoint + "?session_id=s2", headers=headers).status_code == 404
        assert client.get(endpoint + "?session_id=s1", headers=headers).json() == response.json()
        body = {"session_id": "s1", "changes": {"title": "只改所选组件"}}
        for forged in ({"block_id": "other"}, {"owner": "bob"}, {"base_version": 999}):
            assert client.post(endpoint + "/propose", headers=headers, json={**body, **forged}).status_code == 422
        for changes in ({"blocks": []}, {"facts_by_result_id": {}}, {"props": {"script": "alert(1)"}}):
            assert client.post(endpoint + "/propose", headers=headers, json={**body, "changes": changes}).status_code == 422
        response = client.post(endpoint + "/propose", headers=headers, json=body)
        assert response.status_code == 201, response.text
        preview_id = response.json()["preview_id"]
        assert client.post(PREFIX + f"/previews/{preview_id}/cancel", headers=headers).status_code == 200
        assert client.get(url, headers=headers).json() == {"context": None}
        assert client.post(endpoint + "/propose", headers=headers, json=body).json()["error"]["code"] == "EDIT_CANCELLED"
        assert store.get(ALICE, bid) == saved


def test_edit_table_additive_install_preserves_saved_v1_and_rejects_unknown_extension(tmp_path):
    directory = private(tmp_path / "boards")
    store = BoardDocumentStore(directory)
    saved = confirm(store, store.generate(ALICE, text_draft()))
    with closing(sqlite3.connect(store.path)) as conn:
        before = conn.execute("SELECT * FROM revisions").fetchall()
        # Isolated fixture reproduces the pre-edit-context v1 physical schema.
        conn.execute("DROP TABLE edit_contexts")
        conn.execute("DELETE FROM metadata WHERE key='edit_context_schema'")
        conn.commit()
    reopened = BoardDocumentStore(directory)
    assert reopened.get(ALICE, saved["spec"]["board_id"]) == saved
    with closing(sqlite3.connect(store.path)) as conn:
        assert conn.execute("SELECT * FROM revisions").fetchall() == before
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        conn.execute("UPDATE metadata SET value='future-version' WHERE key='edit_context_schema'")
        conn.commit()
    with pytest.raises(AnalyticsError, match="BINDING_CORRUPT"):
        BoardDocumentStore(directory)


def test_parallel_selection_and_proposals_do_not_replace_another_tabs_draft(tmp_path):
    directory = private(tmp_path / "boards")
    store = BoardDocumentStore(directory)
    saved = confirm(store, store.generate(ALICE, text_draft()))
    clients = [store, BoardDocumentStore(directory)]
    gate = Barrier(2)
    def attempt(index):
        gate.wait(timeout=5)
        try:
            return clients[index].select_edit(ALICE, saved["spec"]["board_id"],
                BoardEditSelection(base_version=1, block_id=["note", "other"][index]))
        except AnalyticsError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [0, 1]))
    assert results.count("EDIT_PENDING") == 1
    context = next(value for value in results if isinstance(value, dict))
    def propose(index):
        gate.wait(timeout=5)
        try:
            return clients[index].propose_edit(ALICE, context["edit_context_id"],
                BoardEditProposal.model_validate({"session_id": "s1", "changes": {"title": f"建议 {index}"}}))
        except AnalyticsError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(propose, [0, 1]))
    assert results.count("EDIT_PROPOSED") == 1
    assert store.get(ALICE, saved["spec"]["board_id"]) == saved
