"""
一键拆解服务 v2

基于历史数据自动完成大促拆解：
- 老客：按R区间（6档）× F段（F>1/F=1）逐层预估
- 新客：按渠道漏斗逐渠道预估
- 支持顺拆（现状→预估）和倒拆（目标→反推）两种模式
- 仅GSV口径

参考：[PROCEDURE] 芙清老客拆解四步法、[PROCEDURE] 芙清新客拆解、[PROCEDURE] 老客RFM分析四步法
"""

from typing import List, Dict, Any


# 语义层统一口径
_VALID_BASE = "is_goujinjin = FALSE AND order_status != '交易关闭'"
_VALID_BASE_T = "o.is_goujinjin = FALSE AND o.order_status != '交易关闭'"


# ── 常量 ─────────────────────────────────────────────────────

# 老客回购率调整系数（基于经验，大促期回购率更高）
REPURCHASE_ADJUSTMENT = {
    "大促期": 1.15,
    "日常": 1.0,
    "年货节": 1.10,
    "3.8": 1.08,
    "618": 1.20,
    "双11": 1.25,
}

# R区间定义（与老客健康分析 RIntervalTab 一致）
# cutoff = 活动开始日 - 1天
R_INTERVALS = [
    ("近1个月已购客",    0,   30),
    ("近2-3个月已购客",  31,  90),
    ("近4-6月已购客",    91, 180),
    ("近7-12个月已购客", 181, 365),
    ("近13-24个月已购客",366, 730),
    ("2年外已购客",      731, 99999),
]

# F分段
F_SEGMENTS = ["F>1", "F=1"]

# 新客相关常量
NEW_CUSTOMER_GROWTH_FACTOR = 1.1       # 新客同比增长系数
DEFAULT_MEMBER_JOIN_RATE = 0.025       # 默认入会率 2.5%
UV_MULTIPLIER = 20                     # UV估算倍数（购买人数×20）

# 渠道固定排序（芙清8层漏斗）
CHANNEL_ORDER = ['货架', '达播', '直播', '淘客', '微博', 'U先派样', '百补派样', '赠品&0.01', '其他']

# GSV口径（硬编码，不支持GMV切换）
GSV_AMOUNT_COL = """
    CASE WHEN is_refund = FALSE AND order_status != '交易关闭'
         THEN actual_amount ELSE 0 END
""".strip()


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
