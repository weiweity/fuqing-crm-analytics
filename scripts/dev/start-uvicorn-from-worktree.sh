#!/usr/bin/env bash
# 从 git worktree 启动 uvicorn，同时保证 worktree 里有主仓库的 .env。
#
# 背景：git worktree 不会继承主仓库的 .env，若直接在 worktree 里启动 uvicorn，
# FQ_CRM_PASSWORDS / DUCKDB_PATH 等配置会丢失或变成随机值，导致登录失败、
# DuckDB 路径错等怪问题。
#
# 用法：
#   scripts/dev/start-uvicorn-from-worktree.sh /path/to/worktree [port]
# 示例：
#   scripts/dev/start-uvicorn-from-worktree.sh /Users/hutou/Desktop/fuqin-date/wt-sprint170-r-bucket 8000

set -euo pipefail

WORKTREE_PATH="${1:-}"
PORT="${2:-8000}"
MAIN_REPO="/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics"
PYTHON_BIN="/Users/hutou/homebrew/bin/python3"

if [[ -z "$WORKTREE_PATH" ]]; then
    echo "Usage: $0 <worktree-path> [port]"
    echo "Example: $0 /Users/hutou/Desktop/fuqin-date/wt-sprint170-r-bucket 8000"
    exit 1
fi

if [[ ! -d "$WORKTREE_PATH" ]]; then
    echo "Error: worktree path does not exist: $WORKTREE_PATH"
    exit 1
fi

if [[ ! -f "$MAIN_REPO/.env" ]]; then
    echo "Error: main repo .env not found at $MAIN_REPO/.env"
    exit 1
fi

# 同步 .env 到 worktree（gitignored，不影响仓库状态）
if [[ ! -f "$WORKTREE_PATH/.env" ]] || ! diff -q "$MAIN_REPO/.env" "$WORKTREE_PATH/.env" >/dev/null 2>&1; then
    echo "Syncing .env from main repo to worktree..."
    cp "$MAIN_REPO/.env" "$WORKTREE_PATH/.env"
fi

# 杀掉该端口上已有的 uvicorn
EXISTING_PIDS=$(lsof -ti tcp:"$PORT" 2>/dev/null || true)
if [[ -n "$EXISTING_PIDS" ]]; then
    echo "Killing existing process on port $PORT: $EXISTING_PIDS"
    kill $EXISTING_PIDS
    sleep 2
fi

cd "$WORKTREE_PATH"
export PYTHONPATH="$WORKTREE_PATH"

echo "Starting uvicorn..."
echo "  worktree:   $WORKTREE_PATH"
echo "  port:       $PORT"
echo "  python:     $PYTHON_BIN"

exec "$PYTHON_BIN" -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
