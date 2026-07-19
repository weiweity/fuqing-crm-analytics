# 技术债台账 (Technical Debt Ledger)

> **唯一开放债短表**。历史叙事：[`history/TECH-DEBT-HISTORY.md`](history/TECH-DEBT-HISTORY.md)

**最后更新**: 2026-07-19 清理续  
**main 基线**: `origin/main`（#30–#35 + docs 分支）

---

## 开放债

| ID | 级 | 说明 | 触发 / 处理 |
|---|---|---|---|
| **#C7-deselect** | P2 | CI deselect C 类 7 条（sampling + W4）。SSOT：`scripts/ci/pytest_c_class_deselects.txt` | 业务改 W4/RFM 口径或「CI 合成 fixture」 |
| **#e2e-preexisting** | P2 | schema-only CI soft/skip 已合；有生产数据后再严跑 | 预发/本地 DuckDB 严跑 |
| **#scripts-ops** | P2 | `scripts/` 根 monitor 可归 `ops/` | 须同步 launchd/hooks，禁盲 mv |
| **#preflight-env** | P2 | 无独立预发；本地即生产 | 预发机 / 抽样库 |
| **#Admin-Upload-WITHDRAWN** | — | 产品路径收回 | **不默认重开** |
| **#L4.74-PG** | — | 0 commit 收口；见 architecture memo + GO-NO-GO | 启动条件 a/b/c 真触发 |

### 已闭环（文档债）

| ID | 结果 |
|---|---|
| **#STATUS-HISTORY** | STATUS 短表 + `history/STATUS-HISTORY.md` |
| **#CLAUDE-L4-sink** | L4.1–62 全文下沉 `docs/rules/L4-permanent-rules.md`；CLAUDE 仅硬门禁摘要（document-release 2026-07-19） |

### Sprint C deselect

| 类 | 状态 |
|---|---|
| A1 / A2 / B | ✅ 已恢复 CI |
| C 7 条 | 📋 见 #C7 |

Sprint C 过程 handoff 已删出树；deselect SSOT 以 `scripts/ci/pytest_c_class_deselects.txt` 为准（git 历史可恢复旧 handoff）。

### 契约

- 可合并：**lint + test**；e2e 不挡（`operating/team-workflow-v1.md`）
- 整洁：`operating/project-hygiene.md`
- deselect SSOT：仅 `scripts/ci/pytest_c_class_deselects.txt`

---

## 已收口指针

| 项 | 证据 |
|---|---|
| #30–#34 hooks/hygiene/TECH-DEBT/e2e gate | PR |
| #35 STATUS + e2e soft | PR |
| document-release + archive 二次精简（handoff/过程文出树） | `docs/workspace-organize-2026-07-19` |

---

## 维护

1. 新债加行；闭环移历史或「已闭环」  
2. 禁止顶部万字编年  
3. 过程文 → `sprints/archive/`，不进开放表  
