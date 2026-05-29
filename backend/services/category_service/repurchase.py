"""
向后兼容 shim
"""

from .repurchase.api import (
    get_category_repurchase_flow,
    get_category_repurchase_flow_by_rfm,
)

__all__ = [
    "get_category_repurchase_flow",
    "get_category_repurchase_flow_by_rfm",
]
