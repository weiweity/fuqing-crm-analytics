"""
市场对焦路由

前缀: /api/v1/market-focus/*
"""

from fastapi import APIRouter, Query, HTTPException
import logging

from backend.contracts.schemas import StoreAssetResponse, ProductAssetResponse
from backend.services.asset_focus_service import (
    get_store_assets,
    get_product_assets,
    get_other_product_assets,
)

router = APIRouter(prefix="/api/v1/market-focus", tags=["市场对焦"])
_logger = logging.getLogger(__name__)


@router.get("/store-assets", response_model=StoreAssetResponse)
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
        _logger.error(f"[market-focus] store-assets error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"全店资产数据加载失败: {str(e)}")


@router.get("/product-assets", response_model=ProductAssetResponse)
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
        _logger.error(f"[market-focus] product-assets error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"单品资产数据加载失败: {str(e)}")


@router.get("/other-product-assets", response_model=ProductAssetResponse)
def get_market_focus_other_product_assets_api(
    weeks: int = Query(default=4, ge=1, le=12, description="周数：4/8/12"),
    days: int = Query(default=0, ge=0, le=90, description="日数：0=按周聚合，>0按日返回"),
):
    """
    市场对焦 - 单品资产-其他产品周数据

    读取 data3.csv，按产品ID映射到8个其他单品，
    展现形式同核心单品资产，返回资产总量 / 浅种草 / 深种草 / 首购资产 / 复购资产 / 连带资产
    含本周对比上周绝对值变化。
    """
    try:
        return get_other_product_assets(weeks=weeks, days=days)
    except Exception as e:
        _logger.error(f"[market-focus] other-product-assets error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"单品资产-其他产品数据加载失败: {str(e)}")
