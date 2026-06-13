"""
Sample CRM - 市场对焦板块：DMP资产数据服务
读取 data2.csv（全店资产），按周聚合后暴露API
"""

import pandas as pd
from datetime import timedelta
from typing import Dict, Any

from ._helpers import (
    _cache_lock,
    _load_data2,
    _validate_daily_unique,
    _get_week_label,
    _get_week_range,
    _last_year_same_date,
)


def get_store_assets(weeks: int = 4, days: int = 0) -> Dict[str, Any]:
    """
    获取全店资产数据
    weeks: 按自然周聚合（默认）
    days:  按日返回（>0时优先级高于weeks）
    """
    with _cache_lock:
        df = _load_data2()

    if df is None or df.empty:
        return {"weeks": [], "latest_week": ""}

    df = df.sort_values("time")

    # 构建日索引（用于YOY查找去年同期：364天前=52周，保证同一星期几）
    daily_index = {}
    for _, r in df.iterrows():
        t = r["time"]
        if pd.notna(t):
            daily_index[t.date()] = r

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

            # 计算YOY同比（去年同期同日期的绝对值差）
            ly_date = _last_year_same_date(d)
            ly_row = daily_index.get(ly_date)
            if ly_row is not None:
                item["total_yoy"] = item["total"] - int(ly_row.get("TOTAL资产总量", 0))
                item["discover_yoy"] = item["discover"] - int(ly_row.get("Discover发现", 0))
                item["engage_yoy"] = item["engage"] - int(ly_row.get("Engage种草", 0))
                item["enthuse_yoy"] = item["enthuse"] - int(ly_row.get("Enthuse互动", 0))
                item["perform_yoy"] = item["perform"] - int(ly_row.get("Perform行动", 0))
                item["initial_yoy"] = item["initial"] - int(ly_row.get("Initial首购", 0))
                item["numerous_yoy"] = item["numerous"] - int(ly_row.get("Numerous复购", 0))
                item["keen_yoy"] = item["keen"] - int(ly_row.get("Keen至爱", 0))
            else:
                item["total_yoy"] = 0
                item["discover_yoy"] = 0
                item["engage_yoy"] = 0
                item["enthuse_yoy"] = 0
                item["perform_yoy"] = 0
                item["initial_yoy"] = 0
                item["numerous_yoy"] = 0
                item["keen_yoy"] = 0

            prev_item = item.copy()
            result.append(item)

        return {
            "weeks": result,
            "latest_week": result[-1]["week_label"] if result else "",
        }

    # 按自然周分组，显式取每组最新有数据的日期（避免依赖 .last() 的隐式行为）
    df["week_end"] = df["time"].apply(
        lambda d: (d - timedelta(days=d.weekday()) + timedelta(days=6)).date()
    )

    # 校验：每天应该只有一条记录
    _validate_daily_unique(df)

    # 获取最近N周（按理论周结束日取，但后续用实际最新日期）
    all_week_ends = sorted(df["week_end"].unique(), reverse=True)[:weeks]
    all_week_ends = sorted(all_week_ends)  # 升序

    result = []
    prev_row = None
    for week_end in all_week_ends:
        week_df = df[df["week_end"] == week_end]
        if week_df.empty:
            continue
        # 显式取该周实际最新有数据的日期（如本周只到周三，就用周三）
        d = week_df["time"].max()
        row = week_df[week_df["time"] == d].iloc[0]

        week_label = _get_week_label(d)
        week_end_str = _get_week_range(d)[1].strftime("%Y-%m-%d")

        item = {
            "week_label": week_label,
            "week_end_date": week_end_str,
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

        # 计算YOY同比：用该周实际最新日期 d 对比去年同期同月日
        ly_date = _last_year_same_date(d)
        ly_row = daily_index.get(ly_date)
        if ly_row is not None:
            item["total_yoy"] = item["total"] - int(ly_row.get("TOTAL资产总量", 0))
            item["discover_yoy"] = item["discover"] - int(ly_row.get("Discover发现", 0))
            item["engage_yoy"] = item["engage"] - int(ly_row.get("Engage种草", 0))
            item["enthuse_yoy"] = item["enthuse"] - int(ly_row.get("Enthuse互动", 0))
            item["perform_yoy"] = item["perform"] - int(ly_row.get("Perform行动", 0))
            item["initial_yoy"] = item["initial"] - int(ly_row.get("Initial首购", 0))
            item["numerous_yoy"] = item["numerous"] - int(ly_row.get("Numerous复购", 0))
            item["keen_yoy"] = item["keen"] - int(ly_row.get("Keen至爱", 0))
        else:
            item["total_yoy"] = 0
            item["discover_yoy"] = 0
            item["enthuse_yoy"] = 0
            item["perform_yoy"] = 0
            item["initial_yoy"] = 0
            item["numerous_yoy"] = 0
            item["keen_yoy"] = 0

        prev_row = item.copy()
        result.append(item)

    return {
        "weeks": result,
        "latest_week": result[-1]["week_label"] if result else "",
    }
