"""Old SNAPSHOT read compatibility vs isolated competition-board/v1."""

from __future__ import annotations

import json
import os
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest

from backend.contracts.competition_c0 import CompetitionBoardSpec
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal
from backend.services.analytics.cockpit import (
    APPLICATION_ID as COCKPIT_APP_ID,
    EMPTY_BOARD_LIMITATION,
    LEGACY_BOARD_LIMITATION,
    CockpitStore,
    legacy_spec_payload,
)
from backend.services.analytics.cockpit_source import project_legacy_board_spec
from backend.services.analytics.competition_assets import CompetitionAssetService
from backend.services.analytics.saved_analyses import SavedAnalysisStore

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
CLOCK_MS = 1_800_000_000_000
CAPS = frozenset({"analysis:save", "analysis:read", "dashboard:read", "dashboard:update"})
SCOPE = frozenset({"channel-followup-fixture"})
ANALYSIS_ID = "analysis_" + "a" * 32


def actor(name="alice"):
    return AnalyticsPrincipal(name, CAPS, SCOPE)


def private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def succeeded_run() -> dict:
    return deepcopy(json.loads((FIXTURE_DIR / "analytics_saved_analysis_succeeded_run.json").read_text())["run"])


def snapshot_bundle() -> dict:
    run = succeeded_run()
    result = run["result"]
    return {
        "analysis_ref": {"analysis_id": ANALYSIS_ID, "version": 1},
        "snapshot": {
            "run_id": run["run_id"],
            "evidence_digest": run["evidence_digest"],
            "resolved_filters": deepcopy(result["resolved_filters"]),
            "data_snapshot_ref": result["data_snapshot_ref"],
            "as_of": result["as_of"],
        },
        "facts": deepcopy(result["facts"]),
        "limitations": list(result["limitations"]),
    }


def make_stack(tmp_path: Path):
    analyses = SavedAnalysisStore(private_dir(tmp_path / "saved"), clock=lambda: CLOCK_MS)
    cockpit = CockpitStore(private_dir(tmp_path / "cockpit"), clock=lambda: CLOCK_MS)
    service = CompetitionAssetService(
        private_dir(tmp_path / "competition"),
        analysis_store=analyses,
        cockpit_store=cockpit,
        clock=lambda: CLOCK_MS,
    )
    return service, analyses, cockpit


def test_empty_legacy_board_is_valid_read_only_spec(tmp_path):
    service, _analyses, cockpit = make_stack(tmp_path)
    board = cockpit.create(actor(), "create-1", {}).as_dict()
    spec = project_legacy_board_spec(cockpit.get(actor(), board["dashboard_id"]))
    CompetitionBoardSpec.model_validate(spec)
    assert spec["data_namespace"] == "analytics-cockpit/v1"
    assert spec["snapshot_compat"] == "READ_OLD_SNAPSHOT"
    assert spec["block_ids"] == []
    assert spec["limitations"] == [EMPTY_BOARD_LIMITATION]
    listed = service.list_boards(actor())
    assert listed[0]["board_id"] == board["dashboard_id"]
    document = service.get_board(actor(), board["dashboard_id"])
    assert document["spec"]["data_namespace"] == "analytics-cockpit/v1"
    assert document["snapshot_compat"] == "READ_OLD_SNAPSHOT"
    with pytest.raises(AnalyticsError) as readonly:
        service.preview_patch(actor(), {
            "board_id": board["dashboard_id"],
            "block_id": "card_x",
            "base_version": 1,
            "attempt_id": "attempt_legacy",
            "idempotency_key": "legacy-1",
            "intent": "STYLE_ONLY",
            "display_op": {
                "op": "display",
                "card_id": "card_x",
                "display_overrides": {"title": "不能写旧板"},
            },
        })
    assert readonly.value.status == 422
    assert readonly.value.code == "REJECT_UNSUPPORTED_VERSION"
    assert cockpit.get(actor(), board["dashboard_id"]).version == 1


def test_legacy_cards_project_as_read_old_snapshot(tmp_path):
    _service, _analyses, cockpit = make_stack(tmp_path)
    board = cockpit.create(actor(), "create-1", {}).as_dict()
    added = cockpit.apply(actor(), "add-1", board["dashboard_id"], "1", {"op": "add", **snapshot_bundle()})
    payload = legacy_spec_payload(added)
    spec = CompetitionBoardSpec.model_validate(payload)
    assert spec.data_namespace == "analytics-cockpit/v1"
    assert spec.snapshot_compat == "READ_OLD_SNAPSHOT"
    assert spec.block_ids == [added.cards[0]["card_id"]]
    assert spec.limitations == [LEGACY_BOARD_LIMITATION]


def test_new_boards_do_not_write_cockpit_sqlite(tmp_path):
    service, analyses, cockpit = make_stack(tmp_path)
    run = succeeded_run()
    analyses.register_succeeded_run(actor(), run)
    saved = analyses.save(actor(), "save-1", {
        "title": "首次观察到的渠道 / 30日二单率",
        "created_from_run_id": run["run_id"],
        "filters": deepcopy(run["request"]),
    })
    ref = {
        "result_id": "result_new",
        "run_id": saved.created_from_run_id,
        "analysis_id": saved.analysis_id,
        "evidence_digest": saved.snapshot["evidence_digest"],
        "completeness": "COMPLETE",
    }
    from backend.tests.test_competition_assets import batch_payload, fingerprint
    receipt = service.apply_batch(actor(), batch_payload(
        batch_id="batch_ns", layout_mode="ONE_BOARD_MULTI_BLOCK",
        operations=[{
            "operation_id": "op_ns",
            "idempotency_key": "ns",
            "request_fingerprint": fingerprint("op_ns"),
            "layout_mode": "ONE_BOARD_MULTI_BLOCK",
            "title": "新命名空间",
            "endorsed_result_refs": [ref],
        }],
    ))
    board_id = receipt["items"][0]["board_id"]
    document = service.get_board(actor(), board_id)
    assert document["spec"]["data_namespace"] == "competition-board/v1"
    assert document["spec"]["snapshot_compat"] == "ISOLATED_NEW"
    assert cockpit.list(actor()) == []
    with sqlite3.connect(cockpit.path) as con:
        assert con.execute("SELECT count(*) FROM dashboards").fetchone()[0] == 0
        assert con.execute("PRAGMA application_id").fetchone()[0] == COCKPIT_APP_ID
    with sqlite3.connect(service.store.path) as con:
        assert con.execute("SELECT count(*) FROM boards").fetchone()[0] == 1
        assert con.execute("SELECT data_namespace FROM boards").fetchone()[0] == "competition-board/v1"


def test_foreign_sqlite_is_refused(tmp_path):
    directory = private_dir(tmp_path / "foreign")
    path = directory / "competition_assets.sqlite3"
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        con.execute("INSERT INTO metadata VALUES ('kind', 'competition_board')")
        con.execute("PRAGMA application_id=1397572401")
        con.execute("PRAGMA user_version=1")
    from backend.services.analytics.competition_assets.store import CompetitionAssetStore
    with pytest.raises(ValueError, match="foreign"):
        CompetitionAssetStore(directory)


def test_downgrade_read_keeps_new_board_and_legacy_board(tmp_path):
    service, analyses, cockpit = make_stack(tmp_path)
    legacy = cockpit.create(actor(), "create-legacy", {"title": "旧板"}).as_dict()
    run = succeeded_run()
    analyses.register_succeeded_run(actor(), run)
    saved = analyses.save(actor(), "save-1", {
        "title": "首次观察到的渠道 / 30日二单率",
        "created_from_run_id": run["run_id"],
        "filters": deepcopy(run["request"]),
    })
    from backend.tests.test_competition_assets import batch_payload, fingerprint
    receipt = service.apply_batch(actor(), batch_payload(
        batch_id="batch_both", layout_mode="ONE_BOARD_MULTI_BLOCK",
        operations=[{
            "operation_id": "op_both",
            "idempotency_key": "both",
            "request_fingerprint": fingerprint("op_both"),
            "layout_mode": "ONE_BOARD_MULTI_BLOCK",
            "title": "新板",
            "endorsed_result_refs": [{
                "result_id": "result_both",
                "run_id": saved.created_from_run_id,
                "analysis_id": saved.analysis_id,
                "evidence_digest": saved.snapshot["evidence_digest"],
                "completeness": "COMPLETE",
            }],
        }],
    ))
    service.close()
    cockpit.close()
    analyses.close()
    restored_analyses = SavedAnalysisStore(tmp_path / "saved", clock=lambda: CLOCK_MS)
    restored_cockpit = CockpitStore(tmp_path / "cockpit", clock=lambda: CLOCK_MS)
    restored = CompetitionAssetService(
        tmp_path / "competition",
        analysis_store=restored_analyses,
        cockpit_store=restored_cockpit,
        clock=lambda: CLOCK_MS,
    )
    listed = restored.list_boards(actor())
    namespaces = {item["data_namespace"] for item in listed}
    assert namespaces == {"analytics-cockpit/v1", "competition-board/v1"}
    old = restored.get_board(actor(), legacy["dashboard_id"])
    new = restored.get_board(actor(), receipt["items"][0]["board_id"])
    assert old["spec"]["snapshot_compat"] == "READ_OLD_SNAPSHOT"
    assert new["spec"]["snapshot_compat"] == "ISOLATED_NEW"
    assert new["blocks"][0]["facts"]["totals"]["channel_repeat_ratio"] == 0.5
