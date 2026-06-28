# Sprint 历史索引

> Sprint 1-104 详细索引 (本表) + Sprint 105-143 1 行指针 (`MEMORY.md` 索引) 减少冷启动 token。
> 
> **最后更新**: 2026-06-28 (Sprint 150 P2 a11y wrapper 闭环最后 0.5 分 (5 section aria-labelledby, plan-design-review 9.5/10 → 10/10 完整闭环) + Sprint 151 CHANGELOG.md append Sprint 145-150 entry (1 file / +15) + Sprint 152 0 业务代码 sprint 暂收口 (0 commit, 跟 Sprint 89/134 模式 stable) + Sprint 153 head: /document-release 累计 7 次真治本 (跟 Sprint 65/135/138/141.5/145/149 模式 stable, 4 文档 head 1:1 swap). 累计 72→76 sprint 0 debt 持续 + pytest 803 passed / 23 skipped / 0 failed + main HEAD `6904d36` + VERSION 0.4.14.157 不 bump 累计 44 sprint + 跟 Sprint 144 + 145 + 149 /document-release 模式 stable 累计 7 次真治本)

## 索引规则

- **内存指针** (一文件一行): `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint{N}_close.md`
- **CHANGELOG** (近 30 entry): 项目根 `CHANGELOG.md`
- **历史归档** (老 entry): `CHANGELOG_HISTORY.md`

## Sprint 索引 (按版本号倒序)

| Sprint | 版本 | 主要内容 | Memory |
|--------|------|----------|--------|
| **143** | v0.4.14.157 | 1 真业务 (改名 ROI→正装转化分析, Q10 推荐 A 仅前端文案 0 breaking change) + 2 全新建 (LTV 90/180/365d + cohort retention matrix + CohortRetentionMatrix.vue 热力图) + 3 个 merge conflicts 解决 (CHANGELOG 双 entry + types 用 Sprint 143 版本) + 跟 Sprint 142 并行 0 冲突区 + race flake L5.1 接受 | ✅ |
| **142** | v0.4.14.157 | 真 refactor + 1 真业务: RFM 扩展 (lifecycle_stage + value_tier + potential_tier 3 新维度, 不替换 8 quadrant) + level 联动 summary 卡二级聚合 (`SamplingLevelSummary` + `summary_by_level`) + `_compute_lock_metrics` 单 SQL 合并 (micro-benchmark 1.513x, Q5 阈值降级 ≥1.5x, 实质收益 26ms/call -33%) + 2 个 Codex 主动越界修复保留 (race flake + .githooks compat) | ✅ |
| **141.5** | v0.4.14.157 | Phase 1: ETL sample_received_at 字段 schema 准备 (6 files / +925/-7, COALESCE 回退 pay_time, Phase 1 全 NULL 等业务侧补数据源) + Q1 已验 (source data = CSV 不是 xlsx, 30 字段无 receive_time, GIFT_SAMPLE_DB = "赠品&0.01渠道"). Q2 + Phase 2 暂收口 (user 拍板"不需要", 跟 Sprint 144+/145+ 一同暂收口) | ✅ |
| **141** | v0.4.14.157 | 留尾治理 sprint: period_distribution 61-90d 静默丢失治本 + sync-agents.sh P2 修 + 12 files / +941/-39 + pytest 740/23/0 baseline | ✅ |
| **140** | v0.4.14.157 | 派样 ROI 自由窗口 1-90 天 + level 联动视觉强化 + contract 瘦身 + 2 ground-truth-lint 钩子 + pytest 738/23/0 baseline | ✅ |
| **139** | v0.4.14.157 | 派样人群正装转化漏斗 (get_sampling_roi 加 spu_type='正装' 拆分 + 回购周期分布 5 桶 + DQM warnings) | ✅ |
| **104** | v0.4.14.157 | 删 `/visitor` 路由别名 — 留尾治理 sprint 真业务必修 + /investigate + workflow 3 视角审查 3/3 agree (8.67/10) + 3 文件 -25 行纯删除 + 推翻 Sprint 52 commit 50eb241 拍板 + 后端 `/api/v1/visitor/*` 100% 保留 (AudienceView 末尾访客段仍调, #12 误判撤掉) + 3 次 amend (跟 Sprint 100+101+102+103 模式一致) + **L4.22 永久规则** (前端 sprint 收口必 rebuild dist + restart vite preview + activate core.hooksPath) + 3 实战补 (Step 12.5 rebuild dist + Step 12.6 L4.22 amend + Step 12.7 #12 误判撤掉) | ✅ |
| **101** | v0.4.14.157 | 全部收尾 sprint — L4.21 反 sprint 自我反馈闭环永久规则 + 跨文档一致性 100% PASS + Codex 主动扩展 5 项亮点 (CLAUDE.md 版本状态 + CHANGELOG.md 修复 Sprint 100 排序漂移 + STATUS.md 多字段 + TECH-DEBT.md 留尾总表 + L4.20 test 1 entry) | ✅ |
| **100** | v0.4.14.157 | L4.20 test 1 CI fresh checkout 必修 1 fail 治根 (1 commit 0 debt amend, 跟 Sprint 92.2 L4.9 实战 fix 模式真闭环 一致) | ✅ |
| **99** | v0.4.14.157 | 留尾 #11 SSOT 漂移闭环 + L4.20 反 SSOT 漂移永久规则 + check_ssot_drift.py 190 行结构化 ground-truth-lint | ✅ |
| **91** | v0.4.14.156 | 必修 4 闭环 (留尾治理 sprint 模式, 跟 Sprint 67+68 一致, 1 sprint 多范围, 1 commit 0 debt) | ✅ |
| **68** | v0.4.14.155 | Sprint 67+68 留尾 SSOT 治理 (L4.12 永久规则 + 4 follow-up gap 闭环, 1 commit amend 0 debt) | ✅ |
| **67** | v0.4.14.155 | Sprint 67 留尾 SSOT 治理 (跟 Sprint 68 amend 闭环) | ✅ |
| **66** | v0.4.14.155 | CI 维修 P0+P1 治根 (lint.yml FQ_DB_MODE 漏修跨 5+sprint 复发 + codex_clone_gc 平台检查从 gc_once 迁 main + L4.10 永久规则 + 5 regression test + pytest 741/21/0 Linux CI runner 实证 + CI 4/4 jobs 全绿) | ✅ |
| **65** | v0.4.14.154 | /document-release 总览文档漂移修正 (4 文件 +10/-10 行, 跨文档一致性 100% PASS) | ✅ |
| **64** | v0.4.14.154 | ruff-action v4→v3 revert + L4.9 永久规则 (1 文件 +1/-1 行) | ✅ |
| **63** | v0.4.14.153 | CI 维修 (lint E741 + e2e FQ_DB_MODE=schema_test + 5 unique action major 升级 Node 24) | ✅ |
| **62.5** | v0.4.14.152 | 4 项磁盘清理治根 (B1 backup retention + B2 giant file bypass cap + B3 /ad-hoc-query tmp_write_conn + B4 Codex clone GC LaunchAgent) | ✅ |
| **62** | v0.4.14.151 | /ad-hoc-query 3 子命令 + P3 uvicorn launchd 守护 | ✅ |
| **61** | v0.4.14.150 | docs(readme) sync Sprint 54-61 + fix(backend) uvicorn 启动 fail-fast + FQ_DB_MODE profile-aware | ✅ |
| **60+** | v0.4.14.147 | 5 sprint 累计 14 commit 0 debt (Sprint 60 + 60.1 + 60.1.1 + 60.2 + 61) | ✅ |
| **60** | v0.4.14.144 | params 顺序错位治本 (overview.py 2 行 + 2 case test) | ✅ |
| **59** | v0.4.14.143 | 收割季: STATUS 自动化 + CHANGELOG 按行数归档 + audit 措辞 SOP | ✅ |
| **58** | v0.4.14.142 | 工具链实战 fix 闭环 (#4 CI e2e 持久化 + #1 OOM 治本 + #2 commit-msg blocking) | ✅ |
| **57** | v0.4.14.141 | 文档沉淀主题 (LESSONS_LEARNED 9 pattern + 4 doc 扩内容 + asset_* 命名混淆) | ✅ |
| **56** | v0.4.14.140 | doc-only 5 phase (CHANGELOG 滚动 + 4 stub DRY + testing 链) | ✅ |
| **55.5** | v0.4.14.139 | docs 子目录化 + 命名重构 + 4 doc + (本任务) | (本次收口后) |
| **55** | v0.4.14.138 | CI 实战 fix 4 次 (HEALTH_API_KEY + F401 + getpath) | ✅ |
| **54** | v0.4.14.138 | L3 FilterBuilder 100% 闭环 (14/14 service) | ✅ |
| **53.5** | v0.4.14.138 | L3 churn.py 治本 | ✅ |
| **53** | v0.4.14.138 | race flake 真治本 (per-worker tmp DuckDB) | ✅ |
| **52** | v0.4.14.138 | visitor 路由激活 + 50m scale + commit-msg WARN | ✅ |
| **51** | v0.4.14.137 | DQ 监控 + e2e fixture + sampling timeout | ✅ |
| **50.1** | v0.4.14.136 | pre-commit L2 spec-lint hook 切换 | ✅ |
| **50** | v0.4.14.135 | L2 AST parser 升级 | ✅ |
| **43** | v0.4.14.134 | spec-lint blocking + e2e 11/11 + Codex 工作流启动 | ✅ |
| **42** | v0.4.14.132 | spec-lint 预防层 + CI 实战 fix 框架 | ✅ |
| **41** | v0.4.14.131 | CI 跑 e2e (12 follow-up 实战 fix) | ✅ |
| **40** | v0.4.14.130 | ground-truth audit | ✅ |
| **39** | v0.4.14.128 | GH Actions CI 修复 + visitor audit | ✅ |
| **38** | v0.4.14.125 | race flake 治标 + e2e advisory | ✅ |
| **37** | v0.4.14.125 | types.ts 重新生成 | ✅ |
| **36.5** | ... | B1+B2 contract audit | (见 CHANGELOG) |
| **35** | ... | 文档清理 (housekeeping) | (见 CHANGELOG) |
| **34.1** | ... | churn.py:418 f 前缀 + L1 SQL f-string lint | (见 CHANGELOG) |
| **34** | ... | Sprint 34 L2 AST + race flake | (见 CHANGELOG) |
| **33** | ... | vite build hook + e2e view smoke | (见 CHANGELOG) |
| **32.x** | ... | Playwright + Spec 修复 | (见 CHANGELOG) |
| **28-31** | ... | 备份 + ETL + 50m scale | (见 CHANGELOG) |
| **1-27** | ... | 早期奠基 | (见 CHANGELOG_HISTORY) |

## 维护规则

- **跨 sprint 留尾意识** (跟 Sprint 41 / 55 / 55.5 / 56 实战 fix 模式一致):
  - **重大改 doc 之前先 `git log --oneline -- <doc_path>` 看历史** (避免误删, Sprint 55.5 11 文件 mv + 19 路径引用教训)
  - **"未集成"/"不存在" 结论必须有 git log 实证** (CLAUDE.md §"强制验证" 规则)
  - **空白槽位 vs stub 内容选择**: 选 stub 内容而非空目录 (Sprint 55.5 4 stub 填 P0 死链接教训)
- **Sprint 索引自动维护**: 每次 sprint 收口必更新本表 + 顶部最后更新字段

## 关联文档

- `~/.claude/projects/-Users-hutou/memory/MEMORY.md` — 全局工作记忆索引
- `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_*.md` — Sprint 收口记忆
- `CHANGELOG.md` (近 30 entry 滚动)
- `CHANGELOG_HISTORY.md` (历史归档)