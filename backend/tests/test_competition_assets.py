"""Competition assets: endorse, batch, 409, undo, persistent attempt. No HTTP."""

from __future__ import annotations

import json
import os
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest

from backend.contracts.competition_c0 import (
    CompetitionBoardBatchReceipt,
    CompetitionBoardSpec,
    CompetitionErrorDetail,
)
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal
from backend.services.analytics.analysis_source import resolve_endorsed_result
from backend.services.analytics.cockpit import CockpitStore
from backend.services.analytics.competition_assets import (
    APPLICATION_ID,
    HTTP_WIRING,
    CompetitionAssetService,
    as_competition_error,
    operation_payload_hash,
)
from backend.services.analytics.resource_profile import content_hash
from backend.services.analytics.saved_analyses import SavedAnalysisStore

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
CLOCK_MS = 1_800_000_000_000
CAPS = frozenset({"analysis:save", "analysis:read", "dashboard:read", "dashboard:update"})
SCOPE = frozenset({"channel-followup-fixture"})


def load_json(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def succeeded_run() -> dict:
    return deepcopy(load_json("analytics_saved_analysis_succeeded_run.json")["run"])


def actor(name="alice", *, capabilities=None, scopes=None):
    return AnalyticsPrincipal(
        name,
        frozenset(CAPS if capabilities is None else capabilities),
        frozenset(SCOPE if scopes is None else scopes),
    )


def private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def save_payload(run: dict, **changes) -> dict:
    payload = {
        "title": "首次观察到的渠道 / 30日二单率",
        "created_from_run_id": run["run_id"],
        "filters": deepcopy(run["request"]),
    }
    payload.update(changes)
    return payload


def seed_analysis(store: SavedAnalysisStore, principal=None, run=None, key="save-1"):
    principal = principal or actor()
    run = run or succeeded_run()
    store.register_succeeded_run(principal, run)
    return store.save(principal, key, save_payload(run))


def make_service(tmp_path: Path, *, with_cockpit: bool = True) -> tuple[CompetitionAssetService, SavedAnalysisStore, CockpitStore | None]:
    analyses = SavedAnalysisStore(private_dir(tmp_path / "saved"), clock=lambda: CLOCK_MS)
    cockpit = CockpitStore(private_dir(tmp_path / "cockpit"), clock=lambda: CLOCK_MS) if with_cockpit else None
    service = CompetitionAssetService(
        private_dir(tmp_path / "competition"),
        analysis_store=analyses,
        cockpit_store=cockpit,
        clock=lambda: CLOCK_MS,
    )
    return service, analyses, cockpit


def endorsed_ref(record, *, result_id: str | None = None) -> dict:
    binding = record.binding()
    return {
        "result_id": result_id or f"result_{binding['run_id'][4:]}",
        "run_id": binding["run_id"],
        "analysis_id": binding["analysis_id"],
        "evidence_digest": binding["evidence_digest"],
        "completeness": "COMPLETE",
    }


def fingerprint(tag: str) -> str:
    return content_hash({"tag": tag})


def batch_payload(*, batch_id: str, layout_mode: str, operations: list[dict]) -> dict:
    return {
        "schema_version": "competition-board-batch/v1",
        "batch_id": batch_id,
        "layout_mode": layout_mode,
        "operations": operations,
    }


def operation(*, operation_id: str, key: str, title: str, refs: list[dict], board_id=None, tag=None, layout_mode="ONE_BOARD_MULTI_BLOCK"):
    body = {
        "operation_id": operation_id,
        "idempotency_key": key,
        "request_fingerprint": fingerprint(tag or operation_id),
        "layout_mode": layout_mode,
        "title": title,
        "endorsed_result_refs": refs,
    }
    if board_id is not None:
        body["board_id"] = board_id
    return body


def style_patch(board_id: str, block_id: str, *, base_version: int, attempt: str, title="渠道贡献（样式）"):
    return {
        "schema_version": "competition-board-patch/v1",
        "board_id": board_id,
        "block_id": block_id,
        "base_version": base_version,
        "attempt_id": attempt,
        "idempotency_key": f"key-{attempt}",
        "intent": "STYLE_ONLY",
        "display_op": {
            "op": "display",
            "card_id": block_id,
            "display_overrides": {"title": title},
        },
    }


def test_http_surface_is_disconnected(tmp_path):
    service, _analyses, _cockpit = make_service(tmp_path)
    assert service.http_api == "NOT_CONNECTED"
    assert HTTP_WIRING["http_api"] == "NOT_CONNECTED"
    assert HTTP_WIRING["prefix"] == "/api/v1/analytics/competition"
    with sqlite3.connect(service.store.path) as con:
        assert con.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID
        assert con.execute("SELECT value FROM metadata WHERE key='data_namespace'").fetchone()[0] == "competition-board/v1"
        assert con.execute("SELECT value FROM metadata WHERE key='http_api'").fetchone()[0] == "NOT_CONNECTED"


def test_endorse_and_shared_result_refs_across_boards(tmp_path):
    service, analyses, _cockpit = make_service(tmp_path)
    saved = seed_analysis(analyses)
    ref = endorsed_ref(saved)
    endorsed = service.endorse_results(actor(), "endorse-1", [ref])
    assert endorsed["result_ids"] == [ref["result_id"]]
    replay = service.endorse_results(actor(), "endorse-1", [ref])
    assert replay == endorsed
    bound = resolve_endorsed_result(analyses, actor(), ref)
    assert bound["analysis_id"] == saved.analysis_id
    assert bound["evidence_digest"] == saved.snapshot["evidence_digest"]
    first = service.apply_batch(actor(), batch_payload(
        batch_id="batch_share_a", layout_mode="ONE_BOARD_MULTI_BLOCK",
        operations=[operation(operation_id="op_share_a", key="board-a", title="板A", refs=[ref])],
    ))
    second = service.apply_batch(actor(), batch_payload(
        batch_id="batch_share_b", layout_mode="ONE_BOARD_MULTI_BLOCK",
        operations=[operation(
            operation_id="op_share_b", key="board-b", title="板B", refs=[ref],
            layout_mode="ONE_BOARD_MULTI_BLOCK",
        )],
    ))
    board_a = service.get_board(actor(), first["items"][0]["board_id"])
    board_b = service.get_board(actor(), second["items"][0]["board_id"])
    assert board_a["spec"]["data_namespace"] == "competition-board/v1"
    assert board_a["blocks"][0]["analysis_ref"]["analysis_id"] == saved.analysis_id
    assert board_b["blocks"][0]["analysis_ref"]["analysis_id"] == saved.analysis_id
    assert board_a["blocks"][0]["evidence_digest"] == board_b["blocks"][0]["evidence_digest"]
    assert board_a["blocks"][0]["facts"]["totals"]["channel_repeat_ratio"] == 0.5
    with sqlite3.connect(analyses.path) as con:
        assert con.execute("SELECT count(*) FROM succeeded_runs").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM analyses").fetchone()[0] == 1


def test_one_board_multi_block_stable_ids(tmp_path):
    service, analyses, _cockpit = make_service(tmp_path)
    first = seed_analysis(analyses, key="save-a")
    run_b = succeeded_run()
    run_b["run_id"] = "run_cccccccccccccccccccccccccccccccc"
    second = seed_analysis(analyses, run=run_b, key="save-b")
    refs = [endorsed_ref(first, result_id="result_one"), endorsed_ref(second, result_id="result_two")]
    receipt = service.apply_batch(actor(), batch_payload(
        batch_id="batch_multi_block", layout_mode="ONE_BOARD_MULTI_BLOCK",
        operations=[operation(operation_id="op_multi_block", key="multi-block", title="一板两块", refs=refs)],
    ))
    CompetitionBoardBatchReceipt.model_validate(receipt)
    assert receipt["status"] == "SUCCEEDED"
    document = service.get_board(actor(), receipt["items"][0]["board_id"])
    spec = CompetitionBoardSpec.model_validate(document["spec"])
    assert spec.layout_mode == "ONE_BOARD_MULTI_BLOCK"
    assert spec.snapshot_compat == "ISOLATED_NEW"
    assert len(spec.block_ids) == 2
    assert spec.block_ids[0] != spec.block_ids[1]
    replay = service.apply_batch(actor(), batch_payload(
        batch_id="batch_multi_block", layout_mode="ONE_BOARD_MULTI_BLOCK",
        operations=[operation(operation_id="op_multi_block", key="multi-block", title="一板两块", refs=refs)],
    ))
    assert replay["items"][0]["board_id"] == receipt["items"][0]["board_id"]
    again = service.get_board(actor(), receipt["items"][0]["board_id"])
    assert again["spec"]["block_ids"] == spec.block_ids
    with sqlite3.connect(service.store.path) as con:
        assert con.execute("SELECT count(DISTINCT board_id) FROM boards").fetchone()[0] == 1


def test_batch_multi_board_partial_and_retry_failed_only(tmp_path):
    service, analyses, _cockpit = make_service(tmp_path)
    saved = seed_analysis(analyses)
    good = endorsed_ref(saved, result_id="result_ok")
    missing = {
        "result_id": "result_missing",
        "run_id": "run_dddddddddddddddddddddddddddddddd",
        "evidence_digest": saved.snapshot["evidence_digest"],
        "completeness": "COMPLETE",
    }
    payload = batch_payload(
        batch_id="batch_partial", layout_mode="BATCH_MULTI_BOARD",
        operations=[
            operation(operation_id="op_ok", key="ok", title="成功板", refs=[good], layout_mode="BATCH_MULTI_BOARD"),
            operation(operation_id="op_bad", key="bad", title="失败板", refs=[missing], layout_mode="BATCH_MULTI_BOARD"),
        ],
    )
    receipt = service.apply_batch(actor(), payload)
    assert receipt["status"] == "PARTIAL"
    assert receipt["items"][0]["status"] == "SUCCEEDED"
    assert receipt["items"][1]["status"] == "FAILED"
    assert receipt["items"][1]["error_code"] == "ANALYSIS_UNAVAILABLE"
    assert receipt["items"][1]["retryable"] is True
    assert receipt["items"][1]["board_id"] is None
    stored = service.get_batch(actor(), "batch_partial")
    assert stored["status"] == "PARTIAL"
    retried = service.apply_batch(actor(), payload)
    assert retried["items"][0]["board_id"] == receipt["items"][0]["board_id"]
    assert retried["items"][1]["status"] == "FAILED"
    run_late = succeeded_run()
    run_late["run_id"] = missing["run_id"]
    seed_analysis(analyses, run=run_late, key="save-missing")
    recovered_receipt = service.apply_batch(actor(), payload)
    assert recovered_receipt["status"] == "SUCCEEDED"
    assert recovered_receipt["items"][0]["board_id"] == receipt["items"][0]["board_id"]
    assert recovered_receipt["items"][1]["board_id"] is not None
    assert recovered_receipt["items"][1]["status"] == "SUCCEEDED"
    with sqlite3.connect(service.store.path) as con:
        assert con.execute("SELECT count(DISTINCT board_id) FROM boards").fetchone()[0] == 2


def test_same_idempotency_key_different_payload_is_409(tmp_path):
    service, analyses, _cockpit = make_service(tmp_path)
    saved = seed_analysis(analyses)
    ref = endorsed_ref(saved)
    first = service.apply_batch(actor(), batch_payload(
        batch_id="batch_key", layout_mode="ONE_BOARD_MULTI_BLOCK",
        operations=[operation(operation_id="op_key", key="same-key", title="原标题", refs=[ref])],
    ))
    with pytest.raises(AnalyticsError) as error:
        service.apply_batch(actor(), batch_payload(
            batch_id="batch_key", layout_mode="ONE_BOARD_MULTI_BLOCK",
            operations=[operation(operation_id="op_key", key="same-key", title="改过的标题", refs=[ref])],
        ))
    assert error.value.status == 409
    assert error.value.code == "CONFLICT"
    current = service.get_board(actor(), first["items"][0]["board_id"])
    assert current["spec"]["title"] == "原标题"
    mapped = as_competition_error(error.value, request_id="req_c0_conflict")
    CompetitionErrorDetail.model_validate(mapped["error"])
    assert mapped["error"]["http_status"] == 409
    assert mapped["error"]["param"] == "idempotency_key"


def test_crash_reopen_replays_receipt_without_new_board(tmp_path):
    service, analyses, _cockpit = make_service(tmp_path)
    saved = seed_analysis(analyses)
    ref = endorsed_ref(saved)
    payload = batch_payload(
        batch_id="batch_reopen", layout_mode="ONE_BOARD_MULTI_BLOCK",
        operations=[operation(operation_id="op_reopen", key="reopen", title="重开板", refs=[ref])],
    )
    first = service.apply_batch(actor(), payload)
    board_id = first["items"][0]["board_id"]
    service.close()
    analyses.close()
    reopened_analyses = SavedAnalysisStore(tmp_path / "saved", clock=lambda: CLOCK_MS)
    reopened = CompetitionAssetService(
        tmp_path / "competition", analysis_store=reopened_analyses,
        cockpit_store=CockpitStore(tmp_path / "cockpit", clock=lambda: CLOCK_MS),
        clock=lambda: CLOCK_MS,
    )
    replay = reopened.apply_batch(actor(), payload)
    assert replay["items"][0]["board_id"] == board_id
    assert replay["items"][0]["version"] == 1
    restored = reopened.get_board(actor(), board_id)
    assert restored["spec"]["board_id"] == board_id
    assert restored["blocks"][0]["facts"]["totals"]["channel_repeat_ratio"] == 0.5
    with sqlite3.connect(reopened.store.path) as con:
        assert con.execute("SELECT count(*) FROM boards").fetchone()[0] == 1


def test_preview_apply_409_discard_not_undo(tmp_path):
    service, analyses, _cockpit = make_service(tmp_path)
    saved = seed_analysis(analyses)
    ref = endorsed_ref(saved)
    created = service.apply_batch(actor(), batch_payload(
        batch_id="batch_edit", layout_mode="ONE_BOARD_MULTI_BLOCK",
        operations=[operation(operation_id="op_edit", key="edit", title="编辑板", refs=[ref])],
    ))
    board_id = created["items"][0]["board_id"]
    document = service.get_board(actor(), board_id)
    block_id = document["spec"]["block_ids"][0]
    digest = document["blocks"][0]["evidence_digest"]
    facts = document["blocks"][0]["facts"]
    preview = service.preview_patch(actor(), style_patch(board_id, block_id, base_version=1, attempt="attempt_style"))
    assert preview["spec"]["preview"] is True
    assert preview["spec"]["persisted"] is False
    assert preview["spec"]["version"] == 1
    assert preview["blocks"][0]["display_overrides"]["title"] == "渠道贡献（样式）"
    assert preview["blocks"][0]["facts"] == facts
    assert preview["blocks"][0]["evidence_digest"] == digest
    current = service.get_board(actor(), board_id)
    assert current["spec"]["version"] == 1
    assert current["blocks"][0]["display_overrides"] == {}
    target = service.get_edit_target(actor(), "attempt_style")
    assert target["board_id"] == board_id
    assert target["block_id"] == block_id
    assert target["status"] == "PREVIEWED"
    other_block = "block_" + "f" * 32
    with pytest.raises(AnalyticsError) as retarget:
        service.preview_patch(actor(), style_patch(
            board_id, other_block, base_version=1, attempt="attempt_style", title="切到B",
        ))
    assert retarget.value.status == 409
    still = service.get_edit_target(actor(), "attempt_style")
    assert still["block_id"] == block_id
    applied = service.apply_patch(actor(), style_patch(board_id, block_id, base_version=1, attempt="attempt_style"))
    assert applied["spec"]["preview"] is False
    assert applied["spec"]["persisted"] is True
    assert applied["spec"]["version"] == 2
    assert applied["spec"]["base_version"] == 1
    assert applied["blocks"][0]["display_overrides"]["title"] == "渠道贡献（样式）"
    replay = service.apply_patch(actor(), style_patch(board_id, block_id, base_version=1, attempt="attempt_style"))
    assert replay["spec"]["version"] == 2
    with pytest.raises(AnalyticsError) as stale:
        service.apply_patch(actor(), style_patch(
            board_id, block_id, base_version=1, attempt="attempt_stale", title="旧版覆盖",
        ))
    assert stale.value.status == 409
    assert stale.value.code == "VERSION_CONFLICT"
    mapped = as_competition_error(stale.value, request_id="req_c0_409_board")
    assert mapped["error"]["http_status"] == 409
    assert mapped["error"]["param"] == "base_version"
    after_conflict = service.get_board(actor(), board_id)
    assert after_conflict["spec"]["version"] == 2
    assert after_conflict["blocks"][0]["display_overrides"]["title"] == "渠道贡献（样式）"
    preview_undo = service.preview_patch(actor(), {
        "board_id": board_id,
        "block_id": None,
        "base_version": 2,
        "attempt_id": "attempt_discard",
        "idempotency_key": "discard-1",
        "intent": "STRUCTURE",
        "cockpit_op": {"op": "undo", "scope": "board", "restore_from_version": 1},
    })
    assert preview_undo["spec"]["preview"] is True
    discarded = service.discard_attempt(actor(), "attempt_discard")
    assert discarded["discarded"] is True
    assert discarded["undone"] is False
    assert discarded["board"]["spec"]["version"] == 2
    undone = service.apply_patch(actor(), {
        "board_id": board_id,
        "block_id": None,
        "base_version": 2,
        "attempt_id": "attempt_undo",
        "idempotency_key": "undo-1",
        "intent": "STRUCTURE",
        "cockpit_op": {"op": "undo", "scope": "board", "restore_from_version": 1},
    })
    assert undone["spec"]["version"] == 3
    assert undone["blocks"][0]["display_overrides"] == {}
    assert undone["blocks"][0]["block_id"] == block_id
    with sqlite3.connect(service.store.path) as con:
        versions = list(con.execute(
            "SELECT version FROM boards WHERE board_id=? ORDER BY version", (board_id,),
        ))
        assert [row[0] for row in versions] == [1, 2, 3]


def test_filter_change_and_illegal_patch_rejected(tmp_path):
    service, analyses, _cockpit = make_service(tmp_path)
    saved = seed_analysis(analyses)
    created = service.apply_batch(actor(), batch_payload(
        batch_id="batch_filter", layout_mode="ONE_BOARD_MULTI_BLOCK",
        operations=[operation(operation_id="op_filter", key="filter", title="筛选板", refs=[endorsed_ref(saved)])],
    ))
    board_id = created["items"][0]["board_id"]
    block_id = service.get_board(actor(), board_id)["spec"]["block_ids"][0]
    with pytest.raises(AnalyticsError) as filtered:
        service.preview_patch(actor(), {
            "board_id": board_id,
            "block_id": block_id,
            "base_version": 1,
            "attempt_id": "attempt_filter",
            "idempotency_key": "filter-1",
            "intent": "FILTER_CHANGE",
            "filter_change": {"op": "filter_change", "card_id": block_id, "local_filters": {"channel_ids": ["A"]}},
        })
    assert filtered.value.status == 422
    assert filtered.value.code == "NOT_CONNECTED"
    with pytest.raises(AnalyticsError) as illegal:
        service.preview_patch(actor(), {
            "board_id": board_id,
            "block_id": block_id,
            "base_version": 1,
            "attempt_id": "attempt_script",
            "idempotency_key": "script-1",
            "intent": "STRUCTURE",
            "cockpit_op": {"op": "eval", "script": "alert(1)"},
        })
    assert illegal.value.status == 422
    current = service.get_board(actor(), board_id)
    assert current["spec"]["version"] == 1
    assert current["blocks"][0]["local_filters"] == {}


def test_permission_isolation(tmp_path):
    service, analyses, _cockpit = make_service(tmp_path)
    saved = seed_analysis(analyses)
    created = service.apply_batch(actor(), batch_payload(
        batch_id="batch_acl", layout_mode="ONE_BOARD_MULTI_BLOCK",
        operations=[operation(operation_id="op_acl", key="acl", title="权限板", refs=[endorsed_ref(saved)])],
    ))
    board_id = created["items"][0]["board_id"]
    bob = actor("bob")
    with pytest.raises(AnalyticsError) as missing:
        service.get_board(bob, board_id)
    assert missing.value.status == 404
    assert service.list_boards(bob) == []
    reader = actor(capabilities={"dashboard:read", "analysis:read"})
    with pytest.raises(AnalyticsError) as forbidden:
        service.apply_batch(reader, batch_payload(
            batch_id="batch_reader", layout_mode="ONE_BOARD_MULTI_BLOCK",
            operations=[operation(operation_id="op_reader", key="reader", title="读者", refs=[endorsed_ref(saved)])],
        ))
    assert forbidden.value.status == 403
    b0_only = actor(scopes={"b0-fixture"})
    with pytest.raises(AnalyticsError) as scope:
        service.get_board(b0_only, board_id)
    assert scope.value.status == 403
    mapped = as_competition_error(forbidden.value, request_id="req_c0_403_board")
    assert mapped["error"]["http_status"] == 403
    assert mapped["error"]["doc_ref"].endswith("#T06")


def test_find_latest_for_run_and_binding(tmp_path):
    _service, analyses, _cockpit = make_service(tmp_path)
    saved = seed_analysis(analyses)
    found = analyses.find_latest_for_run(actor(), saved.created_from_run_id)
    assert found is not None
    assert found.analysis_id == saved.analysis_id
    assert found.binding()["evidence_digest"] == saved.snapshot["evidence_digest"]
    assert analyses.find_latest_for_run(actor(), "run_ffffffffffffffffffffffffffffffff") is None
    assert analyses.find_latest_for_run(actor("bob"), saved.created_from_run_id) is None
    with pytest.raises(AnalyticsError) as forbidden:
        analyses.find_latest_for_run(actor(capabilities={"dashboard:read"}), saved.created_from_run_id)
    assert forbidden.value.status == 403


def test_preview_matches_apply_and_copy_keeps_shared_ref(tmp_path):
    service, analyses, _cockpit = make_service(tmp_path)
    saved = seed_analysis(analyses)
    created = service.apply_batch(actor(), batch_payload(
        batch_id="batch_copy", layout_mode="ONE_BOARD_MULTI_BLOCK",
        operations=[operation(operation_id="op_copy", key="copy", title="复制板", refs=[endorsed_ref(saved)])],
    ))
    board_id = created["items"][0]["board_id"]
    block_id = service.get_board(actor(), board_id)["spec"]["block_ids"][0]
    payload = {
        "board_id": board_id,
        "block_id": block_id,
        "base_version": 1,
        "attempt_id": "attempt_copy",
        "idempotency_key": "copy-1",
        "intent": "STRUCTURE",
        "cockpit_op": {"op": "copy", "card_id": block_id},
    }
    preview = service.preview_patch(actor(), payload)
    applied = service.apply_patch(actor(), payload)
    assert preview["spec"]["affected_block_ids"] == applied["spec"]["affected_block_ids"]
    assert applied["spec"]["block_ids"][0] == block_id
    clone_id = applied["spec"]["block_ids"][1]
    assert clone_id == preview["spec"]["block_ids"][1]
    original = next(block for block in applied["blocks"] if block["block_id"] == block_id)
    clone = next(block for block in applied["blocks"] if block["block_id"] == clone_id)
    assert clone["analysis_ref"] == original["analysis_ref"]
    assert clone["evidence_digest"] == original["evidence_digest"]
    assert clone["facts"] == original["facts"]


def test_operation_payload_hash_is_stable():
    from backend.contracts.competition_c0 import BoardOperation
    op = BoardOperation.model_validate(operation(
        operation_id="op_hash", key="hash", title="指纹",
        refs=[{
            "result_id": "result_x",
            "run_id": "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "analysis_id": "analysis_" + "a" * 32,
            "evidence_digest": "a" * 64,
        }],
    ))
    assert operation_payload_hash("batch_x", op) == operation_payload_hash("batch_x", op)
    assert operation_payload_hash("batch_x", op) != operation_payload_hash("batch_y", op)
