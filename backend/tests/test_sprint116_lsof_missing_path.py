"""Sprint 116 真 refactor sprint: lsof FileNotFoundError 路径 coverage (修 #D10).

Sprint 112 抽 _prune_with_safety 后, lsof subprocess.run 在 CI Linux runner 上
没装 lsof → FileNotFoundError → 走 'pass 保守放行' 跳过 lsof check.
实际生产 macOS launchd 有 lsof, 但 CI 跑 5 safety check 而不是 8.

Sprint 116 加 test 验证 _prune_with_safety 在 lsof 不可用时 (FileNotFoundError)
仍能删 candidate 文件, 验证保守放行行为 + 跟 Sprint 95+96+96.5 e2e CI runner 教训一致.

Branch: fix/sprint116-fix-d7-d10-refactor-defer
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestSprint116LsofMissingPath:
    """Sprint 116 修 #D10: lsof FileNotFoundError 路径 coverage."""

    def _make_zst(self, path: Path, days_old: int) -> Path:
        path.write_bytes(b"\x28\xb5\x2f\xfd" + b"\x00" * 100)
        old_time = time.time() - days_old * 86400
        os.utime(path, (old_time, old_time))
        return path

    def test_prune_proceeds_when_lsof_missing(self, tmp_path, monkeypatch):
        """Case 1: lsof FileNotFoundError 保守放行 (修 #D10).

        验证: CI Linux runner 没装 lsof, _prune_with_safety 走 FileNotFoundError catch
        → 'pass' 跳过 lsof check → 仍能删 candidate 文件 (5 safety check 实际生效).
        """
        from scripts.etl.common import _prune_lib

        # 造 1 份超 retention .duckdb.zst (10d > 2d cutoff)
        zst = self._make_zst(tmp_path / "a.duckdb.zst", days_old=10)

        # Mock subprocess.run raise FileNotFoundError (模拟 lsof 不可用)
        def mock_lsof_missing(*args, **kwargs):
            raise FileNotFoundError("lsof not installed (Sprint 116 test mock)")

        # Patch _prune_lib 的 subprocess.run (lsof 调用)
        monkeypatch.setattr(_prune_lib.subprocess, "run", mock_lsof_missing)

        deleted, deleted_names = _prune_lib._prune_with_safety(
            backup_dir=tmp_path,
            glob_patterns=("*.duckdb.zst",),
            retention_days=2,
            keep_min=0,  # 全候选, 强制触发 lsof check
            log_fn=lambda msg: None,
        )

        # 验证: lsof missing 时保守放行应删 candidate
        assert deleted == 1, f"lsof missing 时保守放行应删 1 个 candidate, 实际 {deleted}"
        assert deleted_names == ["a.duckdb.zst"], f"deleted_names 应是 ['a.duckdb.zst'], 实际 {deleted_names}"
        assert not zst.exists(), "zst 应被删 (lsof missing 走保守放行)"

    def test_prune_per_extension_magic_check_parquet(self, tmp_path):
        """Case 2: per-extension magic check (修 #D7) — .parquet 文件 PAR1 magic 通过.

        验证: 真 PAR1 magic 的 .parquet 文件不被 magic check skip.
        """
        from scripts.etl.common import _prune_lib

        # 造 1 份真 PAR1 magic 的 .parquet 文件
        parquet = tmp_path / "a.parquet"
        parquet.write_bytes(b"PAR1" + b"\x00" * 100)  # 真 parquet magic
        old_time = time.time() - 10 * 86400
        os.utime(parquet, (old_time, old_time))

        deleted, deleted_names = _prune_lib._prune_with_safety(
            backup_dir=tmp_path,
            glob_patterns=("*.parquet",),
            retention_days=2,
            keep_min=0,
            log_fn=lambda msg: None,
        )

        # 验证: PAR1 magic 通过 → 文件被删
        assert deleted == 1, f"PAR1 magic 通过应删 1 个, 实际 {deleted}"
        assert deleted_names == ["a.parquet"], f"deleted_names 应是 ['a.parquet'], 实际 {deleted_names}"

    def test_prune_per_extension_magic_check_skip_non_matching(self, tmp_path):
        """Case 3: per-extension magic check (修 #D7) — 非匹配 magic 被 skip.

        验证: 误 glob 到 .txt 改名为 .parquet 但 magic 不匹配 → magic check skip, 不误删.
        """
        from scripts.etl.common import _prune_lib

        # 造 1 份 .parquet 后缀但 magic 不是 PAR1 (模拟误 glob 到非 parquet)
        fake = tmp_path / "a.parquet"
        fake.write_bytes(b"XXXX" + b"\x00" * 100)  # magic 不匹配
        old_time = time.time() - 10 * 86400
        os.utime(fake, (old_time, old_time))

        deleted, deleted_names = _prune_lib._prune_with_safety(
            backup_dir=tmp_path,
            glob_patterns=("*.parquet",),
            retention_days=2,
            keep_min=0,
            log_fn=lambda msg: None,
        )

        # 验证: magic 不匹配 → skip → 文件保留
        assert deleted == 0, f"magic 不匹配应 skip, 实际 deleted={deleted}"
        assert deleted_names == [], f"deleted_names 应是 [], 实际 {deleted_names}"
        assert fake.exists(), "非匹配 magic 文件应保留 (magic check skip)"

    def test_prune_per_extension_magic_check_duckdb(self, tmp_path):
        """Case 4: per-extension magic check (修 #D7) — .duckdb 文件 DUCK magic 通过.

        验证: 真 DUCK magic (offset 8) 的 .duckdb 文件不被 magic check skip.
        """
        from scripts.etl.common import _prune_lib

        # 造 1 份 .duckdb 文件, magic 在 offset 8 = 'DUCK' (DuckDB v0.9+ standard)
        duckdb_file = tmp_path / "a.duckdb"
        # 12 bytes random + 'DUCK' (4 bytes at offset 8) + 12 bytes padding
        header = b"\x00" * 8 + b"DUCK" + b"\x00" * 12
        duckdb_file.write_bytes(header + b"\x00" * 100)
        old_time = time.time() - 10 * 86400
        os.utime(duckdb_file, (old_time, old_time))

        deleted, deleted_names = _prune_lib._prune_with_safety(
            backup_dir=tmp_path,
            glob_patterns=("*.duckdb",),
            retention_days=2,
            keep_min=0,
            log_fn=lambda msg: None,
        )

        # 验证: DUCK magic 通过 → 文件被删
        assert deleted == 1, f"DUCK magic 通过应删 1 个, 实际 {deleted}"
        assert deleted_names == ["a.duckdb"], f"deleted_names 应是 ['a.duckdb'], 实际 {deleted_names}"

    def test_prune_unknown_suffix_trust_caller(self, tmp_path):
        """Case 5: per-extension magic check (修 #D7) — 未知后缀 trust caller.

        验证: 没在 MAGIC_CHECKS table 的后缀走 default (trust caller), 不做 magic check.
        (e.g. .txt 文件, 没有 magic check 要求, caller 负责 glob 准确).
        """
        from scripts.etl.common import _prune_lib

        # 造 1 份 .txt 文件 (不在 MAGIC_CHECKS)
        txt = tmp_path / "a.txt"
        txt.write_bytes(b"random content, no magic check")
        old_time = time.time() - 10 * 86400
        os.utime(txt, (old_time, old_time))

        deleted, deleted_names = _prune_lib._prune_with_safety(
            backup_dir=tmp_path,
            glob_patterns=("*.txt",),
            retention_days=2,
            keep_min=0,
            log_fn=lambda msg: None,
        )

        # 验证: 未知后缀 trust caller → 文件被删
        assert deleted == 1, f"未知后缀 trust caller 应删 1 个, 实际 {deleted}"
        assert deleted_names == ["a.txt"], f"deleted_names 应是 ['a.txt'], 实际 {deleted_names}"

    def test_prune_returns_deleted_names_for_observability(self, tmp_path):
        """Case 6: Tuple[int, list[str]] 返值 (修 #D9) — deleted_names observability.

        验证: _prune_with_safety 返 (deleted_count, deleted_names) tuple,
        callers 拼回 '| files: ...' observability 字段 (跟 Sprint 111 一致).
        """
        from scripts.etl.common import _prune_lib

        # 造 3 份超 retention .duckdb.zst (5d/7d/10d)
        # mtime 5d 前 是最近的 (最新), mtime 10d 前 是最老的.
        # sorted desc by mtime = [a (5d), b (7d), c (10d)].
        self._make_zst(tmp_path / "a.duckdb.zst", days_old=5)
        self._make_zst(tmp_path / "b.duckdb.zst", days_old=7)
        self._make_zst(tmp_path / "c.duckdb.zst", days_old=10)

        deleted, deleted_names = _prune_lib._prune_with_safety(
            backup_dir=tmp_path,
            glob_patterns=("*.duckdb.zst",),
            retention_days=2,
            keep_min=0,
            log_fn=lambda msg: None,
        )

        # 验证: deleted count + names 完整
        assert deleted == 3, f"期望删 3 个, 实际 {deleted}"
        assert len(deleted_names) == 3, f"deleted_names 应有 3 个, 实际 {len(deleted_names)}"
        # 按 mtime desc 顺序: a (5d 最新) → b (7d) → c (10d 最老)
        assert deleted_names == ["a.duckdb.zst", "b.duckdb.zst", "c.duckdb.zst"], (
            f"deleted_names 顺序错 (期望 mtime desc): {deleted_names}"
        )

    def test_magic_checks_table_is_ssot(self):
        """Case 7 (Sprint 116 /review maintainability + Sprint 3 P1-3 教训):
        MAGIC_CHECKS table 内容恒定 SSOT check.

        验证: MAGIC_CHECKS keys 跟 magic bytes 跟 offset 都跟设计一致,
        防止后人加新 suffix 但忘了更新 SSOT 引起 silent failure.
        跟 L4.20 SSOT 反漂移永久规则 + Sprint 90 L4.7 ground-truth-lint 防回归 模式一致.
        """
        from scripts.etl.common import _prune_lib

        # 3 个 suffix 必须都在 (Sprint 116 抽 _prune_lib 时确定)
        assert set(_prune_lib.MAGIC_CHECKS.keys()) == {".parquet", ".duckdb", ".duckdb.zst"}, (
            f"MAGIC_CHECKS keys 应是 3 个 suffix, 实际 {list(_prune_lib.MAGIC_CHECKS.keys())}"
        )
        # magic bytes 跟 offset 验证 (Sprint 116 真治本 #D7)
        assert _prune_lib.MAGIC_CHECKS[".parquet"] == (b"PAR1", 0), (
            f".parquet magic 应是 (b'PAR1', 0), 实际 {_prune_lib.MAGIC_CHECKS['.parquet']}"
        )
        assert _prune_lib.MAGIC_CHECKS[".duckdb"] == (b"DUCK", 8), (
            f".duckdb magic 应是 (b'DUCK', 8), 实际 {_prune_lib.MAGIC_CHECKS['.duckdb']}"
        )
        assert _prune_lib.MAGIC_CHECKS[".duckdb.zst"] == (_prune_lib.ZSTD_MAGIC, 0), (
            f".duckdb.zst magic 应是 (ZSTD_MAGIC, 0), 实际 {_prune_lib.MAGIC_CHECKS['.duckdb.zst']}"
        )

    def test_retention_zero_deletes_all_above_keep_min(self, tmp_path):
        """Case 8 (Sprint 116 /review maintainability + Sprint 111 cap=0 风险):
        retention=0 边界 case — keep_min 守护 cap=0 误删全部.

        验证: retention_days=0 时, KEEP_MIN=1 守护最新 1 份,
        其他 > 0d 全部删 (Sprint 111 必修 4 闭环 cap=0 误删全部 风险).
        """
        from scripts.etl.common import _prune_lib

        # 造 3 份超 retention=0 (mtime 全部 > 0d → 都超 0d retention)
        # a.duckdb.zst 1d (最新, KEEP_MIN 守护内)
        # b.duckdb.zst 10d (超 retention=0 + 不在 KEEP_MIN 守护内 → 删)
        # c.duckdb.zst 100d (超 retention=0 + 不在 KEEP_MIN 守护内 → 删)
        self._make_zst(tmp_path / "a.duckdb.zst", days_old=1)
        self._make_zst(tmp_path / "b.duckdb.zst", days_old=10)
        self._make_zst(tmp_path / "c.duckdb.zst", days_old=100)

        deleted, deleted_names = _prune_lib._prune_with_safety(
            backup_dir=tmp_path,
            glob_patterns=("*.duckdb.zst",),
            retention_days=0,  # 极端边界: 0 天 retention (跟 Sprint 111 cap=0 风险对应)
            keep_min=1,  # KEEP_MIN=1 守护最新 1 份 (a.duckdb.zst)
            log_fn=lambda msg: None,
        )

        # 验证: KEEP_MIN=1 守护 a (1d 最新), 删 b + c (10d + 100d)
        assert deleted == 2, f"retention=0 + KEEP_MIN=1 应删 2 个 (b + c), 实际 {deleted}"
        assert sorted(deleted_names) == ["b.duckdb.zst", "c.duckdb.zst"], (
            f"deleted_names 应是 ['b.duckdb.zst', 'c.duckdb.zst'], 实际 {sorted(deleted_names)}"
        )
        assert (tmp_path / "a.duckdb.zst").exists(), "a.duckdb.zst (KEEP_MIN=1 守护) 应保留"

    def test_main_summary_includes_deleted_files_observability(self, tmp_path, monkeypatch):
        """Case 9 (Sprint 116 修 #D9 真测): cleanup_backups.py main() 拼 '| files: ...' observability.

        验证: cleanup_backups.py main() 调 _prune_lib._prune_with_safety 返 Tuple[int, list[str]]
        后, summary 拼回 '| files: {names}' observability 字段 (跟 Sprint 111 一致).
        风险: Sprint 116 改 main() summary 格式后, observability regression 静默 fail.
        """
        from scripts.etl import cleanup_backups

        # Mock LOCK_DIR + BACKUP_DIR + LOG_FILE
        monkeypatch.setattr(cleanup_backups, "LOCK_DIR", tmp_path / "lock")
        monkeypatch.setattr(cleanup_backups, "BACKUP_DIR", tmp_path / "backups")
        monkeypatch.setattr(cleanup_backups, "BACKUP_KEEP_MIN", 0)  # 全候选
        log_file = tmp_path / "cleanup.log"
        monkeypatch.setattr(cleanup_backups, "LOG_FILE", log_file)
        (tmp_path / "backups").mkdir()

        # 造 2 份超 retention=2 天 (RETENTION_DAYS=2 default)
        zst_a = self._make_zst(tmp_path / "backups" / "a.duckdb.zst", days_old=10)
        zst_b = self._make_zst(tmp_path / "backups" / "b.duckdb.zst", days_old=10)

        # 调 main() (会调 _prune_lib._prune_with_safety 返 Tuple[int, list[str]])
        exit_code = cleanup_backups.main()

        # 验证: exit 0 + 文件删 + log 含 '| files: ...' observability 字段
        assert exit_code == 0, f"期望 exit 0, 实际 {exit_code}"
        assert not zst_a.exists() and not zst_b.exists(), "2 份超 retention 文件应删"
        log_content = log_file.read_text()
        assert "| files:" in log_content, (
            f"期望 log 含 '| files: ...' observability 字段 (修 #D9), 实际: {log_content}"
        )
        assert "a.duckdb.zst" in log_content and "b.duckdb.zst" in log_content, (
            f"期望 log 含具体文件名 a.duckdb.zst + b.duckdb.zst, 实际: {log_content}"
        )
