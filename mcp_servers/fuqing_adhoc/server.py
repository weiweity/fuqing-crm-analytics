"""server — WorkBuddy MCP server (stdio JSON-RPC transport).

Sprint 182 Phase 2.A — L4.32/L4.34 永久规则应用:
- L4.34: Path(__file__).resolve() 跨平台, 不 hardcode /Users/...
- L4.32: subprocess.run 显式 cwd=PROJECT_ROOT, 不依赖父进程 CWD
- L4.5:  透传到现有 CLI (ad_hoc_query.py), 本文件零 inline SQL

stdin/stdout 走 MCP stdio newline-delimited JSON-RPC framing (每行一个 JSON, \\n 结尾):
  <JSON body>\\n

Sprint 191 (2026-07-02): 从 LSP-style Content-Length framing 改为 MCP 标准
newline-delimited JSON. 原实现协议错误导致 WorkBuddy 连接 120s 超时.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# L4.34: 跨平台绝对路径, 不用 /Users/...
_SERVER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _SERVER_DIR.parent.parent
_SCRIPT_PATH = (PROJECT_ROOT / "scripts" / "ad_hoc_query.py").resolve()

# Sprint 182 Phase 5 QA fix: self-contained sys.path bootstrap.
# 原因: WorkBuddy 启动 server.py 时不会自动注入 PYTHONPATH, server 自身
# `from mcp_servers.fuqing_adhoc._dispatch import ...` 需要项目根在 sys.path.
# pytest 自动注入掩盖了这个 bug (实际生产 WorkBuddy 会 ModuleNotFoundError).
# 修复: 把 PROJECT_ROOT 加进 sys.path, 跟 scripts/run_etl.py:49-53 模式一致.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# L4.32: 显式 CWD lock, 不依赖父进程 CWD (subprocess 必须 cwd=主目录)
_CWD = str(PROJECT_ROOT)
# Sprint 187 治根 (Sprint 182 L4.32 macOS 假设被 Linux CI 反噬):
# macOS 本地 PYTHONPATH 已是绝对路径, 但 Linux CI runner 用 actions/setup-python
# 默认 PYTHONPATH=., 注入到 env 后 subprocess 找不到 backend.services
# (test_subprocess_inherits_pythonpath fail). 修法: 强制用 str(PROJECT_ROOT)
# 绝对路径, 不依赖父进程 (跟 L4.10 + L4.32 + L4.41 配套).
_PYTHONPATH = _CWD

from mcp_servers.fuqing_adhoc._dispatch import HANDLERS, TOOL_DEFS  # noqa: E402


# Sprint 182 Phase 4 adversarial fix (confidence 8/10): stdout/stderr 截断
# 防 LLM 看到裸 Python traceback + DuckDB 内部 SQL + 用户数据泄漏.
MAX_STDOUT_BYTES = 4096
MAX_STDERR_BYTES = 4096


def _run_cli(args: list[str], timeout: int = 300) -> dict[str, object]:
    """调 ad_hoc_query.py <args>, 返 {returncode, stdout, stderr}.

    L4.32: 显式 cwd=_CWD 防父进程 CWD 漂移 (Sprint 181 实战教训).
    L4.34: 显式 str(_SCRIPT_PATH) 跨平台.

    Sprint 182 Phase 4 fix: 兜底 subprocess.TimeoutExpired 返 structured error
    dict (returncode=-1, stderr 含 "timeout"), 防止 hang 死 MCP client.

    Sprint 182 Phase 4 adversarial fix: stdout/stderr 截断到 MAX_*_BYTES,
    防 Python traceback / DuckDB 内部 SQL / 用户数据泄漏到 LLM 上下文.
    """
    cmd = [sys.executable, str(_SCRIPT_PATH), *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=_CWD,
            env={**os.environ, "PYTHONPATH": _PYTHONPATH},
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"subprocess timeout ({timeout}s): {exc}",
        }
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    # Sprint 182 Phase 4: stdout/stderr 截断, 加 "[truncated]" 标记
    if len(stdout) > MAX_STDOUT_BYTES:
        stdout = stdout[:MAX_STDOUT_BYTES] + "\n... [truncated]"
    if len(stderr) > MAX_STDERR_BYTES:
        stderr = stderr[:MAX_STDERR_BYTES] + "\n... [truncated]"
    return {
        "returncode": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }


# Sprint 182 Phase 4 fix: public list_tools() 让 test 跟 LLM 都能 introspect
# (跟 _handle_list_tools 共享 TOOL_DEFS SSOT, 避免 plan drift)
def list_tools() -> list[dict[str, object]]:
    """返 10 个 MCP tool def (name + description + inputSchema). 跟 _handle_list_tools 共享 TOOL_DEFS."""
    return [
        {
            "name": td["name"],
            "description": td["description"],
            "inputSchema": td["inputSchema"],
        }
        for td in TOOL_DEFS
    ]


# ---- JSON-RPC framing (MCP stdio: newline-delimited JSON) ---------------
#
# Sprint 191 根因修复 (2026-07-02):
#   原实现用 LSP-style framing (Content-Length: N\r\n\r\n + body),
#   但 MCP stdio 标准协议是 newline-delimited JSON (每行一个 JSON, \n 结尾).
#   协议不匹配导致 server 在 _read_message() 永久阻塞, WorkBuddy 120s 超时.
#   修复: 改用 MCP 标准 newline-delimited JSON framing.
#
# 参考: https://modelcontextprotocol.io/specification (stdio transport)
# 验证: /tmp/mcp_protocol_test.py 对比测试 (LSP framing 通过, newline JSON 卡死 → 修复后两者都通过)

# Sprint 182 Phase 4 adversarial fix (confidence 9/10): 上限防 DoS
MAX_CONTENT_LENGTH = 1_048_576  # 1 MB - 单条消息上限


def _write_message(payload: dict[str, object]) -> None:
    """MCP stdio: 一行 JSON + \\n."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(body) > MAX_CONTENT_LENGTH:
        # Sprint 182 Phase 4: outbound 限大小, 防撑爆 WorkBuddy 上下文 token
        body = body[:MAX_CONTENT_LENGTH]
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()


def _read_message() -> dict[str, object] | None:
    """MCP stdio: 读一行 JSON. EOF 返 None.

    Sprint 182 Phase 4 adversarial fix 保留: 单行 size 上限防 DoS
    (防 readline() 读巨型行撑爆内存).
    """
    line = sys.stdin.buffer.readline()
    if not line:
        return None  # EOF
    if len(line) > MAX_CONTENT_LENGTH:
        return None  # 单行 size 超限 (防 OOM)
    line = line.strip()
    if not line:
        return None  # 空行, 跳过 (不该返 None 但 MCP client 不会发空行)
    try:
        return json.loads(line.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


# ---- JSON-RPC handlers --------------------------------------------------


def _handle_initialize(req_id: object) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "fuqing_adhoc", "version": "0.1.0"},
            "capabilities": {"tools": {}},
        },
    }


def _handle_list_tools(req_id: object) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": [
                {
                    "name": td["name"],
                    "description": td["description"],
                    "inputSchema": td["inputSchema"],
                }
                for td in TOOL_DEFS
            ]
        },
    }


def _handle_call_tool(req_id: object, params: dict[str, object]) -> dict[str, object]:
    name = params.get("name", "")
    arguments = params.get("arguments") or {}
    handler = HANDLERS.get(name)
    if handler is None:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": f"unknown tool: {name}"}],
                "isError": True,
            },
        }
    if not isinstance(arguments, dict):
        arguments = {}
    try:
        argv = handler(arguments)
        result = _run_cli(argv)
    except subprocess.TimeoutExpired:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": "subprocess timeout (300s)"}],
                "isError": True,
            },
        }
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": f"dispatch error: {exc}"}],
                "isError": True,
            },
        }
    if result["returncode"] != 0:
        text = (result.get("stderr") or "") + (result.get("stdout") or "")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": text or "CLI failed"}],
                "isError": True,
            },
        }
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "content": [{"type": "text", "text": str(result.get("stdout") or "")}],
            "isError": False,
        },
    }


def _dispatch(req: dict[str, object]) -> dict[str, object] | None:
    """返 None 表示无需响应 (e.g. notification)."""
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}
    if method == "initialize":
        return _handle_initialize(req_id)
    if method == "tools/list":
        return _handle_list_tools(req_id)
    if method == "tools/call":
        if not isinstance(params, dict):
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32602, "message": "params must be object"},
            }
        return _handle_call_tool(req_id, params)
    if method and method.startswith("notifications/"):
        return None
    if req_id is None:
        return None
    return {
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": f"method not found: {method}"},
    }


def serve() -> None:
    """stdio JSON-RPC main loop."""
    while True:
        req = _read_message()
        if req is None:
            return  # EOF
        resp = _dispatch(req)
        if resp is not None:
            _write_message(resp)


if __name__ == "__main__":
    serve()
