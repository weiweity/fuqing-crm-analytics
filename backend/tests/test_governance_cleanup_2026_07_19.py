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
