"""
芙清 CRM - 人群分层定义 (Segments Registry)

统一管理所有人群分层规则：
- RFM 8象限（经典分割，>=4 vs <4）
- RFM 评分阈值
- 新老客定义
- 流失风险定义

所有人群相关的 CASE WHEN SQL 必须通过本模块生成，禁止在 Service 中手写。
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional


# ============================================================
# RFM 固定阈值（单一数据源）
# ============================================================
RFM_THRESHOLDS = {
    "r": [30, 90, 180, 365],
    "f": [1, 2, 3, 4],
    "m": [100, 300, 500, 1000],
}


# ============================================================
# 8象限定义（经典 RFM，分割线 >=4 vs <4）
# ============================================================
@dataclass
class SegmentDefinition:
    segment_id: int
    name_cn: str
    name_en: str
    r_high: bool
    f_high: bool
    m_high: bool
    description: str
    color: str
    priority: int = 99


SEGMENTS: List[SegmentDefinition] = [
    SegmentDefinition(
        segment_id=1, name_cn="重要价值客户", name_en="Champions",
        r_high=True, f_high=True, m_high=True,
        description="最近购买、购买频繁且消费高，最有价值客户",
        color="#FF6B6B", priority=1,
    ),
    SegmentDefinition(
        segment_id=2, name_cn="重要保持客户", name_en="Loyal Customers",
        r_high=False, f_high=True, m_high=True,
        description="购买频繁且消费高，但最近未购买，需唤回",
        color="#4ECDC4", priority=2,
    ),
    SegmentDefinition(
        segment_id=3, name_cn="重要发展客户", name_en="Potential Loyalists",
        r_high=True, f_high=False, m_high=True,
        description="最近购买且消费高，但频次低，需提升复购",
        color="#45B7D1", priority=3,
    ),
    SegmentDefinition(
        segment_id=4, name_cn="重要挽留客户", name_en="At Risk",
        r_high=False, f_high=False, m_high=True,
        description="消费高但最近未购买且频次低，流失风险高",
        color="#96CEB4", priority=4,
    ),
    SegmentDefinition(
        segment_id=5, name_cn="一般价值客户", name_en="New Customers",
        r_high=True, f_high=True, m_high=False,
        description="最近购买且频次高，但消费低，可引导升单",
        color="#DDA0DD", priority=5,
    ),
    SegmentDefinition(
        segment_id=6, name_cn="一般保持客户", name_en="Promising",
        r_high=False, f_high=True, m_high=False,
        description="频次高但最近未购买且消费低，需激活",
        color="#98D8C8", priority=6,
    ),
    SegmentDefinition(
        segment_id=7, name_cn="一般发展客户", name_en="Need Attention",
        r_high=True, f_high=False, m_high=False,
        description="最近购买但频次和消费都低，需关注",
        color="#F7DC6F", priority=7,
    ),
    SegmentDefinition(
        segment_id=8, name_cn="一般挽留客户", name_en="About to Sleep",
        r_high=False, f_high=False, m_high=False,
        description="最近未购买、频次低、消费低，濒临流失",
        color="#BDC3C7", priority=8,
    ),
    SegmentDefinition(
        segment_id=9, name_cn="其他用户", name_en="Others",
        r_high=False, f_high=False, m_high=False,
        description="未命中任何象限的用户",
        color="#BDC3C7", priority=99,
    ),
]


class SegmentRegistry:
    """人群分层注册表"""

    def __init__(self):
        self._segments: Dict[int, SegmentDefinition] = {s.segment_id: s for s in SEGMENTS}

    def get(self, segment_id: int) -> Optional[SegmentDefinition]:
        return self._segments.get(segment_id)

    def list_all(self) -> List[SegmentDefinition]:
        return list(self._segments.values())

    def get_name_cn(self, segment_id: int) -> str:
        s = self._segments.get(segment_id)
        return s.name_cn if s else "其他"

    def get_name_en(self, segment_id: int) -> str:
        s = self._segments.get(segment_id)
        return s.name_en if s else "Others"

    def get_color(self, segment_id: int) -> str:
        s = self._segments.get(segment_id)
        return s.color if s else "#BDC3C7"

    @staticmethod
    def build_r_score_sql(thresholds: List[int] = None) -> str:
        """生成 R 评分 CASE WHEN SQL"""
        t = thresholds or RFM_THRESHOLDS["r"]
        return f"""CASE
            WHEN recency_days < {t[0]} THEN 5
            WHEN recency_days < {t[1]} THEN 4
            WHEN recency_days < {t[2]} THEN 3
            WHEN recency_days < {t[3]} THEN 2
            ELSE 1
        END"""

    @staticmethod
    def build_f_score_sql(thresholds: List[int] = None) -> str:
        """生成 F 评分 CASE WHEN SQL"""
        t = thresholds or RFM_THRESHOLDS["f"]
        return f"""CASE
            WHEN frequency >= {t[3] + 1} THEN 5
            WHEN frequency >= {t[2] + 1} THEN 4
            WHEN frequency = {t[2]} THEN 3
            WHEN frequency = {t[1]} THEN 2
            ELSE 1
        END"""

    @staticmethod
    def build_m_score_sql(thresholds: List[int] = None) -> str:
        """生成 M 评分 CASE WHEN SQL"""
        t = thresholds or RFM_THRESHOLDS["m"]
        return f"""CASE
            WHEN monetary >= {t[3]} THEN 5
            WHEN monetary >= {t[2]} THEN 4
            WHEN monetary >= {t[1]} THEN 3
            WHEN monetary >= {t[0]} THEN 2
            ELSE 1
        END"""

    def build_segment_case_when_sql(self) -> str:
        """生成 8象限 segment_id 的 CASE WHEN SQL（经典分割：>=4 vs <4）"""
        parts = []
        for seg in SEGMENTS:
            if seg.segment_id == 9:
                continue
            r_op = ">= 4" if seg.r_high else "< 4"
            f_op = ">= 4" if seg.f_high else "< 4"
            m_op = ">= 4" if seg.m_high else "< 4"
            parts.append(
                f"WHEN r_score {r_op} AND f_score {f_op} AND m_score {m_op} THEN {seg.segment_id}"
            )
        parts.append("ELSE 9")
        return f"CASE {' '.join(parts)} END"

    def build_segment_name_case_when_sql(self, lang: str = "cn") -> str:
        """生成 segment_name 的 CASE WHEN SQL"""
        parts = []
        for seg in SEGMENTS:
            name = seg.name_cn if lang == "cn" else seg.name_en
            parts.append(f"WHEN {seg.segment_id} THEN '{name}'")
        return f"CASE segment_id {' '.join(parts)} END"


# 全局单例
_registry = SegmentRegistry()


def get_registry() -> SegmentRegistry:
    return _registry
