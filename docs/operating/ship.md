# /ship 接入 12 步流程

> Meta-Sprint 治理收口: 把 `/ship` skill 接入项目 12 步流程,留 audit trail。
> 跟现有 pre-commit / pre-push hook 配合,补 "merge 后没记录" 的空缺。

---

## 背景

CLAUDE.md "AI 执行检查点" 列了 5 个 STOP 检查点: commit / push / merge / restart / contract 改字段。Sprint 1-18 retrospective 显示 sprint 收口总缺一步**显式 audit trail** —— merge 完没记录就过去了,后续复查 Sprint N 收了哪些 commit 必须翻 git log / Sprint-N-RETROSPECTIVE.md。

Meta-Sprint 决定:

1. **不强制跑 `/ship` skill 本身** (太重, 触发 telemetry / gstack 升级检查 / artifacts sync, 12 步流程里已经够忙)
2. **强制留 audit trail** —— 在 `post-merge` hook 里写 `.ship-audit.log`,append-only
3. **CLAUDE.md 检查点加 1 行** —— "sprint 收口" → "必跑 /ship skill (留 audit trail)"

效果: merge 到 main 后立即在 `.ship-audit.log` 看到一行 `[时间] SHIPPED to main: <SHA> <subject>`,可 `cat .ship-audit.log` 复核。

---

## /ship skill 位置

- 全局 skill: `~/.claude/skills/ship/SKILL.md` (gstack ship workflow)
- 备选: `~/.claude/skills/land-and-deploy/SKILL.md` (用于需配合部署的场景)

> 本次接入用 `post-merge` hook 替代手工跑 `/ship` —— 仅留 audit trail, 跳过 `/ship` 内部的 merge base / version bump / CHANGELOG / PR 创建等重型步骤,这些走 12 步流程手工做。

---

## 实施: post-merge hook

文件: `.githooks/post-merge` (chmod +x)

```bash
#!/usr/bin/env bash
set -euo pipefail
BRANCH=$(git rev-parse --abbrev-ref HEAD)
[ "$BRANCH" != "main" ] && [ "$BRANCH" != "master" ] && exit 0
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LAST_COMMIT=$(git log -1 --pretty=format:"%H %s")
printf "[%s] SHIPPED to %s: %s\n" "$TIMESTAMP" "$BRANCH" "$LAST_COMMIT" >> .ship-audit.log
```

激活: `git config core.hooksPath .githooks`

---

## 怎么 verify

合并 1 个 test branch 到 main 后:

```bash
cat .ship-audit.log
# 期望: 末尾追加一行, 时间 + branch + commit SHA
```

回归: `git revert <merge-commit>` 后 .ship-audit.log 仍保留该行(append-only, 留作历史)。

---

## 跟 Sprint 1-18 retrospective 关系

- **现状**: 18 个 sprint 收口 retrospective (`docs/SPRINT-*-RETROSPECTIVE.md`) 都有 commit SHA / merge commit 记录
- **缺**: 没有机器可读的 append-only audit log, 需要从 18 份 md 反推
- **本接入**: 未来 sprint 收口会自动追加到 `.ship-audit.log`, retrospective 写 commit SHA 时直接 `tail -1 .ship-audit.log` 拿
- **不补历史**: Sprint 1-18 不补 .ship-audit.log (避免混入手工补的数据)

---

## 跟 CLAUDE.md "AI 执行检查点" 配套

CLAUDE.md "AI 执行检查点" 表格加 1 行:

| 检查点 | 触发条件 | 必须执行 | 阻塞动作 |
|--------|----------|----------|----------|
| **sprint 收口** | merge --no-ff 到 main | 必跑 /ship skill (留 audit trail) | post-merge hook 未追加 .ship-audit.log → 视为 sprint 没收口 |

注: "必跑" 指 "必须让 post-merge hook 跑成功 (写入 .ship-audit.log)",不要求手工调 `/ship` skill。

---

## 失败模式 / FAQ

**Q: hook 没跑?** A: 1) 检查 `git config core.hooksPath` 输出是否为 `.githooks`; 2) 检查 `.githooks/post-merge` 是否有 `chmod +x`。

**Q: .ship-audit.log 提交到 git 吗?** A: 推荐 commit 进去 (作为 audit trail 的一部分),如不要可加到 `.gitignore`。

**Q: hook 在 fast-forward merge 跑吗?** A: 跑。post-merge 在所有 merge (含 fast-forward) 完成后触发。

**Q: 跨平台兼容?** A: `date -u +"%Y-%m-%dT%H:%M:%SZ"` macOS BSD date 和 Linux GNU date 都支持。
