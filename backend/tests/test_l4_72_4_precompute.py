"""L4.72.4 old-customer precompute regression tests."""
from __future__ import annotations

import json
import plistlib
import sys
import types
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import scripts.precompute_old_customer_9_sub_modules as precompute  # noqa: E402


def test_build_jobs_covers_hot_windows_and_customer_health_modules() -> None:
    jobs = precompute.build_jobs("2026-07-09")
    slugs = {job.slug for job in jobs}

    assert len(jobs) == len(precompute.HOT_WINDOWS) * len(precompute.SUB_MODULES)
    assert precompute.HOT_WINDOWS == (7, 30, 180, 365)
    assert {
        "overview",
        "repurchase-cycle",
        "cohort-retention",
        "value-tiers",
        "tier-flow",
        "rfm-analysis",
        "rfm-category-drilldown",
        "new-customer-conversion",
        "promotion-calendar",
        "channel-health-scores",
        "health-targets",
    }.issubset(slugs)


def test_precompute_runner_calls_existing_service_and_writes_json(tmp_path: Path, monkeypatch) -> None:
    module = types.ModuleType("fake_old_customer_service")

    def build(**kwargs):
        return {"ok": True, "params": kwargs}

    @contextmanager
    def fake_read_request_context(_query_type: str = "read"):
        yield

    module.build = build
    monkeypatch.setitem(sys.modules, "fake_old_customer_service", module)
    monkeypatch.setattr(precompute, "read_request_context", fake_read_request_context)

    job = precompute.PrecomputeJob(
        slug="fake",
        callable_path="fake_old_customer_service:build",
        params={"analysis_date": "2026-07-09", "period_days": 7},
        window_days=7,
        end_date="2026-07-09",
    )

    result = precompute.run_job(job, tmp_path)
    payload = json.loads(Path(result["path"]).read_text(encoding="utf-8"))

    assert result["status"] == "ok"
    assert payload["meta"]["callable"] == "fake_old_customer_service:build"
    assert payload["data"]["ok"] is True


def test_precompute_runner_uses_read_request_context(tmp_path: Path, monkeypatch) -> None:
    events: list[tuple[str, str]] = []
    module = types.ModuleType("fake_old_customer_read_context_service")

    def build(**kwargs):
        events.append(("service", kwargs["analysis_date"]))
        return {"ok": True}

    @contextmanager
    def fake_read_request_context(query_type: str = "read"):
        events.append(("enter", query_type))
        yield
        events.append(("exit", query_type))

    module.build = build
    monkeypatch.setitem(sys.modules, "fake_old_customer_read_context_service", module)
    monkeypatch.setattr(precompute, "read_request_context", fake_read_request_context)

    job = precompute.PrecomputeJob(
        slug="fake",
        callable_path="fake_old_customer_read_context_service:build",
        params={"analysis_date": "2026-07-09"},
        window_days=7,
        end_date="2026-07-09",
    )

    result = precompute.run_job(job, tmp_path)

    assert result["status"] == "ok"
    assert events == [
        ("enter", "old_customer_precompute"),
        ("service", "2026-07-09"),
        ("exit", "old_customer_precompute"),
    ]


def test_precompute_script_does_not_copy_orders_sql() -> None:
    src = (ROOT / "scripts/precompute_old_customer_9_sub_modules.py").read_text(encoding="utf-8")
    assert "FROM orders" not in src
    assert "backend.services.health" in src


def test_old_customer_precompute_plist_uses_python3_not_bash() -> None:
    plist_path = ROOT / "scripts/launchd/com.fuqing.old-customer-precompute.daily.plist"
    data = plistlib.loads(plist_path.read_bytes())
    args = data["ProgramArguments"]

    assert args[0].endswith("python3")
    assert all("bash" not in arg for arg in args)
    assert "precompute_old_customer_9_sub_modules.py" in args[1]
