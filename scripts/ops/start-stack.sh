#!/usr/bin/env bash
# 伸美 AI 增长董事会本地栈一键启动。默认仅监听 loopback，端口可通过环境变量覆盖。
set -euo pipefail

CRM_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
API_PORT="${FQ_API_PORT:-8000}"
FRONTEND_PORT="${FQ_FRONTEND_PORT:-5173}"
STATE_DIR="${FQ_STACK_STATE_DIR:-${TMPDIR:-/tmp}/fuqing-crm-analytics-${UID}}"
API_PID_FILE="$STATE_DIR/api.pid"
API_PORT_FILE="$STATE_DIR/api.port"
API_START_FILE="$STATE_DIR/api.started_at"
FRONTEND_PID_FILE="$STATE_DIR/frontend.pid"
FRONTEND_PORT_FILE="$STATE_DIR/frontend.port"
FRONTEND_START_FILE="$STATE_DIR/frontend.started_at"
API_LOG="$STATE_DIR/api.log"
FRONTEND_LOG="$STATE_DIR/frontend.log"

api_started=0
frontend_started=0
api_pid=""
frontend_pid=""
api_started_at=""
frontend_started_at=""

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

valid_port() {
  [[ "$1" =~ ^[0-9]+$ ]] && (( "$1" >= 1 && "$1" <= 65535 ))
}

port_owners() {
  local port="$1"
  local output
  local status
  local line

  if output="$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>&1 | sort -u)"; then
    status=0
  else
    status=$?
  fi
  if [[ "$status" -eq 1 && -z "$output" ]]; then
    return 1
  fi
  if [[ "$status" -ne 0 || -z "$output" ]]; then
    echo "ERROR: lsof failed while checking port $port: ${output:-no output}" >&2
    return 2
  fi
  while IFS= read -r line; do
    if [[ ! "$line" =~ ^[0-9]+$ ]]; then
      echo "ERROR: unexpected lsof output for port $port: $line" >&2
      return 2
    fi
  done <<< "$output"
  printf '%s\n' "$output"
}

pid_command() {
  ps -p "$1" -o command= 2>/dev/null || true
}

pid_started_at() {
  ps -p "$1" -o lstart= 2>/dev/null \
    | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' || true
}

pid_is_running() {
  local process_state
  process_state="$(ps -p "$1" -o stat= 2>/dev/null | sed -e 's/^[[:space:]]*//' || true)"
  [[ -n "$process_state" && "$process_state" != Z* ]]
}

pid_is_owned() {
  local pid="$1"
  local marker="$2"
  local command
  command="$(pid_command "$pid")"
  [[ -n "$command" && "$command" == *"$CRM_ROOT"* && "$command" == *"$marker"* ]]
}

pid_start_matches() {
  local pid="$1"
  local expected="$2"
  local actual
  actual="$(pid_started_at "$pid")"
  [[ -n "$expected" && -n "$actual" && "$actual" == "$expected" ]]
}

tracked_pid() {
  local pid_file="$1"
  local start_file="$2"
  local marker="$3"
  local pid
  local expected_start

  [[ -f "$pid_file" ]] || return 1
  IFS= read -r pid < "$pid_file" || true
  if [[ ! "$pid" =~ ^[0-9]+$ ]] || ! pid_is_running "$pid"; then
    rm -f "$pid_file" "$start_file"
    return 1
  fi
  IFS= read -r expected_start < "$start_file" 2>/dev/null || true
  if ! pid_is_owned "$pid" "$marker" \
    || ! pid_start_matches "$pid" "$expected_start"; then
    echo "ERROR: refusing unowned PID $pid from $pid_file" >&2
    return 2
  fi
  printf '%s\n' "$pid"
}

terminate_owned() {
  local pid="$1"
  local marker="$2"
  local expected_start="$3"
  local attempt

  [[ -n "$pid" ]] || return 0
  pid_is_running "$pid" || return 0
  if [[ -n "$expected_start" ]]; then
    pid_start_matches "$pid" "$expected_start" || return 1
  else
    pid_is_owned "$pid" "$marker" || return 1
  fi
  kill -TERM "$pid" 2>/dev/null || true
  for attempt in $(seq 1 20); do
    pid_is_running "$pid" || return 0
    sleep 0.25
  done
  if { [[ -n "$expected_start" ]] && pid_start_matches "$pid" "$expected_start"; } \
    || { [[ -z "$expected_start" ]] && pid_is_owned "$pid" "$marker"; }; then
    kill -KILL "$pid" 2>/dev/null || true
    for attempt in $(seq 1 8); do
      pid_is_running "$pid" || return 0
      sleep 0.25
    done
    return 1
  fi
  return 0
}

cleanup_started() {
  local cleanup_failed=0

  if [[ "$frontend_started" -eq 1 ]]; then
    if terminate_owned "$frontend_pid" "node_modules/.bin/vite" "$frontend_started_at"; then
      rm -f "$FRONTEND_PID_FILE" "$FRONTEND_PORT_FILE" "$FRONTEND_START_FILE"
    else
      echo "ERROR: frontend PID $frontend_pid survived cleanup; state files preserved" >&2
      cleanup_failed=1
    fi
  fi
  if [[ "$api_started" -eq 1 ]]; then
    if terminate_owned "$api_pid" "backend.main:app" "$api_started_at"; then
      rm -f "$API_PID_FILE" "$API_PORT_FILE" "$API_START_FILE"
    else
      echo "ERROR: API PID $api_pid survived cleanup; state files preserved" >&2
      cleanup_failed=1
    fi
  fi
  return "$cleanup_failed"
}

on_exit() {
  local status=$?
  trap - EXIT
  cleanup_started || status=1
  exit "$status"
}

handle_signal() {
  exit 130
}

api_healthy() {
  local body
  body="$(curl -fsS --max-time 2 "http://127.0.0.1:$API_PORT/openapi.json" 2>/dev/null)" \
    || return 1
  [[ "$body" == *'Sample CRM 客户分析系统 API'* ]]
}

frontend_healthy() {
  local body
  body="$(curl -fsS --max-time 2 "http://127.0.0.1:$FRONTEND_PORT/" 2>/dev/null)" \
    || return 1
  [[ "$body" == *'<title>伸美 AI 增长董事会</title>'* ]]
}

trap on_exit EXIT
trap handle_signal INT TERM HUP

valid_port "$API_PORT" || fail "invalid FQ_API_PORT=$API_PORT"
valid_port "$FRONTEND_PORT" || fail "invalid FQ_FRONTEND_PORT=$FRONTEND_PORT"
[[ "$API_PORT" != "$FRONTEND_PORT" ]] || fail "API and frontend ports must differ"
command -v lsof >/dev/null 2>&1 || fail "lsof is required for safe port ownership checks"

mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"
cd "$CRM_ROOT"

if [[ -n "${FQ_PYTHON_BIN:-}" ]]; then
  PY="$FQ_PYTHON_BIN"
elif [[ -x /Users/hutou/homebrew/bin/python3 ]]; then
  PY=/Users/hutou/homebrew/bin/python3
elif command -v python3.14 >/dev/null 2>&1; then
  PY="$(command -v python3.14)"
else
  fail "Python 3.14+ is required; set FQ_PYTHON_BIN to an explicit interpreter"
fi

"$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 14) else 1)' \
  || fail "Python 3.14+ is required; found $($PY --version 2>&1)"
echo "using PY=$PY ($($PY --version 2>&1))"

api_existing=0
if api_pid="$(tracked_pid "$API_PID_FILE" "$API_START_FILE" "backend.main:app")"; then
  api_existing=1
else
  tracked_status=$?
  [[ "$tracked_status" -ne 2 ]] || fail "API PID file is not owned by this checkout"
fi

if api_owner="$(port_owners "$API_PORT")"; then
  :
else
  owner_status=$?
  [[ "$owner_status" -eq 1 ]] || fail "cannot safely determine owner of API port $API_PORT"
  api_owner=""
fi
if [[ "$api_existing" -eq 1 ]]; then
  stored_api_port="$(sed -n '1p' "$API_PORT_FILE" 2>/dev/null || true)"
  [[ "$stored_api_port" == "$API_PORT" ]] || fail "tracked API uses port ${stored_api_port:-unknown}, not $API_PORT"
  [[ "$api_owner" == "$api_pid" ]] || fail "tracked API PID $api_pid does not own port $API_PORT"
  api_healthy || fail "tracked API on port $API_PORT failed the product health signature"
  echo "api already up: pid=$api_pid port=$API_PORT"
else
  [[ -z "$api_owner" ]] || fail "port $API_PORT is owned by unrelated PID $api_owner"
  CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:$FRONTEND_PORT,http://127.0.0.1:$FRONTEND_PORT}" \
    nohup "$PY" -m uvicorn backend.main:app \
      --app-dir "$CRM_ROOT" --host 127.0.0.1 --port "$API_PORT" \
      > "$API_LOG" 2>&1 &
  api_pid=$!
  api_started=1
  api_started_at="$(pid_started_at "$api_pid")"
  [[ -n "$api_started_at" ]] || fail "could not fingerprint newly started API PID $api_pid"
  printf '%s\n' "$api_pid" > "$API_PID_FILE"
  printf '%s\n' "$API_PORT" > "$API_PORT_FILE"
  printf '%s\n' "$api_started_at" > "$API_START_FILE"
  echo "started api: pid=$api_pid port=$API_PORT"
fi

VITE_BIN="$CRM_ROOT/frontend-vue3/node_modules/.bin/vite"
[[ -x "$VITE_BIN" ]] || fail "frontend dependencies are missing; run npm ci in frontend-vue3"

frontend_existing=0
if frontend_pid="$(tracked_pid "$FRONTEND_PID_FILE" "$FRONTEND_START_FILE" "node_modules/.bin/vite")"; then
  frontend_existing=1
else
  tracked_status=$?
  [[ "$tracked_status" -ne 2 ]] || fail "frontend PID file is not owned by this checkout"
fi

if frontend_owner="$(port_owners "$FRONTEND_PORT")"; then
  :
else
  owner_status=$?
  [[ "$owner_status" -eq 1 ]] || fail "cannot safely determine owner of frontend port $FRONTEND_PORT"
  frontend_owner=""
fi
if [[ "$frontend_existing" -eq 1 ]]; then
  stored_frontend_port="$(sed -n '1p' "$FRONTEND_PORT_FILE" 2>/dev/null || true)"
  [[ "$stored_frontend_port" == "$FRONTEND_PORT" ]] \
    || fail "tracked frontend uses port ${stored_frontend_port:-unknown}, not $FRONTEND_PORT"
  [[ "$frontend_owner" == "$frontend_pid" ]] \
    || fail "tracked frontend PID $frontend_pid does not own port $FRONTEND_PORT"
  frontend_healthy || fail "tracked frontend on port $FRONTEND_PORT failed the product health signature"
  echo "frontend already up: pid=$frontend_pid port=$FRONTEND_PORT"
else
  [[ -z "$frontend_owner" ]] || fail "port $FRONTEND_PORT is owned by unrelated PID $frontend_owner"
  VITE_API_PROXY="${VITE_API_PROXY:-http://127.0.0.1:$API_PORT}" \
    nohup "$VITE_BIN" "$CRM_ROOT/frontend-vue3" \
      --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort \
      > "$FRONTEND_LOG" 2>&1 &
  frontend_pid=$!
  frontend_started=1
  frontend_started_at="$(pid_started_at "$frontend_pid")"
  [[ -n "$frontend_started_at" ]] \
    || fail "could not fingerprint newly started frontend PID $frontend_pid"
  printf '%s\n' "$frontend_pid" > "$FRONTEND_PID_FILE"
  printf '%s\n' "$FRONTEND_PORT" > "$FRONTEND_PORT_FILE"
  printf '%s\n' "$frontend_started_at" > "$FRONTEND_START_FILE"
  echo "started frontend: pid=$frontend_pid port=$FRONTEND_PORT"
fi

for attempt in $(seq 1 60); do
  pid_is_running "$api_pid" || fail "API exited; see $API_LOG"
  pid_is_running "$frontend_pid" || fail "frontend exited; see $FRONTEND_LOG"
  if api_healthy && frontend_healthy; then
    trap - EXIT INT TERM HUP
    echo "stack ready: api=http://127.0.0.1:$API_PORT frontend=http://127.0.0.1:$FRONTEND_PORT"
    exit 0
  fi
  sleep 1
done

fail "stack start timed out; inspect $API_LOG and $FRONTEND_LOG"
