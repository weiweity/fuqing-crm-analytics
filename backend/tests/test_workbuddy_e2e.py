"""test_workbuddy_e2e — Sprint 188 WorkBuddy 真端到端 MCP server 测试.

取代 Sprint 182 的 mock backend test (test_fuqing_adhoc_mcp_server.py 把
subprocess.run mock 掉纯验证参数形状), 真正启 server.py stdio 子进程发
JSON-RPC 验证 WorkBuddy LLM 视角的端到端行为.

L4.41 (Sprint 187) 配套: env[PYTHONPATH]=str(PROJECT_ROOT) 强制绝对路径, 不
依赖父进程, CI runner PYTHONPATH=. 也能跑.
L4.32 (Sprint 181) 配套: cwd=PROJECT_ROOT 防 chdir 污染源.
L4.34 (Sprint 181.1) 配套: Path(__file__).resolve() 跨平台, 不硬编码 /Users/.

Sprint 188 立项 Phase 1 B2: 用 Python 原生 subprocess + 手写 JSON-RPC
framing (跟 server.py _read_message 反向对接), 模拟 Codex CLI / WorkBuddy
MCP client 行为.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# L4.34 + L4.32: 跨平台绝对路径, 强制 lock subprocess cwd
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = REPO_ROOT
SERVER_SCRIPT = PROJECT_ROOT / "mcp_servers" / "fuqing_adhoc" / "server.py"
E2E_SCRIPT = PROJECT_ROOT / "scripts" / "e2e_workbuddy_test.py"

# 11 tools: 跟 _dispatch.py TOOL_DEFS SSOT (Sprint 182 + Sprint 183)
EXPECTED_TOOL_COUNT = 11
EXPECTED_TOOL_NAMES = {
    "daily_gsv", "yoy_battle", "channel_slice", "two_year_overview",
    "new_old_customer", "rfm_repurchase", "top_n", "export_excel",
    "dq_report", "daily-gsv-multi-period", "ask",
}


# ─────────────────────────────────────────────────────────────
# Mini LSP-style JSON-RPC helpers (mirror server.py _write_message / _read_message)
# ─────────────────────────────────────────────────────────────

def _frame(payload: dict) -> bytes:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8") + body


def _read_one(buf: bytearray, proc: subprocess.Popen) -> dict | None:
    """从 proc.stdout 读 1 条 LSP-style 消息. EOF 返 None."""
    while b"\r\n\r\n" not in buf:
        ch = proc.stdout.read(1)
        if not ch:
            return None
        buf.extend(ch)
    head, _, rest = buf.partition(b"\r\n\r\n")
    content_length = 0
    for line in head.split(b"\r\n"):
        k, _, v = line.partition(b":")
        if k.strip().lower() == b"content-length":
            try:
                content_length = int(v.strip())
            except ValueError:
                content_length = 0
            break
    if content_length <= 0:
        return None
    while len(rest) < content_length:
        chunk = proc.stdout.read(content_length - len(rest))
        if not chunk:
            return None
        rest.extend(chunk)
    body = bytes(rest[:content_length])
    buf.clear()
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return None


@pytest.fixture
def server_proc():
    """启 server.py stdio subprocess, yield Popen, teardown 时 kill."""
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
    proc = subprocess.Popen(
        [sys.executable, str(SERVER_SCRIPT)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(PROJECT_ROOT),
        env=env,
        bufsize=0,
    )
    try:
        yield proc
    finally:
        if proc.poll() is None:
            proc.stdin.close() if proc.stdin and not proc.stdin.closed else None
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def _send(proc: subprocess.Popen, payload: dict) -> None:
    assert proc.stdin and not proc.stdin.closed, "stdin 已关闭, 无法再发"
    proc.stdin.write(_frame(payload))
    proc.stdin.flush()


# ─────────────────────────────────────────────────────────────
# Class 1: TestStdJsonRpcFraming (WorkBuddy 协议层 smoke test)
# ─────────────────────────────────────────────────────────────

class TestStdJsonRpcFraming:
    """验证 server.py stdio JSON-RPC framing 跟 WorkBuddy / Codex MCP client
    期望一致. 真发 initialize / tools/list, 不 mock.

    L4.41: PYTHONPATH=str(PROJECT_ROOT) 强制绝对路径, Linux CI runner 也能跑
    (Sprint 187 真因).
    """

    def test_initialize_returns_server_info(self, server_proc):
        """initialize MUST return protocolVersion + serverInfo (MCP spec)."""
        _send(server_proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest_workbuddy_e2e", "version": "0.1.0"},
            },
        })
        buf = bytearray()
        resp = _read_one(buf, server_proc)
        assert resp is not None, "initialize 未响应 (stdio 通讯失败)"
        assert resp.get("id") == 1
        result = resp.get("result", {})
        assert result.get("protocolVersion") == "2024-11-05", (
            f"期望 protocolVersion=2024-11-05, got {result.get('protocolVersion')!r}"
        )
        server_info = result.get("serverInfo", {})
        assert server_info.get("name") == "fuqing_adhoc", (
            f"期望 serverInfo.name=fuqing_adhoc, got {server_info.get('name')!r}"
        )

    def test_tools_list_returns_11_tools(self, server_proc):
        """tools/list MUST return 11 tools (10 query + 1 ask, Sprint 183 加 daily-gsv-multi-period)."""
        _send(server_proc, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
        })
        buf = bytearray()
        resp = _read_one(buf, server_proc)
        assert resp is not None, "tools/list 未响应"
        assert resp.get("id") == 2
        tools = resp.get("result", {}).get("tools", [])
        assert isinstance(tools, list)
        assert len(tools) == EXPECTED_TOOL_COUNT, (
            f"期望 {EXPECTED_TOOL_COUNT} tools, got {len(tools)}: "
            f"{[t.get('name') for t in tools]}"
        )
        names = {t.get("name") for t in tools}
        missing = EXPECTED_TOOL_NAMES - names
        assert not missing, f"missing tools: {missing}"

    def test_tool_schemas_have_input_schema(self, server_proc):
        """Each tool MUST have a valid JSON Schema (type=object)."""
        _send(server_proc, {
            "jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {},
        })
        buf = bytearray()
        resp = _read_one(buf, server_proc)
        assert resp is not None
        for t in resp.get("result", {}).get("tools", []):
            schema = t.get("inputSchema", {})
            assert schema.get("type") == "object", (
                f"tool {t.get('name')!r} inputSchema.type 必须是 object"
            )
            assert isinstance(schema.get("properties"), dict), (
                f"tool {t.get('name')!r} inputSchema.properties 必须是 dict"
            )

    def test_call_unknown_tool_returns_isError(self, server_proc):
        """tools/call name=__nonexistent__ MUST return isError=true (no crash)."""
        _send(server_proc, {
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "__nonexistent_tool_xyz__", "arguments": {}},
        })
        buf = bytearray()
        resp = _read_one(buf, server_proc)
        assert resp is not None
        result = resp.get("result", {})
        assert result.get("isError") is True, (
            f"未知 tool 期望 isError=true, got {result.get('isError')!r}"
        )
        content = result.get("content", [])
        text = ""
        if content and isinstance(content[0], dict):
            text = content[0].get("text", "")
        assert "unknown tool" in text, (
            f"期望 'unknown tool' 提示, got text={text[:200]!r}"
        )


# ─────────────────────────────────────────────────────────────
# Class 2: TestDailyGsvMultiPeriodE2E (Sprint 183 第 11 个 tool 真端到端)
# ─────────────────────────────────────────────────────────────

class TestDailyGsvMultiPeriodE2E:
    """验证 Sprint 183 daily-gsv-multi-period 第 11 个 tool 走完整个
    server.py → _dispatch.py → scripts/ad_hoc_queries/daily_gsv_multi_period.py
    → DuckDB read_only conn 路径.

    注意: DuckDB 锁可能冲突 (Sprint 53 race flake), 接受 graceful error.
    重点是协议层 path 走通, 不是数据正确性 (data correctness 由
    backend/tests/test_daily_gsv_multi_period.py 验证).
    """

    def test_call_daily_gsv_multi_period_dispatches(self, server_proc):
        """daily-gsv-multi-period MUST dispatch through MCP, returning
        isError=true (DuckDB lock) OR isError=false (data). Both are valid."""
        _send(server_proc, {
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {
                "name": "daily-gsv-multi-period",
                "arguments": {"periods": ["2026-06-21", "2026-06-21"]},
            },
        })
        buf = bytearray()
        resp = _read_one(buf, server_proc)
        assert resp is not None, "daily-gsv-multi-period call 未响应"
        assert resp.get("id") == 5
        result = resp.get("result", {})
        assert "content" in result, "期望 result.content 存在"
        content = result.get("content", [])
        assert isinstance(content, list) and len(content) >= 1
        text = content[0].get("text", "")
        is_error = result.get("isError", True)
        if is_error:
            # Lock conflict 或 DuckDB 不可用, 期望 stderr 含可读错误
            assert text, "isError=true 但 content[0].text 为空"
        else:
            # 数据路径: 期望 stdout 含 sample_gsv / member_gsv 列
            # (Sprint 183 multi-period 输出列是 metric_name 直接)
            assert any(
                col in text for col in ("sample_gsv", "member_gsv", "new_gsv")
            ), (
                f"daily-gsv-multi-period 期望含 sample_gsv/member_gsv 列, "
                f"got text 前 300: {text[:300]!r}"
            )


# ─────────────────────────────────────────────────────────────
# Class 3: TestE2EScriptIntegration (验证 scripts/e2e_workbuddy_test.py 也能跑)
# ─────────────────────────────────────────────────────────────

class TestE2EScriptIntegration:
    """验证手工 e2e 脚本 (scripts/e2e_workbuddy_test.py) 集成: 当作 CI
    smoke test 跑一遍, 期望 exit 0 + 含 PASS 关键字."""

    @pytest.mark.skipif(
        not shutil.which("python3"),
        reason="python3 不可用, 跳过 subprocess e2e",
    )
    def test_e2e_script_exits_zero_with_pass(self):
        """scripts/e2e_workbuddy_test.py MUST exit 0 + 打印 PASS 关键字."""
        if not E2E_SCRIPT.exists():
            pytest.skip("scripts/e2e_workbuddy_test.py 还没创建 (Sprint 188 未实施)")
        result = subprocess.run(
            [sys.executable, str(E2E_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"e2e 脚本期望 exit 0, got {result.returncode}; "
            f"stdout 前 500: {result.stdout[:500]!r}; "
            f"stderr: {result.stderr[:300]!r}"
        )
        assert "PASS" in result.stdout, (
            f"期望 stdout 含 PASS 关键字, got 前 500: {result.stdout[:500]!r}"
        )

    @pytest.mark.skipif(
        not shutil.which("codex"),
        reason="Codex CLI 未装, 跳过 (实际 WorkBuddy 调用 Codex)",
    )
    def test_codex_cli_present_acknowledged(self):
        """如果 Codex CLI 已装, which codex 应能定位. 这是 soft check
        (e2e_workbuddy_test.py 直接发 JSON-RPC, 不需要 Codex CLI),
        留给未来 Sprint 188+ 用 Codex CLI 真跑 MCP integration test."""
        path = shutil.which("codex")
        assert path, "shutil.which('codex') 应返路径"
        assert "codex" in path.lower()
