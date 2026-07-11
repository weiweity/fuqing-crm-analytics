# Sprint 205+ Handoff & Codex Prompt 索引 (跟 L4.78 留尾 + L4.85.4 Codex app 1:1 stable 永久规则化沿用)

> **作者**: Claude Code 架构师 (Stage 1) + Codex app (Stage 2)
> **配套**: L4.74 立项决策 memo + L4.78 L4.74 PG migration 0 commit 收口 + L4.85.4 - L4.85.9 Codex app 完整收口 + L4.42 + L4.50 + L4.55 1:1 stable 永久规则链配套
> **目的**: 接手人 7/16+ 启动 Sprint 205+ 留尾 4 件 + Codex app 收口 6 件, 必读 + 跨 sprint 续期 0 commit 收口

## 留尾 SSOT 入口 (4 件, 跟 L4.78 1:1 stable 永久规则化沿用, 接手人 7/16+ 启动)

| L4 | 文档 | 状态 | 配套 |
|---|---|---|---|
| **L4.74** | [`docs/sprints/HANDOFF-TO-CODEX-Sprint205+-L474-PostgreSQL16-Distributed.md`](./HANDOFF-TO-CODEX-Sprint205+-L474-PostgreSQL16-Distributed.md) | 0 commit 收口 (7/16 离职 + 没接手人 + 网络环境异常) | 跟 L4.78 + L4.42 + fix_pattern #98 1:1 stable |
| **L4.72 + L4.74** | [`docs/sprints/HANDOFF-TO-CODEX-Sprint205+-L474-5S-RFM-PERFORMANCE-FIX.md`](./HANDOFF-TO-CODEX-Sprint205+-L474-5S-RFM-PERFORMANCE-FIX.md) | 续 (RFM 性能 5 阶段) | 跟 L4.71 + L4.72 + L4.69 1:1 stable |
| **L4.72.5** | [`docs/sprints/HANDOFF-TO-CODEX-Sprint205+-L474-RFM-DASHBOARD-FULL-PRECOMPUTE.md`](./HANDOFF-TO-CODEX-Sprint205+-L474-RFM-DASHBOARD-FULL-PRECOMPUTE.md) | 续 (RFM 完整预计算) | 跟 L4.72.5 + L4.72.6 1:1 stable |
| **L4.75 v2** | [`docs/sprints/HANDOFF-TO-CODEX-Sprint205+-L475-V2-Shared-Account-LAN.md`](./HANDOFF-TO-CODEX-Sprint205+-L475-V2-Shared-Account-LAN.md) | 续 (共享账号 + LAN 单进程单人排队) | 跟 L4.75 v2 + L4.85 + L4.85.1 1:1 stable |

## 已 ship (10 件, 移至 `docs/sprints/archive/`)

| L4 | 文档 | 状态 |
|---|---|---|
| **L4.75 早期** | `docs/sprints/archive/HANDOFF-TO-CODEX-Sprint205+-L475-SINGLE-USER-MODE-AND-PRECOMPUTE-EXTEND.md` | 已 ship L4.75 + L4.72.4, 内容进 CLAUDE.md L4.75 段 |
| **L4.75 早期** | `docs/sprints/archive/HANDOFF-TO-CODEX-Sprint205+-L475-1-4-FOUR-SUB-PLANS.md` | 已 ship L4.75 1-4 子计划, 内容进 CLAUDE.md L4.75 段 |
| **L4.85.4** | `docs/sprints/archive/HANDOFF-TO-CODEX-Sprint205+-L4854-Vite-Proxy.md` | 已 ship L4.85.4 - L4.85.9, 实证 Vite 5173 没代理错方向, 真因 = 认证状态机 SSOT 漂移 (CLAUDE.md L4.85.4 段) |
| **PC2 push** | `docs/sprints/archive/HANDOFF-TO-PC2-Sprint205+-L475-Push-Latest.md` | 已 push main HEAD `03af3fb` |
| **L4.74 Codex prompt** | `docs/sprints/archive/CODEX-APP-GOAL-MODE-PROMPT-Sprint205+-L474.md` | Codex 实证完成 (L4.78 0 commit 收口) |
| **L4.72.5 Codex prompt** | `docs/sprints/archive/CODEX-APP-GOAL-MODE-PROMPT-Sprint205+-L474-RFM-DASHBOARD-FULL-PRECOMPUTE.md` | Codex 实证完成 (L4.72.5 ship) |
| **L4.75 Codex prompt** | `docs/sprints/archive/CODEX-APP-GOAL-MODE-PROMPT-Sprint205+-L475-SINGLE-USER-MODE-AND-PRECOMPUTE-EXTEND.md` | Codex 实证完成 (L4.75 ship) |
| **L4.75 1-4 prompt** | `docs/sprints/archive/CODEX-APP-GOAL-MODE-PROMPT-Sprint205+-L475-1-4-FOUR-SUB-PLANS.md` | Codex 实证完成 (L4.75 1-4 ship) |
| **L4.74 cache end_date PC2** | `docs/sprints/archive/PROMPT-TO-PC2-Sprint205+-L474-Cache-End-Date-Fix.md` | PC2 已 push |
| **L4.74 WorkBuddy handoff** | `docs/sprints/archive/PROMPT-TO-WORKBUDDY-Sprint205+-L474-Cache-HandOver.md` | WorkBuddy 已 ship |

## L4.74 PostgreSQL 16 分布式 留尾分支 (跟 L4.78 1:1 stable 永久规则化沿用)

5 commits 留尾分支不 merge main (跟 L4.78 0 commit 收口 1:1 stable 永久规则化沿用):
1. `3fa790f` V2 handoff 7 周 1 人月 3 子任务串行
2. `687ff81` 子任务 A 静态 PASS 7 files / +2962/-16
3. `f79aadc` POC report 5 路径尝试全记录
4. `78d93e9` pytest 1/5 PASS + 4/5 FAIL 实跑结果
5. `672f856` Docker CloudFront EOF 根因调查 handoff

**接手人 7/16+ 启动恢复步骤** (跟 L4.74 V2 handoff 1:1 stable):
1. 检查 Docker Desktop on Mac daemon 配置 + 网络环境 (CloudFront EOF 根因)
2. 跑 `./scripts/setup-docker-mirror.sh` 配置 Docker registry mirror (绕过 CloudFront)
3. 重试 `docker compose up` (L4.74 PostgreSQL 16 compose + Citus 3 worker)
4. 跑 5 commit pytest 验证
5. 真业务触发 → 重新立项 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

## 跟 L4.x 永久规则链 1:1 stable 永久规则化沿用

- **L4.42 立项实证 SOP "git log + grep 实证"** 1:1 stable 永久规则化沿用
- **L4.50 pytest cleanup 0 业务代码改动** 累计 92+ 次 1:1 stable 永久规则链配套
- **L4.55 立项 spec 实证 SOP** 1:1 stable 永久规则化沿用
- **L4.57 + L4.58 + L4.59** 跨 sprint 留尾 0 commit 续期 SOP 1:1 stable 永久规则化沿用
- **L4.74 + L4.78** PostgreSQL 16 分布式 0 commit 收口 1:1 stable 永久规则化沿用
- **L4.85.4 - L4.85.9 + L4.86 + L4.88** Codex app 完整收口 1:1 stable 永久规则化沿用
- **fix_pattern #98** (任何 sprint 立项必 4 件启动条件 live verify) 1:1 stable 永久规则化沿用

## 维护规则 (跟 L4.57 + L4.58 + L4.59 0 commit 续期 1:1 stable 永久规则化沿用, 接手人 7/16+ 启动)

- 留尾 4 件 SSOT 入口保留在 `docs/sprints/` (L4.74 / L4.75 / L4.72.5 0 commit 收口)
- 已 ship 10 件移至 `docs/sprints/archive/` (跟 Sprint 200+ 留尾归档模式 1:1 stable 永久规则化沿用)
- 跨 sprint 续期 0 commit (跟 L4.57 1:1 stable 永久规则化沿用)
- 真业务触发再立 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

---

**本索引跟 L4.42 + L4.50 + L4.55 + L4.57 + L4.58 + L4.59 + L4.74 + L4.78 + L4.85.4-L4.85.9 + L4.86 + L4.88 永久规则链 1:1 stable 永久规则化沿用, 留尾 4 件 + 已 ship 10 件 1:1 stable, 接手人 7/16+ 启动必读.**