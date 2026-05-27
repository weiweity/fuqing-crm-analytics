"""
Tests for semantic/segments.py - SegmentRegistry and RFM threshold definitions.
"""
from backend.semantic.segments import (
    get_registry,
    SEGMENTS,
    RFM_THRESHOLDS,
)


class TestSegmentRegistry:
    """Test SegmentRegistry functionality."""

    def test_get_registry_singleton(self):
        """get_registry() returns the same instance."""
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_get_segment_by_id(self):
        """get() returns correct segment definition."""
        registry = get_registry()
        seg = registry.get(1)
        assert seg is not None
        assert seg.name_cn == "重要价值客户"
        assert seg.segment_id == 1

    def test_get_segment_invalid_id(self):
        """get() returns None for invalid segment ID."""
        registry = get_registry()
        assert registry.get(99) is None

    def test_list_all_returns_9_segments(self):
        """list_all() returns all 9 segments (8 quadrants + others)."""
        registry = get_registry()
        segs = registry.list_all()
        assert len(segs) == 9

    def test_get_name_cn(self):
        """get_name_cn() returns correct Chinese name."""
        registry = get_registry()
        assert registry.get_name_cn(1) == "重要价值客户"
        assert registry.get_name_cn(8) == "一般挽留客户"
        assert registry.get_name_cn(9) == "其他用户"
        assert registry.get_name_cn(99) == "其他"

    def test_get_color(self):
        """get_color() returns hex color string."""
        registry = get_registry()
        color = registry.get_color(1)
        assert color.startswith("#")
        assert len(color) == 7  # #RRGGBB format


class TestRFMScoreSQL:
    """Test RFM score SQL generation."""

    def test_r_score_sql_format(self):
        """build_r_score_sql() returns valid CASE WHEN SQL."""
        registry = get_registry()
        sql = registry.build_r_score_sql(RFM_THRESHOLDS["r"])
        assert "CASE" in sql
        assert "WHEN" in sql
        assert "recency_days" in sql
        assert "THEN 5" in sql  # Highest score for lowest recency

    def test_f_score_sql_format(self):
        """build_f_score_sql() returns valid CASE WHEN SQL."""
        registry = get_registry()
        sql = registry.build_f_score_sql(RFM_THRESHOLDS["f"])
        assert "CASE" in sql
        assert "frequency" in sql

    def test_m_score_sql_format(self):
        """build_m_score_sql() returns valid CASE WHEN SQL."""
        registry = get_registry()
        sql = registry.build_m_score_sql(RFM_THRESHOLDS["m"])
        assert "CASE" in sql
        assert "monetary" in sql


class TestSegmentCaseWhen:
    """Test segment CASE WHEN SQL generation (8象限)."""

    def test_build_segment_case_when_sql(self):
        """build_segment_case_when_sql() returns complete 8-quadrant CASE WHEN."""
        registry = get_registry()
        sql = registry.build_segment_case_when_sql()
        assert "CASE" in sql
        assert "THEN 1" in sql   # 重要价值客户
        assert "THEN 4" in sql   # 重要挽留客户
        assert "THEN 8" in sql   # 一般挽留客户
        assert "ELSE 9" in sql   # 其他用户 catch-all
        # 旧11象限ID 10、11 不应再出现
        assert "THEN 10" not in sql
        assert "THEN 11" not in sql

    def test_all_8_segments_covered(self):
        """All 8 quadrants appear in registry (plus segment 9 others)."""
        registry = get_registry()
        for seg_id in range(1, 9):
            seg = registry.get(seg_id)
            assert seg is not None, f"Segment {seg_id} not found in registry"

    def test_build_segment_name_case_when_sql(self):
        """build_segment_name_case_when_sql() covers all 9 segments."""
        registry = get_registry()
        sql = registry.build_segment_name_case_when_sql("cn")
        assert "重要价值客户" in sql
        assert "一般挽留客户" in sql
        assert "其他用户" in sql


class TestThresholds:
    """Test RFM threshold values."""

    def test_rfm_thresholds_match_strategy(self):
        """RFM thresholds match user requirements."""
        assert RFM_THRESHOLDS["r"] == [30, 90, 180, 365]
        assert RFM_THRESHOLDS["f"] == [1, 2, 3, 4]
        assert RFM_THRESHOLDS["m"] == [100, 300, 500, 1000]

    def test_f_score_five_threshold_is_5(self):
        """F 5分对应 >=5 次 (t[3] + 1 = 4 + 1 = 5)."""
        t = RFM_THRESHOLDS["f"]
        assert t[3] + 1 == 5

    def test_segment_priority_order(self):
        """Segments are sorted by priority in SEGMENTS list."""
        priorities = [s.priority for s in SEGMENTS]
        assert priorities == sorted(priorities)
