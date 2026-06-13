#!/usr/bin/env bash
# scripts/setup-hooks.sh — 一次性激活 githooks
# 作用: git config core.hooksPath .githooks
# 根因 (B1 P1-3 review, 2026-06-06): core.hooksPath 默认指向空目录,
#   .githooks/pre-commit 钩子在大多数开发者机器上是死代码。
#   演示代码检查 (gstack review) 会跳过 hooks, 必须手动激活。
# 一次性, session 保持; 重新 clone / 重新 init 需重跑。
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if [ ! -d ".githooks" ]; then
    echo "FAIL: .githooks/ 目录不存在, 请确认在 sample-crm-analytics 仓库根目录运行"
    exit 1
fi

# 关键: 让 .githooks/pre-commit 真正被 git 调
git config core.hooksPath .githooks

echo "✅ githooks activated (.githooks/pre-commit)"
echo "   当前 core.hooksPath: $(git config core.hooksPath)"
echo "   验证: ls -la \$(git rev-parse --git-path hooks)/pre-commit"
echo "   下次 commit 会自动跑 ruff + pytest + ground-truth lint"
