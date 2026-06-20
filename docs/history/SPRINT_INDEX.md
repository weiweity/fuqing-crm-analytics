# Sprint 历史索引

> Sprint 1-55+ 索引, 高密度入口, 减少冷启动 token。

## 索引规则

- **内存指针** (一文件一行): `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint{N}_close.md`
- **CHANGELOG** (近 30 entry): 项目根 `CHANGELOG.md`
- **历史归档** (老 entry): `CHANGELOG_HISTORY.md`

## Sprint 索引 (按版本号倒序)

| Sprint | 版本 | 主要内容 | Memory |
|--------|------|----------|--------|
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

## 关联文档

- `~/.claude/projects/-Users-hutou/memory/MEMORY.md` — 全局工作记忆索引
- `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_*.md` — Sprint 收口记忆
- `CHANGELOG.md` (近 30 entry 滚动)
- `CHANGELOG_HISTORY.md` (历史归档)