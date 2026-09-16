"""
指标目录（未接入查询）。

GSV 谓词仍引用 calculations.GSV_PREDICATE，供对照。出数 SQL 以各
service 为准。不要调用 get_sql() 当查询口径。

老客/新客 GSV：品类页见 category_service.overview
（窗口内购买且首购日 ≤ 该窗口月初的前一天）。本文件不存放那条 SQL。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend.semantic.calculations import GSV_AMOUNT_COL, GSV_PREDICATE


@dataclass
class MetricDefinition:
    """指标定义"""
    key: str                      # 英文标识（前端/后端通用）
    name: str                     # 中文名称
    sql_expr: str                 # DuckDB SQL 表达式（可直接用于 SELECT）
    description: str              # 业务口径说明
    filters: List[str] = field(default_factory=list)  # 依赖的过滤条件键（如 gsv, member）
    dimensions: List[str] = field(default_factory=list)  # 支持的分组维度
    format: str = "float"         # 输出格式: int, float, pct, currency
    precision: int = 2            # 小数精度


# ============================================================
# 核心指标定义
# ============================================================

METRICS: Dict[str, MetricDefinition] = {
    # 金额类
    "gmv": MetricDefinition(
        key="gmv",
        name="GMV",
        sql_expr="SUM(CASE WHEN is_goujinjin = FALSE THEN actual_amount ELSE 0 END)",
        description="商品交易总额，剔除购物金，含退款",
        dimensions=["date", "channel", "spu_tier", "spu_product_class", "spu_product_subclass", "province", "city", "segment"],
        format="currency",
    ),
    "gsv": MetricDefinition(
        key="gsv",
        name="GSV",
        sql_expr=f"SUM({GSV_AMOUNT_COL})",
        description="有效销售额，剔除购物金和退款订单",
        filters=["gsv"],
        dimensions=["date", "channel", "spu_tier", "spu_product_class", "spu_product_subclass", "province", "city", "segment"],
        format="currency",
    ),
    "member_gmv": MetricDefinition(
        key="member_gmv",
        name="会员GMV",
        sql_expr="SUM(CASE WHEN is_member = TRUE THEN actual_amount ELSE 0 END)",
        description="会员订单的GMV",
        filters=["member"],
        dimensions=["date", "channel", "spu_tier", "province", "segment"],
        format="currency",
    ),
    "member_gsv": MetricDefinition(
        key="member_gsv",
        name="会员GSV",
        sql_expr=f"SUM(CASE WHEN is_member = TRUE AND ({GSV_PREDICATE}) THEN actual_amount ELSE 0 END)",
        description="会员订单的有效销售额",
        filters=["member", "gsv"],
        dimensions=["date", "channel", "spu_tier", "province", "segment"],
        format="currency",
    ),

    # 人数类
    "total_users": MetricDefinition(
        key="total_users",
        name="购买人数",
        sql_expr="COUNT(DISTINCT user_id)",
        description="去重购买用户数",
        dimensions=["date", "channel", "spu_tier", "spu_product_class", "spu_product_subclass", "province", "city", "segment"],
        format="int",
    ),
    "gsv_users": MetricDefinition(
        key="gsv_users",
        name="有效购买人数",
        sql_expr="COUNT(DISTINCT user_id)",
        description="GSV口径下的去重购买用户数（在已过滤GSV的查询中使用）",
        dimensions=["date", "channel", "spu_tier", "spu_product_class", "spu_product_subclass", "province", "city", "segment"],
        format="int",
    ),
    "order_count": MetricDefinition(
        key="order_count",
        name="订单数",
        sql_expr="COUNT(DISTINCT order_id)",
        description="去重订单数",
        dimensions=["date", "channel", "spu_tier", "province", "segment"],
        format="int",
    ),
    "gsv_order_count": MetricDefinition(
        key="gsv_order_count",
        name="有效订单数",
        sql_expr=f"COUNT(DISTINCT CASE WHEN ({GSV_PREDICATE}) THEN order_id END)",
        description="GSV口径下的去重订单数",
        filters=["gsv"],
        dimensions=["date", "channel", "spu_tier", "province", "segment"],
        format="int",
    ),
    "member_users": MetricDefinition(
        key="member_users",
        name="会员人数",
        sql_expr="COUNT(DISTINCT CASE WHEN is_member = TRUE THEN user_id END)",
        description="去重会员用户数",
        filters=["member"],
        dimensions=["date", "channel", "spu_tier", "province", "segment"],
        format="int",
    ),

    # 均值类
    "avg_order_value": MetricDefinition(
        key="avg_order_value",
        name="客单价",
        sql_expr="AVG(actual_amount)",
        description="平均订单金额（GMV / 订单数）",
        dimensions=["date", "channel", "spu_tier", "province", "segment"],
        format="currency",
    ),
    "aus": MetricDefinition(
        key="aus",
        name="人均消费",
        sql_expr="SUM(actual_amount) / NULLIF(COUNT(DISTINCT user_id), 0)",
        description="人均消费金额（GSV / 有效人数）",
        dimensions=["channel", "spu_tier", "spu_product_class", "spu_product_subclass", "province", "segment"],
        format="currency",
    ),
    "member_aus": MetricDefinition(
        key="member_aus",
        name="会员人均消费",
        sql_expr="SUM(CASE WHEN is_member = TRUE THEN actual_amount ELSE 0 END) / NULLIF(COUNT(DISTINCT CASE WHEN is_member = TRUE THEN user_id END), 0)",
        description="会员人均消费金额",
        filters=["member"],
        dimensions=["channel", "spu_tier", "province", "segment"],
        format="currency",
    ),

    # 占比类（通常由 Python 层计算；下列表达式不能单独执行）
    "member_gsv_ratio": MetricDefinition(
        key="member_gsv_ratio",
        name="会员GSV占比",
        sql_expr="member_gsv / gsv",
        description="会员GSV / 总GSV（未接入查询）",
        filters=["member", "gsv"],
        dimensions=["channel", "spu_tier", "province", "segment"],
        format="pct",
    ),
}


class MetricRegistry:
    """指标目录。未接入查询，get_sql 仅供对照。"""

    def __init__(self):
        self._metrics: Dict[str, MetricDefinition] = {}
        for key, definition in METRICS.items():
            self.register(definition)

    def register(self, definition: MetricDefinition) -> None:
        if definition.key in self._metrics:
            raise ValueError(f"指标 '{definition.key}' 已存在")
        self._metrics[definition.key] = definition

    def get(self, key: str) -> Optional[MetricDefinition]:
        return self._metrics.get(key)

    def list_keys(self) -> List[str]:
        return list(self._metrics.keys())

    def list_by_dimension(self, dimension: str) -> List[MetricDefinition]:
        return [m for m in self._metrics.values() if dimension in m.dimensions]

    def get_sql(self, key: str, alias: Optional[str] = None) -> str:
        """获取指标SQL表达式，可指定别名"""
        m = self._metrics.get(key)
        if not m:
            raise KeyError(f"未注册指标: {key}")
        expr = m.sql_expr
        if alias:
            return f"{expr} AS {alias}"
        return f"{expr} AS {key}"


# 全局单例（进程内共享）
_registry = MetricRegistry()


def get_registry() -> MetricRegistry:
    return _registry
