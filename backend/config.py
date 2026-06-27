"""
Sample CRM 客户分析系统 - 后端配置 (Sprint 131 P0-2 写死运营配置)

战略转向 (user 2026-06-27 拍板): 不再追求性能/灵活性, 写死代码方便运营。
所有环境变量 (.env 加载) 已删除, 配置写死到代码常量。
"""

from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
PARQUET_DATA_DIR = DATA_DIR / "parquet"  # Parquet 缓存（ETL 增量写入）

# 数据源路径（写死运营配置, Sprint 131 P0-2）
_CRM_BASE = Path.home() / "Desktop" / "fuqin-date" / "芙清CRM数据库" / "芙清crm原始数据库"

SHOP_DATA_SOURCE = _CRM_BASE / "店铺数据库"
MEMBER_DATA_SOURCE = _CRM_BASE / "会员数据库"
SPU_MAPPING_SOURCE = _CRM_BASE / "天猫_spu单品匹配表_数据表.csv"

# 每日状态刷新 CSV 源文件（手动放置近30天 CSV）
SHOP_STATUS_SOURCE = _CRM_BASE
SHOP_STATUS_REFRESH_DIR = SHOP_STATUS_SOURCE / "订单状态刷新"

# 店铺流量数据（访客数/新增会员数）
VISITOR_DATA_SOURCE = _CRM_BASE / "店铺流量数据库"

VISITOR_XLSX_FILE = VISITOR_DATA_SOURCE / "24-26年访客数情况0427.xlsx"

# 活动节奏数据（大促时间表）
CAMPAIGN_SCHEDULE_SOURCE = _CRM_BASE / "Sample全年平台活动节奏 - Sheet2.csv"

# 渠道判定规则表
CHANNEL_RULES_SOURCE = _CRM_BASE / "渠道判定.csv"

# 淘客数据库（历史曾称 affiliate）
TAOKE_DATA_SOURCE = _CRM_BASE / "淘客数据库"

# 淘客商品ID表（历史曾称 affiliate）
TAOKE_PRODUCT_SOURCE = _CRM_BASE / "天猫_淘客数据商品ID_数据表.csv"

# 直播间数据源
LIVE_DATA_SOURCE = _CRM_BASE / "直播间数据源"

def get_shop_files():
    """获取所有店铺数据文件（递归搜索）"""
    return list(SHOP_DATA_SOURCE.rglob("*.xlsx"))

def get_member_files():
    """获取所有会员数据文件（递归搜索）"""
    return list(MEMBER_DATA_SOURCE.rglob("*.xlsx"))

def get_shop_status_files():
    """获取店铺今日放入的状态刷新文件（优先 .zip，兼容 .csv，只取最新一个）

    扫描路径: SHOP_STATUS_REFRESH_DIR（Samplecrm原始数据库/订单状态刷新/）
    用户每天将最新状态 zip 放入该目录，脚本自动解压并读取。
    只读取今天修改的文件，避免误用旧文件。
    """
    from datetime import datetime
    today = datetime.now().date()
    source_dir = SHOP_STATUS_REFRESH_DIR if SHOP_STATUS_REFRESH_DIR.exists() else SHOP_STATUS_SOURCE

    # 优先匹配 zip，其次 csv
    all_files = []
    for pattern in ["*.zip", "*.csv"]:
        all_files.extend(source_dir.glob(pattern))

    files = sorted(
        [f for f in all_files
         if datetime.fromtimestamp(f.stat().st_mtime).date() == today],
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )
    return files[:1] if files else []

# P3 fix: 路径环境变量化，默认指向 monorepo 内的 scraper/core（2026-06-02 物理合并 work plat → scraper/）
# 2026-06-02 数据物理迁移完成，scraper/core/ 是主路径；空字符串 fallback 修复（之前 DMP_DATA_DIR="" 会
# 导致 Path("") 解析为 Path(".")，不是默认 monorepo 路径）
# Sprint 131 P0-2 写死运营配置
DMP_DATA_DIR = PROJECT_ROOT / "scraper" / "core"
DMP_DATA2_PATH = DMP_DATA_DIR / "data2.csv"   # 全店资产（日级）
DMP_DATA3_PATH = DMP_DATA_DIR / "data3.csv"   # 单品资产（周级）
DMP_DATA_PATH = DMP_DATA_DIR / "data.csv"     # 人群漏斗流转数据（日级）

# DuckDB 数据库路径（写死运营配置, Sprint 131 P0-2）
DUCKDB_PATH = PROJECT_ROOT / "data" / "processed" / "fuqing_crm.duckdb"

# DuckDB 内存限制（写死 8GB，避免占用过多系统内存）
# Sprint 131 P0-2 写死运营配置
DUCKDB_MEMORY_LIMIT = "8GB"


def get_duckdb_memory_limit() -> str:
    """返回 DuckDB 内存限制。Sprint 131 P0-2 写死 8GB, 不再读 env override。

    保留此函数以保持向后兼容（scripts/etl/precompute_fact_rfm.py 等 ETL 模块仍调用），
    但不再根据环境变量动态调整，统一返回 "8GB"。
    """
    return DUCKDB_MEMORY_LIMIT

# 数据库模式（写死 production: 缺 orders 表 / 0 行 / max(pay_time) < today-30d → raise RuntimeError 拒绝启动）
# Sprint 131 P0-2 写死运营配置
DB_MODE = "production"
# 数据新鲜度阈值（天）: 写死 30 天
DB_FRESHNESS_DAYS = 30

# 日志配置
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 数据清洗配置 (Sprint 131 P0-2 写死运营配置)
YEAR_RANGE = (2025, 2026)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ─────────────────────────────────────────────────────────────
# API 默认日期（动态，避免硬编码过时日期）
# ─────────────────────────────────────────────────────────────
from datetime import date, timedelta

def _default_end_date() -> str:
    """默认结束日期：昨天"""
    return (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

def _default_start_date() -> str:
    """默认开始日期：当月1号"""
    today = date.today()
    return today.replace(day=1).strftime("%Y-%m-%d")

# 会员定义基准日期（用于判断新老客，写死运营配置 Sprint 131 P0-2）
MEMBER_BASE_DATE = "2025-01-01"

# 老客回购率调整系数（基于经验，大促期回购率更高）
# 拆解服务根据活动类型选取对应系数
REPURCHASE_ADJUSTMENT = {
    "大促期": 1.15,
    "日常": 1.0,
    "年货节": 1.10,
    "3.8": 1.08,
    "summer_sale": 1.20,
    "双11": 1.25,
}
