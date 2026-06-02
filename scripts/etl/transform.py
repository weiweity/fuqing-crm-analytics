"""ETL 数据转换
渠道匹配、数据清洗、品类映射。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


import pandas as pd

# QW4 埋点：transform 步骤内部计时（独立路径下 perf.py 可能不在 sys.path）
try:
    from scripts.etl._timer import PerfTimer  # noqa: F401
except ImportError:
    class PerfTimer:  # type: ignore[no-redef]
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

def match_channel(df, keyword_rules, id_rules, taoke_order_ids=None, live_order_ids=None, taoke_product_rules=None):
    """
    8层漏斗渠道判定（从高优先级到低优先级，高优先级永不被低优先级覆盖）。

    P1: U先派样      — spu_type 含 "小样-U先"（不区分大小写）OR product_title 含 "U先"（不区分大小写）OR product_title 含 "会员尝鲜"
    P2: 百补派样     — spu_type 含 "小样-百亿补贴" OR product_title 含 "by"（不区分大小写）
    P3: 赠品&0.01渠道 — spu_type 含 "小样"（排除P1/P2）OR product_title 含 "赠品"
    P4: 达播/微博    — keyword_rules / id_rules（仅对 channel='其他' 生效，含P4保护）
    P5: 直播         — order_id 匹配直播CSV的父订单号
    P6: 淘客(订单号) — order_id 在淘客数据库中
    P6-2: 淘客(关键词) — product_title 含 T1/T2/T4/TK（大小写不敏感，芙清淘客商品标识后缀）
    P7: 购物金       — product_title 含 "购物金"
    P8: 货架         — P1-P7未命中 且 spu_type 含 "正装"
    P9: 其他         — P1-P8未命中
    """
    # QW4 埋点：match_channel 整体入口
    _match_channel_timer = PerfTimer(
        "transform_match_channel",
        rows=len(df),
        kw_rules=len(keyword_rules or []),
        id_rules=len(id_rules or []),
    )
    _match_channel_timer.__enter__()
    try:
        return _match_channel_body(df, keyword_rules, id_rules,
                                   taoke_order_ids, live_order_ids, taoke_product_rules,
                                   _match_channel_timer)
    finally:
        _match_channel_timer.__exit__(None, None, None)


def _match_channel_body(df, keyword_rules, id_rules, taoke_order_ids, live_order_ids, taoke_product_rules, _timer):
    """match_channel 的实际实现（被外层 QW4 埋点包裹）"""
    # 默认值
    df['channel'] = '其他'

    spu_type = df['spu_type'].astype(str)
    product_title = df['product_title'].astype(str)

    # P1: U先派样
    # 修复：spu_type 实际值是"小样-U先"（大写U），需不区分大小写
    # 修复：product_title 包含"【U先】"和"【天猫U先】"，需匹配所有"U先"变体
    # 新增：product_title 含"会员尝鲜"也归入U先派样
    mask_u = (
        spu_type.str.contains('小样-u先', case=False, na=False) |
        product_title.str.contains('u先', case=False, na=False) |
        product_title.str.contains('会员尝鲜', case=False, na=False)
    )
    df.loc[mask_u, 'channel'] = 'U先派样'
    print(f"  P1 U先派样: {mask_u.sum():,}")

    # P2: 百补派样
    mask_b = spu_type.str.contains('小样-百亿补贴', na=False) | product_title.str.contains('by', case=False, na=False)
    df.loc[mask_b, 'channel'] = '百补派样'
    print(f"  P2 百补派样: {mask_b.sum():,}")

    # P3: 赠品&0.01渠道
    # 修复：移除 actual_amount < 4 的独立条件，避免覆盖P1/P2的分类结果
    mask_z = (
        (spu_type.str.contains('小样', na=False) & ~mask_u & ~mask_b) |
        product_title.str.contains('赠品', na=False)
    )
    df.loc[mask_z, 'channel'] = '赠品&0.01渠道'
    print(f"  P3 赠品&0.01渠道: {mask_z.sum():,}")

    # P4: 达播/微博（仅对未匹配订单生效，保护P1-P3）
    p4_count = 0
    if keyword_rules or id_rules:
        # 1. 商品ID精确匹配（仅对未匹配订单生效）
        if id_rules:
            id_map = {str(int(pid)): ch for pid, ch in id_rules
                      if pd.notna(pid) and pd.notna(ch)}
            if id_map:
                matched_ids = df['product_id'].astype(str).map(id_map)
                mask_unmatched = df['channel'] == '其他'
                df.loc[mask_unmatched & matched_ids.notna(), 'channel'] = matched_ids.dropna().values
                p4_count += (mask_unmatched & matched_ids.notna()).sum()

        # 2. 关键词模糊匹配（仅对未匹配订单生效，长词优先）
        if keyword_rules:
            kw_list = [(str(k).strip(), str(ch).strip())
                      for k, ch in keyword_rules if pd.notna(k) and pd.notna(ch)]
            if kw_list:
                kw_list.sort(key=lambda x: -len(x[0]))  # 长词优先
                titles = df['product_title'].astype(str)
                mask_unmatched = df['channel'] == '其他'
                # QW4 埋点：关键词循环（plan hot spot #4）
                with PerfTimer("transform_p4_keyword_loop", kw_count=len(kw_list)):
                    for kw, ch in kw_list:
                        mask_kw = titles.str.contains(kw, case=False, na=False)
                        df.loc[mask_unmatched & mask_kw, 'channel'] = ch
                        p4_count += (mask_unmatched & mask_kw).sum()

        print(f"  P4 达播/微博: {p4_count:,}")

    # P5: 直播（仅对未匹配订单生效，order_id 在直播CSV父订单号集合中）
    if live_order_ids:
        mask_unmatched = df['channel'] == '其他'
        mask_live = mask_unmatched & df['order_id'].astype(str).isin(live_order_ids)
        df.loc[mask_live, 'channel'] = '直播'
        print(f"  P5 直播: {mask_live.sum():,}")

    # P6: 淘客（仅对未匹配订单生效）
    if taoke_order_ids:
        mask_unmatched = df['channel'] == '其他'
        mask_tk = mask_unmatched & df['order_id'].astype(str).isin(taoke_order_ids)
        df.loc[mask_tk, 'channel'] = '淘客'
        print(f"  P6 淘客: {mask_tk.sum():,}")

    # P6-2: 淘客补充（商品标题关键词匹配）
    # 芙清淘客商品标识后缀：T1/T2/T4/TK（大小写不敏感）
    # 例：...30支T1 / ...30支T2 / ...修复贴T4 / ...消械字TK
    mask_unmatched = df['channel'] == '其他'
    mask_tk_kw = product_title.str.contains(r'T[124K]', case=False, na=False)
    df.loc[mask_unmatched & mask_tk_kw, 'channel'] = '淘客'
    print(f"  P6-2 淘客关键词: {(mask_unmatched & mask_tk_kw).sum():,}")

    # P7: 购物金（product_title 含 "购物金"，仅对未匹配订单生效）
    mask_unmatched = df['channel'] == '其他'
    mask_card = product_title.str.contains('购物金', na=False)
    df.loc[mask_unmatched & mask_card, 'channel'] = '购物金'
    print(f"  P7 购物金: {(mask_unmatched & mask_card).sum():,}")

    # P8: 货架（P1-P7未命中 且 spu_type 含"正装"）
    mask_unmatched = df['channel'] == '其他'
    mask_zheng = spu_type.str.contains('正装', na=False)
    df.loc[mask_unmatched & mask_zheng, 'channel'] = '货架'
    print(f"  P8 货架: {(mask_unmatched & mask_zheng).sum():,}")

    # P9: 其他（P1-P8未命中）
    print(f"  P9 其他: {(df['channel'] == '其他').sum():,}")

    # 验证：检查高优先级渠道订单是否被错误覆盖为淘客
    if taoke_order_ids:
        wrong_taoke = (
            (df['channel'] == '淘客') &
            (
                spu_type.str.contains('小样', na=False) |
                product_title.str.contains('u先|赠品|购物金', case=False, na=False) |
                (df['actual_amount'] < 4)
            )
        )
        wrong_count = wrong_taoke.sum()
        if wrong_count > 0:
            print(f"  ⚠️ 警告: {wrong_count:,} 条订单疑似被错误标记为淘客（含小样/U先/赠品/<¥4）")

    channel_stats = df['channel'].value_counts()
    print(f"  渠道分布: {channel_stats.to_dict()}")
    return df


def clean_data(df, spu_df, keyword_rules, id_rules, taoke_order_ids=None, live_order_ids=None, taoke_product_rules=None, force_continue=False):
    """清洗数据"""
    # QW4 埋点：clean_data 整体入口
    _cd_timer = PerfTimer("transform_clean_data", rows=len(df))
    _cd_timer.__enter__()
    try:
        return _clean_data_body(df, spu_df, keyword_rules, id_rules,
                                taoke_order_ids, live_order_ids, taoke_product_rules,
                                force_continue)
    finally:
        _cd_timer.__exit__(None, None, None)


def _clean_data_body(df, spu_df, keyword_rules, id_rules, taoke_order_ids, live_order_ids, taoke_product_rules, force_continue):
    """clean_data 实际实现（被外层 QW4 埋点包裹）"""
    print(f"\n清洗数据: {len(df)} 行")

    # 日期字段处理（向量化）
    for col in ['order_time', 'pay_time', 'ship_time']:
        if col in df.columns:
            # 先直接尝试 pd.to_datetime（处理大部分标准格式）
            df[col] = pd.to_datetime(df[col], errors='coerce')
            # 对仍为空的用兼容解析（处理特殊格式）
            null_mask = df[col].isna()
            if null_mask.any():
                df.loc[null_mask, col] = pd.to_datetime(
                    df.loc[null_mask, col].astype(str).str.strip(),
                    format='%Y/%m/%d %H:%M:%S',
                    errors='coerce'
                )

    # 金额字段处理
    for col in ['amount', 'refund_amount', 'actual_amount']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 数量字段
    if 'quantity' in df.columns:
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(1)

    # ID字段强制转字符串（避免Parquet缓存与xlsx数据类型冲突，导致to_parquet时ArrowTypeError）
    for col in ['order_id', 'sub_order_id', 'user_id', 'product_id', 'sku_id', 'merchant_code']:
        if col in df.columns:
            df[col] = df[col].astype(str).replace('nan', '').replace('None', '')

    # SPU 匹配（向量化版本：用 pd.merge_asof 替代逐行循环）
    if spu_df is not None and 'product_id' in df.columns and 'order_time' in df.columns:
        print("  执行SPU时间范围匹配（向量化）...")

        spu_cols = ['product_id', 'spu_category', 'spu_type', 'spu_tier',
                     'spu_product_class', 'spu_product_subclass', 'spu_cosmetic',
                     'spu_spec', 'spu_start_date', 'spu_end_date']
        spu_cols = [c for c in spu_cols if c in spu_df.columns]
        spu_df_clean = spu_df[spu_cols].copy()

        # 准备订单数据：只保留需要匹配的列
        orders_match = df[['product_id', 'order_time']].copy()
        orders_match['order_idx'] = orders_match.index

        # 过滤无效行，并统一 product_id 类型为字符串（避免 merge 时类型冲突）
        orders_match = orders_match.dropna(subset=['product_id', 'order_time'])
        orders_match['product_id'] = orders_match['product_id'].astype(str)

        spu_valid = spu_df_clean.dropna(subset=['product_id', 'spu_start_date']).copy()
        # 去掉 float 的 .0 后缀，转换为整数字符串（如 744510508122.0 → "744510508122"）
        spu_valid['product_id'] = spu_valid['product_id'].apply(
            lambda x: str(int(x)) if pd.notna(x) else x
        )

        if len(orders_match) > 0 and len(spu_valid) > 0:
            spu_attr_cols = ['spu_category', 'spu_type', 'spu_tier',
                             'spu_product_class', 'spu_product_subclass',
                             'spu_cosmetic', 'spu_spec', 'spu_hash']
            spu_attr_cols = [c for c in spu_attr_cols if c in spu_valid.columns]

            # 步骤1：过滤出 product_id 在 SPU 表中的订单（避免 merge_asof 跨产品乱匹配）
            orders_in_spu = orders_match[orders_match['product_id'].isin(spu_valid['product_id'])].copy()
            print(f"  product_id 可匹配: {len(orders_in_spu):,} / {len(orders_match):,} ({len(orders_in_spu)/max(len(orders_match),1)*100:.1f}%)")

            if len(orders_in_spu) > 0:
                # 步骤2：常规 merge（product_id + 时间范围），产生候选行
                spu_merge = spu_valid[['product_id', 'spu_start_date', 'spu_end_date'] + spu_attr_cols].copy()
                merged = orders_in_spu.merge(spu_merge, on='product_id', how='left')

                # 步骤3：时间窗口过滤（订单时间在 SPU 有效期内的保留）
                # 条件：order_time >= spu_start_date（已生效）AND order_time <= spu_end_date（未过期）
                # FIX(2026-04-26): 用 normalize() 只比较日期部分，避免 end_date 被解析为
                # YYYY-MM-DD 00:00:00 时，过滤掉同一天后续时间的订单
                valid_mask = (
                    (merged['spu_start_date'].isna() | (merged['order_time'].dt.normalize() >= merged['spu_start_date'].dt.normalize())) &
                    (merged['spu_end_date'].isna() | (merged['spu_end_date'].dt.normalize() >= merged['order_time'].dt.normalize()))
                )
                merged_valid = merged[valid_mask].copy()

                # 步骤4：同一订单可能匹配到多个 SPU，按特异性排序取最优
                # 优先级：spu_product_class 非空 > spu_type 非空 > 更新的 spu_start_date
                # FIX(2026-04-26): spu_start_date 改为降序，确保时间范围更新的记录优先
                merged_valid['_spu_score'] = (
                    merged_valid['spu_product_class'].notna().astype(int) * 100 +
                    merged_valid['spu_type'].notna().astype(int) * 10 +
                    merged_valid['spu_start_date'].notna().astype(int)
                )
                merged_valid = merged_valid.sort_values(
                    ['_spu_score', 'spu_start_date'], ascending=[False, False]
                ).drop_duplicates(subset='order_idx', keep='first')

                matched_count = len(merged_valid)
                print(f"  SPU匹配: {matched_count} / {len(df)} ({matched_count/len(df)*100:.1f}%)")

                # 写回原 DataFrame（通过 order_idx 对齐）
                # 防御：如果 merged_valid 为空，确保 SPU 列初始化为 NaN（不覆盖已有数据）
                if len(merged_valid) > 0:
                    result = merged_valid.set_index('order_idx')[spu_attr_cols]
                    for col in spu_attr_cols:
                        if col in result.columns:
                            df[col] = result[col].reindex(df.index)
                else:
                    # SPU 匹配失败时初始化为空（避免旧数据残留）
                    for col in spu_attr_cols:
                        if col not in df.columns:
                            df[col] = pd.NA

        # SPU 数据验收门卫：在 load_spu_mapping 之后验证 end_date 解析结果
        if spu_df is not None and 'spu_end_date' in spu_df.columns:
            end_date_valid = spu_df['spu_end_date'].notna().mean()
            print(f"  SPU end_date 有效率: {end_date_valid:.1%}  (应为 >0，否则日期解析失败)")
            if end_date_valid < 0.01:
                print("  ⚠️ 警告: spu_end_date 几乎全为 NaT，请检查日期解析逻辑")

    # 渠道匹配（8层漏斗判定）
    print("  执行渠道匹配（8层漏斗）...")
    df = match_channel(df, keyword_rules, id_rules,
                       taoke_order_ids=taoke_order_ids, live_order_ids=live_order_ids,
                       taoke_product_rules=taoke_product_rules)

    # ============================================================
    # 人群看板清洗标记（P0-1, P0-3）
    # ============================================================

    # is_goujinjin：三个字段任意一个含"购物金"或"面值"即标记为购物金用户（剔除）
    mask_gj = (
        df['product_title'].astype(str).str.contains('购物金', na=False) |
        df['sku_name'].astype(str).str.contains('面值', na=False) |
        df['spu_product_class'].astype(str).str.contains('购物金', na=False)
    )
    df['is_goujinjin'] = mask_gj
    print(f"  is_goujinjin（购物金用户）: {mask_gj.sum():,} 行")

    # is_refund：三种情况任意一种即标记为退款（剔除）
    #   1. order_status 含"交易关闭"或"退款"
    #   2. refund_status 非空
    #   3. refund_amount > 0
    order_status_str = df['order_status'].astype(str)
    mask_refund = (
        order_status_str.str.contains('交易关闭', na=False) |
        order_status_str.str.contains('退款', na=False) |
        df['refund_status'].notna() & (df['refund_status'].astype(str).str.strip() != '') |
        (pd.to_numeric(df['refund_amount'], errors='coerce').fillna(0) > 0)
    )
    df['is_refund'] = mask_refund
    print(f"  is_refund（退款订单）: {mask_refund.sum():,} 行")

    print(f"  清洗后: {len(df)} 行")

    # ID字段去重（order_id + sub_order_id 联合唯一，防止Parquet/xlsx混读产生重复）
    before_dedup = len(df)
    df = df.drop_duplicates(subset=['order_id', 'sub_order_id'], keep='first')
    if len(df) < before_dedup:
        print(f"  去重: {before_dedup - len(df)} 行重复订单")

    # ========================================
    # 数据验收门卫（防止脏数据进入数据库）
    # ========================================
    refund_rate = df['is_refund'].mean()
    goujinjin_rate = df['is_goujinjin'].mean()
    REFUND_THRESHOLD = 0.40  # 大促期间退款率可达 35%+
    GOUJINJIN_THRESHOLD = 0.40
    print("\n  【数据验收】")
    print(f"    退款率:   {refund_rate:.1%}  （门卫: <{REFUND_THRESHOLD:.0%} → {'✅' if refund_rate < REFUND_THRESHOLD else '❌ 异常!'}")
    print(f"    购物金率: {goujinjin_rate:.1%}  （门卫: <{GOUJINJIN_THRESHOLD:.0%} → {'✅' if goujinjin_rate < GOUJINJIN_THRESHOLD else '❌ 异常!'}'")
    if not force_continue:
        assert refund_rate < REFUND_THRESHOLD, f"退款率 {refund_rate:.1%} 异常（>{REFUND_THRESHOLD:.0%}），ETL 中止，请检查数据源"
        assert goujinjin_rate < GOUJINJIN_THRESHOLD, f"购物金率 {goujinjin_rate:.1%} 异常（>{GOUJINJIN_THRESHOLD:.0%}），ETL 中止，请检查数据源"
    return df
