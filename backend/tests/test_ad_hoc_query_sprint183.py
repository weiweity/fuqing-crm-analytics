"""Sprint 183 /ad-hoc-query v2.2 regression tests.

L4.36 锁回归, 防 WorkBuddy self-review 暴露的 4 个根因复发:
1. 不知 SKILL.md v2.2 顶部 "执行路径强制" 段
2. 误把 3 个 CLI 子命令当能力全集
3. 误判 DuckDB 锁让用户停 uvicorn
4. 写临时脚本重复造轮子
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


SKILL_MD_PATH = Path.home() / ".claude/skills/ad-hoc-query/SKILL.md"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLAUDE_MD_PATH = PROJECT_ROOT / "CLAUDE.md"


# Sprint 185 治本 (Sprint 182 / 183 / 184 跨 3 sprint CI 复发真因):
# ~/.claude/skills/* 是 macOS 本地 skill 路径, Linux CI runner (GitHub Actions
# ubuntu-latest) 永远是 /home/runner/.claude/skills, SKILL.md 不存在. 这些
# 测试是 macOS 端 L4.36 锁回归, Linux runner 应 skip 而非 fail.
# 跟 L4.10 平台守卫永久规则同位.
@pytest.mark.skipif(
    sys.platform != "darwin",
    reason="macOS-only: ~/.claude/skills/ 路径在 Linux CI runner 不存在 (Sprint 182/183/184 跨 3 sprint CI 复发)",
)
class TestSprint183L4Regression:
    """L4.36 锁回归: SKILL.md v2.2 + CLAUDE.md L4.36."""

    def test_skill_md_v22_has_execution_path_section(self):
        """SKILL.md v2.2 顶部必须有执行路径强制段."""
        assert SKILL_MD_PATH.exists(), f"SKILL.md 不存在: {SKILL_MD_PATH}"
        content = SKILL_MD_PATH.read_text(encoding="utf-8")
        assert "## 0. 执行路径强制" in content, (
            "SKILL.md v2.2 必须含 '## 0. 执行路径强制' 段"
        )
        forbidden_markers = [
            "查 openapi.json",
            "直连 DuckDB",
            "写 scripts/adhoc",
            "停 uvicorn",
        ]
        forbidden_count = sum(1 for marker in forbidden_markers if marker in content)
        assert forbidden_count >= 3, (
            "执行路径强制段必须列 >=3 条禁止路径 "
            f"(openapi/DuckDB/adhoc/uvicorn), 实际命中 {forbidden_count}"
        )

    def test_skill_md_v22_lists_10_mcp_tools_not_3_cli(self):
        """SKILL.md 必须列 10 个 MCP tool, 不是 3 个 CLI 子命令."""
        content = SKILL_MD_PATH.read_text(encoding="utf-8")
        expected_tools = [
            "daily_gsv",
            "yoy_battle",
            "channel_slice",
            "two_year_overview",
            "new_old_customer",
            "rfm_repurchase",
            "top_n",
            "export_excel",
            "dq_report",
            "ask",
        ]
        missing = [tool for tool in expected_tools if f"`{tool}`" not in content]
        assert not missing, f"SKILL.md v2.2 缺 MCP tools 描述: {missing}"

    def test_skill_md_v22_disallows_stop_uvicorn(self):
        """SKILL.md 必须明确禁止停 uvicorn 并给 graceful fallback."""
        content = SKILL_MD_PATH.read_text(encoding="utf-8")
        assert "停 uvicorn" in content or "禁停 uvicorn" in content, (
            "SKILL.md v2.2 必须含 '停 uvicorn' 禁止文案"
        )
        assert "graceful" in content.lower() or "重试" in content, (
            "SKILL.md v2.2 必须含锁冲突 graceful fallback 教法"
        )


# Sprint 185 治根: test_claude_md_l4_36_added 跨平台 (CLAUDE.md 路径 project-relative),
# 单独 class 不受 macOS-only skipif 守卫, Linux CI runner 也跑. 配套 L4.10/L4.39 永久规则.
class TestSprint183L4CrossPlatform:
    """L4.36 锁回归, 跨平台 (CLAUDE.md 在主仓, 不依赖 macOS 本地路径)."""

    def test_claude_md_l4_36_added(self):
        assert CLAUDE_MD_PATH.exists(), f"CLAUDE.md 不存在: {CLAUDE_MD_PATH}"
        content = CLAUDE_MD_PATH.read_text(encoding="utf-8")
        assert "L4.36" in content, "CLAUDE.md 必须含 L4.36 永久规则"

        # 提取 L4.x 永久规则段: markdown 表格行 " | **L4.xx ..." (允许 0+ 前导空格)
        import re
        rule_pattern = re.compile(r"^[ ]*\| \*\*L4\.(\d+)", re.MULTILINE)
        rule_positions = [
            (int(m.group(1)), m.start())
            for m in rule_pattern.finditer(content)
        ]
        assert rule_positions, "CLAUDE.md 缺 L4.x 永久规则段"
        rule_dict = dict(rule_positions)
        assert 35 in rule_dict and 36 in rule_dict, "需有 L4.35 / L4.36 规则段"
        assert rule_dict[36] > rule_dict[35], (
            f"L4.36 永久规则段必须出现在 L4.35 之后 (实际位置 {rule_dict})"
        )


class TestDailyGsvMultiPeriod:
    """daily_gsv_multi_period 新子命令 acceptance tests."""

    def test_metric_sql_keys_complete(self):
        """daily_gsv_multi_period 8 个 metric 必须全在 _METRIC_SQL."""
        from scripts.ad_hoc_queries import daily_gsv_multi_period as mod

        expected = {
            "sample_gmv",
            "sample_gsv",
            "member_gmv",
            "member_gsv",
            "new_users",
            "new_gsv",
            "old_users",
            "old_gsv",
        }
        actual = set(mod._METRIC_SQL.keys())
        assert actual == expected, (
            f"_METRIC_SQL 不全: missing={expected - actual}, "
            f"extra={actual - expected}"
        )

    def test_registry_registers_daily_gsv_multi_period(self):
        """daily-gsv-multi-period 必须注册到 QUERIES dict.

        Sprint 183 Phase 4 QA fix (confidence 9/10): pytest collection 会触发 import
        新模块, 让 test 通过但生产环境 standalone CLI 跑不到. 修复:
        registry.py _load_builtins() 显式 import 新模块 + name 跟其他 query
        统一用 hyphen 风格 (跟 daily-gsv / yoy-battle 一致).
        """
        # 不主动 import, 模拟真实场景: 只通过 _load_builtins() 自动加载
        from scripts.ad_hoc_queries.registry import QUERIES, _load_builtins
        _load_builtins()  # 显式重跑 (防 import order 飘移)
        assert "daily-gsv-multi-period" in QUERIES, (
            "QUERIES dict 缺 daily-gsv-multi-period 注册. "
            "根因: registry.py _load_builtins() 没显式 import 新模块. "
            "Sprint 183 QA 抓到: pytest 自动 import 测试目录的 daily_gsv_multi_period "
            "让 test 通过, 但 standalone CLI 跑不到 (argparse 找不到 subcommand)."
        )

    def test_query_name_uses_hyphen_style(self):
        """Sprint 183 Phase 4 QA fix (confidence 9/10): query name 必须 hyphen 风格.

        锁回归: argparse subcommand 严格匹配 name (不自动转 _ → -).
        Codex 第一次用 underscore (daily_gsv_multi_period) 导致 CLI 调用失败.
        修后改成 hyphen (daily-gsv-multi-period) 跟其他 9 个 query 一致.
        """
        from scripts.ad_hoc_queries.registry import QUERIES
        for name, spec in QUERIES.items():
            assert "_" not in name, (
                f"query name {name!r} 含下划线, argparse 调用匹配会失败. "
                f"必须用 hyphen 风格 (e.g. daily-gsv-multi-period). "
                f"参考: daily-gsv / yoy-battle / channel-slice 等 10 个 query."
            )

    def test_cli_subcommand_daily_gsv_multi_period_recognized(self):
        """Sprint 183 Phase 4 QA fix (confidence 9/10): argparse 必须能识别 daily-gsv-multi-period.

        端到端锁回归: 模拟用户 CLI 调用, 验证 argparse subcommand 列表包含新 tool.
        pytest collection 自动 import 掩盖了这个问题 (registry 已 load), 必须真跑
        argparse 入口, 不依赖任何测试 setup 的隐式 import.
        """
        # 关键: 不 import 任何 daily_gsv_multi_period 模块, 模拟 production CLI
        import subprocess
        import sys as _sys

        result = subprocess.run(
            [_sys.executable, "scripts/ad_hoc_query.py", "daily-gsv-multi-period", "--help"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(PROJECT_ROOT),
            env={**__import__("os").environ, "PYTHONPATH": str(PROJECT_ROOT)},
        )
        # 期望: argparse 找到 subcommand, 走 help 路径, rc=0
        # 实际 bug 行为: rc=2 + "invalid choice: 'daily-gsv-multi-period'"
        assert result.returncode == 0, (
            f"CLI 找不到 daily-gsv-multi-period subcommand. "
            f"rc={result.returncode}, stderr={result.stderr[:500]!r}. "
            f"根因: registry.py _load_builtins() 没显式 import daily_gsv_multi_period. "
            f"Sprint 183 Phase 4 QA fix 已修."
        )
        assert "--periods" in result.stdout, (
            f"daily-gsv-multi-period --help 期望含 --periods 参数, "
            f"got stdout={result.stdout[:500]!r}"
        )

    def test_mcp_server_lists_daily_gsv_multi_period(self):
        """Sprint 183 Phase 4 QA fix (confidence 9/10): MCP server tools/list 必须含 daily_gsv_multi_period.

        端到端锁回归: 真 subprocess 启动 MCP server, 走 JSON-RPC handshake, 验证
        tools/list 返 11 个 tool (含新 tool). pytest 不启动 server, 所以这个 case 必
        须真跑.
        """
        import subprocess
        import json
        import sys as _sys

        proc = subprocess.Popen(
            [_sys.executable, "mcp_servers/fuqing_adhoc/server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        try:
            def send(msg):
                body = json.dumps(msg).encode("utf-8")
                header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
                proc.stdin.write(header + body)
                proc.stdin.flush()

            def recv():
                line = proc.stdout.readline()
                if not line:
                    return None
                cl = int(line.split(b":")[1].strip())
                proc.stdout.readline()
                return json.loads(proc.stdout.read(cl).decode("utf-8"))

            send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            recv()
            send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            r = recv()
            tools = [t["name"] for t in r["result"]["tools"]]
            assert "daily-gsv-multi-period" in tools, (
                f"MCP server tools/list 缺 daily-gsv-multi-period. "
                f"实际: {tools}. "
                f"根因: mcp_servers/fuqing_adhoc/_dispatch.py TOOL_DEFS 没加新 tool entry. "
                f"Sprint 183 Phase 4 QA fix 已修."
            )
            assert len(tools) == 11, (
                f"期望 11 个 tool (10 Sprint 182 + 1 Sprint 183), got {len(tools)}: {tools}"
            )
        finally:
            proc.stdin.close()
            proc.wait(timeout=5)
