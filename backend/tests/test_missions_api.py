from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import duckdb
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.routers.missions import router
from scripts.synthetic.generate_hackathon_dataset import generate_dataset


ANALYSIS_DATE = __import__("datetime").date(2026, 8, 31)


@pytest.fixture(scope="module")
def synthetic_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db_path = tmp_path_factory.mktemp("mission-source") / "mission.duckdb"
    generate_dataset(
        db_path,
        seed=20260904,
        analysis_as_of_date=ANALYSIS_DATE,
        n_users=600,
        n_orders=2_100,
    )
    return db_path


@pytest.fixture
def mission_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    synthetic_db: Path,
) -> tuple[TestClient, Path, Path]:
    control_db = tmp_path / "control" / "missions.sqlite3"
    export_dir = tmp_path / "exports"
    monkeypatch.setenv("FQ_MISSION_DEMO_ENABLED", "1")
    monkeypatch.setenv("FQ_MISSION_DEMO_RESET_ENABLED", "1")
    monkeypatch.setenv("FQ_CRM_ADMINS", "JUDGE_DEMO")
    monkeypatch.setenv("FQ_SYNTHETIC_DB_PATH", str(synthetic_db))
    monkeypatch.setenv("FQ_MISSION_CONTROL_DB", str(control_db))
    monkeypatch.setenv("FQ_MISSION_EXPORT_DIR", str(export_dir))

    app = FastAPI()

    @app.middleware("http")
    async def inject_authenticated_actor(request: Request, call_next):
        request.state.username = request.headers.get("X-Test-Actor", "JUDGE_DEMO")
        return await call_next(request)

    app.include_router(router)
    return TestClient(app), control_db, export_dir


def test_mission_chain_from_today_to_draft_export(
    mission_client: tuple[TestClient, Path, Path],
    synthetic_db: Path,
) -> None:
    client, control_db, export_dir = mission_client
    source_mtime_ns = synthetic_db.stat().st_mtime_ns

    today_response = client.get("/api/v1/missions/today")
    assert today_response.status_code == 200
    today = today_response.json()
    assert today["status"] == "AWAITING_APPROVAL"
    assert today["version"] == 1
    assert today["decision"]["volume_leader"] == "直播"
    assert today["decision"]["quality_leader"] == "货架"
    assert today["target_audience"]["eligible_customers"] > 0
    assert today["data_provenance"]["data_profile"] == "synthetic"
    assert today["data_provenance"]["contains_real_data"] is False
    assert today["demo_controls"] == {"reset_enabled": True}

    question = "哪个渠道粘性最强？"
    diagnose_response = client.post(
        "/api/v1/missions/diagnose",
        json={"question": question},
    )
    assert diagnose_response.status_code == 200
    diagnosis = diagnose_response.json()
    assert diagnosis["intent"] == "CHANNEL_QUALITY"
    assert diagnosis["answer_mode"] == "DETERMINISTIC_TOOL"
    assert "货架" in diagnosis["answer"]

    mission_id = today["mission_id"]
    export_before_approval = client.post(
        f"/api/v1/missions/{mission_id}/audience-export",
        headers={"If-Match": "1", "Idempotency-Key": "export-too-early"},
    )
    assert export_before_approval.status_code == 409

    missing_headers = client.post(
        f"/api/v1/missions/{mission_id}/approve",
        json={"decision": "APPROVE"},
    )
    assert missing_headers.status_code == 428

    approval_headers = {"If-Match": "1", "Idempotency-Key": "approve-demo-001"}
    approval_response = client.post(
        f"/api/v1/missions/{mission_id}/approve",
        headers=approval_headers,
        json={"decision": "APPROVE", "note": "同意生成合成名单"},
    )
    assert approval_response.status_code == 200
    approved = approval_response.json()
    assert approved["status"] == "APPROVED"
    assert approved["version"] == 2
    assert approved["approval"]["approved_by"] == "JUDGE_DEMO"

    stale_approval = client.post(
        f"/api/v1/missions/{mission_id}/approve",
        headers={"If-Match": "1", "Idempotency-Key": "approve-stale"},
        json={"decision": "APPROVE"},
    )
    assert stale_approval.status_code == 409

    repeated_approval = client.post(
        f"/api/v1/missions/{mission_id}/approve",
        headers=approval_headers,
        json={"decision": "APPROVE", "note": "同意生成合成名单"},
    )
    assert repeated_approval.status_code == 200
    assert repeated_approval.json() == approved

    cross_actor_replay = client.post(
        f"/api/v1/missions/{mission_id}/approve",
        headers={**approval_headers, "X-Test-Actor": "OTHER_JUDGE"},
        json={"decision": "APPROVE", "note": "同意生成合成名单"},
    )
    assert cross_actor_replay.status_code == 409

    export_headers = {"If-Match": "2", "Idempotency-Key": "export-demo-001"}
    export_response = client.post(
        f"/api/v1/missions/{mission_id}/audience-export",
        headers=export_headers,
    )
    assert export_response.status_code == 200
    draft_export = export_response.json()
    assert draft_export["export_status"] == "DRAFT_EXPORT_READY"
    assert draft_export["mission_status"] == "WAITING_MEASUREMENT"
    assert draft_export["mission_version"] == 3
    assert draft_export["row_count"] == (
        draft_export["experiment_count"] + draft_export["holdout_count"]
    )
    assert draft_export["holdout_count"] > 0

    csv_path = export_dir / f"{draft_export['export_id']}.csv"
    assert csv_path.is_file()
    assert csv_path.stat().st_mode & 0o777 == 0o600
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == draft_export["row_count"]
    assert set(rows[0]) == {"synthetic_user_id", "mission_id", "experiment_arm"}
    assert all(row["synthetic_user_id"].startswith("SYN-U-") for row in rows)
    assert {row["experiment_arm"] for row in rows} == {"EXPERIMENT", "HOLDOUT"}

    repeated_export = client.post(
        f"/api/v1/missions/{mission_id}/audience-export",
        headers=export_headers,
    )
    assert repeated_export.status_code == 200
    assert repeated_export.json() == draft_export

    download_response = client.get(draft_export["download_url"])
    assert download_response.status_code == 200
    assert download_response.content == csv_path.read_bytes()

    latest = client.get(f"/api/v1/missions/{mission_id}").json()
    assert latest["status"] == "WAITING_MEASUREMENT"
    assert latest["version"] == 3
    assert latest["latest_export"] == draft_export
    assert control_db.is_file()

    reset_headers = {"If-Match": "3", "Idempotency-Key": "reset-demo-001"}
    reset_response = client.post(
        f"/api/v1/missions/{mission_id}/demo-reset",
        headers=reset_headers,
    )
    assert reset_response.status_code == 200
    reset = reset_response.json()
    assert reset["status"] == "AWAITING_APPROVAL"
    assert reset["version"] == 4
    assert reset["approval"] is None
    assert reset["latest_export"] is None
    assert not csv_path.exists()
    archived_csv = export_dir / ".reset-archive" / mission_id / "v3" / csv_path.name
    assert archived_csv.is_file()
    assert archived_csv.read_bytes() == download_response.content

    repeated_reset = client.post(
        f"/api/v1/missions/{mission_id}/demo-reset",
        headers=reset_headers,
    )
    assert repeated_reset.status_code == 200
    assert repeated_reset.json() == reset

    reused_approval_key = client.post(
        f"/api/v1/missions/{mission_id}/approve",
        headers={"If-Match": "4", "Idempotency-Key": "approve-demo-001"},
        json={"decision": "APPROVE", "note": "同意生成合成名单"},
    )
    assert reused_approval_key.status_code == 200
    assert reused_approval_key.json()["version"] == 5
    assert synthetic_db.stat().st_mtime_ns == source_mtime_ns


def test_demo_reset_requires_admin_and_explicit_flag(
    mission_client: tuple[TestClient, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _, _ = mission_client
    mission = client.get("/api/v1/missions/today").json()
    endpoint = f"/api/v1/missions/{mission['mission_id']}/demo-reset"
    headers = {"If-Match": str(mission["version"]), "Idempotency-Key": "reset-guard"}

    not_admin = client.post(endpoint, headers={**headers, "X-Test-Actor": "OTHER_JUDGE"})
    assert not_admin.status_code == 403

    monkeypatch.setenv("FQ_MISSION_DEMO_RESET_ENABLED", "0")
    disabled = client.post(endpoint, headers=headers)
    assert disabled.status_code == 404
    assert "未启用" in disabled.json()["detail"]


def test_demo_reset_rejects_stale_version_without_changing_state(
    mission_client: tuple[TestClient, Path, Path],
) -> None:
    client, _, _ = mission_client
    mission = client.get("/api/v1/missions/today").json()
    response = client.post(
        f"/api/v1/missions/{mission['mission_id']}/demo-reset",
        headers={"If-Match": "99", "Idempotency-Key": "reset-stale"},
    )
    assert response.status_code == 409
    current = client.get("/api/v1/missions/today").json()
    assert current["status"] == "AWAITING_APPROVAL"
    assert current["version"] == 1


def test_mission_api_is_fail_closed_when_demo_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FQ_MISSION_DEMO_ENABLED", raising=False)
    app = FastAPI()

    @app.middleware("http")
    async def inject_authenticated_actor(request: Request, call_next):
        request.state.username = "JUDGE_DEMO"
        return await call_next(request)

    app.include_router(router)
    response = TestClient(app).get("/api/v1/missions/today")
    assert response.status_code == 404
    assert "未启用" in response.json()["detail"]


def test_mission_api_rejects_manifest_not_marked_synthetic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    synthetic_db: Path,
) -> None:
    copied_db = tmp_path / "tampered.duckdb"
    copied_db.write_bytes(synthetic_db.read_bytes())
    manifest = __import__("json").loads(
        synthetic_db.with_suffix(".manifest.json").read_text(encoding="utf-8")
    )
    manifest["database_filename"] = copied_db.name
    manifest["contains_real_data"] = True
    copied_db.with_suffix(".manifest.json").write_text(
        __import__("json").dumps(manifest),
        encoding="utf-8",
    )
    monkeypatch.setenv("FQ_MISSION_DEMO_ENABLED", "1")
    monkeypatch.setenv("FQ_SYNTHETIC_DB_PATH", str(copied_db))
    monkeypatch.setenv("FQ_MISSION_CONTROL_DB", str(tmp_path / "control.sqlite3"))
    monkeypatch.setenv("FQ_MISSION_EXPORT_DIR", str(tmp_path / "exports"))
    app = FastAPI()

    @app.middleware("http")
    async def inject_authenticated_actor(request: Request, call_next):
        request.state.username = "JUDGE_DEMO"
        return await call_next(request)

    app.include_router(router)
    response = TestClient(app).get("/api/v1/missions/today")
    assert response.status_code == 503
    assert "synthetic" in response.json()["detail"]


def test_mission_api_revalidates_database_content_at_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    synthetic_db: Path,
) -> None:
    copied_db = tmp_path / "tampered-content.duckdb"
    copied_db.write_bytes(synthetic_db.read_bytes())
    manifest = json.loads(
        synthetic_db.with_suffix(".manifest.json").read_text(encoding="utf-8")
    )
    manifest["database_filename"] = copied_db.name
    manifest.pop("manifest_sha256")
    manifest_payload = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    manifest["manifest_sha256"] = f"sha256:{hashlib.sha256(manifest_payload).hexdigest()}"
    copied_db.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    synthetic_phone = "138" + "0" * 8
    conn = duckdb.connect(str(copied_db))
    try:
        conn.execute(
            "UPDATE synthetic_products SET generic_product_name = ? WHERE product_code = ?",
            [f"联系 {synthetic_phone}", "SYN-P-001"],
        )
    finally:
        conn.close()

    monkeypatch.setenv("FQ_MISSION_DEMO_ENABLED", "1")
    monkeypatch.setenv("FQ_SYNTHETIC_DB_PATH", str(copied_db))
    monkeypatch.setenv("FQ_MISSION_CONTROL_DB", str(tmp_path / "control.sqlite3"))
    monkeypatch.setenv("FQ_MISSION_EXPORT_DIR", str(tmp_path / "exports"))
    app = FastAPI()

    @app.middleware("http")
    async def inject_authenticated_actor(request: Request, call_next):
        request.state.username = "JUDGE_DEMO"
        return await call_next(request)

    app.include_router(router)

    response = TestClient(app).get("/api/v1/missions/today")
    assert response.status_code == 503
    assert "隐私或结构校验失败" in response.json()["detail"]


def test_mission_api_rejects_control_db_aliasing_analysis_db(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    synthetic_db: Path,
) -> None:
    monkeypatch.setenv("FQ_MISSION_DEMO_ENABLED", "1")
    monkeypatch.setenv("FQ_SYNTHETIC_DB_PATH", str(synthetic_db))
    monkeypatch.setenv("FQ_MISSION_CONTROL_DB", str(synthetic_db))
    monkeypatch.setenv("FQ_MISSION_EXPORT_DIR", str(tmp_path / "exports"))
    app = FastAPI()

    @app.middleware("http")
    async def inject_authenticated_actor(request: Request, call_next):
        request.state.username = "JUDGE_DEMO"
        return await call_next(request)

    app.include_router(router)

    response = TestClient(app).get("/api/v1/missions/today")
    assert response.status_code == 503
    assert "物理隔离" in response.json()["detail"]


def test_diagnose_covers_lifecycle_and_product_intents(
    mission_client: tuple[TestClient, Path, Path],
) -> None:
    client, _, _ = mission_client

    lifecycle = client.post(
        "/api/v1/missions/diagnose",
        json={"question": "生命周期里有多少待补货客户？"},
    )
    assert lifecycle.status_code == 200
    assert lifecycle.json()["intent"] == "LIFECYCLE_DISTRIBUTION"
    assert lifecycle.json()["evidence"]

    product = client.post(
        "/api/v1/missions/diagnose",
        json={"question": "哪个产品更适合做老客？"},
    )
    assert product.status_code == 200
    assert product.json()["intent"] == "PRODUCT_ROLE"
    assert product.json()["evidence"]


def test_main_app_registers_documented_mission_routes() -> None:
    from backend.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/missions/today" in paths
    assert "/api/v1/missions/diagnose" in paths
    assert "/api/v1/missions/{mission_id}/approve" in paths
    assert "/api/v1/missions/{mission_id}/audience-export" in paths
    assert "/api/v1/missions/{mission_id}/demo-reset" in paths
    assert (
        "/api/v1/missions/{mission_id}/audience-exports/{export_id}/download"
        in paths
    )
    assert TestClient(app).get("/api/v1/missions/today").status_code == 401

    operation_ids = {
        operation["operationId"]
        for path in paths.values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    }
    assert {
        "mission_get_today",
        "mission_diagnose",
        "mission_get",
        "mission_approve",
        "mission_create_draft_export",
        "mission_reset_demo",
        "mission_download_draft_export",
    }.issubset(operation_ids)
