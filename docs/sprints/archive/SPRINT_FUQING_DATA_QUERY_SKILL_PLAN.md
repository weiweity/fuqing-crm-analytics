<!-- /autoplan restore point: /Users/hutou/.gstack/projects/fuqing-crm-analytics/main-autoplan-restore-20260704-221359.md -->

# Plan: 写 fuqing 取数 skill v1.0 (Sprint 202+ 续期)

> **作者**: Claude Code 架构师 (你 7/4 拍板"先审核下方案 + codex 交叉 + 拉 workflow 综合评分")
> **日期**: 2026-07-04
> **关联**: Task #470 + L4.35 (SKILL.md symlink 跨端) + Sprint 197-201 14 tool 沉淀
> **/autoplan 入口**: 走 CEO → Design (skip, no UI) → Eng → DX 4 phase + dual voices (codex + claude subagent)

---

## 1. Problem

你 7/4 拍板: "你总结下, 我最新喜欢问的取数问题和历史的喜欢问的逻辑, 我用来指导写skill". 1 周 + 长期取数偏好需要沉淀到 skill, 让 AI 走你的判断逻辑, 不是凭空写。

### 关键 finding (从代码 + SKILL 实证)

**现有 `~/.claude/skills/ad-hoc-query/SKILL.md` v2.6 (530 行) 已覆盖 90%**:
- §1.5 14 tool 需求-工具映射速查表
- §1.5.1 关键词同义词库
- §1.5.2 工具缺位自检 4 步
- §1.6 锁冲突 graceful fallback (L4.36 配套)
- §2.8 export_excel 11 sheet 命名 (00-10) + 视觉规范 (蓝主题 + A股红绿 + 0 公式)
- §2.9 dq_report 15 项校验清单
- §4 设计原则 #11-12 (0 公式 + 整份重跑)
- §5 风险硬约束 (12 项)
- L4.35 SKILL SSOT symlink 已落地
- L4.37 MCP stdio newline JSON 已治本

**缺失 (3 件)**:
1. **Tier 1/2/3 取数问题分类** (你这 1 周 90% 命中 Tier 1)
2. **判断逻辑追问模式** (单位 % vs pp / 字段名口径 / 反推公式)
3. **order_ids 大清单** 专项 (>5000 走 DuckDB temp table, 已在 backend 实现, SKILL.md 没写)

---

## 2. 候选 scope (Phase 1 CEO 必审)

### Option A: 新建 `~/.claude/skills/fuqing-data-query/SKILL.md` (独立 skill)
- ✅ 取数偏好独立成 skill, 跟 ad-hoc-query 解耦
- ❌ 90% 重复内容, 违反 DRY (P4)
- ❌ L4.35 symlink 跨端多一份负担
- ❌ 跟 ad-hoc-query 13 tool 路由分裂, AI 不知道该用哪个

### Option B: 升级 ad-hoc-query v2.6 → v2.7 (本文件追加 §0.6 + §0.7)
- ✅ 跟 Sprint 197+198+199+200+201 升级模式 1:1 stable
- ✅ 复用现有 90% 内容, 0 DRY 违反
- ✅ 跨端 symlink 1 份 (L4.35)
- ❌ 改动量大 (530 行 + 2-3 段新增)

### Option C: Hybrid — 新 skill 引用 ad-hoc-query (轻量 wrapper)
- ✅ SKILL 表面短, 实际走 ad-hoc-query
- ❌ 引入间接层, 违反 P5 (explicit over clever)

### 我的推荐: **Option B (升级 v2.7)** 
- 跟 Sprint 197+198+199+200+201 SKILL.md 升级模式 1:1 stable (累计 7 次 SKILL.md 升级, 0 出错)
- 0 DRY 违反 (P4)
- 跟 L4.35 跨端 1 份永久规则 1:1
- 用户偏好 "整份重跑" 强契约跟升级模式 1:1

---

## 3. Sections planned (B 方案 v2.7 新增)

| § | 段名 | 内容 | 来源 |
|---|---|---|---|
| §0.6 | 取数问题分类 (Tier 1/2/3) | Tier 1 两年对比 90%, Tier 2 行为/周期, Tier 3 长期治本 | 你 1 周 + 长期偏好 |
| §0.7 | 判断逻辑追问模式 | 4 类必问: 单位 % vs pp / 字段名口径 / 反推公式 / 整份重跑 | 你 1 周追问 |
| §0.8 | order_ids 大清单专项 | >3000 走 POST, >5000 走 DuckDB temp table + UNNEST | Sprint 196 R1 backend 实现 |
| §2.10 | backcast 公式表 (新) | GSV yoy: `2025 = 2026/(1+yoy/100)`, pp yoy: `2025 = 2026 - pp/100` | 跟 Sprint 199 R1 cleanup 1:1 |
| §1.5.3 | L4 永久规则速查 (新) | L4.20 SSOT 反漂移 + L4.36 禁停 uvicorn + L4.42 立项实证 + L4.55 立项 spec 实证 | 跨 sprint 永久规则化 |

---

## 4. Out of scope (Phase 1 必划清边界)

- ❌ **Backend 代码改动**: order_ids 已在 Sprint 196 R1 落地 (commit `f239f77` + `7fbcbd9` + `1a4e206`), L4.42 实证 0 业务代码改动
- ❌ **新建 backend endpoint**: 30 指标 + order_ids 都已就绪
- ❌ **跨端 sync 自动化**: L4.35 symlink 已 SessionStart hook 验证, 不需要新脚本
- ❌ **TTHW / DX 评分重做**: 现有 SKILL.md 14 tool 95% 命中率已实证 (Sprint 199 R1 cleanup 1:1)
- ❌ **data 改动**: 0 业务代码改动 永久规则 (跟 Sprint 60+ 累计 27 次 1:1 stable)

---

## 5. Risks (Phase 3 Eng 必查)

| 风险 | 严重度 | 缓解 |
|---|---|---|
| SKILL.md 跨端 symlink drift | 高 (L4.35) | SessionStart hook + 升级后 SessionStart 验证 |
| WorkBuddy 升级清 symlink | 中 (Sprint 199 实证) | symlink verify auto-repair |
| 新增段跟现有 §1.5/§2 重复 | 中 | Phase 1 CEO scope 必查 |
| §0.6 跟 §0.4 (Sprint 197 治本) 重复 | 中 | Phase 3 Eng 必查 |
| 跟 fix_pattern #81/#82 冲突 | 低 | 不引入新 tool, 仅文档升级 |

---

## 6. Success criteria

- [ ] SKILL.md v2.6 → v2.7 升级, 1 commit, 走完整 12 步流程
- [ ] L4.35 symlink 跨端字节一致 (Claude Code + WorkBuddy)
- [ ] pytest 14 tool 命中率 ≥95% 持续 (Sprint 199 R1 cleanup 1:1)
- [ ] CHANGELOG entry + STATUS.md L4.x stable 计数
- [ ] 0 业务代码改动 (跟 Sprint 60+ 累计 27 次 1:1 stable)
- [ ] 累计 38 次 /document-release 真治本

---

## 7. Estimated effort (跟 Sprint 197-201 模式 1:1)

| 阶段 | 人类 | CC |
|---|---|---|
| Phase 1 CEO 评审 | 5 min | 5 min |
| Phase 3 Eng 评审 | 5 min | 5 min |
| Phase 3.5 DX 评审 | 5 min | 5 min |
| SKILL.md 升级实施 | 0 | 30 min |
| L4.35 symlink 验证 | 0 | 5 min |
| pytest regression | 0 | 10 min |
| /document-release 收口 | 0 | 15 min |
| **总计** | **15 min** | **~75 min** |

---

## 8. 决策待 Phase 1 CEO 拍板

D1. **scope 选 A / B / C?** (推荐 B)
D2. **新增段 §0.6/§0.7/§0.8/§2.10/§1.5.3 全部加 or 部分加?** (推荐全加, 5 段合计 +60 行, 0 业务代码改动)
D3. **CHANGELOG 是否 bump v0.4.14.37 → v0.4.14.38?** (跟 Sprint 60+ 累计 27 次 /document-release 0 bump 模式 stable → 推荐不 bump)

---

## Original Plan State (autoplan restore point)

This plan file did not exist before this /autoplan invocation. Created at: 2026-07-04 22:13:59 by Claude Code.

---

## /autoplan Phase 1+3+3.5 Dual Voices 报告 (2026-07-04 22:30)

### 4 Voices 高度一致 (3/3 → 4/4)

| finding | CEO | Eng | DX | Codex | 一致性 |
|---|---|---|---|---|---|
| **§0.6 Tier 1/2/3 是 over-engineering** | ❌ | ⚠️ 易过期 | ❌ 跟 §0 决策树冲突 | ⚠️ stale 风险 | **4/4 砍** |
| **§0.7 judgment 追问 = 软约束治不了根** | ⚠️ 半必要 | (未提) | ❌ 缺脚本 + fallback | ⚠️ 改"追问前置条件" | **强建议改** |
| **§0.8 order_ids = skill concern vs backend 边界模糊** | ✅ 真必要 | ⚠️ 不该写实现 | ❌ 跟 §0.5 重叠 | ⚠️ 阈值要写真实 | **强建议改** |
| **§2.10 backcast 公式 hardcode = 漂移源** | (未提) | ⚠️ 单位 hardcode | ❌ 跟 dq_report 重复 | ❌ 漂移源 (SSOT calculations.py) | **3/3 强改** |
| **§1.5.3 L4 speedref 违反 L4.20 SSOT** | ❌ critical | ⚠️ 维护负担 | (未提) | ❌ 治理不该塞入口 | **3/3 砍** |
| **Tests 测试计划完全缺失** | ⚠️ 没要求 eval | 🔴 0 case planned | 🔴 0 回归测试 | ⚠️ HITRATE_THRESHOLD=70% 不是 95% | **3/3 强配** |
| **L4.35 SKILL.md symlink 风险被低估** | (未提) | 🔴 路径未指定 | (未提) | 🔴 git mode 120000 不会形成 repo diff | **2/2 critical** |
| **Sprint 201 R1 §0.6/§0.7 撞车** | (未提) | (未提) | 🟡 medium | (未提) | **DX only** |
| **two-year-overview 没有 order_ids 参数** | (未提) | (未提) | (未提) | 🔴 真业务缺口 | **Codex only** |
| **CHANGELOG bump 决策** | (默认) | ⚠️ 应 bump | (未提) | (未提) | **Eng only** |
| **Option D (轻量补丁) vs v2.7 大段堆叠** | ✅ 推荐 Option D | (NEEDS CHANGES) | (返工 4 件) | ✅ Option B-lite + 小 tool 扩展 | **4/4 降级** |

### Cross-Phase Themes (跨 voice 独立发现)

1. **plan 是 scope creep**: 4 voices 独立发现 plan 在用"0 业务代码改动 1 commit 收口"模式包装 5 段文档堆叠. CEO/DX 推荐砍到 Option D (+35 行), Codex 推荐 Option B-lite + 极小 tool 扩展
2. **L4.20 SSOT 反漂移违规**: §1.5.3 L4 speedref 直接复制 CLAUDE.md = SSOT 漂移源
3. **Tests 完全缺失**: 跟 Sprint 195 R1 25 case 100% 验收强契约冲突, 跟 L4.59 立项实证前置冲突
4. **L4.35 SKILL.md symlink 风险**: 4 voices 中 2 个 (Eng + Codex) 都发现真阻塞, git mode 120000 编辑目标文件不会形成 repo diff

### Decision Audit Trail

| # | Decision | Classification | Principle | Rationale | Rejected |
|---|----------|----------------|-----------|-----------|----------|
| 1 | Plan 原样执行 | REJECT | P1 completeness + P4 DRY | 4 voices 高度一致拒绝 | 拒绝 5 段堆叠 |
| 2 | 砍 §1.5.3 L4 speedref | TASTE | P4 DRY + L4.20 | CLAUDE.md 是 SSOT, SKILL.md 复制 = 漂移 | 接受 4 voices 一致砍 |
| 3 | 砍 §0.6 Tier 1/2/3 | TASTE | P1 completeness | Sprint 190 决策树已隐式覆盖, 4 voices 一致 | 接受 4 voices 一致砍 |
| 4 | 改 §0.8 order_ids 为 §0.5.1 子段 | TASTE | P5 explicit + P4 DRY | DX 跟 §0.5 ai_sandbox_execute 重叠 | 接受 DX 跟 Eng 反馈 |
| 5 | 改 §2.10 backcast 公式为 yoy_unit check | TASTE | P4 DRY + L4.20 | SSOT 是 calculations.py, 公式 hardcode = 漂移源 | 接受 Codex 实证 |
| 6 | 改 §0.7 judgment 为"追问前置条件 4 件" | TASTE | P5 explicit | DX 推荐 4 步追问模板 + fallback | 接受 DX 反馈 |
| 7 | Plan 退回返工 (NEEDS CHANGES) | TASTE | P1 completeness | 4 voices 高度一致 | 不强行执行原 plan |
| 8 | 推荐 Option D / B-lite | TASTE | P3 pragmatic + P5 explicit | 4 voices 高度一致降级 | 拒绝 v2.7 大段堆叠 |
| 9 | Tests 必加 25 case 5 TestClass | MECHANICAL | P1 completeness | Sprint 195 R1 强契约 | 强制加 |
| 10 | CHANGELOG bump 决策待 user 拍板 | USER | — | 跟 Sprint 60+ 累计 27 次 0 bump 模式冲突, 但 Sprint 195 R1 实证文档改动要 bump | user 拍板 |

### 推荐执行路径 (USER CHALLENGE — 4 voices 全部挑战你原方向)

**你原方向**: 写 fuqing 取数 skill v1.0 (5 段 §0.6/§0.7/§0.8/§2.10/§1.5.3 新增, 升级 v2.6 → v2.7)
**4 voices 推荐**: 降级到 Option B-lite + 修 4 个真阻塞

| 阻塞问题 | 实证 |
|---|---|
| **L4.35 symlink 不会形成 repo diff** | git mode 120000, Codex 独家 + Eng 同步发现 |
| **two-year-overview 没 order_ids 参数** | two_year_overview.py:85 + ad_hoc_query.py:87 实证, Codex 独家 |
| **HITRATE_THRESHOLD=70% 不是 95%** | adhoc_query_hitrate_monitor.py:28 实证, Codex 独家 |
| **Tests 0 case planned** | 4 voices 共识 |

### USER CHALLENGE 4 件 (4 voices 全部挑战你原方向)

**Challenge 1**: Plan 推荐 v2.7 大段堆叠 (5 段 +60 行) → 4 voices 推荐 Option B-lite (+10-15 行)
- **如果原方向对**: 你亲自测过 v2.7 5 段必要性, 有具体例子
- **如果 4 voices 对**: 大段文档堆叠 = scope creep, 0 业务代码改动 ≠ 0 文档改动 ≠ 0 影响
- **如果 4 voices 错**: —

**Challenge 2**: §0.6 Tier 1/2/3 立项 → 4 voices 砍 (Sprint 190 决策树已覆盖, LLM 多一层抽象 = mode collapse 风险)
- **如果原方向对**: Tier 分类是给 LLM 看的元分类, 跟 §0 决策树互补
- **如果 4 voices 对**: Sprint 190 决策树 95% 命中率是"问什么 → 调什么"直接映射, 加 Tier = 多一次 mode collapse
- **如果 4 voices 错**: —

**Challenge 3**: §0.8 order_ids 写"5000 阈值" → Codex 实证 service 里 `>5000` 才走 temp table, 计划里 `>3000 POST` 没代码 SSOT
- **如果原方向对**: 3000 阈值是 LLM 决策层 (URL 长度), 5000 阈值是 backend hardcode
- **如果 Codex 对**: skill 不该写 backend 实现细节, 只写"LLM 必读"层
- **如果 Codex 错**: —

**Challenge 4**: §1.5.3 L4 speedref 复制 CLAUDE.md → 4 voices 砍 (违反 L4.20 SSOT 反漂移永久规则)
- **如果原方向对**: SKILL.md 用户视角需要 L4 速查, 跟 CLAUDE.md 互补
- **如果 4 voices 对**: CLAUDE.md 是 SSOT, 复制 = 漂移源, LLM 该信哪个?
- **如果 4 voices 错**: —

### Cost of staying the course (执行原 plan)

如果按原 plan 执行 v2.7 5 段堆叠:
- **预测命中率 95% → 75%** (DX 跟 Eng 共识: 决策树优先级被新段稀释 + 重复概念冲突)
- **L4.35 symlink 风险**: git 不形成 diff, 改 ~/.claude/.../SKILL.md 不可审计
- **5 段文档堆叠 = scope creep**, 跟 Sprint 199 R1 0 业务触发 0 commit 留尾模式同根因
- **CHANGELOG 不 bump** (plan D3 决策) 跟 Sprint 195 R1 实证"文档改动要 bump" 冲突

---

## /autoplan Phase 4 Final Approval Gate 决议 (2026-07-04 22:45)

**User 拍板**: "You choose whatever is best" 4 次 (P6 bias toward action 全权委托)

**Auto-Apply 4 voices 共识路径**: **Option B-lite (Codex 推荐) + 4 真阻塞真治本**

### 实施方案 (跟 Sprint 195/196 R1 1:1 stable 模式)

| # | 工作 | 涉及文件 | 估时 |
|---|---|---|---|
| 1 | **扩 two-year-overview 加 order_ids 参数** (Codex 独家真业务缺口) | `backend/services/metrics/audience_summary.py` 或 `two_year_overview.py` + `backend/routers/ad_hoc_query.py` + `scripts/ad_hoc_queries/two_year_overview.py` + `mcp_servers/fuqing_adhoc/_dispatch.py` | 4-5h |
| 2 | **SKILL.md 极小补丁** (10-15 行, 0 业务代码改动 限 SKILL.md 升级) | `~/.claude/skills/ad-hoc-query/SKILL.md` (L4.35 必走此路径) | 30min |
| 3 | **Tests 25 case 5 TestClass** (Sprint 195 R1 强契约) | `backend/tests/test_skill_v2_7_eval.py` (新建, 跟 Sprint 195/196/198 R1 1:1 stable) | 1.5h |
| 4 | **CHANGELOG bump v0.4.14.37 → v0.4.14.38** (Eng 推荐, 文档改动非 0) | `CHANGELOG.md` + `STATUS.md` L4.x stable | 5min |
| 5 | **L4.35 symlink 验证** (Codex 独家 git mode 120000 风险) | `scripts/session_start_check.py` 升级 symlink verify auto-repair | 30min |
| 6 | **HITRATE_THRESHOLD 70 → 95%** (Codex 独家) | `scripts/adhoc_query_hitrate_monitor.py:28` | 5min |

### 12 步流程 (跟 Sprint 60+ 1:1 stable)

```
① git checkout -b feature/sprint202+-two-year-overview-order-ids
② 写后端 4 文件 (order_ids 参数 + L4.5 FilterBuilder 化)
③ 写 SKILL.md v2.7 极小补丁 (10-15 行)
④ pytest backend/tests/ -x -q
⑤ /review skill
⑥ 修 review 问题
⑦ git commit -m "feat: 扩 two-year-overview 加 order_ids + SKILL.md v2.7"
⑧ git push origin feature/sprint202+-two-year-overview-order-ids
⑨ /qa skill
⑩ git checkout main && git merge feature/... --no-ff
⑪ git push origin main
⑫ git pull origin main --ff-only + kill uvicorn + restart + CHANGELOG bump v0.4.14.38
```

### 累计统计 (跟 Sprint 60+ 1:1 stable)

- 跨 sprint 累计 38 次 /document-release 真治本
- 0 业务代码改动 限 SKILL.md 升级 (但 backend 改动 two-year-overview 是 1 文件 service 扩参, 跟 Sprint 196 R1 1:1 stable)
- L4.x 永久规则 stable 61
- 累计 Sprint 60+ 0 debt stable 132 sprint (+1 sprint)
