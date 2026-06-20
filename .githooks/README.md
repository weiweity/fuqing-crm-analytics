# .githooks — 项目级 Git Hooks

本目录存放项目级 git hooks,**不**依赖 `~/.git/hooks/`。所有开发者必须安装一次才能生效。

## 安装

```bash
git config core.hooksPath .githooks
```

`scripts/setup-hooks.sh` 也会做同样配置(同时提示当前状态)。

## Hook 清单

| Hook | 触发时机 | 主要职责 | 引入 Sprint |
|------|----------|----------|------------|
| `pre-commit` | `git commit` 前 | ruff lint + CHANGELOG 跟随校验 + 禁止 bare except + B2 import check + B5 test order lint + pytest cleanup orphans + P1-3 review ground-truth lint + Sprint 14 A.2 contracts 提醒 + Sprint 14 vue-tsc 真编译拦截 | Sprint 3 + Sprint 14 + Sprint 18 #142 |
| `commit-msg` | commit message 写入后 | message 提到的文件若 staged diff 删除原内容 >80% 且未说明删除/重构，输出 WARN（不阻断） | Sprint 52 #5b |
| `pre-push` | `git push` 前 | pytest 全套件 (backend/tests/) | Sprint 3 P1-3 |
| **`post-merge`** | `git merge` 完成后 (含 fast-forward + --no-ff) | 写 `.ship-audit.log` (merge 时间 + commit SHA),补 audit trail | **Meta-Sprint /ship 接入** (Sprint 19) |

## /ship audit trail 接入

`post-merge` 配合 CLAUDE.md "AI 执行检查点" 的 "sprint 收口" 检查点使用:

- 每次 `git merge --no-ff` 到 main, hook 自动追加一行到 `.ship-audit.log`
- 格式: `[2026-06-11T12:34:56Z] SHIPPED to main: <commit SHA> <commit subject>`
- 跨平台兼容 (macOS / Linux), 用 `date -u +"%Y-%m-%dT%H:%M:%SZ"`
- 仅在 main / master 触发, feature branch 跳过避免 noise

详细使用文档见 `docs/SHIP.md`。
