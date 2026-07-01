"""Sprint 183 /ad-hoc-query v2.2 regression tests.

L4.36 锁回归, 防 WorkBuddy self-review 暴露的 4 个根因复发:
1. 不知 SKILL.md v2.2 顶部 "执行路径强制" 段
2. 误把 3 个 CLI 子命令当能力全集
3. 误判 DuckDB 锁让用户停 uvicorn
4. 写临时脚本重复造轮子
"""
from __future__ import annotations

from pathlib import Path


SKILL_MD_PATH = Path.home() / ".claude/skills/ad-hoc-query/SKILL.md"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLAUDE_MD_PATH = PROJECT_ROOT / "CLAUDE.md"


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

    def test_claude_md_l4_36_added(self):
        """CLAUDE.md L4.36 永久规则必须存在且在 L4.35 后."""
        assert CLAUDE_MD_PATH.exists(), f"CLAUDE.md 不存在: {CLAUDE_MD_PATH}"
        content = CLAUDE_MD_PATH.read_text(encoding="utf-8")
        assert "L4.36" in content, "CLAUDE.md 必须含 L4.36 永久规则"
        l4_35_pos = content.find("L4.35")
        l4_36_pos = content.find("L4.36")
        assert l4_35_pos > 0, "CLAUDE.md 缺 L4.35"
        assert l4_36_pos > l4_35_pos, "L4.36 必须紧跟 L4.35 之后"


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
        """daily_gsv_multi_period 必须注册到 QUERIES dict."""
        from scripts.ad_hoc_queries import daily_gsv_multi_period  # noqa: F401
        from scripts.ad_hoc_queries.registry import QUERIES

        assert "daily_gsv_multi_period" in QUERIES, (
            "QUERIES dict 缺 daily_gsv_multi_period 注册"
        )
