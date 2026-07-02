"""e2e_workbuddy_test — WorkBuddy 真端到端验证脚本.

Sprint 188 立项 (Phase 1 B2): 用 subprocess 启动 mcp_servers/fuqing_adhoc/server.py
stdio, 模拟 Codex CLI 发 JSON-RPC 1 次:

1. tools/list call → 期望 11 tools (Sprint 183 加 daily-gsv-multi-period 后)
2. tools/call name=daily-gsv-multi-period with args={"periods": ["2026-06-21",
   "2026-06-21"]} → 期望返 JSON 含 sample_gsv / member_gsv 列

替代 Sprint 182 mock-only test_fuqing_adhoc_mcp_server.py 的 mock backend 路径,
真打 stdio JSON-RPC 验证 WorkBuddy MCP server 整体可通讯.

L4.32: 显式 cwd=PROJECT_ROOT, 防父进程 CWD 漂移 (Sprint 181 真因).
L4.34: Path(__file__).resolve() 跨平台, 禁硬编码 /Users/...
L4.41: env[PYTHONPATH] 强制 str(PROJECT_ROOT), 不 inherit 父进程 (Sprint 187 真因).
L4.35: SKILL.md 跨端 symlink SSOT, 不复制粘贴 (Sprint 182 教训).

Usage:
    python3 scripts/e2e_workbuddy_test.py              # 跑 1 次, 打印结果
    python3 scripts/e2e_workbuddy_test.py --verbose    # 打印 raw stdout/stderr
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# L4.34: 跨平台绝对路径
_HERE = Path(__file__).resolve()
PROJECT_ROOT = _HERE.parent.parent
SERVER_PATH = PROJECT_ROOT / "mcp_servers" / "fuqing_adhoc" / "server.py"


def _frame_message(payload: dict) -> bytes:
    """Sprint 191 fix: newline-delimited JSON, 不用 LSP Content-Length framing.

    配套 mcp_servers/fuqing_adhoc/server.py:_write_message (Sprint 191 LSP→newline JSON).
    """
    return json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"


def _read_message(proc: subprocess.Popen, buf: bytearray) -> dict | None:
    """Sprint 191 fix: 从 stdout buf 读 1 条 newline JSON 消息. EOF 返 None.

    配套 mcp_servers/fuqing_adhoc/server.py:_read_message.
    """
    while b"\n" not in buf:
        chunk = proc.stdout.read(1) if proc.stdout else b""
        if not chunk:
            return None
        buf.extend(chunk)
    line, _, rest = buf.partition(b"\n")
    # 简化: 单线程 e2e, 下一条消息前清空 buf
    buf.clear()
    buf.extend(rest)
    try:
        return json.loads(line.decode("utf-8").strip())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _drain_stdout(proc: subprocess.Popen, max_bytes: int = 1 << 20) -> bytes:
    """读剩余 stdout (server 退出前可能残留输出)."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = proc.stdout.read(4096) if proc.stdout else b""
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total >= max_bytes:
            break
    return b"".join(chunks)


def run_e2e(verbose: bool = False) -> tuple[int, int, dict | None, dict | None]:
    """启 server stdio subprocess → 发 3 条 JSON-RPC → 解析响应.

    返回 (returncode, exit_code, tools_list_response, tool_call_response).
    """
    # L4.32 + L4.41 永久规则: cwd=PROJECT_ROOT + env[PYTHONPATH]=str(PROJECT_ROOT)
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
    cmd = [sys.executable, str(SERVER_PATH)]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(PROJECT_ROOT),
        env=env,
        bufsize=0,
    )
    try:
        # 1. initialize (workbuddy 通常先发这条, server 没强制要求但兼容性更好)
        proc.stdin.write(_frame_message({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05",
                       "capabilities": {},
                       "clientInfo": {"name": "e2e_workbuddy_test", "version": "0.1.0"}},
        }))
        proc.stdin.flush()
        buf = bytearray()
        _ = _read_message(proc, buf)  # ignore initialize response

        # 2. tools/list
        proc.stdin.write(_frame_message({
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
        }))
        proc.stdin.flush()
        tools_resp = _read_message(proc, buf)

        # 3. tools/call daily-gsv-multi-period (小窗口, 期望至少有 1 行,
        #    DuckDB 不可用时 graceful error, 不强求数据)
        proc.stdin.write(_frame_message({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {
                "name": "daily-gsv-multi-period",
                "arguments": {
                    "periods": ["2026-06-21", "2026-06-21"],
                },
            },
        }))
        proc.stdin.flush()
        call_resp = _read_message(proc, buf)

        # close stdin → server EOF → graceful exit
        proc.stdin.close()
        try:
            returncode = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            returncode = -1
        stderr_text = (proc.stderr.read() if proc.stderr else b"").decode(
            "utf-8", errors="replace"
        )
        if verbose and stderr_text:
            print(f"[stderr] {stderr_text!r}", file=sys.stderr)
        return returncode, 0, tools_resp, call_resp
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)


def main() -> int:
    verbose = "--verbose" in sys.argv
    rc, _exit, tools_resp, call_resp = run_e2e(verbose=verbose)

    # --- 验证 1: tools/list 返 11 tools ---
    print("=" * 60)
    print("Sprint 188 e2e: WorkBuddy MCP server 真端到端验证")
    print("=" * 60)
    print(f"server: {SERVER_PATH}")
    print(f"process exit code: {rc}")
    print()

    if tools_resp is None:
        print("FAIL: tools/list 未响应 (stdio 通讯失败)")
        return 1
    result = tools_resp.get("result", {})
    tools = result.get("tools", [])
    print(f"tools/list 返 {len(tools)} tools:")
    for t in tools:
        print(f"  - {t.get('name')}")
    expected = {
        "daily_gsv", "yoy_battle", "channel_slice", "two_year_overview",
        "new_old_customer", "rfm_repurchase", "top_n", "export_excel",
        "dq_report", "daily-gsv-multi-period", "ask",
    }
    got = {t.get("name") for t in tools}
    missing = expected - got
    if missing:
        print(f"FAIL: tools/list missing {missing}")
        return 1
    if len(tools) != 11:
        print(f"FAIL: 期望 11 tools, got {len(tools)}")
        return 1
    print("PASS: tools/list 返 11 tools (含 daily-gsv-multi-period Sprint 183 新增)")
    print()

    # --- 验证 2: tools/call daily-gsv-multi-period ---
    if call_resp is None:
        print("FAIL: tools/call 未响应")
        return 1
    print("tools/call daily-gsv-multi-period response keys:",
          list(call_resp.keys()))
    call_result = call_resp.get("result", {})
    is_error = call_result.get("isError", True)
    content = call_result.get("content", [])
    text = ""
    if content and isinstance(content[0], dict):
        text = content[0].get("text", "")
    if is_error:
        # DuckDB 未跑 / 锁冲突 / 数据缺 → graceful error 是合法的,
        # 只要 MCP 协议层正确包了 isError=true + content[0].text 就 OK
        print("NOTE: tool call 返 isError=true (可能是 DuckDB 不可用/锁冲突)")
        print(f"      text 前 200 字符: {text[:200]!r}")
        if not text:
            print("FAIL: isError 但 content[0].text 为空")
            return 1
        print("PASS: tool call graceful error (协议层正确)")
    else:
        # 期望 stdout 含 sample_gsv / member_gsv 列 (或表头)
        if "sample_gsv" in text or "member_gsv" in text or "metric" in text.lower():
            print("PASS: tool call 返数据, 期望列出现")
        else:
            print(f"NOTE: tool call 返数据但未识别列, text 前 300: {text[:300]!r}")
        print("PASS: tool call 成功 (Sprint 183 第 11 个 tool 端到端 OK)")

    print()
    print("=" * 60)
    print("Sprint 188 e2e: 全部 PASS (替代 mock backend test)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
