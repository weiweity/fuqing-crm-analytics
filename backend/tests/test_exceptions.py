"""
Tests for backend/services/exceptions.py - unified exception types.
"""
import pytest
from backend.services.exceptions import (
    ServiceError,
    ValidationError,
    NotFoundError,
    DataSourceError,
    ComputationError,
)


class TestExceptionTypes:
    """Test custom exception classes."""

    def test_service_error_status_code(self):
        """ServiceError maps to HTTP 500."""
        exc = ServiceError("test error")
        assert exc.status_code == 500
        assert exc.detail["error"] == "SERVICE_ERROR"
        assert exc.detail["message"] == "test error"

    def test_validation_error_status_code(self):
        """ValidationError maps to HTTP 422."""
        exc = ValidationError("invalid param")
        assert exc.status_code == 422
        assert exc.detail["error"] == "VALIDATION_ERROR"

    def test_not_found_error_status_code(self):
        """NotFoundError maps to HTTP 404."""
        exc = NotFoundError("resource not found")
        assert exc.status_code == 404
        assert exc.detail["error"] == "NOT_FOUND"

    def test_data_source_error(self):
        """DataSourceError is a subclass of ServiceError."""
        exc = DataSourceError("DB connection failed")
        assert exc.status_code == 500
        assert exc.detail["error"] == "DATA_SOURCE_ERROR"

    def test_computation_error(self):
        """ComputationError is a subclass of ServiceError."""
        exc = ComputationError("calculation failed")
        assert exc.status_code == 500
        assert exc.detail["error"] == "COMPUTATION_ERROR"

    def test_service_error_custom_code(self):
        """ServiceError accepts custom error code."""
        exc = ServiceError("custom error", error_code="CUSTOM_CODE")
        assert exc.detail["error"] == "CUSTOM_CODE"
