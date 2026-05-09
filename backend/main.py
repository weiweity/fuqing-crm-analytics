"""
芙清 CRM 客户分析系统 - FastAPI 后端
Week 1-4 API
"""

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Optional, List, Any, Dict
from datetime import datetime, timedelta, date

from backend.services.exceptions import ServiceError, ValidationError, NotFoundError

from backend.contracts.schemas import (
    DateRangeResponse,
    OverviewMetrics,
    TrendData,
    FlowMatrixResponse,
    FlowSankeyResponse,
    ChurnDistributionResponse,
    ChurnUsersResponse,
    AssetSummaryResponse,
    AssetTrendResponse,
    GeoDistributionResponse,
    GeoSegmentMatrixResponse,
    GeoTrendResponse,
    CategoryDistributionResponse,
    CategoryOverviewResponse,
    CategorySegmentMatrixResponse,
    CategoryUserProfileResponse,
    CategoryValueTierResponse,
    CategoryFlowResponse,
    CategoryChurnResponse,
    MarketBasketResponse,
    CategoryRepurchaseFlowResponse,
    CategoryDailyTrendResponse,
    CategoryUserListResponse,
    ExportPPTRequest,
    ExportPPTResponse,
    TemplatesResponse,
    AudienceTableRequest,
    AudienceTableResponse,
    AudienceSummaryResponse,
    RFMRFlowResponse,
    RFMFRFlowResponse,
    RFMMFlowResponse,
    SegmentOrdersResponse,
    StoreAssetResponse,
    ProductAssetResponse,
    VisitorSummaryResponse,
    VisitorDailyTrendResponse,
    BreakdownRequest,
    BreakdownResponse,
    SamplingROIResponse,
    SamplingLockAnalysisResponse,
)

from backend.services.metrics_service import (
    get_overview_metrics,
    get_daily_trend,
    get_audience_table,
    calculate_audience_summary,
)
from backend.services.flow_service import (
    get_flow_matrix,
    get_flow_sankey
)
from backend.services.rfm_service import (
    get_rfm_r_flow,
    get_rfm_f_flow,
    get_rfm_m_flow,
    get_segment_orders,
)
from backend.services.churn_service import (
    get_churn_risk_distribution,
    get_churn_risk_users
)
from backend.services.asset_service import (
    get_asset_summary,
    get_asset_trend
)
from backend.services.geo_service import (
    get_geo_distribution,
    get_geo_segment_matrix,
    get_geo_trend
)
from backend.services.category_service import (
    get_category_distribution,
    get_category_overview,
    get_category_segment_matrix,
    get_category_user_profile,
    get_category_value_tier,
    get_category_flow,
    get_category_churn,
    get_market_basket,
    get_category_daily_trend,
    get_category_user_list,
    get_category_repurchase_flow,
)
from backend.services.export_service import (
    generate_ppt_report,
    get_available_templates
)
from backend.services.report_service import (
    get_report_summary
)
from backend.services.dmp_asset_service import (
    get_store_assets,
    get_product_assets,
    get_other_product_assets,
)
from backend.services.visitor_service import (
    get_visitor_summary,
    get_visitor_daily_trend,
)
from backend.services.breakdown_service import (
    calculate_one_click_breakdown,
)
from backend.services.sampling_service import (
    get_sampling_roi,
    get_sampling_lock_analysis,
)

app = FastAPI(
    title="芙清 CRM 客户分析系统 API",
    description="提供核心指标、RFM、人群流转等数据 API",
    version="1.0.0"
)

# CORS 配置（生产环境移除 localhost，仅保留实际内网域名）
import os
_DEFAULT_ORIGINS = "http://192.168.101.171:5173"
_CORS_ORIGINS = os.environ.get("CORS_ORIGINS", _DEFAULT_ORIGINS).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _CORS_ORIGINS if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# ─────────────────────────────────────────────────────────────
# 结构化访问日志中间件
# ─────────────────────────────────────────────────────────────
import time
import logging

_access_logger = logging.getLogger("access")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000
    _access_logger.info(
        "API request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": request.client.host if request.client else "unknown",
        }
    )
    return response


# ─────────────────────────────────────────────────────────────
# 全局认证中间件（除认证路由和健康检查外，所有 API 需 Bearer token）
# ─────────────────────────────────────────────────────────────
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # 白名单：登录/校验接口、健康检查无需 token
    if path.startswith("/api/v1/auth/") or path == "/api/v1/health":
        return await call_next(request)
    # 放行 OPTIONS 预检请求（CORS 预检不应被认证拦截）
    if request.method == "OPTIONS":
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "未提供认证令牌"})

    token = auth[7:]
    # 延迟导入避免循环依赖
    from backend.routers.auth import _verify_token
    if _verify_token(token) is None:
        return JSONResponse(status_code=401, content={"detail": "登录已过期，请重新登录"})

    return await call_next(request)


# ─────────────────────────────────────────────────────────────
# 全局异常处理器（统一错误响应格式）
# ─────────────────────────────────────────────────────────────
@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    return JSONResponse(status_code=exc.status_code, content=exc.detail)


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    return JSONResponse(status_code=exc.status_code, content=exc.detail)


@app.exception_handler(NotFoundError)
async def not_found_error_handler(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=exc.status_code, content=exc.detail)


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    """未捕获的异常返回 500，避免堆栈信息暴露"""
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "message": "服务器内部错误，请稍后重试"}
    )


# @app.get("/")
# def root():
#     """健康检查"""
#     return {"status": "ok", "service": "芙清 CRM 客户分析系统", "version": "1.0.0"}


@app.get("/api/v1/metrics/overview", response_model=OverviewMetrics)
def get_metrics_overview(
    start_date: str = Query(default="2026-01-01", description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(default="2026-01-31", description="结束日期 YYYY-MM-DD"),
    metric_type: str = Query(default="GMV", description="指标类型：GMV 或 GSV"),
    channel: Optional[str] = Query(default=None, description="渠道筛选（UI渠道名）"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """
    获取核心指标概览

    返回:
    - GMV、订单数、客单价
    - 新老客数量和 GMV
    - 会员指标
    - 环比、同比变化
    """
    return get_overview_metrics(start_date, end_date, metric_type, channel, exclude_channels,
                                compare_start_date, compare_end_date)


@app.get("/api/v1/metrics/trend", response_model=TrendData)
def get_metrics_trend(
    start_date: str = Query(default="2026-01-01", description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(default="2026-01-31", description="结束日期 YYYY-MM-DD"),
    metric_type: str = Query(default="GMV", description="指标类型：GMV 或 GSV"),
    channel: Optional[str] = Query(default=None, description="渠道筛选（UI渠道名）"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """
    获取每日趋势数据

    返回每日 GMV、订单数、用户数，用于绘制折线图
    """
    return get_daily_trend(start_date, end_date, metric_type, channel, exclude_channels,
                           compare_start_date, compare_end_date)


@app.get("/api/v1/health")
def health_check():
    """系统健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "duckdb"
    }


# ============================================================
# Week 3: 人群流转 API
# ============================================================


@app.get("/api/v1/flow/matrix", response_model=FlowMatrixResponse)
def get_flow_matrix_api(
    from_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    to_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
    metric_type: str = Query(default="GMV", description="GMV/GSV"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表")
):
    """
    人群流转矩阵

    返回 9x9 矩阵 + 留存/升级/降级汇总指标
    """
    return get_flow_matrix(from_date, to_date, lookback_days, metric_type, exclude_channels)


@app.get("/api/v1/flow/sankey", response_model=FlowSankeyResponse)
def get_flow_sankey_api(
    from_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    to_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
    metric_type: str = Query(default="GMV", description="GMV/GSV"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表")
):
    """
    桑基图数据

    返回 nodes + links，用于可视化
    """
    return get_flow_sankey(from_date, to_date, lookback_days, metric_type, exclude_channels)


# ============================================================
# Week 3: 流失预警 API
# ============================================================

@app.get("/api/v1/churn/distribution", response_model=ChurnDistributionResponse)
def get_churn_distribution_api(
    date: str = Query(..., description="分析日期 YYYY-MM-DD"),
    segment_id: Optional[int] = Query(default=None, description="象限ID筛选"),
    churn_mode: str = Query(default="dynamic", description="dynamic 或 fixed"),
    fixed_threshold: int = Query(default=60, description="固定阈值天数"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表")
):
    """
    各象限流失风险分布
    """
    return get_churn_risk_distribution(date, segment_id, churn_mode, fixed_threshold, exclude_channels)


@app.get("/api/v1/churn/risk", response_model=ChurnUsersResponse)
def get_churn_risk_users_api(
    date: str = Query(..., description="分析日期 YYYY-MM-DD"),
    risk_level: Optional[str] = Query(default=None, description="high/medium/low"),
    segment_id: Optional[int] = Query(default=None, description="象限ID筛选"),
    churn_mode: str = Query(default="dynamic", description="dynamic 或 fixed"),
    fixed_threshold: int = Query(default=60, description="固定阈值天数"),
    limit: int = Query(default=100, description="返回条数上限"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表")
):
    """
    高流失风险用户列表
    """
    return get_churn_risk_users(date, risk_level, segment_id, churn_mode, fixed_threshold, limit, exclude_channels)


# ============================================================
# Week 3: 资产分析 API
# ============================================================

@app.get("/api/v1/asset/summary", response_model=AssetSummaryResponse)
def get_asset_summary_api(
    date: str = Query(default="2026-03-19", description="分析日期 YYYY-MM-DD")
):
    """
    资产汇总（订单 GMV 模拟）
    """
    return get_asset_summary(date)


@app.get("/api/v1/asset/trend", response_model=AssetTrendResponse)
def get_asset_trend_api(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    granularity: str = Query(default="month", description="month 或 week")
):
    """
    资产趋势（多月/周）
    """
    return get_asset_trend(start_date, end_date, granularity)


# ============================================================
# Week 4: 地域分析 API
# ============================================================

@app.get("/api/v1/geo/distribution", response_model=GeoDistributionResponse)
def get_geo_distribution_api(
    date: str = Query(default="2026-03-19", description="分析日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
    level: str = Query(default="省份", description="省份/城市"),
    top_n: int = Query(default=50, description="返回前 N 条"),
    segment_id: Optional[int] = Query(default=None, description="象限ID筛选"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表")
):
    """
    地域分布

    返回各省/市的用户数、GMV 及占比
    """
    return get_geo_distribution(date, lookback_days, level, top_n, segment_id, exclude_channels)


@app.get("/api/v1/geo/segment", response_model=GeoSegmentMatrixResponse)
def get_geo_segment_api(
    date: str = Query(default="2026-03-19", description="分析日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
    top_n: int = Query(default=10, description="每个象限返回前 N 个省份"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表")
):
    """
    地域-象限交叉矩阵

    返回各象限Top省份分布
    """
    return get_geo_segment_matrix(date, lookback_days, top_n, exclude_channels)


@app.get("/api/v1/geo/trend", response_model=GeoTrendResponse)
def get_geo_trend_api(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
    top_n: int = Query(default=5, description="追踪前 N 个省份"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表")
):
    """
    地域趋势（多时间点）

    返回各省份随时间的变化趋势
    """
    return get_geo_trend(start_date, end_date, lookback_days, top_n, exclude_channels)


# ============================================================
# Week 4: 品类分析 API
# ============================================================

@app.get("/api/v1/category/distribution", response_model=CategoryDistributionResponse)
def get_category_distribution_api(
    date: str = Query(default="2026-03-19", description="分析日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
    level: str = Query(default="category", description="category/type/tier/class/subclass/cosmetic/spec"),
    segment_id: Optional[int] = Query(default=None, description="象限ID筛选"),
    channel: Optional[str] = Query(default=None, description="渠道筛选"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表")
):
    """
    品类分布 (GSV口径)

    返回各品类的用户数、GSV 及占比
    """
    return get_category_distribution(date, lookback_days, level, segment_id, channel, exclude_channels)


@app.get("/api/v1/category/overview", response_model=CategoryOverviewResponse)
def get_category_overview_api(
    start_date: str = Query(default="2026-04-01", description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(default="2026-04-17", description="结束日期 YYYY-MM-DD"),
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
    return get_category_overview(start_date, end_date, level, metric_type, channel, exclude_channels, compare_start_date, compare_end_date)


@app.get("/api/v1/category/segment", response_model=CategorySegmentMatrixResponse)
def get_category_segment_api(
    date: str = Query(default="2026-03-19", description="分析日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
    level: str = Query(default="type", description="category/type/tier/class/subclass/cosmetic/spec"),
    top_n: int = Query(default=10, description="每个象限返回前 N 个品类"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表")
):
    """
    品类-象限交叉矩阵

    返回各象限Top品类分布
    """
    return get_category_segment_matrix(date, lookback_days, level, top_n, exclude_channels)


@app.get("/api/v1/category/user-profile", response_model=CategoryUserProfileResponse)
def get_category_user_profile_api(
    date: str = Query(default="2026-03-19", description="分析日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
    category: str = Query(default="护肤", description="一级品类筛选"),
    type: Optional[str] = Query(default=None, description="二级品类筛选")
):
    """
    品类用户画像

    返回某品类的用户特征（象限分布、省份分布、渠道分布）
    """
    return get_category_user_profile(date, lookback_days, category, type)


# ============================================================
# Week 5-6: 品类看板 v2 API
# ============================================================

@app.get("/api/v1/category/value-tier", response_model=CategoryValueTierResponse)
def get_category_value_tier_api(
    start_date: str = Query(default="2026-04-01"),
    end_date: str = Query(default="2026-04-20"),
    level: str = Query(default="class"),
    channel: Optional[str] = Query(default=None),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """
    品类价值分层

    返回各品类的价值分层分布（高/中/低价值用户占比）
    """
    return get_category_value_tier(start_date, end_date, level, channel, exclude_channels)


@app.get("/api/v1/category/repurchase-flow", response_model=CategoryRepurchaseFlowResponse)
def get_category_repurchase_flow_api(
    start_date: str = Query(default="2026-01-01"),
    end_date: str = Query(default="2026-03-31"),
    category: str = Query(default="B5面膜", description="目标品类"),
    level: str = Query(default="class"),
    metric_type: str = Query(default="GSV"),
    channel: Optional[str] = Query(default=None),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """
    品类回购分析

    返回同品回购+跨品类回购的R区间明细（含3年同比）
    """
    return get_category_repurchase_flow(
        start_date, end_date, category, level, metric_type, channel, exclude_channels
    )


@app.get("/api/v1/category/flow", response_model=CategoryFlowResponse)
def get_category_flow_api(
    start_date: str = Query(default="2026-04-01"),
    end_date: str = Query(default="2026-04-20"),
    level: str = Query(default="class"),
    top_n: int = Query(default=10),
    window_days: int = Query(default=90),
    channel: Optional[str] = Query(default=None),
    exclude_channels: Optional[List[str]] = Query(default=None),
    target_category: Optional[str] = Query(default=None),
):
    """
    品类流转

    返回品类间的用户流转矩阵和桑基图数据。传入 target_category 时返回前后置购买关联分析。
    """
    return get_category_flow(start_date, end_date, level, top_n, window_days, channel, exclude_channels, target_category)


@app.get("/api/v1/category/churn", response_model=CategoryChurnResponse)
def get_category_churn_api(
    start_date: str = Query(default="2026-04-01"),
    end_date: str = Query(default="2026-04-20"),
    level: str = Query(default="class"),
    channel: Optional[str] = Query(default=None),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """
    品类流失分析

    返回各品类的流失用户数、流失率及特征
    """
    return get_category_churn(start_date, end_date, level, channel, exclude_channels)


@app.get("/api/v1/category/basket", response_model=MarketBasketResponse)
def get_market_basket_api(
    start_date: str = Query(default="2026-04-01"),
    end_date: str = Query(default="2026-04-20"),
    target_category: str = Query(..., description="目标品类名称"),
    level: str = Query(default="class"),
    channel: Optional[str] = Query(default=None),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """
    购物篮分析

    返回目标品类的关联品类及YoY对比（Support/Confidence/Lift）
    """
    return get_market_basket(start_date, end_date, target_category, level, channel, exclude_channels)


@app.get("/api/v1/category/detail/daily-trend", response_model=CategoryDailyTrendResponse)
def get_category_daily_trend_api(
    category_id: str = Query(...),
    start_date: str = Query(default="2026-04-01"),
    end_date: str = Query(default="2026-04-20"),
    granularity: str = Query(default="daily"),
):
    """
    品类每日趋势

    返回单个品类在时间维度上的GMV、用户数等指标趋势
    """
    return get_category_daily_trend(category_id, start_date, end_date, granularity)


@app.get("/api/v1/category/detail/user-list", response_model=CategoryUserListResponse)
def get_category_user_list_api(
    category_id: str = Query(...),
    start_date: str = Query(default="2026-04-01"),
    end_date: str = Query(default="2026-04-20"),
    limit: int = Query(default=100),
):
    """
    品类用户列表

    返回单个品类的典型用户列表（高价值/高活跃/流失预警等）
    """
    return get_category_user_list(category_id, start_date, end_date, limit)


# ============================================================
# Week 4: PPT 导出 API
# ============================================================

@app.post("/api/v1/export/ppt", response_model=ExportPPTResponse)
def export_ppt_api(request: ExportPPTRequest):
    """
    生成 PPT 报告

    支持模块: cover, metrics, segments, geo, category, actions
    """
    result = generate_ppt_report(
        report_type=request.report_type,
        start_date=request.start_date,
        end_date=request.end_date,
        modules=request.modules,
        template=request.template
    )
    return ExportPPTResponse(**result)


@app.get("/api/v1/export/templates", response_model=TemplatesResponse)
def get_templates_api():
    """
    获取可用模板列表

    返回模板ID、名称、描述和支持的模块
    """
    return get_available_templates()


# ============================================================
# Week 4: 报告汇总 API
# ============================================================

@app.get("/api/v1/report/summary")
def get_report_summary_api(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数")
):
    """
    获取报告汇总

    整合所有数据：核心指标、象限分布、地域分布、品类分布
    """
    return get_report_summary(start_date, end_date, lookback_days)


# ============================================================
# Week 1 大改版：人群看板 API
# ============================================================

@app.get("/api/v1/audience/table", response_model=AudienceTableResponse)
def get_audience_table_api(
    dimension: str = Query(default="channel", description="维度：channel 或 spu_tier"),
    mode: str = Query(default="mtd", description="模式：mtd 或 free"),
    start_date: Optional[str] = Query(default=None, description="开始日期（free模式必填）"),
    end_date: Optional[str] = Query(default=None, description="结束日期（free模式必填）"),
    channels: Optional[str] = Query(default=None, description="逗号分隔的渠道列表"),
    metric_type: str = Query(default="GMV", description="指标类型：GMV 或 GSV"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表")
):
    """
    人群看板主表

    默认 MTD 同月对比（当年MTD vs 去年MTD），
    支持自由时间段筛选和渠道筛选。

    返回 24 个指标字段：
    - 全店：gsv_users, gsv, aus, old_users, old_gsv, old_aus, old_gsv_ratio, old_users_ratio
    - 新客：new_users, new_gsv, new_aus, new_gsv_ratio, new_users_ratio
    - 会员：member_users, member_gsv, member_aus, member_gs_v_ratio, member_users_ratio
    - 会员老客：member_old_users, member_old_gs_v, member_old_aus, member_old_gs_v_ratio, member_old_users_ratio
    - 会员新客：member_new_users, member_new_gs_v, member_new_aus, member_new_gs_v_ratio, member_new_users_ratio
    """
    # 解析渠道列表
    channel_list = None
    if channels:
        channel_list = [ch.strip() for ch in channels.split(",") if ch.strip()]

    # 参数校验
    if mode == "free" and (not start_date or not end_date):
        raise ValueError("free 模式需要传入 start_date 和 end_date")

    return get_audience_table(
        dimension=dimension,
        mode=mode,
        start_date=start_date,
        end_date=end_date,
        channels=channel_list,
        metric_type=metric_type,
        exclude_channels=exclude_channels,
    )


# ============================================================
# 人群看板 - 汇总（30指标对比 + 渠道概览）
# ============================================================

@app.get("/api/v1/audience/summary", response_model=AudienceSummaryResponse)
def get_audience_summary_api(
    year: int = Query(default=2026, description="对比基准年（仅影响列标签）"),
    metric_type: str = Query(default="GSV", description="GMV 或 GSV"),
    period: Optional[str] = Query(default=None, description="WTD / MTD / YTD / Q1-Q4"),
    start_date: Optional[str] = Query(default=None, description="开始日期 YYYY-MM-DD（period为空时使用）"),
    end_date: Optional[str] = Query(default=None, description="结束日期 YYYY-MM-DD（period为空时使用）"),
    channel: Optional[str] = Query(default=None, description="渠道筛选"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """
    人群看板汇总接口

    一次返回三块数据：
    - Panel A：30指标对比（__TOTAL__ 全店，3年同比）
    - Panel B：渠道概览-全店（各渠道 GSV，3年同比 + 占比；选渠道时仅返回该渠道）
    - Panel C：渠道概览-会员（各渠道会员 GSV，3年同比 + 占比）

    period 联动：WTD/MTD/YTD/Q1-Q4 使用 PeriodBuilder 计算三周期；
    自定义日期时（start_date/end_date）使用用户指定范围。
    compare_start_date/compare_end_date 可覆盖自动推算的对比期（仅替换 Y-1 对比期，Y-2 归零）。
    """
    from backend.semantic.time import PeriodBuilder

    resolved_start = start_date
    resolved_end = end_date

    # 当指定了 period 且无自定义日期时，用 PeriodBuilder 计算
    if period and not (start_date and end_date):
        try:
            pb = getattr(PeriodBuilder, period.lower())(today=date.today())
            resolved_start = pb["current"].start
            resolved_end = pb["current"].end
        except (AttributeError, KeyError):
            pass  # 回退到 MTD 默认

    result = calculate_audience_summary(
        year=year,
        metric_type=metric_type,
        start_date=resolved_start,
        end_date=resolved_end,
        channel=channel,
        exclude_channels=exclude_channels,
        compare_start_date=compare_start_date,
        compare_end_date=compare_end_date,
    )
    return result


# ============================================================
# RFM - R区间流转看板
# ============================================================

@app.get("/api/v1/rfm/r-flow", response_model=RFMRFlowResponse)
def get_rfm_r_flow_api(
    year: int = Query(default=2026, description="对比基准年（仅影响列标签）"),
    metric_type: str = Query(default="GSV", description="GMV 或 GSV"),
    period: Optional[str] = Query(default=None, description="WTD / MTD / YTD / Q1-Q4"),
    start_date: Optional[str] = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="结束日期 YYYY-MM-DD"),
    channel: Optional[str] = Query(default=None, description="渠道筛选"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """
    RFM - R区间流转看板
    """
    return get_rfm_r_flow(
        year=year,
        metric_type=metric_type,
        period=period,
        start_date=start_date,
        end_date=end_date,
        channel=channel,
        exclude_channels=exclude_channels,
        compare_start_date=compare_start_date,
        compare_end_date=compare_end_date,
    )


@app.get("/api/v1/rfm/f-flow", response_model=RFMFRFlowResponse)
def get_rfm_f_flow_api(
    year: int = Query(default=2026, description="对比基准年（仅影响列标签）"),
    metric_type: str = Query(default="GSV", description="GMV 或 GSV"),
    period: Optional[str] = Query(default=None, description="WTD / MTD / YTD / Q1-Q4"),
    start_date: Optional[str] = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="结束日期 YYYY-MM-DD"),
    channel: Optional[str] = Query(default=None, description="渠道筛选"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """
    RFM - F区间流转看板
    """
    return get_rfm_f_flow(
        year=year,
        metric_type=metric_type,
        period=period,
        start_date=start_date,
        end_date=end_date,
        channel=channel,
        exclude_channels=exclude_channels,
        compare_start_date=compare_start_date,
        compare_end_date=compare_end_date,
    )


@app.get("/api/v1/rfm/m-flow", response_model=RFMMFlowResponse)
def get_rfm_m_flow_api(
    year: int = Query(default=2026, description="对比基准年（仅影响列标签）"),
    metric_type: str = Query(default="GSV", description="GMV 或 GSV"),
    period: Optional[str] = Query(default=None, description="WTD / MTD / YTD / Q1-Q4"),
    start_date: Optional[str] = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="结束日期 YYYY-MM-DD"),
    channel: Optional[str] = Query(default=None, description="渠道筛选"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """
    RFM - M区间流转看板
    """
    return get_rfm_m_flow(
        year=year,
        metric_type=metric_type,
        period=period,
        start_date=start_date,
        end_date=end_date,
        channel=channel,
        exclude_channels=exclude_channels,
        compare_start_date=compare_start_date,
        compare_end_date=compare_end_date,
    )


@app.get("/api/v1/rfm/segment-orders", response_model=SegmentOrdersResponse)
def get_segment_orders_api(
    dimension: str = Query(..., description="维度：r / f / m"),
    segment: str = Query(..., description="区间名称（如 近1个月已购客）"),
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    metric_type: str = Query(default="GSV", description="GMV 或 GSV"),
    mode: str = Query(default="all", description="all / member / same_channel / member_same_channel"),
    channel: Optional[str] = Query(default=None, description="渠道筛选"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
):
    """
    RFM 区间订单明细导出

    根据维度和区间，返回该区间内所有用户的订单号明细，用于二次营销。
    """
    return get_segment_orders(
        dimension=dimension,
        segment=segment,
        start_date=start_date,
        end_date=end_date,
        metric_type=metric_type,
        mode=mode,
        channel=channel,
        exclude_channels=exclude_channels,
    )


# ============================================================
# 老客健康分析仪表盘 (Phase 1)
# ============================================================
from backend.routers import health as health_router
app.include_router(health_router.router)

# ============================================================
# 认证路由 (Auth)
# ============================================================
from backend.routers import auth as auth_router
app.include_router(auth_router.router)


# ============================================================
# 市场对焦板块 (Market Focus)
# ============================================================

@app.get("/api/v1/market-focus/store-assets", response_model=StoreAssetResponse)
def get_market_focus_store_assets_api(
    weeks: int = Query(default=4, ge=1, le=12, description="周数：4/8/12"),
    days: int = Query(default=0, ge=0, le=90, description="日数：0=按周聚合，>0按日返回"),
):
    """
    市场对焦 - 全店资产数据

    读取 data2.csv（日级），
    days>0时按日返回最近N天数据，days=0时按自然周聚合（取每周最后一天）。
    返回 TOTAL资产总量 / Discover发现 / Engage种草 / Enthuse互动 / Perform行动 / Initial首购 / Numerous复购 / Keen至爱
    含环比绝对值变化。
    """
    try:
        return get_store_assets(weeks=weeks, days=days)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[market-focus] store-assets error: {e}", exc_info=True)
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"全店资产数据加载失败: {str(e)}")


@app.get("/api/v1/market-focus/product-assets", response_model=ProductAssetResponse)
def get_market_focus_product_assets_api(
    weeks: int = Query(default=4, ge=1, le=12, description="周数：4/8/12"),
    days: int = Query(default=0, ge=0, le=90, description="日数：0=按周聚合，>0按日返回"),
):
    """
    市场对焦 - 单品资产周数据

    读取 data3.csv，按产品ID映射到7个核心单品，
    返回资产总量 / 浅种草 / 深种草 / 首购资产 / 复购资产 / 连带资产
    含本周对比上周绝对值变化。
    """
    try:
        return get_product_assets(weeks=weeks, days=days)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[market-focus] product-assets error: {e}", exc_info=True)
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"单品资产数据加载失败: {str(e)}")


@app.get("/api/v1/market-focus/other-product-assets", response_model=ProductAssetResponse)
def get_market_focus_other_product_assets_api(
    weeks: int = Query(default=4, ge=1, le=12, description="周数：4/8/12"),
    days: int = Query(default=0, ge=0, le=90, description="日数：0=按周聚合，>0按日返回"),
):
    """
    市场对焦 - 单品资产-其他产品周数据

    读取 data3.csv，按产品ID映射到8个其他单品（医用凝胶/医用洁面/黑膜/胶原水乳/白膜/祛痘精华/水杨酸涂抹面膜/凉茶面膜），
    展现形式同核心单品资产，返回资产总量 / 浅种草 / 深种草 / 首购资产 / 复购资产 / 连带资产
    含本周对比上周绝对值变化。
    """
    try:
        return get_other_product_assets(weeks=weeks, days=days)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[market-focus] other-product-assets error: {e}", exc_info=True)
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"单品资产-其他产品数据加载失败: {str(e)}")


# ============================================================
# 访客入会率 (Visitor Member Join Rate)
# ============================================================

@app.get("/api/v1/visitor/summary", response_model=VisitorSummaryResponse)
def get_visitor_summary_api(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """
    访客入会率汇总

    返回指定周期内的：
    - 访客数、新增会员数、入会率
    - 去年同期对比（访客数YoY、新增会员数YoY、入会率百分点差）
    - 环比（访客数MoM、新增会员数MoM、入会率百分点差）
    """
    return get_visitor_summary(start_date, end_date, compare_start_date, compare_end_date)


@app.get("/api/v1/visitor/daily-trend", response_model=VisitorDailyTrendResponse)
def get_visitor_daily_trend_api(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """
    访客入会率每日趋势

    返回每日访客数、新增会员数、入会率，含对比期同天数据。
    """
    data = get_visitor_daily_trend(start_date, end_date, compare_start_date, compare_end_date)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "data": data,
    }


# ============================================================
# 一键拆解 API
# ============================================================

@app.post("/api/v1/breakdown/one-click", response_model=BreakdownResponse)
def get_one_click_breakdown_api(request: BreakdownRequest):
    """
    一键拆解 v2 — GSV only

    支持两种模式：
    - forward（顺拆）：从现状数据预估，计算目标gap
    - reverse（倒拆）：从目标反推各R区间/渠道所需人数/UV

    老客拆解：按R区间（6档）× F段（F>1/F=1）逐层预估
    新客拆解：按渠道漏斗逐渠道预估

    示例请求（顺拆）:
    ```json
    {
        "target_gmv": 5000000,
        "activity_start": "2026-06-01",
        "activity_end": "2026-06-18",
        "breakdown_mode": "forward",
        "old_customer_ratio_target": 0.6
    }
    ```

    示例请求（倒拆）:
    ```json
    {
        "target_gmv": 5000000,
        "activity_start": "2026-06-01",
        "activity_end": "2026-06-18",
        "breakdown_mode": "reverse",
        "old_customer_ratio_target": 0.6
    }
    ```
    """
    return calculate_one_click_breakdown(
        target_gmv=request.target_gmv,
        activity_start=request.activity_start,
        activity_end=request.activity_end,
        last_year_start=request.last_year_start,
        last_year_end=request.last_year_end,
        old_customer_ratio_target=request.old_customer_ratio_target,
        breakdown_mode=request.breakdown_mode,
    )


# ============================================================
# 派样看板 (Sampling Dashboard)
# ============================================================

@app.get("/api/v1/sampling/roi", response_model=SamplingROIResponse)
def get_sampling_roi_api(
    start_date: str = Query(default="2026-01-01", description="派样起始日期"),
    end_date: str = Query(default="2026-01-31", description="派样结束日期"),
    window_days: int = Query(default=30, description="回购窗口天数：7/30/60"),
    level: str = Query(default="spu_category", description="品类维度：spu_category/spu_tier/spu_product_class"),
    channel: Optional[str] = Query(default=None, description="筛选特定派样渠道"),
):
    """
    派样 ROI 分析

    返回 U先派样 / 百补派样 在指定时间窗口内的：
    - 渠道汇总：派样人数、7/30/60天回购人数、回购率、贡献GSV、AUS
    - 品类明细：每个渠道×品类的回购情况（含同品类回购）
    """
    return get_sampling_roi(start_date, end_date, window_days, level, channel)


@app.get("/api/v1/sampling/lock-analysis", response_model=SamplingLockAnalysisResponse)
def get_sampling_lock_analysis_api(
    campaign_name: str = Query(default="618节日", description="大促名称：618节日/双11/38节日"),
    year: int = Query(default=2026, description="年份"),
):
    """
    0.01派样锁权分析

    返回指定大促周期的：
    - 锁权人数、锁权率（UV→锁权）
    - 转化人数、转化率、贡献GSV、AUS
    - 新客锁权人数、新客占比、新客转化率、新客GSV
    - 同比对比（去年同大促）
    """
    return get_sampling_lock_analysis(campaign_name, year)


# ─────────────────────────────────────────────────────────────
# 静态文件托管（构建后的前端 dist 目录，支持 Vue Router history 模式）
# 注：当前开发阶段前后端分离，前端通过 Vite dev server (5173) 访问，
#     如需生产部署，取消下面注释即可让后端托管前端构建产物。
# ─────────────────────────────────────────────────────────────
# class SPAStaticFiles(StaticFiles):
#     """自定义 StaticFiles，在 404 时 fallback 到 index.html（SPA 支持）"""
#     async def get_response(self, path: str, scope):
#         try:
#             return await super().get_response(path, scope)
#         except Exception as exc:
#             # Starlette StaticFiles 在不匹配时抛出 HTTPException(404)
#             from starlette.exceptions import HTTPException as StarletteHTTPException
#             if isinstance(exc, StarletteHTTPException) and exc.status_code == 404 and self.html:
#                 return await super().get_response("index.html", scope)
#             raise
#
#
# _DIST_DIR = Path(__file__).parent.parent / "frontend-vue3" / "dist"
# app.mount("/", SPAStaticFiles(directory=str(_DIST_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000,
                reload=True,
                reload_dirs=["/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/backend"])
