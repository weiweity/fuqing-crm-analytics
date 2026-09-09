"""Owned test executable: real SQL barriers and bounded pressure, never app code."""

import json
import os
import select
import signal
import subprocess
import sys
import threading
import time
from contextlib import AbstractContextManager

from backend.tests.analytics_run_support import REPO_ROOT, child_environment


class ProbeDumpOnly:
    """Trusted test producer: run_child emits this payload via the normal result frame."""

    __slots__ = ("_payload",)

    def __init__(self, payload):
        self._payload = payload

    def model_dump(self, mode="json"):
        return self._payload


class ProbeLauncher(AbstractContextManager):
    def __init__(self, mode, *, ignore_term=False):
        self.mode, self.ignore_term = mode, ignore_term
        self.proof_read, self.proof_write = os.pipe()
        self.gate_read, self.gate_write = os.pipe()
        self.child = None
        self.pending = b""

    def __call__(self, config, lease_fd):
        payload = {**config, "probe": {"mode": self.mode, "ignore_term": self.ignore_term,
                                      "proof_fd": self.proof_write, "gate_fd": self.gate_read}}
        self.child = subprocess.Popen([sys.executable, "-m", "backend.tests.analytics_worker_probe"],
                                     cwd=REPO_ROOT, env=child_environment(), stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     pass_fds=(lease_fd, self.proof_write, self.gate_read), close_fds=True)
        self.child.stdin.write((json.dumps(payload) + "\n").encode())
        self.child.stdin.flush()
        return self.child

    def receive(self, timeout=8):
        deadline = time.monotonic() + timeout
        while b"\n" not in self.pending:
            available, _, _ = select.select([self.proof_read], [], [], max(0, deadline - time.monotonic()))
            assert available, "real SQL did not reach its controlled proof barrier"
            data = os.read(self.proof_read, 65536)
            assert data, "owned probe closed before its proof barrier"
            self.pending += data
            assert len(self.pending) <= 65536
        line, self.pending = self.pending.split(b"\n", 1)
        return json.loads(line)

    def release(self):
        os.write(self.gate_write, b"1")

    def close(self, *, close_worker_streams=True):
        # Only owned children; ensure a failed test cannot strand a live query.
        if self.child is not None and self.child.poll() is None:
            self.child.kill()
            self.child.wait(timeout=5)
        if self.child is not None and close_worker_streams:
            for stream in (self.child.stdin, self.child.stdout, self.child.stderr):
                stream.close()
        for fd in (self.proof_read, self.proof_write, self.gate_read, self.gate_write):
            os.close(fd)

    def __exit__(self, *_exc):
        self.close()


def main():
    from pathlib import Path

    import backend.analytics_worker as worker

    config = json.loads(sys.stdin.readline())
    if config.get("action") == "owner":
        run_owner(config)
        return
    probe = config.pop("probe")
    if probe["ignore_term"]:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)

    def proof(event, **details):
        os.write(probe["proof_fd"], (json.dumps({"event": event, "pid": os.getpid(),
                                               **config["binding"], **details}) + "\n").encode())

    def hold():
        if os.read(probe["gate_fd"], 1) == b"":
            # EOF does not itself finish the test SQL; the production control
            # watcher must terminate an orphan even while this query is stuck.
            threading.Event().wait()

    def workload(con, current):
        import duckdb

        if probe["mode"] == "sql_hold":
            def barrier(value):
                proof("SQL_ACTIVE")
                hold()
                return value

            try:
                con.create_function("b0_barrier", barrier, [duckdb.sqltypes.BIGINT], duckdb.sqltypes.BIGINT,
                                    side_effects=True)
                assert con.execute("SELECT b0_barrier(1)").fetchone() == (1,)
            except Exception as error:
                # Private proof pipe: fail at setup instead of waiting for an
                # SQL_ACTIVE event that can never arrive. No app error leak.
                proof("PROBE_SETUP_FAILED", error_type=type(error).__name__)
                raise
        elif probe["mode"] == "temp_exceed":
            # A bounded owned disposable, not an enlarged business database.
            with (Path(current["temp_dir"]) / "duckdb_temp_storage_PROBE-0.tmp").open("xb") as stream:
                stream.write(b"\0" * (2 * 1024 * 1024))
            proof("TEMP_WRITTEN", bytes=2 * 1024 * 1024)
            hold()
        elif probe["mode"] == "spill":
            try:
                # Window ordering prevents the optimizer dropping the sort.
                con.execute("SELECT max(rn) FROM (SELECT row_number() OVER (ORDER BY hash(i)) rn "
                            "FROM range(2000000) t(i))").fetchone()
            except duckdb.OutOfMemoryException as error:
                proof("ENGINE_LIMIT", temp_quota="max_temp_directory_size" in str(error)
                      or "offload" in str(error).lower())
                raise
            proof("SPILL_COMPLETE", temp_files=[entry.name for entry in Path(current["temp_dir"]).iterdir()])
        elif probe["mode"] == "foreign_frame":
            worker.emit({"type": "result", **current["binding"], "attempt_id": "foreign-attempt",
                         "profile_hash": current["profile_hash"],
                         "result": worker.query_fixture(con, current).model_dump(mode="json")})
        elif probe["mode"] in {"unknown_schema", "illegal_facts"}:
            # Correctly bound frame, invalid payload only. No extra error frame.
            payload = worker.query_fixture(con, current).model_dump(mode="json")
            if probe["mode"] == "unknown_schema":
                payload["schema_version"] = "analytics-run-b0/v99"
            else:
                payload["facts"] = {**payload["facts"], "repeat_ratio": 0.99}
            return ProbeDumpOnly(payload)
        elif probe["mode"] == "passthrough":
            pass
        elif probe["mode"] != "closed_hold":
            raise ValueError("unsupported test workload")
        return worker.query_fixture(con, current)

    worker.run_child(workload=workload, config=config)
    if probe["mode"] == "closed_hold":
        proof("CLOSED_FRAME_NOT_EXIT")
        hold()


def run_owner(payload):
    from pathlib import Path

    from backend.analytics_fixture import SyntheticFixture
    from backend.services.analytics.jobs import RunStore, StepReservation
    from backend.services.analytics.resource_profile import B0ResourceProfile
    from backend.services.analytics.worker import WorkerManager
    from backend.tests.analytics_run_support import actor

    def hook(point, _details=None):
        if point == payload.get("fault"):
            print(json.dumps({"event": point}), flush=True)
            sys.stdin.readline()

    store = RunStore(Path(payload["state_dir"]), B0ResourceProfile(**payload["profile"]), fault_hook=hook)
    intent = store.runtime_work()[0]["intent"]
    with ProbeLauncher("sql_hold", ignore_term=True) as launch:
        def forward_proof():
            proof = launch.receive()
            print(json.dumps(proof), flush=True)

        def start(config, lease_fd):
            child = launch(config, lease_fd)
            if payload["fault"] == "SQL_ACTIVE":
                threading.Thread(target=forward_proof, daemon=True).start()
            return child

        manager = WorkerManager(store, lambda _: actor(), SyntheticFixture(**payload["fixture"]),
                                launch=start, fault_hook=hook)
        manager.execute(actor(), intent, StepReservation(**payload["step"]))


if __name__ == "__main__":
    main()
