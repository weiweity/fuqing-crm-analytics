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

## 维护规则

- 新 handoff 在 active sprint 期间放 `docs/sprints/` 根目录
- Sprint 收口并 merge 到 main 后，move 到本目录
- 不再修改归档内容；如需引用，用 `git show` 或查看原始文件
