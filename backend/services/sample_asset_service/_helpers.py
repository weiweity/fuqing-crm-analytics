"""
sample_asset_service 包共享辅助函数

从 sample_asset_service.py (809行) 拆分后恢复。
原始文件: backend/services/sample_asset_service.py (commit c411cde)
"""

import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any

import pandas as pd

from backend.config import DMP_DATA2_PATH, DMP_DATA3_PATH


# ─────────────────────────────────────────────────────────────
# 缓存（线程安全，跨三个子模块共享）
# ─────────────────────────────────────────────────────────────
_cache = {
    "data2": {"mtime": 0, "df": None},
    "data3": {"mtime": 0, "df": None, "result": None, "result_other": None},
}
_cache_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────
# data3.csv ID → 产品名称映射（跨模块共享）
# ─────────────────────────────────────────────────────────────
ID_TO_PRODUCT = {
    587051744204: "经典膜",
    803474428381: "凉茶次抛",
    870597889980: "凉茶水乳",
    994162104051: "凉茶面霜",
    933524395698: "童颜乳酸次抛",
    900975734816: "童颜乳酸面膜",
    1010458880710: "传明酸面膜",
}

ID_TO_PRODUCT_OTHER = {
    587053192746: "医用凝胶",
    597655781410: "医用洁面",
    601760206476: "黑膜",
    612503357090: "胶原水乳",
    621639424901: "白膜",
    654390297284: "祛痘精华",
    683395365107: "水杨酸涂抹面膜",
    803417397714: "凉茶面膜",
}

_ALL_ID_TO_PRODUCT = {**ID_TO_PRODUCT, **ID_TO_PRODUCT_OTHER}

# 产品展示顺序（单一数据源，前端 CORE_PRODUCTS 应与此保持一致）
PRODUCT_ORDER = list(ID_TO_PRODUCT.values())

PRODUCT_TO_SPU_CLASSES: Dict[str, List[str]] = {
    "经典膜": ["经典膜", "【妆】经典膜"],
    "凉茶次抛": ["凉茶次抛"],
    "凉茶水乳": ["凉茶水乳"],
    "凉茶面霜": ["凉茶面霜"],
    "童颜乳酸次抛": ["童颜乳酸精华"],
    "童颜乳酸面膜": ["童颜乳酸面膜"],
    "传明酸面膜": ["传明酸光感面膜"],
}

PRODUCT_ORDER_OTHER = list(ID_TO_PRODUCT_OTHER.values())

PRODUCT_TO_SPU_CLASSES_OTHER: Dict[str, List[str]] = {
    "医用凝胶": ["医用凝胶"],
    "医用洁面": ["医用洁面"],
    "黑膜": ["黑膜"],
    "胶原水乳": ["胶原水乳"],
    "白膜": ["白膜"],
    "祛痘精华": ["祛痘精华"],
    "水杨酸涂抹面膜": ["水杨酸涂抹面膜"],
    "凉茶面膜": ["凉茶面膜"],
}


# ══════════════════════════════════════════════════════════════
# 辅助函数（原始文件 lines 95-182）
# ══════════════════════════════════════════════════════════════


def _parse_date(val) -> Optional[datetime]:
    """解析日期字符串"""
    if pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(str(val).strip(), fmt)
        except ValueError:
            continue
    return None


def _get_week_label(d: datetime) -> str:
    """生成周标签，如 03/23-03/29（补零对齐）"""
    week_start = d - timedelta(days=d.weekday())
    week_end = week_start + timedelta(days=6)
    return f"{week_start.month:02d}/{week_start.day:02d}-{week_end.month:02d}/{week_end.day:02d}"


def _get_week_range(d: datetime) -> tuple:
    """返回自然周的起止日期"""
    week_start = d - timedelta(days=d.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def _last_year_same_date(d: datetime) -> datetime.date:
    """
    返回去年同期同日期的 date 对象（同一月日，如 5/6 → 去年 5/6）。
    处理闰年边界：今年2/29 → 去年2/28。
    """
    try:
        return d.replace(year=d.year - 1).date()
    except ValueError:
        return d.replace(year=d.year - 1, day=28).date()


def _check_reload(key: str, path: Path) -> bool:
    """检查文件是否变化，需要重新加载"""
    if not path.exists():
        return False
    mtime = os.path.getmtime(path)
    if _cache[key]["mtime"] != mtime or _cache[key]["df"] is None:
        _cache[key]["mtime"] = mtime
        return True
    return False


def _parse_number(val) -> int:
    """解析可能带千分位逗号的数字，浮点数四舍五入"""
    if pd.isna(val):
        return 0
    if isinstance(val, (int, float)):
        return round(val)
    s = str(val).replace(",", "").replace('"', '').strip()
    try:
        return round(float(s))
    except ValueError:
        return 0


# ══════════════════════════════════════════════════════════════
# 数据加载函数
# ══════════════════════════════════════════════════════════════


def _load_data2() -> pd.DataFrame:
    """
    加载并解析 data2.csv（线程安全，CSV读取在锁内避免竞态）。
    注意：此函数本身不获取锁，调用方必须在持有 _cache_lock 时调用。
    get_store_assets 已正确持有锁后调用。
    """
    if not _check_reload("data2", DMP_DATA2_PATH):
        return _cache["data2"]["df"]
    # 在锁内完成读取（调用方持有锁）
    df = pd.read_csv(DMP_DATA2_PATH, encoding="utf-8")
    df["time"] = df["time"].apply(_parse_date)
    df = df.dropna(subset=["time"])
    for col in ["TOTAL资产总量", "Discover发现", "Engage种草", "Enthuse互动",
                "Perform行动", "Initial首购", "Numerous复购", "Keen至爱"]:
        if col in df.columns:
            df[col] = df[col].apply(_parse_number)
    _cache["data2"]["df"] = df
    return df


def _load_data3() -> pd.DataFrame:
    """
    加载并解析 data3.csv（线程安全，CSV读取在锁内避免竞态）。
    注意：此函数本身不获取锁，调用方必须在持有 _cache_lock 时调用。
    get_product_assets / get_other_product_assets 已正确持有锁后调用。
    """
    if not _check_reload("data3", DMP_DATA3_PATH):
        return _cache["data3"]["df"]
    # mtime 变了 → df 即将重读 → 清掉按 _weeks key 缓存的 result/result_other，
    # 否则 result 缓存命中时会继续返回旧数据
    _cache["data3"]["result"] = None
    _cache["data3"]["result_other"] = None
    # 在锁内完成读取（调用方持有锁）
    df = pd.read_csv(DMP_DATA3_PATH, encoding="utf-8")
    df["时间"] = df["时间"].apply(_parse_date)
    df = df.dropna(subset=["时间"])
    for col in ["资产总量", "浅种草", "深种草", "首购资产", "复购资产", "连带资产"]:
        if col in df.columns:
            df[col] = df[col].apply(_parse_number)
    df["ID"] = pd.to_numeric(df["ID"], errors="coerce")
    df = df.dropna(subset=["ID"])
    df["ID"] = df["ID"].astype(int)
    df = df[df["ID"].isin(_ALL_ID_TO_PRODUCT.keys())]
    df["product_name"] = df["ID"].map(_ALL_ID_TO_PRODUCT)
    # data_quality_flag：标识每行采集质量（legacy / verified / likely-wrong），
    # 缺列或缺值时统一填 'legacy'，与历史数据保持兼容（不会被前端过滤掉）
    if "data_quality_flag" in df.columns:
        df["data_quality_flag"] = df["data_quality_flag"].fillna("legacy").astype(str)
    else:
        df["data_quality_flag"] = "legacy"
    _cache["data3"]["df"] = df
    return df


def _validate_daily_unique(df: pd.DataFrame) -> None:
    """校验日级数据每天唯一行，否则 warn"""
    if "week_end" not in df.columns:
        return
    dup_counts = df.groupby("week_end").size()
    max_per_week = dup_counts.max()
    if max_per_week > 7:
        import logging
        logging.getLogger(__name__).warning(
            f"data2.csv: 存在一周超过7条记录（max={max_per_week}），.last()可能遗漏数据"
        )


# ══════════════════════════════════════════════════════════════
# 日维度单品资产计算（product.py 和 other.py 共用）
# ══════════════════════════════════════════════════════════════


def _compute_product_assets_daily(
    days: int,
    df: pd.DataFrame,
    id_to_product: Dict[int, str],
    product_order: List[str],
    product_to_spu: Dict[str, List[str]],
) -> Dict[str, Any]:
    """日维度单品资产计算（df 由调用方在持有锁时传入）"""
    if df is None or df.empty:
        return {"products": [], "latest_week": ""}

    df = df[df["ID"].isin(id_to_product.keys())]
    if df.empty:
        return {"products": [], "latest_week": ""}

    # 构建按 (product_name, date) 索引的字典（用于YOY查找）
    lookup_index = {}
    for _, r in df.iterrows():
        d = r["时间"]
        if pd.notna(d):
            lookup_index[(r["product_name"], d.date())] = r

    products_result = []
    latest_label = ""

    for product_name in product_order:
        product_df = df[df["product_name"] == product_name]
        if product_df.empty:
            continue

        # 按时间排序，取最近 N 天，再正序排列
        product_df = product_df.sort_values("时间", ascending=False).head(days).sort_values("时间", ascending=True)

        product_days = []
        prev_row = None
        for _, row in product_df.iterrows():
            d = row["时间"]
            date_label = d.strftime("%m/%d")
            date_str = d.strftime("%Y-%m-%d")
            latest_label = date_label

            item = {
                "week_label": date_label,
                "week_end_date": date_str,
                "quality_flag": str(row.get("data_quality_flag", "legacy")),
                "total": int(row.get("资产总量", 0)),
                "shallow_grass": int(row.get("浅种草", 0)),
                "deep_grass": int(row.get("深种草", 0)),
                "initial": int(row.get("首购资产", 0)),
                "repurchase": int(row.get("复购资产", 0)),
                "lian_dai": int(row.get("连带资产", 0)),
            }

            # 日环比
            if prev_row is not None:
                item["total_change"] = item["total"] - prev_row["total"]
                item["shallow_grass_change"] = item["shallow_grass"] - prev_row["shallow_grass"]
                item["deep_grass_change"] = item["deep_grass"] - prev_row["deep_grass"]
                item["initial_change"] = item["initial"] - prev_row["initial"]
                item["repurchase_change"] = item["repurchase"] - prev_row["repurchase"]
                item["lian_dai_change"] = item["lian_dai"] - prev_row["lian_dai"]
            else:
                item["total_change"] = 0
                item["shallow_grass_change"] = 0
                item["deep_grass_change"] = 0
                item["initial_change"] = 0
                item["repurchase_change"] = 0
                item["lian_dai_change"] = 0

            # YOY：去年同期同月日
            ly_date = _last_year_same_date(d)
            ly_key = (product_name, ly_date)
            ly_row = lookup_index.get(ly_key)
            if ly_row is not None:
                item["total_yoy"] = item["total"] - int(ly_row.get("资产总量", 0))
                item["shallow_grass_yoy"] = item["shallow_grass"] - int(ly_row.get("浅种草", 0))
                item["deep_grass_yoy"] = item["deep_grass"] - int(ly_row.get("深种草", 0))
                item["initial_yoy"] = item["initial"] - int(ly_row.get("首购资产", 0))
                item["repurchase_yoy"] = item["repurchase"] - int(ly_row.get("复购资产", 0))
                item["lian_dai_yoy"] = item["lian_dai"] - int(ly_row.get("连带资产", 0))
            else:
                item["total_yoy"] = 0
                item["shallow_grass_yoy"] = 0
                item["deep_grass_yoy"] = 0
                item["initial_yoy"] = 0
                item["repurchase_yoy"] = 0
                item["lian_dai_yoy"] = 0

            prev_row = {
                "total": item["total"],
                "shallow_grass": item["shallow_grass"],
                "deep_grass": item["deep_grass"],
                "initial": item["initial"],
                "repurchase": item["repurchase"],
                "lian_dai": item["lian_dai"],
            }
            product_days.append(item)

        products_result.append({
            "name": product_name,
            "spu_classes": product_to_spu.get(product_name, [product_name]),
            "weeks": product_days,
        })

    return {
        "products": products_result,
        "latest_week": latest_label,
    }
