# Sprint Handoff 归档

> 历史 Codex handoff / prompt 文档归档目录。
> 规则：Sprint 收口完成后，一次性 handoff 文档从 `docs/sprints/` 根目录移入本目录，减少根目录噪音。

## Sprint 186+ 新规（HANDOFF-TO-CODEX 物理 rm）

- **Sprint 183 / 184** 的 `HANDOFF-TO-CODEX-Sprint183.md` / `Sprint184.md` **未归档**（根目录物理 rm）
- 真因：Sprint 183 / 184 handoff 内容已沉淀到 close memory file（`~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint{N}_close.md`），物理文件长期无价值
- 配套 `.gitignore` 规则：`HANDOFF-TO-CODEX-*.md`（Sprint 184 实战发现）
- 后续 Sprint handoff **推荐**（用户拍板）：
  1. 物理 rm（轻量，不再 archive）— 适用于"干货已沉淀到 close memory"场景
  2. archive 此目录（重溯场景，演练仍需 handoff 实体文件）
- **Sprint 186 起新规 = 默认走 #1 物理 rm**，仅在特殊需要时走 #2 archive

## 归档清单

| 文件 | Sprint | 说明 |
|---|---|---|
| `CODEX-PROMPT-Sprint144.md` | Sprint 144 | Codex prompt |
| `HANDOFF-TO-CODEX-Sprint139-Posize-Conversion.md` | Sprint 139 | Posize Conversion handoff |
| `HANDOFF-TO-CODEX-Sprint140-Flexible-Window-Level-Link.md` | Sprint 140 | Flexible Window Level Link handoff |
| `HANDOFF-TO-CODEX-Sprint141-Period-Distribution-Debt.md` | Sprint 141 | Period Distribution Debt handoff |
| `HANDOFF-TO-CODEX-Sprint141.5-Plus-Roadmap.md` | Sprint 141.5 | Plus Roadmap handoff |
| `HANDOFF-TO-CODEX-Sprint142-RFM-Level-Lock-Perf.md` | Sprint 142 | RFM Level Lock Perf handoff |
| `HANDOFF-TO-CODEX-Sprint143-LTV-Cohort-ROI-Rename.md` | Sprint 143 | LTV Cohort ROI Rename handoff |
| `HANDOFF-TO-CODEX-Sprint144-Sampling-Refactor.md` | Sprint 144 | Sampling Refactor handoff |
| `HANDOFF-TO-CODEX-Sprint158-Sample-Navbar-Refactor.md` | Sprint 158 | Sample Navbar Refactor handoff |
| `HANDOFF-TO-CODEX-Sprint159-Sampling-02-Logo-Favicon.md` | Sprint 159 | Sampling 02 Logo Favicon handoff |
| `HANDOFF-TO-CODEX-SprintN+1-ClickHouse-POC.md` | Sprint N+1 | ClickHouse POC 单节点 handoff (跟 L4.56 ClickHouse POC 留尾 SOP 1:1 stable 永久规则化沿用, Sprint N+5 No-Go 反转后归档) |
| `HANDOFF-TO-CODEX-SprintN+3-ClickHouse-POC-Trino-Cluster.md` | Sprint N+3 | ClickHouse POC Trino Cluster handoff (跟 L4.55 + L4.56 1:1 stable 永久规则化沿用, Sprint N+5 No-Go 反转后归档) |
| `HANDOFF-TO-CODEX-SprintN+4-ClickHouse-POC-DuckDB-Trino-ETL.md` | Sprint N+4 | ClickHouse POC DuckDB → Trino ETL handoff (跟 L4.54 + L4.55 + L4.56 1:1 stable 永久规则化沿用, Sprint N+5 No-Go 反转后归档) |
| `HANDOFF-SprintN+5-Stage-Architecture-Inputs.md` | Sprint N+5 | Sprint N+5 Go/No-Go 决策模板 (跟 L4.56 立项决策备忘录 SOP 1:1 stable 永久规则化沿用, No-Go 反转后归档) |
| `SPRINT_FUQING_DATA_QUERY_SKILL_PLAN.md` | Sprint 199+ | ad-hoc-query skill plan (跟 Sprint 199 收口 1:1 stable 永久规则化沿用) |
| `SPRINT205+_L442_VERIFICATION_L4724_L473_L474.md` | Sprint 205+ | L4.42 立项实证 3 件 0 commit 续期 (跟 L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 1:1 stable 永久规则化沿用) |
| `SPRINT205+_L442_VERIFICATION_L474_TRIGGERED.md` | Sprint 205+ | L4.74 启动条件 b+c 真触发重新立项 (跟 L4.42 立项实证 SOP "真业务触发" 1:1 stable 永久规则化沿用) |
| `SPRINT202+_R6_WALL_MIN_FINAL_VERIFICATION.md` | Sprint 202+ R6 | R6 wall_min 验证最终 (跟 L4.58 跑批 wall_min 验证 SOP 1:1 stable 永久规则化沿用) |
| `SPRINT202+_R7_DUCKDB_WAL_EPERM.md` | Sprint 202+ R7 | R7 DuckDB WAL EPERM 治本 (跟 L4.63 uvicorn 持锁 + DuckDB 异 config detector 1:1 stable 永久规则化沿用) |
| `SPRINT-N+5-NO-GO-DECISION-2026-07-06.md` | Sprint N+5 | No-Go 反转决策 (跟 system locked down + handoff advisory 1:1 stable 永久规则化沿用) |
| `SPRINT-N+5-GO-DECISION-2026-07-06.md` | Sprint N+5 | Go 拍板 (已反转 No-Go, 跟 L4.42 立项实证 SOP "凭印象 0 commit 收口" 反例 1:1 stable 永久规则化沿用) |
| `SPRINT-N-PLUS-WAVE1-CROSS-STABLE-2026-07-06.md` | Sprint N+ | Wave 1 跨 sprint plan (跟 L4.40 fail-open + L4.57 + L4.58 SOP 1:1 stable 永久规则化沿用) |
| `SPRINT-N+5-TRINO-POC-SUMMARY.md` | Sprint N+5 | Trino POC summary (跟 L4.56 立项决策备忘录 SOP 1:1 stable 永久规则化沿用, No-Go 反转后归档) |
| `SPRINT-N+1-DUCKDB-BASELINE-2026-07.md` | Sprint N+1 | W2 DuckDB 128GB baseline (跟 L4.68 DuckDB 性能调优 1:1 stable 永久规则化沿用) |
| `SPRINT-N+1-BUSINESS-INTERVIEW-REQUIREMENTS.md` | Sprint N+1 | 业务方访谈 PDF 需求文档 (跟 Wave 1 跨 sprint plan 1:1 stable 永久规则化沿用) |

## 维护规则

- 新 handoff 在 active sprint 期间放 `docs/sprints/` 根目录
- Sprint 收口并 merge 到 main 后，move 到本目录
- 不再修改归档内容；如需引用，用 `git show` 或查看原始文件
