"""FastAPI-owned physical worker adapter with one durable shared computation slot.

Handles are kept only to supervise children of this process. Business state,
budgets and recovery decisions stay in RunStore. Restart recovery checks the
persisted inode lease and never adopts or kills a process by its saved PID.
"""

import json
import os
import re
import selectors
import subprocess
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

import psutil

from backend.contracts.analytics import AnalyticsB0Result
from .access import AnalyticsError, require
from .execution_lease import create_lease
from .resource_profile import MIB

REPO_ROOT = Path(__file__).resolve().parents[3]


def spawn_worker(config, lease_fd):
    env = {
        "PATH": os.pathsep.join((str(Path(sys.executable).parent), "/usr/bin", "/bin")),
        "PYTHONPATH": str(REPO_ROOT), "PYTHONNOUSERSITE": "1", "PYTHON_DOTENV_DISABLED": "1",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1", "TMPDIR": config["temp_dir"],
    }
    child = subprocess.Popen([sys.executable, "-m", "backend.analytics_worker"], cwd=REPO_ROOT, env=env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             pass_fds=(lease_fd,), close_fds=True)
    try:
        child.stdin.write((json.dumps(config, allow_nan=False) + "\n").encode())
        child.stdin.flush()
    except BaseException:
        child.kill()
        child.wait(timeout=3)
        for stream in (child.stdin, child.stdout, child.stderr):
            stream.close()
        raise
    return child


def temp_bytes(directory):
    """Bounded scan of this execution's own temp tree; never follow links."""
    total, count = 0, 0
    pending = [directory]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                count += 1
                if count > 1024 or entry.is_symlink():
                    raise ValueError("unexpected worker temp tree")
                try:
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                    else:
                        raise ValueError("unexpected worker temp object")
                except FileNotFoundError:
                    continue  # DuckDB can remove a disposable between scan and stat.
    return total


class WorkerManager:
    def __init__(self, store, resolve_actor, fixture, *, launch=spawn_worker, fault_hook=None):
        fixture.validate()
        self.store, self.resolve_actor, self.fixture = store, resolve_actor, fixture
        self.launch, self.fault_hook = launch, fault_hook
        self._owned = set()
        self._mutex = threading.Lock()

    def _hook(self, point, payload):
        if self.fault_hook is not None:
            self.fault_hook(point, payload)

    def recover(self):
        """Called by the single dispatcher. Busy/missing leases retain slots."""
        for record in self.store.worker_records():
            with self._mutex:
                owned_here = record["execution_id"] in self._owned
            if owned_here:
                continue
            try:
                self.store.worker_exited(record["execution_id"], exit_code=None,
                                         error_code="EXECUTION_UNKNOWN", metrics={"recovered_lease_exit": True})
            except (OSError, ValueError, AnalyticsError):
                # A startup race, a still-live orphan or missing durable state
                # is not a release signal and does not authorize PID killing.
                continue

    def _stop_reason(self, record):
        principal = self.resolve_actor(record["owner"])
        try:
            if principal is None or principal.actor_id != record["owner"]:
                return "PERMISSION_REVOKED"
            require(principal, "run:create")
        except AnalyticsError:
            return "PERMISSION_REVOKED"
        if record["cancel_reason"]:
            return "TOOL_FAILED" if record["cancel_reason"] == "USER_REQUEST" else record["cancel_reason"]
        if min(record["deadline_ms"], record["run_deadline_ms"]) <= self.store.clock():
            return "TIMEOUT"
        if record["run_status"] != "RUNNING":
            return "EXECUTION_UNKNOWN"
        return None

    def execute(self, principal, intent, step):
        # The child validates before opening DuckDB and again before emitting a
        # result. Execute-time validation belongs inside that leased protocol:
        # a parent preflight exception would leave no durable failure/exit proof.
        execution_id = "exec_" + uuid4().hex
        fd, dev, ino, temporary = create_lease(self.store.directory, execution_id)
        binding = {"execution_id": execution_id, "run_id": intent.run_id,
                   "attempt_id": intent.attempt_id, "step_id": step.step_id}
        child, registered = None, False
        result, ready, closed, error = None, False, False, None
        metrics = {"rss_peak_bytes": 0, "temp_peak_bytes": 0, "forced_kill": False}
        started = time.monotonic()
        with self._mutex:
            self._owned.add(execution_id)
        try:
            self.store.begin_worker(principal, intent.run_id, intent.attempt_id, step.step_id, execution_id, dev, ino)
            registered = True
            config = {"binding": binding, "profile": self.store.profile.model_dump(), "profile_hash": self.store.profile.digest,
                      "fixture": asdict(self.fixture), "lease_fd": fd, "temp_dir": str(temporary)}
            child = self.launch(config, fd)
            # Closing (not unlocking) leaves the inherited description held by
            # the child. There is no unleased interval before or after spawn.
            os.close(fd)
            fd = None
            self._hook("worker:spawned", {**binding, "pid": child.pid})
            self.store.worker_started(execution_id, child.pid)
            process = psutil.Process(child.pid)
            pending, stderr_bytes, frames, stop_started = b"", 0, 0, None
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ, "stdout")
                selector.register(child.stderr, selectors.EVENT_READ, "stderr")
                while child.poll() is None or selector.get_map():
                    if child.poll() is None:
                        try:
                            record = self.store.worker_records(execution_id=execution_id)[0]
                            error = error or self._stop_reason(record)
                            metrics["rss_peak_bytes"] = max(metrics["rss_peak_bytes"], process.memory_info().rss)
                            metrics["temp_peak_bytes"] = max(metrics["temp_peak_bytes"], temp_bytes(temporary))
                            if (metrics["rss_peak_bytes"] > self.store.profile.worker_rss_observation_mib * MIB
                                    or metrics["temp_peak_bytes"] > self.store.profile.worker_temp_mib * MIB):
                                error = "RESOURCE_EXCEEDED"
                        except psutil.NoSuchProcess:
                            pass
                        except (OSError, ValueError, AnalyticsError, IndexError, psutil.Error):
                            error = error or "EXECUTION_UNKNOWN"
                        if error and stop_started is None:
                            try:
                                self.store.request_stop(intent.run_id, intent.attempt_id, error)
                            except AnalyticsError:
                                pass  # Physical stop still occurs; persistence failure does not free a slot.
                            child.terminate()
                            stop_started = time.monotonic()
                            self._hook("worker:stop-requested", {**binding, "pid": child.pid, "error": error})
                        if stop_started is not None and time.monotonic() - stop_started >= 0.5:
                            child.kill()
                            metrics["forced_kill"] = True
                    for key, _events in selector.select(timeout=0.02):
                        data = os.read(key.fileobj.fileno(), 65536)
                        if not data:
                            selector.unregister(key.fileobj)
                            continue
                        if key.data == "stderr":
                            stderr_bytes += len(data)
                            if stderr_bytes > 65536:
                                error = "RESOURCE_EXCEEDED"
                            continue  # Driver details/paths are not public diagnostics.
                        pending += data
                        if len(pending) > self.store.profile.max_result_bytes + 65536:
                            error, pending = "RESOURCE_EXCEEDED", b""
                            continue
                        while b"\n" in pending:
                            line, pending = pending.split(b"\n", 1)
                            frames += 1
                            if frames > 8:
                                error = "RESOURCE_EXCEEDED"
                                continue
                            try:
                                frame = json.loads(line)
                                if not isinstance(frame, dict):
                                    raise ValueError("invalid worker frame")
                                if any(frame.get(field) != value for field, value in binding.items()):
                                    raise ValueError("foreign worker frame")
                                if frame["type"] == "ready" and not ready:
                                    if frame["profile_hash"] != self.store.profile.digest:
                                        raise ValueError("profile drift")
                                    ready = True
                                    metrics["settings"] = frame["settings"]
                                    version, revision = frame["engine_version"], frame["engine_revision"]
                                    if (not isinstance(version, str) or re.fullmatch(r"[0-9a-z.]{1,32}", version) is None
                                            or not isinstance(revision, str) or re.fullmatch(r"[a-f0-9]{7,40}", revision) is None):
                                        raise ValueError("invalid engine identity")
                                    metrics["engine"] = {"version": version, "source_revision": revision}
                                    self._hook("worker:ready", {**binding, "pid": child.pid})
                                elif frame["type"] == "result" and ready and result is None and not error:
                                    if frame["profile_hash"] != self.store.profile.digest:
                                        raise ValueError("profile drift")
                                    result = AnalyticsB0Result.model_validate(frame["result"])
                                    self._hook("worker:result", {**binding, "pid": child.pid})
                                elif frame["type"] == "error" and frame["code"] in {"TOOL_FAILED", "RESOURCE_EXCEEDED"}:
                                    error = frame["code"]
                                elif frame["type"] == "closed" and not closed:
                                    peak = frame["rss_peak_bytes"]
                                    if type(peak) is not int or not 0 <= peak <= 2**50:
                                        raise ValueError("invalid observation")
                                    metrics["rss_peak_bytes"] = max(metrics["rss_peak_bytes"], peak)
                                    closed = True
                                else:
                                    raise ValueError("invalid worker frame order")
                            except (KeyError, TypeError, ValueError):
                                error = error or "TOOL_FAILED"
            child.wait(timeout=3)
            metrics["temp_peak_bytes"] = max(metrics["temp_peak_bytes"], temp_bytes(temporary))
            metrics["elapsed_ms"] = round((time.monotonic() - started) * 1000)
            record = self.store.worker_records(execution_id=execution_id)[0]
            error = error or self._stop_reason(record)
            if metrics["rss_peak_bytes"] > self.store.profile.worker_rss_observation_mib * MIB:
                error = "RESOURCE_EXCEEDED"
            if not ready or not closed or result is None or child.returncode != 0:
                error = error or "TOOL_FAILED"
            self._hook("worker:exited", {**binding, "pid": child.pid, "exit_code": child.returncode})
            self.store.worker_exited(execution_id, exit_code=child.returncode, error_code=error, metrics=metrics)
            if error:
                raise AnalyticsError(409, error, "合成查询已停止或失败；原任务状态可继续查询。")
            try:
                current = self.resolve_actor(principal.actor_id)
                if current is None:
                    raise AnalyticsError(403, "PERMISSION_REVOKED", "当前任务权限已撤销。")
                self.store.complete_step(current, intent.run_id, intent.attempt_id, step.step_id, result)
            except AnalyticsError as failure:
                reason = {"QUERY_TIMEOUT": "TIMEOUT", "PERMISSION_REVOKED": "PERMISSION_REVOKED",
                          "FORBIDDEN": "PERMISSION_REVOKED"}.get(failure.code, "TOOL_FAILED")
                self.store.request_stop(intent.run_id, intent.attempt_id, reason)
                raise
            return result
        finally:
            if child is not None:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=3)
                for stream in (child.stdin, child.stdout, child.stderr):
                    stream.close()
            if fd is not None:
                os.close(fd)
            if registered:
                # Only a still-active record is changed. If commit/IPC failed,
                # persist uncertainty after proven exit; never invent success.
                try:
                    self.store.worker_exited(execution_id, exit_code=child.returncode if child else None,
                                             error_code=error or "EXECUTION_UNKNOWN", metrics=metrics)
                except (OSError, ValueError, AnalyticsError):
                    pass  # The next dispatcher recovery keeps/reconciles the reservation.
            with self._mutex:
                self._owned.discard(execution_id)
