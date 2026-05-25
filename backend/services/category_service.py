"""品类分析服务 - Facade（向后兼容）"""
from backend.services.category_service import (
    get_category_distribution,
    get_category_segment_matrix,
    get_category_user_profile,
    get_category_overview,
    get_category_value_tier,
    get_category_flow,
    get_category_flow_matrix,
    get_category_flow_association,
    get_market_basket,
    get_category_churn,
    get_category_daily_trend,
    get_category_user_list,
    get_category_repurchase_flow,
    get_category_repurchase_flow_by_rfm,
)
