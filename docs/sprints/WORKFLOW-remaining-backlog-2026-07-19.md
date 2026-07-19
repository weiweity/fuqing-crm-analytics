# Workflow：剩余 backlog 收口（2026-07-19）

## 范围

处理「当前剩余任务」清单中可在 1 个 sprint 闭环的治理项；**不**重开 Admin Upload / L4.74 PG。

## 本分支交付

| 项 | 动作 |
|---|---|
| TECH-DEBT | 短表 SSOT；长文 → `docs/history/TECH-DEBT-HISTORY.md` |
| e2e 不挡 CI | `lint.yml` e2e job `continue-on-error: true` |
| pre-push | `.gitignore` / `VERSION` 等 `_SKIP_EXACT` → skip |
| team-workflow backlog | 更新完成态 |
| STATUS 快照表 | 对齐债路径 / e2e 策略 |
| C7 deselect | **保留**，登记 #C7-deselect |
| e2e 修稳 | **不修业务 spec**，登记 #e2e-preexisting |
| branch protection | 仓库未开启（API 404）；文档说明手设路径 |
| 预发 / CLAUDE 瘦身 / scripts ops | 仍开放债 P2 |

## 验证

- `pytest test_pre_push_smart_path + test_project_hygiene_ignore`
- classifier: `.gitignore VERSION STATUS.md docs/...` → `skip`
- 8000/5173 本机已监听（运维，非本 commit）
