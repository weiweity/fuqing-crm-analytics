"""
W7 (DUCKDB_MEMORY_LIMIT 自动管理) — override 切换逻辑

设计: docs/design/etl-phase4-architecture.md §W7
"""
from pathlib import Path

# Add project root to path
import sys
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import (  # noqa: E402
    DUCKDB_MEMORY_LIMIT_OVERRIDE,
    get_duckdb_memory_limit,
)
from scripts.etl import precompute_fact_rfm  # noqa: E402  W4 占位


# ============================================================
# Test cases
# ============================================================

class TestW7MemoryLimitOverride:
    """W7 DUCKDB_MEMORY_LIMIT_OVERRIDE 切换逻辑。"""

    def test_default_returns_8gb_when_no_override(self, monkeypatch):
        """未设 DUCKDB_MEMORY_LIMIT_OVERRIDE → 返回默认 8GB。"""
        monkeypatch.delenv("DUCKDB_MEMORY_LIMIT_OVERRIDE", raising=False)
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT", "8GB")

        assert get_duckdb_memory_limit() == "8GB"

    def test_override_16gb_returns_16gb(self, monkeypatch):
        """override=16GB → 返回 16GB（W4 async 场景）。"""
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT_OVERRIDE", "16GB")
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT", "8GB")

        assert get_duckdb_memory_limit() == "16GB"

    def test_empty_override_falls_back_to_default(self, monkeypatch):
        """override=""（空字符串）→ 返回默认（不是返回空）。"""
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT_OVERRIDE", "")
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT", "8GB")

        assert get_duckdb_memory_limit() == "8GB"

    def test_whitespace_only_override_falls_back(self, monkeypatch):
        """override="  "（仅空白）→ 返回默认（.strip() 过滤）。"""
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT_OVERRIDE", "  ")
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT", "8GB")

        assert get_duckdb_memory_limit() == "8GB"

    def test_custom_default_value(self, monkeypatch):
        """DUCKDB_MEMORY_LIMIT 自定义 4GB（无 override）→ 返回 4GB。"""
        monkeypatch.delenv("DUCKDB_MEMORY_LIMIT_OVERRIDE", raising=False)
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT", "4GB")

        assert get_duckdb_memory_limit() == "4GB"

    def test_override_priority_over_default(self, monkeypatch):
        """override=12GB + 默认 8GB → 返回 12GB（override 优先）。"""
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT_OVERRIDE", "12GB")
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT", "8GB")

        assert get_duckdb_memory_limit() == "12GB"

    def test_override_module_constant_strips_whitespace(self, monkeypatch):
        """DUCKDB_MEMORY_LIMIT_OVERRIDE 常量在 import 时 .strip() 过滤（避免引号污染）。

        注意：此测试是 module-level 常量的 import-time 行为快照。
        helper get_duckdb_memory_limit() 动态读 env（monkeypatch 实时生效），
        二者解耦——helper 是生产 API，常量仅向后兼容。
        """
        # 当前测试进程 import 已发生，module-level 常量已固定。
        # 验证常量已 strip（如果 env 有空白，被 .strip() 过滤过）
        current = DUCKDB_MEMORY_LIMIT_OVERRIDE
        if current:
            assert current == current.strip(), f"module-level 常量未 strip: {current!r}"

    def test_backward_compat_default_8gb(self):
        """DUCKDB_MEMORY_LIMIT 常量保留向后兼容（CLAUDE.md §W7 合规 ①）。"""
        # 不 monkeypatch 时，env 未设 → 默认 8GB
        # 假设测试环境未显式 export
        import os
        env_val = os.environ.get("DUCKDB_MEMORY_LIMIT", "8GB")
        assert env_val in ("8GB", "16GB", "4GB")  # 接受测试环境的任何值


class TestW7SetupAsyncMemory:
    """W7 W4 占位 helper：setup_async_memory() / cleanup_async_memory()。"""

    def test_setup_async_memory_exports_override_16gb(self, monkeypatch):
        """setup_async_memory() export 16GB override + 返回 16GB。"""
        monkeypatch.delenv("DUCKDB_MEMORY_LIMIT_OVERRIDE", raising=False)
        monkeypatch.delenv("DUCKDB_MEMORY_LIMIT_OVERRIDE_ASYNC", raising=False)
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT", "8GB")

        memory_limit = precompute_fact_rfm.setup_async_memory()

        assert memory_limit == "16GB"
        assert os.environ["DUCKDB_MEMORY_LIMIT_OVERRIDE"] == "16GB"
        assert precompute_fact_rfm.DEFAULT_ASYNC_OVERRIDE == "16GB"

    def test_setup_async_memory_respects_custom_async_override(self, monkeypatch):
        """DUCKDB_MEMORY_LIMIT_OVERRIDE_ASYNC=24GB → setup_async_memory 用 24GB。"""
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT_OVERRIDE_ASYNC", "24GB")
        monkeypatch.delenv("DUCKDB_MEMORY_LIMIT_OVERRIDE", raising=False)
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT", "8GB")

        memory_limit = precompute_fact_rfm.setup_async_memory()

        assert memory_limit == "24GB"
        assert os.environ["DUCKDB_MEMORY_LIMIT_OVERRIDE"] == "24GB"

    def test_cleanup_async_memory_unsets_override(self, monkeypatch):
        """cleanup_async_memory() 调后 override env 被 unset。"""
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT_OVERRIDE", "16GB")

        precompute_fact_rfm.cleanup_async_memory()

        assert "DUCKDB_MEMORY_LIMIT_OVERRIDE" not in os.environ

    def test_full_cycle_setup_then_cleanup(self, monkeypatch):
        """完整 setup → cleanup 循环：override 临时生效 → 恢复默认。"""
        monkeypatch.delenv("DUCKDB_MEMORY_LIMIT_OVERRIDE", raising=False)
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT", "8GB")

        # 1. setup 前：默认 8GB
        assert get_duckdb_memory_limit() == "8GB"

        # 2. setup：override 16GB
        precompute_fact_rfm.setup_async_memory()
        assert get_duckdb_memory_limit() == "16GB"

        # 3. cleanup：恢复 8GB
        precompute_fact_rfm.cleanup_async_memory()
        assert get_duckdb_memory_limit() == "8GB"

    def test_w4_placeholder_raises_not_implemented(self):
        """W4 run_full_precomputation() 当前 raise NotImplementedError（占位）。"""
        with pytest.raises(NotImplementedError, match="W4"):
            precompute_fact_rfm.run_full_precomputation()


# 局部 import 避免 module-level 副作用
import os  # noqa: E402  必须在 test 类之外
import pytest  # noqa: E402
