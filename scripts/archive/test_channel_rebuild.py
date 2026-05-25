#!/usr/bin/env python3
"""
渠道重建一致性验证脚本

验证三种渠道标记逻辑的一致性：
1. 基准（Baseline）：DuckDB 中已有 channel（ETL 全量重建结果）
2. 旧Bug（Buggy）：模拟 update_taoke_channel() 错误版本
   - 保护列表不完整（缺货架/达播/微博/购物金）
   - 标记条件用 != '淘客' 而非 = '其他'
3. 新方案（Rebuild）：全部重置为'其他'，按 P1→P9 优先级逐层标记

失败标准：新方案与基准不一致
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

import duckdb
import pandas as pd
from backend.config import DUCKDB_PATH
from scripts.run_etl import (
    load_spu_mapping, load_channel_rules,
    load_taoke_order_ids, load_live_order_ids,
    load_taoke_product_rules, match_channel
)

# 渠道优先级（用于排序输出）
CHANNEL_ORDER = [
    'U先派样', '百补派样', '赠品&0.01渠道',
    '达播', '微博', '直播',
    '淘客', '购物金', '货架', '其他'
]


def load_sample_data():
    """从 DuckDB 读取最近 60 天的订单样本"""
    print("=" * 70)
    print("渠道重建一致性验证")
    print("=" * 70)
    print(f"\n数据库路径: {DUCKDB_PATH}")

    conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        # 先查看数据时间范围
        range_result = conn.execute("""
            SELECT MIN(pay_time) AS min_dt, MAX(pay_time) AS max_dt, COUNT(*) AS total
            FROM orders WHERE pay_time IS NOT NULL
        """).fetchone()
        print(f"\n数据库总数据: {range_result[2]:,} 行")
        print(f"时间范围: {range_result[0]} ~ {range_result[1]}")

        # 取最近 60 天的数据（约 1-2 个月）
        df = conn.execute("""
            SELECT
                order_id,
                product_title,
                spu_type,
                channel,
                pay_time,
                actual_amount,
                product_id
            FROM orders
            WHERE pay_time >= CURRENT_DATE - INTERVAL '60 days'
              AND pay_time IS NOT NULL
        """).fetchdf()

        print(f"\n样本数据: {len(df):,} 行 (最近 60 天)")

        # 检查当前渠道分布
        print("\nDuckDB 当前渠道分布（样本）:")
        vc = df['channel'].value_counts()
        for ch in CHANNEL_ORDER:
            if ch in vc.index:
                cnt = vc[ch]
                print(f"  {ch:<16} {cnt:>10,} ({cnt/len(df)*100:>5.1f}%)")
        # 补充不在 CHANNEL_ORDER 中的
        for ch, cnt in vc.items():
            if ch not in CHANNEL_ORDER:
                print(f"  {ch:<16} {cnt:>10,} ({cnt/len(df)*100:>5.1f}%)")

        return df
    finally:
        conn.close()


def simulate_old_bug(df, taoke_order_ids):
    """
    模拟 update_taoke_channel() 错误版本

    Bug 1: 保护列表不完整（缺货架/达播/微博/购物金）
    Bug 2: 标记条件用 != '淘客' 而非 = '其他'

    这导致：
    - 货架/达播/微博/购物金 被重置为 '其他'
    - 由于 != '淘客' 条件，这些订单又被错误标记为淘客
    """
    df = df.copy()

    # Bug 1: 保护列表不完整（与 MEMORY.md 2026-04-26 P0 一致）
    # 正确保护列表应包含: U先派样, 百补派样, 赠品&0.01渠道, 直播, 货架, 达播, 微博, 购物金
    protected = ['U先派样', '百补派样', '赠品&0.01渠道', '直播']
    # 缺少: '货架', '达播', '微博', '购物金'

    # Step 1: 重置非保护渠道为 '其他'
    reset_mask = ~df['channel'].isin(protected)
    reset_count = reset_mask.sum()
    df.loc[reset_mask, 'channel'] = '其他'

    # Step 2 & 3: 标记淘客
    # Bug 2: 使用 != '淘客' 而非 = '其他'
    # 这意味着所有非淘客订单（包括刚被重置的 '其他'，以及其他渠道如货架/达播/微博/购物金）
    # 都可能被错误标记为淘客

    # P6: 订单号匹配
    if taoke_order_ids:
        mask_tk = (
            df['order_id'].astype(str).isin(taoke_order_ids) &
            (df['channel'] != '淘客')  # Bug: 应该是 = '其他'
        )
        df.loc[mask_tk, 'channel'] = '淘客'

    # P6-2: 关键词匹配（注意：旧bug版本只有 T4/TK，缺少 T1/T2）
    product_title = df['product_title'].astype(str)
    mask_kw = (
        product_title.str.contains(r'T4|t4|tk|TK|Tk|tK', case=False, na=False) &
        (df['channel'] != '淘客')  # Bug: 应该是 = '其他'
    )
    df.loc[mask_kw, 'channel'] = '淘客'

    return df


def simulate_new_rebuild(df, keyword_rules, id_rules, taoke_order_ids, live_order_ids):
    """
    模拟新方案: rebuild_all_channels()

    全部重置为 '其他'，按 P1→P9 优先级逐层标记。
    这就是 match_channel() 的核心逻辑。
    """
    return match_channel(
        df.copy(),
        keyword_rules, id_rules,
        taoke_order_ids=taoke_order_ids,
        live_order_ids=live_order_ids
    )


def print_distribution(title, series):
    """打印渠道分布表"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

    vc = series.value_counts()
    total = len(series)

    # 按 CHANNEL_ORDER 排序
    ordered = []
    for ch in CHANNEL_ORDER:
        if ch in vc.index:
            ordered.append((ch, vc[ch]))
    # 补充不在 CHANNEL_ORDER 中的
    for ch, cnt in vc.items():
        if ch not in [x[0] for x in ordered]:
            ordered.append((ch, cnt))

    for ch, cnt in ordered:
        print(f"  {ch:<16} {cnt:>10,} ({cnt/total*100:>5.1f}%)")
    print(f"  {'合计':<16} {total:>10,}")


def print_comparison(base_vc, buggy_vc, new_vc):
    """打印三方案对比表"""
    print(f"\n{'='*70}")
    print("  渠道分布对比（三张表合一）")
    print(f"{'='*70}")

    all_ch = sorted(
        set(base_vc.index) | set(buggy_vc.index) | set(new_vc.index),
        key=lambda x: CHANNEL_ORDER.index(x) if x in CHANNEL_ORDER else 999
    )

    # 表头
    print(f"\n  {'渠道':<16} {'基准':>10} {'旧Bug':>10} {'新方案':>10} {'Bug-基准':>10} {'新-基准':>8}  {'标记'}")
    print("  " + "-" * 76)

    issues_bug = []
    issues_new = []

    for ch in all_ch:
        b = base_vc.get(ch, 0)
        g = buggy_vc.get(ch, 0)
        n = new_vc.get(ch, 0)
        db = g - b
        dn = n - b

        # 标记异常
        markers = []
        if ch in ['U先派样', '百补派样', '赠品&0.01渠道', '直播', '货架', '达播', '微博', '购物金']:
            if db < 0:
                markers.append("渠道被覆盖")
                issues_bug.append(f"{ch}: 基准 {b:,} -> 旧Bug {g:,} (减少 {abs(db):,})")
            if dn != 0:
                markers.append("新方案不一致")
                issues_new.append(f"{ch}: 基准 {b:,} -> 新方案 {n:,} (差异 {dn:+,})")

        if ch == '淘客':
            if db > 0:
                markers.append("淘客虚增")
                issues_bug.append(f"淘客: 基准 {b:,} -> 旧Bug {g:,} (虚增 {db:+,})")
            if dn != 0:
                markers.append("新方案不一致")
                issues_new.append(f"淘客: 基准 {b:,} -> 新方案 {n:,} (差异 {dn:+,})")

        marker_str = f"  [{' | '.join(markers)}]" if markers else ""

        print(f"  {ch:<16} {b:>10,} {g:>10,} {n:>10,} {db:>+10,} {dn:>+8,}{marker_str}")

    print("  " + "-" * 76)
    print(f"  {'合计':<16} {base_vc.sum():>10,} {buggy_vc.sum():>10,} {new_vc.sum():>10,}")

    return issues_bug, issues_new


def main():
    # 1. 加载样本数据
    df = load_sample_data()
    if df.empty:
        print("\n错误: 未读取到数据")
        return 1

    # 2. 加载辅助数据
    print("\n" + "-" * 60)
    print("加载辅助数据...")
    print("-" * 60)
    spu_df = load_spu_mapping()
    keyword_rules, id_rules = load_channel_rules()
    taoke_order_ids = load_taoke_order_ids()
    live_order_ids = load_live_order_ids()
    taoke_product_rules = load_taoke_product_rules()

    # 3. 基准: DuckDB 已有 channel（ETL 全量重建结果）
    df_baseline = df.copy()

    # 4. 旧Bug: 模拟 update_taoke_channel() 错误版本
    print("\n" + "-" * 60)
    print("模拟旧 Bug 逻辑...")
    print("-" * 60)
    df_buggy = simulate_old_bug(df.copy(), taoke_order_ids)

    # 5. 新方案: 全部重置 + P1→P9 逐层标记
    print("\n" + "-" * 60)
    print("模拟新方案逻辑（全部重置 + P1→P9 逐层标记）...")
    print("-" * 60)
    df_new = simulate_new_rebuild(
        df.copy(), keyword_rules, id_rules,
        taoke_order_ids, live_order_ids
    )

    # 6. 输出三张分布表
    print_distribution("基准 (DuckDB 已有 channel)", df_baseline['channel'])
    print_distribution("旧Bug (update_taoke_channel 错误版)", df_buggy['channel'])
    print_distribution("新方案 (match_channel 全量重建)", df_new['channel'])

    # 7. 输出对比表
    base_vc = df_baseline['channel'].value_counts()
    buggy_vc = df_buggy['channel'].value_counts()
    new_vc = df_new['channel'].value_counts()

    issues_bug, issues_new = print_comparison(base_vc, buggy_vc, new_vc)

    # 8. 差异摘要
    print(f"\n{'='*70}")
    print("  差异摘要")
    print(f"{'='*70}")

    # 旧Bug 问题
    print("\n  【旧Bug 发现的问题】")
    if issues_bug:
        for issue in issues_bug:
            print(f"    - {issue}")
    else:
        print("    无异常")

    # 新方案 一致性
    print("\n  【新方案一致性检查】")
    new_diff = (df_new['channel'] != df_baseline['channel']).sum()
    if new_diff == 0:
        print("    新方案与基准完全一致")
        print("    结果: PASS")
    else:
        print(f"    新方案与基准有 {new_diff:,} 行差异")
        print("    结果: FAIL")
        # 打印差异详情
        print("\n    差异详情（前 20 条）:")
        diff_mask = df_new['channel'] != df_baseline['channel']
        diff_sample = df_baseline.loc[diff_mask, ['order_id', 'product_title', 'channel']].copy()
        diff_sample['new_channel'] = df_new.loc[diff_mask, 'channel'].values
        for _, row in diff_sample.head(20).iterrows():
            title = str(row['product_title'])[:35] if pd.notna(row['product_title']) else ''
            print(f"      {row['order_id']}: {row['channel']} -> {row['new_channel']} ({title})")

    # 淘客混入详情（旧Bug）
    print(f"\n{'='*70}")
    print("  淘客混入详情（旧Bug 导致其他渠道被错误标记为淘客）")
    print(f"{'='*70}")
    found = False
    for ch in ['U先派样', '百补派样', '赠品&0.01渠道', '直播', '货架', '达播', '微博', '购物金']:
        cnt = ((df_baseline['channel'] == ch) & (df_buggy['channel'] == '淘客')).sum()
        if cnt > 0:
            print(f"    {ch:<16} -> 淘客: {cnt:,} 行")
            found = True
    if not found:
        print("    无混入")

    # 最终结论
    print(f"\n{'='*70}")
    print("  最终结论")
    print(f"{'='*70}")
    if new_diff == 0:
        print("  新方案（全量逐层重建）与基准一致，验证通过。")
        print("  建议：可以放心切换为 rebuild_all_channels() 全量重建模式。")
        return 0
    else:
        print(f"  新方案与基准有 {new_diff:,} 行差异，验证失败。")
        print("  建议：检查 match_channel() 逻辑或 DuckDB 数据是否需要重新 ETL。")
        return 1


if __name__ == '__main__':
    sys.exit(main())
