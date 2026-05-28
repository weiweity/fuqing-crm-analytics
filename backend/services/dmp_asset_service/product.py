"""
芙清 CRM - 市场对焦板块：DMP资产数据服务
读取 data3.csv（单品资产），按周聚合后暴露API
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any

from ._helpers import (
    ID_TO_PRODUCT,
    PRODUCT_ORDER,
    PRODUCT_TO_SPU_CLASSES,
    _cache,
    _cache_lock,
    _load_data3,
    _get_week_label,
    _last_year_same_date,
    _compute_product_assets_daily,
)


def get_product_assets(weeks: int = 4, days: int = 0) -> Dict[str, Any]:
    """
    获取单品资产数据
    weeks: 按自然周聚合（days=0 时生效，默认）
    days:  按日返回（>0时优先级高于weeks）
    """
    with _cache_lock:
        if days > 0:
            df = _load_data3()
            return _compute_product_assets_daily(days, df, ID_TO_PRODUCT, PRODUCT_ORDER, PRODUCT_TO_SPU_CLASSES)

        cached = _cache["data3"].get("result")
        if cached is not None and cached.get("_weeks") == weeks:
            return cached
        df = _load_data3()
        result = _compute_product_assets(weeks, df)
        _cache["data3"]["result"] = result
        result["_weeks"] = weeks
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

    # 构建按 (product_name, 实际日期) 索引的字典（用于YOY查找：用实际日期而非理论周日）
    lookup_index = {}
    for _, r in df.iterrows():
        d = r["时间"]
        if pd.notna(d):
            lookup_index[(r["product_name"], d.date())] = r

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
                    "total_yoy": 0, "shallow_grass_yoy": 0,
                    "deep_grass_yoy": 0, "initial_yoy": 0,
                    "repurchase_yoy": 0, "lian_dai_yoy": 0,
                }
            else:
                # 显式取该周实际最新日期（data3通常是周日，但以防万一）
                d = week_df["时间"].max()
                row = week_df[week_df["时间"] == d].iloc[0]
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

                # 计算YOY同比：用该周实际最新日期 d 对比去年同期同月日
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
