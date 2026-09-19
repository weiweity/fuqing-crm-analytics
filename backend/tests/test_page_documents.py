"""Free-page persistence with isolated SQLite. Not a BoardSpec mock."""
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

from backend.contracts.board_spec import BoardDraft
from backend.contracts.competition_computed import DATA_SCOPE
from backend.contracts.page_documents import (
    FORBIDDEN_BRIDGE_OPS, PACKAGE_MAX_BYTES, PAGE_ERRORS, PageBindingManifest, PageDataReadRequest,
    PageDocument, PageDraft, PagePackage, PagePatchPreview, PageRollbackPreview, PageSavePreview,
    SCHEMA_VERSION, is_package_too_large, page_documents_openapi,
)
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, B0IdentityRegistry
from backend.services.analytics.board_documents import BoardDocumentStore
from backend.services.analytics.page_documents import PageDocumentStore, ResolvedPageBinding
from backend.services.analytics.page_documents_routes import PREFIX, create_page_app

ROOT = Path(__file__).resolve().parents[2]
CAPS = frozenset({"analysis:read", "analysis:save", "dashboard:read", "dashboard:update"})
ALICE = AnalyticsPrincipal("alice", CAPS, frozenset({DATA_SCOPE, "brand-a"}))
BOB = AnalyticsPrincipal("bob", CAPS, ALICE.data_scopes)
TOKEN = "library-page-isolated-test-token-32chars"
FROZEN = json.loads((ROOT / "docs/hackathon/free-html-cockpit/fixtures/frozen-contract-v0.json").read_text())


def private(path):
    path.mkdir(mode=0o700)
    return path


def sample_package(**overrides):
    body = deepcopy(FROZEN["asset"]["package"])
    body.update(overrides)
    return body


def draft(**overrides):
    body = {"title": FROZEN["asset"]["title"], "session_id": FROZEN["asset"]["session_id"],
            "package": sample_package(), "binding_manifest": deepcopy(FROZEN["asset"]["binding_manifest"])}
    body.update(overrides)
    return PageDraft.model_validate(body)


def confirm(store, preview, key="confirm"):
    return store.confirm(ALICE, preview["preview_id"], key)


def test_frozen_fixture_is_the_lane_a_target():
    assert FROZEN["approved_plan_sha256"] == "47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb"
    assert FROZEN["asset"]["schema_version"] == SCHEMA_VERSION
    assert FROZEN["asset"]["binding_states"] == ["UNBOUND_SAMPLE", "BOUND_VERIFIED", "BOUND_STALE"]
    assert FROZEN["operations"] == ["GENERATE", "PATCH", "SAVE", "ROLLBACK"]
    assert FROZEN["errors"]["INVALID_PAGE"] == 422
    assert "INVALID_BOARD" not in FROZEN["errors"]
    PageDocument.model_validate({
        "schema_version": SCHEMA_VERSION, "page_id": FROZEN["asset"]["page_id"],
        "session_id": FROZEN["asset"]["session_id"], "title": FROZEN["asset"]["title"],
        "version": 1, "binding_state": "UNBOUND_SAMPLE",
        "package": FROZEN["asset"]["package"], "binding_manifest": FROZEN["asset"]["binding_manifest"],
    })


def test_contract_rejects_unknown_fields_board_spec_and_invalid_binding():
    body = draft().model_dump(mode="json")
    with pytest.raises(ValidationError):
        PageDraft.model_validate({**body, "owner": "alice"})
    with pytest.raises(ValidationError):
        PageDraft.model_validate({**body, "blocks": []})
    with pytest.raises(ValidationError):
        PageDraft.model_validate({**body, "board_id": "board_x"})
    with pytest.raises(ValidationError):
        PageDocument.model_validate({**body, "schema_version": "board-spec/v1",
                                     "page_id": "page_x", "version": 1, "binding_state": "UNBOUND_SAMPLE"})
    with pytest.raises(ValidationError):
        PageDocument.model_validate({**body, "page_id": "page_x", "version": 1,
                                     "binding_state": "BOUND_SAMPLE"})
    with pytest.raises(ValidationError):
        PageDraft.model_validate({**body, "package": {**body["package"], "html": ""}})
    with pytest.raises(ValidationError):
        PageDocument.model_validate({**body, "page_id": "page_x", "version": 1,
                                     "binding_state": "BOUND_VERIFIED"})
    with pytest.raises(ValidationError):
        PageDocument.model_validate({**body, "page_id": "page_x", "version": 1,
                                     "binding_state": "UNBOUND_SAMPLE",
                                     "binding_manifest": {"result_refs": ["result_fixture_1"],
                                                          "bindings": [{"binding_id": "bind_1",
                                                                        "result_ref": "result_fixture_1"}]}})
    fat = {**body["package"], "resources": [{
        "resource_id": "blob_1", "content_type": "image/png", "sha256": "a" * 64,
        "byte_length": PACKAGE_MAX_BYTES,
    }]}
    with pytest.raises(ValidationError) as oversized:
        PagePackage.model_validate(fat)
    assert is_package_too_large(oversized.value)
    with pytest.raises(ValidationError):
        PagePatchPreview.model_validate({"base_version": 1, "package": body["package"], "title": None})
    schema = page_documents_openapi()
    assert schema["x-free-page-schema"] == SCHEMA_VERSION
    assert "INVALID_BOARD" not in schema["x-page-errors"]
    assert schema["x-page-errors"] == PAGE_ERRORS
    assert "BoardDraft" not in schema["components"]["schemas"]
    patch_schema = schema["components"]["schemas"]["PagePatchPreview"]
    assert patch_schema["required"] == ["base_version"]
    assert "default" not in patch_schema["properties"]["title"]
    assert "anyOf" not in patch_schema["properties"]["title"]
    assert "$ref" in patch_schema["properties"]["package"]
    read = PageDataReadRequest.model_validate({
        "protocol": "free-page-bridge/v1", "instance_id": "inst_1", "request_id": "req_1",
        "nonce": "nonce_1", "seq": 0, **FROZEN["data_read"]["request"],
    })
    assert read.op == "data.read" and read.limit == 50
    for op in FORBIDDEN_BRIDGE_OPS:
        with pytest.raises(ValidationError):
            PageDataReadRequest.model_validate({
                "protocol": "free-page-bridge/v1", "instance_id": "inst_1", "request_id": "req_1",
                "nonce": "nonce_1", "seq": 0, "op": op, "result_ref": "result_fixture_1",
            })


def test_origin_path_round_trip_and_old_drafts_remain_valid(tmp_path):
    store = PageDocumentStore(private(tmp_path / "pages"))
    with pytest.raises(ValidationError):
        draft(origin_path="../etc/passwd")
    with pytest.raises(ValidationError):
        draft(origin_path="/tmp/a.html")
    preview = store.generate(ALICE, draft(
        origin_path="ops/web/index.html",
        binding_manifest={"bindings": [], "result_refs": []},
    ))
    assert preview["snapshot"]["spec"]["origin_path"] == "ops/web/index.html"
    saved = confirm(store, preview)
    assert saved["spec"]["origin_path"] == "ops/web/index.html"
    assert store.get(ALICE, saved["spec"]["page_id"])["spec"]["origin_path"] == "ops/web/index.html"
    assert store.list(ALICE)[0]["origin_path"] == "ops/web/index.html"
    body = draft().model_dump(mode="json")
    body.pop("origin_path", None)
    PageDraft.model_validate(body)


def test_generate_is_not_saved_until_confirm_and_failed_generate_leaves_no_asset(tmp_path):
    store = PageDocumentStore(private(tmp_path / "pages"))
    preview = store.generate(ALICE, draft())
    assert preview["operation"] == "GENERATE" and preview["base_version"] == 0
    assert preview["snapshot"]["spec"]["schema_version"] == SCHEMA_VERSION
    assert preview["snapshot"]["spec"]["binding_state"] == "UNBOUND_SAMPLE"
    assert store.list(ALICE) == []
    with pytest.raises(ValidationError):
        draft(package={**sample_package(), "html": ""})
    with pytest.raises(ValidationError):
        draft(package={**sample_package(), "js": "x" * 524_289})
    assert store.list(ALICE) == []
    forged = draft().model_dump(mode="json")
    forged["package"]["html"] = ""
    with pytest.raises(AnalyticsError) as error:
        store.generate(ALICE, PageDraft.model_construct(**forged))
    assert error.value.code == "INVALID_PAGE" and error.value.status == 422
    fat = draft().model_dump(mode="json")
    fat["package"]["resources"] = [{"resource_id": "blob_1", "content_type": "image/png",
                                    "sha256": "a" * 64, "byte_length": PACKAGE_MAX_BYTES}]
    with pytest.raises(AnalyticsError) as error:
        store.generate(ALICE, PageDraft.model_construct(**fat))
    assert error.value.code == "PACKAGE_TOO_LARGE" and error.value.status == 413
    bound = draft(binding_manifest={"result_refs": ["result_fixture_1"],
                                    "bindings": [{"binding_id": "bind_1", "result_ref": "result_fixture_1"}]})
    with pytest.raises(AnalyticsError) as error:
        store.generate(ALICE, bound)
    assert error.value.code == "RESULT_UNAVAILABLE" and error.value.status == 409
    assert store.list(ALICE) == []
    saved = confirm(store, preview)
    assert saved["spec"]["version"] == 1
    assert store.list(ALICE)[0]["page_id"] == saved["spec"]["page_id"]
    assert confirm(store, preview) == saved
    assert confirm(store, preview, "a-new-key") == saved
    assert len(store.history(ALICE, saved["spec"]["page_id"])) == 1


def test_d6_patch_and_d9_save_are_separate_one_version_each_and_cancel_does_not_save(tmp_path):
    store = PageDocumentStore(private(tmp_path / "pages"))
    v1 = confirm(store, store.generate(ALICE, draft()))
    page_id = v1["spec"]["page_id"]
    patched = store.patch(ALICE, page_id, PagePatchPreview.model_validate({
        "base_version": 1, "package": sample_package(html="<html><body>patched</body></html>"),
    }))
    assert patched["operation"] == "PATCH"
    assert store.get(ALICE, page_id) == v1
    store.cancel(ALICE, patched["preview_id"])
    store.cancel(ALICE, patched["preview_id"])
    with pytest.raises(AnalyticsError, match="PREVIEW_CANCELLED"):
        confirm(store, patched, "cancelled")
    assert store.get(ALICE, page_id) == v1
    patched = store.patch(ALICE, page_id, PagePatchPreview.model_validate({
        "base_version": 1, "package": sample_package(html="<html><body>patched</body></html>"),
    }))
    v2 = confirm(store, patched, "d6")
    assert v2["spec"]["version"] == 2
    assert v2["spec"]["package"]["html"] == "<html><body>patched</body></html>"
    assert v2["spec"]["binding_manifest"] == v1["spec"]["binding_manifest"]
    saved = store.save(ALICE, page_id, PageSavePreview.model_validate({
        "base_version": 2, "title": "显式保存草稿",
        "package": sample_package(html="<html><body>host-draft</body></html>", js="console.log(1)"),
        "binding_manifest": {"bindings": [], "result_refs": []},
    }))
    assert saved["operation"] == "SAVE"
    assert store.get(ALICE, page_id) == v2
    v3 = confirm(store, saved, "d9")
    assert v3["spec"]["version"] == 3 and v3["spec"]["title"] == "显式保存草稿"
    assert v3["spec"]["package"]["js"] == "console.log(1)"
    assert [item["operation"] for item in store.history(ALICE, page_id)] == ["SAVE", "PATCH", "GENERATE"]
    assert confirm(store, patched, "d6") == v2
    with pytest.raises(AnalyticsError, match="IDEMPOTENCY_CONFLICT"):
        confirm(store, saved, "d6")


def test_process_reopen_new_connection_and_monotonic_rollback(tmp_path):
    directory = private(tmp_path / "pages")
    store = PageDocumentStore(directory)
    v1 = confirm(store, store.generate(ALICE, draft()))
    page_id = v1["spec"]["page_id"]
    v2 = confirm(store, store.patch(ALICE, page_id, PagePatchPreview.model_validate({
        "base_version": 1, "title": "第二版",
    })), "v2")
    script = """
import json, sys
from pathlib import Path
from backend.services.analytics.access import AnalyticsPrincipal
from backend.services.analytics.page_documents import PageDocumentStore
actor=AnalyticsPrincipal('alice',frozenset({'dashboard:read'}),frozenset({'competition-diagnosis-fixture'}))
print(json.dumps(PageDocumentStore(Path(sys.argv[1])).get(actor,sys.argv[2])))
"""
    process = subprocess.run([sys.executable, "-c", script, str(directory), page_id], cwd=tmp_path,
        env={"PATH": str(Path(sys.executable).parent) + ":/usr/bin:/bin", "PYTHONPATH": str(ROOT),
             "PYTHONNOUSERSITE": "1", "PYTHON_DOTENV_DISABLED": "1"},
        capture_output=True, text=True, timeout=30, check=True)
    assert json.loads(process.stdout) == v2
    reopened = PageDocumentStore(directory)
    rollback = reopened.rollback(ALICE, page_id, PageRollbackPreview(base_version=2, to_version=1))
    assert reopened.get(ALICE, page_id) == v2
    v3 = confirm(reopened, rollback, "rollback")
    assert v3["spec"]["package"] == v1["spec"]["package"] and v3["spec"]["version"] == 3
    assert v3["spec"]["title"] == v1["spec"]["title"]
    assert reopened.get(ALICE, page_id, 2) == v2
    assert [item["version"] for item in reopened.history(ALICE, page_id)] == [3, 2, 1]
    assert confirm(reopened, rollback, "rollback") == v3
    assert reopened.get(ALICE, page_id) == v3
    assert directory.stat().st_mode & 0o077 == 0
    assert reopened.path.stat().st_mode & 0o077 == 0


def test_parallel_confirm_exactly_one_wins_and_retry_is_idempotent(tmp_path):
    directory = private(tmp_path / "pages")
    store = PageDocumentStore(directory)
    v1 = confirm(store, store.generate(ALICE, draft()))
    page_id = v1["spec"]["page_id"]
    drafts = [store.patch(ALICE, page_id, PagePatchPreview.model_validate(
        {"base_version": 1, "title": title})) for title in ("A", "B")]
    clients = [PageDocumentStore(directory), PageDocumentStore(directory)]
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
    assert len(store.history(ALICE, page_id)) == 2
    with pytest.raises(AnalyticsError, match="IDEMPOTENCY_CONFLICT"):
        confirm(store, drafts[1 - winner], f"key-{winner}")


def test_expiry_locked_sqlite_and_midtransaction_failure_preserve_head(tmp_path):
    instant = [100]
    store = PageDocumentStore(private(tmp_path / "pages"), clock=lambda: instant[0])
    v1 = confirm(store, store.generate(ALICE, draft()))
    page_id = v1["spec"]["page_id"]
    edit = store.patch(ALICE, page_id, PagePatchPreview.model_validate({"base_version": 1, "title": "不会丢失旧版"}))
    instant[0] = edit["expires_at_ms"]
    with pytest.raises(AnalyticsError, match="PREVIEW_EXPIRED"):
        confirm(store, edit, "expired")
    edit = store.patch(ALICE, page_id, PagePatchPreview.model_validate({"base_version": 1, "title": "可重试"}))
    with closing(sqlite3.connect(store.path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        with pytest.raises(AnalyticsError, match="STATE_UNAVAILABLE") as error:
            confirm(store, edit, "locked")
        assert error.value.retryable
        conn.rollback()
        conn.execute("CREATE TRIGGER fail_revision BEFORE INSERT ON revisions BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
        conn.commit()
        with pytest.raises(AnalyticsError, match="STATE_UNAVAILABLE"):
            confirm(store, edit, "locked")
        assert store.get(ALICE, page_id) == v1
        assert store.preview(ALICE, edit["preview_id"])["status"] == "PENDING"
        conn.execute("DROP TRIGGER fail_revision")
        conn.commit()
    assert confirm(store, edit, "locked")["spec"]["version"] == 2


def test_ownership_permission_revocation_and_payload_integrity(tmp_path):
    def resolver(actor, session_id, result_id):
        assert session_id == "native_session_fixture" and result_id == "result_fixture_1"
        return ResolvedPageBinding("VERIFIED", frozenset({"brand-a"}))

    store = PageDocumentStore(private(tmp_path / "pages"), resolve_binding=resolver)
    bound = draft(binding_manifest=PageBindingManifest.model_validate({
        "result_refs": ["result_fixture_1"],
        "bindings": [{"binding_id": "bind_1", "result_ref": "result_fixture_1", "node_id": "n_title"}],
    }))
    preview = store.generate(ALICE, bound)
    assert preview["snapshot"]["spec"]["binding_state"] == "BOUND_VERIFIED"
    v1 = confirm(store, preview)
    page_id = v1["spec"]["page_id"]
    assert store.list(BOB) == []
    for operation in (lambda: store.get(BOB, page_id), lambda: store.preview(BOB, preview["preview_id"]),
                      lambda: store.confirm(BOB, preview["preview_id"], "key")):
        with pytest.raises(AnalyticsError) as error:
            operation()
        assert error.value.status == 404
    revoked = AnalyticsPrincipal("alice", CAPS, frozenset({DATA_SCOPE}))
    assert store.list(revoked) == []
    with pytest.raises(AnalyticsError) as error:
        store.get(revoked, page_id)
    assert error.value.status == 403
    readonly = AnalyticsPrincipal("alice", frozenset({"dashboard:read"}), ALICE.data_scopes)
    assert store.get(readonly, page_id) == v1
    with pytest.raises(AnalyticsError) as error:
        store.confirm(readonly, preview["preview_id"], "confirm")
    assert error.value.status == 403
    with closing(sqlite3.connect(store.path)) as conn:
        conn.execute("UPDATE revisions SET payload='{}'")
        conn.commit()
    with pytest.raises(AnalyticsError, match="BINDING_CORRUPT"):
        store.get(ALICE, page_id)


def test_rollback_rechecks_grants_and_marks_stale_or_revoked(tmp_path):
    state = {"status": "VERIFIED"}

    def resolver(actor, session_id, result_id):
        return ResolvedPageBinding(state["status"], frozenset({"brand-a"}))

    store = PageDocumentStore(private(tmp_path / "pages"), resolve_binding=resolver)
    manifest = {"result_refs": ["result_fixture_1"],
                "bindings": [{"binding_id": "bind_1", "result_ref": "result_fixture_1"}]}
    v1 = confirm(store, store.generate(ALICE, draft(binding_manifest=manifest)))
    page_id = v1["spec"]["page_id"]
    v2 = confirm(store, store.patch(ALICE, page_id, PagePatchPreview.model_validate({
        "base_version": 1, "title": "改标题",
    })), "v2")
    state["status"] = "STALE"
    restored = confirm(store, store.rollback(ALICE, page_id, PageRollbackPreview(base_version=2, to_version=1)), "rb")
    assert restored["spec"]["binding_state"] == "BOUND_STALE"
    assert restored["spec"]["package"] == v1["spec"]["package"]
    assert restored["spec"]["version"] == 3
    state["status"] = "REVOKED"
    with pytest.raises(AnalyticsError) as error:
        store.rollback(ALICE, page_id, PageRollbackPreview(base_version=3, to_version=1))
    assert error.value.code == "RESULT_REVOKED" and error.value.status == 403
    assert store.get(ALICE, page_id)["spec"]["version"] == 3
    assert v2["spec"]["title"] == "改标题"


def test_foreign_or_linked_state_is_never_reinitialized(tmp_path):
    directory = private(tmp_path / "pages")
    path = directory / "page_documents.sqlite3"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE valuable(value TEXT)")
        conn.execute("INSERT INTO valuable VALUES ('keep')")
        conn.commit()
    before = path.read_bytes()
    with pytest.raises(ValueError):
        PageDocumentStore(directory)
    assert path.read_bytes() == before
    linked = private(tmp_path / "linked")
    os.symlink(path, linked / "page_documents.sqlite3")
    with pytest.raises(ValueError):
        PageDocumentStore(linked)
    assert path.read_bytes() == before


def test_boardspec_store_and_codec_stay_independent(tmp_path):
    pages = PageDocumentStore(private(tmp_path / "pages"))
    boards = BoardDocumentStore(private(tmp_path / "boards"))
    page = confirm(pages, pages.generate(ALICE, draft()))
    board_draft = BoardDraft.model_validate({"title": "经营看板", "session_id": "s1", "blocks": [
        {"block_id": "note", "kind": "TEXT", "title": "说明", "props": {"content": "旧内容"},
         "layout": {"x": 0, "y": 0, "w": 6, "h": 5}},
    ]})
    board = boards.confirm(ALICE, boards.generate(ALICE, board_draft)["preview_id"], "board")
    assert page["spec"]["schema_version"] == SCHEMA_VERSION
    assert board["spec"]["schema_version"] == "board-spec/v1"
    assert "blocks" not in page["spec"]
    assert "package" not in board["spec"]
    with pytest.raises(AnalyticsError, match="NOT_FOUND"):
        boards.get(ALICE, page["spec"]["page_id"])
    with pytest.raises(AnalyticsError, match="NOT_FOUND"):
        pages.get(ALICE, board["spec"]["board_id"])


def test_http_generate_patch_save_rollback_unknown_fields_and_reopen(tmp_path):
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, ALICE)
    directory = private(tmp_path / "pages")
    headers = {"Authorization": "Bearer " + TOKEN}
    body = draft().model_dump(mode="json")
    with TestClient(create_page_app(identities=registry, page_state_dir=directory)) as client:
        assert client.get(PREFIX + "/pages").status_code == 401
        assert client.post(PREFIX + "/previews", json={**body, "owner": "alice"}).status_code == 422
        response = client.post(PREFIX + "/previews", headers=headers, json=body)
        assert response.status_code == 201, response.text
        assert response.headers["cache-control"] == "no-store"
        preview = response.json()
        assert preview["operation"] == "GENERATE"
        endpoint = PREFIX + "/previews/" + preview["preview_id"]
        assert client.get(PREFIX + "/pages", headers=headers).json() == {"items": []}
        assert client.post(endpoint + "/confirm", headers=headers).status_code == 428
        response = client.post(endpoint + "/confirm", headers={**headers, "Idempotency-Key": "save"})
        assert response.status_code == 200, response.text
        snapshot = response.json()
        page_id = snapshot["spec"]["page_id"]
        patch = {"base_version": 1, "package": sample_package(html="<html><h1>d6</h1></html>")}
        response = client.post(PREFIX + f"/pages/{page_id}/patch-preview", headers=headers, json=patch)
        assert response.status_code == 201 and response.json()["operation"] == "PATCH"
        assert client.post(PREFIX + "/previews/" + response.json()["preview_id"] + "/confirm",
                           headers={**headers, "Idempotency-Key": "d6"}).status_code == 200
        save = {"base_version": 2, "title": "d9", "package": sample_package(html="<html>d9</html>"),
                "binding_manifest": {"bindings": [], "result_refs": []}}
        response = client.post(PREFIX + f"/pages/{page_id}/save-preview", headers=headers, json=save)
        assert response.status_code == 201 and response.json()["operation"] == "SAVE"
        assert client.post(PREFIX + "/previews/" + response.json()["preview_id"] + "/confirm",
                           headers={**headers, "Idempotency-Key": "d9"}).status_code == 200
        rollback = {"base_version": 3, "to_version": 1}
        response = client.post(PREFIX + f"/pages/{page_id}/rollback-preview", headers=headers, json=rollback)
        assert response.status_code == 201 and response.json()["operation"] == "ROLLBACK"
        restored = client.post(PREFIX + "/previews/" + response.json()["preview_id"] + "/confirm",
                               headers={**headers, "Idempotency-Key": "rb"})
        assert restored.status_code == 200
        assert restored.json()["spec"]["package"]["html"] == body["package"]["html"]
        assert restored.json()["spec"]["version"] == 4
        forged = client.post(PREFIX + f"/pages/{page_id}/patch-preview", headers=headers,
                             json={**patch, "owner": "bob"})
        assert forged.status_code == 422
        assert forged.json()["error"]["code"] == "INVALID_PAGE"
        null_patch = client.post(PREFIX + f"/pages/{page_id}/patch-preview", headers=headers,
                                 json={"base_version": 4, "package": sample_package(), "title": None})
        assert null_patch.status_code == 422
        fat = {**body, "package": {**body["package"], "resources": [{
            "resource_id": "blob_1", "content_type": "image/png", "sha256": "a" * 64,
            "byte_length": PACKAGE_MAX_BYTES,
        }]}}
        huge = client.post(PREFIX + "/previews", headers=headers, json=fat)
        assert huge.status_code == 413
        assert huge.json()["error"]["code"] == "PACKAGE_TOO_LARGE"
        registry.revoke(TOKEN)
        assert client.get(PREFIX + f"/pages/{page_id}", headers=headers).status_code == 401
    registry.grant(TOKEN, ALICE)
    with TestClient(create_page_app(identities=registry, page_state_dir=directory)) as client:
        reopened = client.get(PREFIX + f"/pages/{page_id}", headers=headers)
        assert reopened.status_code == 200
        assert reopened.json()["spec"]["version"] == 4


def test_http_uses_the_offline_contract():
    schema = create_page_app().openapi()
    offline = page_documents_openapi()
    for name in ("PageDraft", "PageDocument", "PagePatchPreview", "PageSavePreview",
                 "PageRollbackPreview", "PagePreview", "PageSnapshot"):
        http = schema["components"]["schemas"][name]
        off = offline["components"]["schemas"][name]
        assert http["required"] == off["required"]
        assert set(http["properties"]) == set(off["properties"])
    paths = schema["paths"]
    for path, model in (("/previews", "PageDraft"), ("/pages/{page_id}/patch-preview", "PagePatchPreview"),
                        ("/pages/{page_id}/save-preview", "PageSavePreview"),
                        ("/pages/{page_id}/rollback-preview", "PageRollbackPreview")):
        assert paths[PREFIX + path]["post"]["requestBody"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/" + model}
    assert schema["x-page-http"] is True
    assert schema["x-b0-board-spec-untouched"] == "board-spec/v1"
    assert "INVALID_BOARD" not in schema["x-page-errors"]
