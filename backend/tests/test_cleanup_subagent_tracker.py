"""Sprint 31.1 — Layer 6 (cleanup_subagent) cross-reference tracker 测试

Phase 2 行为:
  - tracked path → 留给 Layer 1 24h 周期, Layer 6 跳过
  - untracked path 走原静态 _FQ_TMP_PREFIXES 白名单逻辑
  - tracker 不可用 → 降级到静态白名单 (跟 Phase 1 之前完全一致)
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class _BrokenTrackerDB:
    """模拟 tracker 不可用 (init 失败 / DB lock 等)."""

    def is_available(self):
        return False

    def is_tracked(self, _path):
        return False


class TestLayer6TrackerCrossRef:
    """Layer 6 跨层判断 (tracker vs static FQ_TMP_PREFIXES) 测试.

    注: _FQ_TMP_PREFIXES 是 hardcoded 静态常量 (/private/tmp/_fq_ro + /private/tmp/fuqing_),
    跨 test 共享. 本测试聚焦于 tracker 跨层逻辑本身, 不测静态白名单的 prefix 匹配
    (那是 test_lsof_protection.py 范围).
    """

    def test_layer6_skips_tracked_files(self, tmp_path, monkeypatch):
        """tracked path → Layer 6 跳过 (留给 Layer 1 24h)."""
        from scripts.etl import cleanup_subagent
        from scripts.etl.common.tmp_tracker import TrackerDB

        # 1. 造一个 tracked 文件
        target = tmp_path / "fuqing_tracked.duckdb"
        target.write_bytes(b"x" * (2 * 1024**3))  # 2GB (超 1GB 阈值)
        old = time.time() - 2 * 3600  # 2h 前
        os.utime(target, (old, old))

        # 2. register 到 tracker (per-test DB 由 conftest fixture 提供)
        tracker = TrackerDB()
        tracker.register(str(target), size=2 * 1024**3, pid=1)
        assert tracker.is_tracked(str(target))

        # 3. 用 monkeypatch 限定 _SCAN_ROOTS 到 tmp_path (隔离)
        monkeypatch.setattr(cleanup_subagent, "_SCAN_ROOTS", (str(tmp_path),))
        monkeypatch.setattr(cleanup_subagent, "_EXCLUDE_PATH_PREFIXES", ())
        monkeypatch.setattr(cleanup_subagent, "_PROTECTED_BASENAMES", set())
        monkeypatch.setattr(cleanup_subagent, "_is_excluded_ext", lambda p: False)
        monkeypatch.setattr(cleanup_subagent, "_MIN_SIZE_BYTES", 1)

        # 4. 跑 Layer 6 — tracked 文件必须跳过
        result = cleanup_subagent.cleanup_subagent_tmp(dry_run=False)
        assert result["deleted_count"] == 0
        assert target.exists(), "tracked 文件绝不能被 Layer 6 删"

    def test_layer6_cleans_untracked_orphans(self, tmp_path, monkeypatch):
        """untracked path (不匹配静态 _FQ_TMP_PREFIXES) → Layer 6 删除."""
        from scripts.etl import cleanup_subagent

        # 造一个 untracked 大文件 (不匹配 fuqing_* 也不匹配 _fq_ro*)
        big = tmp_path / "unrelated_huge.duckdb"
        big.write_bytes(b"x" * (2 * 1024**3))
        old = time.time() - 2 * 3600
        os.utime(big, (old, old))

        monkeypatch.setattr(cleanup_subagent, "_SCAN_ROOTS", (str(tmp_path),))
        monkeypatch.setattr(cleanup_subagent, "_EXCLUDE_PATH_PREFIXES", ())
        monkeypatch.setattr(cleanup_subagent, "_PROTECTED_BASENAMES", set())
        monkeypatch.setattr(cleanup_subagent, "_is_excluded_ext", lambda p: False)
        monkeypatch.setattr(cleanup_subagent, "_MIN_SIZE_BYTES", 1)

        result = cleanup_subagent.cleanup_subagent_tmp(dry_run=False)
        assert result["deleted_count"] == 1
        assert not big.exists(), "untracked orphan 应被 Layer 6 删"

    def test_layer6_falls_back_to_static_prefix_on_tracker_error(self, tmp_path, monkeypatch):
        """tracker 不可用时 _is_in_whitelist 仍走 _FQ_TMP_PREFIXES 静态白名单.

        验证 _is_in_whitelist 在 tracker.is_available()=False 时降级路径.
        不实际跑 cleanup_subagent_tmp (避免 hardcoded /private/tmp/ prefix 限制),
        直接验证 _is_in_whitelist helper 行为.
        """
        from scripts.etl import cleanup_subagent

        broken = _BrokenTrackerDB()

        # tracker 不可用 + path 在 /private/tmp/fuqing_ → True (静态白名单)
        assert cleanup_subagent._is_in_whitelist(
            "/private/tmp/fuqing_xxx.duckdb", broken
        ) is True
        # tracker 不可用 + path 在 /private/tmp/_fq_ro → True
        assert cleanup_subagent._is_in_whitelist(
            "/private/tmp/_fq_ro_xxx.duckdb", broken
        ) is True
        # tracker 不可用 + path 不匹配白名单 → False
        assert cleanup_subagent._is_in_whitelist(
            "/private/tmp/other.duckdb", broken
        ) is False
        # tracker None + path 在白名单 → True
        assert cleanup_subagent._is_in_whitelist(
            "/private/tmp/fuqing_xxx.duckdb", None
        ) is True
        # tracker None + path 不匹配 → False
        assert cleanup_subagent._is_in_whitelist(
            "/private/tmp/other.duckdb", None
        ) is False

    def test_layer6_tracked_overrides_static(self, tmp_path, monkeypatch):
        """tracker 跟踪 + 不匹配静态白名单 → True (tracker 优先级)."""
        from scripts.etl import cleanup_subagent
        from scripts.etl.common.tmp_tracker import TrackerDB

        # 跟踪一个不匹配 fuqing_/_fq_ro 前缀的 path
        weird = tmp_path / "weird_path.duckdb"  # 任何 prefix
        tracker = TrackerDB()
        tracker.register(str(weird), size=100, pid=1)
        assert tracker.is_tracked(str(weird))

        # 即便 path 不匹配 _FQ_TMP_PREFIXES, tracked 仍返 True (留给 Layer 1)
        assert cleanup_subagent._is_in_whitelist(str(weird), tracker) is True
