"""本地起停脚本的进程所有权与端口配置回归测试。"""
from __future__ import annotations

import os
import shutil
import socket
import stat
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
START_SCRIPT = ROOT / "scripts" / "ops" / "start-stack.sh"
STOP_SCRIPT = ROOT / "scripts" / "ops" / "stop-stack.sh"


def _started_at(pid: int) -> str:
    return subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart="],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _write_fake_http_python(path: Path) -> None:
    path.write_text(
        """#!/bin/sh
if [ "${1:-}" = "-c" ]; then
  exit 0
fi
if [ "${1:-}" = "--version" ]; then
  echo "Python 3.14.0"
  exit 0
fi
exec /usr/bin/env python3 -c '
import http.server, sys
args = sys.argv[1:]
port = int(args[args.index("--port") + 1])
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = "{\\\"title\\\":\\\"Sample CRM 客户分析系统 API\\\"}".encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *_args):
        pass
http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
' "$@"
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_fake_vite(path: Path) -> None:
    path.write_text(
        """#!/bin/sh
if [ "${1:-}" != "${EXPECTED_VITE_ROOT:-}" ]; then
  echo "unexpected vite root: ${1:-missing}" >&2
  exit 42
fi
exec /usr/bin/env python3 -c '
import http.server, sys
args = sys.argv[1:]
port = int(args[args.index("--port") + 1])
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = "<title>伸美 AI 增长董事会</title>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *_args):
        pass
http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
' "$@" "$0"
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_stack_scripts_keep_executable_mode() -> None:
    for script in (START_SCRIPT, STOP_SCRIPT):
        assert script.stat().st_mode & stat.S_IXUSR, f"{script} must stay executable"


def test_start_script_has_owned_pid_and_configurable_port_guards() -> None:
    content = START_SCRIPT.read_text(encoding="utf-8")
    assert 'FQ_API_PORT:-8000' in content
    assert 'FQ_FRONTEND_PORT:-5173' in content
    assert 'FQ_STACK_STATE_DIR' in content
    assert 'started_at' in content
    assert 'backend.main:app' in content
    assert 'node_modules/.bin/vite' in content
    assert '"$VITE_BIN" "$CRM_ROOT/frontend-vue3"' in content
    assert '--strictPort' in content
    assert 'openapi.json' in content
    assert 'Sample CRM 客户分析系统 API' in content
    assert 'trap on_exit EXIT' in content
    assert 'pkill -f' not in content


@pytest.mark.skipif(shutil.which("lsof") is None, reason="lsof is required")
def test_start_script_serves_frontend_from_frontend_root(tmp_path: Path) -> None:
    isolated_root = tmp_path / "checkout"
    ops_dir = isolated_root / "scripts" / "ops"
    ops_dir.mkdir(parents=True)
    isolated_start = ops_dir / "start-stack.sh"
    isolated_stop = ops_dir / "stop-stack.sh"
    shutil.copy2(START_SCRIPT, isolated_start)
    shutil.copy2(STOP_SCRIPT, isolated_stop)

    fake_python = tmp_path / "fake-python"
    _write_fake_http_python(fake_python)
    fake_vite = isolated_root / "frontend-vue3" / "node_modules" / ".bin" / "vite"
    fake_vite.parent.mkdir(parents=True)
    _write_fake_vite(fake_vite)

    state_dir = tmp_path / "state"
    api_port = _free_port()
    frontend_port = _free_port()
    while frontend_port == api_port:
        frontend_port = _free_port()
    env = os.environ.copy()
    env.update(
        {
            "FQ_PYTHON_BIN": str(fake_python),
            "FQ_STACK_STATE_DIR": str(state_dir),
            "FQ_API_PORT": str(api_port),
            "FQ_FRONTEND_PORT": str(frontend_port),
            "EXPECTED_VITE_ROOT": str(isolated_root / "frontend-vue3"),
        }
    )

    try:
        result = subprocess.run(
            ["bash", str(isolated_start)],
            cwd=isolated_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "stack ready" in result.stdout
        with urllib.request.urlopen(
            f"http://127.0.0.1:{frontend_port}/", timeout=5
        ) as response:
            body = response.read().decode("utf-8")
        assert response.status == 200
        assert "<title>伸美 AI 增长董事会</title>" in body
    finally:
        stop = subprocess.run(
            ["bash", str(isolated_stop)],
            cwd=isolated_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    assert stop.returncode == 0, stop.stderr
    assert not (state_dir / "api.pid").exists()
    assert not (state_dir / "frontend.pid").exists()


def test_stop_script_refuses_unowned_pid(tmp_path: Path) -> None:
    state_dir = tmp_path / "stack-state"
    state_dir.mkdir()
    sleeper = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        cwd=tmp_path,
    )
    try:
        (state_dir / "api.pid").write_text(f"{sleeper.pid}\n", encoding="utf-8")
        (state_dir / "api.port").write_text("65431\n", encoding="utf-8")
        (state_dir / "api.started_at").write_text(
            f"{_started_at(sleeper.pid)}\n", encoding="utf-8"
        )
        env = os.environ.copy()
        env.update(
            {
                "FQ_STACK_STATE_DIR": str(state_dir),
                "FQ_FRONTEND_PORT": "65432",
            }
        )
        result = subprocess.run(
            ["bash", str(STOP_SCRIPT)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode != 0
        assert f"refusing to stop unowned api PID {sleeper.pid}" in result.stderr
        assert sleeper.poll() is None, "stop-stack must not kill an unowned process"
    finally:
        sleeper.terminate()
        sleeper.wait(timeout=5)


def test_stop_script_refuses_spoofed_command_without_listening_port(
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / "stack-state"
    state_dir.mkdir()
    spoofed_marker = str(ROOT / "backend.main:app")
    sleeper = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)", spoofed_marker],
        cwd=ROOT,
    )
    try:
        (state_dir / "api.pid").write_text(f"{sleeper.pid}\n", encoding="utf-8")
        api_port = _free_port()
        frontend_port = _free_port()
        (state_dir / "api.port").write_text(f"{api_port}\n", encoding="utf-8")
        (state_dir / "api.started_at").write_text(
            f"{_started_at(sleeper.pid)}\n", encoding="utf-8"
        )
        env = os.environ.copy()
        env.update(
            {
                "FQ_STACK_STATE_DIR": str(state_dir),
                "FQ_FRONTEND_PORT": str(frontend_port),
            }
        )
        result = subprocess.run(
            ["bash", str(STOP_SCRIPT)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode != 0
        assert f"does not exclusively own port {api_port}" in result.stderr
        assert sleeper.poll() is None, "a spoofed command must not be killed"
    finally:
        sleeper.terminate()
        sleeper.wait(timeout=5)


def test_stop_script_rejects_invalid_ports(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.update(
        {
            "FQ_STACK_STATE_DIR": str(tmp_path / "missing-state"),
            "FQ_API_PORT": "not-a-port",
            "FQ_FRONTEND_PORT": "also-not-a-port",
        }
    )
    result = subprocess.run(
        ["bash", str(STOP_SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0
    assert "invalid API port" in result.stderr


def test_stop_script_stops_matching_process_and_port(tmp_path: Path) -> None:
    state_dir = tmp_path / "stack-state"
    state_dir.mkdir()
    marker = str(ROOT / "backend.main:app")
    listener = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import socket,sys,time; "
                "s=socket.socket(); s.bind(('127.0.0.1', 0)); s.listen(); "
                "print(s.getsockname()[1], flush=True); time.sleep(60)"
            ),
            marker,
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert listener.stdout is not None
        api_port = int(listener.stdout.readline().strip())
        frontend_port = _free_port()
        (state_dir / "api.pid").write_text(f"{listener.pid}\n", encoding="utf-8")
        (state_dir / "api.port").write_text(f"{api_port}\n", encoding="utf-8")
        (state_dir / "api.started_at").write_text(
            f"{_started_at(listener.pid)}\n", encoding="utf-8"
        )
        env = os.environ.copy()
        env.update(
            {
                "FQ_STACK_STATE_DIR": str(state_dir),
                "FQ_FRONTEND_PORT": str(frontend_port),
            }
        )
        result = subprocess.run(
            ["bash", str(STOP_SCRIPT)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        listener.wait(timeout=5)
        assert not (state_dir / "api.pid").exists()
        assert not (state_dir / "api.started_at").exists()
    finally:
        if listener.poll() is None:
            listener.terminate()
            listener.wait(timeout=5)


@pytest.mark.skipif(shutil.which("lsof") is None, reason="lsof is required")
def test_start_script_cleans_api_when_frontend_preflight_fails(
    tmp_path: Path,
) -> None:
    isolated_root = tmp_path / "checkout"
    ops_dir = isolated_root / "scripts" / "ops"
    ops_dir.mkdir(parents=True)
    isolated_start = ops_dir / "start-stack.sh"
    shutil.copy2(START_SCRIPT, isolated_start)

    fake_python = tmp_path / "fake-python"
    fake_python.write_text(
        """#!/bin/sh
if [ "${1:-}" = "-c" ]; then
  exit 0
fi
if [ "${1:-}" = "--version" ]; then
  echo "Python 3.14.0"
  exit 0
fi
exec /usr/bin/env python3 -c '
import socket, sys, time
args = sys.argv[1:]
port = int(args[args.index("--port") + 1])
listener = socket.socket()
listener.bind(("127.0.0.1", port))
listener.listen()
time.sleep(60)
' "$@"
""",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    state_dir = tmp_path / "state"
    api_port = _free_port()
    frontend_port = _free_port()
    env = os.environ.copy()
    env.update(
        {
            "FQ_PYTHON_BIN": str(fake_python),
            "FQ_STACK_STATE_DIR": str(state_dir),
            "FQ_API_PORT": str(api_port),
            "FQ_FRONTEND_PORT": str(frontend_port),
        }
    )
    result = subprocess.run(
        ["bash", str(isolated_start)],
        cwd=isolated_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode != 0
    assert "frontend dependencies are missing" in result.stderr
    assert not (state_dir / "api.pid").exists()
    assert not (state_dir / "api.started_at").exists()
    port_check = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{api_port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert port_check.returncode == 1
    assert port_check.stdout == ""
