#!/bin/bash

set -euo pipefail

RECOVERY_LOG="${RECOVERY_LOG:-/tmp/auto_recover_ci.log}"
MAX_RETRIES=1

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" >> "$RECOVERY_LOG"
}

cleanup_cache() {
  log "Cache cleanup start"
  rm -rf .pytest_cache/ 2>/dev/null || true
  rm -rf backend/tests/.pytest_cache/ 2>/dev/null || true
  rm -rf frontend-vue3/node_modules/.cache/ 2>/dev/null || true
  find /tmp -maxdepth 1 -type d -name 'playwright_*' -mmin +60 -exec rm -rf {} + 2>/dev/null || true
  log "Cache cleanup done"
}

retry_test() {
  local cmd=("$@")
  local attempt=0

  while [ "$attempt" -le "$MAX_RETRIES" ]; do
    log "Attempt $((attempt + 1))/$((MAX_RETRIES + 1)): ${cmd[*]}"
    if "${cmd[@]}"; then
      log "Test PASS on attempt $((attempt + 1))"
      return 0
    fi

    attempt=$((attempt + 1))
    if [ "$attempt" -le "$MAX_RETRIES" ]; then
      log "Test FAIL, retry with cache cleanup"
      cleanup_cache
      sleep 5
    fi
  done

  log "Test FAIL after $((MAX_RETRIES + 1)) attempts, give up"
  return 1
}

main() {
  if [ "$#" -eq 0 ]; then
    echo "Usage: $0 <test_cmd> [args...]" >&2
    exit 2
  fi

  : > "$RECOVERY_LOG"
  log "=== auto_recover_ci.sh start (Sprint 58 #4 持久化) ==="
  cleanup_cache
  retry_test "$@"
}

main "$@"

# ## Stage 2 完成 — Sprint 58 #4
# - 完成时间: 2026-06-21
# - 关键点: 只用数组参数执行命令, 不使用 eval
# - Stage 3: 请核对 recovery 日志与 cleanup 范围
