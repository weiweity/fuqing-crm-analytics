"""A9 G4 independent acceptance. Wire fail-closed skeleton to the integration SUT.

Unimplemented entries FAIL. Implemented entries are compared to A9 goldens only.
Do not import A1/A2 expected tables. Do not bind 8000/5173/4327.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

A9_ROOT = Path(__file__).resolve().parents[2]
SUT_ROOT = Path(
    os.environ.get(
        "A9_SUT_ROOT",
        str(A9_ROOT),
    )
).resolve()
EVIDENCE = A9_ROOT / "docs/hackathon/parallel-competition-2026-09-09/evidence/A9"
FIXTURES = EVIDENCE / "fixtures"
CASE_IDS = [f"T{i:02d}" for i in range(1, 18)]
SHANGHAI = ZoneInfo("Asia/Shanghai")
FORBIDDEN_PORTS = {"8000", "5173", "4327"}
TOKEN = "a9-independent-http-token-32chars-min"


def prefer_sut() -> Path:
    sut = str(SUT_ROOT)
    a9 = str(A9_ROOT)
    if not (SUT_ROOT / "backend" / "services" / "metrics" / "competition_compute.py").is_file():
        pytest.fail(f"A9 fail-closed: SUT metrics missing at {SUT_ROOT}")
    if SUT_ROOT == A9_ROOT:
        if sut not in sys.path:
            sys.path.insert(0, sut)
        return SUT_ROOT
    cleaned = []
    for item in sys.path:
        try:
            resolved = str(Path(item).resolve())
        except OSError:
            cleaned.append(item)
            continue
        if resolved in {sut, a9}:
            continue
        cleaned.append(item)
    sys.path[:] = cleaned
    sys.path.insert(0, sut)
    for name in list(sys.modules):
        if name != "backend" and not name.startswith("backend."):
            continue
        if name == "backend.tests" or name.startswith("backend.tests."):
            continue
        module = sys.modules.get(name)
        filename = getattr(module, "__file__", "") or ""
        if filename.startswith(a9) or filename == "":
            del sys.modules[name]
    return SUT_ROOT


prefer_sut()


def load_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def require_module(dotted: str):
    prefer_sut()
    try:
        module = importlib.import_module(dotted)
    except ImportError as exc:
        pytest.fail(f"A9 fail-closed: {dotted} is not implemented on SUT ({exc})")
    filename = getattr(module, "__file__", "") or ""
    if filename.startswith(str(A9_ROOT)) and not filename.startswith(str(SUT_ROOT)):
        pytest.fail(f"A9 fail-closed: {dotted} resolved to A9 tree {filename}, not SUT")
    return module


def require_attr(dotted: str, name: str):
    module = require_module(dotted)
    if not hasattr(module, name):
        pytest.fail(f"A9 fail-closed: {dotted}.{name} missing")
    return getattr(module, name)


def assert_not_user_ports() -> None:
    for key in ("PORT", "UVICORN_PORT", "VITE_PORT", "DSH_PORT"):
        value = os.environ.get(key)
        if value and str(value) in FORBIDDEN_PORTS:
            pytest.fail(f"A9 must not bind user demo ports: {key}={value}")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def seed_orders(conn, orders: list[dict]) -> None:
    conn.execute(
        """
        CREATE TABLE orders (
            order_id VARCHAR,
            sub_order_id VARCHAR,
            user_id VARCHAR,
            pay_time TIMESTAMP,
            channel VARCHAR,
            actual_amount DOUBLE,
            is_member BOOLEAN,
            is_refund BOOLEAN,
            is_goujinjin BOOLEAN,
            order_status VARCHAR,
            product_id VARCHAR,
            spu_type VARCHAR
        )
        """
    )
    for order in orders:
        refunds = order.get("refunds") or []
        net = Decimal(str(order["actual_amount"])) - sum(
            (Decimal(str(item["amount"])) for item in refunds), Decimal("0")
        )
        lines = order.get("lines") or [{"sku": "SKU", "amount": order["actual_amount"]}]
        for index, line in enumerate(lines, start=1):
            conn.execute(
                """
                INSERT INTO orders VALUES (?, ?, ?, ?::TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    order["order_id"],
                    f"S{index}",
                    order["user_id"],
                    f"{order['paid_date']} 12:00:00",
                    order["channel"],
                    float(line["amount"]),
                    order.get("is_member"),
                    bool(order.get("is_refund")) or net <= 0,
                    False,
                    "交易关闭" if net <= 0 else "交易成功",
                    line.get("sku") or order.get("product") or "P",
                    "正装",
                ],
            )


def identities_from(result: dict, rfm: dict, analysis: dict) -> dict:
    cutoff = analysis["new_old_cutoff"]
    period_users = set(result.get("users") or [])
    old = set(result.get("old_users") or [])
    new = set(result.get("new_users") or [])
    out = {}
    for user_id, row in rfm.items():
        first = row.get("first_pay")
        identity = "OLD" if first and first <= cutoff else "NEW"
        period_gsv = Decimal("0.00")
        if user_id in period_users:
            if user_id in old:
                identity = "OLD"
            elif user_id in new:
                identity = "NEW"
        out[user_id] = {
            "identity": identity,
            "lifetime_f": int(row.get("f") or 0),
            "period_gsv": period_gsv,
            "in_period_buyers": user_id in period_users,
            "first_pay": first,
        }
    return out


class A9T05FeatureSource:
    """A9 C01–C10 source. Not A8 t05u* gold."""

    def __init__(self, fixture: dict):
        self.fixture = fixture
        self.pinned = tuple(fixture["snapshot"]["member_ids"])
        self.origin_channel = fixture["snapshot"]["original_channel"]
        self.origin_product = fixture["snapshot"]["original_product"]
        self.scope = "scope-brand-a"
        self.events = self._events()

    def _events(self):
        ObservationEvent = require_attr(
            "backend.services.analytics.competition_audience.features",
            "ObservationEvent",
        )
        items = []
        for row in self.fixture["year_2026_repurchase"]:
            paid = datetime.fromisoformat(f"{row['paid_date']}T12:00:00").replace(tzinfo=SHANGHAI)
            items.append(
                ObservationEvent(
                    customer_key=row["user_id"],
                    order_id=f"o-{row['user_id']}",
                    paid_at=paid,
                    channel=row["channel"],
                    product_ids=(row["product"],),
                    net_paid_minor=int(Decimal(str(row["amount"])) * 100),
                    permission_scope=self.scope,
                )
            )
        return tuple(items)

    def pinned_enrollment_keys(self, *, permission_scope: str, as_of, enrollment_window, source_tense: str, data_version: str, rule_version: str):
        if permission_scope != self.scope:
            return ()
        seen = []
        for key in (self.pinned[0], *self.pinned):
            if key not in seen:
                seen.append(key)
        return tuple(seen)

    def load_cohort_features(self, *, permission_scope: str, customer_keys, as_of, timezone: str, history_scope: dict, sample_mode: str, member_mode: str, source_tense: str, data_version: str, rule_version: str):
        CohortFeatureRow = require_attr(
            "backend.services.analytics.competition_audience.features",
            "CohortFeatureRow",
        )
        FeatureBundle = require_attr(
            "backend.services.analytics.competition_audience.features",
            "FeatureBundle",
        )
        wanted = customer_keys if customer_keys is not None else self.pinned
        rows = []
        for key in wanted:
            if key not in self.pinned or permission_scope != self.scope:
                continue
            rows.append(
                CohortFeatureRow(
                    customer_key=key,
                    synthetic_user_id=key,
                    first_paid_at=datetime(2025, 2, 10, 12, tzinfo=SHANGHAI),
                    first_channel=self.origin_channel,
                    first_product_ids=(self.origin_product,),
                    last_paid_at=datetime(2025, 11, 3, 12, tzinfo=SHANGHAI),
                    last_channel=self.origin_channel,
                    last_product_ids=(self.origin_product,),
                    valid_order_count_as_of=4,
                    valid_net_amount_as_of=7600,
                    recency_days_as_of=58,
                    member_status_as_of="unknown",
                    history_truncated=True,
                    source_tense=source_tense,
                    sample_mode_applied=sample_mode,
                    permission_scope=permission_scope,
                )
            )
        return FeatureBundle(
            rows=tuple(rows),
            coverage={"member_history_available": False, "history_truncated": True, "f_applied_for_reselect": False},
            member_history_available=False,
            f_grain_status="W4_ORDER_GRAIN",
            source_tense=source_tense,
            data_version=data_version,
            rule_version=rule_version,
            sample_mode_applied=sample_mode,
            timezone=timezone,
        )

    def load_observation_events(self, *, permission_scope: str, customer_keys, window, timezone: str, history_scope: dict, sample_mode: str, source_tense: str, published_at):
        allowed = set(customer_keys)
        out = []
        start = window.start_date
        end = window.end_date
        for event in self.events:
            if event.permission_scope != permission_scope:
                continue
            if event.customer_key not in allowed:
                continue
            day = event.paid_at.astimezone(SHANGHAI).date()
            if start <= day <= end:
                out.append(event)
        return tuple(out)


def a9_t05_payload(fixture: dict, kind: str, *, combine: str = "AND", extra=None) -> dict:
    snapshot = fixture["snapshot"]
    observation = fixture["observation"]
    body = {
        "cohort": {
            "cohort_id": "cohort_a9_t05_ly_f4_10",
            "enrollment_window": {"start_date": "2025-01-01", "end_date": snapshot["as_of"]},
            "observation_window": {
                "start_date": observation["start"],
                "end_date": observation["end"],
            },
            "enrollment_rule_version": "competition-cohort-rule-v1",
            "as_of": "2025-12-31T04:00:00.000000+00:00",
            "published_at": "2026-09-21T16:00:00.000000+00:00",
            "source_tense": "PUBLISHED_SNAPSHOT",
            "member_history_status": "UNKNOWN",
            "existing_family": "none",
            "rules": [{
                "rule_id": f"rule_{kind.lower()}",
                "kind": "NON_REPURCHASE",
                "non_repurchase": kind,
                "member_mark": "UNKNOWN",
                "f_threshold": None,
                "f_grain_status": "UNKNOWN",
                "channel_ids": [],
                "product_ids": [],
            }],
            "permission_scope": "scope-brand-a",
            "limitations": ["A9 independent T05 gold; last-year F>=4 frozen 10."],
        },
        "combine": combine,
        "source_result_ref": "result_a9_t05_gsv",
        "permission_scope": "scope-brand-a",
        "auto_send": False,
    }
    if extra:
        body.update(extra)
    return body


def private_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def competition_http(tmp_path: Path):
    create_app = require_attr("backend.analytics_competition_app", "create_competition_app")
    AnalyticsPrincipal = require_attr("backend.services.analytics.access", "AnalyticsPrincipal")
    B0IdentityRegistry = require_attr("backend.services.analytics.access", "B0IdentityRegistry")
    CockpitStore = require_attr("backend.services.analytics.cockpit", "CockpitStore")
    SavedAnalysisStore = require_attr("backend.services.analytics.saved_analyses", "SavedAnalysisStore")
    identities = B0IdentityRegistry()
    caps = frozenset({
        "analysis:save", "analysis:read", "dashboard:read", "dashboard:update",
        "cohort:read", "draft:write",
    })
    identities.grant(TOKEN, AnalyticsPrincipal("alice", caps, frozenset({
        "channel-followup-fixture", "brand-a", "scope-brand-a",
    })))
    identities.grant(
        "a9-other-actor-token-32chars-minimum",
        AnalyticsPrincipal("bob", caps, frozenset({"scope-brand-b", "brand-b"})),
    )
    analyses = SavedAnalysisStore(private_dir(tmp_path / "saved"))
    cockpit = CockpitStore(private_dir(tmp_path / "cockpit"))
    app = create_app(
        analyses, cockpit, identities,
        asset_state_dir=private_dir(tmp_path / "assets"),
        audience_state_dir=private_dir(tmp_path / "audience"),
    )
    return app, analyses, identities


def seed_saved_analysis(analyses, principal):
    payload = json.loads(
        (SUT_ROOT / "backend/tests/fixtures/analytics_saved_analysis_succeeded_run.json").read_text()
    )["run"]
    run = deepcopy(payload)
    analyses.register_succeeded_run(principal, run)
    return analyses.save(principal, "save-a9", {
        "title": "A9 board",
        "created_from_run_id": run["run_id"],
        "filters": deepcopy(run["request"]),
    })


def endorsed_ref(record) -> dict:
    binding = record.binding()
    return {
        "result_id": f"result_{binding['run_id'][4:]}",
        "run_id": binding["run_id"],
        "analysis_id": binding["analysis_id"],
        "evidence_digest": binding["evidence_digest"],
        "completeness": "COMPLETE",
    }


def fingerprint(tag: str) -> str:
    content_hash = require_attr("backend.services.analytics.resource_profile", "content_hash")
    return content_hash({"tag": tag})


def audience_client():
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    audience_router = require_attr("backend.routers.audience", "router")
    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        user = request.headers.get("x-test-user")
        if user:
            request.state.username = user
        return await call_next(request)

    app.include_router(audience_router)
    return TestClient(app)


def test_does_not_bind_user_demo_ports():
    assert_not_user_ports()
    assert SUT_ROOT.is_dir()


def test_real_sut_modules_are_importable_from_integration_tree():
    prefer_sut()
    compute = require_module("backend.services.metrics.competition_compute")
    assert SUT_ROOT.as_posix() in (getattr(compute, "__file__", "") or "")
    require_module("backend.routers.audience")
    require_module("backend.services.analytics.competition_assets")
    require_module("backend.services.analytics.competition_audience")
    require_module("backend.analytics_competition_app")
    board = SUT_ROOT / "dsh-plugins/analytics-workbench/src/client/competition-board/BoardWorkbench.tsx"
    if not board.is_file():
        pytest.fail("A9 fail-closed: competition-board UI missing on SUT")


def test_t06_http_unauthenticated_and_cross_actor(tmp_path, monkeypatch):
    assert_not_user_ports()
    monkeypatch.setattr("backend.routers.audience.calculate_audience_summary", lambda **k: {
        "year_label": "2026", "comp_year_label": "2025", "prev2_year_label": "2024",
        "metric_type": "GSV", "indicators": [{"field": "全店GSV", "kind": "money", "values_by_year": {"2026": 1}, "yoy": 0}],
        "channel_all": [], "channel_member": [],
    })
    client = audience_client()
    denied = client.get("/api/v1/audience/summary", params={"metric_type": "GSV", "period": "MTD"})
    assert denied.status_code == 401
    body = denied.json()["error"]
    assert body["code"] in {"UNAUTHENTICATED", "AUTH_REQUIRED"}
    created = client.get(
        "/api/v1/audience/summary",
        params={"metric_type": "GSV", "period": "MTD"},
        headers={"X-Test-User": "alice"},
    )
    assert created.status_code == 200
    result_id = created.json()["result_ref"]["result_id"]
    other = client.get(f"/api/v1/audience/results/{result_id}", headers={"X-Test-User": "bob"})
    assert other.status_code == 403
    assert other.json()["error"]["code"] == "FORBIDDEN"
    assert "alice" not in other.text
    from fastapi.testclient import TestClient

    app, _analyses, _identities = competition_http(tmp_path)
    boards = TestClient(app).get("/api/v1/analytics/competition/boards")
    assert boards.status_code == 401
    assert boards.json()["error"]["code"] == "UNAUTHENTICATED"


def test_t06_revoke_after_grant(tmp_path):
    from fastapi.testclient import TestClient

    app, analyses, identities = competition_http(tmp_path)
    AnalyticsPrincipal = require_attr("backend.services.analytics.access", "AnalyticsPrincipal")
    principal = AnalyticsPrincipal(
        "alice",
        frozenset({"analysis:save", "analysis:read", "dashboard:read", "dashboard:update", "cohort:read", "draft:write"}),
        frozenset({"channel-followup-fixture", "brand-a", "scope-brand-a"}),
    )
    saved = seed_saved_analysis(analyses, principal)
    ref = endorsed_ref(saved)
    headers = {"Authorization": f"Bearer {TOKEN}", "Idempotency-Key": "endorse-a9"}
    client = TestClient(app, headers=headers)
    first = client.post("/api/v1/analytics/competition/endorsements", json={"result_refs": [ref]})
    assert first.status_code == 201
    identities.revoke(TOKEN)
    revoked = client.get("/api/v1/analytics/catalog")
    assert revoked.status_code in {401, 403}
    assert "password" not in revoked.text.lower()
    assert "TOKEN" not in revoked.text


def test_t07_oversize_body_is_not_complete_success(tmp_path):
    from fastapi.testclient import TestClient

    app, _, _ = competition_http(tmp_path)
    client = TestClient(app, headers={"Authorization": f"Bearer {TOKEN}", "Idempotency-Key": "big"})
    huge = {"result_refs": [], "pad": "的" * 30000}
    response = client.post("/api/v1/analytics/competition/endorsements", json=huge)
    assert response.status_code in {400, 413, 422}
    payload = response.json()
    completeness = (payload.get("result_ref") or {}).get("completeness")
    assert completeness != "COMPLETE"
    empty = client.post("/api/v1/analytics/competition/endorsements", content=b"{", headers={"content-type": "application/json"})
    assert empty.status_code in {400, 422}
    assert empty.json().get("error", {}).get("code") != "SUCCEEDED_EMPTY"


def test_t07_stale_result_and_empty_vs_invalid(monkeypatch):
    monkeypatch.setattr("backend.routers.audience.calculate_audience_summary", lambda **k: {
        "year_label": "2026", "comp_year_label": "2025", "prev2_year_label": "2024",
        "metric_type": "GSV", "indicators": [], "channel_all": [], "channel_member": [],
    })
    client = audience_client()
    empty = client.get(
        "/api/v1/audience/summary",
        params={"metric_type": "GSV", "start_date": "2026-09-15", "end_date": "2026-09-21"},
        headers={"X-Test-User": "alice"},
    )
    assert empty.status_code == 200
    assert empty.json()["result_ref"]["completeness"] in {"EMPTY", "COMPLETE"}
    missing = client.get("/api/v1/audience/results/result_missing_a9", headers={"X-Test-User": "alice"})
    assert missing.status_code in {403, 404}
    assert missing.json()["error"]["code"] in {"FORBIDDEN", "NOT_FOUND", "RESULT_UNAVAILABLE"}


def test_t08_readonly_post_admission_and_503():
    QueryRouterMiddleware = require_attr("backend.middleware.query_router", "QueryRouterMiddleware")
    mw = QueryRouterMiddleware(lambda scope, receive, send: None)
    assert mw.classify("/api/v1/audience/summary", "POST") == "read"
    assert mw.classify("/api/v1/audience/summary", "GET") == "read"
    assert mw.classify("/api/v1/ad-hoc/export-excel", "POST") != "read"
    dual_conn = require_module("backend.services.dual_conn")

    def boom(timeout=5.0):
        raise dual_conn.ReadPoolTimeout("DuckDB read pool full, 请重试")

    original = dual_conn.get_read_connection
    dual_conn.get_read_connection = boom
    try:
        async def scenario():
            messages = []

            async def send(message):
                messages.append(message)

            async def receive():
                return {"type": "http.disconnect"}

            scope = {
                "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                "method": "GET", "path": "/api/v1/audience/summary",
                "raw_path": b"/api/v1/audience/summary", "query_string": b"",
                "headers": [(b"x-request-id", b"req_a9_503")],
                "client": ("127.0.0.1", 123), "server": ("testserver", 80), "scheme": "http",
            }
            await mw(scope, receive, send)
            return messages

        messages = asyncio.run(scenario())
        start = next(item for item in messages if item["type"] == "http.response.start")
        assert start["status"] == 503
        body = b"".join(item.get("body", b"") for item in messages if item["type"] == "http.response.body")
        payload = json.loads(body)
        assert payload["error"]["retryable"] is True
        assert payload["error"]["http_status"] == 503
        assert payload["error"]["code"] in {"STATE_UNAVAILABLE", "CAPACITY_BUSY"}
    finally:
        dual_conn.get_read_connection = original


def test_t08_late_attempt_publish_guard_missing_is_fail():
    app_mod = require_module("backend.analytics_competition_app")
    source = Path(app_mod.__file__).read_text(encoding="utf-8")
    if "late" not in source.lower() and "cancel" not in source.lower():
        pytest.fail("A9 T08: competition HTTP has no cancel/late-attempt publish guard")


def test_t09_http_endorse_batch_idempotency_and_partial(tmp_path):
    from fastapi.testclient import TestClient

    app, analyses, _identities = competition_http(tmp_path)
    AnalyticsPrincipal = require_attr("backend.services.analytics.access", "AnalyticsPrincipal")
    principal = AnalyticsPrincipal(
        "alice",
        frozenset({"analysis:save", "analysis:read", "dashboard:read", "dashboard:update", "cohort:read", "draft:write"}),
        frozenset({"channel-followup-fixture", "brand-a", "scope-brand-a"}),
    )
    saved = seed_saved_analysis(analyses, principal)
    ref = endorsed_ref(saved)
    client = TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})
    first = client.post(
        "/api/v1/analytics/competition/endorsements",
        headers={"Idempotency-Key": "endorse-same"},
        json={"result_refs": [ref]},
    )
    assert first.status_code == 201
    replay = client.post(
        "/api/v1/analytics/competition/endorsements",
        headers={"Idempotency-Key": "endorse-same"},
        json={"result_refs": [ref]},
    )
    assert replay.status_code in {200, 201}
    changed = dict(ref)
    changed["result_id"] = "result_other_payload"
    conflict = client.post(
        "/api/v1/analytics/competition/endorsements",
        headers={"Idempotency-Key": "endorse-same"},
        json={"result_refs": [changed]},
    )
    assert conflict.status_code == 409
    batch = {
        "schema_version": "competition-board-batch/v1",
        "batch_id": "batch_a9_partial",
        "layout_mode": "BATCH_MULTI_BOARD",
        "operations": [
            {
                "operation_id": "op_ok",
                "idempotency_key": "ok-board",
                "request_fingerprint": fingerprint("ok"),
                "layout_mode": "BATCH_MULTI_BOARD",
                "title": "成功板",
                "endorsed_result_refs": [ref],
            },
            {
                "operation_id": "op_bad",
                "idempotency_key": "bad-board",
                "request_fingerprint": fingerprint("bad"),
                "layout_mode": "BATCH_MULTI_BOARD",
                "title": "失败板",
                "endorsed_result_refs": [{
                    "result_id": "result_missing_a9",
                    "run_id": "run_dddddddddddddddddddddddddddddddd",
                    "evidence_digest": ref["evidence_digest"],
                    "completeness": "COMPLETE",
                }],
            },
        ],
    }
    receipt = client.post("/api/v1/analytics/competition/batches", json=batch)
    assert receipt.status_code == 200
    body = receipt.json()
    assert body["status"] == "PARTIAL"
    assert body["items"][0]["status"] == "SUCCEEDED"
    assert body["items"][1]["status"] != "SUCCEEDED"
    assert body["http_api"] == "CONNECTED"


def test_t10_t11_http_inflight_style_409_discard(tmp_path):
    from fastapi.testclient import TestClient

    app, analyses, _identities = competition_http(tmp_path)
    AnalyticsPrincipal = require_attr("backend.services.analytics.access", "AnalyticsPrincipal")
    principal = AnalyticsPrincipal(
        "alice",
        frozenset({"analysis:save", "analysis:read", "dashboard:read", "dashboard:update", "cohort:read", "draft:write"}),
        frozenset({"channel-followup-fixture", "brand-a", "scope-brand-a"}),
    )
    saved = seed_saved_analysis(analyses, principal)
    run_b = deepcopy(json.loads(
        (SUT_ROOT / "backend/tests/fixtures/analytics_saved_analysis_succeeded_run.json").read_text()
    )["run"])
    run_b["run_id"] = "run_cccccccccccccccccccccccccccccccc"
    analyses.register_succeeded_run(principal, run_b)
    saved_b = analyses.save(principal, "save-a9-b", {
        "title": "A9 board B",
        "created_from_run_id": run_b["run_id"],
        "filters": deepcopy(run_b["request"]),
    })
    ref = endorsed_ref(saved)
    ref_b = endorsed_ref(saved_b)
    client = TestClient(app, headers={"Authorization": f"Bearer {TOKEN}", "Idempotency-Key": "en"})
    client.post("/api/v1/analytics/competition/endorsements", json={"result_refs": [ref, ref_b]})
    created = client.post("/api/v1/analytics/competition/batches", json={
        "schema_version": "competition-board-batch/v1",
        "batch_id": "batch_a9_patch",
        "layout_mode": "ONE_BOARD_MULTI_BLOCK",
        "operations": [{
            "operation_id": "op_patch",
            "idempotency_key": "patch-board",
            "request_fingerprint": fingerprint("patch"),
            "layout_mode": "ONE_BOARD_MULTI_BLOCK",
            "title": "A9板",
            "endorsed_result_refs": [ref, ref_b],
        }],
    })
    board_id = created.json()["items"][0]["board_id"]
    document = client.get(f"/api/v1/analytics/competition/boards/{board_id}").json()
    block_id = document["spec"]["block_ids"][0]
    other_block = document["spec"]["block_ids"][1] if len(document["spec"]["block_ids"]) > 1 else block_id
    version = document["spec"]["version"]
    style = {
        "schema_version": "competition-board-patch/v1",
        "board_id": board_id,
        "block_id": block_id,
        "base_version": version,
        "attempt_id": "attempt_a9_style",
        "idempotency_key": "style-1",
        "intent": "STYLE_ONLY",
        "display_op": {"op": "display", "card_id": block_id, "display_overrides": {"title": "样式"}},
    }
    preview = client.post(f"/api/v1/analytics/competition/boards/{board_id}/preview", json=style)
    assert preview.status_code == 200
    switched = dict(style)
    switched["block_id"] = other_block
    switched["display_op"] = {"op": "display", "card_id": other_block, "display_overrides": {"title": "切B"}}
    locked = client.post(f"/api/v1/analytics/competition/boards/{board_id}/preview", json=switched)
    assert locked.status_code == 409
    target = client.get("/api/v1/analytics/competition/attempts/attempt_a9_style").json()
    assert target["board_id"] == board_id
    assert target["block_id"] == block_id
    discard = client.post("/api/v1/analytics/competition/attempts/attempt_a9_style/discard")
    assert discard.status_code == 200
    assert discard.json().get("undone") is False
    apply_body = dict(style)
    apply_body["attempt_id"] = "attempt_a9_save"
    apply_body["idempotency_key"] = "save-1"
    saved_patch = client.post(
        f"/api/v1/analytics/competition/boards/{board_id}/versions",
        headers={"If-Match": str(version)},
        json=apply_body,
    )
    assert saved_patch.status_code == 200
    conflict = client.post(
        f"/api/v1/analytics/competition/boards/{board_id}/versions",
        headers={"If-Match": str(version)},
        json={**apply_body, "attempt_id": "attempt_a9_save_b", "idempotency_key": "save-2"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] in {"VERSION_CONFLICT", "CONFLICT"}
    illegal = client.post(
        f"/api/v1/analytics/competition/boards/{board_id}/preview",
        json={**style, "attempt_id": "attempt_bad", "intent": "FILTER_CHANGE", "filter_change": {"op": "filter_change", "card_id": block_id, "local_filters": {"channel_ids": ["x"]}}},
    )
    assert illegal.status_code in {409, 422}


def test_t12_zero_candidates_and_no_autosend(tmp_path):
    CompetitionAudienceService = require_attr(
        "backend.services.analytics.competition_audience",
        "CompetitionAudienceService",
    )
    AnalyticsPrincipal = require_attr("backend.services.analytics.access", "AnalyticsPrincipal")
    fixture = load_json("t05_cohort.json")
    returned_only = deepcopy(fixture)
    returned_only["snapshot"]["member_ids"] = ["C01", "C02", "C03", "C04"]
    returned_only["year_2026_repurchase"] = [
        row for row in fixture["year_2026_repurchase"] if row["user_id"] in {"C01", "C02", "C03", "C04"}
    ]
    svc = CompetitionAudienceService(private_dir(tmp_path / "aud"), feature_source=A9T05FeatureSource(returned_only))
    actor = AnalyticsPrincipal("analyst.brand-a", frozenset({"cohort:read", "draft:write"}), frozenset({"scope-brand-a"}))
    zero = svc.preview_candidates(actor, a9_t05_payload(returned_only, "ORIGIN_CHANNEL_ABSENT", extra={"candidate_set_id": "cand_a9_zero"}))
    keys = zero["candidates"].customer_keys
    assert zero["candidates"].unique_count == 0
    assert keys == []
    assert zero["candidates"].explanations == []
    assert zero["auto_send"] is False
    with pytest.raises(Exception) as error:
        svc.preview_candidates(actor, a9_t05_payload(returned_only, "STOREWIDE_ABSENT", extra={"auto_send": True}))
    assert getattr(error.value, "param", None) == "auto_send"


def test_t12_and_or_copy_vs_rule_expire(tmp_path):
    CompetitionAudienceService = require_attr(
        "backend.services.analytics.competition_audience",
        "CompetitionAudienceService",
    )
    AnalyticsPrincipal = require_attr("backend.services.analytics.access", "AnalyticsPrincipal")
    fixture = load_json("t05_cohort.json")
    svc = CompetitionAudienceService(private_dir(tmp_path / "aud"), feature_source=A9T05FeatureSource(fixture))
    actor = AnalyticsPrincipal("analyst.brand-a", frozenset({"cohort:read", "draft:write"}), frozenset({"scope-brand-a"}))
    payload = a9_t05_payload(
        fixture,
        "ORIGIN_CHANNEL_ABSENT",
        extra={"candidate_set_id": "cand_a9_or"},
    )
    payload["cohort"]["rules"] = [
        payload["cohort"]["rules"][0],
        {**payload["cohort"]["rules"][0], "rule_id": "rule_store", "non_repurchase": "STOREWIDE_ABSENT"},
    ]
    payload["combine"] = "OR"
    union = svc.preview_candidates(actor, payload)
    assert union["candidates"].unique_count == 6
    assert set(union["candidates"].customer_keys) == set(fixture["sets"]["orig_channel_not_returned"])
    payload_and = deepcopy(payload)
    payload_and["combine"] = "AND"
    payload_and["candidate_set_id"] = "cand_a9_and"
    inter = svc.preview_candidates(actor, payload_and)
    assert inter["candidates"].unique_count == 4
    draft = svc.save_draft(actor, {
        "draft_id": "draft_a9_t12",
        "candidate_set_id": "cand_a9_and",
        "permission_scope": "scope-brand-a",
        "owner_id": "analyst.brand-a",
        "reviewer_id": "reviewer.ops",
        "review_by": "2026-09-15",
        "budget_cap_minor": 1,
        "control_design": "A",
        "stop_condition": "stop",
        "auto_send": False,
    })
    copied = svc.save_draft(actor, {
        "draft_id": "draft_a9_t12",
        "base_version": draft.version,
        "candidate_set_id": "cand_a9_and",
        "permission_scope": "scope-brand-a",
        "copy_only_change": True,
        "control_design": "B 文案",
        "stop_condition": "stop",
        "reviewer_id": "reviewer.ops",
        "review_by": "2026-09-15",
        "budget_cap_minor": 1,
        "auto_send": False,
    })
    assert copied.status.value == "DRAFT"
    assert copied.expired_reason is None
    svc.preview_candidates(actor, a9_t05_payload(fixture, "ORIGIN_PRODUCT_ABSENT", extra={"candidate_set_id": "cand_a9_rule"}))
    expired = svc.get_draft(actor, "draft_a9_t12", permission_scope="scope-brand-a")
    assert expired.status.value == "EXPIRED"
    assert expired.expired_reason == "RULE_CHANGED"


@pytest.mark.parametrize("item_id", ["T06", "T07", "T08", "T09", "T10", "T11", "T12"])
def test_checklist_is_independent_a9_text(item_id: str):
    checklist = load_json("t06_t12_checklist.json")["items"][item_id]
    assert len(checklist) >= 4
    joined = "\n".join(checklist)
    assert "A2" not in joined


def test_t13_real_model_is_not_run():
    row = next(item for item in load_json("t01_t17_matrix.json")["cases"] if item["id"] == "T13")
    assert row["requires_real_model"] is True
    assert os.environ.get("A9_REAL_MODEL") in {None, "", "0"}
    if Path(SUT_ROOT / "dsh-plugins/analytics-workbench/src/competition-acceptance-runtime.mjs").is_file():
        pytest.fail("T13 stub runtime must not be treated as a real model pass")


def test_t15_browser_uat_is_not_run():
    row = next(item for item in load_json("t01_t17_matrix.json")["cases"] if item["id"] == "T15")
    assert row["requires_browser"] is True
    assert row["requires_real_model"] is True


def test_t16_capacity_is_not_run():
    row = next(item for item in load_json("t01_t17_matrix.json")["cases"] if item["id"] == "T16")
    assert row["requires_capacity"] is True
    assert os.environ.get("A9_RUN_CAPACITY") not in {"1", "true", "TRUE"}


def test_t17_native_dsh_is_not_run():
    row = next(item for item in load_json("t01_t17_matrix.json")["cases"] if item["id"] == "T17")
    assert row["requires_browser"] is True
    assert os.environ.get("A9_INDEPENDENT_DSH") in {None, "", "0"}
    assert_not_user_ports()


def test_t01_http_end_before_start_is_422():
    client = audience_client()
    inverted = client.get(
        "/api/v1/audience/summary",
        params={"metric_type": "GSV", "start_date": "2026-09-15", "end_date": "2026-09-01"},
        headers={"X-Test-User": "alice"},
    )
    assert inverted.status_code == 422
    error = inverted.json()["error"]
    assert error["code"] in {"INVALID_REQUEST", "INVALID_PERIOD"}
    assert error["param"] == "end_date"


def test_t01_http_default_mtd_empty_on_sept1(monkeypatch):
    real = require_attr("backend.services.metrics.audience_summary", "calculate_audience_summary")

    def wrapped(**kwargs):
        kwargs["today"] = date(2026, 9, 1)
        kwargs["conn"] = kwargs.get("conn")
        return real(**kwargs)

    monkeypatch.setattr("backend.routers.audience.calculate_audience_summary", wrapped)

    class FakeDate(date):
        @classmethod
        def today(cls):
            return date(2026, 9, 1)

        @classmethod
        def fromisoformat(cls, value):
            return date.fromisoformat(value)

    monkeypatch.setattr("backend.routers.audience.date", FakeDate)
    client = audience_client()
    response = client.get(
        "/api/v1/audience/summary",
        params={"metric_type": "GSV"},
        headers={"X-Test-User": "alice"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    blob = json.dumps(payload, ensure_ascii=False)
    assert payload["result_ref"]["completeness"] in {"EMPTY", "COMPLETE"}
    if payload["result_ref"]["completeness"] != "EMPTY":
        pytest.fail("T01 HTTP default MTD on 2026-09-01 was not EMPTY")
    assert "2026-08-01" not in blob


def test_t01_http_period_mtd_on_sept1_must_not_be_august(monkeypatch):
    monkeypatch.setattr("backend.routers.audience.calculate_audience_summary", lambda **k: {
        "year_label": "2026", "comp_year_label": "2025", "prev2_year_label": "2024",
        "metric_type": "GSV", "indicators": [], "channel_all": [], "channel_member": [],
        "completeness": "EMPTY", "empty_reason": "NO_CURRENT_MONTH_DATA", "current_period": None,
    })

    class FakeDate(date):
        @classmethod
        def today(cls):
            return date(2026, 9, 1)

        @classmethod
        def fromisoformat(cls, value):
            return date.fromisoformat(value)

    monkeypatch.setattr("backend.routers.audience.date", FakeDate)
    client = audience_client()
    response = client.get(
        "/api/v1/audience/summary",
        params={"metric_type": "GSV", "period": "MTD"},
        headers={"X-Test-User": "alice"},
    )
    assert response.status_code == 200, response.text
    current = response.json()["current_period"]
    if current.get("start") == "2026-08-01":
        pytest.fail("T01 HTTP period=MTD on 2026-09-01 returned August as September MTD")


def test_t04_http_rejects_gmv():
    client = audience_client()
    gmv = client.get(
        "/api/v1/audience/summary",
        params={"metric_type": "GMV", "period": "MTD"},
        headers={"X-Test-User": "alice"},
    )
    assert gmv.status_code == 422
    assert gmv.json()["error"]["param"] == "metric_type"


def test_t03_http_cannot_silently_drop_sample_mode():
    client = audience_client()
    silent = client.get(
        "/api/v1/audience/summary",
        params={"metric_type": "GSV", "period": "MTD", "sample_mode": "INCLUDE"},
        headers={"X-Test-User": "alice"},
    )
    assert silent.status_code == 422
    assert silent.json()["error"]["param"] == "sample_mode"
