"""
Sprint 14.5 治根测试: 验证 rfm _parse_flow_rows 不算 "已购客TTL" 段 ratio.

根因复盘 (Sprint 14 A.3 引入 regression):
  - Sprint 14 A.3 给 contracts/rfm.py RFM*RFlowRow 14 个 repurchase_gsv_ratio_* 字段
    加 RatioField (0-1) 验证.
  - service backend/services/rfm/_flow_engine.py:139-143 算 ratio 循环包含 TTL 段,
    但 line 135-136 totals 累加排除 TTL 段 → ttl_gsv / (sum - ttl) > 1.0 越界.
  - 真实越界值 2.8754 (member_same_channel_rows[6] R 桶 2年外已购客).
  - 治根 (sprint14-rfm-ratio-ttl): 排除 TTL 段 ratio 计算, 留 0.0, 前端 RFMView
    已过滤 TTL 段显示.

测试覆盖:
  1. 6 段 R 桶 ratio 在 [0, 1] 范围 (含 sum ≤ 1.0)
  2. TTL 段 ratio = 0.0 (不论 ttl_gsv 多大)
  3. 缺失 segment ratio = 0.0 (_DEFAULT_ENTRY)
  4. 4 mode (all / same / member_all / member_same) 都生效
"""
from backend.services.rfm._flow_engine import _parse_flow_rows


def _make_rows():
    """构造 4 mode x 7 段 (6 R 桶 + TTL) 的样本数据, ttl_gsv > sum(R_buckets)
    触发越界场景. 真实值 2.87x 来自 prod 数据 (TTL 含当期新购客复购)."""
    rows = []
    for mode in ("all", "same", "member_all", "member_same"):
        # 6 个 R 桶段, 各 1000 复购 GSV
        for seg in (
            "近1个月已购客", "近2-3个月已购客", "近4-6月已购客",
            "近7-12个月已购客", "近13个月-近24个月已购客", "2年外已购客",
        ):
            rows.append((mode, seg, 100, 50, 1000.0))
        # TTL 段: 8000 GSV (>6 R 桶 sum = 6000, 模拟真实越界)
        rows.append((mode, "已购客TTL", 100, 80, 8000.0))
    return rows


_SEGMENT_ORDER = [
    "近1个月已购客", "近2-3个月已购客", "近4-6月已购客",
    "近7-12个月已购客", "近13个月-近24个月已购客", "2年外已购客",
    "已购客TTL",
]


class TestRfmFlowTtlRatio:
    """Sprint 14.5 治根: TTL 段 ratio 不算, 留 0.0; 6 R 桶 ratio 在 0-1."""

    def test_r_buckets_ratio_in_range(self):
        """6 个 R 桶段 ratio 必须 ∈ [0, 1] (契约 RatioField 0-1)."""
        all_r, same_r, member_all_r, member_same_r = _parse_flow_rows(
            _make_rows(), _SEGMENT_ORDER,
        )
        # sum(R 桶) = 6000, total = 6000 (TTL 排除)
        # 每段 ratio = 1000/6000 = 0.1667
        for seg in _SEGMENT_ORDER[:-1]:
            for result in (all_r, same_r, member_all_r, member_same_r):
                ratio = result[seg]["repurchase_gsv_ratio"]
                assert 0.0 <= ratio <= 1.0, (
                    f"{seg} ratio {ratio} 越界 [0, 1]"
                )

    def test_ttl_segment_ratio_is_zero(self):
        """TTL 段 ratio 留 0.0 (治根: 排除计算, 避免越界)."""
        all_r, same_r, member_all_r, member_same_r = _parse_flow_rows(
            _make_rows(), _SEGMENT_ORDER,
        )
        for result in (all_r, same_r, member_all_r, member_same_r):
            assert result["已购客TTL"]["repurchase_gsv_ratio"] == 0.0, (
                f"TTL 段 ratio 应 = 0.0, 实际 {result['已购客TTL']['repurchase_gsv_ratio']}"
            )

    def test_ttl_ratio_zero_regardless_of_ttl_gsv(self):
        """核心: 不论 ttl_gsv 多大 (含 2.87x 越界场景), ratio 都 = 0."""
        # ttl_gsv = sum(R) * 5, 真实越界
        rows = []
        for mode in ("all",):
            for seg in _SEGMENT_ORDER[:-1]:
                rows.append((mode, seg, 100, 50, 1000.0))
            rows.append((mode, "已购客TTL", 100, 80, 30000.0))  # 5x 越界
        all_r, _, _, _ = _parse_flow_rows(rows, _SEGMENT_ORDER)
        assert all_r["已购客TTL"]["repurchase_gsv_ratio"] == 0.0
        # 6 段 R 桶 ratio 正常算 = 1000/6000 = 0.1667
        for seg in _SEGMENT_ORDER[:-1]:
            assert 0.0 < all_r[seg]["repurchase_gsv_ratio"] <= 1.0

    def test_r_bucket_ratio_sums_to_le_1(self):
        """6 段 R 桶 ratio 累加 ≤ 1.0 (sum 是 TTL 的子集)."""
        all_r, _, _, _ = _parse_flow_rows(_make_rows(), _SEGMENT_ORDER)
        total = sum(all_r[seg]["repurchase_gsv_ratio"] for seg in _SEGMENT_ORDER[:-1])
        assert total <= 1.0, f"6 段 R 桶 ratio 累加 {total} 应 ≤ 1.0"

    def test_missing_segment_ratio_is_zero(self):
        """缺失 segment 用 _DEFAULT_ENTRY, ratio = 0.0 (跟 TTL 一致, 都 0)."""
        # 1 mode, 0 段 (SQL 无返回行)
        rows = [("all", "近1个月已购客", 0, 0, 0.0)]
        all_r, same_r, member_all_r, member_same_r = _parse_flow_rows(
            rows, _SEGMENT_ORDER,
        )
        # 缺失的 6 段 (含 TTL) ratio 应 = 0
        for seg in _SEGMENT_ORDER:
            for result in (all_r, same_r, member_all_r, member_same_r):
                assert result[seg]["repurchase_gsv_ratio"] == 0.0
