"""Governance cleanup lock regression (2026-07-19).

Proves shipped layout: Admin Upload product surface gone; monitors under scripts/ops.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_admin_upload_product_files_removed() -> None:
    """Withdrawn product path must not exist as live modules."""
    assert not (REPO_ROOT / "backend" / "services" / "admin_upload.py").exists()
    assert not (REPO_ROOT / "backend" / "routers" / "admin.py").exists()
    assert not (REPO_ROOT / "frontend-vue3" / "src" / "views" / "AdminUploadView.vue").exists()
    assert not (REPO_ROOT / "frontend-vue3" / "e2e" / "admin-upload.spec.ts").exists()


def test_main_does_not_register_admin_router() -> None:
    main_src = (REPO_ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert "admin_router" not in main_src
    assert "include_router(admin_router)" not in main_src


def test_ops_monitors_exist_and_repo_root_resolves() -> None:
    ops = REPO_ROOT / "scripts" / "ops"
    for name in (
        "pre_existing_fail_monitor.py",
        "memory_size_monitor.py",
        "adhoc_query_hitrate_monitor.py",
        "clickhouse_poc_monitor.py",
        "check_db_size.py",
    ):
        path = ops / name
        assert path.is_file(), f"missing ops monitor: {name}"
        text = path.read_text(encoding="utf-8")
        assert "parents[2]" in text or "parent.parent.parent" in text, (
            f"{name} must resolve REPO_ROOT from scripts/ops/ (parents[2])"
        )


def test_launchd_plists_point_to_scripts_ops() -> None:
    launchd = REPO_ROOT / "scripts" / "launchd"
    plists = list(launchd.glob("com.fuqing.*monitor*.plist")) + list(
        launchd.glob("com.fuqing.db-size-alert*.plist")
    )
    assert plists, "expected monitor/db-size launchd plists"
    for pl in plists:
        body = pl.read_text(encoding="utf-8")
        assert "scripts/ops/" in body, f"{pl.name} must reference scripts/ops/"
        # no stale scripts/<monitor>.py at scripts root
        assert "scripts/pre_existing_fail_monitor.py" not in body
        assert "scripts/clickhouse_poc_monitor.py" not in body


def test_clickhouse_monitor_module_loads_from_ops() -> None:
    """Real import of shipped module path (not a reimplementation)."""
    path = REPO_ROOT / "scripts" / "ops" / "clickhouse_poc_monitor.py"
    spec = importlib.util.spec_from_file_location("clickhouse_poc_monitor_gov", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "REPO_ROOT")
    assert Path(mod.REPO_ROOT).resolve() == REPO_ROOT.resolve()


def test_tech_debt_has_no_vague_open_scripts_ops_or_admin_row() -> None:
    debt = (REPO_ROOT / "docs" / "TECH-DEBT.md").read_text(encoding="utf-8")
    assert "scripts/ops" in debt
    assert "Admin" in debt and ("撤回" in debt or "WITHDRAWN" in debt or "已闭环" in debt)
    # open section before closed must not treat scripts-ops as pending move
    if "## 本目标已闭环" in debt:
        open_section = debt.split("## 本目标已闭环")[0]
    else:
        open_section = debt
    assert "可归" not in open_section


def test_install_launchagents_script_exists_and_requires_ops_paths() -> None:
    """Shipped bootstrap must enforce scripts/ops/ before cp to LaunchAgents."""
    script = REPO_ROOT / "scripts" / "ops" / "install_launchagents.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "scripts/ops/" in text
    assert "LaunchAgents" in text
    assert "bootstrap" in text or "load" in text
    # must refuse plists that do not reference ops
    assert "does not reference scripts/ops" in text or "scripts/ops/" in text


def test_repo_launchd_plists_only_reference_ops_monitors() -> None:
    launchd = REPO_ROOT / "scripts" / "launchd"
    for name in (
        "com.fuqing.pre-existing-fail-monitor.weekly.plist",
        "com.fuqing.memory-size-monitor.weekly.plist",
        "com.fuqing.adhoc-hitrate-monitor.weekly.plist",
        "com.fuqing.clickhouse-poc-monitor.weekly.plist",
        "com.fuqing.db-size-alert.daily.plist",
    ):
        body = (launchd / name).read_text(encoding="utf-8")
        assert "scripts/ops/" in body, name
        # forbidden stale root paths
        assert "scripts/pre_existing_fail_monitor.py" not in body
        assert "scripts/clickhouse_poc_monitor.py" not in body
        assert "scripts/check_db_size.py" not in body


@pytest.mark.skipif(__import__("sys").platform != "darwin", reason="LaunchAgents is macOS-only")
def test_installed_launchagents_point_to_existing_ops_scripts() -> None:
    """Local-as-prod: installed agents must not point at deleted scripts/*.py paths."""
    import os
    from pathlib import Path as P

    home = P.home() / "Library" / "LaunchAgents"
    names = [
        "com.fuqing.pre-existing-fail-monitor.weekly.plist",
        "com.fuqing.memory-size-monitor.weekly.plist",
        "com.fuqing.adhoc-hitrate-monitor.weekly.plist",
        "com.fuqing.clickhouse-poc-monitor.weekly.plist",
        "com.fuqing.db-size-alert.daily.plist",
    ]
    missing_agents = [n for n in names if not (home / n).is_file()]
    if missing_agents:
        pytest.skip(f"LaunchAgents not installed: {missing_agents}")
    for name in names:
        pl = home / name
        # Parse ProgramArguments:1 via plutil - extract path containing scripts/ops
        body = pl.read_text(encoding="utf-8", errors="replace")
        assert "scripts/ops/" in body, f"{name} still missing scripts/ops/"
        # resolve script path
        for line in body.splitlines():
            if "scripts/ops/" in line and ".py" in line:
                # strip XML
                start = line.find("/")
                end = line.rfind(".py") + 3
                if start >= 0 and end > start:
                    path = P(line[start:end])
                    assert path.is_file(), f"{name} target missing: {path}"
                    break
        else:
            pytest.fail(f"{name}: no scripts/ops/*.py path found in plist body")


def test_l4_rules_do_not_document_deleted_scripts_root_monitors() -> None:
    import re

    rules = (REPO_ROOT / "docs" / "rules" / "L4-permanent-rules.md").read_text(encoding="utf-8")
    assert "scripts/ops/pre_existing_fail_monitor.py" in rules
    assert "scripts/ops/check_db_size.py" in rules
    # living paths must not omit ops/ (negative lookbehind)
    for name in (
        "pre_existing_fail_monitor.py",
        "memory_size_monitor.py",
        "adhoc_query_hitrate_monitor.py",
        "clickhouse_poc_monitor.py",
        "check_db_size.py",
    ):
        stale = re.findall(rf"(?<!ops/)scripts/{re.escape(name)}", rules)
        assert not stale, f"stale non-ops path for {name}: {stale}"
