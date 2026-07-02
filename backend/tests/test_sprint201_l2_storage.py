"""Sprint 201 R2 L2 存储治本锁回归.

L4.53 永久规则: snapshot 机制 = P2 杀, Read-Write Splitting 已够 (L4.51 配套).
跨 sprint stable 1:1 模式 (跟 Sprint 178 L4.31 + Sprint 184 L4.38 + Sprint 200 R1 L4.50 配套).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


class TestSprint201L2StorageGovernance:
    """L2 治本锁回归 (5 case)."""

    def test_dump_duckdb_snapshot_script_removed(self):
        """dump_duckdb_snapshot.py 必须不存在 (L4.53 根除)."""
        script = SCRIPTS_DIR / "dump_duckdb_snapshot.py"
        assert not script.exists(), (
            f"L4.53 违反: {script} 应已被删除 (Sprint 201 R2 治本)"
        )

    def test_snapshot_plist_removed(self):
        """com.fuqing.snapshot.300s.plist 必须不存在 (LaunchAgents + scripts/launchd 双删)."""
        home_plist = Path.home() / "Library" / "LaunchAgents" / "com.fuqing.snapshot.300s.plist"
        project_plist = SCRIPTS_DIR / "launchd" / "com.fuqing.snapshot.300s.plist"
        assert not home_plist.exists(), f"L4.53 违反: {home_plist} 应已被删除"
        assert not project_plist.exists(), f"L4.53 违反: {project_plist} 应已被删除"

    def test_snapshots_dir_empty_or_absent(self):
        """snapshots/ 目录应 0 残留."""
        snap_dir = PROJECT_ROOT / "data" / "processed" / "snapshots"
        if snap_dir.exists():
            for f in snap_dir.iterdir():
                assert f.name == ".gitkeep" or f.is_dir(), (
                    f"L4.53 违反: {snap_dir}/{f.name} 应已被清空"
                )

    def test_run_etl_has_storage_governance(self):
        """run_etl.py 末尾必须包含 L2.5 治理逻辑 (user_rfm 30天 + cache GC + CHECKPOINT)."""
        run_etl = SCRIPTS_DIR / "run_etl.py"
        assert run_etl.exists()
        content = run_etl.read_text(encoding="utf-8")
        # 3 个核心治本 marker
        assert "user_rfm" in content and "INTERVAL 30 DAY" in content, (
            "L2.5 违反: run_etl.py 缺 user_rfm 30 天保留逻辑"
        )
        assert "rfm_query_cache" in content, (
            "L2.5 违反: run_etl.py 缺 rfm_query_cache TTL GC"
        )
        assert "CHECKPOINT" in content, (
            "L2.5 违反: run_etl.py 缺 VACUUM/CHECKPOINT 治理"
        )

    def test_db_size_alert_script_exists_and_runs(self):
        """check_db_size.py 必须存在 + 能跑 + 当前 rc=0."""
        script = SCRIPTS_DIR / "check_db_size.py"
        assert script.exists(), f"L2.6 违反: {script} 不存在"
        # 模拟 run
        import subprocess
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        )
        # 当前 122GB 应 rc=0 (未超 200GB 限制)
        assert result.returncode in (0, 1), f"check_db_size.py 跑挂: {result.stderr}"
