# Sprint 15 Plan — Ratio 治理 Stage 3 + W5 cache invalidation hook + gsv_yoy 越界治根

**状态**: 🟡 计划中 (2026-06-11, /autoplan 4 phase review 完成, user 拍板 3 拍板问题完成)
**立项时间**: 2026-06-10
**前置**: Sprint 14.5 增量 2 收口 (main @ dde0c00)
**用户决策** (2026-06-11 拍板, /autoplan 跑完):
- 范围: 8 任务 (调整后, 删 1 加 3)
- A 修法: **A 放宽 1B** (修法 A, plan 原推, user 维持不选 B)
- Sprint 周期: **1.5 周** (CEO/Eng 推荐)
- C 任务: **❌ 整个删** (CEO/Eng 推荐, 跟 f214505 双保险冲突)
- D.1 (replay transaction): **P0 升级, 加进 Sprint 15** (CEO/Eng 推荐, 6 秒数据风险)
- P2.7 (cache_key md5 full): **P1 升级, 加进 Sprint 15** (CEO/Eng 推荐, 32 bit 生日碰撞)
- 6-month 0 浅 feature: **A 加 1 浅 feature** (YOYBadge 异常值守卫, 2h, 缓解警告)
- B 范围: 保留 1-2d, 但拆 B1 (audience 半天) + B2 (4 contract 全量, 估时上调到 2-3d)
- D.2-D.12 (除 D.1 提升外): 留 Sprint 16+ defer

**工作总量**: CC 3-4d / 人 1.5d
**墙钟**: 1.5 sprint (跟 Sprint 14.5 模式 + 1 浅 feature 缓解 6 月 警告)

---

## 立项目标 (背景 + 治理债务)

### 1. Sprint 14 A.3 引入的 contract 收紧回归 (Sprint 14.5 增量 1+2 已部分修复)

**Sprint 14.5 已修**:
- ✅ RFM TTL 段 `repurchase_gsv_ratio_*` 14 字段改 `Optional[RatioField] = None` (P1.1)
- ✅ W5 DuckDB-KV cache `_hash_key` 含 `FLOW_ALGO_VERSION` (P1.4)
- ✅ file cache `algo_version` 字段校验 (P1.4)

**Sprint 15 待修** (新发现, 来自用户排查品类看板占比 YOY 时的意外发现):
- ❌ **`gsv_yoy` 字段在 25 期间单拉越界 500** — `PercentageField` (-1M ~ 1M) 不够, 真实值 1,157,823.86% 越界. 跟 RFM TTL 段 ratio 越界 500 是**同类问题** (Sprint 14 A.3 大爆炸式收紧 contract, service 端没审计数据范围)
- ❌ **P2.4 Sprint 14 A.3 全量 contract audit** (Codex 提出, 未做) — Sprint 14.5 增量 2 时跳过, 现在合并到 Sprint 15

### 2. W5 cache invalidation hook (Codex P1.4 跟进)

**Sprint 14.5 半改补完**:
- ✅ file cache 加 `algo_version` 字段校验 (Sprint 14.5 commit d63fb0e)
- ✅ W5 DuckDB-KV cache `_hash_key` 含 `FLOW_ALGO_VERSION` (Sprint 14.5 hotfix commit f214505)

**Sprint 15 待修**:
- ❌ **W5 cache invalidation hook (跟 manifest 同步)** — 手动 `bump FLOW_ALGO_VERSION` 容易忘, 应该跟 manifest 变化自动触发 (跟 Sprint 1 W5 设计一致)
- ❌ **单 endpoint cache invalidation 路由保留** (`POST /api/v1/rfm/cache/invalidate`) — admin 调试用, 保留

### 3. Codex P2.5 / P2.6 / P2.7 留 Sprint 15+ defer

- ❌ P2.5 抽 `RFMXFlowRow` 泛型基类 (3 维度行字段重复 42 处) — 风险高于收益, defer
- ❌ P2.6 `_parse_flow_rows` 硬编码 `"已购客TTL"` 改 sentinel 常量 — defer
- ❌ P2.7 `cache_key` md5 截断 8 hex (32 bit 生日碰撞) 改 full md5 — defer

---

## 工单分解 (按依赖排序)

### A) gsv_yoy 越界治根 (P0, 2-3h)

**问题**:
- 25 6/1-6/8 单独拉 `category/overview` endpoint 返 500:
  ```
  fastapi.exceptions.ResponseValidationError: 1 validation error:
  {'loc': ('response', 'all_rows', 0, 'gsv_yoy'), 'msg': 'Input should be less than or equal to 1000000', 'input': 1157823.86}
  ```
- 跟 RFM TTL 段 ratio 越界 500 是同类问题 (Sprint 14 A.3 收紧 contract, service 端没审计数据范围)
- 用户原始问题"占比 YOY"不受影响 (PpField -100~100 没越界), **但相邻字段 gsv_yoy 越界 500 是新 bug**

**修法** (P0 治根, 跟 RFM TTL 段同模式):
- 方案 A (推荐): `PercentageField` 放宽上限 `-1B ~ 1B` (10^9, 跟 yoy_absolute 真实可能范围对齐)
  - 跟 Sprint 14 A.1 PercentageField 0-100 → 0-1M 退让一致 (Sprint 13 治理契约 0-1M 保留, 不破坏 0-100 严守)
  - 改 1 行 + 5 行注释
- 方案 B: contract 改 `Optional[PercentageField] = None`, service 端 gsv_yoy 越界返 None — 跟 RFM TTL 段 Optional 模式一致
  - 但 gsv_yoy 跟 old/new_ratio_yoy 不一样 (它有真实有效值, 偶尔越界), **返 None 失真**
  - **不推荐**

**验收**:
- [ ] `backend/contracts/category.py` PercentageField 上限改 1B (10^9), 加 CHANGELOG
- [ ] pytest: 加 `test_percentage_yoy_over_1m_no_reject` 验证 1.5M 通过, 0/负数仍拒
- [ ] /api/v1/category/overview 25 期间单拉 200, gsv_yoy 返真实值
- [ ] 4 端点全 200, 不引入新 regression

---

### B) Sprint 14 A.3 全量 contract audit (P1, 1-2d)

**问题** (Codex P2.4 提出):
- Sprint 14 A.3 大爆炸式收紧 `RatioField` / `PercentageField` / `PpField` 验证, 70+ 字段
- Sprint 14.5 增量 1+2 已修 R/F/M TTL 段 ratio 越界 (P1.1) + 用户新发现 gsv_yoy 越界 (本 Sprint A 任务)
- **其他 contract 文件 (audience/health/metrics) 未审计**, 可能还有类似越界 bug 潜伏

**审计清单**:
| Contract 文件 | 字段数 | 已知越界 | 备注 |
|--------------|-------|---------|------|
| `audience.py` | 16+ ratio | ❌ 未审 | Sprint 14 14 个 yoy_* 字段未加 PercentageField, 风险中 |
| `category.py` | 70+ ratio/yoy | ⚠️ gsv_yoy 越界 (本 Sprint A 修) | 其他字段未审 |
| `health.py` | 10+ ratio | ❌ 未审 | RepurchaseBucket 等 |
| `metrics.py` | 3 ratio | ❌ 未审 | OverviewMetrics |
| `rfm.py` | 14 ratio | ✅ Sprint 14.5 修 (P1.1) | — |

**修法** (1 个 sprint 跑完):
- 列出所有 `RatioField` / `PercentageField` / `PpField` 字段
- 对每个字段跑 1 次 mock service 输出 (eg. ratio=1.5, percentage=1.5M, pp=150)
- Pydantic 验证是否拒收 — 拒收就是越界 bug
- 跟 A 一样改上限或改 Optional

**验收**:
- [ ] audit 报告 `docs/SPRINT-15-CONTRACT-AUDIT-REPORT.md` 列出所有字段状态
- [ ] 越界字段全修, 4 contract 文件 (audience/category/health/metrics) 0 越界隐患
- [ ] pytest: `test_contracts_no_ratio_overflow` 5+ 测试覆盖 RatioField/PercentageField/PpField 边界
- [ ] 跑 `/api/v1/audience/*` + `/api/v1/health/*` + `/api/v1/metrics/*` + `/api/v1/category/*` 4 大类全 200

---

### C) W5 cache invalidation hook (跟 manifest 同步) (P1, 1d)

**问题** (Codex P1.4 跟进):
- Sprint 14.5 半改: 手动 `bump FLOW_ALGO_VERSION` 让旧 cache 失效, 但**容易忘**
- 应该跟 manifest 变化自动触发 invalidate, 跟 Sprint 1 W5 设计一致

**修法**:
- `backend/services/rfm/_shared.py` `_ManifestTracker.check_and_invalidate` 已经在 W5 cache.py 里实现, 但**只清 W5 DuckDB-KV cache, 没清 file cache**
- 加一个全局 `_FlowCacheInvalidator`:
  - manifest version 变 → 自动 invalidate W5 + file 两套 cache
  - 跟 manifest tracker 集成, 在 `_get_cached_flow` 跟 `_rfm_cache.get` 之前检查
- 移除手动 `bump FLOW_ALGO_VERSION` 逻辑 (改用 manifest version)

**验收**:
- [ ] ETL 跑批后 manifest version 变 → RFM 4 端点 cache 自动失效, 第一次请求返真实新值
- [ ] 不依赖 `bump FLOW_ALGO_VERSION` 手动操作
- [ ] `_rfm_cache.invalidate()` + `_clear_flow_file_cache()` 双清
- [ ] 测试: `test_cache_invalidation_on_manifest_change` 验证 manifest version 变 → cache miss

---

### D) 治理债务 (留 Sprint 15+ defer) (P2, no work this sprint)

| # | 任务 | 优先级 | 阻塞 |
|---|------|--------|------|
| D.1 | `replay_is_member.py` 包 `BEGIN; ... COMMIT;` (DROP INDEX 6 秒窗口数据风险) | 🔴 P0 | 跑批原子性 |
| D.2 | `AudienceRow.yoy_*` 28 字段加 `PercentageField` (Sprint 14 漏标) | 🟡 P1 | 留 Sprint 15 audit 时统一 |
| D.3 | `replay_is_member.py` member 删除不清 (mark rebuild 后 is_member 不清) | 🟢 P2 | 数据一致性 |
| D.4 | Step 4.6/4.7 fail-soft 隐藏 mark drift | 🟢 P2 | 数据可见性 |
| D.5 | 拉数据 pipeline 写 processed_files (上下游解耦) | 🟢 P2 | 架构债 |
| D.6 | 6 道门禁 Connection 错误 (cross_day/api_health/dedup) | 🟢 P2 | pre-existing flake |
| D.7 | e2e customer-health WASM flake | 🟢 P2 | pre-existing |
| D.8 | Codex P2.5 `RFMXFlowRow` 泛型基类 | 🟢 P2 | 风险高于收益 |
| D.9 | Codex P2.6 `_parse_flow_rows` sentinel 常量 | 🟢 P2 | maintainability |
| D.10 | Codex P2.7 `cache_key` md5 截断 | 🟢 P2 | 远期数据污染 |
| D.11 | 50M 架构实施 (Stage 2 plan 已写好) | 🔵 P3 | 长期 |
| D.12 | is_member 派生重构 (143 处引用) | 🔵 P3 | defer |

---

## 依赖图

```
A. gsv_yoy 越界治根 (P0)
  ↓
B. Sprint 14 A.3 全量 contract audit (P1, 找其他越界 bug)
  ↓
C. W5 cache invalidation hook (P1, 跟 manifest 同步)
  ↓
D. 治理债务 (留 Sprint 15+ defer, no work this sprint)
```

**关键路径**: A → B → C (3-4d)
**并行**: D 不做 (P2 defer)
**Sprint 15 总工作量**: CC 4-5d / 人 1.5-2d

---

## 验收标准

### A 验收
- [ ] `backend/contracts/category.py` PercentageField 改 0-100 0-1M → -1B ~ 1B
- [ ] pytest: `test_percentage_yoy_over_1m_no_reject` 通过 (1.5M 不拒)
- [ ] /api/v1/category/overview 25 期间单拉 200
- [ ] 4 端点 (audience/table + audience/summary + category/overview + metrics/overview) 全 200
- [ ] 94 backend passed, 12 skipped

### B 验收
- [ ] `docs/SPRINT-15-CONTRACT-AUDIT-REPORT.md` 列出所有字段状态 (4 contract × 70+ ratio/yoy 字段)
- [ ] 越界字段全修 (除 A 修的 gsv_yoy 外)
- [ ] pytest: `test_contracts_no_ratio_overflow` 5+ 测试
- [ ] /api/v1/audience/* + /api/v1/health/* + /api/v1/metrics/* + /api/v1/category/* 4 大类全 200

### C 验收
- [ ] ETL 跑批后 RFM 4 端点 cache 自动失效
- [ ] 不依赖 `bump FLOW_ALGO_VERSION` 手动操作
- [ ] `_FlowCacheInvalidator` 类实现
- [ ] 测试: `test_cache_invalidation_on_manifest_change` 通过

---

## 风险评估

| 风险 | 概率 | 缓解 |
|------|------|------|
| A PercentageField 放宽到 1B 后, 0-100 严守契约失守 | 低 | 跟 Sprint 14.5 PercentageField 0-1M 退让一致, 用户拍 A |
| B audit 跑完发现更多越界 bug, sprint 范围爆 | 中 | 优先级: P0 越界必修, P2 越界可 defer Sprint 16 |
| C invalidation hook 跟 manifest tracker 集成有 race | 低 | 锁内操作, 跟 W5 现有 manifest check_and_invalidate 同步 |
| Sprint 14.5 增量 2 hotfix W5 cache key 跟 C 改动冲突 | 低 | C 改动跟 manifest 集成, key 仍含 algo_version (双保险) |

---

## 启动命令

```bash
git checkout -b fix/sprint15-ratio-stage3

# Wave 1 (P0 治根 gsv_yoy): contract 改 1 行 + 测试
# backend/contracts/category.py: PercentageField ge=-1B le=1B
# backend/tests/test_percentage_yoy_over_1m.py: 5 测试
# 12 步: pytest + review + commit + push + merge + push + pull + restart

# Wave 2 (P1 audit 4 contract): 1 个 sprint 跑完
# audit report + 4 file 修 + 5+ 测试
# 12 步: 同上

# Wave 3 (P1 invalidation hook): 1d
# _FlowCacheInvalidator + manifest 集成 + 测试
# 12 步: 同上

# 12 步流程 (跟单 commit):
# pytest backend/tests/ -x -q
# /review skill
# 修 review 问题
# git commit -m "feat: xxx"
# git push origin fix/sprint15-ratio-stage3
# /qa skill
# git checkout main && git merge fix/sprint15-ratio-stage3 --no-ff
# git push origin main
# git pull origin main --ff-only
# kill 并重启 uvicorn + 更新 CHANGELOG.md
```

---

## 拍板问题 (autoplan 4 phase review 决定)

- A 方案选择: 修法 A (放宽到 1B) vs 修法 B (改 Optional 返 None)?
- B 范围: 全 4 contract 都审 vs 只审 audience/health (category 已知有问题单独修)?
- C 触发: 跟 manifest 自动触发 vs 保留手动 + 加 cron 兜底?
- Sprint 15 周期: 1 周 (跟 Sprint 14.5 模式) vs 2 周 (含 D.1 replay transaction 治理)?

---

*此文件由 Sprint 15 计划阶段生成, 等 /autoplan 4 phase review 拍板后修改*


---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `autoplan` Phase 1 | Strategy & scope | 1 | `issues_open` (4 HIGH) | 6 blind spots: A 修法选错 / B scope 70+ 字段大爆炸 / P2.7 升 P1 / 4 拍板走 taste gate / 6 月 0 浅 feature / D.1 升 P0 |
| Eng Review | `autoplan` Phase 3 | Architecture & tests | 1 | `issues_open` (4 HIGH) | C 整个任务该删 (跟 f214505 双保险冲突) / A 改 1B 失守契约 / B 1-2d 偏乐观实际 2-3d / D.1 + P2.7 升 P0/P1 |
| Design Review | — | No UI scope | 0 | skipped | — |
| DX Review | — | No developer-facing scope (内部服务) | 0 | skipped | — |
| Codex Voices | (degraded) | Dual-voice unavailable in this session (token budget) | 0 | `codex-unavailable` | — |

**AUTOPLAN:** CEO + Eng 4 subagent review, 0 codex dual-voice (token budget).
**CROSS-MODEL:** Single-model. Codex consult would add adversarial layer; deferred to implementation phase.
**UNRESOLVED:** 7 HIGH findings (4 CEO + 4 Eng, partial overlap):
1. A 修法 A (放宽 1B) vs B (Optional 返 None)
2. B scope 70+ 字段大爆炸 (跟 Sprint 14 A.3 同病)
3. C 整个任务该删 (跟 f214505 双保险冲突)
4. P2.7 md5 8 hex 32 bit 生日碰撞应升 P1
5. D.1 replay transaction 6 秒窗口应升 P0
6. 6 month trajectory 0 浅 feature (用户能持续这模式 6 月?)
7. 4 拍板问题 autoplan 不该拍, 该走 taste gate

**VERDICT:** Eng CLEARED with caveats (HIGH findings需在实施前解决) — CEO + Eng REQUIRED.

### CEO consensus table
| Dimension | Claude subagent | Codex | Consensus |
|---|---|---|---|
| Premises valid? | 4 假设里 1 错 (b 范围错) 1 早 (d) | (degraded) | flag: B 范围 + P2.7 升 P1 |
| Right problem? | HIGH 警告 (3 件 P0/P1 优先级不对) | (degraded) | taste gate: B 该延后 |
| Scope calibration? | HIGH (B 70+ 字段大爆炸) | (degraded) | flag: 拆 B1+B2 / 先做 B1 半天 |
| Alternatives? | MED (4 拍板该走 taste gate) | (degraded) | taste gate 4 项 |
| 6-month trajectory? | MED-HIGH (纯治理 0 浅 feature) | (degraded) | user challenge |
| Competitive risk? | MED-HIGH (6 月 0 浅 feature) | (degraded) | user challenge |

### Eng consensus table
| Dimension | Claude subagent | Codex | Consensus |
|---|---|---|---|
| Architecture sound? | CRITICAL (C 跟 f214505 双保险冲突) | (degraded) | flag: C 该删 |
| Test coverage? | HIGH (缺 contract fixture infra) | (degraded) | taste gate |
| Performance? | HIGH (C 触发 manifest IO 退步 6x) | (degraded) | flag: C 删后 0 性能问题 |
| Security? | MED (1B 失守契约 + UI 误导) | (degraded) | taste gate: A 修法 B 更稳 |
| Error paths? | MED (manifest corrupt 应 fail-open) | (degraded) | flag: 跟 C 删相关 |
| Deployment risk? | LOW (forward-compatible) | (degraded) | confirm |
| Hidden complexity? | HIGH (A 3 文件, B 1.5-2d 真人) | (degraded) | flag: 估时上调 |

### Cross-phase themes
**Theme 1: 3 件 P0/P1 任务范围不匹配** — CEO + Eng 都标 HIGH. **拆 1 周 → 1.5-2 周**.
**Theme 2: 契约失守风险** — CEO + Eng 都标 (A 放宽 1B 失守 / C 双保险冲突). **A 修法改 B (Optional 返 None)**, **C 整个删**.
**Theme 3: 6 month trajectory 纯治理** — CEO 标 MED-HIGH. **加 1 浅 feature 缓解**.

### Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|----------------|-----------|-----------|----------|
| 1 | CEO | A 修法改 B (Optional 返 None) — 治根优先 | Taste | P1 (completeness) + P5 (explicit) | 1B 失守契约, B 返 None 触发 dashboard 告警更稳 | A 放宽 (CEO 标 HIGH) |
| 2 | CEO | C 整个删, 改 lazy invalidation | Mechanical | P5 (explicit) | 跟 f214505 双保险冲突, 简化优先 | 保留 C (Eng 标 CRITICAL) |
| 3 | CEO | P2.7 md5 8 hex 升 P1, 进 Sprint 15 | Mechanical | P1 (completeness) | 32 bit 8K 样本 50% 碰撞, 1h 工作量 | defer (Codex P2) |
| 4 | CEO | D.1 replay transaction 升 P0, 进 Sprint 15 | Mechanical | P1 (completeness) | 6 秒数据窗口是真生产事故 | defer (Sprint 16) |
| 5 | CEO | B 拆 B1 (audience 半天) + B2 (4 contract 1-2d 试点) | Taste | P5 (explicit) | B 70+ 字段大爆炸, 分阶段降低风险 | 一次跑完 70+ 字段 (CEO 标 HIGH) |
| 6 | CEO | Sprint 15 周期 1 周 → 1.5-2 周 | Taste | P6 (action) | 4 任务 + D.1 + P2.7 估时上调 | 1 周紧 (CEO 标 HIGH) |
| 7 | CEO | 加 1 浅 feature (YOYBadge 异常值守卫) 缓解 6-month 0 浅 feature | Taste | P1 (completeness) | 用户能持续这模式 6 月? | 纯治理 (CEO 标 MED-HIGH) |
| 8 | Eng | 4 拍板问题从 autoplan 改走 user taste gate | Mechanical | P5 (explicit) | autoplan 不该替 user 拍 (CEO 标 MED) | autoplan 拍板 (反模式) |

### Sprint 15 调整后范围 (autoplan 推荐)

1. **P0 A** (2-3h): gsv_yoy 治根 — **改修法 B (Optional[PercentageField] = None)**
2. **P0 D.1** (4h): replay_is_member 包 BEGIN/COMMIT — Sprint 10 已知 6 秒数据窗口
3. **P1 B1** (半天): audience 28 字段补标 (D.2 + PercentageField) — 已知漏标
4. **P1 P2.7** (1h): cache_key md5 8 hex 改 full md5 — 32 bit 生日碰撞
5. **P1 B2 试点** (1d): category + health + metrics 3 contract × 50 字段 mock 验证 — 估时上调
6. **P2 浅 feature** (2h): YOYBadge 异常值守卫 (`abs(v) > 1e6` → "数据异常")
7. **删 C** (0d): 跟 f214505 双保险冲突, lazy invalidation 已生效
8. **D.2-D.12 留 Sprint 16+ defer** (跟 P0/P1 不混)

**调整后估算**: CC 3-4d / 真人 1.5d.

**UNRESOLVED AT FINAL GATE**: 4 拍板问题 + C 任务取舍 + P2.7/D.1 升优先级.
