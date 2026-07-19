# 技术债台账 (Technical Debt Ledger)

> **唯一开放债短表**。历史：[`history/TECH-DEBT-HISTORY.md`](history/TECH-DEBT-HISTORY.md)

**最后更新**: 2026-07-19 项目治理收口  
**main 基线**: `git rev-parse origin/main`

---

## 开放债（仅「有触发才立」的延期项）

| ID | 级 | 说明 | **触发条件**（未触发 = 不立项） |
|---|---|---|---|
| **#C7-deselect** | P2 | CI 仍 deselect C 类 7 条 | 业务改 W4/RFM 预计算口径，**或**交付「CI 合成 fixture」 |
| **#preflight-env** | P2 | 无独立预发 | 有预发机 **或** 抽样 DuckDB 方案获批 |
| **#L4.74-PG** | — | PG/分布式 0 commit 收口 | 启动条件 a/b/c 任一真触发（见 architecture memo） |

> 上表 **不是**「待办清单」；无触发条件命中时 **零未规划债**。  
> SSOT deselect：`scripts/ci/pytest_c_class_deselects.txt`

---

## 本目标已闭环

| ID | 结果 |
|---|---|
| **#STATUS-HISTORY** | STATUS 短表 + history |
| **#CLAUDE-L4-sink** | L4 → `docs/rules/` |
| **#scripts-ops** | monitors → `scripts/ops/` + launchd 路径同步 |
| **#Admin-Upload-WITHDRAWN** | 产品面删除（router/service/view/e2e/test）；**不重开** |
| **#e2e-data** | 夹具能力保留（`FQ_CRM_TEST_MODE` + seed）；**PR 门禁已撤回**（2026-07-19 分层：可选 `e2e-smoke.yml`） |

---

## 工作流契约

- **可合并**: **lint + test 必绿**（e2e **不**挡 PR merge；`docs/operating/team-workflow-v1.md`）
- **可选 UI smoke**: `.github/workflows/e2e-smoke.yml`（`workflow_dispatch` + 工作日 schedule；`requirements-e2e.txt` + login 壳层）
- **整洁**: `docs/operating/project-hygiene.md`
- **运维监控入口**: `scripts/ops/` + `scripts/launchd/`

## 维护

1. 新债必须有触发条件或立即排期；禁止「以后再清」空行  
2. 长编年只进 `history/`  
3. 撤回功能优先删代码，不留死路由  
