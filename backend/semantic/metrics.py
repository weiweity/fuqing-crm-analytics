"""
芙清 CRM - 指标注册表 (Metrics Registry)

所有业务指标必须在此注册，包含：
- 指标唯一标识（snake_case）
- 中文名称
- 计算口径（SQL表达式或Python函数引用）
- 依赖的过滤条件
- 支持的分组维度

新增指标流程：
1. 在 METRICS 字典中新增定义
2. 在 MetricRegistry 中注册（自动完成）
3. 在 Service 中通过 MetricRegistry.get() 引用
4. 在 contracts/schemas.py 中更新 Response 字段（如有新增）
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


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
        sql_expr="SUM(CASE WHEN (is_goujinjin = FALSE AND order_status != '交易关闭' AND is_refund = FALSE) THEN actual_amount ELSE 0 END)",
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
        sql_expr="SUM(CASE WHEN is_member = TRUE AND (is_goujinjin = FALSE AND order_status != '交易关闭' AND is_refund = FALSE) THEN actual_amount ELSE 0 END)",
        description="会员订单的有效销售额",
        filters=["member", "gsv"],
        dimensions=["date", "channel", "spu_tier", "province", "segment"],
        format="currency",
    ),
    "old_gsv": MetricDefinition(
        key="old_gsv",
        name="老客GSV",
        sql_expr="SUM(CASE WHEN is_old = 1 THEN amount ELSE 0 END)",
        description="在窗口期内购买且首购日期 <= cutoff 的用户的GSV",
        filters=["gsv", "new_old"],
        dimensions=["channel", "spu_tier", "spu_product_class", "spu_product_subclass"],
        format="currency",
    ),
    "new_gsv": MetricDefinition(
        key="new_gsv",
        name="新客GSV",
        sql_expr="SUM(CASE WHEN is_new = 1 THEN amount ELSE 0 END)",
        description="在窗口期内首次购买（首购 > cutoff）的用户的GSV",
        filters=["gsv", "new_old"],
        dimensions=["channel", "spu_tier", "spu_product_class", "spu_product_subclass"],
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
        sql_expr="COUNT(DISTINCT CASE WHEN (is_goujinjin = FALSE AND order_status != '交易关闭' AND is_refund = FALSE) THEN order_id END)",
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
    "new_users": MetricDefinition(
        key="new_users",
        name="新客人数",
        sql_expr="COUNT(DISTINCT CASE WHEN is_new = 1 THEN user_id END)",
        description="窗口期内首次购买的用户数",
        filters=["new_old"],
        dimensions=["channel", "spu_tier", "spu_product_class", "spu_product_subclass"],
        format="int",
    ),
    "old_users": MetricDefinition(
        key="old_users",
        name="老客人数",
        sql_expr="COUNT(DISTINCT CASE WHEN is_old = 1 THEN user_id END)",
        description="窗口期内有购买且历史有购买的用户数",
        filters=["new_old"],
        dimensions=["channel", "spu_tier", "spu_product_class", "spu_product_subclass"],
        format="int",
    ),
    "member_new_users": MetricDefinition(
        key="member_new_users",
        name="会员新客人数",
        sql_expr="COUNT(DISTINCT CASE WHEN is_member = TRUE AND is_new = 1 THEN user_id END)",
        description="窗口期内首次购买的会员用户数",
        filters=["member", "new_old"],
        dimensions=["channel", "spu_tier", "spu_product_class", "spu_product_subclass"],
        format="int",
    ),
    "member_old_users": MetricDefinition(
        key="member_old_users",
        name="会员老客人数",
        sql_expr="COUNT(DISTINCT CASE WHEN is_member = TRUE AND is_old = 1 THEN user_id END)",
        description="窗口期内有购买的会员老客用户数",
        filters=["member", "new_old"],
        dimensions=["channel", "spu_tier", "spu_product_class", "spu_product_subclass"],
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

    # 占比类（通常由前端或Python层计算，SQL层提供原始值）
    "member_gsv_ratio": MetricDefinition(
        key="member_gsv_ratio",
        name="会员GSV占比",
        sql_expr="member_gsv / gsv",
        description="会员GSV / 总GSV",
        filters=["member", "gsv"],
        dimensions=["channel", "spu_tier", "province", "segment"],
        format="pct",
    ),
    "old_gsv_ratio": MetricDefinition(
        key="old_gsv_ratio",
        name="老客GSV占比",
        sql_expr="old_gsv / gsv",
        description="老客GSV / 总GSV",
        filters=["gsv", "new_old"],
        dimensions=["channel", "spu_tier", "spu_product_class", "spu_product_subclass"],
        format="pct",
    ),
}


class MetricRegistry:
    """指标注册表"""

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
