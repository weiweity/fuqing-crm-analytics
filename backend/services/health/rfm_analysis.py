"""向后兼容 shim"""
from .rfm_analysis import get_rfm_analysis  # noqa: F401

__all__ = ["get_rfm_analysis"]
