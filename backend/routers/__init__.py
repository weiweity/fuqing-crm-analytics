"""
backend.routers - API 路由包

所有路由统一通过 include_router 注册到 main.py。
每个路由模块暴露一个 `router` 实例。
"""

__all__ = [
    "auth_router",
    "health_router",
    "metrics_router",
    "flow_router",
    "asset_router",
    "category_router",
    "audience_router",
    "rfm_router",
    "sampling_router",
    "lifetime_value_router",
    "market_focus_router",
    "visitor_router",
    "export_router",
    "report_router",
    "ad_hoc_query_router",
    "session_router",
    "notifications_router",  # L4.75.3
    "login_request_router",  # L4.85 申请+同意 模式
    "admin_router",  # Sprint 205+ Admin Upload sprint 1 (v5 prompt)
]

from backend.routers.auth import router as auth_router
from backend.routers.health import router as health_router
from backend.routers.metrics import router as metrics_router
from backend.routers.flow import router as flow_router
from backend.routers.asset import router as asset_router
# Sprint 203 R9: geo_router 删除 (geo_service 保留供 report/export 用, 见 services/geo_service.py)
from backend.routers.category import router as category_router
from backend.routers.audience import router as audience_router
from backend.routers.rfm import router as rfm_router
from backend.routers.sampling import router as sampling_router
from backend.routers.lifetime_value import router as lifetime_value_router
# Sprint 203 R9: cohort_retention_router 删除 (前端 sampling 03-tab 解耦)
from backend.routers.market_focus import router as market_focus_router
from backend.routers.visitor import router as visitor_router
from backend.routers.export import router as export_router
from backend.routers.report import router as report_router
from backend.routers.ad_hoc_query import router as ad_hoc_query_router  # Sprint 188
from backend.routers.session import router as session_router
from backend.routers.notifications import router as notifications_router  # L4.75.3
from backend.routers.login_request import router as login_request_router  # L4.85 申请+同意 模式
from backend.routers.admin import router as admin_router  # Sprint 205+ Admin Upload sprint 1
