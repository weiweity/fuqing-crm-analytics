"""品类分析服务 - Facade（向后兼容）"""

from backend.services.category_service._shared import (  # noqa: F401
    SPU_LEVELS, EXCLUDED_PRODUCT_CATEGORIES, _RFM_SEGMENT_ORDER,
    _normalize_date, _cat_expr, _excluded_cat_filter,
    _resolve_repurchase_date_ranges,
)
from backend.services.category_service.distribution import (  # noqa: F401
    get_category_distribution, get_category_segment_matrix,
)
from backend.services.category_service.user_profile import get_category_user_profile  # noqa: F401
from backend.services.category_service.overview import (  # noqa: F401
    get_category_overview, get_category_value_tier,
)
from backend.services.category_service.flow import (  # noqa: F401
    get_category_flow, get_category_flow_matrix, get_category_flow_association,
)
from backend.services.category_service.basket import get_market_basket  # noqa: F401
from backend.services.category_service.churn import (  # noqa: F401
    get_category_churn, get_category_daily_trend, get_category_user_list,
)
from backend.services.category_service.repurchase import (  # noqa: F401
    get_category_repurchase_flow, get_category_repurchase_flow_by_rfm,
)
