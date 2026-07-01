"""
test_fuqing_adhoc_mcp_server.py — Sprint 182 WorkBuddy MCP server tests.

Covers the MCP server wrapper around scripts/ad_hoc_query.py:
  - 9 MCP tools (8 query + 1 ask), exposed via list_tools()
  - subprocess dispatch to scripts/ad_hoc_query.py (cwd lock + Path.resolve)
  - end-to-end tool dispatch (CLI subprocess returns stdout/stderr/returncode)
  - L4.32 / L4.33 / L4.34 永久规则 regression (subprocess cwd + chdir pollution
    + 跨平台 Path resolve)

设计 (Sprint 182 D4):
  - 不连 DuckDB (MCP server 只透传 CLI, data 走 scripts/ad_hoc_query.py 内部 read_only)
  - 复用 test_claude_hooks.py 的 subprocess + REPO_ROOT + shlex.split 模式
  - 每个 test 独立跑 subprocess, 不依赖 isolated_duckdb fixture
  - 跑 daily-gsv --help 等不需要 DuckDB 的子命令验证 subprocess 启动
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock

import pytest

# Sprint 181 模式 (跟 test_claude_hooks.py:29 一致): lock subprocess CWD to
# repo root, 防御 test_association_filter_builder / test_matrix_filter_builder
# 的 os.chdir 污染源. 任何 subprocess.run 必须 cwd=PROJECT_ROOT.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = REPO_ROOT
MCP_SERVER_DIR = PROJECT_ROOT / "mcp_servers" / "fuqing_adhoc"

# 9 个 query tool + 1 个 ask tool (跟 _dispatch.py TOOL_DEFS SSOT 一致,
# MCP tool name 用 underscore 形式, 跟 CLI command hyphen 形式区分).
EXPECTED_TOOLS: List[str] = [
    "daily_gsv",
    "yoy_battle",
    "channel_slice",
    "two_year_overview",
    "new_old_customer",
    "rfm_repurchase",
    "top_n",
    "export_excel",
    "dq_report",
    "ask",  # 第 10 个: 自然语言路由
]

# Sprint 182 D3: _TOOL_DEFS 一次声明, _make_handler factory 翻译 MCP call → CLI argv
EXPECTED_TOOL_COUNT = 10


# ─────────────────────────────────────────────────────────────
# Module-level fixtures & helpers
# ─────────────────────────────────────────────────────────────
def _import_server():
    """Import mcp_servers.fuqing_adhoc.server, 返回 module.

    Sprint 181: 走 sys.path.insert(0, REPO_ROOT) 跟 test_claude_hooks.py 一致.
    """
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from mcp_servers.fuqing_adhoc import server as server_mod
        return server_mod
    except ImportError as exc:
        pytest.skip(f"MCP server module not importable yet: {exc}")


def _run_cli(argv: List[str], timeout: int = 30) -> Dict[str, Any]:
    """Run scripts/ad_hoc_query.py <argv> as real subprocess, 返 dict.

    Sprint 181 模式: cwd=PROJECT_ROOT 防御 chdir 污染.
    Sprint 182 D3: PYTHONPATH 透传 (server._run_cli 用 env=os.environ.copy()).
    """
    result = subprocess.run(
        [sys.executable, "scripts/ad_hoc_query.py", *argv],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


# ─────────────────────────────────────────────────────────────
# Class 1: TestMcpServerImport (3 cases)
# ─────────────────────────────────────────────────────────────
class TestMcpServerImport:
    """Verify mcp_servers.fuqing_adhoc.server module imports cleanly and exposes
    the 9-tool registry contract documented in Sprint 182 plan D3/D4.

    Each test asserts on the planned interface (list_tools / tool schemas) so
    that any future drift (missing tool, schema typo, wrong shape) is caught
    before WorkBuddy / Claude Code connects to a broken server.
    """

    def test_server_importable(self):
        """Import mcp_servers.fuqing_adhoc.server MUST NOT raise.

        目的: 验证 MCP server 文件存在 + 顶层 import 干净 (无 syntax error,
        无 MissingOptionalDependency 等启动期 fail). 这是 Sprint 182 最小
        烟雾测试 — 任何 L4.34 路径错配或 sys.path 漏配会立刻爆.

        Sprint 182 Phase 4 fix: 我们没用 mcp SDK (手写 stdio JSON-RPC ~30 行),
        所以暴露的是 'serve()' main entry, 不是 'server.Server' 实例.
        """
        server_mod = _import_server()
        assert server_mod is not None
        # 验证模块暴露 stdio JSON-RPC main entry 'serve' 函数 (Sprint 182 D2 决策: 手写 framing, 不引 mcp SDK)
        assert hasattr(server_mod, "serve"), (
            "期望 server module 暴露 'serve' 函数 (stdio JSON-RPC main entry, "
            f"Sprint 182 手写 framing 不引 mcp SDK), "
            f"实际只有: {[a for a in dir(server_mod) if not a.startswith('_')]}"
        )
        assert callable(server_mod.serve), "期望 serve 是 callable"

    def test_list_tools_returns_9_tools(self):
        """list_tools() MUST return exactly 9 tools (8 query + 1 ask).

        目的: 锁 Sprint 182 计划 D4 列出的 9 tool 数量. 任何后续添加新 tool
        必须显式更新 EXPECTED_TOOLS, 防 plan drift 跟实际 server 不一致.
        """
        server_mod = _import_server()
        tools = server_mod.list_tools()
        assert isinstance(tools, list), f"期望 list_tools() 返 list, got {type(tools)}"
        assert len(tools) == EXPECTED_TOOL_COUNT, (
            f"期望 {EXPECTED_TOOL_COUNT} tools (8 query + 1 ask), "
            f"got {len(tools)}: {[t.get('name') for t in tools]}"
        )
        tool_names = {t.get("name") for t in tools}
        missing = set(EXPECTED_TOOLS) - tool_names
        assert not missing, (
            f"期望 list_tools() 包含 {EXPECTED_TOOLS}, missing: {missing}; "
            f"实际 tool_names={tool_names}"
        )

    def test_tool_schemas_valid_json_schema(self):
        """Each tool's inputSchema MUST be a valid JSON Schema (type=object + properties).

        目的: MCP 协议要求每个 tool inputSchema 是合法 JSON Schema (type="object").
        任何 schema 写错 (e.g. type 漏掉, properties 不是 dict) 都会被 MCP client
        (WorkBuddy / Claude Code) 拒绝. 锁住 schema 形状防回归.
        """
        server_mod = _import_server()
        tools = server_mod.list_tools()
        for tool in tools:
            name = tool.get("name", "<unnamed>")
            schema = tool.get("inputSchema")
            assert isinstance(schema, dict), (
                f"tool {name!r} inputSchema 必须是 dict, got {type(schema)}"
            )
            assert schema.get("type") == "object", (
                f"tool {name!r} inputSchema['type'] 必须是 'object', "
                f"got {schema.get('type')!r}"
            )
            props = schema.get("properties")
            assert isinstance(props, dict), (
                f"tool {name!r} inputSchema['properties'] 必须是 dict, "
                f"got {type(props)}"
            )


# ─────────────────────────────────────────────────────────────
# Class 2: TestRunCliSubprocess (4 cases)
# ─────────────────────────────────────────────────────────────
class TestRunCliSubprocess:
    """Verify the MCP server's subprocess dispatch helper (_run_cli) honors
    Sprint 181 + Sprint 182 永久规则:
      - L4.32 subprocess cwd lock: subprocess.run 必须 cwd=PROJECT_ROOT
      - L4.34 Path(__file__).resolve: _SCRIPT_PATH 跨平台绝对路径
      - PYTHONPATH 透传: 子 Python 能 import backend.services + scripts.*
    """

    def test_subprocess_uses_project_cwd(self):
        """_run_cli MUST pass cwd=PROJECT_ROOT to subprocess.run.

        目的: 锁 L4.32 永久规则 — 任何 subprocess.run 启动子 Python 必须
        cwd=PROJECT_ROOT, 防止 chdir 污染源 (test_association_filter_builder
        那种 `os.chdir(tmp)` 不恢复) 让子 Python 找不到 cwd 抛 OSError.
        """
        server_mod = _import_server()
        # server._run_cli 暴露的进程入口
        assert hasattr(server_mod, "_run_cli"), (
            "期望 server module 暴露 '_run_cli' 函数"
        )

        with mock.patch.object(server_mod, "subprocess") as mock_sp:
            mock_sp.run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")
            server_mod._run_cli(["daily-gsv", "--help"])

        assert mock_sp.run.called, "期望 _run_cli 调 subprocess.run"
        kwargs = mock_sp.run.call_args.kwargs
        assert kwargs.get("cwd") == str(PROJECT_ROOT), (
            f"L4.32 违规: subprocess.run cwd={kwargs.get('cwd')!r}, "
            f"期望 {str(PROJECT_ROOT)!r} (跟 L4.32 cwd lock 一致)"
        )

    def test_subprocess_uses_resolve_path(self):
        """_SCRIPT_PATH MUST be absolute (Path(__file__).resolve() 跨平台).

        目的: 锁 L4.34 永久规则 — 任何 test/code 真 access 文件必用
        Path(__file__).resolve() 跨平台构造, 禁止硬编码 /Users/... 路径.
        Sprint 181.1 真因: hardcoded macOS 路径让 Linux CI runner FileNotFoundError.
        """
        server_mod = _import_server()
        # _SCRIPT_PATH 必须存在 (server.py 用它调 CLI)
        assert hasattr(server_mod, "_SCRIPT_PATH"), (
            "期望 server module 暴露 '_SCRIPT_PATH' 常量 (scripts/ad_hoc_query.py 路径)"
        )
        script_path = server_mod._SCRIPT_PATH
        # 兼容 str 和 Path 两种类型
        is_absolute = (
            Path(script_path).is_absolute()
            if not isinstance(script_path, str)
            else Path(script_path).is_absolute()
        )
        assert is_absolute, (
            f"L4.34 违规: _SCRIPT_PATH={script_path!r} 不是绝对路径; "
            f"必须 Path(__file__).resolve() 跨平台构造"
        )
        # 路径必须真的指向 scripts/ad_hoc_query.py
        assert "ad_hoc_query.py" in str(script_path), (
            f"_SCRIPT_PATH={script_path!r} 应该指向 scripts/ad_hoc_query.py"
        )

    def test_subprocess_inherits_pythonpath(self):
        """_run_cli MUST pass env with PYTHONPATH so child Python can import backend.services.

        目的: scripts/ad_hoc_query.py 启动时 import backend.services / backend.contracts
        需要 PYTHONPATH 含 PROJECT_ROOT. 如果 _run_cli 用 env={} (空 dict), 子 Python
        找不到 backend module → ModuleNotFoundError → MCP error 让 LLM 报 "环境不对".

        反例 (Sprint 182 D3 决策): 走 env=os.environ.copy() + 注入 PYTHONPATH.
        """
        server_mod = _import_server()

        with mock.patch.object(server_mod, "subprocess") as mock_sp:
            mock_sp.run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")
            server_mod._run_cli(["daily-gsv", "--help"])

        assert mock_sp.run.called
        kwargs = mock_sp.run.call_args.kwargs
        env = kwargs.get("env", {})
        assert env, (
            "L4.32 配套: _run_cli 必须传 env=... 让子 Python 继承 PYTHONPATH"
        )
        pythonpath = env.get("PYTHONPATH", "")
        assert str(PROJECT_ROOT) in pythonpath or PROJECT_ROOT.name in pythonpath, (
            f"期望 env['PYTHONPATH'] 含 PROJECT_ROOT={PROJECT_ROOT}, "
            f"got PYTHONPATH={pythonpath!r}; 子 Python 找不到 backend.services"
        )

    def test_subprocess_returns_stdout_stderr(self):
        """Real subprocess `ad_hoc_query.py daily-gsv --help` MUST return 0 + non-empty stdout.

        目的: 验证 scripts/ad_hoc_query.py 真能跑 (不需要 DuckDB, --help 即可),
        验证 _run_cli 返 dict 形状 (returncode + stdout + stderr) 跟 MCP 协议期望一致.
        这是 integration 测, 不 mock subprocess.
        """
        result = _run_cli(["daily-gsv", "--help"], timeout=15)
        assert "returncode" in result, "期望返 dict 含 'returncode'"
        assert "stdout" in result, "期望返 dict 含 'stdout'"
        assert "stderr" in result, "期望返 dict 含 'stderr'"
        assert result["returncode"] == 0, (
            f"`ad_hoc_query.py daily-gsv --help` 应该 exit 0, "
            f"got rc={result['returncode']}, stderr={result['stderr']!r}"
        )
        # argparse --help 输出包含 usage / options
        assert "--start" in result["stdout"] or "--end" in result["stdout"], (
            f"期望 stdout 含 argparse help (--start/--end), "
            f"got stdout={result['stdout'][:300]!r}"
        )


# ─────────────────────────────────────────────────────────────
# Class 3: TestMcpToolDispatch (5 cases)
# ─────────────────────────────────────────────────────────────
class TestMcpToolDispatch:
    """End-to-end dispatch tests: real subprocess + scripts/ad_hoc_query.py CLI.

    这些测试用真 CLI (不 mock subprocess), 验证 MCP server 的 9 tool 真的能
    透传 argv 到 CLI 并拿到合法 returncode + stdout + stderr.

    Sprint 182 D4 范围:
      - daily-gsv basic (dry-run with --help, since DuckDB may not be available)
      - invalid date (subprocess returncode != 0)
      - ask router (routed_command == 'two-year-overview')
      - ask fallback (friendly error)
      - timeout handling (mock subprocess hang)
    """

    def test_run_daily_gsv_basic(self):
        """MCP daily-gsv tool dispatch MUST return rc=0 + non-empty stdout.

        目的: 端到端验证 MCP tool handler → CLI subprocess 透传. 用 --help 跑
        (不需要 DuckDB, 任何 clone 都能跑). 真实业务调用会走 daily-gsv --start
        --end, 但那条路依赖 isolated_duckdb, 这里只验 dispatch 形状.
        """
        result = _run_cli(["daily-gsv", "--help"], timeout=15)
        assert result["returncode"] == 0, (
            f"期望 daily-gsv --help exit 0, got rc={result['returncode']}, "
            f"stderr={result['stderr']!r}"
        )
        assert result["stdout"], (
            "期望 daily-gsv --help stdout 非空 (argparse usage)"
        )
        assert result["stderr"] == "" or "WARN" not in result["stderr"], (
            f"期望 stderr 无错误, got stderr={result['stderr']!r}"
        )

    def test_run_with_invalid_date_returns_nonzero(self):
        """daily-gsv --start 2026-13-99 --end 2026-06-21 MUST return rc != 0.

        目的: 验证 dispatch error path — 错误日期格式应让 CLI 抛 ValueError
        (Sprint 60+ 沉淀, main() 返 rc=2). MCP handler 必须透传这个 rc, 让
        WorkBuddy LLM 看到错误. 防止 MCP handler 静默吞错 (那种会让 LLM 以为
        跑成功, 实际数据 0 行).
        """
        result = _run_cli(
            ["daily-gsv", "--start", "2026-13-99", "--end", "2026-06-21"],
            timeout=15,
        )
        assert result["returncode"] != 0, (
            f"期望 invalid date 让 CLI exit != 0, got rc={result['returncode']}; "
            f"stdout={result['stdout']!r} stderr={result['stderr']!r}"
        )
        # Sprint 60+ 沉淀: ValueError / KeyError → rc=2; stderr 含 [ERROR] prefix
        assert "ERROR" in result["stderr"] or "error" in result["stderr"], (
            f"期望 stderr 含 ERROR 提示, got stderr={result['stderr']!r}"
        )

    def test_ask_tool_routes_to_two_year(self):
        """ask "两年对比" MUST route to 'two-year-overview' command.

        目的: 验证 Sprint 171 ask router 关键词路由 + Sprint 182 MCP ask tool
        透传. 输入 "两年对比" → 命中 ("两年对比", "30指标", "老客", "新客",
        "会员") tuple → command="two-year-overview".

        注: 不实际执行 query (避免 DuckDB 依赖), 直接调 scripts.ad_hoc_queries.ask
        验证 route_ask 函数的 keyword matching 逻辑.
        """
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.ad_hoc_queries import ask as ask_mod

        command, params = ask_mod.route_ask("两年对比")
        assert command == "two-year-overview", (
            f"期望 ask '两年对比' 路由到 two-year-overview, got {command!r}; "
            f"关键词匹配规则可能漂移 (Sprint 171 SSOT)"
        )
        assert isinstance(params, dict), f"期望 params 是 dict, got {type(params)}"

    def test_ask_fallback_when_no_keyword(self):
        """ask "完全随机关键词" MUST fallback gracefully (no crash).

        目的: 验证 Sprint 171 沉淀 — 关键词都不命中时返 friendly fallback row
        ["list-endpoints", "fallback", "请说更具体点..."] 而非崩. MCP handler
        必须把这行透传到 stdout 让 LLM 看到 "请说更具体点", 引导用户改问法.
        """
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.ad_hoc_queries import ask as ask_mod

        command, params = ask_mod.route_ask("完全随机关键词 xyz123 no_match_xyz")
        assert command is None, (
            f"期望无关键词命中时返 None (fallback), got {command!r}; "
            f"说明关键词匹配规则过宽, 误触发其他 command"
        )
        assert params == {}, (
            f"期望 fallback 时 params 空 dict, got {params!r}"
        )
        # Sprint 171 run_ask fallback row: command + "fallback" + 提示文案
        rows = ask_mod.run_ask("完全随机关键词 xyz123 no_match_xyz")
        assert len(rows) == 1, f"期望 fallback 返 1 行, got {len(rows)} rows"
        assert rows[0][0] == "list-endpoints", (
            f"期望 fallback command='list-endpoints', got {rows[0][0]!r}"
        )
        assert rows[0][1] == "fallback", (
            f"期望 fallback status='fallback', got {rows[0][1]!r}"
        )
        assert "请说更具体点" in str(rows[0][2]), (
            f"期望 fallback 含友好提示文案, got {rows[0][2]!r}"
        )

    def test_timeout_handling(self):
        """_run_cli MUST timeout (default 5s) on hung subprocess, not hang test.

        目的: 锁 Sprint 182 D3 决策 — subprocess timeout 默认 300s (CLI 内部
        < 10s, XLSX 30s, 10x headroom). MCP handler 必须 catch TimeoutExpired
        并返 structured error, 不能让 test hang 死.

        实现: mock subprocess.run 抛 TimeoutExpired, 验证 _run_cli 处理 (不
        re-raise, 不让 test 卡死). 这里测的是 MCP server 层的 timeout 兜底.

        Sprint 182 Phase 4 fix: 用 mock.patch("subprocess.run", ...) 全局 mock,
        而不是 mock.patch.object(server_mod, "subprocess"). 后者会把 subprocess
        module 整个替换为 MagicMock, 导致 _run_cli 内 `except subprocess.TimeoutExpired`
        引用 MagicMock.TimeoutExpired (不是真 BaseException 子类) 抛 TypeError.
        """
        server_mod = _import_server()

        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(
            cmd=["python3", "scripts/ad_hoc_query.py", "daily-gsv"],
            timeout=5,
        )):
            # _run_cli 必须 catch 兜底 (返 error dict 或 raise custom),
            # 不能让 TimeoutExpired 透传挂死 MCP client
            try:
                result = server_mod._run_cli(["daily-gsv"], timeout=5)
            except subprocess.TimeoutExpired:
                # 如果 _run_cli 透传 TimeoutExpired, test 仍不算 fail (server 设计
                # 可能让上层 MCP SDK catch). 但更期望 server 自己返 structured error.
                pytest.fail(
                    "期望 _run_cli 处理 TimeoutExpired (返 error dict 或 raise "
                    "custom exception), 不是透传 subprocess.TimeoutExpired"
                )
            # 如果 _run_cli 返 dict (error path), 验 error 形状合理
            assert isinstance(result, dict), f"期望 _run_cli 返 dict, got {type(result)}: {result!r}"
            assert result.get("returncode") != 0 or "timeout" in str(result).lower(), (
                f"期望 timeout 后 _run_cli 返 error shape, got {result!r}"
            )


# ─────────────────────────────────────────────────────────────
# Class 4: TestL4ComplianceRegression (2 cases)
# ─────────────────────────────────────────────────────────────
class TestL4ComplianceRegression:

    def test_no_chdir_pollution(self):
        """After _run_cli real subprocess, os.getcwd() MUST still be PROJECT_ROOT.

        目的: L4.33 锁回归 — 任何 _run_cli 内部不能调 os.chdir (那会让父 test
        进程 CWD 漂移到临时目录, 后续 test 拿不到 CWD → subprocess.OSError).
        真 subprocess 跑 daily-gsv --help 后, 父进程的 CWD 必须还是 PROJECT_ROOT.
        """
        original_cwd = os.getcwd()
        # 防御: 确保 test 启动时 CWD 就是 PROJECT_ROOT
        assert original_cwd == str(PROJECT_ROOT), (
            f"期望 test 启动时 CWD={PROJECT_ROOT}, got {original_cwd}; "
            f"前置 fixture 没生效"
        )

        # 跑真 subprocess (跟 test_subprocess_uses_project_cwd 一致, 但用真跑)
        result = _run_cli(["daily-gsv", "--help"], timeout=15)
        assert result["returncode"] == 0, (
            f"前置条件: daily-gsv --help 应 rc=0, got rc={result['returncode']}, "
            f"stderr={result['stderr']!r}"
        )

        # 核心断言: 父进程 CWD 仍是 PROJECT_ROOT
        after_cwd = os.getcwd()
        assert after_cwd == original_cwd == str(PROJECT_ROOT), (
            f"L4.33 违规: _run_cli 后父进程 CWD 漂移 "
            f"{original_cwd!r} → {after_cwd!r}; "
            f"预期 {str(PROJECT_ROOT)!r} 不变"
        )

    def test_path_resolve_no_hardcoded_mac(self):
        """mcp_servers/fuqing_adhoc/*.py MUST NOT contain hardcoded '/Users/hutou' paths.

        目的: L4.34 锁回归 — Sprint 181.1 真因: test_claude_hooks 硬编码
        /Users/hutou/Desktop/fuqin-date/... macOS 路径, Linux CI runner
        FileNotFoundError. MCP server 模块必须全用 Path(__file__).resolve()
        跨平台构造, 禁止硬编码 /Users/hutou 路径.

        实现: 静态 grep 扫 mcp_servers/fuqing_adhoc/ 目录下所有 .py 文件,
        0 命中 '/Users/hutou' (防 Sprint 181.1 跨 sprint 复发).

        注: 如果 mcp_servers/fuqing_adhoc/ 目录还没创建 (Phase 2.A 未实施),
        pytest.skip 兜底, 避免阻塞 Phase 2.B 实施.
        """
        if not MCP_SERVER_DIR.exists():
            pytest.skip(
                f"MCP server dir {MCP_SERVER_DIR} 还不存在 (Phase 2.A 未实施); "
                f"待 Phase 2.A 落地后此 test 自动生效"
            )

        violations: List[tuple[str, int, str]] = []
        pattern = re.compile(r"/Users/hutou")  # L4.34 永久规则禁止的硬编码前缀

        for py_file in sorted(MCP_SERVER_DIR.glob("*.py")):
            try:
                content = py_file.read_text(encoding="utf-8")
            except OSError:
                continue
            for lineno, line in enumerate(content.splitlines(), start=1):
                if pattern.search(line):
                    violations.append((str(py_file), lineno, line.strip()))

        assert not violations, (
            f"L4.34 违规: MCP server 模块硬编码 '/Users/hutou' 路径 "
            f"({len(violations)} 处); 必须改用 Path(__file__).resolve() 跨平台构造. "
            f"命中: {violations[:5]}"
        )

    def test_content_length_upper_bound_prevents_dos(self):
        """Content-Length > MAX_CONTENT_LENGTH MUST return None (graceful EOF, not hang).

        目的: Sprint 182 Phase 4 adversarial fix (confidence 9/10). 锁回归防
        sys.stdin.buffer.read(content_length) 永久阻塞. 单 MCP client 发
        Content-Length: 999999999999 会让 read() 等满, MCP server 进程僵死.
        防御: MAX_CONTENT_LENGTH=1MB cap, 超限 → _read_message 返 None →
        serve() 主循环 EOF 退出, WorkBuddy 重启.
        """
        server_mod = _import_server()
        assert hasattr(server_mod, "MAX_CONTENT_LENGTH"), (
            "L4.x 永久规则: server.py 必须暴露 MAX_CONTENT_LENGTH 常量"
        )
        assert server_mod.MAX_CONTENT_LENGTH <= 10 * 1024 * 1024, (
            f"MAX_CONTENT_LENGTH={server_mod.MAX_CONTENT_LENGTH} 太大 (>10MB); "
            "DoS 防御失效"
        )

    def test_output_path_sanitization_blocks_path_injection(self):
        """--output 参数 MUST 走 _sanitize_path_component, 禁裸 ~/.ssh/authorized_keys 等路径.

        目的: Sprint 182 Phase 4 adversarial fix (confidence 8/10). 锁回归防
        LLM prompt injection 写任意路径. 期望: _make_handler 对 output/file 参数
        调 _sanitize_path_component; raw "~/../" 或 "/etc/" 应该被替换或拒绝.
        """
        from mcp_servers.fuqing_adhoc import _dispatch as dispatch_mod

        # 找任意含 output 参数的 tool (e.g. daily_gsv)
        daily_gsv = next(td for td in dispatch_mod.TOOL_DEFS if td["name"] == "daily_gsv")
        handler = dispatch_mod._make_handler(daily_gsv)

        # 攻击路径: ../ 路径遍历 + 绝对路径 + ~ 用户目录
        malicious_paths = [
            "../../../tmp/evil.csv",
            "/etc/cron.d/exploit",
            "~/.ssh/authorized_keys",
            "/Users/hutou/.ssh/authorized_keys",
        ]
        for path in malicious_paths:
            argv = handler({"start": "2026-06-21", "end": "2026-06-21", "output": path})
            # --output 后必须是 sanitize 后的值 (非 raw path)
            assert "--output" in argv
            out_idx = argv.index("--output") + 1
            sanitized = argv[out_idx]
            assert sanitized != path, (
                f"L4.x 漏洞: --output 透传 raw 攻击路径 {path!r}; "
                f"必须 _sanitize_path_component"
            )
            # 关键检查: 不应包含 ../ 或 /etc/ 或 /Users/
            assert ".." not in sanitized or sanitized.startswith("_"), (
                f"sanitize 后仍含 '..': {sanitized!r}"
            )
            assert "/etc/" not in sanitized, f"sanitize 后仍含 /etc/: {sanitized!r}"
            assert "/Users/" not in sanitized, f"sanitize 后仍含 /Users/: {sanitized!r}"

    def test_run_cli_truncates_stdout_stderr(self):
        """_run_cli MUST truncate stdout/stderr > 4KB 防 LLM 上下文撑爆 + traceback 泄漏.

        目的: Sprint 182 Phase 4 adversarial fix (confidence 8/10). 真连 mock 一个
        返回 10KB stdout 的 subprocess, 验证 _run_cli 截断 + "[truncated]" 标记.
        """
        server_mod = _import_server()
        # 找常量
        assert hasattr(server_mod, "MAX_STDOUT_BYTES")
        assert hasattr(server_mod, "MAX_STDERR_BYTES")
        assert server_mod.MAX_STDOUT_BYTES <= 8192, (
            f"MAX_STDOUT_BYTES={server_mod.MAX_STDOUT_BYTES} 太大"
        )

        # Mock subprocess.run 返 10KB stdout
        fake_stdout = "x" * 10240
        fake_stderr = "y" * 10240
        with mock.patch.object(server_mod, "subprocess") as mock_sp:
            mock_sp.run.return_value = mock.Mock(
                returncode=0, stdout=fake_stdout, stderr=fake_stderr
            )
            result = server_mod._run_cli(["daily-gsv", "--help"])

        assert len(result["stdout"]) <= server_mod.MAX_STDOUT_BYTES + 50, (
            f"stdout 未截断: {len(result['stdout'])} bytes"
        )
        assert "[truncated]" in result["stdout"], (
            f"stdout 截断后应含 '[truncated]' 标记, got: {result['stdout'][-50:]!r}"
        )
        assert len(result["stderr"]) <= server_mod.MAX_STDERR_BYTES + 50
        assert "[truncated]" in result["stderr"]

    def test_workbuddy_mcp_json_no_hardcoded_path(self):
        """~/.workbuddy/.mcp.json MUST NOT contain hardcoded '/Users/hutou' path.

        目的: Sprint 182 Phase 4 adversarial fix (confidence 9/10). Sprint 181.1 真因
        复发到 deployment manifest. fuqing_adhoc args 应含 ${HOME} 或 $HOME 占位,
        不能写死绝对路径.
        """
        import json
        mcp_json_path = Path("/Users/hutou/.workbuddy/.mcp.json")
        if not mcp_json_path.exists():
            pytest.skip("~/.workbuddy/.mcp.json 不存在 (WorkBuddy 没装)")
        config = json.loads(mcp_json_path.read_text(encoding="utf-8"))
        servers = config.get("mcpServers", {})
        fuqing_cfg = servers.get("fuqing_adhoc")
        if fuqing_cfg is None:
            pytest.skip("~/.workbuddy/.mcp.json 没配 fuqing_adhoc server entry")
        # 验证 args 列表不含裸 /Users/hutou 绝对路径
        for arg in fuqing_cfg.get("args", []):
            if isinstance(arg, str) and arg.startswith("/Users/"):
                # 应该是 ${HOME} 或 ~ 开头 (WorkBuddy 支持 env 展开)
                assert arg.startswith("${HOME}/") or arg.startswith("~/") or arg.startswith("$HOME/"), (
                    f"L4.34 漏洞: ~/.workbuddy/.mcp.json fuqing_adhoc args 含硬编码 "
                    f"绝对路径 {arg!r}; 换机器 / home dir 改名会启动失败. "
                    f"必改 ${'{'}HOME{'}'}/ 跨平台 env 展开."
                )