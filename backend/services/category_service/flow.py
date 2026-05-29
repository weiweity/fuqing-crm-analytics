"""
向后兼容 shim
"""

from .flow.association import (
    get_category_flow,
    get_category_flow_association,
)
from .flow.matrix import (
    get_category_flow_matrix,
)

__all__ = [
    "get_category_flow",
    "get_category_flow_matrix",
    "get_category_flow_association",
]
