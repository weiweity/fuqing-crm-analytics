#!/usr/bin/env python3
"""
芙清人群数据库自动清洗归库脚本
================================
支持任意Excel宽表自动识别结构、清洗为标准长表、增量归库。

用法示例:
  # 首次清洗（全量）
  python scripts/clean_crowd_data.py \
    --input "raw/26年芙清人群数据库0513.xlsx" \
    --output "processed/芙清人群数据库_清洗后.csv" \
    --mode overwrite

  # 增量归库（只追加新月份）
  python scripts/clean_crowd_data.py \
    --input "raw/26年芙清人群数据库0615.xlsx" \
    --output "processed/芙清人群数据库_清洗后.csv" \
    --mode append \
    --since 2026-03

  # 输出清洗报告
  python scripts/clean_crowd_data.py \
    --input "raw/xx.xlsx" \
    --output "processed/xx.csv" \
    --report "reports/clean_report.json"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════════
# 常量与映射表
# ═══════════════════════════════════════════════════════════════════════════════

ATTR_GROUP_MAP = {
    "性别": "gender",
    "年龄": "age",
    "城市等级": "city_tier",
    "月均消费金额": "monthly_consumption",
    "策略人群": "strategy_group",
}

ATTR_SUBGROUP_MAP = {
    "总购买人数": "total_purchasers",
    "女性": "female",
    "男性": "male",
    "18-24": "18-24",
    "25-29": "25-29",
    "30-34": "30-34",
    "35-39": "35-39",
    "40-49": "40-49",
    "50以上": "50_plus",
    "一线": "tier1",
    "准一线": "tier1_sub",
    "二线": "tier2",
    "三线": "tier3",
    "四线": "tier4",
    "五线": "tier5",
    "低于400": "below_400",
    "400-1000": "400_to_1000",
    "1000-3000": "1000_to_3000",
    "3000-6000": "3000_to_6000",
    "6000以上": "above_6000",
    "新锐白领": "white_collar",
    "小镇青年": "small_town_youth",
    "Genz": "gen_z",
    "小镇中年": "small_town_middle_aged",
    "精致妈妈": "sophisticated_mom",
    "资深中产": "established_middle_class",
    "都市蓝领": "urban_blue_collar",
    "小镇老年": "small_town_elderly",
    "都市银发": "urban_silver_hair",
}

ATTR_SUBGROUP_CN = {
    "total_purchasers": "总购买人数",
    "female": "女性",
    "male": "男性",
    "18-24": "18-24岁",
    "25-29": "25-29岁",
    "30-34": "30-34岁",
    "35-39": "35-39岁",
    "40-49": "40-49岁",
    "50_plus": "50岁以上",
    "tier1": "一线城市",
    "tier1_sub": "准一线城市",
    "tier2": "二线城市",
    "tier3": "三线城市",
    "tier4": "四线城市",
    "tier5": "五线城市",
    "below_400": "低于400元",
    "400_to_1000": "400-1000元",
    "1000_to_3000": "1000-3000元",
    "3000_to_6000": "3000-6000元",
    "above_6000": "6000元以上",
    "white_collar": "新锐白领",
    "small_town_youth": "小镇青年",
    "gen_z": "Gen Z",
    "small_town_middle_aged": "小镇中年",
    "sophisticated_mom": "精致妈妈",
    "established_middle_class": "资深中产",
    "urban_blue_collar": "都市蓝领",
    "small_town_elderly": "小镇老年",
    "urban_silver_hair": "都市银发",
}


# ═══════════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════════

def excel_date_to_datetime(excel_date: Any) -> datetime | None:
    """Excel日期序列号 → datetime（1900日期系统）"""
    if pd.isna(excel_date):
        return None
    try:
        days = int(float(excel_date))
        return datetime(1899, 12, 30) + timedelta(days=days)
    except Exception:
        return None


def parse_time_period(val: Any) -> tuple[str | None, str | None]:
    """解析时间维度 → (period_str, period_type)"""
    if pd.isna(val):
        return None, None
    val_str = str(val).strip()

    # 汇总维度
    if "全年" in val_str:
        return f"20{val_str[:2]}", "year"
    elif "H2" in val_str:
        return f"20{val_str[:2]}-H2", "half_year"
    elif "H1" in val_str:
        return f"20{val_str[:2]}-H1", "half_year"
    elif "Q4" in val_str:
        return f"20{val_str[:2]}-Q4", "quarter"
    elif "Q3" in val_str:
        return f"20{val_str[:2]}-Q3", "quarter"
    elif "Q2" in val_str:
        return f"20{val_str[:2]}-Q2", "quarter"
    elif "Q1" in val_str:
        return f"20{val_str[:2]}-Q1", "quarter"

    # 月度维度 - Excel日期序列号
    try:
        dt = excel_date_to_datetime(float(val_str))
        if dt:
            return dt.strftime("%Y-%m"), "month"
    except Exception:
        pass

    return val_str, "unknown"


def parse_product_name(full_name: str) -> tuple[str, str]:
    """从产品全名提取 (产品名, 产品ID)"""
    match = re.match(r"^(.+?)(\d+)$", full_name)
    if match:
        return match.group(1), match.group(2)
    return full_name, ""


# ═══════════════════════════════════════════════════════════════════════════════
# 结构自动识别
# ═══════════════════════════════════════════════════════════════════════════════

def auto_detect_structure(df_raw: pd.DataFrame) -> dict[str, Any]:
    """
    自动识别Excel宽表结构：
      - 产品列边界（通过第0行非空值）
      - 属性行分组（通过第0列+第1列）
      - 校验基本结构一致性
    返回结构描述字典，异常时抛ValueError。
    """
    n_rows, n_cols = df_raw.shape
    if n_rows < 3 or n_cols < 3:
        raise ValueError(f"Excel尺寸异常：{n_rows}行×{n_cols}列，至少需要3行3列")

    # ── 识别产品列范围 ──
    row0 = df_raw.iloc[0]
    products_info: list[tuple[int, str]] = []
    for i, val in enumerate(row0):
        if pd.notna(val) and i >= 2:
            products_info.append((i, str(val).strip()))
    if len(products_info) == 0:
        raise ValueError("未识别到任何产品列（第0行第2列之后无非空值）")

    # 添加end边界
    products_info.append((n_cols, "end"))

    products = []
    for idx in range(len(products_info) - 1):
        start_col = products_info[idx][0]
        end_col = products_info[idx + 1][0]
        full_name = products_info[idx][1]
        name, pid = parse_product_name(full_name)
        products.append(
            {
                "start_col": start_col,
                "end_col": end_col,
                "product_name": name,
                "product_id": pid,
                "full_name": full_name,
                "n_cols": end_col - start_col,
            }
        )

    # ── 识别属性行分组 ──
    attr_groups: list[dict[str, Any]] = []
    current_group: dict[str, Any] | None = None

    for row_idx in range(2, n_rows):
        col0 = df_raw.iloc[row_idx, 0]
        col1 = df_raw.iloc[row_idx, 1]

        if pd.isna(col0) and pd.isna(col1):
            continue

        # 新属性大类
        if pd.notna(col0):
            group_cn = str(col0).strip()
            group_en = ATTR_GROUP_MAP.get(group_cn, group_cn)
            current_group = {
                "group_cn": group_cn,
                "group_en": group_en,
                "start_row": row_idx,
                "subgroups": [],
            }
            attr_groups.append(current_group)

        if current_group is None:
            continue

        # 属性细分
        if pd.notna(col1):
            sub_cn = str(col1).strip()
            sub_en = ATTR_SUBGROUP_MAP.get(sub_cn, sub_cn)
            current_group["subgroups"].append(
                {
                    "name_cn": sub_cn,
                    "name_en": sub_en,
                    "row": row_idx,
                }
            )

    # 过滤无细分属性的异常组（如Excel公式残留行）
    attr_groups = [g for g in attr_groups if len(g["subgroups"]) > 0]

    if len(attr_groups) == 0:
        raise ValueError("未识别到任何属性分组（第2行之后无有效属性数据）")

    # ── 校验 ──
    # 检查每个产品的时间行是否都有值
    for prod in products:
        time_row = df_raw.iloc[1, prod["start_col"] : prod["end_col"]]
        n_times = time_row.notna().sum()
        if n_times == 0:
            raise ValueError(
                f"产品 '{prod['product_name']}' (列{prod['start_col']}-{prod['end_col']-1}) "
                f"未识别到任何时间维度"
            )
        prod["n_times"] = n_times

    # 检查属性行是否有数据（至少抽查第一个产品）
    first_prod = products[0]
    sample_col = first_prod["start_col"]
    has_data = False
    for grp in attr_groups:
        for sub in grp["subgroups"]:
            if pd.notna(df_raw.iloc[sub["row"], sample_col]):
                has_data = True
                break
        if has_data:
            break
    if not has_data:
        raise ValueError(f"属性行在首个产品列(列{sample_col})中无数据，请检查Excel结构")

    return {
        "n_rows": n_rows,
        "n_cols": n_cols,
        "products": products,
        "attr_groups": attr_groups,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 核心清洗逻辑
# ═══════════════════════════════════════════════════════════════════════════════

def clean_data(df_raw: pd.DataFrame, since: str | None = None) -> pd.DataFrame:
    """
    将宽表Excel清洗为标准长表DataFrame。
    若指定since（如'2026-03'），则只保留该时间之后的数据。
    """
    structure = auto_detect_structure(df_raw)
    all_records: list[dict[str, Any]] = []

    for prod in structure["products"]:
        start_col = prod["start_col"]
        end_col = prod["end_col"]
        product_name = prod["product_name"]
        product_id = prod["product_id"]

        # 解析时间维度
        time_row = df_raw.iloc[1, start_col:end_col]
        time_periods: list[str | None] = []
        time_types: list[str | None] = []
        for val in time_row:
            period, ttype = parse_time_period(val)
            time_periods.append(period)
            time_types.append(ttype)

        # 遍历属性组
        for grp in structure["attr_groups"]:
            group_en = grp["group_en"]
            group_cn = grp["group_cn"]

            for sub in grp["subgroups"]:
                attr_subgroup = sub["name_en"]
                attr_subgroup_cn = ATTR_SUBGROUP_CN.get(attr_subgroup, sub["name_cn"])
                row_idx = sub["row"]
                metric_type = "total_count" if attr_subgroup == "total_purchasers" else "ratio"

                # 遍历时间列
                for col_offset, (period, ttype) in enumerate(zip(time_periods, time_types)):
                    if period is None:
                        continue

                    # since过滤
                    if since and ttype == "month" and period < since:
                        continue

                    col_idx = start_col + col_offset
                    value = df_raw.iloc[row_idx, col_idx]

                    if pd.isna(value):
                        continue

                    value_str = str(value).strip()
                    is_censored = False

                    # 处理 "未满200" 等特殊值
                    if "未满" in value_str:
                        numeric_value = np.nan
                        is_censored = True
                    else:
                        try:
                            numeric_value = float(value)
                        except ValueError:
                            continue

                    # 百分比
                    value_pct = np.nan
                    if metric_type == "ratio" and not pd.isna(numeric_value):
                        value_pct = round(numeric_value * 100, 2)

                    all_records.append(
                        {
                            "product_name": product_name,
                            "product_id": product_id,
                            "time_period": period,
                            "time_type": ttype or "",
                            "attr_group": group_en,
                            "attr_group_cn": group_cn,
                            "attr_subgroup": attr_subgroup,
                            "attr_subgroup_cn": attr_subgroup_cn,
                            "metric_type": metric_type,
                            "value": numeric_value,
                            "value_pct": value_pct,
                            "is_censored": is_censored,
                        }
                    )

    df_clean = pd.DataFrame(all_records)

    # ── 后处理：censored级联标记 ──
    censored_keys = df_clean[
        (df_clean["attr_subgroup"] == "total_purchasers") & (df_clean["is_censored"] == True)
    ][["product_name", "time_period"]].drop_duplicates()

    for _, row in censored_keys.iterrows():
        mask = (
            (df_clean["product_name"] == row["product_name"])
            & (df_clean["time_period"] == row["time_period"])
            & (df_clean["metric_type"] == "ratio")
        )
        df_clean.loc[mask, "is_censored"] = True

    return df_clean


# ═══════════════════════════════════════════════════════════════════════════════
# 数据质量校验
# ═══════════════════════════════════════════════════════════════════════════════

def validate_data(df: pd.DataFrame) -> dict[str, Any]:
    """执行数据质量校验，返回报告字典"""
    report: dict[str, Any] = {
        "total_rows": len(df),
        "products": df["product_name"].nunique(),
        "time_periods": df["time_period"].nunique(),
        "attr_groups": df["attr_group"].nunique(),
        "censored_rows": int(df["is_censored"].sum()),
        "checks": {},
    }

    # 1. ratio值范围
    ratio_df = df[(df["metric_type"] == "ratio") & (df["is_censored"] == False)]
    out_of_range = ratio_df[(ratio_df["value"] < 0) | (ratio_df["value"] > 1)]
    report["checks"]["ratio_range"] = {
        "status": "PASS" if len(out_of_range) == 0 else "FAIL",
        "out_of_range_count": len(out_of_range),
    }

    # 2. 属性组比例和（互斥维度应接近1）
    group_sums = (
        df[(df["metric_type"] == "ratio") & (df["is_censored"] == False)]
        .groupby(["product_name", "time_period", "attr_group"])["value"]
        .sum()
        .reset_index()
    )

    for attr in ["gender", "age", "city_tier", "monthly_consumption"]:
        sub = group_sums[group_sums["attr_group"] == attr]["value"]
        if len(sub) > 0:
            vmin, vmax = sub.min(), sub.max()
            report["checks"][f"{attr}_sum"] = {
                "status": "PASS" if 0.8 <= vmin and vmax <= 1.2 else "WARNING",
                "min": round(float(vmin), 3),
                "max": round(float(vmax), 3),
            }

    # 3. strategy_group允许>1
    sg = group_sums[group_sums["attr_group"] == "strategy_group"]["value"]
    if len(sg) > 0:
        report["checks"]["strategy_group_sum"] = {
            "status": "INFO",
            "min": round(float(sg.min()), 3),
            "max": round(float(sg.max()), 3),
            "note": "策略人群可重叠，比例和可大于1",
        }

    # 4. 总购买人数为正整数
    tc = df[df["metric_type"] == "total_count"]["value"]
    negative = tc[tc < 0]
    report["checks"]["total_count_positive"] = {
        "status": "PASS" if len(negative) == 0 else "FAIL",
        "negative_count": len(negative),
    }

    # 总体状态
    fail_count = sum(1 for c in report["checks"].values() if c.get("status") == "FAIL")
    report["overall_status"] = "PASS" if fail_count == 0 else "FAIL"

    return report


# ═══════════════════════════════════════════════════════════════════════════════
# 增量归库
# ═══════════════════════════════════════════════════════════════════════════════

def merge_with_existing(
    df_new: pd.DataFrame, existing_path: str, mode: str
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    将新清洗数据与已有CSV合并。
    mode='overwrite': 直接覆盖
    mode='append': 智能合并（去重，保留新数据）
    返回 (merged_df, merge_info)
    """
    merge_info = {
        "mode": mode,
        "existing_file": existing_path,
        "existing_rows": 0,
        "new_rows": len(df_new),
        "merged_rows": len(df_new),
        "duplicates_dropped": 0,
    }

    if mode == "overwrite":
        return df_new, merge_info

    if not Path(existing_path).exists():
        return df_new, merge_info

    df_existing = pd.read_csv(existing_path, keep_default_na=True)
    merge_info["existing_rows"] = len(df_existing)

    # 合并策略：以 (product_name, time_period, attr_subgroup) 为键
    # 新数据覆盖旧数据（同键保留新）
    key_cols = ["product_name", "time_period", "attr_subgroup"]

    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    before_dedup = len(df_combined)
    df_merged = df_combined.drop_duplicates(subset=key_cols, keep="last")
    after_dedup = len(df_merged)

    merge_info["duplicates_dropped"] = before_dedup - after_dedup
    merge_info["merged_rows"] = after_dedup

    return df_merged, merge_info


# ═══════════════════════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(
        description="芙清人群数据库自动清洗归库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s -i raw/26年数据.xlsx -o processed/out.csv --mode overwrite
  %(prog)s -i raw/27年数据.xlsx -o processed/out.csv --mode append --since 2026-03
        """,
    )
    parser.add_argument("--input", "-i", required=True, help="输入Excel文件路径")
    parser.add_argument("--output", "-o", required=True, help="输出CSV文件路径")
    parser.add_argument(
        "--mode",
        choices=["append", "overwrite"],
        default="append",
        help="归库模式：append=增量追加(默认), overwrite=全量覆盖",
    )
    parser.add_argument(
        "--since",
        help="增量起始时间，如'2026-03'，只处理该时间之后的月度数据",
    )
    parser.add_argument(
        "--report",
        help="清洗报告输出路径(JSON)，如'reports/clean_report.json'",
    )
    args = parser.parse_args()

    print("=" * 60)
    print(" 芙清人群数据库自动清洗归库")
    print("=" * 60)

    # ── 读取 ──
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] 输入文件不存在: {args.input}")
        return 1

    print(f"\n📂 读取: {args.input}")
    try:
        df_raw = pd.read_excel(args.input, sheet_name="Sheet1", header=None, dtype=object)
    except Exception as e:
        print(f"[ERROR] 读取Excel失败: {e}")
        return 1

    print(f"   原始尺寸: {df_raw.shape[0]} 行 × {df_raw.shape[1]} 列")

    # ── 结构识别 ──
    print("\n🔍 自动识别结构...")
    try:
        structure = auto_detect_structure(df_raw)
    except ValueError as e:
        print(f"[ERROR] 结构识别失败: {e}")
        return 1

    print(f"   识别到 {len(structure['products'])} 个产品:")
    for p in structure["products"]:
        print(f"     • {p['product_name']:<12} (ID:{p['product_id']})  列{p['start_col']}-{p['end_col']-1}  {p['n_times']}个时间周期")

    print(f"   识别到 {len(structure['attr_groups'])} 个属性大类:")
    for g in structure["attr_groups"]:
        print(f"     • {g['group_cn']} ({g['group_en']}): {len(g['subgroups'])} 个细分属性")

    # ── 清洗 ──
    print("\n🧹 执行清洗...")
    if args.since:
        print(f"   增量过滤: 只保留 {args.since} 及之后的数据")

    df_clean = clean_data(df_raw, since=args.since)
    print(f"   清洗后: {len(df_clean)} 条记录")

    # ── 校验 ──
    print("\n✅ 数据质量校验...")
    report = validate_data(df_clean)
    for check_name, result in report["checks"].items():
        icon = "✓" if result["status"] in ("PASS", "INFO") else "⚠" if result["status"] == "WARNING" else "✗"
        print(f"   {icon} {check_name}: {result['status']}")
        if "min" in result:
            print(f"      范围: [{result['min']}, {result['max']}]")

    if report["overall_status"] != "PASS":
        print("\n[WARNING] 数据质量校验发现异常，请检查上方明细")

    # ── 归库 ──
    print(f"\n💾 归库: {args.output} (mode={args.mode})")
    df_merged, merge_info = merge_with_existing(df_clean, args.output, args.mode)

    if merge_info["existing_rows"] > 0:
        print(f"   已有数据: {merge_info['existing_rows']:,} 条")
        print(f"   新增数据: {merge_info['new_rows']:,} 条")
        print(f"   去重合并: 删除 {merge_info['duplicates_dropped']:,} 条重复")
        print(f"   合并结果: {merge_info['merged_rows']:,} 条")
    else:
        print(f"   新建数据: {merge_info['merged_rows']:,} 条")

    # 确保输出目录存在
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df_merged.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"   ✅ 已保存: {args.output}")

    # ── 报告 ──
    full_report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "input_file": str(args.input),
        "output_file": str(args.output),
        "mode": args.mode,
        "since": args.since,
        "structure": {
            "raw_shape": list(df_raw.shape),
            "products": [p["product_name"] for p in structure["products"]],
            "attr_groups": [g["group_cn"] for g in structure["attr_groups"]],
        },
        "cleaning": {
            "new_rows": len(df_clean),
            "censored_rows": int(df_clean["is_censored"].sum()),
        },
        "merge": merge_info,
        "validation": report,
    }

    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(full_report, f, ensure_ascii=False, indent=2)
        print(f"\n📝 清洗报告已保存: {args.report}")

    print("\n" + "=" * 60)
    print(" 清洗归库完成")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
