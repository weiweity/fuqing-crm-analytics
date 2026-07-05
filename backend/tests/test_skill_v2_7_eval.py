"""Sprint 202+ Data Query v2.7 regression tests.

All cases stay deterministic: no DuckDB access, no uvicorn restart, and no MCP
stdio process. The goal is to lock the order_ids contract and the SKILL.md
guidance that routes "30 指标 + order_ids" to two-year-overview.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path
from typing import Any

import pytest

from backend.routers import ad_hoc_query as ad_hoc_router
from backend.services.metrics import audience_summary as audience_summary_mod
from mcp_servers.fuqing_adhoc import _dispatch as mcp_dispatch
from scripts import adhoc_query_hitrate_monitor as hitrate_monitor
from scripts import session_start_check as session_check
from scripts.ad_hoc_queries import ask as ask_mod
from scripts.ad_hoc_queries import two_year_overview as two_year_mod
from scripts.ad_hoc_queries.registry import get


def _fake_summary(label: str = "全店GSV", yoy: float | None = 0.25) -> dict[str, Any]:
    return {
        "year_label": "2026",
        "comp_year_label": "2025",
        "indicators": [
            {
                "field": label,
                "values_by_year": {"2026": 100.0, "2025": 80.0},
                "yoy": yoy,
            }
        ],
    }


def _skill_text() -> str:
    skill_path = Path.home() / ".claude" / "skills" / "ad-hoc-query" / "SKILL.md"
    if not skill_path.exists():
        pytest.skip(f"L4.35 SKILL.md source path not found: {skill_path}")
    return skill_path.read_text(encoding="utf-8")


class TestOrderIdsTwoYearOverview:
    """order_ids must pass from every two-year-overview entry to the service."""

    def test_service_signature_has_order_ids(self) -> None:
        sig = inspect.signature(audience_summary_mod.calculate_audience_summary)
        assert "order_ids" in sig.parameters

    def test_build_summary_passes_order_ids_to_service(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}

        def fake_calculate(**kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            return _fake_summary()

        monkeypatch.setattr(two_year_mod, "calculate_audience_summary", fake_calculate)
        monkeypatch.setattr(two_year_mod.AudienceSummaryResponse, "model_validate", lambda result: result)
        result = two_year_mod._build_summary(
            year=2026,
            start="2026-01-01",
            end="2026-06-30",
            order_ids=["ORDER001", "ORDER002"],
        )
        assert result["indicators"][0]["field"] == "全店GSV"
        assert captured["order_ids"] == ["ORDER001", "ORDER002"]

    def test_run_two_year_overview_accepts_order_ids(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}

        def fake_build(*args: Any, **kwargs: Any) -> dict[str, Any]:
            del args
            captured.update(kwargs)
            return _fake_summary()

        monkeypatch.setattr(two_year_mod, "_build_summary", fake_build)
        rows = two_year_mod.run_two_year_overview(
            start="2026-01-01",
            end="2026-06-30",
            order_ids=["ORDER001"],
        )
        assert rows[0][0] == "all_gsv"
        assert captured["order_ids"] == ["ORDER001"]

    def test_query_spec_declares_order_ids_nargs(self) -> None:
        spec = get("two-year-overview")
        order_arg = next(arg for arg in spec.args if "--order-ids" in arg["flags"])
        assert order_arg["nargs"] == "+"
        assert order_arg["default"] is None

    def test_http_request_passes_order_ids(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}

        def fake_run(**kwargs: Any) -> list[list[Any]]:
            captured.update(kwargs)
            return [["all_gsv", "全店GSV", 100.0, 80.0, 0.25, "%"]]

        monkeypatch.setattr(two_year_mod, "run_two_year_overview", fake_run)
        response = ad_hoc_router.post_two_year_overview(
            ad_hoc_router.TwoYearOverviewRequest(
                year=2026,
                start="2026-01-01",
                end="2026-06-30",
                order_ids=["ORDER001", "ORDER002"],
            )
        )
        assert response.row_count == 1
        assert captured["order_ids"] == ["ORDER001", "ORDER002"]


class TestBackcastFormulaUnit:
    """YOY unit output stays field-driven instead of formula hardcoding."""

    def test_ratio_metrics_emit_pp_unit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(two_year_mod, "_build_summary", lambda *a, **kw: _fake_summary("老客GSV占比"))
        assert two_year_mod.run_two_year_overview(start="2026-01-01", end="2026-06-30")[0][-1] == "pp"

    def test_absolute_metrics_emit_percent_unit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(two_year_mod, "_build_summary", lambda *a, **kw: _fake_summary("全店GSV"))
        assert two_year_mod.run_two_year_overview(start="2026-01-01", end="2026-06-30")[0][-1] == "%"

    def test_member_share_emit_pp_unit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(two_year_mod, "_build_summary", lambda *a, **kw: _fake_summary("会员渗透率"))
        assert two_year_mod.run_two_year_overview(start="2026-01-01", end="2026-06-30")[0][-1] == "pp"

    def test_unknown_label_defaults_to_all_prefix_percent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(two_year_mod, "_build_summary", lambda *a, **kw: _fake_summary("自定义指标"))
        row = two_year_mod.run_two_year_overview(start="2026-01-01", end="2026-06-30")[0]
        assert row[0] == "all_自定义指标"
        assert row[-1] == "%"

    def test_outlier_yoy_is_clamped_to_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(two_year_mod, "_build_summary", lambda *a, **kw: _fake_summary("全店GSV", yoy=1_000_001))
        assert two_year_mod.run_two_year_overview(start="2026-01-01", end="2026-06-30")[0][4] is None


class TestHitRateThreshold95:
    """R8 monitor and MCP registry must reflect the 95% hit-rate bar."""

    def test_threshold_is_95_percent(self) -> None:
        assert hitrate_monitor.HITRATE_THRESHOLD == 0.95

    def test_threshold_is_fraction_not_integer(self) -> None:
        assert 0 < hitrate_monitor.HITRATE_THRESHOLD <= 1

    def test_expected_tool_count_stays_14(self) -> None:
        # Sprint 198 治本 14 tool, Sprint 203 R5 加 4 件 → 18 (top_n 月/季/年 axis 扩算 modify 不算新 tool)
        # 跟 L4.20 SSOT 反漂移 1:1 stable: 动态读 EXPECTED_TOOL_COUNT, 不 hardcode
        assert hitrate_monitor.EXPECTED_TOOL_COUNT >= 14, (
            f"Sprint 198+ 治本至少 14 tool, got {hitrate_monitor.EXPECTED_TOOL_COUNT}"
        )

    def test_mcp_tool_count_matches_monitor_contract(self) -> None:
        # 跟 L4.20 SSOT 反漂移 1:1 stable: MCP TOOL_DEFS 必须 == EXPECTED_TOOL_COUNT (动态)
        assert len(mcp_dispatch.TOOL_DEFS) == hitrate_monitor.EXPECTED_TOOL_COUNT, (
            f"MCP TOOL_DEFS ({len(mcp_dispatch.TOOL_DEFS)}) != EXPECTED_TOOL_COUNT ({hitrate_monitor.EXPECTED_TOOL_COUNT})"
        )

    def test_monitor_output_uses_threshold_percent(self) -> None:
        source = inspect.getsource(hitrate_monitor)
        assert "HITRATE_THRESHOLD * 100" in source


class TestL4_35SymlinkVerify:
    """SessionStart symlink verification supports realpath + mode 120000 checks."""

    def _prepare_home(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        *,
        relative_link: bool = False,
        copied_file: bool = False,
        wrong_target: bool = False,
    ) -> tuple[Path, Path]:
        monkeypatch.setattr(session_check.Path, "home", lambda: tmp_path)
        claude_dir = tmp_path / ".claude" / "skills" / "ad-hoc-query"
        wb_dir = tmp_path / ".workbuddy" / "skills" / "ad-hoc-query"
        claude_dir.mkdir(parents=True)
        wb_dir.mkdir(parents=True)
        claude_skill = claude_dir / "SKILL.md"
        wb_skill = wb_dir / "SKILL.md"
        claude_skill.write_text("skill source\n", encoding="utf-8")
        if copied_file:
            wb_skill.write_text("skill source\n", encoding="utf-8")
        elif wrong_target:
            other = tmp_path / "other.md"
            other.write_text("other source\n", encoding="utf-8")
            wb_skill.symlink_to(other)
        elif relative_link:
            wb_skill.symlink_to(os.path.relpath(claude_skill, wb_dir))
        else:
            wb_skill.symlink_to(claude_skill)
        return claude_skill, wb_skill

    def test_absolute_symlink_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        self._prepare_home(tmp_path, monkeypatch)
        session_check._verify_skill_symlinks()
        assert "1 OK / 0 drift" in capsys.readouterr().out

    def test_relative_symlink_ok_via_realpath(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        self._prepare_home(tmp_path, monkeypatch, relative_link=True)
        session_check._verify_skill_symlinks()
        assert "1 OK / 0 drift" in capsys.readouterr().out

    def test_regular_file_is_drift(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        self._prepare_home(tmp_path, monkeypatch, copied_file=True)
        session_check._verify_skill_symlinks()
        assert "mode 0o100000 不是 0o120000" in capsys.readouterr().out

    def test_wrong_realpath_is_drift(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        self._prepare_home(tmp_path, monkeypatch, wrong_target=True)
        session_check._verify_skill_symlinks()
        assert "realpath=" in capsys.readouterr().out

    def test_workbuddy_only_skill_is_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        monkeypatch.setattr(session_check.Path, "home", lambda: tmp_path)
        wb_dir = tmp_path / ".workbuddy" / "skills" / "workbuddy-only"
        wb_dir.mkdir(parents=True)
        (wb_dir / "SKILL.md").write_text("solo\n", encoding="utf-8")
        (tmp_path / ".claude" / "skills").mkdir(parents=True)
        session_check._verify_skill_symlinks()
        assert "L4.35 skill symlink" not in capsys.readouterr().out


class TestSkillV27LLMEval:
    """SKILL.md v2.7 guidance and ask routing must hit two-year-overview."""

    def test_skill_title_bumped_to_v27(self) -> None:
        assert "WorkBuddy MCP 版, v2.7" in _skill_text()

    def test_skill_decision_tree_mentions_order_ids(self) -> None:
        text = _skill_text()
        assert "30 指标 + order_ids/订单号清单" in text
        assert "必用 `two_year_overview`" in text

    def test_skill_fast_table_has_order_ids_row(self) -> None:
        assert "two_year_overview(year, start, end, order_ids=...)" in _skill_text()

    def test_skill_synonym_table_mentions_matched_order_set(self) -> None:
        text = _skill_text()
        assert "matched order set" in text
        assert "5000+ 自动走 DuckDB temp table" in text

    def test_ask_routes_order_id_30_metrics_to_two_year(self) -> None:
        command, params = ask_mod.route_ask("30 指标 + order_ids 清单 ORDER001 ORDER002")
        assert command == "two-year-overview"
        assert params["order_ids"] == ["ORDER001", "ORDER002"]
