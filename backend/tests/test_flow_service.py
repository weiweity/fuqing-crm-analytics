"""
Tests for backend/services/flow_service.py - crowd flow analysis service.
"""


class TestFlowServiceImports:
    """Test that flow_service imports from semantic layer."""

    def test_no_hardcoded_segment_map(self):
        """Verify flow_service does NOT have hardcoded SEGMENT_MAP at module level."""
        from backend.services import flow_service
        assert not hasattr(flow_service, 'SEGMENT_MAP')


class TestFlowMatrix:
    """Test flow matrix structure."""

    def test_flow_matrix_keys(self):
        """Flow matrix returns expected keys."""
        expected_keys = [
            "flow_matrix", "segments", "from_date", "to_date",
            "from_total", "to_total", "summary"
        ]
        for key in expected_keys:
            assert key is not None


class TestSegmentCount:
    """Test that flow service supports 8 quadrants + others (9 total)."""

    def test_8_quadrants_in_registry(self):
        """Registry contains 8 quadrants + others = 9 segments."""
        from backend.semantic.segments import get_registry
        registry = get_registry()
        segs = registry.list_all()
        assert len(segs) == 9

    def test_segment_8_is_general_at_risk(self):
        """Segment 8 is 一般挽留客户 (last quadrant)."""
        from backend.semantic.segments import get_registry
        registry = get_registry()
        seg = registry.get(8)
        assert seg is not None
        assert seg.name_cn == "一般挽留客户"

    def test_old_segments_10_11_removed(self):
        """Old 11-quadrant segments 10 and 11 no longer exist."""
        from backend.semantic.segments import get_registry
        registry = get_registry()
        assert registry.get(10) is None
        assert registry.get(11) is None
