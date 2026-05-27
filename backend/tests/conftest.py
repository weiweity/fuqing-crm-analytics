"""
Pytest fixtures for backend service tests.
"""
import pytest
import sys
from pathlib import Path

# Add backend/ to path for imports
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))


@pytest.fixture
def sample_rfm_record():
    """Sample RFM record for testing."""
    return {
        "user_id": "u001",
        "monetary": 500.0,
        "frequency": 3,
        "recency_days": 15,
        "r_score": 4,
        "f_score": 2,
        "m_score": 3,
    }


@pytest.fixture
def segment_ids():
    """All valid segment IDs (1-11, excluding 9)."""
    return [1, 2, 3, 4, 5, 6, 7, 8, 10, 11]


@pytest.fixture
def rfm_thresholds():
    """Standard RFM thresholds (from semantic/segments.py RFM_THRESHOLDS)."""
    from backend.semantic.segments import RFM_THRESHOLDS
    return RFM_THRESHOLDS
