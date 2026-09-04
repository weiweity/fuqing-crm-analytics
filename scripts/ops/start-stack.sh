#!/usr/bin/env bash
# 芙清 CRM 本地栈一键启动（无空格路径 + 固定 Homebrew Python）
set -euo pipefail
CRM_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$CRM_ROOT"

# 优先 Homebrew Python（项目需 3.10+；系统 3.9 会在 str|None 处炸）
if [[ -x /Users/hutou/homebrew/bin/python3 ]]; then
  PY=/Users/hutou/homebrew/bin/python3
elif command -v python3.14 >/dev/null 2>&1; then
  PY="$(command -v python3.14)"
elif command -v python3.12 >/dev/null 2>&1; then
  PY="$(command -v python3.12)"
else
  PY="$(command -v python3)"
fi
echo "using PY=$PY ($($PY --version 2>&1))"

ver="$($PY -c 'import sys; print(sys.version_info[:2])')"
if [[ "$ver" == "(3, 9)" ]] || [[ "$ver" == "(3, 8)" ]]; then
  echo "ERROR: Python too old for this project: $ver. Install Homebrew python@3.14" >&2
  exit 1
fi

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8000/docs; then
  nohup "$PY" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend \
    > /tmp/fuqing-uvicorn.log 2>&1 &
  echo "started uvicorn pid=$!"
else
  echo "uvicorn already up"
fi

cd "$CRM_ROOT/frontend-vue3"
if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:5173/; then
  if [[ -d node_modules ]]; then
    nohup npm run dev > /tmp/fuqing-vite.log 2>&1 &
    echo "started vite pid=$!"
  else
    echo "skip vite: no node_modules" >&2
  fi
else
  echo "vite already up"
fi

for i in $(seq 1 60); do
  api_ok=0; vite_ok=0
  curl -sf -o /dev/null --max-time 1 http://127.0.0.1:8000/docs && api_ok=1 || true
  curl -sf -o /dev/null --max-time 1 http://127.0.0.1:5173/ && vite_ok=1 || true
  if [[ $api_ok -eq 1 && $vite_ok -eq 1 ]]; then
    echo "stack ready: api=:8000 vite=:5173"
    exit 0
  fi
  sleep 1
done
echo "stack start timeout; api_ok=$api_ok vite_ok=$vite_ok" >&2
echo "--- uvicorn log ---" >&2
tail -40 /tmp/fuqing-uvicorn.log >&2 || true
exit 1
