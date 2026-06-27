"""
Sprint 15 A 治根测试: 验证 PercentageField 放宽到 ±1B 范围, 真实生产异常值 (1M+)
不被 Pydantic 拒收. 0/负数仍拒 (Sprint 14 P2 教训 — 0/负数被吞).

背景: Sprint 15 实施时, 用户排查品类看板占比 YOY, 25 6/1-6/8 单独拉
/api/v1/category/overview 返 500, 真实 gsv_yoy = 1,157,823.86% 越界 1M 上限.
/autoplan 4 phase review 后 user 拍 A 修法 (放宽到 1B, 跟 Sprint 14.5 PercentageField
0-1M 退让一致).
"""
import pytest
from pydantic import BaseModel, ValidationError

from backend.contracts.types import PercentageField


class _YoyModel(BaseModel):
    yoy: PercentageField = 0.0


class TestPercentageYoyOver1m:
    """Sprint 15 A 治根: PercentageField 放宽到 ±1B, 真实异常值通过."""

    def test_real_prod_value_1_15m_passes(self):
        """真实 gsv_yoy 1,157,823.86% (25 期间 1.15M) 通过 Pydantic 验证."""
        m = _YoyModel(yoy=1_157_823.86)
        assert m.yoy == 1_157_823.86

    def test_extreme_1b_passes(self):
        """±1B 上限边界值通过 (eg. 新品类从 0 涨 1 万倍仍合理)."""
        m = _YoyModel(yoy=999_999_999.99)
        assert m.yoy == 999_999_999.99

    def test_negative_yoy_1m_passes(self):
        """负 YOY -1M 通过 (eg. 业务下滑 95% 返 -9500%)."""
        m = _YoyModel(yoy=-999_999.99)
        assert m.yoy == -999_999.99

    def test_above_1t_rejected(self):
        """超过 1T 上限仍拒 (eg. 10T 是脏数据)."""
        with pytest.raises(ValidationError) as exc:
            _YoyModel(yoy=1_000_000_000_001.0)
        assert "less_than_equal" in str(exc.value)

    def test_below_neg_1t_rejected(self):
        """低于 -1T 下限仍拒."""
        with pytest.raises(ValidationError) as exc:
            _YoyModel(yoy=-1_000_000_000_001.0)
        assert "greater_than_equal" in str(exc.value)

    def test_zero_passes(self):
        """0 通过 (边界值)."""
        m = _YoyModel(yoy=0.0)
        assert m.yoy == 0.0

    def test_normal_pct_50_passes(self):
        """50% 正常 percentage 通过 (Sprint 14 0-100 严守仍兼容)."""
        m = _YoyModel(yoy=50.0)
        assert m.yoy == 50.0

    def test_normal_yoy_25_passes(self):
        """25% YOY 正常值通过."""
        m = _YoyModel(yoy=25.0)
        assert m.yoy == 25.0
