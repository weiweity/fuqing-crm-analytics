"""
芙清 CRM - 市场对焦板块：DMP资产数据服务
读取 data2.csv（全店资产）和 data3.csv（单品资产），按周聚合后暴露API
"""

import os
import threading
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

from backend.config import DMP_DATA2_PATH, DMP_DATA3_PATH


# ─────────────────────────────────────────────────────────────
# 文件路径由 backend/config.py 统一管理
# ─────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────
# data3.csv ID → 产品名称映射
# ─────────────────────────────────────────────────────────────
ID_TO_PRODUCT = {
    587051744204: "经典膜",
    803474428381: "凉茶次抛",
    870597889980: "凉茶水乳",
    994162104051: "凉茶面霜",
    933524395698: "童颜乳酸次抛",   # 实际为"童颜乳酸精华"
    900975734816: "童颜乳酸面膜",
    1010458880710: "传明酸面膜",    # 实际为"传明酸光感面膜"
}

# 产品展示顺序（单一数据源，前端 CORE_PRODUCTS 应与此保持一致）
PRODUCT_ORDER = list(ID_TO_PRODUCT.values())

# ─────────────────────────────────────────────────────────────
# 产品名 → SPU类目名列表映射（单一数据源，与前端 CORE_PRODUCTS.spuc_classes 一致）
# 用途：product-assets API 返回 spu_classes，前端去掉硬编码
# 维护规则：修改 ID_TO_PRODUCT 时同步更新此映射
# ─────────────────────────────────────────────────────────────
PRODUCT_TO_SPU_CLASSES: Dict[str, List[str]] = {
    "经典膜": ["经典膜", "【妆】经典膜"],
    "凉茶次抛": ["凉茶次抛"],          # TODO: 确认 data3 中对应的 SPU 类目名
    "凉茶水乳": ["凉茶水乳"],
    "凉茶面霜": ["凉茶面霜"],
    "童颜乳酸次抛": ["童颜乳酸精华"],   # 后端展示名"童颜乳酸次抛"，SPU类目为"童颜乳酸精华"
    "童颜乳酸面膜": ["童颜乳酸面膜"],
    "传明酸面膜": ["传明酸光感面膜"],   # 后端展示名"传明酸面膜"，SPU类目为"传明酸光感面膜"
}

# ════════════════════════════════════════════════════════════
# 模块三：单品资产 - 其他产品
# ════════════════════════════════════════════════════════════

# data3.csv 中剩余未在核心单品资产展示的 8 个产品 ID → 名称映射
# 名称来源：天猫_spu单品匹配表_数据表.csv 的「单品归类」列
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

# 合并映射，供 _load_data3 统一加载所有产品数据
_ALL_ID_TO_PRODUCT = {**ID_TO_PRODUCT, **ID_TO_PRODUCT_OTHER}

# ─────────────────────────────────────────────────────────────
# 缓存（线程安全，结果级缓存避免重复计算）
# ─────────────────────────────────────────────────────────────
_cache = {
    "data2": {"mtime": 0, "df": None},  # 全店资产（result级缓存由get_store_assets自行管理）
    "data3": {"mtime": 0, "df": None, "result": None, "result_other": None},
}
_cache_lock = threading.Lock()


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


# ════════════════════════════════════════════════════════════
# 模块二：全店资产
# ════════════════════════════════════════════════════════════

def _load_data2() -> pd.DataFrame:
    """加载并解析 data2.csv（线程安全，CSV读取在锁内避免竞态）"""
    with _cache_lock:
        if not _check_reload("data2", DMP_DATA2_PATH):
            return _cache["data2"]["df"]
        # 在锁内完成读取，避免多线程重复读取
        df = pd.read_csv(DMP_DATA2_PATH, encoding="utf-8")
        df["time"] = df["time"].apply(_parse_date)
        df = df.dropna(subset=["time"])
        # 解析数字列
        for col in ["TOTAL资产总量", "Discover发现", "Engage种草", "Enthuse互动",
                    "Perform行动", "Initial首购", "Numerous复购", "Keen至爱"]:
            if col in df.columns:
                df[col] = df[col].apply(_parse_number)
        _cache["data2"]["df"] = df
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


def get_store_assets(weeks: int = 4, days: int = 0) -> Dict[str, Any]:
    """
    获取全店资产数据
    weeks: 按自然周聚合（默认）
    days:  按日返回（>0时优先级高于weeks）
    """
    df = _load_data2()
    if df is None or df.empty:
        return {"weeks": [], "latest_week": ""}

    df = df.sort_values("time")

    # 按日返回模式
    if days > 0:
        df["date"] = df["time"].dt.date
        daily = df.groupby("date").last().reset_index()
        daily = daily.sort_values("date").tail(days)

        result = []
        prev_item = None
        for _, row in daily.iterrows():
            d = row["time"]
            date_label = d.strftime("%m/%d")
            date_str = d.strftime("%Y-%m-%d")

            item = {
                "week_label": date_label,
                "week_end_date": date_str,
                "total": int(row.get("TOTAL资产总量", 0)),
                "discover": int(row.get("Discover发现", 0)),
                "engage": int(row.get("Engage种草", 0)),
                "enthuse": int(row.get("Enthuse互动", 0)),
                "perform": int(row.get("Perform行动", 0)),
                "initial": int(row.get("Initial首购", 0)),
                "numerous": int(row.get("Numerous复购", 0)),
                "keen": int(row.get("Keen至爱", 0)),
            }
            # 计算日环比绝对值变化
            if prev_item is not None:
                item["total_change"] = item["total"] - prev_item["total"]
                item["discover_change"] = item["discover"] - prev_item["discover"]
                item["engage_change"] = item["engage"] - prev_item["engage"]
                item["enthuse_change"] = item["enthuse"] - prev_item["enthuse"]
                item["perform_change"] = item["perform"] - prev_item["perform"]
                item["initial_change"] = item["initial"] - prev_item["initial"]
                item["numerous_change"] = item["numerous"] - prev_item["numerous"]
                item["keen_change"] = item["keen"] - prev_item["keen"]
            else:
                item["total_change"] = 0
                item["discover_change"] = 0
                item["engage_change"] = 0
                item["enthuse_change"] = 0
                item["perform_change"] = 0
                item["initial_change"] = 0
                item["numerous_change"] = 0
                item["keen_change"] = 0

            prev_item = item.copy()
            result.append(item)

        return {
            "weeks": result,
            "latest_week": result[-1]["week_label"] if result else "",
        }

    # 按自然周分组，取每周最后一天
    df["week_end"] = df["time"].apply(
        lambda d: (d - timedelta(days=d.weekday()) + timedelta(days=6)).date()
    )

    # 校验：每天应该只有一条记录，否则 .last() 可能遗漏
    _validate_daily_unique(df)
    weekly = df.groupby("week_end").last().reset_index()
    weekly = weekly.sort_values("week_end", ascending=False)

    # 取最近N周
    weekly = weekly.head(weeks).sort_values("week_end", ascending=True)

    result = []
    prev_row = None
    for _, row in weekly.iterrows():
        d = row["time"]
        week_label = _get_week_label(d)
        week_end = _get_week_range(d)[1].strftime("%Y-%m-%d")

        item = {
            "week_label": week_label,
            "week_end_date": week_end,
            "total": int(row.get("TOTAL资产总量", 0)),
            "discover": int(row.get("Discover发现", 0)),
            "engage": int(row.get("Engage种草", 0)),
            "enthuse": int(row.get("Enthuse互动", 0)),
            "perform": int(row.get("Perform行动", 0)),
            "initial": int(row.get("Initial首购", 0)),
            "numerous": int(row.get("Numerous复购", 0)),
            "keen": int(row.get("Keen至爱", 0)),
        }

        # 计算本周对比上周绝对值变化
        if prev_row is not None:
            item["total_change"] = item["total"] - prev_row["total"]
            item["discover_change"] = item["discover"] - prev_row["discover"]
            item["engage_change"] = item["engage"] - prev_row["engage"]
            item["enthuse_change"] = item["enthuse"] - prev_row["enthuse"]
            item["perform_change"] = item["perform"] - prev_row["perform"]
            item["initial_change"] = item["initial"] - prev_row["initial"]
            item["numerous_change"] = item["numerous"] - prev_row["numerous"]
            item["keen_change"] = item["keen"] - prev_row["keen"]
        else:
            item["total_change"] = 0
            item["discover_change"] = 0
            item["engage_change"] = 0
            item["enthuse_change"] = 0
            item["perform_change"] = 0
            item["initial_change"] = 0
            item["numerous_change"] = 0
            item["keen_change"] = 0

        prev_row = item.copy()
        result.append(item)

    return {
        "weeks": result,
        "latest_week": result[-1]["week_label"] if result else "",
    }


# ════════════════════════════════════════════════════════════
# 模块三：单品资产
# ════════════════════════════════════════════════════════════

def _load_data3() -> pd.DataFrame:
    """
    加载并解析 data3.csv（线程安全，CSV读取在锁内避免竞态）。
    注意：此函数本身不获取锁，调用方必须在持有 _cache_lock 时调用。
    get_product_assets / get_other_product_assets 已正确持有锁后调用。
    """
    if not _check_reload("data3", DMP_DATA3_PATH):
        return _cache["data3"]["df"]
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
    # 加载全部已知产品（核心 + 其他），统一映射 product_name
    df = df[df["ID"].isin(_ALL_ID_TO_PRODUCT.keys())]
    df["product_name"] = df["ID"].map(_ALL_ID_TO_PRODUCT)
    _cache["data3"]["df"] = df
    return df


def get_product_assets(weeks: int = 4) -> Dict[str, Any]:
    """
    获取单品资产周数据（含 spu_classes 供前端去硬编码）
    结果级缓存：文件未变化时直接返回缓存结果，避免重复 groupby 计算
    """
    with _cache_lock:
        cached = _cache["data3"].get("result")
        if cached is not None and cached.get("_weeks") == weeks:
            return cached
        # 持有锁后调用 _load_data3（不再重复加锁）
        df = _load_data3()
        result = _compute_product_assets(weeks, df)
        _cache["data3"]["result"] = result
        result["_weeks"] = weeks  # 标记缓存粒度
        return result


def _compute_product_assets(weeks: int, df: pd.DataFrame) -> Dict[str, Any]:
    """真正执行单品资产计算（df 由调用方在持有锁时传入）"""
    if df is None or df.empty:
        return {"products": [], "latest_week": ""}

    # 只保留核心单品资产对应的产品ID
    df = df[df["ID"].isin(ID_TO_PRODUCT.keys())]
    if df.empty:
        return {"products": [], "latest_week": ""}

    # 按自然周分组（data3的日期已经是每周日，即自然周最后一天）
    df["week_end"] = df["时间"].apply(
        lambda d: (d - timedelta(days=d.weekday()) + timedelta(days=6)).date()
    )

    # 获取唯一的产品和周的笛卡尔积
    all_week_ends = sorted(df["week_end"].unique(), reverse=True)[:weeks]
    all_week_ends = sorted(all_week_ends)  # 升序

    products_result = []
    latest_week_label = ""

    # 按产品名称分组
    for product_name in PRODUCT_ORDER:
        product_df = df[df["product_name"] == product_name]
        if product_df.empty:
            continue

        product_weeks = []
        prev_row = None
        for week_end in all_week_ends:
            week_df = product_df[product_df["week_end"] == week_end]
            if week_df.empty:
                # 填充空值
                item = {
                    "week_label": _get_week_label(datetime.combine(week_end, datetime.min.time())),
                    "week_end_date": week_end.strftime("%Y-%m-%d"),
                    "total": 0, "shallow_grass": 0, "deep_grass": 0,
                    "initial": 0, "repurchase": 0, "lian_dai": 0,
                    "total_change": 0, "shallow_grass_change": 0,
                    "deep_grass_change": 0, "initial_change": 0,
                    "repurchase_change": 0, "lian_dai_change": 0,
                }
            else:
                row = week_df.iloc[0]
                d = row["时间"]
                week_label = _get_week_label(d)
                latest_week_label = week_label

                item = {
                    "week_label": week_label,
                    "week_end_date": week_end.strftime("%Y-%m-%d"),
                    "total": int(row.get("资产总量", 0)),
                    "shallow_grass": int(row.get("浅种草", 0)),
                    "deep_grass": int(row.get("深种草", 0)),
                    "initial": int(row.get("首购资产", 0)),
                    "repurchase": int(row.get("复购资产", 0)),
                    "lian_dai": int(row.get("连带资产", 0)),
                }

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

                prev_row = {
                    "total": item["total"],
                    "shallow_grass": item["shallow_grass"],
                    "deep_grass": item["deep_grass"],
                    "initial": item["initial"],
                    "repurchase": item["repurchase"],
                    "lian_dai": item["lian_dai"],
                }

            product_weeks.append(item)

        products_result.append({
            "name": product_name,
            "spu_classes": PRODUCT_TO_SPU_CLASSES.get(product_name, [product_name]),
            "weeks": product_weeks,
        })

    return {
        "products": products_result,
        "latest_week": latest_week_label,
    }


def get_other_product_assets(weeks: int = 4) -> Dict[str, Any]:
    """
    获取单品资产-其他产品周数据（展现形式同核心单品资产）
    结果级缓存：文件未变化时直接返回缓存结果，避免重复 groupby 计算
    """
    with _cache_lock:
        cached = _cache["data3"].get("result_other")
        if cached is not None and cached.get("_weeks") == weeks:
            return cached
        # 持有锁后调用 _load_data3（不再重复加锁）
        df = _load_data3()
        result = _compute_other_product_assets(weeks, df)
        _cache["data3"]["result_other"] = result
        result["_weeks"] = weeks  # 标记缓存粒度
        return result


def _compute_other_product_assets(weeks: int, df: pd.DataFrame) -> Dict[str, Any]:
    """真正执行单品资产-其他产品计算（df 由调用方在持有锁时传入）"""
    if df is None or df.empty:
        return {"products": [], "latest_week": ""}

    # 只保留其他产品对应的产品ID
    df = df[df["ID"].isin(ID_TO_PRODUCT_OTHER.keys())]
    if df.empty:
        return {"products": [], "latest_week": ""}

    # 按自然周分组（data3的日期已经是每周日，即自然周最后一天）
    df["week_end"] = df["时间"].apply(
        lambda d: (d - timedelta(days=d.weekday()) + timedelta(days=6)).date()
    )

    # 获取唯一的产品和周的笛卡尔积
    all_week_ends = sorted(df["week_end"].unique(), reverse=True)[:weeks]
    all_week_ends = sorted(all_week_ends)  # 升序

    products_result = []
    latest_week_label = ""

    # 按产品名称分组
    for product_name in PRODUCT_ORDER_OTHER:
        product_df = df[df["product_name"] == product_name]
        if product_df.empty:
            continue

        product_weeks = []
        prev_row = None
        for week_end in all_week_ends:
            week_df = product_df[product_df["week_end"] == week_end]
            if week_df.empty:
                # 填充空值
                item = {
                    "week_label": _get_week_label(datetime.combine(week_end, datetime.min.time())),
                    "week_end_date": week_end.strftime("%Y-%m-%d"),
                    "total": 0, "shallow_grass": 0, "deep_grass": 0,
                    "initial": 0, "repurchase": 0, "lian_dai": 0,
                    "total_change": 0, "shallow_grass_change": 0,
                    "deep_grass_change": 0, "initial_change": 0,
                    "repurchase_change": 0, "lian_dai_change": 0,
                }
            else:
                row = week_df.iloc[0]
                d = row["时间"]
                week_label = _get_week_label(d)
                latest_week_label = week_label

                item = {
                    "week_label": week_label,
                    "week_end_date": week_end.strftime("%Y-%m-%d"),
                    "total": int(row.get("资产总量", 0)),
                    "shallow_grass": int(row.get("浅种草", 0)),
                    "deep_grass": int(row.get("深种草", 0)),
                    "initial": int(row.get("首购资产", 0)),
                    "repurchase": int(row.get("复购资产", 0)),
                    "lian_dai": int(row.get("连带资产", 0)),
                }

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

                prev_row = {
                    "total": item["total"],
                    "shallow_grass": item["shallow_grass"],
                    "deep_grass": item["deep_grass"],
                    "initial": item["initial"],
                    "repurchase": item["repurchase"],
                    "lian_dai": item["lian_dai"],
                }

            product_weeks.append(item)

        products_result.append({
            "name": product_name,
            "spu_classes": PRODUCT_TO_SPU_CLASSES_OTHER.get(product_name, [product_name]),
            "weeks": product_weeks,
        })

    return {
        "products": products_result,
        "latest_week": latest_week_label,
    }
