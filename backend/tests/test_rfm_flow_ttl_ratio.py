"""
Sprint 14.5 治根测试: 验证 rfm _parse_flow_rows TTL 段 ratio 处理 + Pydantic 端到端契约.

根因复盘 (Sprint 14 A.3 引入 regression):
  - Sprint 14 A.3 给 contracts/rfm.py RFM*RFlowRow 14 个 repurchase_gsv_ratio_* 字段
    加 RatioField (0-1) 验证.
  - service _flow_engine.py:139-143 算 ratio 循环包含 TTL 段, 但 totals 累加排除
    TTL 段 → ttl_gsv / (sum - ttl) > 1.0 越界, /api/v1/rfm/r-flow 4 端点 500.

Sprint 14.5 P1.1 治根 (Codex audit): 14 个 ratio 字段改 Optional[RatioField] = None,
service 端 TTL 段写 None, 前端 RFMView 已 .filter 过滤此段.

测试覆盖 (Codex P1.2 / P1.3 / P2.1 / P2.2 / P2.8):
  1. 6 段 R 桶 ratio ∈ [0, 1] (含 sum ≤ 1.0)
  2. TTL 段 ratio = None (不论 ttl_gsv 多大)
  3. TTL 段 gsv 数据保留 (P2.8 防后人误读测试)
  4. 缺失 segment ratio = None
  5. 4 mode (all/same/member_all/member_same) 都生效
  6. F/M 桶同样适用 (_parse_flow_rows 共享, R/F/M 三维生效) (P1.2)
  7. 非均匀 GSV 分布下, 单段 ratio 仍 ≤ 1.0 (P2.1 浮点误差边界)
  8. 0 数据场景 (全 0) ratio 仍 = None, 不抛异常 (P2.2)
  9. Pydantic 端到端断言 (P1.3): _parse_flow_rows 输出直接喂给 RFMRFlowRow/RFMFRFlowRow
     /RFMMFlowRow 不抛 ValidationError, 验证契约层跟 service 层一致
"""
import pytest
from backend.services.rfm._flow_engine import _parse_flow_rows
from backend.contracts.rfm import RFMRFlowRow, RFMFRFlowRow, RFMMFlowRow


# ─────────────────────────────────────────────────────────────
# Test data builders
# ─────────────────────────────────────────────────────────────

R_SEGMENTS_7 = [
    "近1个月已购客", "近2-3个月已购客", "近4-6月已购客",
    "近7-12个月已购客", "近13个月-近24个月已购客", "2年外已购客",
    "已购客TTL",
]
F_SEGMENTS_6 = ["1次购买", "2次购买", "3次购买", "4次购买", "5次及以上", "已购客TTL"]
M_SEGMENTS_6 = ["0-100元", "100-300元", "300-500元", "500-1000元", "1000元以上", "已购客TTL"]


def _make_uniform_r_rows(per_seg_gsv=1000.0, ttl_gsv=8000.0):
    """R 桶 6 段均匀分布, TTL 段 gsv > 6 R 桶 sum (触发越界场景, 真实 2.87x 来自 prod)."""
    rows = []
    for mode in ("all", "same", "member_all", "member_same"):
        for seg in R_SEGMENTS_7[:-1]:
            rows.append((mode, seg, 100, 50, per_seg_gsv))
        rows.append((mode, "已购客TTL", 100, 80, ttl_gsv))
    return rows


def _make_skewed_r_rows():
    """P2.1: 非均匀 GSV 分布 - "近1个月" 占 90%, 其余各 2%. 验证单段 ratio 仍 ≤ 1.0."""
    rows = []
    gsv_per_seg = [
        (9000.0, "近1个月已购客"),
        (200.0, "近2-3个月已购客"),
        (200.0, "近4-6月已购客"),
        (200.0, "近7-12个月已购客"),
        (200.0, "近13个月-近24个月已购客"),
        (200.0, "2年外已购客"),
    ]
    for mode in ("all",):
        for gsv, seg in gsv_per_seg:
            rows.append((mode, seg, 100, 50, gsv))
        rows.append((mode, "已购客TTL", 100, 80, 11000.0))  # TTL > sum(R 桶) = 10000
    return rows


def _make_empty_rows():
    """P2.2: 0 数据场景 - 所有段全 0, 验证 ratio = None 不抛异常."""
    rows = []
    for mode in ("all",):
        for seg in R_SEGMENTS_7[:-1]:
            rows.append((mode, seg, 0, 0, 0.0))
        rows.append((mode, "已购客TTL", 0, 0, 0.0))
    return rows


def _make_f_rows():
    """P1.2: F 桶 5 段 + TTL, 验证 _parse_flow_rows 共享引擎对 F 桶同样生效."""
    rows = []
    for mode in ("all",):
        for seg in F_SEGMENTS_6[:-1]:
            rows.append((mode, seg, 100, 50, 1000.0))
        rows.append((mode, "已购客TTL", 100, 80, 6000.0))
    return rows


def _make_m_rows():
    """P1.2: M 桶 5 段 + TTL."""
    rows = []
    for mode in ("all",):
        for seg in M_SEGMENTS_6[:-1]:
            rows.append((mode, seg, 100, 50, 1000.0))
        rows.append((mode, "已购客TTL", 100, 80, 6000.0))
    return rows


# ─────────────────────────────────────────────────────────────
# 核心治根测试
# ─────────────────────────────────────────────────────────────

class TestRfmFlowTtlRatio:
    """Sprint 14.5 治根: TTL 段 ratio = None; 6 段 R/F/M 桶 ratio ∈ [0, 1]."""

    def test_r_buckets_ratio_in_range(self):
        """6 个 R 桶段 ratio ∈ [0, 1] (契约 RatioField 0-1)."""
        all_r, same_r, member_all_r, member_same_r = _parse_flow_rows(
            _make_uniform_r_rows(), R_SEGMENTS_7,
        )
        for seg in R_SEGMENTS_7[:-1]:
            for result in (all_r, same_r, member_all_r, member_same_r):
                ratio = result[seg]["repurchase_gsv_ratio"]
                assert 0.0 <= ratio <= 1.0, f"{seg} ratio {ratio} 越界 [0, 1]"

    def test_ttl_segment_ratio_is_none(self):
        """P1.1: TTL 段 ratio = None (Optional[RatioField] 允许)."""
        all_r, _, _, _ = _parse_flow_rows(_make_uniform_r_rows(), R_SEGMENTS_7)
        assert all_r["已购客TTL"]["repurchase_gsv_ratio"] is None, (
            f"TTL 段 ratio 应 = None, 实际 {all_r['已购客TTL']['repurchase_gsv_ratio']}"
        )

    def test_ttl_ratio_none_regardless_of_ttl_gsv(self):
        """P1.1: 不论 ttl_gsv 多大 (含 5x 越界场景), ratio = None. P2.8: gsv 仍保留."""
        rows = []
        for mode in ("all",):
            for seg in R_SEGMENTS_7[:-1]:
                rows.append((mode, seg, 100, 50, 1000.0))
            rows.append((mode, "已购客TTL", 100, 80, 30000.0))  # 5x 越界
        all_r, _, _, _ = _parse_flow_rows(rows, R_SEGMENTS_7)
        # P1.1: TTL ratio = None
        assert all_r["已购客TTL"]["repurchase_gsv_ratio"] is None
        # P2.8: gsv 数据仍保留 (防后人误读 "整行被清零")
        assert all_r["已购客TTL"]["repurchase_gsv"] == 30000.0
        # 6 段 R 桶 ratio 正常算 = 1000/6000 = 0.1667
        for seg in R_SEGMENTS_7[:-1]:
            assert 0.0 < all_r[seg]["repurchase_gsv_ratio"] <= 1.0

    def test_r_bucket_ratio_sums_to_le_1(self):
        """6 段 R 桶 ratio 累加 ≤ 1.0 (sum 是 TTL 的子集)."""
        all_r, _, _, _ = _parse_flow_rows(_make_uniform_r_rows(), R_SEGMENTS_7)
        total = sum(all_r[seg]["repurchase_gsv_ratio"] for seg in R_SEGMENTS_7[:-1])
        assert total <= 1.0, f"6 段 R 桶 ratio 累加 {total} 应 ≤ 1.0"

    def test_missing_segment_ratio_is_zero(self):
        """缺失 segment (SQL 0 行返回) ratio = 0.0, _DEFAULT_ENTRY 兜底, contract 0-1 验证通过.
        注: TTL 段 ratio = None (Optional), 缺失段 ratio = 0.0 (RatioField 0-1) — 两种 fallback 策略共存."""
        rows = [("all", "近1个月已购客", 0, 0, 0.0)]
        all_r, same_r, member_all_r, member_same_r = _parse_flow_rows(rows, R_SEGMENTS_7)
        for seg in R_SEGMENTS_7:
            for result in (all_r, same_r, member_all_r, member_same_r):
                if seg == "已购客TTL":
                    # TTL 不在补全路径 (line 156-158 用 _DEFAULT_ENTRY 跳过 "已购客TTL"?)
                    # 实际: 补全逻辑 for seg in segment_order, TTL 也在, 同样补 _DEFAULT_ENTRY.
                    # 但 _parse_flow_rows line 134 target[segment]=entry 已经为有数据的段建了 entry,
                    # 缺失段走 line 156-158 _DEFAULT_ENTRY = {"repurchase_gsv_ratio": 0.0}.
                    assert result[seg]["repurchase_gsv_ratio"] == 0.0
                else:
                    assert result[seg]["repurchase_gsv_ratio"] == 0.0, (
                        f"{seg} 缺失段 ratio 应 = 0.0, 实际 {result[seg]['repurchase_gsv_ratio']}"
                    )

    def test_f_buckets_share_same_engine(self):
        """P1.2: F 桶 (_parse_flow_rows 共享) 同样 TTL ratio = None, 5 桶 ratio ∈ [0, 1]."""
        all_r, _, _, _ = _parse_flow_rows(_make_f_rows(), F_SEGMENTS_6)
        # 5 段 F 桶 ratio ∈ [0, 1]
        for seg in F_SEGMENTS_6[:-1]:
            assert 0.0 <= all_r[seg]["repurchase_gsv_ratio"] <= 1.0
        # TTL ratio = None
        assert all_r["已购客TTL"]["repurchase_gsv_ratio"] is None

    def test_m_buckets_share_same_engine(self):
        """P1.2: M 桶同样."""
        all_r, _, _, _ = _parse_flow_rows(_make_m_rows(), M_SEGMENTS_6)
        for seg in M_SEGMENTS_6[:-1]:
            assert 0.0 <= all_r[seg]["repurchase_gsv_ratio"] <= 1.0
        assert all_r["已购客TTL"]["repurchase_gsv_ratio"] is None

    def test_skewed_gsv_distribution_under_1(self):
        """P2.1: 非均匀 GSV (近1个月占 90%, 其余各 2%) 单段 ratio 仍 ≤ 1.0 (浮点边界)."""
        all_r, _, _, _ = _parse_flow_rows(_make_skewed_r_rows(), R_SEGMENTS_7)
        for seg in R_SEGMENTS_7[:-1]:
            ratio = all_r[seg]["repurchase_gsv_ratio"]
            assert ratio <= 1.0, f"非均匀 {seg} ratio {ratio} 越界"
        # 累加 ≤ 1.0 (浮点误差 ≤ 1e-9)
        total = sum(all_r[seg]["repurchase_gsv_ratio"] for seg in R_SEGMENTS_7[:-1])
        assert total <= 1.0 + 1e-9

    def test_empty_data_no_exception(self):
        """P2.2: 全 0 数据场景不抛异常. TTL 段 ratio = None (P1.1), 缺失段 ratio = 0.0 (_DEFAULT_ENTRY)."""
        all_r, _, _, _ = _parse_flow_rows(_make_empty_rows(), R_SEGMENTS_7)
        for seg in R_SEGMENTS_7:
            if seg == "已购客TTL":
                assert all_r[seg]["repurchase_gsv_ratio"] is None
            else:
                assert all_r[seg]["repurchase_gsv_ratio"] == 0.0


# ─────────────────────────────────────────────────────────────
# Pydantic 端到端契约断言 (P1.3 Codex)
# ─────────────────────────────────────────────────────────────

class TestRfmFlowPydanticContract:
    """P1.3: _parse_flow_rows 输出直接喂给 RFMRFlowRow / RFMFRFlowRow / RFMMFlowRow
    不抛 ValidationError. 防止 service 算对但 contract 拒收 (Sprint 14 A.3 真实场景)."""

    def _build_row_dict(self, seg, all_data, comp_data, prev2_data, seg_col):
        """复刻 _flow_engine._build_rows 行为 (除 None 透传)."""
        c, p, p2 = all_data.get(seg, {}), comp_data.get(seg, {}), prev2_data.get(seg, {})
        return {
            seg_col: seg,
            "hist_users_current": c.get("hist_users", 0),
            "repurchase_users_current": c.get("repurchase_users", 0),
            "repurchase_rate_current": round(c.get("repurchase_rate", 0.0), 4),
            "repurchase_gsv_current": round(c.get("repurchase_gsv", 0.0), 2),
            "repurchase_gsv_ratio_current": (
                None if c.get("repurchase_gsv_ratio") is None
                else round(c.get("repurchase_gsv_ratio"), 4)
            ),
            "hist_users_comp": p.get("hist_users", 0),
            "repurchase_users_comp": p.get("repurchase_users", 0),
            "repurchase_rate_comp": round(p.get("repurchase_rate", 0.0), 4),
            "repurchase_gsv_comp": round(p.get("repurchase_gsv", 0.0), 2),
            "repurchase_gsv_ratio_comp": (
                None if p.get("repurchase_gsv_ratio") is None
                else round(p.get("repurchase_gsv_ratio"), 4)
            ),
            "hist_users_prev2": p2.get("hist_users", 0),
            "repurchase_users_prev2": p2.get("repurchase_users", 0),
            "repurchase_rate_prev2": round(p2.get("repurchase_rate", 0.0), 4),
            "repurchase_gsv_prev2": round(p2.get("repurchase_gsv", 0.0), 2),
            "repurchase_gsv_ratio_prev2": (
                None if p2.get("repurchase_gsv_ratio") is None
                else round(p2.get("repurchase_gsv_ratio"), 4)
            ),
        }

    def test_r_row_with_ttl_none_passes_pydantic(self):
        """P1.3: R 桶行 TTL 段 ratio=None, RFMRFlowRow 验证通过 (Optional 字段 None)."""
        all_r, _, _, _ = _parse_flow_rows(_make_uniform_r_rows(), R_SEGMENTS_7)
        # 6 段 R 桶 + 1 段 TTL 全部喂给 contract
        for seg in R_SEGMENTS_7:
            row = self._build_row_dict(seg, all_r, all_r, all_r, "r_segment")
            # 应该不抛 ValidationError
            rfm_row = RFMRFlowRow(**row)
            if seg == "已购客TTL":
                assert rfm_row.repurchase_gsv_ratio_current is None
            else:
                assert 0.0 <= rfm_row.repurchase_gsv_ratio_current <= 1.0

    def test_f_row_with_ttl_none_passes_pydantic(self):
        """P1.3: F 桶行 TTL 段 ratio=None, RFMFRFlowRow 验证通过."""
        all_r, _, _, _ = _parse_flow_rows(_make_f_rows(), F_SEGMENTS_6)
        for seg in F_SEGMENTS_6:
            row = self._build_row_dict(seg, all_r, all_r, all_r, "f_segment")
            rfm_row = RFMFRFlowRow(**row)
            if seg == "已购客TTL":
                assert rfm_row.repurchase_gsv_ratio_current is None

    def test_m_row_with_ttl_none_passes_pydantic(self):
        """P1.3: M 桶行 TTL 段 ratio=None, RFMMFlowRow 验证通过."""
        all_r, _, _, _ = _parse_flow_rows(_make_m_rows(), M_SEGMENTS_6)
        for seg in M_SEGMENTS_6:
            row = self._build_row_dict(seg, all_r, all_r, all_r, "m_segment")
            rfm_row = RFMMFlowRow(**row)
            if seg == "已购客TTL":
                assert rfm_row.repurchase_gsv_ratio_current is None

    def test_pydantic_rejects_non_optional_over_1_ratio(self):
        """P1.3 回归: 即使没显式 None, ratio > 1.0 仍被 RatioField 0-1 拒收.
        这测试确保 P1.1 改 Optional 没破坏 ratio 字段本身的 0-1 验证 (R/F/M 桶段
        不受影响, 仅 TTL 段允许 None)."""
        from pydantic import ValidationError
        # ratio=1.5 (非 None) 仍越界
        with pytest.raises(ValidationError) as exc:
            RFMRFlowRow(
                r_segment="近1个月已购客",
                repurchase_gsv_ratio_current=1.5,
            )
        assert "less_than_equal" in str(exc.value)
