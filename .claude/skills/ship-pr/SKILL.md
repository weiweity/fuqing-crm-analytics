---
name: ship-pr
description: 标准化 PR 流程 (替代 P3 session 直接 merge --no-ff main 模式). 6 步: 1) feat/fix branch  2) commit  3) push  4) gh pr create  5) CI 绿  6) gh pr merge --squash. post-merge hook 自动写 .ship-audit.log.
disable-model-invocation: true
---

# ship-pr — 标准化 PR 流程

适用场景: 任何代码改动 ship 到 main。**不**用此 skill = 直接在 main commit (违反 CLAUDE.md 12 步流程)。

## 6 步流程

### Step 1: feature branch

```bash
git checkout main
git pull origin main --ff-only
git checkout -b feat/<name>  # 或 fix/<name>
```

### Step 2: 改代码 + commit

按 CLAUDE.md "强制验证" + "Sprint 3 P1 教训" 走 (commit 前 `/review` skill, push 前 pytest 全绿)。

### Step 3: push 分支

```bash
git push --no-verify -u origin <branch>
# 注: --no-verify 绕 pre-push hook 防 SSH hang, 跟 Sprint 22+ P0-3 一致
```

### Step 4: 创建 PR

```bash
gh pr create \
  --title "feat/fix: <description>" \
  --body "## 改动\n- \n## 测试\n- \n## 关联\n- Sprint X #Y" \
  --base main
```

### Step 5: 等 CI 绿

```bash
# 轮询 PR checks 状态
gh pr checks <branch> --watch
# 全绿后才 merge
```

### Step 6: merge + 清理

```bash
# Squash merge (跟 Sprint 16.5 起的 B1+B2 模式一致)
gh pr merge <branch> --squash --delete-branch

# 拉 main 最新
git checkout main
git pull origin main --ff-only

# 重启 uvicorn (CLAUDE.md 必跑)
kill <old_uvicorn_pid>
nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 \
  > /tmp/uvicorn.log 2>&1 &

# 更新 CHANGELOG.md
# (加 v0.4.XX 段, 分类 Changed/Added/Fixed, 跟 Sprint 22 模式一致)
```

## 失败排查

| 错 | 原因 | 修法 |
|---|---|---|
| `gh pr create` 报 404 | gh CLI 没认证 | `gh auth login` |
| CI lint fail | ruff 错 | `ruff check backend/ --fix` |
| CI pytest fail | 新代码 regression | 跑单测查根因, 修后 push --force-with-lease |
| merge conflict | main 推进了 | `git rebase main` 后再 push --force-with-lease |
| `.ship-audit.log` 没新行 | post-merge hook 没触发 | 检查 `git config core.hooksPath` 设了 `.githooks` |

## 跟 CLAUDE.md 12 步流程对照

| 12 步 | ship-pr |
|---|---|
| ① git checkout -b | Step 1 |
| ② 写代码 | (skill 外) |
| ③ pytest | (skill 外, 跑前) |
| ④ review | (skill 外, commit 前) |
| ⑤ 修 review | (skill 外) |
| ⑥ commit | Step 2 |
| ⑦ push | Step 3 |
| ⑧ qa | (skill 外, push 前) |
| ⑨ merge | Step 6 (`gh pr merge --squash`) |
| ⑩ push main | Step 6 (PR 合并自动) |
| ⑪ pull | Step 6 |
| ⑫ restart | Step 6 (uvicorn) |

## 历史背景

Sprint 22+ P0-3 P3 session 直接用 `git merge --no-ff fix/xxx` 走 main 跳过 PR 流程, 优点快, 缺点无 CI 检查 + 公开 repo 缺 PR review trail。**ship-pr 是更稳的 P0+ 流程**, 适用 main 分支保护 + 多人协作场景。
