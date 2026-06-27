"""Sprint 117 真 refactor sprint: rename _prune_lib → prune_lib (修 #D11) +
4 项真治本 (#D11+#D12+#D13+#D14).

Sprint 116 /review maintainability 反馈 4 项 defer:
- #D11: '_' 前缀违反 PEP 8 private 约定
- #D12: _matches_magic 返 False 时 log 丢 offset + actual magic info
- #D13: case-sensitive glob mismatch (macOS APFS case-preserving vs Linux HFS+ case-insensitive)
- #D14: longest-wins 依赖 dict iteration order (implicit contract)

Sprint 117 修:
- #D11: rename _prune_lib.py → prune_lib.py (PEP 8 public, 跨模块访问合法)
- #D12: _matches_magic 改返 tuple[bool, str] (reason), caller log 完整信息
- #D13: case-insensitive 匹配 (Path(p).suffix.lower())
- #D14: 显式 sort longest first (sorted(MAGIC_CHECKS, key=len, reverse=True))

Branch: fix/sprint117-fix-d11-d14-prune-lib-refactor
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestSprint117PruneLibRefactor:
    """Sprint 117 修 #D11-#D14: prune_lib 真治本 4 项."""

    def _make_duckdb_zst(self, path: Path, days_old: int) -> Path:
        """造 .duckdb.zst 文件 + 设 mtime."""
        path.write_bytes(b"\x28\xb5\x2f\xfd" + b"\x00" * 100)
        old_time = time.time() - days_old * 86400
        os.utime(path, (old_time, old_time))
        return path

    def test_prune_lib_is_public_no_underscore_prefix(self):
        """Case 1 (Sprint 117 修 #D11): prune_lib.py '_' 前缀消失 (PEP 8 public).

        验证: scripts/etl/common/prune_lib.py 文件存在 (无 '_' 前缀),
        跟 scripts/etl/common/lark.py 命名风格一致 (public module).
        老的 _prune_lib.py 已删 (git rm, Sprint 117 真治本).
        """
        from scripts.etl.common import prune_lib

        # 1. module 存在, 无 '_' 前缀
        assert prune_lib.__name__ == "scripts.etl.common.prune_lib", (
            f"module name 应是 scripts.etl.common.prune_lib, 实际 {prune_lib.__name__}"
        )
        # 2. _prune_with_safety 跟 _matches_magic 仍是 private (Sprint 117 不重命名, 跟 callers 期望一致)
        assert hasattr(prune_lib, "_prune_with_safety"), "_prune_with_safety 应存在"
        assert hasattr(prune_lib, "_matches_magic"), "_matches_magic 应存在"
        # 3. 旧 _prune_lib module 不应再存在
        try:
            from scripts.etl.common import _prune_lib  # noqa: F401
            assert False, "_prune_lib 不应再存在 (Sprint 117 rename 去 _)"
        except ImportError:
            pass  # 期望: ImportError, _prune_lib.py 已删

    def test_matches_magic_returns_tuple_with_reason(self, tmp_path):
        """Case 2 (Sprint 117 修 #D12): _matches_magic 改返 tuple[bool, str].

        验证: _matches_magic 返 (ok: bool, reason: str).
        reason 含 offset + actual magic info (Sprint 60+ 留尾 #D7 修法初心).
        Caller _prune_with_safety log 完整 reason (vs Sprint 116 log 'magic check failed' 丢 info).
        """
        from scripts.etl.common import prune_lib

        # 1. magic mismatch → (False, "magic mismatch for .parquet: expected b'PAR1'@0, got b'XXXX'@0")
        fake = tmp_path / "a.parquet"
        fake.write_bytes(b"XXXX" + b"\x00" * 100)
        old_time = time.time() - 10 * 86400
        os.utime(fake, (old_time, old_time))

        ok, reason = prune_lib._matches_magic(fake)
        assert ok is False, f"magic mismatch 应返 False, 实际 {ok}"
        assert "magic mismatch" in reason, f"reason 应含 'magic mismatch', 实际 {reason!r}"
        assert ".parquet" in reason, f"reason 应含 suffix, 实际 {reason!r}"
        assert "expected" in reason and "got" in reason, (
            f"reason 应含 'expected' + 'got' 完整对比, 实际 {reason!r}"
        )
        assert "@0" in reason, f"reason 应含 offset @0, 实际 {reason!r}"

        # 2. magic 匹配 → (True, "magic OK (.parquet: b'PAR1'@0)")
        real = tmp_path / "b.parquet"
        real.write_bytes(b"PAR1" + b"\x00" * 100)
        old_time = time.time() - 10 * 86400
        os.utime(real, (old_time, old_time))
        ok2, reason2 = prune_lib._matches_magic(real)
        assert ok2 is True, f"PAR1 magic 应返 True, 实际 {ok2}"
        assert "magic OK" in reason2 and ".parquet" in reason2, (
            f"reason 应含 'magic OK' + suffix, 实际 {reason2!r}"
        )

        # 3. 未知后缀 → (True, "trust caller (unknown suffix '.txt')")
        txt = tmp_path / "c.txt"
        txt.write_bytes(b"random content")
        ok3, reason3 = prune_lib._matches_magic(txt)
        assert ok3 is True, f"未知后缀 trust caller 应返 True, 实际 {ok3}"
        assert "trust caller" in reason3 and ".txt" in reason3, (
            f"reason 应含 'trust caller' + suffix, 实际 {reason3!r}"
        )

    def test_matches_magic_case_insensitive(self, tmp_path):
        """Case 3 (Sprint 117 修 #D13): case-insensitive 匹配.

        验证: .PARQUET / .Parquet / .PaRqUeT 大小写混用都跟 .parquet PAR1 magic 匹配.
        修 macOS APFS case-preserving vs Linux HFS+ default case-insensitive 行为不一致 bug.
        """
        from scripts.etl.common import prune_lib

        # 造 .PARQUET (大写) + PAR1 magic
        parquet_upper = tmp_path / "a.PARQUET"
        parquet_upper.write_bytes(b"PAR1" + b"\x00" * 100)
        ok, reason = prune_lib._matches_magic(parquet_upper)
        assert ok is True, (
            f".PARQUET + PAR1 magic 应 case-insensitive 匹配, 实际 ok={ok} reason={reason!r}"
        )
        assert "magic OK" in reason, f"reason 应含 'magic OK', 实际 {reason!r}"

        # 造 .DuckDB (混合大小写) + DUCK magic
        duckdb_mixed = tmp_path / "b.DuckDB"
        duckdb_mixed.write_bytes(b"\x00" * 8 + b"DUCK" + b"\x00" * 100)
        ok2, reason2 = prune_lib._matches_magic(duckdb_mixed)
        assert ok2 is True, (
            f".DuckDB + DUCK magic 应 case-insensitive 匹配, 实际 ok={ok2} reason={reason2!r}"
        )

        # 造 .DUCKDB.zst (混合大小写) + ZSTD_MAGIC
        zst_mixed = tmp_path / "c.DUCKDB.zst"
        zst_mixed.write_bytes(prune_lib.ZSTD_MAGIC + b"\x00" * 100)
        ok3, reason3 = prune_lib._matches_magic(zst_mixed)
        assert ok3 is True, (
            f".DUCKDB.zst + ZSTD_MAGIC 应 case-insensitive 匹配, 实际 ok={ok3} reason={reason3!r}"
        )

    def test_suffix_order_is_explicit_longest_first(self):
        """Case 4 (Sprint 117 修 #D14): 显式 sort longest-first, 不依赖 dict iteration order.

        验证: _suffix_order() 返 sorted(MAGIC_CHECKS, key=len, reverse=True).
        即 .duckdb.zst (10) → .parquet (8) → .duckdb (7).
        后人加新 suffix 到 MAGIC_CHECKS 任何位置, _matches_magic 仍 longest-first 选.
        """
        from scripts.etl.common import prune_lib

        order = prune_lib._suffix_order()

        # 1. 返 list (不是 dict view), 显式 sort
        assert isinstance(order, list), f"_suffix_order 应返 list, 实际 {type(order)}"
        # 2. 顺序: .duckdb.zst (10) → .parquet (8) → .duckdb (7)
        assert order == [".duckdb.zst", ".parquet", ".duckdb"], (
            f"_suffix_order 顺序错 (期望 longest-first): {order}"
        )
        # 3. 顺序按 len 严格递减
        for i in range(len(order) - 1):
            assert len(order[i]) > len(order[i + 1]), (
                f"len 严格递减违反: {order[i]} (len={len(order[i])}) vs {order[i + 1]} (len={len(order[i + 1])})"
            )

    def test_prune_with_safety_uses_new_prune_lib_signature(self, tmp_path):
        """Case 5 (Sprint 117 sanity check): _prune_with_safety 返 Tuple[int, list[str]] 持续生效.

        验证: Sprint 117 改 _matches_magic 内部 (Sprint 116 Tuple 返值持续, callers 0 改动).
        """
        from scripts.etl.common import prune_lib

        # 造 2 份超 retention=2 天 .duckdb.zst
        zst_a = self._make_duckdb_zst(tmp_path / "a.duckdb.zst", days_old=10)
        zst_b = self._make_duckdb_zst(tmp_path / "b.duckdb.zst", days_old=10)

        deleted, deleted_names = prune_lib._prune_with_safety(
            backup_dir=tmp_path,
            glob_patterns=("*.duckdb.zst",),
            retention_days=2,
            keep_min=0,
            log_fn=lambda msg: None,
        )

        # 验证: 返 tuple, 2 份都删
        assert deleted == 2, f"期望删 2 个, 实际 {deleted}"
        assert isinstance(deleted_names, list), f"deleted_names 应是 list, 实际 {type(deleted_names)}"
        assert len(deleted_names) == 2, f"deleted_names 应有 2 个, 实际 {len(deleted_names)}"
        assert sorted(deleted_names) == ["a.duckdb.zst", "b.duckdb.zst"], (
            f"deleted_names 应是 a + b, 实际 {deleted_names}"
        )
        assert not zst_a.exists() and not zst_b.exists(), "2 份超 retention 应删"
