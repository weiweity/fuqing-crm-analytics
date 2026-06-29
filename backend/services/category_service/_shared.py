"""品类分析服务 - 共享常量和工具函数"""
from collections import OrderedDict
from typing import Any, Dict

SPU_LEVELS = {
    "category": "spu_category",      # 一级品类
    "type": "spu_type",               # 二级品类
    "tier": "spu_tier",              # 层级
    "class": "spu_product_class",    # 产品类
    "subclass": "spu_product_subclass",  # 产品子类
    "cosmetic": "spu_cosmetic",      # 功效
    "spec": "spu_spec",              # 规格
}

# 非产品品类（营销赠品、虚拟商品、物料等），从品类看板中排除
EXCLUDED_PRODUCT_CATEGORIES = (
    '购物金', '0.01', '邮费补差链接', '明星小卡', '刮刮卡',
    '有价优惠劵', '盲盒', '手持镜', '帆布袋', '帆布包',
    '加湿器', '起泡网', '吸油纸', '硅胶刷', '湿敷棉',
    '洗脸巾', 'PR礼盒', '多品类集合链',
)


def _cat_expr(field: str) -> str:
    """品类字段表达式：TRIM + COALESCE，修复尾部空格问题"""
    return f"COALESCE(TRIM(o.{field}), '未知')"


def _excluded_cat_filter(field: str) -> str:
    """生成排除非产品品类的 SQL 片段"""
    placeholders = ",".join(["?"] * len(EXCLUDED_PRODUCT_CATEGORIES))
    return f"AND TRIM(COALESCE(o.{field}, '未知')) NOT IN ({placeholders})"


# L2043-2046: 关联缓存
_ASSOC_CACHE_MAX_SIZE = 100
_assoc_cache: OrderedDict[str, Any] = OrderedDict()
_assoc_cache_lock = __import__('threading').Lock()

# Sprint 170: 业务口径变更 — 品类回购分析由 RFM 8 象限改为 R 桶 (6 档 Recency + 1 TTL 汇总)
# 删除原 _RFM_SEGMENT_ORDER (8 象限), 改复公共 SSOT backend.semantic.segments.R_SEGMENT_ORDER
# 调用方更新 from backend.semantic.segments import R_SEGMENT_ORDER (Sprint 60+ 沉淀的公共 SSOT)

# L3172-3208: 复购日期范围解析
def _resolve_repurchase_date_ranges(
    start_date: str,
    end_date: str,
) -> Dict[str, Any]:
    """
    解析品类回购分析的日期范围（当前期/同比期/前年期）。
    复用 _resolve_date_ranges 的逻辑但简化接口。
    """
    from datetime import date as dt_date, timedelta as dt_timedelta
    import calendar

    sy, sm, sd = map(int, start_date.split("-"))
    ey, em, ed = map(int, end_date.split("-"))
    cutoff_date = dt_date(sy, sm, 1) - dt_timedelta(days=1)
    cutoff = cutoff_date.strftime("%Y-%m-%d")

    def _safe_date(y: int, m: int, d: int) -> dt_date:
        """闰年安全: 2-29 → 2-28"""
        max_day = calendar.monthrange(y, m)[1]
        return dt_date(y, m, min(d, max_day))

    # 同比期: 去年同期
    comp_start = _safe_date(sy - 1, sm, sd).strftime("%Y-%m-%d")
    comp_end = _safe_date(ey - 1, em, ed).strftime("%Y-%m-%d")
    comp_cutoff = (dt_date(sy - 1, sm, 1) - dt_timedelta(days=1)).strftime("%Y-%m-%d")

    # 前年期
    prev2_start = _safe_date(sy - 2, sm, sd).strftime("%Y-%m-%d")
    prev2_end = _safe_date(ey - 2, em, ed).strftime("%Y-%m-%d")
    prev2_cutoff = (dt_date(sy - 2, sm, 1) - dt_timedelta(days=1)).strftime("%Y-%m-%d")

    return {
        "current": (f"{start_date} 00:00:00", f"{end_date} 23:59:59", cutoff),
        "comp": (f"{comp_start} 00:00:00", f"{comp_end} 23:59:59", comp_cutoff),
        "prev2": (f"{prev2_start} 00:00:00", f"{prev2_end} 23:59:59", prev2_cutoff),
        "labels": (str(sy), str(sy - 1), str(sy - 2)),
    }
