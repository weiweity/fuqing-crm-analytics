"""
品类分析路由

前缀: /api/v1/category/*
"""

from fastapi import APIRouter, Query
from typing import Optional, List

from backend.config import _default_start_date, _default_end_date
from backend.contracts.schemas import (
    CategoryDistributionResponse,
    CategoryOverviewResponse,
    CategorySegmentMatrixResponse,
    CategoryUserProfileResponse,
    CategoryValueTierResponse,
    CategoryRepurchaseFlowResponse,
    CategoryFlowResponse,
    CategoryFlowAssociationResponse,
    CategoryFlowMatrixResponse,
    CategoryChurnResponse,
    MarketBasketResponse,
    CategoryDailyTrendResponse,
    CategoryUserListResponse,
    AnchorMode,
    PathDepth,
)
from backend.services.category_service import (
    get_category_distribution,
    get_category_overview,
    get_category_segment_matrix,
    get_category_user_profile,
    get_category_value_tier,
    get_category_flow,
    get_category_flow_association,
    get_category_flow_matrix,
    get_category_churn,
    get_market_basket,
    get_category_daily_trend,
    get_category_user_list,
    get_category_repurchase_flow,
    get_category_repurchase_flow_by_rfm,
)

router = APIRouter(prefix="/api/v1/category", tags=["品类分析"])


@router.get("/distribution", response_model=CategoryDistributionResponse)
def get_category_distribution_api(
    date: str = Query(default=_default_end_date(), description="分析日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
    level: str = Query(default="category", description="category/type/tier/class/subclass/cosmetic/spec"),
    segment_id: Optional[int] = Query(default=None, description="象限ID筛选"),
    channel: Optional[str] = Query(default=None, description="渠道筛选"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
):
    """品类分布 (GSV口径)：返回各品类的用户数、GSV 及占比"""
    return get_category_distribution(date, lookback_days, level, segment_id, channel, exclude_channels)


@router.get("/overview", response_model=CategoryOverviewResponse)
def get_category_overview_api(
    start_date: str = Query(default=_default_start_date(), description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(default=_default_end_date(), description="结束日期 YYYY-MM-DD"),
    level: str = Query(default="type", description="category/type/tier/class/subclass/cosmetic/spec"),
    metric_type: str = Query(default="GSV", description="GSV 或 GMV"),
    channel: Optional[str] = Query(default=None, description="渠道筛选"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """
    品类概览（按Excel格式）

    返回两张表：
    - all_rows: 全店数据（全店/老客/新客 GSV、人数、AUS + 同比）
    - member_rows: 会员数据（全店/老客/新客 GSV、人数、AUS + 同比 + 会员占比）
    """
    return get_category_overview(
        start_date, end_date, level, metric_type, channel, exclude_channels,
        compare_start_date, compare_end_date
    )


@router.get("/segment", response_model=CategorySegmentMatrixResponse)
def get_category_segment_api(
    date: str = Query(default=_default_end_date(), description="分析日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
    level: str = Query(default="type", description="category/type/tier/class/subclass/cosmetic/spec"),
    top_n: int = Query(default=10, description="每个象限返回前 N 个品类"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
):
    """品类-象限交叉矩阵：返回各象限Top品类分布"""
    return get_category_segment_matrix(date, lookback_days, level, top_n, exclude_channels)


@router.get("/user-profile", response_model=CategoryUserProfileResponse)
def get_category_user_profile_api(
    date: str = Query(default=_default_end_date(), description="分析日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
    category: str = Query(default="护肤", description="一级品类筛选"),
    type: Optional[str] = Query(default=None, description="二级品类筛选"),
):
    """品类用户画像：返回某品类的用户特征（象限分布、省份分布、渠道分布）"""
    return get_category_user_profile(date, lookback_days, category, type)


@router.get("/value-tier", response_model=CategoryValueTierResponse)
def get_category_value_tier_api(
    start_date: str = Query(default=_default_start_date()),
    end_date: str = Query(default=_default_end_date()),
    level: str = Query(default="class"),
    channel: Optional[str] = Query(default=None),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """品类价值分层：返回各品类的价值分层分布（高/中/低价值用户占比）"""
    return get_category_value_tier(start_date, end_date, level, channel, exclude_channels)


@router.get("/repurchase-flow", response_model=CategoryRepurchaseFlowResponse)
def get_category_repurchase_flow_api(
    start_date: str = Query(default=_default_start_date()),
    end_date: str = Query(default=_default_end_date()),
    category: str = Query(default="B5面膜", description="目标品类"),
    level: str = Query(default="class"),
    metric_type: str = Query(default="GSV"),
    channel: Optional[str] = Query(default=None),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """
    品类回购分析

    返回同品回购+跨品类回购的RFM 8象限明细（含3年同比）。
    """
    return get_category_repurchase_flow(
        start_date, end_date, category, level, metric_type, channel, exclude_channels
    )


@router.get("/repurchase-flow-by-rfm", response_model=CategoryRepurchaseFlowResponse)
def get_category_repurchase_flow_by_rfm_api(
    start_date: str = Query(default=_default_start_date()),
    end_date: str = Query(default=_default_end_date()),
    category: str = Query(default="B5面膜", description="目标品类"),
    level: str = Query(default="class"),
    metric_type: str = Query(default="GSV"),
    channel: Optional[str] = Query(default=None),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """
    历史老客回购分析（RFM 8象限分群，不限品类）

    返回同品回购+跨品类回购的RFM 8象限明细（含3年同比）。
    与 repurchase-flow 的区别：hist_customers 包含所有历史老客（不限品类），
    按 RFM 象限分群后观察各象限在分析期内对目标品类的回购表现。
    """
    return get_category_repurchase_flow_by_rfm(
        start_date, end_date, category, level, metric_type, channel, exclude_channels
    )


@router.get("/flow", response_model=CategoryFlowResponse)
def get_category_flow_api(
    start_date: str = Query(default=_default_start_date()),
    end_date: str = Query(default=_default_end_date()),
    level: str = Query(default="class"),
    top_n: int = Query(default=10),
    window_days: int = Query(default=90),
    channel: Optional[str] = Query(default=None),
    exclude_channels: Optional[List[str]] = Query(default=None),
    target_category: Optional[str] = Query(default=None),
    anchor_mode: AnchorMode = Query(default=AnchorMode.every),
    path_depth: PathDepth = Query(default=PathDepth.d1),
):
    """品类流转（兼容旧接口，返回完整数据）"""
    return get_category_flow(
        start_date, end_date, level, top_n, window_days, channel, exclude_channels,
        target_category, anchor_mode.value, int(path_depth.value)
    )


@router.get("/flow/association", response_model=CategoryFlowAssociationResponse)
def get_category_flow_association_api(
    start_date: str = Query(default=_default_start_date()),
    end_date: str = Query(default=_default_end_date()),
    level: str = Query(default="class"),
    window_days: int = Query(default=90),
    channel: Optional[str] = Query(default=None),
    exclude_channels: Optional[List[str]] = Query(default=None),
    target_category: str = Query(..., description="目标品类名称"),
    anchor_mode: AnchorMode = Query(default=AnchorMode.last),
    path_depth: PathDepth = Query(default=PathDepth.d1),
):
    """
    品类流转 - 时序关联分析（买了产品A之后/之前买了什么）
    独立接口，支持内存缓存，响应更快。
    """
    return get_category_flow_association(
        start_date, end_date, level, window_days, channel, exclude_channels,
        target_category, anchor_mode.value, int(path_depth.value)
    )


@router.get("/flow/matrix", response_model=CategoryFlowMatrixResponse)
def get_category_flow_matrix_api(
    start_date: str = Query(default=_default_start_date()),
    end_date: str = Query(default=_default_end_date()),
    level: str = Query(default="class"),
    top_n: int = Query(default=10),
    window_days: int = Query(default=90),
    channel: Optional[str] = Query(default=None),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """
    品类流转 - 全局流转矩阵（首购→次购鸟瞰）
    独立接口，默认折叠时前端可不请求。
    """
    return get_category_flow_matrix(
        start_date, end_date, level, top_n, window_days, channel, exclude_channels
    )


@router.get("/churn", response_model=CategoryChurnResponse)
def get_category_churn_api(
    start_date: str = Query(default=_default_start_date()),
    end_date: str = Query(default=_default_end_date()),
    level: str = Query(default="class"),
    channel: Optional[str] = Query(default=None),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """品类流失分析：返回各品类的流失用户数、流失率及特征"""
    return get_category_churn(start_date, end_date, level, channel, exclude_channels)


@router.get("/basket", response_model=MarketBasketResponse)
def get_market_basket_api(
    start_date: str = Query(default=_default_start_date()),
    end_date: str = Query(default=_default_end_date()),
    target_category: str = Query(..., description="目标品类名称"),
    level: str = Query(default="class"),
    channel: Optional[str] = Query(default=None),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """
    购物篮分析

    返回目标品类的关联品类及YoY对比（支持度/置信度/提升度/连带客单价/GSV提升）。
    """
    return get_market_basket(start_date, end_date, target_category, level, channel, exclude_channels)


@router.get("/detail/daily-trend", response_model=CategoryDailyTrendResponse)
def get_category_daily_trend_api(
    category_id: str = Query(...),
    start_date: str = Query(default=_default_start_date()),
    end_date: str = Query(default=_default_end_date()),
    granularity: str = Query(default="daily"),
):
    """品类每日趋势：返回单个品类在时间维度上的GMV、用户数等指标趋势"""
    return get_category_daily_trend(category_id, start_date, end_date, granularity)


@router.get("/detail/user-list", response_model=CategoryUserListResponse)
def get_category_user_list_api(
    category_id: str = Query(...),
    start_date: str = Query(default=_default_start_date()),
    end_date: str = Query(default=_default_end_date()),
    limit: int = Query(default=100),
):
    """品类用户列表：返回单个品类的典型用户列表（高价值/高活跃/流失预警等）"""
    return get_category_user_list(category_id, start_date, end_date, limit)
