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
    DUCKDB_MEMORY_LIMIT,
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
        """DUCKDB_MEMORY_LIMIT_OVERRIDE 常量在 import 时 .strip() 过滤。

        FIX-S8: 原测试 `if current: assert current == current.strip()` 是 vacuous —
        current 为空时跳过, 不验任何东西; current 非空时 strip() 总等自己.
        改: 强制 reload backend.config 在 monkeypatch setenv 后, 验常量 strip 真生效.
        """
        import importlib
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT_OVERRIDE", "  16GB  ")
        # Reload module-level 重新读 env
        import backend.config as _bc
        importlib.reload(_bc)
        assert _bc.DUCKDB_MEMORY_LIMIT_OVERRIDE == "16GB", (
            f"module-level 常量未 strip: {_bc.DUCKDB_MEMORY_LIMIT_OVERRIDE!r}"
        )

    def test_backward_compat_default_8gb(self, monkeypatch):
        """DUCKDB_MEMORY_LIMIT 常量保留向后兼容（CLAUDE.md §W7 合规 ①）。

        FIX-S8: 原测试 assert `env_val in ('8GB', '16GB', '4GB')` 是 vacuous —
        接受任意 3 值, 即使实现改成 return '32GB' 也通过, 名为 '向后兼容默认 8GB'
        实际未断言任何 W7 行为。修: 显式 monkeypatch DUCKDB_MEMORY_LIMIT='8GB'
        验常量 = 8GB。
        """
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT", "8GB")
        # DUCKDB_MEMORY_LIMIT 是 module-level 常量, import 时已固定, monkeypatch env 不影响
        # 但常量本身 = os.environ.get("DUCKDB_MEMORY_LIMIT", "8GB") 在 import 时读
        # 若测试环境 import 时 DUCKDB_MEMORY_LIMIT 未设, 常量 = "8GB"
        # 若测试环境 import 时 DUCKDB_MEMORY_LIMIT 设为其他值, 常量 = 该值
        # 接受这两种情况 (向后兼容 + 测试环境差异)
        import os
        env_at_import = os.environ.get("DUCKDB_MEMORY_LIMIT", "8GB")
        assert DUCKDB_MEMORY_LIMIT in (env_at_import, "8GB"), (
            f"DUCKDB_MEMORY_LIMIT={DUCKDB_MEMORY_LIMIT!r} 不匹配 import 时 env={env_at_import!r}"
        )


class TestW7SetupAsyncMemory:
    """W7 W4 占位 helper：setup_async_memory() / cleanup_async_memory()。"""

    def test_setup_async_memory_exports_override_8gb(self, monkeypatch):
        """setup_async_memory() export 8GB override + 返回 8GB (Sprint 10 B1: 16GB→8GB)。"""
        monkeypatch.delenv("DUCKDB_MEMORY_LIMIT_OVERRIDE", raising=False)
        monkeypatch.delenv("DUCKDB_MEMORY_LIMIT_OVERRIDE_ASYNC", raising=False)
        monkeypatch.setenv("DUCKDB_MEMORY_LIMIT", "8GB")

        memory_limit = precompute_fact_rfm.setup_async_memory()

        assert memory_limit == "8GB"
        assert os.environ["DUCKDB_MEMORY_LIMIT_OVERRIDE"] == "8GB"
        assert precompute_fact_rfm.DEFAULT_ASYNC_OVERRIDE == "8GB"

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

        # 2. setup：override 8GB (Sprint 10 B1: 16GB→8GB 跟主 conn 一致)
        precompute_fact_rfm.setup_async_memory()
        assert get_duckdb_memory_limit() == "8GB"

        # 3. cleanup：恢复 8GB
        precompute_fact_rfm.cleanup_async_memory()
        assert get_duckdb_memory_limit() == "8GB"

    def test_w4_full_v0_4_12_implemented(self):
        """W4 full v0.4.12 — 540 组合 + dbt-style merge 已实施, run_full_precomputation 占位已替换.

        旧 v0.4.9 时代占位: raise NotImplementedError("W4")
        v0.4.12 W4 full 实施: incremental_load + merge_replace + rfm_recompute_window.py
        验证方法: 540 组合 / dbt-style merge / 全量重算 都已在 test_w4_full.py 覆盖.
        """
        # W4 full 已实施, 验证关键 API 存在
        assert hasattr(precompute_fact_rfm, "incremental_load"), "incremental_load 应存在"
        assert hasattr(precompute_fact_rfm, "merge_replace"), "merge_replace 应存在"
        assert hasattr(precompute_fact_rfm, "incremental_load_with_merge"), "incremental_load_with_merge 应存在"
        assert hasattr(precompute_fact_rfm, "W4_TOTAL_COMBOS"), "W4_TOTAL_COMBOS 应存在"
        assert precompute_fact_rfm.W4_TOTAL_COMBOS == 540, "W4_TOTAL_COMBOS 应 == 540"


# 局部 import 避免 module-level 副作用
import os  # noqa: E402  必须在 test 类之外
