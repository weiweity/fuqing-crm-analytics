# Plan: `--rescan-channel` 子命令

## 背景

渠道规则（`渠道判定.csv`）频繁变更（2026-05-15 新增 8 条规则）。每次规则变更后，历史订单的 `channel` 字段需要更新。

当前做法：`--full` 全量重建（42 分钟，处理 234 个源文件 + 10M+ 订单）。

**痛点**：
- 全量重跑时间成本太高（42 分钟）
- 实际只需更新 `channel` 字段，不需要重新解析 Excel、重新匹配 SPU
- 阻塞后续分析工作流

## 目标

实现 `--rescan-channel` 子命令，仅对已有 orders 表中的订单重新匹配渠道规则，**10 分钟内完成**。

## 方案

```bash
# 预览变更
python scripts/run_etl.py --rescan-channel --dry-run

# 执行写入
python scripts/run_etl.py --rescan-channel --apply
```

## 实现步骤

### Step 1: CLI 参数解析

在 `argparse` 中新增：
- `--rescan-channel`: flag，启用渠道重匹配模式
- `--dry-run`: flag，仅预览不写入
- `--apply`: flag，执行写入
- `--since`: 可选，限制日期范围（默认全量）

### Step 2: 加载依赖（复用已有函数）

```python
keyword_rules, id_rules = load_channel_rules()
taoke_order_ids = load_taoke_order_ids()
live_order_ids = load_live_order_ids()
taoke_product_rules = load_taoke_product_rules()
```

### Step 3: 读取 orders 表

从 DuckDB 读取需要重新匹配的订单：
- 字段：`order_id`, `product_title`, `product_id`, `actual_amount`, `pay_time`, `member`, `channel AS old_channel`
- 可选 `--since` 过滤 `pay_time`

### Step 4: 重新匹配渠道

复用 `match_channel(df, keyword_rules, id_rules, ...)`：
1. 将 `channel` 重置为 `'其他'`（作为漏斗起点）
2. 调用 `match_channel()` 重新计算
3. 对比 `old_channel` vs `new_channel`

### Step 5: 生成变更报告

统计并输出：
- 总订单数
- channel 无变化订单数
- channel 有变化订单数
- 变更明细（old → new: count）

### Step 6: 写入（仅在 `--apply` 时）

1. **备份**：受影响订单写入 parquet（复用 `--rescan-spu` 的备份逻辑）
2. **批量 UPDATE**：使用 DuckDB `UPDATE...FROM...JOIN` 语法

## 性能预估

| 步骤 | 预估耗时 |
|------|---------|
| 加载规则（3个函数） | ~30s（淘客缓存） |
| 读取 orders | ~2s（DuckDB 索引） |
| match_channel | ~5-10s（向量化） |
| 写入 UPDATE | ~2s |
| **总计** | **~10min**（含淘客冷加载） |

## 风险与回滚

| 风险 | 缓解措施 |
|------|---------|
| 误更新 | `--dry-run` 预览 + parquet 备份 |
| 写入中断 | DuckDB 是原子事务，UPDATE 失败自动回滚 |
| 规则冲突 | 复用 `match_channel()`，口径与全量一致 |

## NOT in scope

- 不修改 `spu_type` 及相关字段（由 `--rescan-spu` 处理）
- 不重新计算 `is_refund` / `is_goujinjin`（由 `--full` 处理）
- 不新增渠道规则编辑功能（仍通过修改 CSV + 重跑实现）
