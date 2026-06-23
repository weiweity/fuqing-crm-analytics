"""
Sample CRM - 统一过滤条件构造器

禁止在任何 Service/ETL 中直接硬编码以下字符串：
- "order_status LIKE '%成功%'"
- "is_goujinjin = FALSE AND is_refund = FALSE"
- "pay_time >= ? AND pay_time <= ?"

所有 SQL 过滤条件必须通过 FilterBuilder 或 OrderFilters 生成。
"""

from enum import Enum
from typing import List, Optional, Tuple, Any

from backend.semantic.channels import UI_TO_DB as _CHANNEL_UI_TO_DB


class MetricType(str, Enum):
    """指标类型"""
    GMV = "GMV"
    GSV = "GSV"

# UI 组合渠道名 → 实际 DB 渠道名列表
_CHANNEL_GROUP_MAP = {
    "纯派样": ["U先派样", "百补派样"],
}

def _expand_channels(channels: List[str]) -> List[str]:
    """展开组合渠道为实际 DB 渠道名列表（去重）"""
    result = []
    seen = set()
    for ch in channels:
        group = _CHANNEL_GROUP_MAP.get(ch)
        if group:
            for db_ch in group:
                if db_ch not in seen:
                    seen.add(db_ch)
                    result.append(db_ch)
        else:
            db_name = _CHANNEL_UI_TO_DB.get(ch, ch)
            if db_name not in seen:
                seen.add(db_name)
                result.append(db_name)
    return result

# Public alias — service layer should use this instead of the private function
expand_channels = _expand_channels

# ── 有效订单基础口径（单一数据源） ──
# 无表前缀版（适用于单表查询 / 已有 FROM orders 无别名的场景）
VALID_ORDER_BASE = "is_goujinjin = FALSE AND order_status != '交易关闭'"
# 带表前缀版（适用于多表 JOIN、需要 o. 前缀区分的场景）
VALID_ORDER_BASE_PREFIXED = "o.is_goujinjin = FALSE AND o.order_status != '交易关闭'"


class OrderFilters:
    """
    订单表基础过滤条件（静态片段）。
    所有方法返回 (sql_fragment: str, params: list) 元组。
    """

    @staticmethod
    def order_status_ok() -> Tuple[str, List[Any]]:
        """订单状态正常（已废弃，请使用 valid_order()）

        注意：原实现使用 LIKE '%成功%'，与 valid_order() 的口径
        (order_status != '交易关闭' AND is_refund = FALSE) 不一致。
        为消除口径差异，已统一为 valid_order() 的语义。
        """
        return "order_status != '交易关闭' AND is_refund = FALSE", []

    @staticmethod
    def not_goujinjin() -> Tuple[str, List[Any]]:
        """非购物金"""
        return "is_goujinjin = FALSE", []

    @staticmethod
    def not_refund() -> Tuple[str, List[Any]]:
        """非退款（双重保险：排除'交易关闭'且is_refund=FALSE）"""
        return "order_status != '交易关闭' AND is_refund = FALSE", []

    @staticmethod
    def valid_order() -> Tuple[str, List[Any]]:
        """有效订单 = 非购物金 AND 非退款（GSV口径，双重保险）"""
        return "is_goujinjin = FALSE AND order_status != '交易关闭' AND is_refund = FALSE", []

    @staticmethod
    def gmv_base() -> Tuple[str, List[Any]]:
        """GMV 基础过滤 = 非购物金（含退款，但排除'交易关闭'）"""
        return "is_goujinjin = FALSE AND order_status != '交易关闭'", []

    @staticmethod
    def pay_time_between(start_dt: str, end_dt: str) -> Tuple[str, List[Any]]:
        """
        付款时间范围（闭区间）
        start_dt/end_dt 格式: "YYYY-MM-DD HH:MM:SS"
        """
        return "pay_time >= ? AND pay_time <= ?", [start_dt, end_dt]

    @staticmethod
    def pay_time_between_dates(start_date: str, end_date: str) -> Tuple[str, List[Any]]:
        """
        付款日期范围（闭区间，自动补全时间）
        start_date/end_date 格式: "YYYY-MM-DD"
        """
        return "pay_time >= ? AND pay_time <= ?", [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]

    @staticmethod
    def pay_time_lookback(date_str: str, lookback_days: int) -> Tuple[str, List[Any]]:
        """
        回溯期过滤：date_str 前 lookback_days 天 到 date_str 当天
        返回闭区间参数（用于 DuckDB 日期计算在 SQL 中完成，此处仅返回参数）
        """
        # 实际 SQL 中通常用 CROSS JOIN base_params 计算，这里返回参数供 base_params 使用
        from datetime import datetime, timedelta
        end_dt = datetime.strptime(date_str, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=lookback_days)
        return OrderFilters.pay_time_between_dates(start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))

    @staticmethod
    def is_member() -> Tuple[str, List[Any]]:
        """会员订单"""
        return "is_member = TRUE", []

    @staticmethod
    def channel_in(
        channels: List[str], table_alias: str = "o"
    ) -> Tuple[str, List[Any]]:
        """渠道 IN 列表（支持组合渠道自动展开）.

        Sprint 98 真治本: 默认使用 orders 的 ``o`` 别名，避免跟 JOIN 表的
        channel 字段冲突；传空字符串时保留无别名单表查询兼容性。
        """
        if not channels:
            return "1=1", []
        db_names = _expand_channels(channels)
        placeholders = ",".join(["?"] * len(db_names))
        prefix = f"{table_alias}." if table_alias else ""
        return f"{prefix}channel IN ({placeholders})", db_names

    @staticmethod
    def channel_not_in(
        channels: List[str], table_alias: str = "o"
    ) -> Tuple[str, List[Any]]:
        """渠道 NOT IN 列表（剔除低价等场景，支持组合渠道自动展开）.

        Sprint 98 真治本: 默认使用 orders 的 ``o`` 别名，避免跟 JOIN 表的
        channel 字段冲突；传空字符串时保留无别名单表查询兼容性。
        """
        if not channels:
            return "1=1", []
        db_names = _expand_channels(channels)
        placeholders = ",".join(["?"] * len(db_names))
        prefix = f"{table_alias}." if table_alias else ""
        return f"{prefix}channel NOT IN ({placeholders})", db_names

    @staticmethod
    def dimension_eq(dimension: str, value: str) -> Tuple[str, List[Any]]:
        """维度值精确匹配（带 COALESCE 空值保护）"""
        return f"COALESCE({dimension}, '未知') = ?", [value]


class FilterBuilder:
    """
    动态 SQL 过滤条件构造器。

    用法示例:
        fb = FilterBuilder()
        fb.with_metric_type(MetricType.GSV)
        fb.with_time_range("2026-01-01", "2026-01-31")
        fb.with_channels(["直播", "货架"])
        sql, params = fb.build()
        # sql => "pay_time >= ? AND pay_time <= ? AND order_status LIKE '%成功%' AND is_goujinjin = FALSE AND is_refund = FALSE AND o.channel IN (?,?)"
    """

    def __init__(self):
        self._metric_type: Optional[MetricType] = None
        self._start_dt: Optional[str] = None
        self._end_dt: Optional[str] = None
        self._channels: Optional[List[str]] = None
        self._exclude_channels: Optional[List[str]] = None
        self._segment_id: Optional[int] = None
        self._member_only: bool = False
        self._dimension: Optional[str] = None
        self._dimension_value: Optional[str] = None
        self._table_alias: str = "o"
        self._extra_conditions: List[Tuple[str, List[Any]]] = []

    def with_metric_type(self, metric_type: MetricType) -> "FilterBuilder":
        self._metric_type = metric_type
        return self

    def with_time_range(self, start_date: str, end_date: str) -> "FilterBuilder":
        """start_date/end_date 格式: YYYY-MM-DD"""
        self._start_dt = f"{start_date} 00:00:00"
        self._end_dt = f"{end_date} 23:59:59.999999"
        return self

    def with_lookback(self, date_str: str, lookback_days: int) -> "FilterBuilder":
        """设置回溯期"""
        from datetime import datetime, timedelta
        end_dt = datetime.strptime(date_str, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=lookback_days)
        return self.with_time_range(start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))

    def with_channels(self, channels: Optional[List[str]]) -> "FilterBuilder":
        self._channels = channels
        return self

    def with_table_alias(self, table_alias: str) -> "FilterBuilder":
        """设置 orders 表别名；空字符串用于无别名的旧单表查询."""
        self._table_alias = table_alias
        return self

    def with_exclude_channels(self, channels: Optional[List[str]]) -> "FilterBuilder":
        self._exclude_channels = channels
        return self

    def with_segment_id(self, segment_id: Optional[int]) -> "FilterBuilder":
        self._segment_id = segment_id
        return self

    def with_member_only(self, member_only: bool = True) -> "FilterBuilder":
        self._member_only = member_only
        return self

    def with_dimension(self, dimension: str, value: str) -> "FilterBuilder":
        self._dimension = dimension
        self._dimension_value = value
        return self

    def add_extra(self, sql_fragment: str, params: List[Any] = None) -> "FilterBuilder":
        self._extra_conditions.append((sql_fragment, params or []))
        return self

    def build(self) -> Tuple[str, List[Any]]:
        """
        构造完整的 WHERE 子句（不含 WHERE 关键字）和参数列表。
        返回: (condition_string, params_list)
        """
        conditions: List[str] = []
        params: List[Any] = []

        # 1. 时间范围
        if self._start_dt and self._end_dt:
            t_sql, t_params = OrderFilters.pay_time_between(self._start_dt, self._end_dt)
            conditions.append(t_sql)
            params.extend(t_params)

        # 2. 基础订单有效性（根据 metric_type 区分 GMV / GSV）
        if self._metric_type == MetricType.GMV:
            base_sql, base_params = OrderFilters.gmv_base()
        else:
            base_sql, base_params = OrderFilters.valid_order()
        conditions.append(base_sql)
        params.extend(base_params)

        # 3. 渠道筛选
        if self._channels:
            ch_sql, ch_params = OrderFilters.channel_in(
                self._channels, self._table_alias
            )
            conditions.append(ch_sql)
            params.extend(ch_params)

        # 3.5 排除渠道
        if self._exclude_channels:
            ex_sql, ex_params = OrderFilters.channel_not_in(
                self._exclude_channels, self._table_alias
            )
            conditions.append(ex_sql)
            params.extend(ex_params)

        # 4. 会员筛选
        if self._member_only:
            mem_sql, mem_params = OrderFilters.is_member()
            conditions.append(mem_sql)
            params.extend(mem_params)

        # 5. 维度筛选
        if self._dimension and self._dimension_value is not None:
            dim_sql, dim_params = OrderFilters.dimension_eq(self._dimension, self._dimension_value)
            conditions.append(dim_sql)
            params.extend(dim_params)

        # 6. 额外条件
        for sql_frag, extra_params in self._extra_conditions:
            conditions.append(sql_frag)
            params.extend(extra_params)

        return " AND ".join(conditions), params

    def build_amount_expr(self, column: str = "actual_amount") -> str:
        """
        构造金额聚合表达式。
        GMV => SUM(column)
        GSV => SUM(CASE WHEN valid_order THEN column ELSE 0 END)
        注意：build() 已经包含 valid_order 过滤，所以 GMV 场景下直接用 SUM(column) 即可。
        但如果需要在同一 SQL 中同时计算 GMV 和 GSV，需要用此方法生成 GSV 的 CASE WHEN。
        """
        if self._metric_type == MetricType.GSV:
            return f"SUM(CASE WHEN (is_goujinjin = FALSE AND order_status != '交易关闭' AND is_refund = FALSE) THEN {column} ELSE 0 END)"
        return f"SUM({column})"

    def build_count_expr(self, distinct_column: str = "order_id") -> str:
        """构造计数表达式（GSV 模式下只计有效订单）"""
        if self._metric_type == MetricType.GSV:
            return f"COUNT(DISTINCT CASE WHEN (is_goujinjin = FALSE AND order_status != '交易关闭' AND is_refund = FALSE) THEN {distinct_column} END)"
        return f"COUNT(DISTINCT {distinct_column})"


class AmountExprBuilder:
    """
    金额表达式构造器（用于同一 SQL 中混合计算 GMV 和 GSV）
    """

    @staticmethod
    def gsv(column: str = "actual_amount") -> str:
        return f"CASE WHEN (is_goujinjin = FALSE AND order_status != '交易关闭' AND is_refund = FALSE) THEN {column} ELSE 0 END"

    @staticmethod
    def gmv(column: str = "actual_amount") -> str:
        return column

    @staticmethod
    def sum_gsv(column: str = "actual_amount") -> str:
        return f"SUM(CASE WHEN (is_goujinjin = FALSE AND order_status != '交易关闭' AND is_refund = FALSE) THEN {column} ELSE 0 END)"

    @staticmethod
    def sum_gmv(column: str = "actual_amount") -> str:
        return f"SUM({column})"

    @staticmethod
    def conditional_sum(column: str = "actual_amount", condition: str = "1=1") -> str:
        """通用条件求和"""
        return f"SUM(CASE WHEN {condition} THEN {column} ELSE 0 END)"
