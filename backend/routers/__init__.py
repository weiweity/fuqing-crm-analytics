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
    "geo_router",
    "category_router",
    "audience_router",
    "rfm_router",
    "sampling_router",
    "market_focus_router",
    "visitor_router",
    "export_router",
    "report_router",
]

from backend.routers.auth import router as auth_router
from backend.routers.health import router as health_router
from backend.routers.metrics import router as metrics_router
from backend.routers.flow import router as flow_router
from backend.routers.asset import router as asset_router
from backend.routers.geo import router as geo_router
from backend.routers.category import router as category_router
from backend.routers.audience import router as audience_router
from backend.routers.rfm import router as rfm_router
from backend.routers.sampling import router as sampling_router
from backend.routers.market_focus import router as market_focus_router
from backend.routers.visitor import router as visitor_router
from backend.routers.export import router as export_router
from backend.routers.report import router as report_router
