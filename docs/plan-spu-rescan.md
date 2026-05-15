# Plan: SPU 重匹配脚本设计

> 创建时间：2026-05-15 22:25
> 状态：待用户确认后执行
> 关联分支：`fix/p1-p3-issues`

---

## 一、问题确认

### 1.1 数据事实

SPU `1008376905465`（凉茶次抛）在匹配表中有两个时间窗口：

| 时间窗口 | spu_type | 规格 | 来源 |
|---------|----------|------|------|
| 2025/12/30 ~ 2026/5/10 | **正装** | 凉茶次抛*1盒30支+5支装*7 | 吴伟东 |
| 2026/5/11 ~ 2099/12/31 | **小样-U先** | 凉茶次抛2支 | 吴伟东 |

当前DuckDB状态：**19,957条订单全部标为"正装"**，其中 5/11~5/15 的 19,936 条应为"小样-U先"。

### 1.2 根因

不是ETL代码bug。ETL的时间窗口过滤逻辑经模拟验证完全正确。  
真正原因：**SPU匹配表在 5/14 数据写入后才更新**，导致历史数据不会自动重新匹配。

### 1.3 影响

- `1008376905465` 从 5/11 起被错误标记为"正装" → 应为"小样-U先"
- 这影响渠道分类：正装 → P8 货架；小样-U先 → P1 U先派样
- 影响渠道分布统计和前端看板数据

---

## 二、脚本设计

### 2.1 脚本路径

`scripts/rescan_spu_mapping.py`

### 2.2 功能规格

```
用法:
  python scripts/rescan_spu_mapping.py --dry-run   # 预览变更（不写入）
  python scripts/rescan_spu_mapping.py --apply      # 执行变更并写入DuckDB

可选参数:
  --product-ids 1008376905465 807010496731          # 指定product_id（默认：全量检查）
  --date-range 2026-05-01 2026-05-15               # 指定订单日期范围（默认：全量）
  --batch-size 50000                                 # 批量写入大小
```

### 2.3 核心逻辑（5步）

```
Step 1: 加载SPU匹配表（复用run_etl.py的load_spu_mapping逻辑）
  → 路径: 芙清CRM数据库/芙清crm原始数据库/天猫_spu单品匹配表_数据表.csv
  → 解析: product_id, spu_start_date, spu_end_date, spu_type等7个属性列
  → 日期解析: 与ETL完全一致

Step 2: 查询受影响订单
  → 从DuckDB读取指定product_id + 日期范围的订单
  → 取: order_id, product_id, pay_time, spu_type (旧值), channel (旧值)

Step 3: 执行SPU匹配（复用run_etl.py第962-1027行逻辑）
  → left join on product_id
  → 时间窗口过滤: order_time >= spu_start_date AND order_time <= spu_end_date
  → 评分排序: spu_product_class非空×100 + spu_type非空×10 + spu_start_date非空×1
  → 取最高分（最新时间窗口优先）

Step 4: 对比新旧spu_type，生成变更报告
  → 统计: 变更订单数、新增/删除/不变
  → 按spu_type分组统计
  → 示例输出:
    ✅ 1008376905465: 19,936 条从 "正装" → "小样-U先"
    ✅ 1008376905465: 21 条保持 "正装" (2026/5/10及之前)

Step 5: 重新匹配渠道（仅在spu_type变更时）
  → 仅对 spu_type 发生变化的订单执行渠道重匹配
  → 复用run_etl.py的match_channel逻辑（但不重新读CSV，直接内联）
  → 关键逻辑:
    - 旧channel="货架"（因为spu_type="正装"走P8）→ 新channel="U先派样"（因为spu_type="小样-U先"走P1）
    - 其他订单channel不变
```

### 2.4 写入策略

```sql
-- 批量UPDATE（通过临时表+JOIN写入）
UPDATE orders 
SET spu_type = ?, channel = ?
WHERE order_id = ?
```

- 支持事务回滚（出错时自动ROLLBACK）
- 写入前打印变更摘要，确认后才执行（--apply模式）
- --dry-run模式：只打印变更报告，不写入

### 2.5 安全措施

| 风险 | 防御 |
|------|------|
| 数据损坏 | 先备份: `COPY orders TO 'backups/orders_before_rescan_YYYYMMDD.parquet'` |
| 误写入 | `--apply`模式需二次确认（输入"yes"） |
| 性能 | 批量写入（batch_size=50000），非逐行UPDATE |
| 回滚 | 出错自动ROLLBACK；备份文件可手动恢复 |

---

## 三、执行计划

### Step 1: 创建脚本
```bash
vim scripts/rescan_spu_mapping.py
```
复用run_etl.py的SPU匹配逻辑，封装为独立可执行脚本。

### Step 2: dry-run验证
```bash
python scripts/rescan_spu_mapping.py --dry-run --product-ids 1008376905465
```
预期输出：19,936 条从"正装"→"小样-U先"。

### Step 3: 执行写入
```bash
python scripts/rescan_spu_mapping.py --apply --product-ids 1008376905465
```

### Step 4: 验证结果
```bash
# 确认spu_type已更新
python -c "
import duckdb
conn = duckdb.connect('data/processed/fuqing_crm.duckdb', read_only=True)
r = conn.execute(\"\"\"
    SELECT COUNT(*), spu_type
    FROM orders WHERE product_id = '1008376905465'
      AND pay_time >= '2026-05-11'
    GROUP BY spu_type
\"\"\").fetchall()
print(r)
conn.close()
"
# 预期: 小样-U先 = 19,936; 正装 = 21 (5/10及之前)
```

### Step 5: 检查渠道变化
```sql
SELECT COUNT(*), channel
FROM orders 
WHERE product_id = '1008376905465' AND pay_time >= '2026-05-11'
GROUP BY channel;
-- 预期: "U先派样" = 19,936（原为"货架"）
```

### Step 6: 检查其他20个受影响ID
```bash
# 逐个dry-run检查
python scripts/rescan_spu_mapping.py --dry-run --product-ids 807010496731
python scripts/rescan_spu_mapping.py --dry-run --product-ids 1008164701807
# ... 依此类推
```

### Step 7: Git提交
```bash
git add scripts/rescan_spu_mapping.py
git commit -m "feat(spu): 重匹配脚本，修复1008376905465时间窗口错标"
```

---

## 四、关键设计决策

| 决策点 | 方案 | 理由 |
|--------|------|------|
| 脚本位置 | `scripts/rescan_spu_mapping.py` | 与ETL脚本同级，独立可执行 |
| 匹配逻辑 | 直接复用run_etl.py 962-1027行 | 保证口径一致，避免引入新bug |
| 渠道重匹配 | 仅对spu_type变更的订单执行 | 避免全量重跑，性能更好 |
| 写入方式 | DuckDB直接UPDATE | 比删库重跑更安全 |
| 回滚机制 | parquet备份 + 事务ROLLBACK | 双保险 |

---

## 五、风险与注意事项

- **数据规模**：1008376905465 有 19,957 条订单，UPDATE 批量执行（预计 <10秒）
- **渠道联动**：spu_type 从"正装"→"小样-U先" 会触发 P1（U先派样）渠道分类
  - 旧channel="货架" → 新channel="U先派样"
  - 前端看板数据会相应变化
- **其他20个ID**：大部分是"正装↔正装"边界日重叠，不影响分类；仅3个需要修复
  - `807010496731`: 小样-U先→正装
  - `1008164701807`: 小样-U先→正装
  - `819173832435`: 正装断裂2天
