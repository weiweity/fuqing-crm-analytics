# Sprint 14 Plan — Ratio 治理 Stage 2 + 治根

**立项时间**: 2026-06-10
**前置**: Sprint 13 收口 (main @ ad1cb20)
**用户决策**:
- 范围: A + B + H (Stage 2 Pydantic + processed_files bug 修 + 清理)
- Sprint 15: C 全做 (useFormat + Branded + Lint)
- Stage 2 顺序: 2a 先 (audience + metrics), 2b 后 (category + health + rfm)

**工作总量**: CC 4-5d / 人 1.5-2d
**墙钟**: 1 周 (1 sprint)

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
B processed_files 误用 bug 修 [独立, 可跟 A 并行]
    ↓
H 清理 [最后, 顺手]
```

**关键路径**: A.1 → A.2 → A.3 (3.5d)
**并行**: B (1-2h) + H (30min) 任意时刻

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

### B 验收
- [ ] 拉数据 pipeline 写 `pending_files.json` 而非 `processed_files_shop.json`
- [ ] ETL Step 0.5 加 pending → processed 转换
- [ ] 模拟拉新 xlsx → 跑 ETL → 6/9 数据进库 (用真实数据)

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
| processed_files bug 修后数据丢失 | 中 | 1 次跑批真实验证, 备份 duckdb |

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

# A.1: 创建 backend/contracts/types.py
# A.1: 替换 audience.py:146-215 (ChannelGSVRow)
# A.1: 替换 metrics.py:19-23 (OverviewMetrics)
# A.1: 跑 pytest + 后端 E2E 验证

# A.2: 装 openapi-typescript + 跑 codegen + 加 pre-commit hook

# A.3: 替换 category.py + health.py + rfm.py
# A.3: 跑 pytest + 后端 E2E 验证

# B: 拉数据 pipeline 改写 pending_files.json
# B: ETL Step 0.5 加转换逻辑
# B: 模拟拉新 xlsx + 跑 ETL 验证

# H: rm 旧 ETL log + 旧备份

# pytest + /review + 修 review + 分批 commit + push + /qa + merge + push main + pull + 重启
```
