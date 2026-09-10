"""Test-only kernel: real runtime_app with an owned probe launcher.

Never a production module. No HTTP fault switch, CRM import, or real DB.
Private proof/release files belong to this synthetic runtime directory only.
"""

from __future__ import annotations

from backend.services.analytics.runtime_ports import runtime_port_base

import json
import os
import re
import secrets
import stat
import sys
import threading
import time
from contextlib import AbstractContextManager
from pathlib import Path

from backend.analytics_runtime import runtime_app
from backend.tests.analytics_worker_probe import ProbeLauncher

ALLOWED_MODES = ("sql_hold", "unknown_schema", "illegal_facts", "passthrough")
EXECUTION_ID = re.compile(r"^exec_[0-9a-f]{32}$")
DEFAULT_SEQUENCE = ("sql_hold", "unknown_schema", "illegal_facts", "passthrough")


def prepare_probe_dir(path, sequence=DEFAULT_SEQUENCE):
    path = Path(path)
    path.mkdir(mode=0o700)
    (path / "release").mkdir(mode=0o700)
    encoded = json.dumps(list(sequence), separators=(",", ":")) + "\n"
    target = path / "sequence.json"
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(fd, encoded.encode())
    finally:
        os.close(fd)
    return path.resolve()


def probe_dir_for_state(state_dir):
    return Path(state_dir).resolve().parent / "probe"


def _owned_stat(path, *, directory, expected_mode=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | (os.O_DIRECTORY if directory else 0))
    try:
        info = os.fstat(fd)
        if info.st_uid != os.getuid():
            raise ValueError("unowned probe path")
        if directory:
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError("probe path is not a directory")
            if expected_mode is not None and (info.st_mode & 0o777) != expected_mode:
                raise ValueError("probe directory mode rejected")
        else:
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("probe path is not a regular file")
        return fd, info
    except Exception:
        os.close(fd)
        raise


def require_probe_dir(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("probe directory may not be a symlink")
    fd, _info = _owned_stat(path, directory=True, expected_mode=0o700)
    os.close(fd)
    resolved = path.resolve(strict=True)
    release = resolved / "release"
    if release.is_symlink():
        raise ValueError("probe release directory may not be a symlink")
    fd, _info = _owned_stat(release, directory=True, expected_mode=0o700)
    os.close(fd)
    sequence_path = resolved / "sequence.json"
    fd, _info = _owned_stat(sequence_path, directory=False)
    try:
        raw = os.read(fd, 4096)
    finally:
        os.close(fd)
    sequence = json.loads(raw)
    if (not isinstance(sequence, list) or not 1 <= len(sequence) <= 8
            or any(item not in ALLOWED_MODES for item in sequence)):
        raise ValueError("invalid probe sequence")
    return resolved, tuple(sequence)


def _append_jsonl(path, payload):
    line = json.dumps(payload, ensure_ascii=False, allow_nan=False) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("invalid proof log")
        os.write(fd, line.encode())
    finally:
        os.close(fd)


def _replace_json(path, payload):
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("invalid current hold file")
        os.write(fd, encoded.encode())
    finally:
        os.close(fd)


def _unlink_if_owned(path):
    try:
        fd, _info = _owned_stat(path, directory=False)
    except (FileNotFoundError, ValueError, OSError):
        return
    try:
        os.close(fd)
        os.unlink(path)
    except FileNotFoundError:
        pass


class NativeProbeCoordinator(AbstractContextManager):
    """Sequential owned launcher. Proof/release are files under this runtime."""

    def __init__(self, probe_dir):
        self.dir, self.sequence = require_probe_dir(probe_dir)
        self.index = 0
        self._lock = threading.Lock()
        self._owned = []
        self._closed = False
        self._hold_generation = 0
        self.current_path = self.dir / "current.json"
        self.proof_path = self.dir / "proof.jsonl"

    def __call__(self, config, lease_fd):
        binding = config["binding"]
        with self._lock:
            if self._closed:
                raise RuntimeError("probe coordinator is closed")
            mode = self.sequence[self.index] if self.index < len(self.sequence) else "passthrough"
            self.index += 1
            launcher = ProbeLauncher(mode)
            self._owned.append(launcher)
        try:
            child = launcher(config, lease_fd)
        except BaseException:
            self._discard(launcher)
            raise
        if mode == "sql_hold":
            generation = self._begin_hold(binding)
            threading.Thread(target=self._watch_hold, args=(launcher, binding, generation),
                             daemon=True, name="b0-native-probe-hold").start()
        return child

    def _begin_hold(self, binding):
        with self._lock:
            self._hold_generation += 1
            generation = self._hold_generation
        if not EXECUTION_ID.fullmatch(binding["execution_id"]):
            raise ValueError("invalid execution binding")
        _unlink_if_owned(self.dir / "release" / binding["execution_id"])
        _unlink_if_owned(self.current_path)
        return generation

    def _watch_hold(self, launcher, binding, generation):
        try:
            proof = launcher.receive(timeout=15)
        except Exception as error:
            _append_jsonl(self.proof_path, {"event": "PROBE_WAIT_FAILED", "error_type": type(error).__name__,
                                            **binding})
            return
        public = {"event": proof.get("event"), "pid": proof.get("pid"), **binding}
        _append_jsonl(self.proof_path, public)
        if proof.get("event") != "SQL_ACTIVE":
            return
        nonce = secrets.token_urlsafe(32)
        _replace_json(self.current_path, {**public, "release_nonce": nonce, "generation": generation})
        if not self._wait_release(binding["execution_id"], nonce, generation):
            return
        launcher.release()
        with self._lock:
            if not self._closed and self._hold_generation == generation:
                _unlink_if_owned(self.current_path)
                _unlink_if_owned(self.dir / "release" / binding["execution_id"])

    def _wait_release(self, execution_id, nonce, generation):
        path = self.dir / "release" / execution_id
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            with self._lock:
                if self._closed or self._hold_generation != generation:
                    return False
            try:
                fd, _info = _owned_stat(path, directory=False)
            except (FileNotFoundError, ValueError, OSError):
                time.sleep(0.05)
                continue
            try:
                payload = os.read(fd, 128)
            finally:
                os.close(fd)
            if payload == nonce.encode():
                return True
            time.sleep(0.05)
        return False

    def _discard(self, launcher):
        with self._lock:
            if launcher in self._owned:
                self._owned.remove(launcher)
        try:
            launcher.__exit__(None, None, None)
        except OSError:
            pass

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._hold_generation += 1
            owned = list(self._owned)
            self._owned.clear()
        _unlink_if_owned(self.current_path)
        for launcher in owned:
            try:
                # WorkerManager owns the returned Popen protocol streams. It
                # must drain EOF and close them after its selector exits.
                launcher.close(close_worker_streams=False)
            except OSError:
                pass

    def __exit__(self, *_exc):
        self.close()


def native_probe_app(config, *, bridge=None):
    """Real runtime_app plus this instance's probe launcher. No extra HTTP routes."""
    probe_dir, _sequence = require_probe_dir(probe_dir_for_state(config["state_dir"]))
    coordinator = NativeProbeCoordinator(probe_dir)
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
    uvicorn.run(native_probe_app(setup), host="127.0.0.1", port=runtime_port_base(setup), access_log=False, log_level="warning",
                loop="asyncio", http="h11", ws="none")
