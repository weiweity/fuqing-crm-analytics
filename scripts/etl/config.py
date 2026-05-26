"""ETL 配置与缓存工具
路径配置、列名映射、缓存读写（淘客/直播/已处理文件）。
"""
import json
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # scripts/etl → scripts → project root
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import (
    DUCKDB_PATH, SHOP_DATA_SOURCE, MEMBER_DATA_SOURCE, SPU_MAPPING_SOURCE,
    PROCESSED_DATA_DIR, PARQUET_DATA_DIR, CHANNEL_RULES_SOURCE,
    TAOKE_DATA_SOURCE, TAOKE_PRODUCT_SOURCE, LIVE_DATA_SOURCE
)

import pandas as pd
import duckdb
import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

COLUMN_MAPPING = {
    '订单编号': 'order_id',
    '子订单号': 'sub_order_id',
    '用户ID': 'user_id',
    '买家昵称': 'user_nickname',
    '下单时间': 'order_time',
    '付款时间': 'pay_time',
    '发货时间': 'ship_time',
    '订单类型': 'order_type',
    '子订单状态': 'order_status',
    '商品ID': 'product_id',
    '商家编码': 'merchant_code',
    '商品标题': 'product_title',
    'SKUID': 'sku_id',
    'SKU编号': 'sku_code',
    'SKU名称': 'sku_name',
    '购买数量': 'quantity',
    '应付金额': 'amount',
    '退款状态': 'refund_status',
    '退款金额': 'refund_amount',
    '实付金额': 'actual_amount',
    '收货人省份': 'province',
    '收货人城市': 'city',
    '达人名称': 'influencer_name',
    '达人id': 'influencer_id',
    '直播间id': 'live_room_id',
    '视频id': 'video_id',
    '流量来源': 'traffic_source',
    '流量体裁': 'traffic_type',
    '卖家备注': 'seller_note'
}

# SPU 列名映射
# 原始 Excel 有合并单元格，pandas 读取 CSV 时 header 与 data 错位（从 col2 开始偏移 1 列）
# 正确映射：按 data 内容反推 → 直接用列位置重命名
#   col0 = 商品ID → product_id
#   col1 = 品类销售 → spu_category
#   col2 = "妆品销售/械品销售" → spu_category 二次映射（品类销售下钻）
#   col3 = "小样-U先/正装"    → spu_type（正装/小样）
#   col4 = "二梯队/核心品"   → spu_tier（商品梯队）
#   col5 = "胶原膜/..."     → spu_product_class（单品归类）
#   col6 = "胶原膜/..."     → spu_product_subclass（单品细分）
#   col7 = "械/妆"         → spu_cosmetic（妆/械）
#   col8 = "胶原膜*2片/..." → spu_spec（商品规格）
#   col9 = "2000/1/1"      → spu_start_date
#   col10 = "45368"        → spu_end_date（Excel serial，load_spu_mapping 中统一转日期）
SPU_COLUMNS = {
    '商品ID': 'product_id',
    '品类销售': 'spu_category',
    '正装/小样': 'spu_type',
    '商品梯队': 'spu_tier',
    '单品归类': 'spu_product_class',
    '单品细分': 'spu_product_subclass',
    '妆/械': 'spu_cosmetic',
    '商品规格': 'spu_spec',
    '开始时间': 'spu_start_date',
    '结束时间': 'spu_end_date'
}

TAOKE_COL = "淘宝父订单编号"

# 淘客订单号全局缓存（进程生命周期内只读一次文件）
_TAOKE_ORDER_IDS_CACHE = None

# 直播订单号全局缓存（进程生命周期内只读一次文件）
_LIVE_ORDER_IDS_CACHE = None

# 淘客商品ID规则缓存（进程生命周期内只读一次文件）
# 格式: [(product_id_str, start_date, end_date), ...]
_TAOKE_PRODUCT_RULES_CACHE = None

# ETL 各数据源扫描统计（供结尾摘要表使用）
_ETL_SOURCE_STATS = {}


def _get_taoke_cache_path():
    """淘客文件级缓存路径（记录每个文件的 mtime + 订单ID列表）"""
    return PROCESSED_DATA_DIR / "taoke_file_cache.json"


def _load_taoke_cache():
    """加载淘客文件缓存。格式: {filename: {"mtime": float, "ids": [str, ...]}}"""
    path = _get_taoke_cache_path()
    if path.exists():
        import json
        with open(path, 'r') as f:
            return json.load(f)
    return {}


def _save_taoke_cache(cache):
    """保存淘客文件缓存"""
    import json
    path = _get_taoke_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(cache, f, indent=2, sort_keys=True)


def _get_live_cache_path():
    """直播文件级缓存路径（记录每个文件的 mtime + 订单ID列表）"""
    return PROCESSED_DATA_DIR / "live_file_cache.json"


def _load_live_cache():
    """加载直播文件缓存。格式: {filename: {"mtime": float, "ids": [str, ...]}}"""
    path = _get_live_cache_path()
    if path.exists():
        import json
        with open(path, 'r') as f:
            return json.load(f)
    return {}


def _save_live_cache(cache):
    """保存直播文件缓存"""
    import json
    path = _get_live_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(cache, f, indent=2, sort_keys=True)




def _get_processed_files_path(data_type):
    """获取已处理文件的追踪路径（新格式：path→mtime dict）"""
    return PROCESSED_DATA_DIR / f"processed_files_{data_type}.json"


def _load_processed_files(data_type):
    """加载已处理文件列表。
    新格式: {"path": mtime, ...}
    兼容旧格式(list): 自动转为 dict，mtime=0（下次会重新处理）
    """
    path = _get_processed_files_path(data_type)
    if path.exists():
        import json
        with open(path, 'r') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        # 旧格式兼容：list/set → dict(mtime=0)
        return {str(p): 0 for p in data}
    return {}


def _save_processed_files(data_type, processed_dict):
    """保存已处理文件列表（dict 格式：path→mtime）"""
    import json
    path = _get_processed_files_path(data_type)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(processed_dict, f, indent=2, sort_keys=True)


