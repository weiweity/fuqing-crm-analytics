"""
老客健康分析仪表盘 - API 路由

前缀: /api/v1/customer-health/*
注意: /api/v1/health 已被系统健康检查占用
"""

from fastapi import APIRouter, Query, Request, HTTPException
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

from backend.contracts.schemas import (
    HealthOverviewMetrics,
    RepurchaseCycleOverview,
    CohortRetentionResponse,
    ValueTierResponse,
    TierFlowResponse,
    RFMAnalysisResponse,
    NewCustomerConversionResponse,
    PromotionCalendarResponse,
    ChannelHealthScoresResponse,
    HealthTargetsResponse,
    ConfigHistoryResponse,
    AuditLogResponse,
    RFMConfigResponse,
    RFMThresholds,
    SegmentDefinitionItem,
)
from backend.services.health import overview as overview_service
from backend.services.health import repurchase as repurchase_service
from backend.services.health import tiers as tiers_service
from backend.services.health import tier_flow as tier_flow_service
from backend.services.health import rfm_analysis as rfm_analysis_service
from backend.services.health import conversion as conversion_service
from backend.services.health import promotion as promotion_service
from backend.services.health import config as health_config
from backend.services.health import channel_scores as channel_scores_service

router = APIRouter(prefix="/api/v1/customer-health", tags=["customer-health"])

# P0 fix: API Key 禁止默认值，必须在环境变量中设置
import os as _os
_HEALTH_API_KEY = _os.environ.get("HEALTH_API_KEY")
if not _HEALTH_API_KEY:
    raise RuntimeError(
        "HEALTH_API_KEY 环境变量未设置。请在 .env 或启动命令中配置一个强随机值。\n"
        "示例：export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    )


def _get_client_ip(request: Request) -> str:
    """从 Request 对象提取客户端 IP"""
    if request.client:
        return request.client.host
    return "unknown"


def _check_api_key(request: Request, x_api_key: str) -> None:
    """校验 API Key，失败时记录访问日志并抛出 401"""
    if x_api_key != _HEALTH_API_KEY:
        logger.warning(
            "Unauthorized access attempt to customer-health API",
            extra={"client_ip": _get_client_ip(request), "path": str(request.url.path)}
        )
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/overview", response_model=HealthOverviewMetrics)
def get_health_overview(
    analysis_date: str = Query(..., description="分析日期 YYYY-MM-DD"),
    period_days: int = Query(default=30, description="分析周期天数"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除渠道"),
    channel: Optional[str] = Query(default=None, description="指定渠道（单渠道过滤，优先于exclude_channels）"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """
    现状概览（运营日报）

    - 全店复购率、本品复购率
    - 老客GSV、老客人均、老客人数、老客GSV占比
    - 会员老客GSV、会员老客人均、会员老客人数、会员老客GSV占比
    - 近7日复购人数
    - 健康评分（0-100）+ 五维雷达数据 + 告警
    - 同比（去年同期同周期）；传 compare_start_date/compare_end_date 时使用自定义对比期
    """
    return overview_service.get_overview(
        analysis_date, period_days, exclude_channels, channel,
        compare_start_date=compare_start_date,
        compare_end_date=compare_end_date,
    )


@router.get("/targets", response_model=HealthTargetsResponse)
def get_health_targets(
    analysis_date: str = Query(..., description="分析日期 YYYY-MM-DD"),
    period_days: int = Query(default=30, description="分析周期天数"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除渠道"),
    channel: Optional[str] = Query(default=None, description="指定渠道"),
):
    """
    获取健康评分目标值（自动沿用去年同周期实际值）。

    用于雷达图动态targets和后端评分计算目标。
    """
    return overview_service.get_health_targets(analysis_date, period_days, exclude_channels, channel)


@router.get("/repurchase-cycle", response_model=RepurchaseCycleOverview)
def get_repurchase_cycle(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除渠道"),
    channel: Optional[str] = Query(default=None, description="指定渠道（单渠道过滤）"),
):
    """复购周期分析（间隔分布 + 品类对比）"""
    return repurchase_service.get_repurchase_cycle(start_date, end_date, exclude_channels, channel)


@router.get("/cohort-retention", response_model=CohortRetentionResponse)
def get_cohort_retention(
    start_month: str = Query(..., description="开始月份 YYYY-MM"),
    end_month: str = Query(..., description="结束月份 YYYY-MM"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除渠道"),
    channel: Optional[str] = Query(default=None, description="指定渠道（单渠道过滤）"),
):
    """Cohort留存矩阵（月度）"""
    return repurchase_service.get_cohort_retention(start_month, end_month, exclude_channels, channel)


@router.get("/value-tiers", response_model=ValueTierResponse)
def get_value_tiers(
    analysis_date: str = Query(..., description="分析日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=365, description="回溯天数"),
    exclude_channels: Optional[List[str]] = Query(default=None),
    channel: Optional[str] = Query(default=None, description="指定渠道（单渠道过滤）"),
):
    """客户价值分层（S/A/B/C × 高/中/低频）"""
    return tiers_service.get_value_tiers(analysis_date, lookback_days, exclude_channels, channel)


@router.get("/tier-flow", response_model=TierFlowResponse)
def get_tier_flow(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    metric_type: str = Query(default="GSV", description="GSV 或 GMV"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除渠道"),
    channel: Optional[str] = Query(default=None, description="指定渠道（单渠道过滤）"),
):
    """
    价值分层回购率流转看板

    逻辑同R区间分析，分层维度替换为历史累计GSV的S/A/B/C × 高/中/低频。
    返回3年对比（当前年/去年/前年）× 4种模式（全店/本渠道/会员/会员本渠道）。
    """
    return tier_flow_service.get_tier_flow(
        start_date=start_date,
        end_date=end_date,
        metric_type=metric_type,
        exclude_channels=exclude_channels,
        channel=channel,
    )


@router.get("/rfm-analysis", response_model=RFMAnalysisResponse)
def get_rfm_analysis(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    metric_type: str = Query(default="GSV", description="GSV 或 GMV"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除渠道"),
    channel: Optional[str] = Query(default=None, description="指定渠道（单渠道过滤）"),
):
    """
    RFM完整分析（8象限人群分群）

    基于R/F/M三维评分将用户划分为8个经典象限，计算各象限回购率。
    返回3年对比（当前年/去年/前年）× 4种模式（全店/本渠道/会员/会员本渠道）。
    """
    return rfm_analysis_service.get_rfm_analysis(
        start_date=start_date,
        end_date=end_date,
        metric_type=metric_type,
        exclude_channels=exclude_channels,
        channel=channel,
    )


@router.get("/new-customer-conversion", response_model=NewCustomerConversionResponse)
def get_new_customer_conversion(
    analysis_date: str = Query(..., description="分析日期"),
    lookback_months: int = Query(default=12, description="回溯月数"),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """新客转化追踪（7/30/90天漏斗 + 渠道质量）"""
    return conversion_service.get_new_customer_conversion(analysis_date, lookback_months, exclude_channels)


@router.get("/promotion-calendar", response_model=PromotionCalendarResponse)
def get_promotion_calendar(
    year: int = Query(default=2025, description="分析年份"),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """大促日历对比（大促 vs 日常）"""
    return promotion_service.get_promotion_calendar(year, exclude_channels)


@router.get("/config")
def get_health_config():
    """获取健康分析配置（阈值、权重、大促定义）"""
    return health_config.get_health_config()


@router.get("/config/rfm", response_model=RFMConfigResponse)
def get_rfm_config():
    """
    获取 RFM 评分阈值和 8 象限定义。

    数据直接来自 backend/semantic/segments.py 的 RFM_THRESHOLDS 和 SEGMENTS，
    确保前后端单一数据源，避免阈值不一致。
    """
    from backend.semantic.segments import RFM_THRESHOLDS, SEGMENTS

    thresholds = RFMThresholds(
        r=RFM_THRESHOLDS["r"],
        f=RFM_THRESHOLDS["f"],
        m=RFM_THRESHOLDS["m"],
    )

    segments = [
        SegmentDefinitionItem(
            segment_id=s.segment_id,
            name_cn=s.name_cn,
            name_en=s.name_en,
            r_high=s.r_high,
            f_high=s.f_high,
            m_high=s.m_high,
            description=s.description,
            color=s.color,
            priority=s.priority,
        )
        for s in SEGMENTS
        if s.segment_id <= 8
    ]

    return RFMConfigResponse(thresholds=thresholds, segments=segments)


# P1 fix: 配置写接口已移除（方案A）。配置修改请直接编辑后端 health_config.json 文件。
# 保留 GET 端点供前端只读展示。


@router.get("/config/history", response_model=ConfigHistoryResponse)
def get_config_history(
    request: Request,
    x_api_key: str = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100, description="返回最近N条记录"),
):
    """获取配置变更历史（自动备份列表）— 需鉴权"""
    _check_api_key(request, x_api_key)
    history = health_config.list_config_history(limit=limit)
    return ConfigHistoryResponse(history=history)


@router.get("/config/audit-log", response_model=AuditLogResponse)
def get_audit_log(
    request: Request,
    x_api_key: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=1000, description="返回最近N条记录"),
):
    """获取配置审计日志 — 需鉴权"""
    _check_api_key(request, x_api_key)
    logs = health_config.get_audit_log(limit=limit)
    return AuditLogResponse(logs=logs)


@router.get("/channel-health-scores", response_model=ChannelHealthScoresResponse)
def get_channel_health_scores(
    analysis_date: str = Query(..., description="分析日期 YYYY-MM-DD"),
    period_days: int = Query(default=30, description="分析周期天数"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除渠道"),
):
    """所有渠道健康评分对比（含去年同期 + YOY）"""
    return channel_scores_service.get_channel_health_scores(analysis_date, period_days, exclude_channels)



