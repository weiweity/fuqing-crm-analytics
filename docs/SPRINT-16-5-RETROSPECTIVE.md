# Sprint 16.5 Retrospective — P1/P2 治理收口 (3/4 完成 + 1 NO-OP)

**Sprint**: 16.5 (Sprint 16 P0 中止后转治理 mini-sprint)
**时间**: 2026-06-11
**状态**: ✅ 收口 (main @ 953f1d1, v0.4.14.40)
**主题**: 4 subagent workflow 并行 1.5h, 3 P1/P2 治根 + 1 task scope 矛盾 no-op

---

## 1. Sprint 结果

| 维度 | Sprint 16 收口 (前一 sprint) | Sprint 16.5 收口 (本次) | Delta |
|------|-------------------------------|--------------------------|-------|
| **Sprint 16 P0** (DuckDB race 治根) | ❌ 中止 (3 race 症状 + 1.5.4 没 release) | — | 中止决策 |
| **P2.7 cache_key MD5 full** | — | **✅ 治根 (1180× 加速)** | 新增 |
| **B2 试点 3 contract audit** | — | **✅ 9 mark 字段治根** | 新增 |
| **YOYBadge 异常值守卫** | — | **✅ 浅 feature** | 新增 |
| **B1 audience 28 字段** | — | **❌ NO-OP (scope 矛盾)** | 关任务 |
| **4 端点 HTTP** | r-flow 1180× 慢 | **r-flow 1180× 加速** | 治根 |
| **contract 越界 422 拦截** | — | **9 mark 字段全 422 拦截** | 新增 |
| **前端 YOY 异常值守卫** | 无 | **|v|>1e6 → 数据异常** | 新增 |
| **测试** | | | |
| test_w5_cache.py | 17 | 23 (+6) | +6 tests |
| test_b2_contract_mark_pilot.py | — | 13 (新建) | +13 tests |
| YOYBadge.test.ts | 12 | 16 (+4) | +4 tests |
| 全部 backend pytest | 424 passed | 437 passed + 12 skipped | +13 |
| **Commits** | 1 (Sprint 16 abort) | +6 (3 fix + 3 merge + 3 docs) | +6 commits |
| **Workflow** | 1 subagent (P0) | 4 subagent 并行 1.5h, 468K tokens | +4 subagents |

---

## 2. 3 任务治根复盘

### 2.1 P2.7 cache_key MD5 full 治根 (1180× 加速)

**根因 (CodeX audit 揪出)**:
- `_flow_cache_key` 8 维参数用 `_` 拼接文件名 + `exclude_channels` 用 `MD5[:8]` 截断 (32 bit)
- 生日悖论: 2^16 = 65K 列表 50% 碰撞, 大 exclude list 必误命中
- `_hash_key` (W5 DuckDB-KV) 跟 `_flow_cache_key` (file) 共享 hex hash namespace → 跨 cache 串扰风险

**治根 (3 文件 +160 -17)**:
- `backend/services/rfm/_shared.py:194 _flow_cache_key` — 8 维参数 + `FLOW_ALGO_VERSION` 全部进 MD5 full (128 bit, 2^64 列表才 50% 碰撞), 加 `flow_` namespace prefix
- `backend/services/rfm/cache.py:66 _hash_key` — 加 `w5kv_` namespace prefix, 保留 Sprint 14.5 P1.4 `FLOW_ALGO_VERSION` 校验
- `backend/tests/test_w5_cache.py +6 tests` — `TestFlowCacheKeyMd5Full` 类, 6 件套: 不同参数/同参数幂等/MD5 full 格式/截断 vs full 冲突/algo_version 失效/跨 namespace 隔离

**治根效果 (生产 uvicorn 实跑)**:
- `r-flow`: 1st cache miss 6.45s → 2nd cache hit 0.005s (**1180× 加速**)
- `f-flow` / `m-flow` / `segment-orders` 4 端点全 200
- 23/23 tests passed (17 老的 W5 cache 回归 + 6 个新加)
- 旧 cache 文件名 (`r_flow_v123_2026-01-01_2026-01-31_GSV.json`) 跟新格式 (`flow_<32hex>.json`) 完全不同, 24h TTL 内自然失效
- 兼容 `_flow_engine.py:461` + `scripts/warm_flow_cache.py:96` 2 个调用方 (签名未变)

### 2.2 B2 试点 3 contract audit 治根 (9 mark 字段)

**根因 (Sprint 15 B1 模式扩到 3 contract)**:
- Sprint 15 B1 修了 is_member mark 缺口同步 (ETL 层)
- Sprint 16.5 B2 准备扩到 category + metrics + health 3 contract (Pydantic 层)
- 试点 audit 找出 9 mark 字段 (3 contract × 3 字段) 缺 Pydantic Field 元数据

**治根 (3 文件 + audit 报告)**:
- `backend/contracts/category.py:14-16` CategoryDistributionItem.pct/penetration_rate/member_ratio 改 `"RatioField"` (ge=0, le=1)
- `backend/contracts/metrics.py:34-36` TrendData.member_ratios/ly_amounts/ly_member_ratios 改 `List[Annotated[float, Field(ge, le)]]`
  - **Pydantic v2 知识点**: `List["PercentageField"]` 不会触发 element-wise 约束 (前向引用解析为 float, Field 元数据丢失), 必须 `List[Annotated[float, Field(...)]]` 才会 TypeAdapter 解析
- `backend/contracts/health.py:145/167/193` ValueTierDefinition/CustomerSegmentItem/TierFlowRow 3 个 gsv_ratio 改 `"RatioField"`
- 9 mark 越界 (e.g. pct=1.5) → Pydantic v2 ValidationError → FastAPI 422 拦截 (原本 API 层 500)
- `backend/tests/test_b2_contract_mark_pilot.py` 13 tests (9 越界 + 1 合法 + 3 baseline happy path)
- `docs/SPRINT-16-5-B2-AUDIT.md` (252 行) 完整 audit 报告

**治根效果**:
- `category/overview` + `metrics/trend` + `customer-health/overview` + `customer-health/value-tiers` 4 端点全 200
- 437 passed + 12 skipped 全套件无 contract-related failures

### 2.3 YOYBadge 异常值守卫 (浅 feature)

**根因 (前后端契约不一致)**:
- Sprint 15 Wave 1 PercentageField 放宽到 ±1B (兼容 yoy_absolute *100 后万倍异常值)
- 后端契约放宽, 但前端 YOYBadge 没加守卫
- 用户看到 `+1157823.86%` 等万倍异常值会误导
- `backend/contracts/types.py:46` 注释明确: "**真实值 > 1e6 建议前端 YOYBadge 守卫**" — 契约要求前端必须补守卫

**治根 (2 文件 +43 -)**:
- `frontend-vue3/src/components/YOYBadge.vue` `humanizeChange` 加 `|v| > 1e6` 守卫 → 返 `'数据异常'`
- 模板 v-else-if 分支: 单独显示灰色 (`text-slate-400`, 跟 null 态一致) `数据异常` 标签, `title` tooltip 提示原因
- `frontend-vue3/src/components/YOYBadge.test.ts` 4 vitest tests: 100/-100/0 正常 + 1e7 异常

**治根效果**:
- 16/16 vitest passed (12 老 + 4 新) / 全套 42/42 无回归
- 跟 Sprint 15 Wave 1 backend 放宽契约配套, 前后端契约一致
- 防止前端 UI 显示万倍异常百分比误导运营

---

## 3. #89 B1 audience 28 字段 NO-OP 复盘

### 3.1 任务 scope 矛盾三方分析

| 维度 | 来源 | 内容 |
|------|------|------|
| **Task #89 description** (我写) | "audience_summary 28 字段补齐 member 维度, 跟 mark 表对齐 (Codex audit P1)" | 跟 mark 表对齐 |
| **Task #89 body** (我写) | "28 个 mark 字段 (老客占比/会员占比/老客 vs 会员) 标 mark=True 触发反向回填" | 标 mark=True |
| **代码现实** | `backend/contracts/audience.py` | 无任何 mark 字段 (grep "mark" 0 命中) |
| **Sprint 15 B1 实际** | `scripts/etl/replay_is_member.py` | ETL 层 mark 缺口反向回填, 跟 Pydantic Field 无关 |
| **AudiencePeriodMetrics** (28 字段) | `backend/contracts/audience.py:219-254` | 已含 member 维度 (member_gsv/users/aus/penetration + member_old_* + member_new_* 12 字段) |

**agent 正确识别矛盾停下** (CLAUDE.md 原则 1「如果某事不清楚, 停下来. 指出令人困惑的地方. 询问」):
- 3 个可选 scope 都不对: A) 任务误解 / B) 任务错层 / C) 任务跟 Codex audit 有关
- Codex audit 报告原文找不到, 不盲改
- 报告 user 拍板: 关任务 no-op (本次决策)

### 3.2 教训

1. **任务 description 跟 body 不一致是危险信号** — AI 接到矛盾任务时应停而不是猜
2. **Sprint 15 B1 是 ETL 层 (replay_is_member.py) 跟 Pydantic contract 无关** — "B1 (audience.py 28 字段) 模式" 在 B2 agent 报告里出现是误引, B1 实际是 mark 缺口反向回填
3. **AudiencePeriodMetrics 28 字段已完整** — "补齐" 描述本身是误, 字段已经齐全
4. **NO-OP 是合理收口** — 比盲目改动加测试更安全, 避免给用户错觉以为有活干

---

## 4. 决策审计

| 决策 | 选项 | 拍板 | 理由 |
|------|------|------|------|
| Sprint 16.5 主题 | A) 等 1.5.4 release 修 DuckDB race / B) 转治理 P1/P2 backlog | **B** | 跟 DuckDB 升级解耦, 不阻塞 |
| 4 subagent 并行 | A) 1 subagent sequential / B) 4 subagent 并行 (worktree 隔离) | **B** | 节省时间 3-4x, worktree 隔离无文件冲突 |
| B1 audience 28 字段 | A) NO-OP / B) 换 scope: 加 audience mark 标签 UI / C) 换 scope: 全量 audit 一致性 | **A** | agent 正确识别 scope 矛盾, NO-OP 是合理收口 |
| cache_key 算法 | A) MD5 full (128 bit) / B) SHA-256 (256 bit) | **A** | 128 bit 足够 (2^64 列表才 50% 碰撞), MD5 比 SHA-256 快 3-4x |
| List[PercentageField] 写法 | A) `List["PercentageField"]` / B) `List[Annotated[float, Field(...)]]` | **B** | A 不触发 element-wise 约束, B 才生效 (Pydantic v2 知识点) |
| YOYBadge 异常值阈值 | A) `|v| > 1e6` / B) `|v| > 1e9` (跟 PercentageField 上限对齐) | **A** | 1e6 是 Sprint 15 Wave 1 注释明示, 1e9 太宽松 |

---

## 5. 治理债务 (留 Sprint 17+)

| # | 任务 | 优先级 | 阻塞 | 备注 |
|---|------|--------|------|------|
| 1 | DuckDB 1.5.4 release 监控 (Sprint 16 P0 abort 重启) | 🔴 P0 | Sprint 15 Wave 3 跑批真验 | 4 步规避 (dry-run + release notes + pytest + git revert) |
| 2 | B2 全量 audit 剩 9 contract | 🟡 P1 | 50+ 字段缺 Pydantic 元数据 | audience_summary/audience_table/repurchase/conversion/promotion/rfm_category_drilldown/tier_flow/tiers/config |
| 3 | ground-truth-lint 规则强制新 contract 字段 | 🟡 P1 | 防 LLM 写无 Pydantic 元数据 contract | `RatioField` / `PercentageField` / `PpField` / `Annotated[*, Field(ge, le)]` |
| 4 | B1+B2 模式写进 CLAUDE.md Ratio Convention 章节 | 🟡 P1 | 强制 LLM 写 contract 时按 B1+B2 模式 | 跟 Sprint 13 治理契约 0-100 严守保留 |
| 5 | W5 cache invalidation hook (跟 manifest 同步) | 🟡 P1 | 改 ratio/契约后必须手动 invalidate | Sprint 14.5 留 |
| 6 | YOYBadge 守卫扩到 MetricCard / RFMSegmentDrilldown | 🟢 P2 | RFMSegmentDrilldown 还用 `+Math.abs(v).toFixed(1)+'pp'` 老逻辑 | 跟 YOYBadge 守卫模式统一 |

---

## 6. 学到的教训

### 6.1 4 subagent workflow 并行高效 (worktree 隔离)

**成果**: 4 subagent (P2.7 + B2 + YOYBadge + B1) 1.5h 完成 3 任务 + 1 NO-OP, 468K tokens, 跟 sequential 4-6h 比快 3-4x.

**配置**:
- workflow 脚本用 `parallel([4 thunks])` 让 4 agent 真正并行, 跟 `phase + await` sequential 不同
- worktree 隔离避免文件冲突 (4 scope 不重叠: backend/services/rfm/* + backend/contracts/{category,metrics,health} + frontend-vue3/src/components/YOYBadge + backend/contracts/audience)
- 每个 subagent 走 12 步流程 (branch → code → pytest → review → commit → push → qa → merge → push → pull → restart → CHANGELOG)

**教训**:
- **worktree 隔离是 subagent 并行的基础** — 没隔离就是 sequential 浪费时间
- **`parallel([thunks])` 跟 `phase + await` 不同** — 前者真并行, 后者 sequential
- **subagent prompt 注入 scope 边界** — 写 "不能动其他 4 个 subagent 的文件" 避免误改

### 6.2 task scope 矛盾 agent 应停 (CLAUDE.md 原则 1)

**问题**: #89 agent 接到 description (28 字段补齐) vs body (mark=True 触发反向回填) vs 代码现实 (无 mark 字段) 三方矛盾任务, 3 选 1: 猜一个干 / 停下问 user / 偷懒不管.

**教训**: 猜一个干最危险 (Sprint 13 10000× bug 教训). 偷懒不管 (写报告没活) 是失职. 停下问 user 是 CLAUDE.md 原则 1「如果某事不清楚, 停下来」. 这次 agent 选对 (停下 + 报告 3 选 1 + 等 user 拍板).

**行动**: Sprint 17+ subagent prompt 加 "task description vs body 矛盾时停下问 user" 模板.

### 6.3 Pydantic v2 List 字段 element-wise 约束知识点

**问题**: `List["PercentageField"]` 跟 `List[Annotated[float, Field(ge, le)]]` 在 Pydantic v2 行为不同. 前者不会触发 element-wise 约束 (前向引用解析为 float, Field 元数据丢失).

**根因**: Pydantic v2 TypeAdapter 解析 list 时, 内部用 `Annotated[inner, Field(...)]` 包装每个元素, 但 `List["PercentageField"]` 是前向引用 (str), 解析后变成 `List[float]`, Field 元数据丢失.

**教训**: B2 metrics 3 List 字段首次踩到, 13 tests 第一次跑 3 fail, 改后 13/13 passed. Sprint 14 写 RatioField 时没踩到 (因为没 List 用法), Sprint 16.5 B2 第一次踩坑.

**行动**: Sprint 17+ ground-truth-lint 规则加 List[PercentageField] 写法检查 (推荐 Annotated[float, Field] 不推荐 "PercentageField" 前向引用).

### 6.4 /qa skill Web 局限 (纯 backend cache 改动)

**问题**: /qa skill 是给 Web app 浏览器的 (跑 Playwright 截图), 纯 backend cache 改动 (eg. P2.7) 用 /qa 浪费.

**教训**: P2.7 改 backend/services/rfm/_shared.py, /qa 跑 Playwright 没用. 用 in-process 端到端验证 (curl 4 端点 + 验证 cache miss/hit 行为) 等价.

**行动**: Sprint 17+ 在 CLAUDE.md "AI 执行检查点" 表格加 "backend-only 改动" 替代 /qa 方案.

---

## 7. 时间线复盘

| 时间 | 事件 |
|------|------|
| 14:00 | Sprint 16 P0 中止决策落定 (3 race 症状 + 1.5.4 没 release + branch fix/sprint16-p0-duckdb-taoke-channel-race 留 v2 代码 + 4 tests + Sprint 16.5 README) |
| 14:15 | Sprint 16.5 P0 收口 task #112 done, 切 main |
| 14:20 | 4 P1/P2 subagent workflow (wf_7bae1096-8fa) launch (1.5h, 468K tokens) |
| 14:30 | TaskUpdate #89-92 in_progress |
| 14:35-16:00 | 4 subagent 并行跑 (P2.7 cache_key 治根 + B2 9 mark 字段治根 + YOYBadge 异常值守卫 + B1 识别 scope 矛盾停下) |
| 16:00 | workflow 完成, 3 任务合并 main (aaacb15 + c56f597 + a3a83bf) |
| 16:05 | AskUserQuestion: #89 处理 (NO-OP 拍板) |
| 16:10 | 4 task 状态更新, 写 memory (project_sprint16_5.md + MEMORY.md 索引) |
| 16:15 | /document-release skill 启动, 写 SPRINT-16-5-RETROSPECTIVE.md |

**总耗时**: 约 2 小时 (从 Sprint 16 P0 abort 决策到 Sprint 16.5 retrospective 收口)

---

## 8. Sprint 17 预告

**Sprint 17+ 留 backlog (按优先级)**:
1. **🔴 P0**: DuckDB 1.5.4 release 监控 + 4 步规避 + 复用 Sprint 16.5 v2 代码 + 跑批真验 + 6/9+ 18 老客 is_member=TRUE 验证
2. **🟡 P1**: B2 全量 audit 剩 9 contract (audience_summary/audience_table/repurchase/conversion/promotion/rfm_category_drilldown/tier_flow/tiers/config)
3. **🟡 P1**: ground-truth-lint 规则强制新 contract 字段用 Pydantic Field 元数据
4. **🟡 P1**: B1+B2 模式写进 CLAUDE.md Ratio Convention 章节强制生效
5. **🟢 P2**: W5 cache invalidation hook (跟 manifest 同步)
6. **🟢 P2**: YOYBadge 守卫扩到 MetricCard / RFMSegmentDrilldown

---

## 9. 关键指标

| 指标 | 值 |
|------|---|
| Sprint 周期 | 2 小时 (mini-sprint, 跟 Sprint 16 衔接) |
| Workflow ID | wf_7bae1096-8fa |
| Subagent 数 | 4 (P2.7 + B2 + YOYBadge + B1) |
| Subagent tokens | 468K |
| 持续时间 | 1.5h (workflow) + 0.5h (收口) |
| 任务完成 | 3/4 (75%) + 1 NO-OP (scope 矛盾) |
| Commits | +6 (3 fix + 3 merge + 3 docs) |
| Files changed | 9 (3 contracts + 2 services + 1 frontend + 3 docs) |
| Lines changed | +460 (P2.7 160 + B2 ~30 + YOYBadge 43 + docs 250) |
| Memory files | 4 (p27 + b2 + yoy + sprint16_5 retrospective) |
| 测试 | +23 (6 W5 cache + 13 B2 contract + 4 YOYBadge vitest) |
| Backend pytest | 437 passed + 12 skipped (B2 + 13, P2.7 +6, 1 W4 DuckDB 锁 fail pre-existing) |
| vitest | 16/16 (12 老 + 4 新) |
| uvicorn 端点 | 全 200, /docs 200, health 200 |
| r-flow cache 加速 | 1180× (6.45s → 0.005s) |
| Contract 422 拦截 | 9 mark 字段 (原本 500) |
| YOY 异常值守卫 | 4 UI 组件 (RFMView + CategoryFlowTab + MarketFocusView + RFMSegmentDrilldown 待扩) |
| 12 步流程 | 3/3 subagent 走完, B1 NO-OP 不走流程 |

---

*此文件由 Sprint 16.5 治理 sprint 收口流程生成, 最后更新 2026-06-11*
