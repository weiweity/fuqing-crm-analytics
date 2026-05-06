"""
芙清 CRM 客户分析系统 - 后端配置
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（本地开发配置，不上传 GitHub）
load_dotenv()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
PARQUET_DATA_DIR = DATA_DIR / "parquet"  # Parquet 缓存（店铺+会员 xlsx 转换后存储）

# P3 fix: 路径环境变量化，默认值使用当前用户 home 目录（避免硬编码用户名）
_DEFAULT_CRM_BASE = Path.home() / "Desktop" / "fuqin date" / "芙清CRM数据库" / "芙清crm原始数据库"

SHOP_DATA_SOURCE = Path(os.environ.get(
    "SHOP_DATA_SOURCE",
    str(_DEFAULT_CRM_BASE / "店铺数据库")
))
MEMBER_DATA_SOURCE = Path(os.environ.get(
    "MEMBER_DATA_SOURCE",
    str(_DEFAULT_CRM_BASE / "会员数据库")
))
SPU_MAPPING_SOURCE = Path(os.environ.get(
    "SPU_MAPPING_SOURCE",
    str(_DEFAULT_CRM_BASE / "天猫_spu单品匹配表_数据表.csv")
))

# 每日状态刷新 CSV 源文件（手动放置近30天 CSV）
SHOP_STATUS_SOURCE = Path(os.environ.get(
    "SHOP_STATUS_SOURCE",
    str(_DEFAULT_CRM_BASE)
))
SHOP_STATUS_REFRESH_DIR = SHOP_STATUS_SOURCE / "订单状态刷新"

# 店铺流量数据（访客数/新增会员数）
VISITOR_DATA_SOURCE = Path(os.environ.get(
    "VISITOR_DATA_SOURCE",
    str(_DEFAULT_CRM_BASE / "店铺流量数据库")
))

# 活动节奏数据（大促时间表）
CAMPAIGN_SCHEDULE_SOURCE = Path(os.environ.get(
    "CAMPAIGN_SCHEDULE_SOURCE",
    str(_DEFAULT_CRM_BASE / "芙清全年平台活动节奏 - Sheet2.csv")
))

def get_shop_files():
    """获取所有店铺数据文件（递归搜索）"""
    return list(SHOP_DATA_SOURCE.rglob("*.xlsx"))

def get_member_files():
    """获取所有会员数据文件（递归搜索）"""
    return list(MEMBER_DATA_SOURCE.rglob("*.xlsx"))

def get_shop_status_files():
    """获取店铺今日放入的状态刷新文件（优先 .zip，兼容 .csv，只取最新一个）

    扫描路径: SHOP_STATUS_REFRESH_DIR（芙清crm原始数据库/订单状态刷新/）
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

# P3 fix: 路径环境变量化
_DEFAULT_DMP_DIR = Path.home() / "Desktop" / "work plat" / "DMP_test_package" / "core"
DMP_DATA_DIR = Path(os.environ.get("DMP_DATA_DIR", str(_DEFAULT_DMP_DIR)))
DMP_DATA2_PATH = DMP_DATA_DIR / "data2.csv"   # 全店资产（日级）
DMP_DATA3_PATH = DMP_DATA_DIR / "data3.csv"   # 单品资产（周级）
DMP_DATA_PATH = DMP_DATA_DIR / "data.csv"     # 人群漏斗流转数据（日级）

# DuckDB 数据库路径（默认使用项目内相对路径）
_DEFAULT_DUCKDB = PROJECT_ROOT / "data" / "processed" / "fuqing_crm.duckdb"
DUCKDB_PATH = Path(os.environ.get("DUCKDB_PATH", str(_DEFAULT_DUCKDB)))

# 日志配置
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 数据清洗配置
YEAR_RANGE = (2025, 2026)  # 处理的年份范围
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 会员定义基准日期（用于判断新老客）
MEMBER_BASE_DATE = "2025-01-01"  # 2025年1月1日之前有过购买记录的为老客

# 新老客定义
def classify_new_old_user(first_order_date: str, analysis_date: str) -> str:
    """
    判断用户是新客还是老客
    - 老客: 在分析周期开始之前有过购买记录
    - 新客: 在分析周期内首次购买
    """
    if not first_order_date:
        return "新客"
    if first_order_date < analysis_date:
        return "老客"
    return "新客"
