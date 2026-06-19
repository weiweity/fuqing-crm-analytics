#!/bin/bash
# sync-agents.sh — 从 CLAUDE.md 生成 AGENTS.md（Codex 自动注入文件）
# 用法: bash scripts/sync-agents.sh
#
# 规则: 改行为规则只改 CLAUDE.md，然后跑这个脚本同步到 AGENTS.md。
# AGENTS.md 在 .gitignore 里，不进 git，仅供 Codex app 自动注入。

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f CLAUDE.md ]; then
  echo "❌ CLAUDE.md not found in project root"
  exit 1
fi

sed \
  -e 's/CLAUDE\.md/AGENTS.md/g' \
  -e 's/Claude Code 自动化配置/Codex 自动化配置/g' \
  CLAUDE.md > AGENTS.md

echo "✅ AGENTS.md synced from CLAUDE.md ($(wc -l < AGENTS.md) lines)"
