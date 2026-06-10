# Sprint 14 Plan — Ratio 治理 Stage 2 + 治根 + ETL 隐藏 Bug

**立项时间**: 2026-06-10
**前置**: Sprint 13 收口 (main @ ad1cb20)
**用户决策** (2026-06-10 拍板):
- 范围: A + B (扩) + B+ (新增 is_member) + H
- B 方案: A 选项 — 统一用源 xlsx mtime (修 processed mtime 语义错位)
- is_member 方案: P 选项 — 集成 build_membership_mark + replay_is_member 到主流程
- Sprint 15: C 全做 (useFormat + Branded + Lint)
- Stage 2 顺序: 2a 先 (audience + metrics), 2b 后 (category + health + rfm)

**工作总量**: CC 5-6d / 人 2-2.5d
**墙钟**: 1 周 (1 sprint)

**Sprint 14 扩范围原因** (2026-06-10 调研):
1. **Bug 1 (file scan)**: `processed_files_*.json` mtime 字段语义错位 — parquet 路径写 parquet mtime, xlsx 路径写 xlsx mtime, _file_changed 比较时间基准不一致
2. **Bug 2 (is_member)**: `pipeline.py:329` 增量模式 `shop_df.is_member = order_id in member_order_ids`,但 `member_order_ids` 仅来自"新 parquet"或"DB 历史 is_member=TRUE",两者均有缺陷;Sprint 10 写了 2 个手动救火脚本未集成

---

## 工单分解 (按依赖排序)

### A) Stage 2 Pydantic 契约加固 (3.5d)

#### A.1 Stage 2a: audience.py + metrics.py (1.5d)

**目标**: 6 个契约加 `Annotated[float, Field(ge/le/decimal_places)]` validator

| 文件 | 关键字段 | 范围 |
|---|---|---|
| `backend/contracts/audience.py:146-215` | ChannelGSVRow 70+ ratio/yoy 字段 | ratio: 0-1 / percentage: 0-100 / pp: -100~100 |
| `backend/contracts/metrics.py:19-23` | OverviewMetrics (old_user_ratio, new_user_ratio, member_ratio) | 0-1 |

**实施**:
- 新建 `backend/contracts/types.py` 三个自定义类型
  ```python
  RatioField: Annotated[float, Field(ge=0, le=1, decimal_places=4)]
  PercentageField: Annotated[float, Field(ge=0, le=100, decimal_places=2)]
  PpField: Annotated[float, Field(ge=-100, le=100, decimal_places=2)]
  ```
- 替换所有 `float = Field(...)` 为对应类型
- 加 OpenAPI schema description ("0-1 decimal" / "0-100 percentage" / "pp 差")
- 跑 backend E2E 验证序列化不回归 (Stage 2a 后必须跑!)

**完成后**:
- pytest backend/tests/ 全过
- /audience API 返 4xx (如果传 5.0 给 RatioField) — 验证 validator 工作

#### A.2 Stage 2a 后: openapi-typescript codegen (0.5d)

**目标**: 让前端 TS 类型从 OpenAPI schema 自动派生, 避免 70 个 ChannelGSVRow 字段手抄 JSDoc drift

- 装 `openapi-typescript`: `npm install -D openapi-typescript`
- 跑 `npx openapi-typescript http://localhost:8000/openapi.json -o frontend-vue3/src/api/types.generated.ts`
- 加 pre-commit hook: 跑 codegen, 验证无 diff
- 前端 caller 改用 `types.generated.ts` 替代手写 types

#### A.3 Stage 2b: category.py + health.py + rfm.py (2d)

**目标**: 4 个契约加 validator (audience + metrics 已 2a 改)

| 文件 | 关键字段 |
|---|---|
| `backend/contracts/category.py:26-183` | CategoryOverviewItem (old_ratio 等 30+ 字段) + CategoryRepurchaseFlowRow + ValueTierTableRow |
| `backend/contracts/health.py:18-92` | HealthOverviewMetrics + RepurchaseBucket |
| `backend/contracts/rfm.py:99-113` | RFMRFlowRow + RFMFRFlowRow + RFMMFlowRow + RFMAnalysisRow |

**实施**:
- 用 Pydantic `Annotated[float, Field(...)]` 模式
- 70+ 字段全替换
- 跑 backend E2E 验证 (主要 caller: CategoryView, HealthOverviewTab, RFMView)

**完成后**:
- pytest 375+ passed
- 后端 OpenAPI schema 自动带 `minimum: 0, maximum: 100` 等约束
- 前端 codegen 后 TS 类型带 `// @min: 0, @max: 100` 注释

---

### B) processed_files 误用 bug 修 (1-2h)

**问题**: 6/9 数据第一次 ETL 没进库 — 拉数据时 (00:29) processed_files_shop.json 提前更新, 但 ETL 跑批 (10:18) 增量模式判定"已处理"跳过, 实际 INSERT 没发生过

**根因**: 拉数据 pipeline 跟 ETL pipeline 是两个独立 pipeline, 但都写 `processed_files_shop.json` 同一个 artifact. 应分离:
- 拉数据 pipeline: 写 `pending_files.json` (待 ETL 处理)
- ETL pipeline: 写 `processed_files_shop.json` (已成功 INSERT)

**实施**:
- 找拉数据 pipeline 代码 (在哪写 processed_files_shop)
- 改成写 `data/processed/pending_files.json`
- ETL pipeline 加新 Step 0.5: 检查 pending_files → 转换 processed_files (INSERT 成功后)
- 跑 1 次 ETL 验证 6/9 数据 (模拟新 xlsx 拉取)

**Sprint 14 修订** (2026-06-10 拍板, 方案 A):
**问题**: 同 1 个 `processed_files_*.json` 的 `mtime` 字段, parquet 路径写 parquet 文件 mtime (ingest.py:149), xlsx 路径写 xlsx 文件 mtime (ingest.py:217). _file_changed 比较时一边的"源 mtime" (取 f.stat().st_mtime, 源 xlsx) 跟"processed mtime" (parquet or xlsx 都有可能) 基准不一致, 导致:
- 6/10 那条 shop xlsx (21596) 走 xlsx fallback 后, processed mtime=11:20:32 (parquet 写入时间), 后续对源 xlsx mtime=00:29:04 比较错位
- 潜在风险: 拉数据 pipeline 重新拉一条 xlsx (mtime 变大), 但 processed mtime 是老的 parquet 时间, 可能数值更小, 误判为 "已处理"

**根因**: v2 hash 实现 (ingest.py:79-97 _file_changed) 假设 processed mtime = 源文件 mtime, 但 ingest 写入时未严格保证此不变量

**修法 (方案 A: 统一用源 xlsx mtime)**:
- ingest.py:144-151 (parquet 路径): 改用 `_xlsx_stem_to_rel` 反查 xlsx 路径, 取 xlsx 的 mtime (而非 parquet 的 mtime) 写入 processed
- 关键: `_xlsx_stem_to_rel` 已在 ingest.py:75-77 构建, key 反查 100% 命中 (Sprint 9 维修时已加固)
- 跑 1 次 ETL 验证: 模拟拉一条新 xlsx → 跑批 → 确认 _file_changed 正确识别

**为什么不用方案 B (拉数据写 pending_files)**: Sprint 14.5 再做, 当前优先治本 mtime 语义错位. 方案 B 是上下游解耦, 治本; 方案 A 是内部一致性, 治标. 选 A 因为改动小 (1 行) + Sprint 10/11 已用 _xlsx_stem_to_rel 路径, 无新依赖.

**Sprint 14 范围调整**: B 工单从 1-2h 扩到 1d (mtime 语义统一 + 验证 + 回归测试)

---

### B+) is_member replay 集成 (新增, 0.5d)

**问题**: prod orders 表 is_member 长期累积错误 (2020-2026 大半 FALSE). 根因: pipeline.py:329 增量模式 `shop_df.is_member = order_id in member_order_ids`, 但 member_order_ids 来源有缺陷 (line 144-174):
- member parquet 空 → 走 fallback 从 DuckDB `WHERE is_member = TRUE` 读 → 鸡生蛋循环 (DB 错 → fallback 错)
- member parquet 新增 → 只用新文件的 order_id → 老会员 order_id 丢失 → 老会员被标 FALSE

**Sprint 10 临时救火**: 写了 2 个手动脚本
- `scripts/etl/build_membership_mark.py` (68 行): 从 79 个 member parquet 加载 4.6M unique order_id 到 `membership_mark` 持久表
- `scripts/etl/replay_is_member.py` (116 行): DROP 6 secondary index → UPDATE orders JOIN membership_mark (1.8s) → 重建 index (19.7s)

**问题**: 0 处自动集成,需手动跑 `python3 scripts/etl/build_membership_mark.py && python3 scripts/etl/replay_is_member.py`

**Sprint 14 修法 (方案 P: 集成到主流程)**:
- pipeline.py 加 Step 4.6 (在 upsert_to_duckdb 之后, _mark_all_files_processed 之前):
  ```python
  from scripts.etl.build_membership_mark import main as build_membership_mark_main
  build_membership_mark_main()
  ```
- pipeline.py 加 Step 4.7 (在 4.6 之后):
  ```python
  from scripts.etl.replay_is_member import main as replay_is_member_main
  replay_is_member_main()
  ```
- 跑批时间增量: +1-2 min (1.8s UPDATE + 19.7s index + 0.5s build)
- 幂等: 两个脚本已幂等 (ON CONFLICT DO NOTHING / 只 UPDATE is_member=FALSE)
- W6 通知里加 stats: `member_mark_count`, `is_member_replay_delta`

**为什么不用方案 Q (cron 自动跑)**: 跟 ETL 主流程不集成, 故障域 +1, 跑批窗口难对齐. 选 P 因为改 2 行 + 自动一致.

**验收**:
- 跑 1 次 ETL: `orders.is_member = TRUE` 数量应从当前 3.xM 涨到 4.6M (跟 membership_mark 对齐)
- 跑 2 次 ETL: 数字稳定 (幂等)
- dq_monitor.py member_ratio check 通过 (>= 10% 阈值)
- 4 页面 is_member 指标 (audience/category/health) 一致

---

### H) 清理 (30min)

**目标**: 释放磁盘 + 清理 Sprint 12/13 跑批残留

| 项 | 路径 | 大小估计 |
|---|---|---|
| 旧 ETL log | /tmp/etl-*.log (8 个) | ~800KB |
| 旧备份 (Sprint 12 之前) | data/processed/backups/ | ~30GB |
| Sprint 12/13 plan | docs/SPRINT-12-*.md (旧) | ~50KB |
| 6 层防护 tmp | /private/tmp/fq-* | ~5GB |

**实施**:
- `rm /tmp/etl-{full,inc,w1,w3,w4}*.log` (保留最近 1 个)
- `rm data/processed/backups/pre-sprint{10,11,12}*.duckdb` (保留 sprint13 最新)
- 6 层防护 (CLAUDE.md): 第 6 层 hourly 兜底会清理

---

## 依赖图

```
A.1 Stage 2a (audience + metrics)
    ↓
A.2 codegen 中间层 (openapi-typescript)
    ↓
A.3 Stage 2b (category + health + rfm) [依赖 2a 经验]
    ↓
B processed_files mtime 语义统一 (方案 A) [独立, 可跟 A 并行]
    ↓
B+ is_member replay 集成 (方案 P) [依赖 B 后的 Step 4.6 位置]
    ↓
H 清理 [最后, 顺手]
```

**关键路径**: A.1 → A.2 → A.3 (3.5d)
**并行**: B (1d) + B+ (0.5d) 跟 A 任意时刻交叉; H (30min) 收口
**Sprint 14 总工作量**: CC 5-6d / 人 2-2.5d (从 4-5d 扩 1.5d)
**Sprint 14 墙钟**: 1 周 (1 sprint)

---

## 验收标准

### A.1 验收
- [ ] `RatioField / PercentageField / PpField` 三个自定义类型在 `backend/contracts/types.py`
- [ ] `contracts/audience.py:146-215` ChannelGSVRow 70+ 字段全替换
- [ ] `contracts/metrics.py:19-23` OverviewMetrics 全替换
- [ ] pytest backend/tests/ 全过 (375+)
- [ ] 错值注入: 传 5.0 给 RatioField → 422 ValidationError
- [ ] OpenAPI schema 自动带 `minimum: 0, maximum: 1`

### A.2 验收
- [ ] `npx openapi-typescript` 跑通, 输出 `frontend-vue3/src/api/types.generated.ts`
- [ ] pre-commit hook 加 codegen 检查 (无 diff 才通过)
- [ ] 前端 `audience.ts:184` 等手写 type 改用 `types.generated.ts`

### A.3 验收
- [ ] `category.py:26-183` CategoryOverviewItem 30+ 字段全替换
- [ ] `health.py:18-92` HealthOverviewMetrics + RepurchaseBucket 全替换
- [ ] `rfm.py:99-113` RFMRFlowRow + RFMFRFlowRow + RFMMFlowRow + RFMAnalysisRow 全替换
- [ ] pytest 375+ passed
- [ ] OpenAPI schema 全部 5 个 contract 文件带 minimum/maximum

### B 验收 (方案 A: mtime 语义统一)
- [ ] `ingest.py:144-151` parquet 路径改用 `_xlsx_stem_to_rel` 反查 xlsx, mtime 写 xlsx 实际 mtime
- [ ] 现有 `processed_files_*.json` 中老 mtime (parquet 写入时间) 一次性迁移: 跑全量 ETL 重建 (Step 7 _mark_all_files_processed 自动覆盖)
- [ ] 模拟拉一条新 xlsx → 跑 ETL → _file_changed 正确识别为新文件
- [ ] pytest: `test_fill_parquet_cache.py` 验证 mtime 语义一致 (key 反查 100% 命中)
- [ ] B 工单完成后, processed_files_*.json 所有 mtime 字段都跟源 xlsx mtime 一致 (验收脚本: `jq -r '.[] | .mtime' data/processed/processed_files_*.json` 对比 xlsx mtime)

### B+ 验收 (方案 P: is_member replay 集成)
- [ ] `pipeline.py` 在 Step 4 (upsert) 之后, Step 7 (_mark_all_files_processed) 之前, 调 `build_membership_mark.main()` + `replay_is_member.main()`
- [ ] 跑 1 次 ETL: `orders.is_member = TRUE` 数量从当前 3.xM 涨到 ~4.6M (跟 membership_mark 对齐)
- [ ] 跑 2 次 ETL: 数字稳定 (幂等)
- [ ] dq_monitor.py member_ratio check 通过 (>= 10% 阈值)
- [ ] 4 页面 (audience/category/health/audience_table) is_member 指标一致
- [ ] W6 通知 stats 加 `member_mark_count` + `is_member_replay_delta`

### H 验收
- [ ] /tmp/etl-*.log 只留最新 1 个
- [ ] data/processed/backups/ 只留 sprint13 最新 1 个
- [ ] 释放磁盘 ~30GB

---

## 风险评估

| 风险 | 概率 | 缓解 |
|---|---|---|
| Pydantic v2 序列化回归 | 中 | A.1 后必跑 E2E, 不通过回滚 |
| 6 个 contract 一次性改回归 | 低 | 2a→2b 拆分验证 |
| codegen 类型跟手写冲突 | 中 | types.generated.ts 跟手写并存 1 sprint, 逐步切换 |
| processed_files mtime 修后 _file_changed 误判 | 中 | 1 次跑批真实验证, 备份 duckdb |
| **mtime 老数据迁移失败** | 中 | 跑全量 ETL (Step 7) 自动覆盖; 不在增量路径硬迁移, 风险隔离 |
| is_member replay 跑批时间 +1-2 min | 低 | 跟 30 min 跑批基线比 < 5%, 接受 |
| DuckDB 1.5.2 ART race 在 replay 时触发 | 低 | DROP 6 secondary index 是 Sprint 10 已验证缓解; 但全量 replay 风险 ↑, 跑 1 次真验 |

---

## Sprint 15 预告 (Stage 3 全做)

**范围**: composables/useFormat.ts + TypeScript Branded Type + ESLint AST 级别 lint
**工作量**: CC 5-7d / 人 2d
**价值**: 50% AI 友好化, 防 LLM 写双重 *100

---

## 启动命令

```bash
git checkout main && git pull origin main --ff-only
git checkout -b fix/sprint14-ratio-stage2

# Wave 1 (Stage 2a Pydantic): 6 字段 Pydantic Field validator
# A.1: 创建 backend/contracts/types.py (RatioField / PercentageField / PpField)
# A.1: 替换 audience.py:146-215 (ChannelGSVRow 70+ 字段)
# A.1: 替换 metrics.py:19-23 (OverviewMetrics)
# A.1: 跑 pytest + 后端 E2E 验证

# Wave 2 (codegen): openapi-typescript 中间层
# A.2: 装 openapi-typescript + 跑 codegen + 加 pre-commit hook

# Wave 3 (Stage 2b Pydantic): 4 contract validator
# A.3: 替换 category.py + health.py + rfm.py
# A.3: 跑 pytest + 后端 E2E 验证

# Wave 4 (B processed_files mtime 语义): 1d
# B: ingest.py:144-151 改用 _xlsx_stem_to_rel 反查 xlsx
# B: pytest test_fill_parquet_cache.py 验证
# B: 跑 1 次 ETL 验证 mtime 一致性 (备份 duckdb 后)
# B: 跑全量 ETL 重建老 mtime 字段 (Step 7 自动)

# Wave 5 (B+ is_member replay 集成): 0.5d
# B+: pipeline.py 加 Step 4.6 (build_membership_mark) + Step 4.7 (replay_is_member)
# B+: 跑 1 次 ETL 验证 is_member 涨到 ~4.6M
# B+: 跑 2 次 ETL 验证幂等
# B+: 4 页面 is_member 指标一致性检查

# Wave 6 (H 清理): 30min
# H: rm 旧 ETL log + 旧备份

# 12 步流程 (跟单 commit):
# pytest backend/tests/ -x -q
# /review skill (每个 commit 前必跑)
# 修 review 问题
# 分批 commit + push origin fix 分支
# /qa skill
# merge → main + push main + pull + 重启 uvicorn
```
