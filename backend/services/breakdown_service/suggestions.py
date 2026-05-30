"""
一键拆解服务 v2 - 补gap建议生成

基于历史数据自动完成大促拆解：
- 老客：按R区间（6档）× F段（F>1/F=1）逐层预估
- 新客：按渠道漏斗逐渠道预估
- 支持顺拆（现状→预估）和倒拆（目标→反推）两种模式
- 仅GSV口径

参考：[PROCEDURE] 芙清老客拆解四步法、[PROCEDURE] 芙清新客拆解、[PROCEDURE] 老客RFM分析四步法
"""

from typing import List, Dict, Any

from backend.semantic.filters import VALID_ORDER_BASE, VALID_ORDER_BASE_PREFIXED

# 语义层统一口径（向后兼容别名）
_VALID_BASE = VALID_ORDER_BASE
_VALID_BASE_T = VALID_ORDER_BASE_PREFIXED


# ── 工具函数 ─────────────────────────────────────────────────


def _generate_suggestions(
    old_gap: float,
    old_target: float,
    new_gap: float,
    new_target: float,
    total_gap: float,
    target_gmv: float
) -> List[Dict[str, Any]]:
    """生成补gap建议"""
    suggestions = []

    if old_gap > 0:
        old_suggestions = []
        if old_gap / old_target > 0.2:
            old_suggestions.append("老客gap较大（>20%），建议加大老客offer力度（复购礼/老客专享券）")
            old_suggestions.append("增加老客触达轮次，短信+客服+群聊组合触达")
        else:
            old_suggestions.append("适当加深老客offer力度")

        old_suggestions.append("唤醒近7-12个月及更久沉睡客户，发送大额回归券")
        old_suggestions.append("针对近1个月高活跃老客，推复购礼/套装提升客单价")

        suggestions.append({
            "dimension": "老客",
            "gap_amount": round(old_gap, 2),
            "suggestions": old_suggestions,
            "priority": "P0" if old_gap / max(old_target, 1) > 0.2 else "P1"
        })

    if new_gap > 0:
        new_suggestions = []
        if new_gap / max(new_target, 1) > 0.2:
            new_suggestions.append("新客gap较大（>20%），建议加大派样力度（U先/小美盒）")
            new_suggestions.append("提升入会率：优化入会引导、增加0.01特权钩子")
        else:
            new_suggestions.append("适当增加新客招募渠道")

        new_suggestions.append("优化钩子商品，提升首单转化率")
        new_suggestions.append("加大达播投入，达播新客是重要新客来源")

        suggestions.append({
            "dimension": "新客",
            "gap_amount": round(new_gap, 2),
            "suggestions": new_suggestions,
            "priority": "P0" if new_gap / max(new_target, 1) > 0.2 else "P1"
        })

    if total_gap > 0 and total_gap / max(target_gmv, 1) > 0.3:
        suggestions.append({
            "dimension": "总店",
            "gap_amount": round(total_gap, 2),
            "suggestions": [
                "总gap较大（>30%），建议重新评估目标合理性",
                "考虑降低目标或延长活动周期",
                "紧急加大达播/店播投入，快速提升GMV"
            ],
            "priority": "P0"
        })

    return suggestions


# ── 主入口 ───────────────────────────────────────────────────
