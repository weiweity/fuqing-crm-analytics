"""Owned synthetic HTTP fixture for the Node/DSH bridge integration test, not a demo service."""
import json
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic, sleep

import uvicorn

from backend.analytics_competition_app import create_competition_app
from backend.contracts.competition_computed import DATA_SCOPE
from backend.services.analytics.access import AnalyticsPrincipal, B0IdentityRegistry
from backend.services.analytics.competition_diagnosis.synthetic import materialize_synthetic_source
from backend.tests.test_competition_computed_results import snapshot


def run():
    assert sys.version_info >= (3, 14)
    assert sys.argv[1:] in ([], ["--known-money-unit"], ["--waterfall-scenario"], ["--funnel-scenario"], ["--cockpit-v2"])
    with TemporaryDirectory(prefix="library-board-http-") as directory:
        root = Path(directory)
        for name in ("source", "diagnosis", "boards", "pages"):
            (root / name).mkdir(mode=0o700)
        payload = snapshot()
        if sys.argv[1:] == ["--funnel-scenario"]:
            from backend.tests.test_board_funnel import frequency_snapshot
            payload = frequency_snapshot()
        if sys.argv[1:]:
            payload["money_unit"] = {"status": "KNOWN", "currency": "CNY", "amount_unit": "major"}
        if sys.argv[1:] == ["--waterfall-scenario"]:
            payload["orders"][0]["channel"] = "CH_LOST"
            payload["orders"][3]["channel"] = payload["orders"][4]["channel"] = "CH_NEW"
        source = materialize_synthetic_source(root / "source", payload)
        registry = B0IdentityRegistry()
        registry.grant("isolated-native-board-integration-token", AnalyticsPrincipal("alice",
            frozenset({"analysis:read", "analysis:save", "dashboard:read", "dashboard:update"}), frozenset({DATA_SCOPE})))
        app = create_competition_app(identities=registry, diagnosis_source=source,
            diagnosis_state_dir=root / "diagnosis", board_state_dir=root / "boards",
            page_state_dir=root / "pages" if sys.argv[1:] == ["--cockpit-v2"] else None)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False,
                loop="asyncio", http="h11", ws="none", lifespan="off"))
            worker = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            worker.start()
            try:
                deadline = monotonic() + 10
                while not server.started:
                    if not worker.is_alive() or monotonic() >= deadline:
                        raise RuntimeError("owned synthetic HTTP failed to start")
                    sleep(0.01)
                print(json.dumps({"port": listener.getsockname()[1], "contains_real_data": False}), flush=True)
                sys.stdin.readline()  # The owning Node test closes stdin to stop only this server.
            finally:
                server.should_exit = True
                worker.join(timeout=10)
                if worker.is_alive():
                    raise RuntimeError("owned synthetic HTTP did not stop")


if __name__ == "__main__":
    run()
