"""
Sample CRM 客户分析系统 - 后端配置
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（本地开发配置，不上传 GitHub）
# Sprint 108 必修 1 L4.7 实战 fix 模式: xdist parallel pytest 触发 dotenv main.py:358 FileNotFoundError
# (跟 Sprint 38 race flake 治本同模式, 真治本: try/except 兜底, 不再依赖 .env 存在).
try:
    load_dotenv()
except FileNotFoundError:
    # 无 .env 文件不阻断启动 — 环境变量可来自 CI / shell export / CI secret
    pass

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
PARQUET_DATA_DIR = DATA_DIR / "parquet"  # Parquet 缓存（ETL 增量写入）

# P3 fix: 路径环境变量化，默认值使用当前用户 home 目录（避免硬编码用户名）
_DEFAULT_CRM_BASE = Path.home() / "Desktop" / "fuqin-date" / "芙清CRM数据库" / "芙清crm原始数据库"

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

VISITOR_XLSX_FILE = Path(os.environ.get(
    "VISITOR_XLSX_FILE",
    str(VISITOR_DATA_SOURCE / "24-26年访客数情况0427.xlsx")
))

# 活动节奏数据（大促时间表）
CAMPAIGN_SCHEDULE_SOURCE = Path(os.environ.get(
    "CAMPAIGN_SCHEDULE_SOURCE",
    str(_DEFAULT_CRM_BASE / "Sample全年平台活动节奏 - Sheet2.csv")
))

# 渠道判定规则表
CHANNEL_RULES_SOURCE = Path(os.environ.get(
    "CHANNEL_RULES_SOURCE",
    str(_DEFAULT_CRM_BASE / "渠道判定.csv")
))

# 淘客数据库（历史曾称 affiliate）
TAOKE_DATA_SOURCE = Path(os.environ.get(
    "TAOKE_DATA_SOURCE",
    str(_DEFAULT_CRM_BASE / "淘客数据库")
))

# 淘客商品ID表（历史曾称 affiliate）
TAOKE_PRODUCT_SOURCE = Path(os.environ.get(
    "TAOKE_PRODUCT_SOURCE",
    str(_DEFAULT_CRM_BASE / "天猫_淘客数据商品ID_数据表.csv")
))

# 直播间数据源
LIVE_DATA_SOURCE = Path(os.environ.get(
    "LIVE_DATA_SOURCE",
    str(_DEFAULT_CRM_BASE / "直播间数据源")
))

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
_DEFAULT_DMP_DIR = PROJECT_ROOT / "scraper" / "core"
_DMP_DATA_DIR_ENV = os.environ.get("DMP_DATA_DIR", "").strip()
DMP_DATA_DIR = Path(_DMP_DATA_DIR_ENV) if _DMP_DATA_DIR_ENV else _DEFAULT_DMP_DIR
DMP_DATA2_PATH = DMP_DATA_DIR / "data2.csv"   # 全店资产（日级）
DMP_DATA3_PATH = DMP_DATA_DIR / "data3.csv"   # 单品资产（周级）
DMP_DATA_PATH = DMP_DATA_DIR / "data.csv"     # 人群漏斗流转数据（日级）

# DuckDB 数据库路径（默认使用项目内相对路径）
_DEFAULT_DUCKDB = PROJECT_ROOT / "data" / "processed" / "fuqing_crm.duckdb"
DUCKDB_PATH = Path(os.environ.get("DUCKDB_PATH", str(_DEFAULT_DUCKDB)))

# DuckDB 内存限制（默认 8GB，避免占用过多系统内存）
# DuckDB 默认使用 80% 系统 RAM，在 16GB 机器上约 12.7GB，容易导致 OOM
DUCKDB_MEMORY_LIMIT = os.environ.get("DUCKDB_MEMORY_LIMIT", "8GB")

# 数据库模式 (Sprint 61 P2 治本): 控制 lifespan 启动校验严格度
# - "production" (默认): 缺 orders 表 / 0 行 / max(pay_time) < today-30d → raise RuntimeError 拒绝启动
# - "schema_test" (CI e2e / schema_test): 跳过数据量检查, 只 WARN log
# - 其他值: 默认 production 行为 (fail-fast)
DB_MODE = os.environ.get("FQ_DB_MODE", "production").strip().lower()
# 数据新鲜度阈值（天）: orders.max(pay_time) 距今超过此天数 → 拒绝启动
DB_FRESHNESS_DAYS = int(os.environ.get("FQ_DB_FRESHNESS_DAYS", "30"))

# W7: DuckDB 内存 override（W4 全历史预计算需要 16GB，平时 8GB）
# 用法：export DUCKDB_MEMORY_LIMIT_OVERRIDE=16GB  临时调高；不设 = 跟默认
# 调用方优先用 get_duckdb_memory_limit() helper；DUCKDB_MEMORY_LIMIT 常量保留
# 向后兼容（8 处 import 仍可用，但读到的是默认 8GB，不会读 override——override
# 仅在 W4 async 跑批期间通过 get_duckdb_memory_limit() 生效）
# DUCKDB_MEMORY_LIMIT_OVERRIDE 不在 module-level 缓存（每次 get_duckdb_memory_limit()
# 动态读 os.environ，monkeypatch.setenv 测试场景正常工作）
# 常量保留仅为向后兼容（业务代码可读这个，但用 helper 才能拿到 override 生效值）
DUCKDB_MEMORY_LIMIT_OVERRIDE = os.environ.get("DUCKDB_MEMORY_LIMIT_OVERRIDE", "").strip()


def get_duckdb_memory_limit() -> str:
    """返回当前生效的 DuckDB 内存限制（override 优先于默认，动态读 env）。

    Returns:
        str: 形如 "8GB" / "16GB" / "1024MB" 的 DuckDB memory_limit 配置值。

    Examples:
        >>> os.environ.pop("DUCKDB_MEMORY_LIMIT_OVERRIDE", None)
        >>> get_duckdb_memory_limit()  # 默认 8GB
        '8GB'
        >>> os.environ["DUCKDB_MEMORY_LIMIT_OVERRIDE"] = "16GB"
        >>> get_duckdb_memory_limit()
        '16GB'
        >>> os.environ["DUCKDB_MEMORY_LIMIT_OVERRIDE"] = ""  # 空字符串 = 走默认
        >>> get_duckdb_memory_limit()
        '8GB'

    CLAUDE.md 合规：
        ① 不破坏现有 DUCKDB_MEMORY_LIMIT=8GB 默认值（向后兼容）
        ② 临时 override 只在 W4 async 期间生效（export 后 unset），不影响日常 ETL
    """
    # 动态读 env（不缓存 module-level），让 monkeypatch.setenv / W4 async export 实时生效
    override = os.environ.get("DUCKDB_MEMORY_LIMIT_OVERRIDE", "").strip()
    if override:
        return override
    return os.environ.get("DUCKDB_MEMORY_LIMIT", "8GB")

# 日志配置
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 数据清洗配置
_year_start = int(os.environ.get("YEAR_RANGE_START", "2025"))
_year_end = int(os.environ.get("YEAR_RANGE_END", "2026"))
YEAR_RANGE = (_year_start, _year_end)
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

# 会员定义基准日期（用于判断新老客）
MEMBER_BASE_DATE = os.environ.get("MEMBER_BASE_DATE", "2025-01-01")

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
