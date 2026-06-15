"""
Sample CRM - 渠道漏斗定义

文档化 ETL 中的 8层渠道判定规则，供后端服务引用。
注意：实际的渠道判定发生在 ETL 阶段（run_etl.py match_channel），
本模块仅做规则声明和元数据管理，供 API 文档、前端下拉选项、校验逻辑使用。
"""

from dataclasses import dataclass
from typing import List, Dict


@dataclass
class ChannelDefinition:
    key: str           # 渠道标识（数据库中 channel 字段的值）
    name: str          # 中文名称
    priority: int      # 漏斗优先级（1=最高）
    description: str   # 判定规则说明
    color: str = "#999999"


# 8层漏斗定义（与 run_etl.py match_channel 完全一致）
# P4 达播/微博为同一层（由 keyword_rules / id_rules 决定具体渠道值）
CHANNEL_FUNNEL: List[ChannelDefinition] = [
    ChannelDefinition(
        key="U先派样",
        name="U先派样",
        priority=1,
        description="spu_type 含'小样-U先' 或 product_title 含'U先' 或 product_title 含'会员尝鲜'",
        color="#E74C3C",
    ),
    ChannelDefinition(
        key="百补派样",
        name="百补派样",
        priority=2,
        description="spu_type 含'小样-百亿补贴' 或 product_title 含'by'",
        color="#E67E22",
    ),
    ChannelDefinition(
        key="赠品&0.01渠道",
        name="赠品&0.01",
        priority=3,
        description="spu_type 含'小样'(排除U先/百补) 或 product_title 含'赠品'",
        color="#F1C40F",
    ),
    ChannelDefinition(
        key="达播",
        name="达播",
        priority=4,
        description="渠道判定表 keyword_rules / id_rules 匹配达播来源（P4，与微博同层）",
        color="#9B59B6",
    ),
    ChannelDefinition(
        key="微博",
        name="微博",
        priority=4,
        description="渠道判定表 keyword_rules / id_rules 匹配微博来源（P4，与达播同层）",
        color="#8E44AD",
    ),
    ChannelDefinition(
        key="直播",
        name="直播",
        priority=5,
        description="order_id 匹配直播CSV父订单号（仅对未匹配订单生效）",
        color="#FF6B6B",
    ),
    ChannelDefinition(
        key="淘客",
        name="淘客",
        priority=6,
        description="P6 订单号匹配 或 P6-2 标题含T1/T2/T4/TK（仅对未匹配订单生效，每次全量重建。Sprint 24 P0: 治根 a505f85 脱敏副作用, DB 真值 '淘客'）",
        color="#3498DB",
    ),
    ChannelDefinition(
        key="购物金",
        name="购物金",
        priority=7,
        description="product_title 含'购物金'（仅对未匹配订单生效，ETL中标记后剔除）",
        color="#1ABC9C",
    ),
    ChannelDefinition(
        key="货架",
        name="货架",
        priority=8,
        description="P1-P7未命中 且 spu_type 含'正装'",
        color="#2ECC71",
    ),
    ChannelDefinition(
        key="其他",
        name="其他",
        priority=9,
        description="P1-P8未命中",
        color="#95A5A6",
    ),
]

# 优先级映射
CHANNEL_PRIORITY: Dict[str, int] = {c.key: c.priority for c in CHANNEL_FUNNEL}

# 用于人群看板渠道筛选的有效渠道列表（剔除购物金，因为购物金订单已被剔除）
ACTIVE_CHANNELS: List[str] = [c.key for c in CHANNEL_FUNNEL if c.key not in ("购物金",)]


# ── DB ↔ UI 映射 ─────────────────────────────────────────────
# ETL 写入 DB 的渠道名与 UI 展示名存在差异（大小写、后缀等）
# 本模块作为唯一真实数据源，所有渠道名转换必须从此导入

# DB 实际名 → UI 展示名
DB_TO_UI: Dict[str, str] = {
    "货架": "货架",
    "直播": "直播",
    "affiliate": "淘客",  # Sprint 24 P0 A3: 旧 alias 映射到新 key, 治根 + 不破前端
    "淘客": "淘客",  # Sprint 24 P0 治根 (a505f85 改前就是 "淘客")
    "微博": "微博",
    "U先派样": "U先派样",  # DB/UI 统一大写U
    "百补派样": "百补派样",
    "其他": "其他",
    "赠品&0.01渠道": "赠品&0.01",
    "达播": "达播",
}

# UI 展示名 → DB 实际名
UI_TO_DB: Dict[str, str] = {v: k for k, v in DB_TO_UI.items()}

# 人群看板渠道展示顺序（UI 名）
CHANNEL_ORDER: List[str] = ["货架", "达播", "直播", "淘客", "微博", "U先派样", "百补派样", "赠品&0.01", "其他"]  # Sprint 24 P0: 治根 affiliate → 淘客

# 用于筛选的有效 UI 渠道列表（剔除购物金）
ACTIVE_UI_CHANNELS: List[str] = [c.name for c in CHANNEL_FUNNEL if c.key not in ("购物金",)]

# 0.01派样相关常量（避免服务层多处硬编码渠道名）
# 数据来源：CHANNEL_FUNNEL，与 ETL 判定规则一致
GIFT_SAMPLE_DB = "赠品&0.01渠道"
SHELF_DB = "货架"


def get_channel_def(key: str) -> ChannelDefinition:
    # Sprint 24 P0 A3: 旧 alias "affiliate" 兼容, 返 "淘客" def
    if key == "affiliate":
        key = "淘客"
    for c in CHANNEL_FUNNEL:
        if c.key == key:
            return c
    return ChannelDefinition(key=key, name=key, priority=99, description="未知渠道")
