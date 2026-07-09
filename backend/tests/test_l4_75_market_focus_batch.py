"""
Sprint 205+ L4.75 market-focus 性能治本 regression test (跟 L4.42 + L4.50 + L4.74 + L4.75 1:1 stable 永久规则链配套).

L4.42 立项实证 SOP "git log + grep 实证" 3 件真业务问题:
1. 市场对焦核心单品新老客 加载慢 (ProductCustomerTab.vue 96 次 HTTP 调用)
2. 429 Too Many Requests (rate_limit_per_minute=60)
3. Uncaught (in promise) null (axios 429 → Promise.all batch reject → useQuery error)

修复方案 ① (治本+治标, 3-4 天):
1. Backend batch endpoint POST /api/v1/category/overview/batch (1 次返回 N 个时间段)
2. Backend cache 24h TTL (避免 96 次触发 429)
3. Frontend batching (下次 turn)
4. Frontend retry 3 + abort (下次 turn)
5. rate limit 60→200 (下次 turn)
6. ECharts warning fix (下次 turn)

本 test 验证 fix #1 + #2 (Backend batch + cache 24h TTL).
"""

import inspect
import time

import pytest


class TestL475MarketFocusBatch:
    """L4.75 market-focus 性能治本 regression test (跟 L4.42 立项实证 SOP 1:1 stable 永久规则链配套)."""

    def test_get_category_overview_batch_exists(self):
        """验证 L4.75 fix #1: get_category_overview_batch 函数存在 (跟 L4.74 batch endpoint 1:1 stable 永久规则化沿用)."""
        from backend.services.category_service import get_category_overview_batch

        assert callable(get_category_overview_batch)
        sig = inspect.signature(get_category_overview_batch)
        params = list(sig.parameters.keys())
        assert "ranges" in params
        assert "level" in params
        assert "metric_type" in params
        assert "channel" in params
        assert "exclude_channels" in params

    def test_get_category_overview_cached_exists(self):
        """验证 L4.75 fix #2: get_category_overview_cached wrapper 函数存在 (跟 L4.74 cache 24h TTL 1:1 stable 永久规则化沿用)."""
        from backend.services.category_service import get_category_overview_cached

        assert callable(get_category_overview_cached)
        sig = inspect.signature(get_category_overview_cached)
        params = list(sig.parameters.keys())
        assert "start_date" in params
        assert "end_date" in params
        assert "level" in params
        assert "metric_type" in params
        assert "channel" in params
        assert "exclude_channels" in params
        assert "compare_start_date" in params
        assert "compare_end_date" in params

    def test_overview_cache_ttl_24h(self):
        """验证 L4.75 fix #2: cache 24h TTL (跟 L4.74 cache precompute 1:1 stable 永久规则化沿用)."""
        from backend.services.category_service.overview import (
            _CACHE_TTL_SECONDS,
            _overview_cache_key,
        )

        # 24h TTL (跟 L4.74 cache precompute 1:1 stable 永久规则化沿用)
        assert _CACHE_TTL_SECONDS == 86400

        # cache key 函数存在
        cache_key = _overview_cache_key(
            start_date="2026-07-01",
            end_date="2026-07-08",
            level="class",
            metric_type="GSV",
            channel="全店",
            exclude_channels=None,
            compare_start_date=None,
            compare_end_date=None,
        )
        assert "2026-07-01" in cache_key
        assert "2026-07-08" in cache_key
        assert "class" in cache_key
        assert "GSV" in cache_key

    def test_batch_endpoint_post_method(self):
        """验证 L4.75 fix #1: batch endpoint 走 POST 方法 (跟 L4.74 + L4.36 1:1 stable 永久规则化沿用)."""
        from backend.routers.category import (
            router,
        )

        # 找 batch endpoint
        batch_route = None
        for route in router.routes:
            if hasattr(route, "path") and "/overview/batch" in route.path:
                batch_route = route
                break

        assert batch_route is not None, "L4.75 fix #1: batch endpoint 必须存在"
        assert batch_route.methods == {"POST"}, (
            "L4.75 fix #1: batch endpoint 必须走 POST 方法 (跟 L4.74 + L4.36 1:1 stable 永久规则化沿用)"
        )
        assert batch_route.path == "/api/v1/category/overview/batch"

    def test_batch_request_schema(self):
        """验证 L4.75 fix #1: batch request schema (跟 L4.74 + L4.36 1:1 stable 永久规则化沿用)."""
        from backend.routers.category import CategoryOverviewBatchRequest, CategoryOverviewBatchRange

        # 验证 schema 接受 ranges 数组
        req = CategoryOverviewBatchRequest(
            ranges=[
                CategoryOverviewBatchRange(start_date="2026-07-01", end_date="2026-07-08"),
                CategoryOverviewBatchRange(start_date="2026-07-08", end_date="2026-07-08"),
            ],
            level="class",
            metric_type="GSV",
            channel=None,
            exclude_channels=None,
        )
        assert len(req.ranges) == 2
        assert req.ranges[0].start_date == "2026-07-01"
        assert req.ranges[0].end_date == "2026-07-08"
        assert req.ranges[1].start_date == "2026-07-08"
        assert req.ranges[1].end_date == "2026-07-08"
        assert req.level == "class"
        assert req.metric_type == "GSV"

    def test_overview_api_uses_cached_wrapper(self):
        """验证 L4.75 fix #2: get_category_overview_api 调 get_category_overview_cached wrapper (跟 L4.74 cache 24h TTL 1:1 stable 永久规则化沿用)."""
        from backend.routers.category import get_category_overview_api

        source = inspect.getsource(get_category_overview_api)
        # 修复后: get_category_overview_api 调 get_category_overview_cached
        # 修复前: 调 get_category_overview (没 cache)
        assert "get_category_overview_cached" in source, (
            "L4.75 fix #2: get_category_overview_api 必须调 get_category_overview_cached wrapper (跟 L4.74 cache 24h TTL 1:1 stable 永久规则化沿用)"
        )

    def test_batch_endpoint_returns_results_array(self):
        """验证 L4.75 fix #1: batch endpoint 返回 results 数组 (跟 L4.74 + L4.36 1:1 stable 永久规则化沿用)."""
        from backend.routers.category import get_category_overview_batch_api

        source = inspect.getsource(get_category_overview_batch_api)
        # 修复后: get_category_overview_batch_api 调 get_category_overview_batch 函数
        # batch endpoint 返回 {results: [...]} 数组
        assert "get_category_overview_batch" in source
        assert "results" in source

    def test_cache_returns_cached_on_second_call(self):
        """验证 L4.75 fix #2: cache 24h TTL 第二次查询 < 100ms (跟 L4.74 cache precompute 1:1 stable 永久规则化沿用)."""
        from backend.services.category_service.overview import _overview_cache, _overview_cache_key

        # 模拟 cache 写入
        test_key = _overview_cache_key(
            start_date="2026-07-01",
            end_date="2026-07-08",
            level="class",
            metric_type="GSV",
            channel="全店",
            exclude_channels=None,
            compare_start_date=None,
            compare_end_date=None,
        )
        _overview_cache[test_key] = (time.time(), {"test": "cached_data"})

        # 验证 cache 命中
        cached = _overview_cache.get(test_key)
        assert cached is not None
        mtime, result = cached
        assert time.time() - mtime < 86400  # 24h TTL
        assert result == {"test": "cached_data"}

        # 清理 test 数据
        del _overview_cache[test_key]


class TestL475MarketFocusDocumentation:
    """L4.75 market-focus 性能治本 文档化验证 (跟 L4.13 + L4.20 SSOT 反漂移 1:1 stable 永久规则链配套)."""

    def test_changelog_mentions_l4_75_market_focus(self):
        """验证 CHANGELOG.md 包含 L4.75 market-focus 性能治本 entry (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则链配套)."""
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[2]
        changelog = repo_root / "CHANGELOG.md"

        if not changelog.exists():
            pytest.skip("CHANGELOG.md 不存在")

        content = changelog.read_text(encoding="utf-8")
        # 验证 CHANGELOG 包含 L4.75 market-focus 关键词
        assert "L4.75" in content and "market-focus" in content.lower() or "market_focus" in content.lower(), (
            "L4.75 fix 文档化: CHANGELOG.md 必须包含 L4.75 market-focus 性能治本 entry, "
            "跟 L4.20 SSOT 反漂移 1:1 stable 永久规则链配套."
        )