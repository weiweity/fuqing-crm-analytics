# Sprint Close Memory 索引 (跟 Sprint 50+ dedup SOP 1:1)

> **SSOT**: Sprint 收口沉淀在 `~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint{N}_close.md` (用户 home 端专属, .gitignore 排除, 不入仓)
> **本文件作用**: 项目仓内单源指针, 让任何协作者 / Claude Code / WorkBuddy / CodeBuddy 跨机器访问时能找到 close memory 沉淀
> **沉淀机制**: Sprint 收口 12 步流程 §12 (kill + restart uvicorn + 4 文档 head swap) 后必写 close memory, append MEMORY.md 索引行 (L4.13 ≤24.4KB)

## Sprint 193-199 索引 (近期, 完整沉淀)

| Sprint | 文件 | 行数 | 关键节点 |
|---|---|---|---|
| 193 | `~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint193_close.md` | 155 | WorkBuddy 话术模板 + synthetic DuckDB fixture 治本 R1+R2 + L4.46 |
| 194 | `~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint194_close.md` | 149 | Sprint 188 B1 剩余 12 case synthetic fixture 治本 + WorkBuddy 话术模板 mock 预读反馈 + fix_pattern #80 |
| 195 | `~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint195_close.md` | 166 | 收敛方案 1 件事: AI 问数准确率 ≥95% + LLM 评估脚本 25 case + ask 路由表补全 + fix_pattern #81 |
| 196 | `~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint196_close.md` | 160 | Sprint 195 plan-eng-review B 治本: 立第 12 个 tool `fixed-product-list-compare` + L4.42 立项信息实证 1:1 + fix_pattern #82 |
| 197 | `~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint197_close.md` | 97 | 拍板 D 真治本: 立第 13 个 tool `fixed-product-list-compare-http` 走 HTTP API 0 直连 DuckDB 子进程 (L4.38 v3 文档化配套) |
| 198 | `~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint198_close.md` | 114 | 拍板选项 3 真治本: 立第 14 个 tool `ai-sandbox-execute` 走 sandbox backend service + audit log + SQL 注入防御 + 跟你"AI 命中不到 → 自行跑数"期望配套 |
| 199 | `~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint199_close.md` | 132 | R1 cleanup: workflow 9 agents 5 phase 排查 14 tool 真实命中率 ~40-65% + L4.35 critical violation 真治本 (.claude/skills/ad-hoc-query/SKILL.md symlink 9889 → 36405 bytes) + 4 uncommitted 改动合规收口 + 立 Sprint 199+ 3 P0 立项 |

## Sprint 192+ (早期, 索引见 MEMORY.md)

| Sprint | 详情 |
|---|---|
| 192 | 见 `~/.claude/projects/-Users-hutou/memory/MEMORY.md` Sprint 192 索引行 |

## Sprint 161-179 (8 sprint 完整沉淀, 1 行/索引)

`ls ~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint{161,162,163,164,165,166,168,169,170,171,172,173,174,175,176,176_1,176plus,177,177plus,178,179}*_close.md`

关键节点: 169/170/171 ad-hoc-query v2.0 升级 + R 6 桶 SSOT (跨 sprint 173/174 复用)

## Sprint 50-59 + 60-66 + 67-89 + 180-187 (合并段, 1 行指针)

`ls ~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint{50..187}*_close.md` (合并段, 见 `~/.claude/projects/-Users-hutou/memory/MEMORY.md` 索引行)

## Sprint 24-43 (早期, 1 行指针)

`ls ~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint{24,25,26,27,28,30,30_1,32,32_1,32_2,32_3,33,34_1,35,37,38,39,40_41,41,42,43}*_close.md`

## Sprint 205+ docs 整合归档 (跟 L4.20 SSOT 反漂移 + L4.59 跨 sprint 维护性 0 commit 续期 SOP 1:1 stable 永久规则化沿用, 2026-07-09 跟 L4.77 1:1 stable 永久规则化沿用)

L4.74 PostgreSQL 16 分布式项目 (留尾 7/16 后接手人启动) 的 16 个 working/template docs 从 `docs/sprints/` 移到 `docs/sprints/archive/`:

- 8 个 `HANDOFF-TO-CODEX-Sprint205+-L474-PostgreSQL16-Distributed-PART{2-9}.md` (~1109 行, 阶段 2-5 handoff)
- 8 个 `SPRINT-L474-STAGE-{1/2/3/5}-*.md` (~332 行, 模板: REQUIREMENT/SELECTION/BENCHMARK/SQL-COMPATIBILITY/CLUSTER-BENCHMARK/GO-NO-GO/POC-SUMMARY/RISK-ASSESSMENT)

主 HANDOFF doc `docs/sprints/HANDOFF-TO-CODEX-Sprint205+-L474-PostgreSQL16-Distributed.md` (PART1 概要 + 阶段 1) 保留在 `docs/sprints/` 作为 SSOT 入口. CODEX prompt docs (`CODEX-APP-GOAL-MODE-PROMPT-Sprint205+-L474.md` + `CODEX-APP-GOAL-MODE-PROMPT-Sprint205+-L475-SINGLE-USER-MODE-AND-PRECOMPUTE-EXTEND.md` + `HANDOFF-TO-CODEX-Sprint205+-L475-SINGLE-USER-MODE-AND-PRECOMPUTE-EXTEND.md`) 的 PART 引用已更新为 `archive/` paths (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用).

**0 业务代码改动累计 Sprint 60+ 82+ 次 1:1 stable 永久规则化沿用** (跟 L4.50 + L4.55 + L4.20 1:1 stable 永久规则链配套).

## 跨 sprint 留尾 (backlog)

- Sprint 199 R1: 业务组真人预读话术模板 (Sprint 195 R4 续, mock 预读待复核) + 跨 sprint 真因排查 (Sprint 192/193/195/196/197/198 R3 续, 持续) + 0 留尾业务债 (持续)

## Sprint 205+ L4.85-L4.88 永久规则化 17 层链收口 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用, 跟之前 1:1 stable 永久规则链配套, 7/11 Codex app 完整收口 + 跟你 7/16 离职 0.5-1 天闭环 1:1 stable 永久规则化沿用, 2026-07-11 跟 L4.88 1:1 stable 永久规则化沿用)

| Sprint 205+ | 文件 | 关键节点 |
|---|---|---|
| L4.85 | `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint205+_l4_85_login_request_approve_close.md` | 申请+同意 模式 4 endpoint (申请/查/同意/拒绝) + 复用 L4.84 _evict_previous_sessions_for_user 1:1 stable + 5 分钟超时 |
| L4.85.1 | `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint205+_l4_85_1_force_one_session_close.md` | admin 强制 1 人在线 + 申请强制弹窗 + 同意后 A 强制退出 + polling adaptive 5s/30s |
| L4.85.2 | `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint205+_l4_85_2_login_both_paths_close.md` | 整合 L4.84 + L4.85 path (auth.py login() 409 check + _is_account_active helper + LoginView catch 409 → handleApply) |
| L4.85.3 | `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint205+_l4_85_3_account_active_timeout_close.md` | _is_account_active last_active_at + 5min 检查 (跟 L4.75 v2 lock_timeout_seconds 1:1 stable 永久规则化沿用) |
| L4.85.4-L4.85.9 | `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint205+_l4_85_4_auth_handoff_close.md` + L4.85.5/6/7/8/9 | Codex app 完整收口: L4.85.4 认证状态机 SSOT 漂移 + L4.85.5 重查询 AbortSignal + L4.85.6 35GB 死机根因 + L4.85.7 缓存永远 miss + L4.85.8 看门狗假退出 + L4.85.9 生产密码明文 (.env 读取 + fail-fast) |
| L4.86 | `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint205+_l4_86_ci_burst_red_close.md` | CI 爆红 4/4 jobs 全绿治本 (.github/workflows/lint.yml test job FQ_CRM_PASSWORDS env) |
| L4.87 | (无 close memory, /investigate Phase 1-5 治本) | 自动弹窗治本 (NavBar.vue polling 不被 document.hidden 跳过 + visibilitychange 立即触发 + 30s → 10s) |
| L4.88 | `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint205+_l4_88_ci_pytest_race_close.md` | CI 爆红 pytest collection race condition 治本 (conftest.py autouse fixture 重置 env + reload VALID_CREDENTIALS) |
| L4.91 | `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint205+_l4_91_excel_export_ssot_close.md` | Excel 导出全量 semantic/contractual 治本 (8 件 bug + 24 视图审计 + kind enum 显式 SSOT) |
| L4.91.1 | (main HEAD `51dbde1` entry via CHANGELOG/STATUS) | market-focus#product-customer 对比行 Excel yoy 格式错治本 (formatValue per-row dispatch + ProductCustomerTab 14 列 WYSIWYG) |
| L4.91.2 | (main HEAD `4f64f9c` entry via CHANGELOG/STATUS) | ProductAssetsTab + OtherProductAssetsTab formatValue + test_helpers reset endpoint + 8 view kind enum 补齐 (34 列 total, 技术债 #1-#4 全部闭环) |

**0 业务代码改动累计 Sprint 60+ 97 次 1:1 stable 永久规则化沿用** (跟 L4.50 1:1 stable 永久规则链配套, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用). 跟你 7/16 离职 0.5-1 天闭环 1:1 stable 永久规则化沿用.

## Sprint 205+ docs 最终归档 (2026-07-12 7/16 离职前最终 doc cleanup)

L4.91 完整收口后最终 doc cleanup:
- **13 件已 ship handoff/investigation → archive/**: L4.85.7 bug1 handoff + L4.91.2 investigate + 4 Sprint205+ handoff + 2 verification index + 1 handoff prompt index + 1 architecture review + 1 dimension autoplan + 1 skill snapshot + 1 Trino benchmark
- **8 件 Codex prompt 纯 prompt → 删除**: CODEX-APP-GOAL-MODE-PROMPT (4) + CODEX-PROMPT-Sprint144 + HANDOFF-TO-PC2 + PROMPT-TO-PC2 + PROMPT-TO-WORKBUDDY
- **sprints/ 精简**: 12 文件 → 1 个索引文件 (_sprint-close-index.md)
- **architecture/ 精简**: 8 文件 → 6 文件 (移出 2 件 handoff/investigate)
- **archive 总计**: 75 件, 完整历史 reference

**0 业务代码改动累计 Sprint 60+ 97 次 1:1 stable 永久规则化沿用** (跟 L4.50 + L4.55 + L4.20 1:1 stable 永久规则链配套).

## 维护规则 (Sprint 收口 12 步流程 §12)

1. **git pull --ff-only origin main** (L4.7 配套)
2. **kill + restart uvicorn** (跟 L4.7 launchd 首选 python3 配套)
3. **写 `~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint{N}_close.md`** (~150 行, 含 0. 痛点真因 + 1. 实施 + 2. L4.x 配套 + 3. 累计统计 + 4. 跨 sprint 关联 + 5. 留尾 + 6. 沉淀 + 7. CI 期望 7 段)
4. **MEMORY.md 索引行 append** (L4.13 ≤24.4KB verify)
5. **本文件 `_sprint-close-index.md` Sprint 行 append** (新增行)