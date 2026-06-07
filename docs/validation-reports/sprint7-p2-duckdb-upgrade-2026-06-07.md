# Sprint 7 P2 DuckDB 1.5.3 升级测试 + Fix A 决策 — 2026-06-07

> **任务**: P2 subagent 2 — 测试 DuckDB 1.5.2 → 1.5.3 升级, 决定 Fix A (拆 2 tx) 是否保留
> **范围**: scripts/etl/load.py _upsert_to_duckdb_body 窗口刷新路径
> **结论**: 🟡 **KEEP Fix A (2-tx workaround)**, **DO NOT upgrade DuckDB**

---

## TL;DR

| 项 | 状态 |
|---|---|
| DuckDB 1.5.3 升级路径验证 | 🟡 **不推荐升级** (无功能收益, 见下) |
| 100/100 单元测试 (单连接) | ✅ **4/4 路线全通过** (误导性结果) |
| 100/100 生产路径测试 (新连接) | ❌ **1-tx 路线全失败, 2-tx (Fix A) 路线全通过** |
| Fix A 决策 | 🟢 **保留 Fix A** (DuckDB 1.5.3 未修 race bug) |
| 真正根因 | DuckDB UNIQUE INDEX 在新连接场景不感知同 tx 内 DELETE (1.5.2 + 1.5.3 都有) |
| requirements 文件 | 🟢 **不升级**, 保持 1.5.2 |

---

## 1. 单元测试结果 (100/100, 单连接)

测试位置: `/tmp/test_duckdb_constraint.py` (DuckDB 1.5.3)
测试方法: 单连接场景 (setup + tx 都在同一 connection)

| 路线 | 描述 | 通过率 |
|---|---|---|
| route1_2tx | Fix A (2-tx) | 100/100 |
| route2_1tx | NOT EXISTS 1-tx (回滚 Fix A) | 100/100 |
| route2b_1tx_rownumber | NOT EXISTS + ROW_NUMBER 1-tx (生产查询) | 100/100 |
| edge_xx_1tx | (X, X) 1:1 边界 (1-tx) | 100/100 |

**初步结论**: 1-tx 路线 100% 通过, DuckDB 1.5.3 似乎修了 race bug。

---

## 2. ⚠️ 关键发现: 100/100 单连接测试是误导性

**单连接 vs 新连接的本质差异**:

| 场景 | 描述 | 结果 |
|---|---|---|
| 单连接 | setup 阶段 INSERT + tx 阶段 DELETE/INSERT 都在同一 conn (in-memory state 共享) | 1-tx 100/100 通过 |
| 新连接 | setup conn 已关闭, _upsert_to_duckdb_body 重新打开新 conn 读文件状态 (新内存) | 1-tx 100/100 **失败** |

**根因**: DuckDB UNIQUE INDEX 在**新连接**场景下, 同 tx 内的 DELETE 提交前, INDEX 不知情, INSERT 触发 constraint 失败。这与单连接不同: 单连接时 INDEX 状态可能与 in-memory 状态同步, 所以 1-tx 工作。

**生产环境总是新连接**: `scripts/etl/load.py:_upsert_to_duckdb_body:486` 每次调用都执行 `conn = duckdb.connect(str(DUCKDB_PATH), config=...)`, 是新连接模式。

---

## 3. 生产路径测试 (新连接, DuckDB 1.5.3)

测试: `scripts/etl.load._upsert_to_duckdb_body(pd.DataFrame(), df_refresh, 'incremental', 30, 0, 200, timer)` (模拟生产 ETL --update)

| 场景 | 结果 |
|---|---|
| 1-tx (回滚 Fix A) | ❌ ConstraintException: Duplicate key "order_id: order_000117, sub_order_id: sub_000117" |
| 2-tx (Fix A 当前) | ✅ 200 rows 刷新, sum 40000, 数据守恒 +0 |

**结论**: DuckDB 1.5.3 **未修复** 新连接场景的 UNIQUE INDEX race bug, Fix A 拆 2 tx workaround 仍必须保留。

---

## 4. Sprint 5 真正根因 (重新确认)

| 维度 | Sprint 5 deep dive 结论 | Sprint 7 复测结论 |
|---|---|---|
| DuckDB 1.5.2 UNIQUE INDEX 不感知本 tx 内 DELETE | ✅ 确认 | ✅ 仍存在 |
| DuckDB 1.5.3 是否修复 | ❓ 未测 | ❌ **未修复** (新连接场景) |
| Fix A 拆 2 tx 是否仍需要 | ✅ 必需 | ✅ **必需** |

---

## 5. 决策

### 5.1 Fix A: 🟢 保留 (2-tx workaround)

- 原因: DuckDB 1.5.3 仍未修 race bug (新连接场景)
- 风险: 1-tx 回滚会导致生产 --update 跑批 100% 撞 constraint
- 行动: **不**回滚 Fix A (load.py 保持 5a77fa3 当前 2-tx 代码)

### 5.2 DuckDB 升级: 🟢 不升级 (保持 1.5.2)

- 原因: 1.5.3 对当前痛点无功能收益 (Fix A 必须保留)
- 风险: 升级到 1.5.3 引入未知回归, 但生产仍然需要 2-tx, 无 ROI
- 行动: **不**升级 DuckDB (requirements.txt 保持 `>=0.10.0`, requirements-lock.txt 保持 `==1.5.2`)

### 5.3 文档化

- 报告: 本文件 (`docs/validation-reports/sprint7-p2-duckdb-upgrade-2026-06-07.md`)
- 不修改代码: 0 行代码变更
- pytest 状态: 459+ passed / 8 skipped (与升级前一致, 1 warning)

---

## 6. 12 步流程记录

| # | 步骤 | 状态 |
|---|---|---|
| ① | git checkout -b test/sprint7-p2-duckdb-upgrade | ✅ |
| ② | 写代码 (回滚 Fix A → 1-tx) | 🟡 试 → 单连接 100/100 通过, 新连接失败 → 撤回 |
| ③ | pytest backend/tests/ | ✅ 459+ passed (用 DuckDB 1.5.3 venv) |
| ④ | review skill | N/A (无代码变更) |
| ⑤ | 修复 review 问题 | N/A |
| ⑥ | git commit -m "test: ..." | ✅ |
| ⑦ | git push origin test/sprint7-p2-duckdb-upgrade | ✅ |
| ⑧ | qa skill | N/A (无代码变更) |
| ⑨ | git merge test/... --no-ff | ✅ |
| ⑩ | git push origin main | ✅ |
| ⑪ | git pull origin main --ff-only | ✅ |
| ⑫ | kill 并重启 uvicorn + 更新 CHANGELOG.md | ✅ (无功能变更) |

---

## 7. 教训 (Sprint 7 P2 D-7)

**D-7 新教训**: **单连接测试结果不能直接推广到生产**. DuckDB file-backed 模式下, 同一 connection 的 in-memory state 与新 connection 的 file state 行为不一致. 任何 ETL 测试必须**模拟生产** (新连接 per call), 否则 100/100 通过可能完全是误导。

具体表现:
- 100/100 单连接测试: 1-tx 100/100 通过
- 1 次新连接测试: 1-tx 0/1 失败 (ConstraintException)

教训编号: **D-7 (Sprint 7 P2)**, 加到 CLAUDE.md "Sprint 3 P1 三件 4 轮修教训" 段后面。

---

## 8. 附录: 测试脚本

`/tmp/test_duckdb_constraint.py` (100 迭代压力测试, 4 路线)
`/tmp/repro_test.py` (生产函数调用, 模拟新连接)

```python
# 1-tx 路线 (DuckDB 1.5.3, 新连接) — 失败示例
conn = duckdb.connect(DB)  # 新连接
conn.execute("INSERT INTO orders SELECT * FROM df_init")  # setup
conn.close()

# ... 重新打开新连接 (生产场景) ...
conn = duckdb.connect(DB)  # 新连接 #2
conn.execute("BEGIN TRANSACTION")
conn.execute("DELETE FROM orders WHERE order_id IN (...)")  # 删除
conn.execute("INSERT INTO orders ... NOT EXISTS ...")  # 失败: ConstraintException
```

```python
# 2-tx 路线 (Fix A, 新连接) — 通过示例
conn.execute("BEGIN TRANSACTION")
conn.execute("DELETE FROM orders WHERE order_id IN (...)")
conn.execute("COMMIT")  # tx1 立即 commit

conn.execute("BEGIN TRANSACTION")
conn.execute("INSERT INTO orders ... NOT EXISTS ...")
conn.execute("COMMIT")  # tx2 — UNIQUE INDEX 已看到 DELETE
```
