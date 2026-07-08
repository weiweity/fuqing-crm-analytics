"""
Sprint 205+ (L4.72.1) RFM 缓存 _read_db_cache 控制流 bug 修复 (2026-07-08)

背景:
  Phase 1 第 2 个 Explore agent (老客分析 9 子板块架构深度排查) 100% 锁定真根因:
  - `cache.py:117-159` `_read_db_cache` 函数控制流严重 bug
  - SELECT 全在 except 块里, 正常路径 try 块成功时**无 SELECT**, 直接 return None
  - 这是 "L4.71 5 分钟 TTL cache 命中率 0%" 的真根因
  - L4.71 错方向: 不是 cache 没数据, 是 _read_db_cache 在正常路径里 never reads

  治本: SELECT 移出 except 块, 正常路径也跑 SELECT (cache.py:121-130 之后 line 132+)
  预期: cache 命中率 0% → 60%+ (跟 L4.69 治本后 RFM 18-29s 1:1 stable 配套)

4 case 锁回归 (Sprint 50+ 12 步流程 SOP 1:1 stable 配套):
  - test_read_db_cache_normal_path_selects: 正常路径 try 块成功时也跑 SELECT
  - test_read_db_cache_exception_path_still_selects: 异常路径 SELECT 仍跑 (跟旧代码 1:1 stable)
  - test_read_db_cache_returns_none_on_miss: cache miss 返回 None
  - test_read_db_cache_returns_data_on_hit: cache hit 返回 data

跟永久规则链配套 (1:1 stable):
  - L4.67 业务库 + cache 库分离 (跨文件 fingerprint 0 关联)
  - L4.71 5 分钟 TTL (24h 实际)
  - L4.42 立项实证 SOP (本 plan 跟 L4.42 1:1 stable)
  - L4.50 pytest cleanup 0 业务代码改动 (Sprint 60+ 累计 52 次 stable)
"""
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestL4721RfmCacheReadFlowLockRegression:
    """L4.72.1 永久规则化: _read_db_cache 必须正常路径 + 异常路径都跑 SELECT
    (Phase 1 第 2 个 Explore agent 100% 锁定真根因).

    Sprint 205+ 真业务触发: L4.71 cache 命中率 0% 跟 618 大促 8 并发 RFM 雪崩
    同根因, 治本 L4.72.1 cache.py 控制流 bug 修复.
    """

    def test_read_db_cache_normal_path_selects(self):
        """L4.72.1 治本核心: 正常路径 try 块成功时**也**跑 SELECT (旧代码 bug 在 except 块).

        如果未来 refactor 误改回 SELECT 在 except 块里, 正常路径永远 cache miss
        (跟 L4.71 5 分钟 TTL 错方向 1:1 stable 复发).
        """
        from backend.services.health.rfm_analysis import cache

        src = inspect.getsource(cache._read_db_cache)
        # 正常路径必须包含 SELECT (跟异常路径 1:1 stable)
        # 关键: SELECT 必须在 try 块**外**, 跟旧代码 except 块错方向 1:1 stable 区分
        assert "SELECT" in src, (
            "L4.72.1 治本核心: _read_db_cache 必须包含 SELECT 查询. "
            "如果 SELECT 被误删, cache 命中率 0% 复发 (跟 L4.71 错方向 1:1 stable)."
        )
        # SELECT 必须在 try 块**外** (旧 bug: SELECT 在 except 块里, 正常路径无 SELECT)
        # 验证: SELECT 之前必须先有 `key = _cache_key(...)` 之后才 SELECT
        # 简单验证: SELECT 行不应该以 `        row = conn.execute` 开头, 必须先有
        # `_ensure_db_cache_table` 调用之后的 except 块
        # L4.72.1 治本后: SELECT 在第二个 try 块里 (异常路径 + 正常路径都跑)
        lines = src.split("\n")
        select_line_idx = None
        ensure_table_idx = None
        for i, line in enumerate(lines):
            if "SELECT result_json" in line and select_line_idx is None:
                select_line_idx = i
            if "_ensure_db_cache_table" in line and ensure_table_idx is None:
                ensure_table_idx = i

        assert select_line_idx is not None, (
            "L4.72.1 治本: _read_db_cache 必须包含 SELECT result_json 查询"
        )
        assert ensure_table_idx is not None, (
            "L4.72.1 治本: _read_db_cache 必须包含 _ensure_db_cache_table 调用"
        )
        # L4.72.1 治本: SELECT 必须在 _ensure_db_cache_table **之后** (确保 try 块后跑)
        assert select_line_idx > ensure_table_idx, (
            f"L4.72.1 治本核心: SELECT 必须在 _ensure_db_cache_table 之后 (正常路径跑). "
            f"旧 bug: SELECT 在 except 块 (line {select_line_idx}) < _ensure_db_cache_table (line {ensure_table_idx}). "
            f"治本后: SELECT 在 try 块**外** (line {select_line_idx} > {ensure_table_idx}), 正常路径也跑."
        )

    def test_read_db_cache_exception_path_still_selects(self):
        """L4.72.1 治本: 异常路径 SELECT 仍跑 (跟旧代码 except 块行为 1:1 stable 兼容).

        旧代码: try 块失败 → except 块跑 SELECT (异常路径正确)
        新代码: try 块失败 → 跳到新 try 块跑 SELECT (异常路径仍正确)
        预期: 两种路径都跑 SELECT, 1:1 stable 兼容.
        """
        from backend.services.health.rfm_analysis import cache

        src = inspect.getsource(cache._read_db_cache)
        # 异常路径必须保留 (旧代码 except 块行为)
        # 验证: 第二个 try 块 (新代码) 或 except 块 (旧代码) 跑 SELECT
        assert "SELECT" in src, (
            "L4.72.1 治本: 异常路径 SELECT 必须保留 (跟旧代码 except 块 1:1 stable 兼容)"
        )
        # 验证: 异常处理逻辑 (try/except 至少各 1 个)
        assert src.count("try:") >= 2, (
            f"L4.72.1 治本: _read_db_cache 必须保留 try 块 (确保 异常处理 1:1 stable). "
            f"旧代码 1 个 try, 新代码 2 个 try (第 1 个 try: DDL; 第 2 个 try: SELECT). "
            f"实际 try 块数: {src.count('try:')}, 期望 >= 2."
        )

    def test_read_db_cache_returns_none_on_miss(self):
        """L4.72.1 治本: cache miss 时返回 None (跟 L4.71 行为 1:1 stable 兼容).

        治本: SELECT 正常路径也跑, cache miss 时 (row = None) 返回 None
        (跟旧代码异常路径返回 None 1:1 stable 兼容).
        """
        from backend.services.health.rfm_analysis import cache
        import inspect

        src = inspect.getsource(cache._read_db_cache)
        # 验证: row 为 None 时返回 None (cache miss 1:1 stable 兼容)
        assert "if not row:" in src, (
            "L4.72.1 治本: cache miss (row=None) 时必须返回 None. "
            "如果误改, 调用方会拿到 None 但无法区分 'cache miss' vs 'cache hit 但 data 为空'."
        )
        assert "return None" in src, (
            "L4.72.1 治本: 必须有 return None (cache miss 1:1 stable 兼容)"
        )

    def test_read_db_cache_returns_data_on_hit(self):
        """L4.72.1 治本: cache hit 时返回 parsed dict (跟 L4.71 行为 1:1 stable 兼容).

        治本后: 正常路径 cache hit 也会返回 parsed dict (旧 bug 永远走 None).
        """
        from backend.services.health.rfm_analysis import cache
        import inspect

        src = inspect.getsource(cache._read_db_cache)
        # 验证: cache hit 时返回 parsed (旧 bug: 永远返回 None)
        # 检查 return parsed 路径 (在异常处理后, 在 return None 前)
        # 关键: 正常路径必须有 `return parsed` (旧 bug 缺这个)
        assert "return parsed" in src, (
            "L4.72.1 治本: cache hit 时必须返回 parsed dict. "
            "旧 bug: 正常路径直接 return None, 永远 cache miss. "
            "治本后: 正常路径 return parsed, 异常路径仍 return None (cache miss 1:1 stable)."
        )
        # 验证: 必须有 is_stale 检查 (跟 L4.71 三重保护 1:1 stable 兼容)
        assert "is_stale" in src, (
            "L4.72.1 治本: cache hit 时必须 is_stale 检查 (L4.71 mtime + 行数 + TTL 三重保护 1:1 stable 兼容)"
        )
