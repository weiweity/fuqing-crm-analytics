"""
Sprint 205+ L4.74 cache end_date fix regression test (跟 L4.42 + L4.50 + L4.55 + L4.65.1 + L4.69.1 + L4.74 + L4.75 1:1 stable 永久规则链配套).

L4.42 立项实证 SOP "git log + grep 实证" 4 个不匹配点 100% 锁定:
1. today 来源 (max_pay+1 vs date.today())
2. cur.end 来源 (max_pay_date vs user 给)
3. compare 参数 (precompute 不传 vs user 传)
4. cache key 算法 (含 end_date + compare)

修复: precompute 改 today=date.today() 跟 user query _resolve_date_ranges() (backend/services/rfm/_shared.py:54) 一致.
"""
import inspect
from datetime import date
from unittest.mock import patch

import duckdb


class TestL474CacheEndDateFix:
    """L4.74 cache end_date fix regression test (跟 L4.42 立项实证 SOP 1:1 stable 永久规则链配套)."""

    def test_precompute_today_uses_date_today(self):
        """验证 L4.74 fix #1: precompute today 跟 user query 一致 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则链配套)."""
        from backend.services.health.rfm_analysis import cache as cache_module

        # Read precompute_rfm_cache source code
        source = inspect.getsource(cache_module.precompute_rfm_cache)
        # 修复后: today = date.today() (跟 user query _resolve_date_ranges() 一致)
        # 修复前: today = max_pay_date + timedelta(days=1) (跟 user query 不一致 → cache key 永远 miss)
        assert "today = date.today()" in source, (
            "L4.74 fix: precompute today 必须用 date.today() 跟 user query _resolve_date_ranges() 一致, "
            "跟 L4.42 立项实证 SOP 4 个不匹配点 100% 锁定 1:1 stable 永久规则化沿用. "
            "修复前 today = max_pay_date + timedelta(days=1) → cache key 永远跟 user 不匹配 → cache miss → 13.77s → watchdog kill → 502."
        )

    def test_precompute_no_max_pay_plus_one_today(self):
        """验证 L4.74 fix #1 反向: 不再用 max_pay_date + timedelta(days=1) (跟 L4.42 立项实证 SOP 1:1 stable 永久规则链配套)."""
        from backend.services.health.rfm_analysis import cache as cache_module

        source = inspect.getsource(cache_module.precompute_rfm_cache)
        # 修复后必须删 `today = max_pay_date + timedelta(days=1)` (业务库无数据分支保留 date.today())
        # 但允许业务库无数据 fallback: `today = date.today() + timedelta(days=1)` 不存在 (否则 cache key 仍不匹配)
        assert "today = max_pay_date + timedelta(days=1)" not in source, (
            "L4.74 fix 反向验证: precompute 不能再用 max_pay_date + timedelta(days=1) 算 today, "
            "跟 L4.42 立项实证 SOP 'today 来源不匹配' 1:1 stable 永久规则化沿用."
        )

    def test_standard_periods_include_original_and_frontend_fixed_periods(self):
        """原 5 周期与新增前端固定周期都由可执行语义层 resolver 覆盖。"""
        from backend.services.health.rfm_analysis import cache as cache_module

        expected_periods = {
            "yesterday", "WTD", "MTD", "YTD", "Q1", "Q2", "Q3", "Q4",
            "last90days", "last180days", "last365days",
        }
        assert set(cache_module.STANDARD_PERIODS) == expected_periods
        for period in expected_periods:
            resolver = getattr(cache_module.PeriodBuilder, period.lower())
            assert resolver(today=date.today())["current"]

    def test_years_only_2026(self):
        """验证 L4.74 fix #3: YEARS 缩 [2026] (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 节省跑批时间 ~67%)."""
        from backend.services.health.rfm_analysis import cache as cache_module

        source = inspect.getsource(cache_module.precompute_rfm_cache)
        # 修复后: YEARS = [2026] (只算今年, 节省跑批时间)
        assert "YEARS = [2026]" in source, (
            "L4.74 fix: YEARS 必须缩 [2026] (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套), "
            "节省跑批时间 ~67%."
        )
        # 反向验证: 不再用 [2024, 2025, 2026] (3 年太慢)
        assert "[2024, 2025, 2026]" not in source, (
            "L4.74 fix 反向验证: YEARS 不能再用 [2024, 2025, 2026] (3 年跑批 ~67% 时间浪费), "
            "跟 L4.50 0 业务代码改动 1:1 stable 永久规则化沿用."
        )

    def test_precompute_today_aligns_with_user_query(self):
        """验证 L4.74 fix #1 端到端: precompute today 跟 user query _resolve_date_ranges() 一致 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则链配套)."""
        from backend.services.health.rfm_analysis import cache as cache_module
        from backend.services.rfm._shared import _resolve_date_ranges

        # 模拟 user query: 跑 MTD 默认周期
        # _resolve_date_ranges() 用 today = date.today() 算 cur.end
        ranges = _resolve_date_ranges("MTD")
        biz_conn = duckdb.connect(":memory:")
        biz_conn.execute("CREATE TABLE orders(pay_time TIMESTAMP)")
        biz_conn.execute("INSERT INTO orders VALUES ('2026-07-05 23:59:58')")

        # L4.74 fix: precompute 用 today = date.today() 算 cur.end (跟 user 一致)
        # mock _run_rfm_period 避免真跑 SQL
        with patch.object(cache_module, "_run_rfm_period") as mock_run, \
             patch.object(cache_module, "_build_rows") as mock_build, \
             patch.object(cache_module, "_ensure_db_cache_table"), \
             patch.object(cache_module, "_fetch_max_pay_time") as mock_fetch, \
             patch("backend.services.health.rfm_analysis.cache._get_cache_conn") as mock_cache_conn, \
             patch.object(cache_module.duckdb, "connect", return_value=biz_conn), \
             patch.object(cache_module, "_prune_rfm_cache_after_success", return_value=0):
            mock_run.return_value = ({}, {}, {}, {})
            mock_build.return_value = []
            mock_fetch.return_value = "2026-07-05 23:59:58"
            mock_conn = mock_cache_conn.return_value

            # 跑 precompute_rfm_cache
            cache_module.precompute_rfm_cache()

            # 验证: precompute 至少有一次 INSERT 用的 end_date 跟 user MTD end_date 一致
            insert_calls = [call for call in mock_conn.execute.call_args_list
                            if "INSERT" in str(call)]
            assert len(insert_calls) > 0, "precompute 必须有 INSERT 调用"

            # MTD 不保证是首个 materialized key；按真实 start/end 在调用集中查找。
            cur_start, cur_end, _ = ranges["current"]
            assert any(
                call.args[1] == cur_start and call.args[2] == cur_end
                for call in mock_run.call_args_list
            ), "precompute 必须物化与 HTTP _resolve_date_ranges 完全一致的 MTD current 范围"


class TestL474CacheEndDateDocumentation:
    """L4.74 cache end_date fix 文档化验证 (跟 L4.42 + L4.50 + L4.13 + L4.20 1:1 stable 永久规则链配套)."""

    def test_changelog_mentions_l474_cache_end_date(self):
        """L4.74 文档在 CHANGELOG 近窗或 history（滚动后仍可检索）。"""
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[2]
        parts = []
        for rel in ("CHANGELOG.md", "docs/history/CHANGELOG_HISTORY.md"):
            p = repo_root / rel
            if p.exists():
                parts.append(p.read_text(encoding="utf-8"))
        content = "\n".join(parts)
        assert content, "CHANGELOG.md / history 均不存在"
        assert "L4.74" in content and ("cache end_date" in content or "cache_end_date" in content), (
            "L4.74 fix 文档化: CHANGELOG 或 CHANGELOG_HISTORY 必须包含 L4.74 cache end_date fix entry, "
            "跟 L4.20 SSOT 反漂移 1:1 stable 永久规则链配套."
        )

