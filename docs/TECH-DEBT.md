# 技术债台账 (Technical Debt Ledger)

> **本文档是 fuqing-crm-analytics 项目所有已知技术债的唯一台账。** 任何债都按 P0/P1/P2 分级，记录触发场景、影响、修复方案、估时。
> 维护规则：每个 Sprint 收口（merge --no-ff 到 main）必须 review 本文件，新债加条目，已修债移到文末"已修复"section。

**最后更新**: 2026-06-17 (Sprint 31.1 v0.4.14.111+112 收口, 5 次复发终极治根 — tracker-database 模式替代 prefix matching 机制错误, 3 commit 闭环)
**当前债数**: 0 条 (全闭环)
**已修复**: 13 条 (债 #1/#2/#3/#4/#5/#6/#7 + 债 #195 + 债 #196 + 债 #S26-1 F6 副检 + 债 #S27-1 Tooltip 5346% ×100 + 债 #S28-1 冷启动 mtime 阈值 + 债 #S28+#197 RFM config 冲突 + 债 #S29+#198 disk full 上游 + 债 #S29+#198 RFM stuck index + 债 #S31-1 5 次复发终极治根 tracker-database)
**延后决策**: 1 条 (50m-scale-architecture Phase 1-3 延后到 30M 数据量触发)
**新待办 (Sprint 30-32 计划)**:
- ✅ Sprint 30.1 W4 540 combo batch INSERT (闭环 v0.4.14.105, 50.4× 加速)
- ✅ Sprint 30.2 pre-commit CHANGELOG 改 post-merge hint (闭环 v0.4.14.106, soft WARN)
- ✅ Sprint 30.3 Sprint 17 #120 全量 9 contract audit 简化范围 (闭环 v0.4.14.107, 4 cohort matrix 字段; 剩余 TierFlowRow ratio / NewCustomerConversionFunnel rate / MarketBasketItem support-confidence 走 Sprint 31+ 单独 sprint)
- ✅ Sprint 30.4 CLAUDE.md `*_rate` 表格对齐 (闭环 v0.4.14.108, doc-only)
- ✅ Sprint 31.1 `/tmp/fuqing_*.duckdb` tracker-database 模式 (闭环 v0.4.14.111+v0.4.14.112, 3 commit: Phase 1 inert infra + Phase 2 source of truth + Phase 3 docs)
- Sprint 32.1 Playwright chromium v1208 SSL 修复 (env config) — 待排期
- Sprint 32.2 e2e spec 回归 (一次性) — 待排期

---

## 债 #1 (P0) tracker JSON 设计缺陷 — `cold_start_marked` 字段语义不清

### 触发场景
2026-06-15 ETL 冷启动后, 197 个文件 tracker entry 被 Sprint 21 P0-3 写入 `cold_start_marked: True`, 但 `_file_changed()` 解读 True 为"需重读" (路径 B), 触发**16-32 小时灾难**: 每次增量 ETL 把 197 个老文件全重读。

### 根因
tracker JSON 字段语义不清: 旧实现用 `cold_start_marked=True` 标记"已处理 (但内容陈旧)", `_file_changed()` 误读为"需重读"。**真相**: "已登记 ≠ 需重读"。

### 影响
- 历史重读 197 个文件 (108GB DuckDB DML) 每次 ETL 16-32h
- 6/15 ETL 卡住 11.5min, 实际只读 6/15 一个新文件 (应是 30s)

### 修复方案
Sprint 24 P0-1 (v0.4.14.90, commit `c111400`): `_mark_all_files_processed()` 写 `cold_start_marked: False`. 新语义: **False = "已登记, 不触发重读"**; 真"需重读"由路径 A (新文件 / mtime 变化) 触发。v0.4.14.89 forward-compat fix (Option B 字段存在性判断) 兼容老格式 tracker 的回退路径 (`'cold_start_marked' not in rec → True`)。

### 验证
- `backend/tests/test_coldstart_false_positive.py` (9 tests, v0.4.14.89)
- 6/15 ETL 跑批成功: 14,181 rows, ¥1,523,995.53 GSV, 跑批时长恢复正常

### 估时
已修复, Sprint 24 P0-1 收口 (v0.4.14.90, 完整修复链含 v0.4.14.89 forward-compat)。

---

## 债 #2 (P1) cli.py L310/L424/L688/L859 — sibling read_only=True 同 bug

### 触发场景
Step 8 修复 (v0.4.14.92) 时发现: `scripts/etl/cli.py` 4 处 read_only=True 连接 (L310/L424/L688/L859) 跟 Step 8 一样的 strict mode 风险。本次**只修 Step 8**, 这 4 处未修。

### Ground-truth 验证
```
$ grep -n "read_only=True" scripts/etl/cli.py
310:    conn = duckdb.connect(str(DUCKDB_PATH), read_only=True, config={"memory_limit": DUCKDB_MEMORY_LIMIT})
424:    conn = duckdb.connect(str(DUCKDB_PATH), read_only=True, config={"memory_limit": DUCKDB_MEMORY_LIMIT})
688:                _c0 = _dd2.connect(str(_DDB), read_only=True, config={"memory_limit": DUCKDB_MEMORY_LIMIT})
859:                _c1 = _dd3.connect(str(_DDB2), read_only=True, config={"memory_limit": DUCKDB_MEMORY_LIMIT})
```
4 处全部使用 `read_only=True` (其中 L688/L859 用 `_dd2/_dd3` alias).

### 根因
- L310/L424: 备份场景读 DuckDB (Step 1, 2 backup)
- L688/L859: 6 道门禁 gate check (跨日, dedup)
- 都在 pipeline 不同阶段打开, 跟 pipeline RW 连接交互, 同样有 access_mode 冲突风险

### 当前状态
4 处运行良好 (生产未触发), 但**结构上跟 Step 8 同 bug**, 未来 pipeline 行为变更可能复现。

### 影响
中等. 当前不影响 ETL 跑批, 但任何 pipeline 重构都可能引入回归。

### 修复方案
A) **统一改为非 read_only** (跟 Step 8 一致, 但需评估每个连接的语义)
B) **统一 helper 函数 `_open_duckdb_readonly()`** (Sprint 11 S11-3 类似思路), 集中管理 config 逻辑
C) **接受现状, 监控**

### 估时
- A: human ~2h / CC ~10min
- B: human ~4h / CC ~20min (加测试)
- C: human 0 / CC 0 (保持)

### 推荐
**A**, 跟 Step 8 收口同思路。

---

## 债 #3 (P1) Step 4.7 is_member 跑批 7 分钟 (5.6M UPDATE)

### 触发场景
Sprint 24 P0-1 batch2 (v0.4.14.90) 修 Step 4.7: `WHERE order_id = ANY(CAST(? AS VARCHAR[]))`. 修完后 6,798 个 6/15 会员订单 is_member 标记成功, 但**全表 UPDATE 耗时 7 分钟** (5.6M 行)。

### 影响
- 每次 ETL Step 4.7 占 7/18 = 39% 总时长
- 痛点 1 (Sprint 22 收口 18min) 目标可能退化
- 高频 ETL (每 30min) 累计时长爆炸

### 修复方案
A) **分区 UPDATE** (按 pay_time 范围, 只更新当天 6,798 行而非 5.6M 全表)
B) **增量标记表** (`orders_is_member_pending` 仅含待标订单, Step 4.7 JOIN)
C) **加 idx_orders_pay_time** 让全表 UPDATE 走索引扫描

### 估时
- A: human ~1 day / CC ~30min (SQL 重写 + 测试)
- B: human ~2 days / CC ~1h (新表 + ETL 流程改)
- C: human ~2h / CC ~10min (DDL + 索引重建测试)

### 推荐
**C** 最快见效 (DuckDB ART 索引对 UPDATE 加速 10×+), A 是治根。

### 排期
**待排期** (跟用户当前 sprint 序列)。痛点 1 已闭环 (18 min < 35 min SLO), 紧迫性中等。

---

## 债 #4 (P1) VERSION 文件滞后 17 个版本

### 触发场景
2026-06-16 写 v0.4.14.92 CHANGELOG 时发现: `VERSION` 文件是 `0.4.14.74`, 但 CHANGELOG 已记录到 `v0.4.14.91`. **VERSION 滞后 17 个版本**。

### 根因
历史 merge 流程遗漏 VERSION bump (从 v0.4.14.74 跳到 v0.4.14.91 中间 17 个版本没改 VERSION)。

### 影响
- `scripts/run_etl.py` 用 VERSION 做 health check
- 飞书告警 / 监控可能误判版本
- 调试时容易困惑 (git tag 跟 VERSION 不一致)

### 修复方案
**v0.4.14.92 merge 时已 bump VERSION** (0.4.14.74 → 0.4.14.92). 后续 Sprint 收口 commit 必须:
1. 同步 bump `VERSION` 文件
2. 同步写 CHANGELOG.md entry
3. 同步 `--no-ff` merge commit message 包含版本号

### 估时
预防性 (PR review 加 checklist): 0 (流程改进)

### 验证
- [ ] 后续 merge commit 检查 VERSION + CHANGELOG + git tag 一致
- [ ] Sprint 25 增设 git hook (pre-commit 提醒 bump VERSION)

---

## 债 #5 (P2) `_mark_all_files_processed` 写 `marked_at` 但 ETL 内部不读

### 触发场景
Sprint 21 P0-3 加了 `marked_at` 字段写入 tracker, 但 `_file_changed()` / `_is_file_processed()` 等 ETL 读取函数**从不引用 `marked_at`**, 仅审计 / 调试用。

### 影响
小. 字段占用 tracker JSON ~20 bytes/file × 200 file = 4KB. 无功能影响。

### 修复方案
A) **删除字段** (减少 surface area, 跟 CLAUDE.md §3 精准修改一致)
B) **添加调试输出** (使用字段, 让审计有用)
C) **保持现状**

### 估时
- A: human 5min / CC 1min (加迁移逻辑兼容老 tracker)
- B: human ~1h / CC 5min
- C: 0

### 推荐
**A** (跟 Sprint 24 P0-1 的 `cold_start_marked: False` 语义统一后, marked_at 冗余)。

---

## 债 #6 (P2) `import time` 在函数内 (pipeline.py:131/768/1113)

### 触发场景
`scripts/etl/pipeline.py` 有 3 处 `import time as _time` 在函数体内 (L131, L768, L1113) 而不是 module 顶部。每次 ETL 跑批调用到这 3 个函数, Python 重新做模块查找 + sys.modules 检查, 影响启动速度 ~5ms × 3 = ~15ms。

### Ground-truth 验证
```
$ grep -n "^    import time as _time\|^import time as _time" scripts/etl/pipeline.py
131:    import time as _time
768:    import time as _time
1113:    import time as _time
```
3 处, 全部在函数体内。

### 影响
微. 仅 startup 性能, 无功能影响。

### 修复方案
**统一移到 module 顶部** (3 行 refactor, L4 附近)

### 估时
human 2min / CC 30s

---

## 债 #7 (P2) `_file_changed` 中 `_xlsx_stem_to_rel` 每次 load_data_files 都重算

### 触发场景
Sprint 24 batch2 (v0.4.14.90) 把 `_file_changed` 从 nested closure 抽到 module-level. 但 `_xlsx_stem_to_rel` 字典**每次 `load_data_files()` 调用都重算一次** (扫所有 parquet 文件, 建 stem → rel 映射)。

### 影响
小. ~200 file × stem lookup ≈ 10ms. 频率低 (每次 ETL 一次)。

### 修复方案
**缓存到 module-level** (加 `@functools.lru_cache(maxsize=1)` 或 module-level dict, 配合 mtime invalidate)

### 估时
human 10min / CC 2min

---

## 债 #195 (P3) uvicorn read_only 单例 × ETL 多 RW 连接不变量

### 触发场景
Sprint 24+ P3 adversarial review (v0.4.14.95 Branch 1 Finding 2) 指出: cli.py 4 处 sibling connection 改成 READ_WRITE 后, 4 处 + pipeline 内部 RW + 6 道门禁 L688/L859 + Step 8 baseline L916 都同时存在。如果未来有人重构成 "RW conn 跨函数持有" (例如把 `_c0` 留到 step1 跑完再关), 多 RW 写锁会跟 uvicorn 进程的 read_only 单例 + DuckDB 1.5.x ART index 互动出未定义行为。

### 根因
- `backend/services/health/rfm_analysis/cache.py:4-16`: uvicorn 启动时永久持有 read_only 单例 (fd 持有至进程退出)
- `backend/main.py` 通过 `get_connection()` 启动时永久持有
- ETL 是独立进程, 但 `_open_write_conn()` 仍可同进程 RW 写入 (cache.py:43)
- 4 处 sibling + Step 8 baseline 都立即 conn.close() 释放, 所以当前 **0 风险**
- 但**不变量**没文档化, 未来重构可能违反

### 影响
当前 0 风险 (4 处都 conn.close() 立即释放)。未来违反不变量, 可能出现:
- DuckDB 1.5.x ART index + 多 RW 写锁 contention
- 跨 connection access_mode race (Sprint 21+ P0 治根的同根因)
- uvicorn 重启触发 read_only 单例重连 + ETL 多 RW 互斥等待

### 修复方案
- 在 cli.py 4 处 sibling connection 上方加 `# INVARIANT: 立刻 conn.close(), 不持有跨 step` 注释
- 提取 `_open_duckdb_ro(path)` helper 函数 (Sprint 11 S11-3 思路) + 加 invariant docstring
- (Optional) pre-commit hook 检查 "duckdb.connect" 后 5 行内必须 `conn.close()`

### 估时
- A: human 5min / CC 1min (注释)
- B: human 1h / CC 10min (helper + 测试)
- C: human 4h / CC 30min (hook 写 + 验证)

### 推荐
A 最小化, B 治根。Sprint 25+ 跟债 #3 一起排期。

---

## 债 #196 (P3) Sprint 11 S11-3 vs Sprint 24+ P3 同根因注释未合并

### 触发场景
Sprint 24+ P3 adversarial review (v0.4.14.95 Branch 1 Finding 5) 指出: cli.py 现在 3 段不同位置的注释讲同一根因 (DuckDB 1.5+ strict mode 拒绝同 file 多连接 config 或 access_mode 不一致):
1. Sprint 11 S11-3 注释 (cli.py:686-689) — config dict 缺省
2. Sprint 24+ P3 注释 (cli.py:916-923) — access_mode 不一致
3. (本次 v0.4.14.95) 4 处 sibling 注释互相引用

### 根因
3 段注释分散在 cli.py 3 个不同位置, 描述同一根因的不同面, 缺少"统一入口"或互相引用。

### 影响
- 无功能影响
- 文档债务: 下次 onboarding 困惑 "为什么 3 段注释讲同一件事"
- 未来类似 bug 修复时, 开发者可能只改其中 1 段, 漏掉其他

### 修复方案
- 在 cli.py 顶部加 module-level docstring 段, 说明 "DuckDB strict mode 治根史 (Sprint 11 S11-3 / Sprint 24+ P3 / 24+ P3 收口)"
- 或者: 在 Sprint 11 S11-3 注释处 (cli.py:686-689) 加 "同根因: Sprint 24+ P3 (v0.4.14.92 af90d86) 修了 access_mode 一致性, v0.4.14.95 (ebcc8a4) 4 处 sibling 治根" 引用

### 估时
- A: human 5min / CC 1min
- B: human 5min / CC 1min

### 排期
Sprint 25+ 跟债 #195 一起排期。

---

## 已修复债 (历史归档)

| 债 | Sprint | 修复 commit | 备注 |
|---|---|---|---|
| Step 8 DuckDB 总行数查询 strict mode 冲突 | Sprint 24+ P3 | af90d86 (v0.4.14.92) | 去掉 read_only=True, READ_WRITE 兼容 |
| #1 tracker JSON 设计缺陷 (`cold_start_marked`) | Sprint 24 P0-1 | c111400 (v0.4.14.90) | 治根 `_mark_all_files_processed` 写 False, 兼容老格式 |
| #2 cli.py L310/424/688/859 sibling read_only | Sprint 24+ P3 收口 | ebcc8a4 (v0.4.14.95) | 4 处 sibling 治根, 注释统一指 Sprint 11 S11-3 + Sprint 24+ P3 同根因 |
| #3 Step 4.7 is_member 性能 | Sprint 15 Wave 3 | (Sprint 15 增量 UPDATE 治根) | Step 4.7 改增量 UPDATE (Sprint 15 Wave 3, `scripts/etl/pipeline.py:540-583` `WHERE order_id IN (?, ?, ...)`) + `idx_orders_pay_time` 已建 (`backend/database.py:129` / `scripts/etl/load.py:258` / `pipeline.py:1156` 等), 5.6M 全表 UPDATE 痛点已闭环. 痛点 1 已闭环 18 min < 35 min SLO (Sprint 22 #26). |
| #4 VERSION 文件滞后 | (v0.4.14.92) | (流程改进) | merge 时同步 bump VERSION + 加 review checklist |
| #5 marked_at 字段冗余 | (本次) | (v0.4.14.96) | 删 L790/L812 写入, 0 读取代码, 纯冗余 |
| #6 import time 函数内 3 处 | (本次) | (v0.4.14.96) | 改 module-level 顶部, _time 引用不动 |
| #7 _xlsx_stem_to_rel 重算 | (本次) | (v0.4.14.96) | 加 @functools.lru_cache(maxsize=4) |
| #195 uvicorn × ETL RW 不变量 | (本次) | (v0.4.14.97) | cli.py L310/L424/L688/L859 4 处 sibling conn 上方加 `# INVARIANT: 立刻 conn.close()` 注释, 文档化跨进程不变量 |
| #196 Sprint 11 vs 24+ P3 同根因注释 | (本次) | (v0.4.14.97) | cli.py 顶部 module-level docstring 加 "DuckDB strict mode 治根史" 段, 统一 3 段分散注释 |

---

## 维护规则

1. **新增债**: 在对应 P 级别 section 加 entry, 包含触发场景 / 根因 / 影响 / 修复方案 / 估时
2. **修复债**: 移到文末 "已修复债" 表, 记录 Sprint + commit
3. **优先级变更**: 改 P 级别时必须附 1 行理由
4. **Sprint 收口必 review**: `merge --no-ff` 到 main 前必须 git diff docs/TECH-DEBT.md

## 延后决策 (Sprint 25 立账, 不算 P0/P1/P2/P3 债)

### 50m-scale-architecture Phase 1-3 (延后到 30M 数据量触发)

**触发场景**: Sprint 25 收口前检查 `docs/design/50m-scale-architecture.md` 3 个 phase 未实施 (Phase 1 预计算表 / Phase 2 索引 + ANALYZE / Phase 3 生产部署).

**当前数据规模** (2026-06-16):
- `data/processed/fuqing_crm.duckdb` 103GB, **未到 50M 行** (实际 ~5.6M orders, 距离 50M 还有 ~9× 空间)
- pytest 529 passed / 15 skipped (baseline 526 + 3 新 test = 529, 0 回归)
- ETL 18 min < 35 min SLO (Sprint 22 #26 痛点 1 闭环)
- 痛点 1/2/3 全闭环

**延后理由**:
- 当前 0 性能压力, 18 min SLO 远低于 35 min 阈值
- 50M 行基准是 Sprint 21 容量规划的预期, 实际数据增长曲线未触发
- Phase 1-3 总估时 2 人日 (1d Phase 1 + 0.5d Phase 2 + 0.5d Phase 3), 投在 0 压力场景 ROI 低
- 早做是为未来的钱浪费今天, 跟 Sprint 25 "治根不治标" 原则一致

**触发条件** (任一):
1. `data/processed/fuqing_crm.duckdb` 行数 >= 30M (留 1.67× buffer, 不等到 50M 才慌)
2. ETL 跑批时长 > 30 min (痛点 1 SLO 35 min 的 85% 阈值)
3. 看板 P95 响应 > 5s

**重评估时机**: Sprint 30+ 或任一触发条件命中时, 重新打开此决策 + 排期.

**估时** (如需实施): 2 人日 (Phase 1 1d + Phase 2 0.5d + Phase 3 0.5d)



## 索引

| 债 | 优先级 | 状态 | 估时 |
|---|---|---|---|
| #1 tracker JSON 设计缺陷 | P0 | ✅ 已修复 (v0.4.14.90) | - |
| #2 cli.py L310/424/688/859 read_only | P1 | ✅ 已修复 (v0.4.14.95) | - |
| #3 Step 4.7 is_member 性能 | P1 | ✅ 已修复 (Sprint 15 Wave 3) | - |
| #4 VERSION 文件滞后 | P1 | ✅ 已修复 (v0.4.14.92) | 流程改进 |
| #5 marked_at 字段冗余 | P2 | ✅ 已修复 (v0.4.14.96) | - |
| #6 import time 函数内 | P2 | ✅ 已修复 (v0.4.14.96) | - |
| #7 _xlsx_stem_to_rel 重算 | P2 | ✅ 已修复 (v0.4.14.96) | - |
| #195 uvicorn × ETL RW 不变量 | P3 | ✅ 已修复 (v0.4.14.97) | - |
| #196 Sprint 11 vs 24+ P3 同根因注释 | P3 | ✅ 已修复 (v0.4.14.97) | - |
