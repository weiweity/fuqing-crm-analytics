# 技术债台账 (Technical Debt Ledger)

> **唯一开放债台账（短表）**。长编年与历史叙事见  
> [`docs/history/TECH-DEBT-HISTORY.md`](history/TECH-DEBT-HISTORY.md)（2026-07-19 从本文件迁出）。

**最后更新**: 2026-07-19（`fix/remaining-backlog-workflow-2026-07-19`）  
**main 基线**: `cb4a719`+（#30 Sprint C / #31 hooks SSOT / #32 pre-push finish / #33 hygiene）

---

## 开放债

| ID | 级 | 说明 | 触发再立 / 处理 |
|---|---|---|---|
| **#C7-deselect** | P2 | CI 仍 `--deselect` C 类 7 条（sampling 3 + W4 4）。SSOT：`scripts/ci/pytest_c_class_deselects.txt` | 业务改 W4/RFM 预计算口径，或立项「CI 合成 fixture」 |
| **#e2e-preexisting** | P1 | CI e2e 跨 sprint 预存红（sampling / category / L4.91 export 等）。**merge 默认不挡**（e2e job `continue-on-error` + team-workflow-v1） | 专开 e2e 修稳 sprint；修稳前 nightly 观察 |
| **#STATUS-HISTORY** | P2 | `STATUS.md` 正文仍保留长编年（顶部已有短表） | 全文截断迁 `docs/history/` 时再立 |
| **#CLAUDE-L4-sink** | P2 | CLAUDE.md 仍含 L4.1–62 巨型表；细则应只在 `docs/rules/` | 文档瘦身 sprint |
| **#scripts-ops** | P2 | `scripts/` 根上 monitor/session 脚本可归 `ops/` | 须同步 launchd/hooks 路径，禁止盲 mv |
| **#preflight-env** | P2 | 无独立预发环境；本地即生产限制多人并行 | 预发机 / 抽样库方案 |
| **#Admin-Upload-WITHDRAWN** | — | Admin Upload 产品路径已收回；WIP 仅 stash/archive 备份 | **不默认重开** |
| **#L4.74-PG** | — | PostgreSQL 16 分布式 0 commit 收口（环境/接手人条件 0 触发） | 启动条件 a/b/c 真触发再立 |

### Sprint C / L4.86 deselect（已合 main，C 类续期）

| 类 | 状态 |
|---|---|
| A1 9 条 | ✅ 恢复进 CI |
| A2 w2 2 条 | ✅ `isolated_read_db` 已合 |
| B 3 死 nodeid | ✅ 已清 deselect |
| C 7 条 | 📋 继续 deselect（上表 #C7） |

详见原 handoff：`docs/sprints/HANDOFF-SprintC-CI-deselect-2026-07-19.md`

### 当前 workflow 契约

- deselect：**仅** `scripts/ci/pytest_c_class_deselects.txt` → pre-push / lint.yml / nightly
- 可合并：**lint + test 必绿**；e2e 默认不挡（见 `docs/operating/team-workflow-v1.md`）
- 整洁：`docs/operating/project-hygiene.md`

---

## 已收口（近期指针，详情见 HISTORY）

| 项 | 证据 |
|---|---|
| Sprint C deselect cleanup | PR #30 / main |
| hooks SSOT + admin CI DuckDB | PR #31 |
| pre-push delete-skip + scoped | PR #32 |
| hygiene + team-workflow v1 | PR #33 |
| L4.91 Excel 等历史债 | `docs/history/TECH-DEBT-HISTORY.md` |

---

## 维护规则

1. Sprint 收口必 review 本文件：**新债加行，闭环移「已收口」**。  
2. 禁止再在本文件顶部堆「最后更新」万字编年。  
3. 长过程文 → `docs/sprints/archive/` 或 HISTORY，不进开放债表。
