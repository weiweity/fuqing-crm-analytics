"""Self-contained B0 fixtures; runnable with --noconftest (no CRM boot)."""

import json
import os
import select
import sqlite3
import subprocess
import sys
import time
from contextlib import closing, contextmanager
from dataclasses import replace
from pathlib import Path

from backend.contracts.analytics import (
    AnalyticsB0Facts, AnalyticsB0Result, AnalyticsConversationRequest, AnalyticsRunRequest,
)
from backend.services.analytics.access import AnalyticsPrincipal
from backend.services.analytics.jobs import ExecutionObservation, RunStore
from backend.services.analytics.resource_profile import B0ResourceProfile, B0_SMALL_FIXTURE_PROFILE

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE = Path(__file__).with_name("analytics_run_fault_probe.py")


def profile(**overrides):
    return B0ResourceProfile(**{**B0_SMALL_FIXTURE_PROFILE, **overrides})


def actor(name="alice", *, capabilities=None, scopes=None):
    return AnalyticsPrincipal(name,
                              frozenset({"run:create", "run:read", "run:cancel"} if capabilities is None else capabilities),
                              frozenset({"b0-fixture"} if scopes is None else scopes))


def make_store(path, **kwargs):
    path.mkdir(mode=0o700, exist_ok=True)
    return RunStore(path, kwargs.pop("resource_profile", profile()), **kwargs)


def synthetic_fixture(path):
    from backend.analytics_fixture import create_synthetic_fixture

    path.mkdir(mode=0o700)
    return create_synthetic_fixture(path)


def conversation(store, principal=None, key="conversation"):
    return store.create_conversation(principal or actor(), key, AnalyticsConversationRequest())


def accept(store, principal=None, *, key="run", conversation_id=None, parent=None):
    principal = principal or actor()
    conv = conversation_id or conversation(store, principal).conversation_id
    return store.accept(principal, conv, key, AnalyticsRunRequest(question="查看合成渠道", parent_run_id=parent))


def observation(intent, outcome, *, exited=True, primary=None, **changes):
    result = ExecutionObservation(intent.run_id, intent.attempt_id, intent.session_id, intent.request_id,
                                  exited, outcome, primary_result_ref=primary)
    return replace(result, **changes)


def fixture_result():
    return AnalyticsB0Result(facts=AnalyticsB0Facts())


def successful_step(store, intent, principal=None, call_id="tool-1"):
    principal = principal or actor()
    step = store.reserve_step(principal, intent.run_id, intent.attempt_id, call_id)
    store.complete_step(principal, intent.run_id, intent.attempt_id, step.step_id, fixture_result())
    return step


@contextmanager
def sqlite_connection(path):
    # sqlite3's transaction context commits/rolls back but does not close.
    with closing(sqlite3.connect(path)) as con, con:
        yield con


def child_environment():
    # Explicit cwd + PYTHONPATH, without inherited provider keys or dotenv.
    return {
        "PATH": os.pathsep.join((str(Path(sys.executable).parent), "/usr/bin", "/bin")),
        "PYTHONPATH": str(REPO_ROOT), "PYTHONNOUSERSITE": "1", "PYTHON_DOTENV_DISABLED": "1",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
    }


def start_probe(payload):
    proc = subprocess.Popen([sys.executable, str(PROBE)], cwd=REPO_ROOT, env=child_environment(),
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    return proc


def receive(proc, timeout=5):
    # Never mix select(fd) with TextIOWrapper.readline(): the wrapper can read
    # the second event ahead while the fd becomes empty. Keep framing here so
    # adjacent child events remain observable without waiting for a third one.
    pending = getattr(proc, "_b0_stdout_pending", b"")
    deadline = time.monotonic() + timeout
    while b"\n" not in pending:
        readable, _, _ = select.select([proc.stdout], [], [], max(0, deadline - time.monotonic()))
        assert readable, "controlled child did not reach the required barrier"
        chunk = os.read(proc.stdout.fileno(), 65536)
        assert chunk, "controlled child exited before the required event"
        pending += chunk
        assert len(pending) <= 131072, "controlled child exceeded its protocol budget"
    line, proc._b0_stdout_pending = pending.split(b"\n", 1)
    return json.loads(line)


def send(proc, value):
    proc.stdin.write(json.dumps(value) + "\n")
    proc.stdin.flush()


def stop_owned(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    for stream in (proc.stdin, proc.stdout, proc.stderr):
        stream.close()


class Clock:
    def __init__(self):
        self.now = 1_800_000_000_000

    def __call__(self):
        return self.now
