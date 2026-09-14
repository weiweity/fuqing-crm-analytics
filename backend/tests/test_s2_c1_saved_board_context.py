"""S2-C1 plan B: catalog must expose the current session's saved board head."""
from contextlib import closing
import json
import sqlite3

from fastapi.testclient import TestClient
import pytest

from backend.analytics_competition_app import create_competition_app
from backend.contracts.board_spec import BoardDraft, BoardPatchPreview
from backend.contracts.competition_computed import DATA_SCOPE
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, B0IdentityRegistry
from backend.services.analytics.board_documents import BoardDocumentStore, ResolvedBoardFacts
from backend.services.analytics.board_result_adapter import board_generation_context, computed_board_resolver
from backend.services.analytics.competition_diagnosis.computed import compute_result
from backend.services.analytics.competition_diagnosis.store import ComputedResultStore
from backend.tests.test_board_documents import ALICE, BOB, CAPS, PREFIX, TOKEN, private
from backend.tests.test_competition_computed_results import condition, source as computed_source

source = computed_source


def hid(n):
    return f"{n:032x}"


def install_hexes(monkeypatch, values):
    leftover = list(values)

    class Token:
        def __init__(self, hex_value):
            self.hex = hex_value

    def factory():
        if not leftover:
            raise AssertionError("uuid4 exhausted")
        return Token(leftover.pop(0))

    monkeypatch.setattr("backend.services.analytics.board_documents.uuid4", factory)


def text_body(session_id="s1", title="经营看板"):
    return {"title": title, "session_id": session_id, "blocks": [
        {"block_id": "note", "kind": "TEXT", "title": "说明", "props": {"content": "旧内容"},
         "layout": {"x": 0, "y": 0, "w": 6, "h": 5}},
    ]}


def save_text(store, actor, session_id="s1", title="经营看板", key="save"):
    preview = store.generate(actor, BoardDraft.model_validate(text_body(session_id, title)))
    return store.confirm(actor, preview["preview_id"], key)


def summary_of(snapshot):
    spec = snapshot["spec"]
    return {"board_id": spec["board_id"], "title": spec["title"], "version": spec["version"]}


def test_generation_context_without_board_store_is_unknown_not_empty(tmp_path):
    computed = ComputedResultStore(private(tmp_path / "diagnosis"))
    context = board_generation_context(computed, ALICE, "s1")
    assert "saved_boards" not in context
    assert context["saved_boards_status"] == "unavailable"


def test_confirm_v2_context_and_catalog_use_committed_head(tmp_path, source):
    computed = ComputedResultStore(private(tmp_path / "diagnosis"))
    store = BoardDocumentStore(private(tmp_path / "boards"), resolve_facts=computed_board_resolver(computed))
    initial = store.generate(ALICE, BoardDraft.model_validate(text_body(title="原板")))
    assert board_generation_context(computed, ALICE, "s1", board_store=store)["saved_boards"] == []
    assert board_generation_context(computed, ALICE, "s1", board_store=store)["saved_boards_status"] == "complete"
    v1 = store.confirm(ALICE, initial["preview_id"], "v1")
    board_id = v1["spec"]["board_id"]
    pending = store.patch(ALICE, board_id, BoardPatchPreview.model_validate(
        {"base_version": 1, "block_id": "note", "changes": {"title": "新标题"}}))
    assert pending["status"] == "PENDING"
    mid = board_generation_context(computed, ALICE, "s1", board_store=store)
    assert mid["saved_boards"] == [summary_of(v1)]
    store.cancel(ALICE, pending["preview_id"])
    assert board_generation_context(computed, ALICE, "s1", board_store=store)["saved_boards"] == [summary_of(v1)]
    edit = store.patch(ALICE, board_id, BoardPatchPreview.model_validate(
        {"base_version": 1, "block_id": "note", "changes": {"title": "新标题"}}))
    v2 = store.confirm(ALICE, edit["preview_id"], "v2")
    stale = store.confirm(ALICE, initial["preview_id"], "v1")
    assert stale["spec"]["version"] == 1
    context = board_generation_context(computed, ALICE, "s1", board_store=store)
    assert context["saved_boards"] == [summary_of(v2)]
    assert context["saved_boards"][0]["version"] == 2
    assert set(context["saved_boards"][0]) == {"board_id", "title", "version"}
    dumped = json.dumps(context["saved_boards"])
    assert "facts" not in dumped and "required_scopes" not in dumped and "payload" not in dumped
    draft = store.generate(ALICE, BoardDraft.model_validate(text_body(title="另一份草稿")))
    assert draft["snapshot"]["spec"]["board_id"] != board_id
    after_generate = board_generation_context(computed, ALICE, "s1", board_store=store)
    assert after_generate["saved_boards"] == [summary_of(v2)]
    store.cancel(ALICE, draft["preview_id"])
    assert board_generation_context(computed, ALICE, "s1", board_store=store)["saved_boards"] == [summary_of(v2)]
    reopened = BoardDocumentStore(store.path.parent)
    assert board_generation_context(computed, ALICE, "s1", board_store=reopened)["saved_boards"] == [summary_of(v2)]


def test_http_context_wires_real_board_store_after_confirm_v2(tmp_path, source):
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, ALICE)
    diagnosis = private(tmp_path / "diagnosis")
    boards = private(tmp_path / "boards")
    headers = {"Authorization": "Bearer " + TOKEN}
    app = create_competition_app(identities=registry, diagnosis_source=source,
                                 diagnosis_state_dir=diagnosis, board_state_dir=boards)
    with TestClient(app) as client:
        empty = client.get(PREFIX + "/context?session_id=s1", headers=headers)
        assert empty.status_code == 200, empty.text
        assert empty.json()["saved_boards"] == []
        assert empty.json()["saved_boards_status"] == "complete"
        created = client.post(PREFIX + "/previews", headers=headers, json=text_body(title="原板"))
        assert created.status_code == 201, created.text
        preview = created.json()
        saved = client.post(PREFIX + "/previews/" + preview["preview_id"] + "/confirm",
                            headers={**headers, "Idempotency-Key": "v1"})
        assert saved.status_code == 200, saved.text
        board_id = saved.json()["spec"]["board_id"]
        patched = client.post(PREFIX + f"/boards/{board_id}/patch-preview", headers=headers, json={
            "base_version": 1, "block_id": "note", "changes": {"title": "v2 标题"}})
        assert patched.status_code == 201, patched.text
        assert client.get(PREFIX + "/context?session_id=s1", headers=headers).json()["saved_boards"] == [
            {"board_id": board_id, "title": "原板", "version": 1}]
        v2 = client.post(PREFIX + "/previews/" + patched.json()["preview_id"] + "/confirm",
                         headers={**headers, "Idempotency-Key": "v2"})
        assert v2.status_code == 200, v2.text
        context = client.get(PREFIX + "/context?session_id=s1", headers=headers).json()
        assert context["saved_boards"] == [{"board_id": board_id, "title": "原板", "version": 2}]
        later = client.get(PREFIX + "/context?session_id=s1&offset=0", headers=headers).json()
        assert later["saved_boards"] == context["saved_boards"]
        other = client.post(PREFIX + "/previews", headers=headers, json=text_body(title="新草稿"))
        assert other.status_code == 201, other.text
        assert other.json()["snapshot"]["spec"]["board_id"] != board_id
        assert other.json()["status"] == "PENDING"
        assert client.get(PREFIX + "/context?session_id=s1", headers=headers).json()["saved_boards"] == [
            {"board_id": board_id, "title": "原板", "version": 2}]


def test_saved_summaries_are_owner_session_and_scope_isolated(tmp_path, monkeypatch):
    store = BoardDocumentStore(private(tmp_path / "boards"), resolve_facts=lambda actor, session_id, result_id: (
        ResolvedBoardFacts({"schema_version": "board-component-facts/v1", "scalar": {"value": 42, "unit": None}},
                           frozenset({"brand-a"}))))
    install_hexes(monkeypatch, [hid(1), hid(101), hid(2), hid(102), hid(3), hid(103), hid(4), hid(104)])
    alice_s1 = save_text(store, ALICE, "s1", "Alice s1", "a-s1")
    save_text(store, ALICE, "s2", "Alice s2", "a-s2")
    save_text(store, BOB, "s1", "Bob s1", "b-s1")
    metric = text_body("s1", "受限")
    metric["blocks"][0].update(kind="METRIC", source_result_id="r1", props={})
    scoped = store.confirm(ALICE, store.generate(ALICE, BoardDraft.model_validate(metric))["preview_id"], "scoped")
    visible = board_generation_context(ComputedResultStore(private(tmp_path / "diagnosis")), ALICE, "s1",
                                       board_store=store)
    assert {item["board_id"] for item in visible["saved_boards"]} == {
        alice_s1["spec"]["board_id"], scoped["spec"]["board_id"]}
    other_session = board_generation_context(ComputedResultStore(private(tmp_path / "s2-diagnosis")), ALICE, "s2",
                                             board_store=store)
    assert other_session["saved_boards"] == [{"board_id": "board_" + hid(2), "title": "Alice s2", "version": 1}]
    bob = board_generation_context(ComputedResultStore(private(tmp_path / "bob-diagnosis")), BOB, "s1",
                                   board_store=store)
    assert bob["saved_boards"] == [{"board_id": "board_" + hid(3), "title": "Bob s1", "version": 1}]
    revoked = AnalyticsPrincipal("alice", CAPS, frozenset({DATA_SCOPE}))
    remaining = store.list_session_saved_summaries(revoked, "s1")
    assert remaining["items"] == [summary_of(alice_s1)]
    assert remaining["status"] == "complete"
    readonly = AnalyticsPrincipal("alice", frozenset({"dashboard:read", "analysis:read"}), ALICE.data_scopes)
    assert store.list_session_saved_summaries(readonly, "s1")["items"][-1]["board_id"] == scoped["spec"]["board_id"]
    with pytest.raises(AnalyticsError) as error:
        store.list_session_saved_summaries(
            AnalyticsPrincipal("alice", frozenset({"analysis:read"}), ALICE.data_scopes), "s1")
    assert error.value.status == 403


def test_later_page_and_permission_short_page_are_not_complete_empty(tmp_path, monkeypatch):
    store = BoardDocumentStore(private(tmp_path / "boards"), resolve_facts=lambda actor, session_id, result_id: (
        ResolvedBoardFacts({"schema_version": "board-component-facts/v1", "scalar": {"value": 1, "unit": None}},
                           frozenset({"brand-a"}))))
    install_hexes(monkeypatch, [hid(n) for pair in range(1, 6) for n in (pair, 100 + pair)])
    save_text(store, ALICE, "s0", "filler-1", "f1")
    save_text(store, ALICE, "s0", "filler-2", "f2")
    target = save_text(store, ALICE, "s1", "目标会话", "target")
    naive = [item for item in store.list(ALICE, limit=2, offset=0) if item["session_id"] == "s1"]
    assert naive == []
    listed = store.list_session_saved_summaries(ALICE, "s1", page_size=2, scan_limit=10)
    assert listed["items"] == [summary_of(target)]
    assert listed["status"] == "complete"
    install_hexes(monkeypatch, [hid(n) for pair in range(10, 14) for n in (pair, 200 + pair)])
    for index, title in enumerate(("拒1", "拒2"), start=1):
        body = text_body("s1", title)
        body["blocks"][0].update(kind="METRIC", source_result_id="r1", props={})
        store.confirm(ALICE, store.generate(ALICE, BoardDraft.model_validate(body))["preview_id"], f"deny-{index}")
    visible = save_text(store, ALICE, "s1", "可见", "visible")
    revoked = AnalyticsPrincipal("alice", CAPS, frozenset({DATA_SCOPE}))
    short = store.list(revoked, limit=2, offset=0)
    assert all(item["session_id"] != "s1" or item["board_id"] != visible["spec"]["board_id"] for item in short)
    recovered = store.list_session_saved_summaries(revoked, "s1", page_size=2, scan_limit=20)
    assert summary_of(visible) in recovered["items"]
    assert recovered["status"] == "complete"
    truncated = store.list_session_saved_summaries(ALICE, "s0", page_size=1, scan_limit=1)
    assert truncated["status"] == "truncated"
    assert truncated["items"] != [] or truncated["status"] != "complete"


def test_corrupt_or_failed_store_is_unknown_not_authoritative_empty(tmp_path):
    computed = ComputedResultStore(private(tmp_path / "diagnosis"))
    directory = private(tmp_path / "boards")
    store = BoardDocumentStore(directory)
    first = save_text(store, ALICE, "s1", "完好", "ok")
    second = save_text(store, ALICE, "s2", "损坏会话", "bad")
    with closing(sqlite3.connect(store.path)) as conn:
        conn.execute("UPDATE revisions SET payload='{}' WHERE board_id=?", (second["spec"]["board_id"],))
        conn.commit()
    damaged = store.list_session_saved_summaries(ALICE, "s2")
    assert damaged["status"] == "unknown"
    assert damaged["items"] == []
    intact = store.list_session_saved_summaries(ALICE, "s1")
    assert intact["items"] == [summary_of(first)]
    store.path.write_bytes(b"not-a-sqlite-database")
    context = board_generation_context(computed, ALICE, "s1", board_store=store)
    assert "saved_boards" not in context
    assert context["saved_boards_status"] == "unavailable"
    assert context["results"] == []


def test_missing_revision_head_is_unknown_not_complete_empty(tmp_path):
    computed = ComputedResultStore(private(tmp_path / "diagnosis"))
    orphan_store = BoardDocumentStore(private(tmp_path / "orphan"))
    orphan = save_text(orphan_store, ALICE, "orphan", "仅损坏", "orphan")
    with closing(sqlite3.connect(orphan_store.path)) as conn:
        deleted = conn.execute("DELETE FROM revisions WHERE board_id=?", (orphan["spec"]["board_id"],)).rowcount
        heads = conn.execute("SELECT count(*) FROM heads WHERE board_id=?", (orphan["spec"]["board_id"],)).fetchone()[0]
        conn.commit()
    assert deleted == 1 and heads == 1
    with pytest.raises(AnalyticsError) as error:
        orphan_store.get(ALICE, orphan["spec"]["board_id"])
    assert error.value.code == "NOT_FOUND"
    empty_missing = board_generation_context(computed, ALICE, "orphan", board_store=orphan_store)
    assert empty_missing["saved_boards"] == []
    assert empty_missing["saved_boards_status"] == "unknown"

    mixed_store = BoardDocumentStore(private(tmp_path / "mixed"))
    missing = save_text(mixed_store, ALICE, "s3", "缺revision", "gone")
    mixed_ok = save_text(mixed_store, ALICE, "s3", "同会话完好", "keep")
    with closing(sqlite3.connect(mixed_store.path)) as conn:
        conn.execute("DELETE FROM revisions WHERE board_id=?", (missing["spec"]["board_id"],))
        conn.commit()
    mixed = mixed_store.list_session_saved_summaries(ALICE, "s3")
    assert mixed["items"] == [summary_of(mixed_ok)]
    assert mixed["status"] == "unknown"

    drift_store = BoardDocumentStore(private(tmp_path / "drift"))
    drifted = save_text(drift_store, ALICE, "s4", "版本漂移", "drift")
    with closing(sqlite3.connect(drift_store.path)) as conn:
        conn.execute("UPDATE heads SET version=? WHERE board_id=?", (99, drifted["spec"]["board_id"]))
        conn.commit()
    with pytest.raises(AnalyticsError) as error:
        drift_store.get(ALICE, drifted["spec"]["board_id"])
    assert error.value.code == "NOT_FOUND"
    drifted_list = drift_store.list_session_saved_summaries(ALICE, "s4")
    assert drifted_list["items"] == []
    assert drifted_list["status"] == "unknown"


def test_default_paging_snapshot_stays_consistent_under_insert_and_upgrade(tmp_path, monkeypatch):
    store = BoardDocumentStore(private(tmp_path / "boards"))
    hexes = [hid(n) for pair in range(1, 102) for n in (pair, 1000 + pair)]
    hexes.extend([hid(0), hid(2000), hid(3000)])
    install_hexes(monkeypatch, hexes)
    for n in range(1, 100):
        save_text(store, ALICE, "s0", f"filler-{n}", f"f{n}")
    first = save_text(store, ALICE, "s1", "A", "a")
    second = save_text(store, ALICE, "s1", "B", "b")
    writer = BoardDocumentStore(store.path.parent)
    decode = store._decode
    inserted = {"done": False}

    def decode_then_insert(actor, row, *, version):
        snapshot = decode(actor, row, version=version)
        if not inserted["done"]:
            inserted["done"] = True
            save_text(writer, ALICE, "s1", "inserted-before-offset", "ins")
        return snapshot

    store._decode = decode_then_insert
    listed = store.list_session_saved_summaries(ALICE, "s1")
    ids = [item["board_id"] for item in listed["items"]]
    assert ids == [first["spec"]["board_id"], second["spec"]["board_id"]]
    assert len(set(ids)) == len(ids)
    assert listed["status"] == "complete"
    after = writer.list_session_saved_summaries(ALICE, "s1")
    assert {item["title"] for item in after["items"]} == {"A", "B", "inserted-before-offset"}
    assert after["status"] == "complete"

    upgraded_id = first["spec"]["board_id"]
    decode = writer._decode
    bumped = {"done": False}

    def decode_then_upgrade(actor, row, *, version):
        snapshot = decode(actor, row, version=version)
        if not bumped["done"] and row["board_id"] == upgraded_id:
            bumped["done"] = True
            preview = store.patch(ALICE, upgraded_id, BoardPatchPreview.model_validate(
                {"base_version": 1, "block_id": "note", "changes": {"title": "A2"}}))
            store.confirm(ALICE, preview["preview_id"], "upgrade")
        return snapshot

    writer._decode = decode_then_upgrade
    snapshot_list = writer.list_session_saved_summaries(ALICE, "s1")
    versions = [item["version"] for item in snapshot_list["items"] if item["board_id"] == upgraded_id]
    assert versions == [1]
    assert store.get(ALICE, upgraded_id)["spec"]["version"] == 2


def test_result_pagination_does_not_drop_saved_boards(tmp_path, source):
    computed = ComputedResultStore(private(tmp_path / "diagnosis"))
    store = BoardDocumentStore(private(tmp_path / "boards"))
    saved = save_text(store, ALICE, "s1", "分页并存", "page")
    for index in range(22):
        request_id = f"request-{index}"
        result = compute_result(source, ALICE, condition(), "diag.gsv", session_id="s1", request_id=request_id)
        computed.save(ALICE, "s1", request_id, "a" * 64, result)
    first = board_generation_context(computed, ALICE, "s1", board_store=store)
    second = board_generation_context(computed, ALICE, "s1", offset=first["next_offset"], board_store=store)
    assert first["has_more"] is True and second["has_more"] is False
    assert first["saved_boards"] == second["saved_boards"] == [summary_of(saved)]
    assert any("只生成待确认草稿" in item for item in first["constraints"])
    assert any("已保存看板不是草稿" in item for item in first["constraints"])
    assert any("承认未知" in item for item in first["constraints"])
