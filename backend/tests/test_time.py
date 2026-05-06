"""
Tests for backend/semantic/time.py - PeriodBuilder and DateRange.

Covers:
- DateRange: start_dt/end_dt properties, cutoff calculation
- PeriodBuilder.wtd: week-to-date periods
- PeriodBuilder.mtd: month-to-date periods
- PeriodBuilder.ytd: year-to-date periods
- PeriodBuilder.free: custom date range periods
- PeriodBuilder.lookback: lookback period
- PeriodBuilder.mom: month-over-month period
- PeriodBuilder.yoy: year-over-year period
"""
import pytest
from datetime import date, timedelta
from backend.semantic.time import PeriodBuilder, DateRange


class TestDateRange:
    """Test DateRange dataclass."""

    def test_start_dt_property(self):
        dr = DateRange(start="2026-01-01", end="2026-01-31", cutoff="2025-12-31")
        assert dr.start_dt == "2026-01-01 00:00:00"

    def test_end_dt_property(self):
        dr = DateRange(start="2026-01-01", end="2026-01-31", cutoff="2025-12-31")
        assert dr.end_dt == "2026-01-31 23:59:59"

    def test_cutoff_is_start_minus_one(self):
        """Cutoff should be 1 day before start (for new/old customer classification)."""
        dr = DateRange(start="2026-04-01", end="2026-04-30", cutoff="2026-03-31")
        assert dr.cutoff == "2026-03-31"


class TestPeriodBuilderWTD:
    """Test WTD (week-to-date) period construction."""

    def test_returns_three_periods(self):
        result = PeriodBuilder.wtd(date(2026, 5, 4))  # Monday
        assert "current" in result
        assert "comparison" in result
        assert "prev2" in result

    def test_current_starts_on_monday(self):
        """Current period should start on Monday."""
        result = PeriodBuilder.wtd(date(2026, 5, 4))  # Monday
        # yesterday = May 3 (Sunday), so current Monday = Apr 27
        assert result["current"].start == "2026-04-27"

    def test_current_ends_yesterday(self):
        """Current period should end on yesterday (t-1)."""
        result = PeriodBuilder.wtd(date(2026, 5, 4))
        assert result["current"].end == "2026-05-03"

    def test_comparison_is_previous_week(self):
        """Comparison period should be 7 days before current."""
        result = PeriodBuilder.wtd(date(2026, 5, 4))
        cur_start = result["current"].start
        comp_start = result["comparison"].start
        diff = (
            date.fromisoformat(cur_start) - date.fromisoformat(comp_start)
        ).days
        assert diff == 7

    def test_prev2_is_previous_year_same_week(self):
        """prev2 should be approximately same week last year."""
        result = PeriodBuilder.wtd(date(2026, 5, 4))
        cur_year = date.fromisoformat(result["current"].start).year
        prev2_year = date.fromisoformat(result["prev2"].start).year
        assert prev2_year == cur_year - 1


class TestPeriodBuilderMTD:
    """Test MTD (month-to-date) period construction."""

    def test_returns_three_periods(self):
        result = PeriodBuilder.mtd(date(2026, 5, 4))
        assert len(result) == 3
        assert "current" in result
        assert "comparison" in result
        assert "prev2" in result

    def test_current_starts_on_first_of_month(self):
        result = PeriodBuilder.mtd(date(2026, 5, 4))
        assert result["current"].start == "2026-05-01"

    def test_current_ends_yesterday(self):
        result = PeriodBuilder.mtd(date(2026, 5, 4))
        assert result["current"].end == "2026-05-03"

    def test_comparison_is_same_month_last_year(self):
        result = PeriodBuilder.mtd(date(2026, 5, 4))
        assert result["comparison"].start == "2025-05-01"
        assert result["comparison"].end == "2025-05-03"

    def test_prev2_is_two_years_ago(self):
        result = PeriodBuilder.mtd(date(2026, 5, 4))
        assert result["prev2"].start == "2024-05-01"


class TestPeriodBuilderYTD:
    """Test YTD (year-to-date) period construction."""

    def test_current_starts_jan_1(self):
        result = PeriodBuilder.ytd(date(2026, 5, 4))
        assert result["current"].start == "2026-01-01"

    def test_current_ends_yesterday(self):
        result = PeriodBuilder.ytd(date(2026, 5, 4))
        assert result["current"].end == "2026-05-03"

    def test_comparison_is_last_year(self):
        result = PeriodBuilder.ytd(date(2026, 5, 4))
        assert result["comparison"].start == "2025-01-01"
        assert result["comparison"].end == "2025-05-03"


class TestPeriodBuilderFree:
    """Test free date range period construction."""

    def test_current_matches_input(self):
        result = PeriodBuilder.free("2026-01-15", "2026-02-15")
        assert result["current"].start == "2026-01-15"
        assert result["current"].end == "2026-02-15"

    def test_comparison_shifts_one_year(self):
        result = PeriodBuilder.free("2026-01-15", "2026-02-15")
        assert result["comparison"].start == "2025-01-15"
        assert result["comparison"].end == "2025-02-15"

    def test_prev2_shifts_two_years(self):
        result = PeriodBuilder.free("2026-01-15", "2026-02-15")
        assert result["prev2"].start == "2024-01-15"
        assert result["prev2"].end == "2024-02-15"

    def test_cutoff_is_start_minus_one(self):
        result = PeriodBuilder.free("2026-01-15", "2026-02-15")
        assert result["current"].cutoff == "2026-01-14"


class TestPeriodBuilderLookback:
    """Test lookback period construction."""

    def test_lookback_90_days(self):
        result = PeriodBuilder.lookback("2026-04-20", 90)
        assert result.end == "2026-04-20"
        assert result.start == "2026-01-20"  # 90 days back

    def test_lookback_30_days(self):
        result = PeriodBuilder.lookback("2026-04-20", 30)
        assert result.end == "2026-04-20"
        assert result.start == "2026-03-21"  # 30 days back


class TestPeriodBuilderMom:
    """Test MOM (month-over-month) period construction."""

    def test_mom_period_length_matches(self):
        """Previous period should have same length as current."""
        result = PeriodBuilder.mom("2026-03-01", "2026-03-31")
        current_days = 31  # March has 31 days
        prev_days = (
            date.fromisoformat(result.end) - date.fromisoformat(result.start)
        ).days + 1
        assert prev_days == current_days

    def test_mom_ends_day_before_current(self):
        result = PeriodBuilder.mom("2026-03-01", "2026-03-31")
        assert result.end == "2026-02-28"  # day before March 1


class TestPeriodBuilderYoY:
    """Test YOY (year-over-year) period construction."""

    def test_yoy_shifts_one_year(self):
        result = PeriodBuilder.yoy("2026-01-15", "2026-02-15")
        assert result.start == "2025-01-15"
        assert result.end == "2025-02-15"

    def test_yoy_cutoff(self):
        result = PeriodBuilder.yoy("2026-01-15", "2026-02-15")
        assert result.cutoff == "2025-01-14"


class TestNormalizeDateString:
    """Test date string normalization."""

    def test_date_object(self):
        assert PeriodBuilder.normalize_date_string(date(2026, 5, 4)) == "2026-05-04"

    def test_string_passthrough(self):
        assert PeriodBuilder.normalize_date_string("2026-05-04") == "2026-05-04"

    def test_datetime_string_truncated(self):
        assert PeriodBuilder.normalize_date_string("2026-05-04 12:00:00") == "2026-05-04"
