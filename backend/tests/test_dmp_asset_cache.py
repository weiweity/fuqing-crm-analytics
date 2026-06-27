"""
Tests for backend/services/asset_focus_service/_helpers.py cache invalidation.

Regression test for: asset_focus_service result 缓存不感知 mtime 变化的 bug。

根因：_cache["data3"]["result"] 按 _weeks 单字段 key 缓存，文件 mtime 变化时
_check_reload 只刷 mtime + df，不动 result 缓存，导致 product.py / other.py
缓存命中 return 旧 result，CSV 更新看不到。

修复：_load_data3 检测到 mtime 变化时，连带清掉 result / result_other。

本测试不依赖真实 data3.csv（避免污染线上 DMP 数据），用 tmp_path 写临时 CSV。
"""

import time
from pathlib import Path

import pytest


# 7 个核心单品 + 8 个其他单品的最小 ID 集合
CORE_IDS = [
    587051744204, 803474428381, 870597889980, 994162104051,
    933524395698, 900975734816, 1010458880710,
]
OTHER_IDS = [
    587053192746, 597655781410, 601760206476, 612503357090,
    621639424901, 654390297284, 683395365107, 803417397714,
]


def _write_csv(path: Path, dates: list[str]) -> None:
    """写入最小可用 data3.csv 格式。"""
    lines = ["ID,时间,资产总量,浅种草,深种草,首购资产,复购资产,连带资产,status"]
    for pid in CORE_IDS + OTHER_IDS:
        for d in dates:
            lines.append(f"{pid},{d},1000,800,100,50,30,20,verified")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def dmp_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """用 tmp_path 写一个临时 data3.csv，并 monkeypatch 服务层引用。"""
    csv_path = tmp_path / "data3.csv"
    _write_csv(csv_path, ["2026/5/20", "2026/5/21", "2026/5/22"])

    from backend.services.asset_focus_service import _helpers
    # _load_data3 在 _helpers.py 模块内引用 DMP_DATA3_PATH，只需 patch 这一处
    monkeypatch.setattr(_helpers, "DMP_DATA3_PATH", csv_path)

    # 清 module-level 缓存（不同测试间共享状态）
    _helpers._cache["data3"] = {
        "mtime": 0, "df": None, "result": None, "result_other": None
    }

    yield csv_path


class TestDmpAssetCacheInvalidation:
    """Regression: result 缓存必须随 mtime 失效。"""

    def test_mtime_unchanged_returns_cached_result(self, dmp_csv: Path) -> None:
        """mtime 没变 → 第二次调应当 return 同一对象（缓存命中）"""
        from backend.services.asset_focus_service.product import get_product_assets

        d1 = get_product_assets(weeks=4, days=0)
        d2 = get_product_assets(weeks=4, days=0)
        assert d1 is d2, "mtime 没变时应该命中 result 缓存"

    def test_mtime_changed_invalidates_result_cache(self, dmp_csv: Path) -> None:
        """mtime 变 → 第二次调必须重算（不返回旧对象）"""
        from backend.services.asset_focus_service.product import get_product_assets

        d1 = get_product_assets(weeks=4, days=0)
        old_total = d1["products"][0]["weeks"][-1]["total"]
        assert old_total == 1000  # 写入时的值

        # 模拟 work plat 更新 CSV：加一天数据 + 改 mtime
        time.sleep(0.05)
        _write_csv(dmp_csv, ["2026/5/20", "2026/5/21", "2026/5/22", "2026/5/23"])

        d2 = get_product_assets(weeks=4, days=0)
        assert d1 is not d2, "❌ bug 还在：mtime 变了却返回旧 result 对象"
        new_total = d2["products"][0]["weeks"][-1]["total"]
        assert new_total == 1000, "新 result 应该来自新 CSV"

    def test_other_product_assets_also_invalidated(self, dmp_csv: Path) -> None:
        """other 缓存（result_other）必须跟 result 同步失效"""
        from backend.services.asset_focus_service.other import get_other_product_assets

        d1 = get_other_product_assets(weeks=4, days=0)
        time.sleep(0.05)
        _write_csv(dmp_csv, ["2026/5/20", "2026/5/21", "2026/5/22", "2026/5/23"])
        d2 = get_other_product_assets(weeks=4, days=0)
        assert d1 is not d2, "other result_other 没随 mtime 失效"

    def test_different_weeks_creates_separate_cache(self, dmp_csv: Path) -> None:
        """weeks=4 和 weeks=8 算出不同的 _weeks 字段（不同缓存 key）"""
        from backend.services.asset_focus_service.product import get_product_assets

        d4 = get_product_assets(weeks=4, days=0)
        d8 = get_product_assets(weeks=8, days=0)
        # 注：当前 result 是单字段缓存，weeks=8 调后会覆盖 weeks=4 的缓存（F7 预存 bug，
        # 不在本次修复范围），所以 d8 is d4_again 必为 False。但 _weeks 字段值应正确。
        assert d4["_weeks"] == 4
        assert d8["_weeks"] == 8
        assert d4 is not d8
