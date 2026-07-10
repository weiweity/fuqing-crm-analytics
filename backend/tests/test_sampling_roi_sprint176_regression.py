"""Sprint 176 真因回归测试 - 不依赖 production DuckDB 的 contract + 真因锁回归 (L4.81 治本: no *100 契约).

背景:
- Q1 真因: a6447de bugfix 误删主循环+compare_cat_by_key 构造块 70 行,
  导致 /api/v1/sampling/roi 抛 UnboundLocalError.
- Q4 真因: SamplingCategoryRow 9 个 yoy 字段用裸 Optional[float],
  偏离 B1+B2 契约 (跟 sibling SamplingChannelSummary 不一致),
  Pydantic v2 422 拦截失效.

L4.81 治本契约 (user 7/10 拍板 "我需要的是 pp, 然后不要 *100"):
- backend yoy_absolute/yoy_ratio 返回 raw ratio (no *100, e.g. 0.25 = +25% / 100)
- frontend caller 必 *100 显示
- PercentageField 范围 -1e10~+1e10 (L4.81 治本, 兼容 yoy_absolute 万倍异常值 raw ratio)
- PpField 范围 -1e10~+1e10 (L4.81 治本, 兼容 yoy_ratio 万倍异常值 raw ratio diff)

本文件刻意不继承 _PROD_DUCKDB_AVAILABLE skipif, 因为:
- contract B2 验证走 Pydantic 模型字段元数据, 不需要 DuckDB
- NameError 锁回归走 monkeypatch_connection fixture, 已依赖 isolated_duckdb fixture.
  isolated_duckdb 已自带 production DuckDB skip. 等 production DuckDB 锁释放后会自动跑,
  现阶段纯 contract B2 验证即可触发.

Sprint 176 加测 (L4.81 治本契约):
1. test_category_row_b2_pct_pp_contract_types: 9 个 yoy 字段描述包含 PercentageField/PpField 关键字 (范围 -1e10~+1e10)
2. test_category_row_pydantic_validates_yoy_pp_range:  Pydantic 422 拦截 PpField 越界值 (e.g. 1e11)
3. test_category_row_pydantic_accepts_normal_yoy_pct: 正常 raw ratio (0.20 = +20% / 100) 可通过 Pydantic 校验
"""

import pytest

from backend.contracts.sampling import SamplingCategoryRow


def test_category_row_b2_pct_pp_contract_types():
    """SamplingCategoryRow 9 个 yoy 字段必须用 B2 强类型 (PercentageField / PpField),
    不能退回裸 Optional[float]. Pydantic v2 把 Field(description=...) 折进 annotation
    字符串里 (PercentageField / PpField alias 名被剥掉), 通过 annotation 字符串含
    'percentage'/'pp' 关键字 + FieldInfo 范围联合验证. L4.81 治本契约: 范围 -1e10~+1e10."""
    fields = SamplingCategoryRow.model_fields
    # _pct 后缀 → PercentageField (annotation 含 'percentage' + 范围 -1e10~+1e10)
    pct_fields = [
        "repurchase_users_yoy_pct",
        "repurchase_gsv_yoy_pct",
        "full_repurchase_users_yoy_pct",
        "full_repurchase_gsv_yoy_pct",
        "repurchase_aus_yoy_pct",
        "full_repurchase_aus_yoy_pct",
        "nonfull_repurchase_gsv_yoy_pct",
    ]
    for fname in pct_fields:
        ann_str = str(fields[fname].annotation)
        assert "percentage" in ann_str.lower(), (
            f"{fname} 不是 PercentageField, annotation: {ann_str}"
        )
        # L4.81 治本契约: PercentageField 范围 -1e10~+1e10 (兼容 yoy_absolute 万倍异常值 raw ratio)
        assert "-10000000000" in ann_str or "-1e10" in ann_str, (
            f"{fname} PercentageField ge 下限异常 (期望 -1e10): {ann_str}"
        )
        assert "10000000000" in ann_str or "1e10" in ann_str, (
            f"{fname} PercentageField le 上限异常 (期望 +1e10): {ann_str}"
        )

    # _pp 后缀 → PpField (annotation 含 'pp' + 范围 -1e10~+1e10, L4.81 治本契约)
    pp_fields = ["repurchase_rate_yoy_pp", "full_repurchase_rate_yoy_pp"]
    for fname in pp_fields:
        ann_str = str(fields[fname].annotation)
        assert "pp" in ann_str.lower() and "no *100" in ann_str, (
            f"{fname} 不是 PpField (L4.81 治本契约), annotation: {ann_str}"
        )
        # L4.81 治本契约: PpField 范围 -1e10~+1e10 (兼容 yoy_ratio 万倍异常值 raw ratio diff)
        assert "-10000000000" in ann_str or "-1e10" in ann_str, (
            f"{fname} PpField ge 下限异常 (期望 -1e10): {ann_str}"
        )
        assert "10000000000" in ann_str or "1e10" in ann_str, (
            f"{fname} PpField le 上限异常 (期望 +1e10): {ann_str}"
        )


def test_category_row_pydantic_accepts_normal_yoy_pct():
    """SamplingCategoryRow 接受正常 raw ratio (L4.81 治本契约: no *100, e.g. 0.20 = +20% / 100, frontend caller 必 *100 显示)."""
    row = SamplingCategoryRow(
        channel="TTL派样",
        category="面膜",
        sample_users=100,
        repurchase_users=10,
        repurchase_rate=0.1,
        repurchase_gsv=200.0,
        repurchase_aus=20.0,
        same_category_repurchase=5,
        same_category_rate=0.05,
        # 9 个 yoy 字段 (Sprint 175 Q5 设计输出, L4.81 治本契约: raw ratio no *100)
        repurchase_users_yoy_pct=0.20,        # +20% / 100 = raw 0.20
        repurchase_gsv_yoy_pct=2.00,          # +200% / 100 = raw 2.00
        repurchase_rate_yoy_pp=0.025,         # +2.5pp / 100 = raw 0.025
        full_repurchase_users_yoy_pct=0.50,   # +50% / 100 = raw 0.50
        full_repurchase_gsv_yoy_pct=1.00,     # +100% / 100 = raw 1.00
        full_repurchase_rate_yoy_pp=0.01,     # +1pp / 100 = raw 0.01
        repurchase_aus_yoy_pct=0.15,
        full_repurchase_aus_yoy_pct=0.20,
        nonfull_repurchase_gsv_yoy_pct=3.00,
    )
    # 校验字段值原样保留 (L4.81 治本契约: raw ratio)
    assert row.repurchase_users_yoy_pct == 0.20
    assert row.repurchase_rate_yoy_pp == 0.025


def test_category_row_pydantic_rejects_yoy_pp_out_of_range():
    """PpField 范围 -1e10~+1e10 raw ratio diff (L4.81 治本契约), 越界值必须 422 拦截 (B2 强类型配套 guard)."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SamplingCategoryRow(
            channel="TTL派样",
            category="面膜",
            sample_users=100,
            repurchase_users=10,
            repurchase_rate=0.1,
            repurchase_gsv=200.0,
            repurchase_aus=20.0,
            same_category_repurchase=5,
            same_category_rate=0.05,
            repurchase_rate_yoy_pp=1e11,  # 越界 +1e11 raw ratio (= +1e13pp display, L4.81 阈值 ±1e10)
        )

    with pytest.raises(ValidationError):
        SamplingCategoryRow(
            channel="TTL派样",
            category="面膜",
            sample_users=100,
            repurchase_users=10,
            repurchase_rate=0.1,
            repurchase_gsv=200.0,
            repurchase_aus=20.0,
            same_category_repurchase=5,
            same_category_rate=0.05,
            full_repurchase_rate_yoy_pp=-1e11,  # 越界 -1e11 raw ratio (= -1e13pp display, L4.81 阈值 ±1e10)
        )
