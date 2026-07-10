"""
Sprint 21 P0-1 回归测试: 验 visitor schema 顶层 forward ref 解析

背景 (2026-06-13 P3 实测):
  backend/contracts/visitor.py 用了 `from __future__ import annotations` + 顶层字符串
  forward ref ("PercentageField"), Pydantic v2 (2.13) 不会自动解析到 globals, 字段退化成
  裸 float 且走错 fallback 路径 (uvicorn Jun 11 启动加载的旧版 schema:
  member_join_rate=RatioField le=1.0, 真实数据 1.2726 抛 ResponseValidationError → 500).

d660352 提交已经把 RatioField → PercentageField 改了, 但 uvicorn 没重启加载.

防回归: schema 字段必须接受真实业务数据 (member_join_rate >100 累计入会率,
member_join_rate_yoy <0 下降 pp 差).
"""
from backend.contracts.visitor import (
    VisitorSummaryResponse,
    VisitorDailyTrendItem,
)


def _collect_ge_le(field_info) -> tuple[set[float], set[float]]:
    """递归从 FieldInfo + annotation.__metadata__ + Union 内层收集所有 Ge/Le 约束.

    Pydantic v2 拆 Annotated 时:
      - 顶层字段: FieldInfo.metadata = [Ge(...), Le(...)]
      - Optional[X] 字段: annotation = Union[Annotated[float, FieldInfo(...,metadata=[Ge,Le])], None]
        约束在内层 FieldInfo.metadata, 也可能直接在 annotation.__metadata__.
    """
    import typing
    ge_set, le_set = set(), set()

    def _scan(items):
        for m in items or []:
            if (v := getattr(m, "ge", None)) is not None:
                ge_set.add(v)
            if (v := getattr(m, "le", None)) is not None:
                le_set.add(v)
            # Pydantic v2 在 Optional[X] 拆解时, X 变 Annotated[float, FieldInfo(...,metadata=[Ge,Le])]
            # FieldInfo 实例自身需要递归其 metadata
            if hasattr(m, "metadata") and m is not field_info:
                _scan(m.metadata)

    _scan(getattr(field_info, "metadata", None))
    ann = getattr(field_info, "annotation", None)
    if ann is not None and hasattr(ann, "__metadata__"):
        _scan(ann.__metadata__)
    if ann is not None and getattr(ann, "__origin__", None) is typing.Union:
        for arg in getattr(ann, "__args__", []):
            if hasattr(arg, "__metadata__"):
                _scan(arg.__metadata__)
            if hasattr(arg, "metadata"):
                _scan(arg.metadata)
    return ge_set, le_set


def _has_constraint(field_info, expected_ge, expected_le) -> bool:
    ge_set, le_set = _collect_ge_le(field_info)
    return expected_ge in ge_set and expected_le in le_set


def test_visitor_summary_member_join_rate_uses_percentage_field():
    """member_join_rate 必须是 PercentageField (L4.81 治本契约: ge=-1e10 le=1e10 raw ratio 0-1), 不是裸 float (RatioField 0-1)."""
    f = VisitorSummaryResponse.model_fields["member_join_rate"]
    assert _has_constraint(f, -1e10, 1e10), (
        f"member_join_rate 必须是 PercentageField (ge=-1e10 le=1e10, L4.81 治本契约), 实际 metadata={f.metadata}. "
        f"修法: backend/contracts/visitor.py 字段类型必须是 PercentageField, 不能是 RatioField."
    )


def test_visitor_summary_ly_member_join_rate_uses_percentage_field():
    f = VisitorSummaryResponse.model_fields["ly_member_join_rate"]
    assert _has_constraint(f, -1e10, 1e10), (
        f"ly_member_join_rate 必须是 PercentageField (L4.81 治本契约: ge=-1e10 le=1e10), 实际 metadata={f.metadata}"
    )


def test_visitor_summary_member_join_rate_yoy_uses_pp_field():
    f = VisitorSummaryResponse.model_fields["member_join_rate_yoy"]
    assert _has_constraint(f, -1e10, 1e10), (
        f"member_join_rate_yoy 必须是 PpField (L4.81 治本契约: ge=-1e10 le=1e10 raw ratio diff), 实际 metadata={f.metadata}. "
        f"修法: backend/contracts/visitor.py 字段类型必须是 PpField (L4.81 治本契约)."
    )


def test_visitor_summary_member_join_rate_mom_uses_pp_field():
    f = VisitorSummaryResponse.model_fields["member_join_rate_mom"]
    assert _has_constraint(f, -1e10, 1e10), (
        f"member_join_rate_mom 必须是 PpField (L4.81 治本契约: ge=-1e10 le=1e10), 实际 metadata={f.metadata}"
    )


def test_daily_trend_member_join_rate_uses_percentage_field():
    f = VisitorDailyTrendItem.model_fields["member_join_rate"]
    assert _has_constraint(f, -1e10, 1e10), (
        f"daily.member_join_rate 必须是 PercentageField (L4.81 治本契约: ge=-1e10 le=1e10), 实际 metadata={f.metadata}"
    )


def test_visitor_summary_accepts_over_100_percentage():
    """业务场景: 累计入会率 >100% (Sprint 4 P0 多次入会累计), schema 必须接受.

    修前 (uvicorn 旧版 schema): RatioField le=1.0, 1.2726 抛 500.
    修后 (d660352): PercentageField le=1B, 接受.
    """
    resp = VisitorSummaryResponse(
        start_date="2026-05-13",
        end_date="2026-06-12",
        visitors=10000,
        new_members=12000,
        member_join_rate=127.26,
        ly_visitors=9000,
        ly_new_members=8000,
        ly_member_join_rate=88.88,
        member_join_rate_yoy=38.38,
    )
    assert resp.member_join_rate == 127.26
    assert resp.member_join_rate_yoy == 38.38


def test_visitor_summary_accepts_negative_pp_yoy():
    """业务场景: 入会率同比下降 (pp < 0), PpField ge=-100 必须接受负数."""
    resp = VisitorSummaryResponse(
        start_date="2026-05-13",
        end_date="2026-06-12",
        visitors=10000,
        new_members=5000,
        member_join_rate=50.0,
        ly_visitors=9000,
        ly_new_members=8000,
        ly_member_join_rate=88.88,
        member_join_rate_yoy=-38.88,
    )
    assert resp.member_join_rate_yoy == -38.88
