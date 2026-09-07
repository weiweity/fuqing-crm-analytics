"""Owned query-worker probe: real SQL barriers and mutants, never app code."""

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
from backend.tests.analytics_worker_probe import ProbeDumpOnly


class QueryProbeLauncher(AbstractContextManager):
    def __init__(self, mode, *, ignore_term=False):
        self.mode, self.ignore_term = mode, ignore_term
        self.proof_read, self.proof_write = os.pipe()
        self.gate_read, self.gate_write = os.pipe()
        self.child = None
        self.pending = b""

    def __call__(self, config, lease_fd):
        payload = {**config, "probe": {"mode": self.mode, "ignore_term": self.ignore_term,
                                      "proof_fd": self.proof_write, "gate_fd": self.gate_read}}
        self.child = subprocess.Popen(
            [sys.executable, "-m", "backend.tests.analytics_query_worker_probe"],
            cwd=REPO_ROOT, env=child_environment(), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            pass_fds=(lease_fd, self.proof_write, self.gate_read), close_fds=True,
        )
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

    def __exit__(self, *_exc):
        if self.child is not None and self.child.poll() is None:
            self.child.kill()
            self.child.wait(timeout=5)
        if self.child is not None:
            for stream in (self.child.stdin, self.child.stdout, self.child.stderr):
                stream.close()
        for fd in (self.proof_read, self.proof_write, self.gate_read, self.gate_write):
            os.close(fd)


def main():
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
            threading.Event().wait()

    def workload(con, current):
        import duckdb

        if probe["mode"] == "sql_hold":
            def barrier(value):
                proof("SQL_ACTIVE")
                hold()
                return value

            try:
                con.create_function("query_barrier", barrier, [duckdb.sqltypes.BIGINT], duckdb.sqltypes.BIGINT,
                                    side_effects=True)
                assert con.execute("SELECT query_barrier(1)").fetchone() == (1,)
            except Exception as error:
                proof("PROBE_SETUP_FAILED", error_type=type(error).__name__)
                raise
        elif probe["mode"] in {"unknown_schema", "wrong_n", "wrong_scope"}:
            from backend.contracts.analytics_query import (
                compute_filter_hash, filter_hash_payload, parse_query_datetime,
            )

            payload = worker.query_channel_followup(con, current).model_dump(mode="json")
            resolved = payload["resolved_filters"]
            if probe["mode"] == "unknown_schema":
                payload["schema_version"] = "analytics-channel-followup/v99"
            elif probe["mode"] == "wrong_n":
                other = 90 if payload["facts"]["observation_days"] != 90 else 30
                payload["facts"]["observation_days"] = other
                resolved["observation_days"] = other
            else:
                resolved["permission_scope"] = "b" * 64
            if probe["mode"] != "unknown_schema":
                digest = compute_filter_hash(filter_hash_payload(
                    as_of=parse_query_datetime(resolved["as_of"]),
                    channel_ids=resolved["channel_ids"],
                    data_digest=resolved["data_digest"],
                    data_snapshot_ref=resolved["data_snapshot_ref"],
                    data_version=resolved["data_version"],
                    observation_days=resolved["observation_days"],
                    permission_scope=resolved["permission_scope"],
                    resolved_cohort_end=parse_query_datetime(resolved["resolved_cohort_end"]),
                    resolved_cohort_start=parse_query_datetime(resolved["resolved_cohort_start"]),
                    timezone_name=resolved["timezone"],
                ))
                resolved["filter_hash"] = digest
                payload["filter_hash"] = digest
            return ProbeDumpOnly(payload)
        elif probe["mode"] == "passthrough":
            pass
        elif probe["mode"] != "closed_hold":
            raise ValueError("unsupported test workload")
        return worker.query_channel_followup(con, current)

    worker.run_child(workload=workload, config=config)
    if probe["mode"] == "closed_hold":
        proof("CLOSED_FRAME_NOT_EXIT")
        hold()


def run_owner(payload):
    from pathlib import Path

    from backend.analytics_query_fixture import ChannelFollowupFixture
    from backend.services.analytics.jobs import RunStore, StepReservation
    from backend.services.analytics.resource_profile import B0ResourceProfile
    from backend.services.analytics.worker import WorkerManager
    from backend.tests.test_analytics_query_jobs import query_actor

    def hook(point, _details=None):
        if point == payload.get("fault"):
            print(json.dumps({"event": point}), flush=True)
            sys.stdin.readline()

    store = RunStore(Path(payload["state_dir"]), B0ResourceProfile(**payload["profile"]),
                     family="channel_followup", fault_hook=hook)
    intent = store.runtime_work()[0]["intent"]
    with QueryProbeLauncher("sql_hold", ignore_term=True) as launch:
        def forward_proof():
            proof = launch.receive()
            print(json.dumps(proof), flush=True)

        def start(config, lease_fd):
            child = launch(config, lease_fd)
            if payload["fault"] == "SQL_ACTIVE":
                threading.Thread(target=forward_proof, daemon=True).start()
            return child

        manager = WorkerManager(store, lambda _: query_actor(), ChannelFollowupFixture(**payload["fixture"]),
                                launch=start, fault_hook=hook)
        manager.execute(query_actor(), intent, StepReservation(**payload["step"]))


if __name__ == "__main__":
    main()
