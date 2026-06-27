"""Sprint 111 真业务 sprint: retention 7 → 2 天 + KEEP_MIN 1 → 2 regression test.

覆盖 2 个核心场景:
  1. FQ_BACKUP_RETENTION_DAYS=2 env override 生效 (默认从 7 改成 2)
  2. BACKUP_KEEP_MIN=2 守护: 即便全部 > 2d 也保留最新 2 份 (防 cap=0 误删全部)

不依赖真实 launchd / DuckDB / lark (mock 隔离), 复用 Sprint 62.5 B1 4 case 模式.

Branch: fix/sprint111-retention-2day-cleanup
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestSprint111Retention2Day:
    """Sprint 111 真业务 sprint: retention 7 → 2 天 + BACKUP_KEEP_MIN 1 → 2."""

    def _make_zst(self, path: Path, days_old: int) -> Path:
        path.write_bytes(b"\x28\xb5\x2f\xfd" + b"\x00" * 100)
        old_time = time.time() - days_old * 86400
        os.utime(path, (old_time, old_time))
        return path

    def test_retention_days_env_override_2(self, tmp_path, monkeypatch):
        """Case 1: FQ_BACKUP_RETENTION_DAYS=2 env override 生效.

        验证: backup_duckdb.BACKUP_RETENTION_DAYS 默认值从 7 改成 2,
        跟 user 拍板 "我项目小, 2 天滚动清理" 一致.
        """
        from scripts.etl import backup_duckdb

        monkeypatch.setattr(backup_duckdb, "BACKUP_DIR", tmp_path)

        # 造 3 份: 1 天 / 3 天 / 5 天
        # KEEP_MIN=2 守护: sorted desc = [new(1d), mid(3d), old(5d)]
        # slice[KEEP_MIN:] = [old(5d)]; old mtime < cutoff(2d) → 删 1 个
        new = self._make_zst(tmp_path / "fuqing_crm_2026-06-24_0330.duckdb.zst", days_old=1)
        mid = self._make_zst(tmp_path / "fuqing_crm_2026-06-22_0330.duckdb.zst", days_old=3)
        old = self._make_zst(tmp_path / "fuqing_crm_2026-06-20_0330.duckdb.zst", days_old=5)

        deleted = backup_duckdb._prune_old_backups()

        assert deleted == 1, f"期望删 1 个 (> 2d + 不在 KEEP_MIN 守护内), 实际 {deleted}"
        assert new.exists(), "新 zst (1d) 不应被删"
        assert mid.exists(), "次新 zst (3d, 在 KEEP_MIN 守护内) 不应被删"
        assert not old.exists(), "老 zst (5d) 应被删"

    def test_keep_min_2_protects_against_cap_zero(self, tmp_path, monkeypatch):
        """Case 2: KEEP_MIN=2 守护 — 即便全部 > retention 也保留最新 2 份.

        修复前 (KEEP_MIN=1 + RETENTION=7): 万一 retention 误设 0, 只留 1 份,
        万一该份被破坏, 完全无备份.
        修复后 (KEEP_MIN=2 + RETENTION=2): 即便 retention=0 误设, 仍保留最新 2 份.
        """
        from scripts.etl import backup_duckdb

        monkeypatch.setattr(backup_duckdb, "BACKUP_DIR", tmp_path)
        monkeypatch.setattr(backup_duckdb, "BACKUP_RETENTION_DAYS", 2)
        monkeypatch.setattr(backup_duckdb, "BACKUP_KEEP_MIN", 2)

        # 造 3 份全部 > 2d (10d/8d/5d) → 应留最新 2 份 (5d + 8d), 删 10d
        oldest = self._make_zst(tmp_path / "fuqing_crm_2026-06-15_0330.duckdb.zst", days_old=10)
        middle = self._make_zst(tmp_path / "fuqing_crm_2026-06-17_0330.duckdb.zst", days_old=8)
        newest = self._make_zst(tmp_path / "fuqing_crm_2026-06-20_0330.duckdb.zst", days_old=5)

        deleted = backup_duckdb._prune_old_backups()

        assert deleted == 1, f"期望删 1 个 (留最新 2 份), 实际 {deleted}"
        assert not oldest.exists(), "最老 (10d) 应被删"
        assert middle.exists(), "次新 (8d, KEEP_MIN 守护内) 应保留"
        assert newest.exists(), "最新 (5d, KEEP_MIN 守护内) 应保留"

        remaining = sorted(tmp_path.glob("*.duckdb.zst"), key=lambda p: p.stat().st_mtime, reverse=True)
        assert len(remaining) == 2, f"期望保留 2 份, 实际 {len(remaining)}"
        assert "06-20" in remaining[0].name, f"最新应是 06-20, 实际 {remaining[0].name}"
        assert "06-17" in remaining[1].name, f"次新应是 06-17, 实际 {remaining[1].name}"
