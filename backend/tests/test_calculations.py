"""
Tests for backend/semantic/calculations.py - unified calculation rules (L4.81 治本 no *100 契约).

Covers:
- yoy_absolute: absolute value YOY (amounts, counts) → returns raw ratio (no *100, e.g. 0.25 = +25% / 100)
- yoy_ratio: ratio/percentage YOY (raw ratio diff no *100, e.g. 0.05 = +5pp / 100)
- yoy_repurchase_rate: repurchase rate YOY (alias of yoy_ratio)
- mom_absolute: absolute value MOM → returns raw ratio (no *100)
- mom_ratio: ratio/percentage MOM → returns raw ratio (no *100)
- safe_ratio: safe division (zero-denominator protection)
- percentage_to_ratio / ratio_to_percentage: unit conversion

L4.81 治本契约变更 (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用, 跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用):
- 旧契约 (已废): backend *100, frontend 直接显示 (e.g. 25.0 = +25%)
- 新契约 (L4.81): backend no *100, frontend *100 显示 (e.g. 0.25 = +25% / 100)
- 跟你 "我需要的是 pp, 然后不要 *100" 1:1 stable 永久规则化沿用
"""
import pytest
from backend.semantic.calculations import (
    yoy_absolute,
    yoy_ratio,
    yoy_repurchase_rate,
    mom_absolute,
    mom_ratio,
    safe_ratio,
    percentage_to_ratio,
    ratio_to_percentage,
)


class TestYoyAbsolute:
    """Test absolute value YOY calculation. Returns raw ratio (no *100, L4.81 治本契约)."""

    def test_positive_growth(self):
        """(100 - 80) / 80 = 0.25 (L4.81: no *100, frontend *100 = +25%)"""
        assert yoy_absolute(100, 80) == 0.25

    def test_negative_growth(self):
        """(60 - 80) / 80 = -0.25 (L4.81: no *100, frontend *100 = -25%)"""
        assert yoy_absolute(60, 80) == -0.25

    def test_zero_growth(self):
        """Equal values => 0 (L4.81: no *100)"""
        assert yoy_absolute(50, 50) == 0.0

    def test_comp_zero_returns_none(self):
        """Division by zero => None"""
        assert yoy_absolute(100, 0) is None

    def test_both_zero_returns_none(self):
        """0 / 0 => None"""
        assert yoy_absolute(0, 0) is None

    def test_cur_none_treated_as_zero(self):
        """None current => 0 / comp = -1.0 (L4.81: no *100)"""
        assert yoy_absolute(None, 100) == -1.0

    def test_comp_none_treated_as_zero(self):
        """None comparison => cur / 0 => None"""
        assert yoy_absolute(100, None) is None

    def test_both_none_returns_none(self):
        """Both None => 0 / 0 => None"""
        assert yoy_absolute(None, None) is None

    def test_string_input(self):
        """String numbers are converted"""
        assert yoy_absolute("100", "80") == 0.25

    def test_invalid_string_returns_none(self):
        """Non-numeric string => None"""
        assert yoy_absolute("abc", 100) is None

    def test_rounding(self):
        """Result is rounded to 4 decimal places (raw ratio, L4.81: no *100)"""
        result = yoy_absolute(100, 3)
        assert result == round((100 - 3) / 3, 4)

    def test_large_values(self):
        """Large values should not overflow"""
        result = yoy_absolute(1_000_000, 800_000)
        assert result == 0.25

    def test_tiny_comp_near_zero(self):
        """Comparison near zero threshold => None"""
        assert yoy_absolute(100, 1e-8) is None


class TestYoyRatio:
    """Test ratio/percentage YOY (raw ratio diff no *100, L4.81 治本契约)."""

    def test_positive_pp(self):
        """(0.60 - 0.55) = 0.05 (L4.81: no *100, frontend *100 = +5pp)"""
        assert yoy_ratio(0.60, 0.55) == 0.05

    def test_negative_pp(self):
        """(0.55 - 0.60) = -0.05 (L4.81: no *100, frontend *100 = -5pp)"""
        assert yoy_ratio(0.55, 0.60) == -0.05

    def test_zero_diff(self):
        """Same values => 0"""
        assert yoy_ratio(0.50, 0.50) == 0.0

    def test_comp_zero_ok(self):
        """(0.30 - 0) = 0.30 (L4.81: no *100)"""
        assert yoy_ratio(0.30, 0) == 0.30

    def test_both_zero(self):
        """Both zero => 0"""
        assert yoy_ratio(0, 0) == 0.0

    def test_none_treated_as_zero(self):
        """None => 0 (L4.81: no *100)"""
        assert yoy_ratio(None, 0.5) == -0.5
        assert yoy_ratio(0.5, None) == 0.5

    def test_string_input(self):
        assert yoy_ratio("0.60", "0.55") == 0.05


class TestYoyRepurchaseRate:
    """Test repurchase rate YOY (alias of yoy_ratio)."""

    def test_same_as_yoy_ratio(self):
        """yoy_repurchase_rate should return identical results to yoy_ratio"""
        pairs = [(0.35, 0.30), (0.50, 0.50), (0, 0.10), (None, 0.5)]
        for cur, comp in pairs:
            assert yoy_repurchase_rate(cur, comp) == yoy_ratio(cur, comp)


class TestMomAbsolute:
    """Test absolute value MOM (month-over-month). Returns raw ratio (no *100, L4.81 治本契约)."""

    def test_positive_mom(self):
        """(120 - 100) / 100 = 0.2 (L4.81: no *100)"""
        assert mom_absolute(120, 100) == 0.2

    def test_negative_mom(self):
        """(80 - 100) / 100 = -0.2 (L4.81: no *100)"""
        assert mom_absolute(80, 100) == -0.2

    def test_prev_zero_returns_none(self):
        """Previous = 0 => divide by zero => None"""
        assert mom_absolute(100, 0) is None

    def test_both_zero_returns_none(self):
        """Both zero => None"""
        assert mom_absolute(0, 0) is None

    def test_none_inputs(self):
        """None treated as 0 (L4.81: no *100)"""
        assert mom_absolute(None, 100) == -1.0
        assert mom_absolute(100, None) is None


class TestMomRatio:
    """Test ratio/percentage MOM (raw ratio diff no *100, L4.81 治本契约)."""

    def test_positive_mom(self):
        """(0.65 - 0.60) = 0.05 (L4.81: no *100)"""
        assert mom_ratio(0.65, 0.60) == 0.05

    def test_negative_mom(self):
        """(0.55 - 0.60) = -0.05 (L4.81: no *100)"""
        assert mom_ratio(0.55, 0.60) == -0.05

    def test_prev_zero_ok(self):
        """(0.30 - 0) = 0.30 (L4.81: no *100)"""
        assert mom_ratio(0.30, 0) == 0.30

    def test_none_inputs(self):
        """(0 - 0.5) = -0.5 (L4.81: no *100)"""
        assert mom_ratio(None, 0.5) == -0.5


class TestSafeRatio:
    """Test safe division with zero-denominator protection."""

    def test_normal_division(self):
        assert safe_ratio(10, 2) == 5.0

    def test_zero_denominator_returns_default(self):
        assert safe_ratio(10, 0) == 0.0

    def test_custom_default(self):
        assert safe_ratio(10, 0, default=-1.0) == -1.0

    def test_zero_numerator(self):
        assert safe_ratio(0, 10) == 0.0

    def test_negative_values(self):
        assert safe_ratio(-10, 2) == -5.0


class TestUnitConversion:
    """Test percentage <-> ratio conversion."""

    def test_percentage_to_ratio(self):
        assert percentage_to_ratio(60) == 0.60
        assert percentage_to_ratio(0) == 0.0
        assert percentage_to_ratio(100) == 1.0

    def test_ratio_to_percentage(self):
        assert ratio_to_percentage(0.60) == 60.0
        assert ratio_to_percentage(0) == 0.0
        assert ratio_to_percentage(1.0) == 100.0

    def test_roundtrip(self):
        """Converting back and forth should preserve value"""
        original = 42.5
        assert ratio_to_percentage(percentage_to_ratio(original)) == pytest.approx(original)
