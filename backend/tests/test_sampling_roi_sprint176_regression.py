"""Sprint 176 真因回归测试 - 不依赖 production DuckDB 的 contract + 真因锁回归.

背景:
- Q1 真因: a6447de bugfix 误删主循环+compare_cat_by_key 构造块 70 行,
  导致 /api/v1/sampling/roi 抛 UnboundLocalError.
- Q4 真因: SamplingCategoryRow 9 个 yoy 字段用裸 Optional[float],
  偏离 B1+B2 契约 (跟 sibling SamplingChannelSummary 不一致),
  Pydantic v2 422 拦截失效.

本文件刻意不继承 _PROD_DUCKDB_AVAILABLE skipif, 因为:
- contract B2 验证走 Pydantic 模型字段元数据, 不需要 DuckDB
- NameError 锁回归走 monkeypatch_connection fixture, 已依赖 isolated_duckdb fixture.
  isolated_duckdb 已自带 production DuckDB skip. 等 production DuckDB 锁释放后会自动跑,
  现阶段纯 contract B2 验证即可触发.

Sprint 176 加测:
1. test_category_row_b2_pct_pp_contract_types: 9 个 yoy 字段描述包含 PercentageField/PpField 关键字
2. test_category_row_pydantic_validates_yoy_pp_range:  Pydantic 422 拦截 PpField 越界值
3. test_category_row_pydantic_accepts_normal_yoy_pct: 正常 YOY %值可通过 Pydantic 校验
"""

import pytest

from backend.contracts.sampling import SamplingCategoryRow


def test_category_row_b2_pct_pp_contract_types():
    """SamplingCategoryRow 9 个 yoy 字段必须用 B2 强类型 (PercentageField / PpField),
    不能退回裸 Optional[float]. Pydantic v2 把 Field(description=...) 折进 annotation
    字符串里 (PercentageField / PpField alias 名被剥掉), 通过 annotation 字符串含
    'percentage'/'pp' 关键字 + FieldInfo 范围联合验证."""
    fields = SamplingCategoryRow.model_fields
    # _pct 后缀 → PercentageField (annotation 含 'percentage' + 范围 -1T~+1T)
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
        # PercentageField 范围 -1T~+1T (Ge=-1e12, Le=1e12)
        assert "-1000000000000" in ann_str or "-1e12" in ann_str, (
            f"{fname} PercentageField ge 下限异常 (期望 -1T): {ann_str}"
        )
        assert "1000000000000" in ann_str or "1e12" in ann_str, (
            f"{fname} PercentageField le 上限异常 (期望 +1T): {ann_str}"
        )

    # _pp 后缀 → PpField (annotation 含 'pp' + 范围 -100~+100)
    pp_fields = ["repurchase_rate_yoy_pp", "full_repurchase_rate_yoy_pp"]
    for fname in pp_fields:
        ann_str = str(fields[fname].annotation)
        assert "pp" in ann_str.lower() and "-100" in ann_str, (
            f"{fname} 不是 PpField, annotation: {ann_str}"
        )
        # PpField 范围 -100~+100 (Ge=-100.0, Le=100.0)
        assert "ge=-100.0" in ann_str or "ge=-100 " in ann_str, (
            f"{fname} PpField ge 下限异常 (期望 -100.0): {ann_str}"
        )
        assert "le=100.0" in ann_str or "le=100 " in ann_str, (
            f"{fname} PpField le 上限异常 (期望 +100.0): {ann_str}"
        )


def test_category_row_pydantic_accepts_normal_yoy_pct():
    """SamplingCategoryRow 接受正常 YOY % 值 (跟 service _add_compare_metrics 输出兼容)."""
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
        # 9 个 yoy 字段 (Sprint 175 Q5 设计输出)
        repurchase_users_yoy_pct=20.0,        # +20%
        repurchase_gsv_yoy_pct=200.0,         # +200%
        repurchase_rate_yoy_pp=2.5,           # +2.5pp
        full_repurchase_users_yoy_pct=50.0,   # +50%
        full_repurchase_gsv_yoy_pct=100.0,    # +100%
        full_repurchase_rate_yoy_pp=1.0,      # +1pp
        repurchase_aus_yoy_pct=15.0,
        full_repurchase_aus_yoy_pct=20.0,
        nonfull_repurchase_gsv_yoy_pct=300.0,
    )
    # 校验字段值原样保留
    assert row.repurchase_users_yoy_pct == 20.0
    assert row.repurchase_rate_yoy_pp == 2.5


def test_category_row_pydantic_rejects_yoy_pp_out_of_range():
    """PpField 范围 -100~+100 pp 差, 越界值必须 422 拦截 (B2 强类型配套 guard)."""
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
            repurchase_rate_yoy_pp=101.0,  # 越界 +101pp
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
            full_repurchase_rate_yoy_pp=-101.0,  # 越界 -101pp
        )
