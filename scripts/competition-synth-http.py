#!/usr/bin/env python3
"""Synthetic competition HTTP on 18082. Does not bind 8000/4327/5173."""

from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HOST = "127.0.0.1"
PORT = int(os.environ.get("COMPETITION_SYNTH_PORT", "18082"))
TOKEN = os.environ.get("COMPETITION_HTTP_TOKEN", "b0-competition-synth-token-32chars")
STATE = Path(os.environ.get(
    "COMPETITION_SYNTH_STATE",
    str(ROOT / ".context" / "competition-synth"),
))


def web_origin() -> str:
    """Allow one explicitly selected, isolated DSH origin."""
    origin = os.environ.get("COMPETITION_SYNTH_WEB_ORIGIN", "http://127.0.0.1:14327")
    allowed = {f"http://127.0.0.1:{port}" for port in (4325, 4326, 4328, 4329, 14327)}
    if origin not in allowed:
        raise ValueError("COMPETITION_SYNTH_WEB_ORIGIN must name an isolated loopback DSH port")
    return origin


def _private(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def main() -> None:
    sys.path.insert(0, str(ROOT))
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn

    from backend.analytics_competition_app import create_competition_app
    from backend.services.analytics.access import AnalyticsPrincipal, B0IdentityRegistry
    from backend.services.analytics.cockpit import CockpitStore
    from backend.services.analytics.saved_analyses import SavedAnalysisStore

    if PORT in {4327, 8000, 5173, 14327}:
        raise SystemExit(f"refusing to bind user/demo port {PORT}")
    identities = B0IdentityRegistry()
    caps = frozenset({
        "analysis:save", "analysis:read", "dashboard:read", "dashboard:update",
        "cohort:read", "draft:write",
    })
    identities.grant(TOKEN, AnalyticsPrincipal("alice", caps, frozenset({
        "channel-followup-fixture", "brand-a", "scope-brand-a",
    })))
    analyses = SavedAnalysisStore(_private(STATE / "saved"))
    cockpit = CockpitStore(_private(STATE / "cockpit"))
    fixture = ROOT / "backend/tests/fixtures/analytics_saved_analysis_succeeded_run.json"
    if fixture.is_file():
        run = deepcopy(json.loads(fixture.read_text())["run"])
        principal = identities.resolve(f"Bearer {TOKEN}")
        analyses.register_succeeded_run(principal, run)
        analyses.save(principal, "save-synth", {
            "title": "synth GSV",
            "created_from_run_id": run["run_id"],
            "filters": deepcopy(run["request"]),
        })
    app = create_competition_app(
        analyses, cockpit, identities,
        asset_state_dir=_private(STATE / "assets"),
        audience_state_dir=_private(STATE / "audience"),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[web_origin()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    print(f"COMPETITION_SYNTH_READY http://{HOST}:{PORT}/api/v1/analytics/catalog", flush=True)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
