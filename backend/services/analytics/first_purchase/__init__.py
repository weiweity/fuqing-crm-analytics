"""Offline first-purchase product-path JSON compute. No HTTP, worker, or DuckDB."""

from backend.services.analytics.first_purchase.compute import execute_first_purchase_path_query

__all__ = ["execute_first_purchase_path_query"]
