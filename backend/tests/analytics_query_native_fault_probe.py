"""Test-only query kernel: real runtime_app plus owned QueryProbeLauncher.

Never a production module. No extra HTTP routes, CRM import, or real DB.
Historical supervisor exits stay UNKNOWN; this probe does not close them.
"""

from __future__ import annotations

from backend.services.analytics.runtime_ports import runtime_port_base

import json
import sys
import threading

from backend.analytics_runtime import runtime_app
from backend.tests.analytics_native_probe import (
    NativeProbeCoordinator, prepare_probe_dir, probe_dir_for_state, require_probe_dir,
)
from backend.tests.analytics_query_worker_probe import QueryProbeLauncher

QUERY_ALLOWED_MODES = ("sql_hold", "unknown_schema", "passthrough")
DEFAULT_SEQUENCE = ("sql_hold", "unknown_schema", "passthrough")
HISTORICAL_SUPERVISOR_EXITS = {
    "count": 3, "status": "UNKNOWN", "closed_by_epipe": False,
    "verdict": "OPEN / 原因未证实",
}


class QueryNativeFaultCoordinator(NativeProbeCoordinator):
    """Same owned proof/release files, but the query-family worker probe."""

    def __call__(self, config, lease_fd):
        binding = config["binding"]
        with self._lock:
            if self._closed:
                raise RuntimeError("probe coordinator is closed")
            mode = self.sequence[self.index] if self.index < len(self.sequence) else "passthrough"
            if mode not in QUERY_ALLOWED_MODES:
                raise ValueError("unsupported query native-fault probe mode")
            self.index += 1
            launcher = QueryProbeLauncher(mode)
            self._owned.append(launcher)
        try:
            child = launcher(config, lease_fd)
        except BaseException:
            self._discard(launcher)
            raise
        if mode == "sql_hold":
            generation = self._begin_hold(binding)
            threading.Thread(target=self._watch_hold, args=(launcher, binding, generation),
                             daemon=True, name="query-native-fault-hold").start()
        return child


def prepare_query_probe_dir(path, sequence=DEFAULT_SEQUENCE):
    if any(item not in QUERY_ALLOWED_MODES for item in sequence):
        raise ValueError("invalid query native-fault probe sequence")
    return prepare_probe_dir(path, sequence=sequence)


def query_native_fault_app(config, *, bridge=None):
    """Real query runtime_app plus this instance's probe launcher."""
    probe_dir, sequence = require_probe_dir(probe_dir_for_state(config["state_dir"]))
    if any(item not in QUERY_ALLOWED_MODES for item in sequence):
        raise ValueError("invalid query native-fault probe sequence")
    coordinator = QueryNativeFaultCoordinator(probe_dir)
    app = runtime_app(config, bridge=bridge)
    app.state.workers.launch = coordinator
    app.state.probe = coordinator
    previous = app.state.dispatcher.close

    def close():
        try:
            previous()
        finally:
            coordinator.close()

    app.state.dispatcher.close = close
    return app


if __name__ == "__main__":
    if sys.version_info < (3, 14):
        raise SystemExit("B0 requires Python 3.14+")
    import uvicorn

    setup = json.loads(sys.stdin.readline(65537))
    if setup.get("family") != "channel_followup":
        raise SystemExit("query native-fault probe requires family=channel_followup")
    uvicorn.run(query_native_fault_app(setup), host="127.0.0.1", port=runtime_port_base(setup), access_log=False, log_level="warning",
                loop="asyncio", http="h11", ws="none")
