"""
Sample CRM - 维度注册表 (Dimensions Registry)

统一管理所有分析维度，包括：
- 维度字段名（数据库列名）
- 维度中文名
- 默认空值填充
- 是否支持下钻

维度列表必须与 strategy_config.yaml 和前端筛选器保持一致。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class DimensionDefinition:
    key: str                # 维度标识（英文，API参数用）
    column: str             # 数据库列名
    name: str               # 中文名称
    default_value: str = "未知"
    drillable: bool = False # 是否支持下钻
    parent: Optional[str] = None  # 父维度key（用于下钻层级）
    order_by: str = "gmv"   # 默认排序指标


DIMENSIONS: Dict[str, DimensionDefinition] = {
    "channel": DimensionDefinition(
        key="channel",
        column="channel",
        name="渠道",
        default_value="其他",
        order_by="gmv",
    ),
    "spu_tier": DimensionDefinition(
        key="spu_tier",
        column="spu_tier",
        name="商品梯队",
        default_value="未知",
        order_by="gmv",
    ),
    "spu_product_class": DimensionDefinition(
        key="spu_product_class",
        column="spu_product_class",
        name="单品归类",
        default_value="未知",
        drillable=True,
        parent="spu_category",
        order_by="gmv",
    ),
    "spu_product_subclass": DimensionDefinition(
        key="spu_product_subclass",
        column="spu_product_subclass",
        name="单品细分",
        default_value="未知",
        drillable=True,
        parent="spu_product_class",
        order_by="gmv",
    ),
    "spu_category": DimensionDefinition(
        key="spu_category",
        column="spu_category",
        name="品类销售",
        default_value="未知",
        drillable=True,
        order_by="gmv",
    ),
    "spu_type": DimensionDefinition(
        key="spu_type",
        column="spu_type",
        name="正装/小样",
        default_value="未知",
        order_by="gmv",
    ),
    "spu_cosmetic": DimensionDefinition(
        key="spu_cosmetic",
        column="spu_cosmetic",
        name="妆/械",
        default_value="未知",
        order_by="gmv",
    ),
    "province": DimensionDefinition(
        key="province",
        column="province",
        name="省份",
        default_value="未知",
        order_by="user_count",
    ),
    "city": DimensionDefinition(
        key="city",
        column="city",
        name="城市",
        default_value="未知",
        drillable=True,
        parent="province",
        order_by="user_count",
    ),
    "segment": DimensionDefinition(
        key="segment",
        column="segment_id",
        name="人群象限",
        default_value="其他",
        order_by="user_count",
    ),
}


class DimensionRegistry:
    """维度注册表"""

    def __init__(self):
        self._dims: Dict[str, DimensionDefinition] = {}
        for key, d in DIMENSIONS.items():
            self.register(d)

    def register(self, definition: DimensionDefinition) -> None:
        self._dims[definition.key] = definition

    def get(self, key: str) -> Optional[DimensionDefinition]:
        return self._dims.get(key)

    def list_keys(self) -> List[str]:
        return list(self._dims.keys())

    def get_group_expr(self, key: str, table_alias: str = "o") -> str:
        """获取 GROUP BY 用的 SQL 表达式（带 COALESCE）"""
        d = self._dims.get(key)
        if not d:
            raise KeyError(f"未注册维度: {key}")
        return f"COALESCE({table_alias}.{d.column}, '{d.default_value}')"

    def get_select_expr(self, key: str, alias: str = "dim_key", table_alias: str = "o") -> str:
        """获取 SELECT 用的 SQL 表达式"""
        expr = self.get_group_expr(key, table_alias)
        return f"{expr} AS {alias}"


# 全局单例
_registry = DimensionRegistry()


def get_registry() -> DimensionRegistry:
    return _registry
