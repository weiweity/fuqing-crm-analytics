#!/usr/bin/env bash
set -euo pipefail

CRM_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STATE_DIR="${FQ_STACK_STATE_DIR:-${TMPDIR:-/tmp}/fuqing-crm-analytics-${UID}}"
API_PID_FILE="$STATE_DIR/api.pid"
API_PORT_FILE="$STATE_DIR/api.port"
API_START_FILE="$STATE_DIR/api.started_at"
FRONTEND_PID_FILE="$STATE_DIR/frontend.pid"
FRONTEND_PORT_FILE="$STATE_DIR/frontend.port"
FRONTEND_START_FILE="$STATE_DIR/frontend.started_at"
API_PORT="$(sed -n '1p' "$API_PORT_FILE" 2>/dev/null || true)"
FRONTEND_PORT="$(sed -n '1p' "$FRONTEND_PORT_FILE" 2>/dev/null || true)"
API_PORT="${API_PORT:-${FQ_API_PORT:-8000}}"
FRONTEND_PORT="${FRONTEND_PORT:-${FQ_FRONTEND_PORT:-5173}}"
stop_status=0

valid_port() {
  [[ "$1" =~ ^[0-9]+$ ]] && (( "$1" >= 1 && "$1" <= 65535 ))
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

pid_owns_port() {
  local pid="$1"
  local port="$2"
  local owners

  owners="$(port_owners "$port")" || return $?
  [[ "$owners" == "$pid" ]]
}

stop_tracked_process() {
  local label="$1"
  local pid_file="$2"
  local port_file="$3"
  local start_file="$4"
  local marker="$5"
  local port="$6"
  local pid
  local expected_start
  local actual_start
  local attempt
  local port_status

  [[ -f "$pid_file" ]] || return 0
  IFS= read -r pid < "$pid_file" || true
  if [[ ! "$pid" =~ ^[0-9]+$ ]]; then
    echo "ERROR: invalid $label PID file: $pid_file" >&2
    stop_status=1
    return 0
  fi
  if ! pid_is_running "$pid"; then
    rm -f "$pid_file" "$port_file" "$start_file"
    echo "$label already stopped; removed stale PID $pid"
    return 0
  fi
  IFS= read -r expected_start < "$start_file" 2>/dev/null || true
  actual_start="$(pid_started_at "$pid")"
  if [[ -z "$expected_start" || -z "$actual_start" || "$actual_start" != "$expected_start" ]]; then
    echo "ERROR: refusing to stop $label PID $pid because its start fingerprint does not match" >&2
    stop_status=1
    return 0
  fi
  if ! pid_is_owned "$pid" "$marker"; then
    echo "ERROR: refusing to stop unowned $label PID $pid" >&2
    stop_status=1
    return 0
  fi
  if pid_owns_port "$pid" "$port"; then
    :
  else
    port_status=$?
    echo "ERROR: refusing to stop $label PID $pid because it does not exclusively own port $port" >&2
    [[ "$port_status" -ne 2 ]] || echo "ERROR: port ownership query failed closed" >&2
    stop_status=1
    return 0
  fi

  kill -TERM "$pid" 2>/dev/null || true
  for attempt in $(seq 1 20); do
    if ! pid_is_running "$pid"; then
      rm -f "$pid_file" "$port_file" "$start_file"
      echo "stopped $label pid=$pid"
      return 0
    fi
    sleep 0.25
  done

  actual_start="$(pid_started_at "$pid")"
  if pid_is_owned "$pid" "$marker" \
    && [[ -n "$actual_start" && "$actual_start" == "$expected_start" ]]; then
    kill -KILL "$pid" 2>/dev/null || true
    sleep 0.25
  fi
  if pid_is_running "$pid"; then
    echo "ERROR: $label PID $pid is still running" >&2
    stop_status=1
  else
    rm -f "$pid_file" "$port_file" "$start_file"
    echo "stopped $label pid=$pid after SIGKILL"
  fi
}

verify_port_free() {
  local label="$1"
  local port="$2"
  local owner
  local port_status

  if owner="$(port_owners "$port")"; then
    echo "ERROR: $label port $port is still owned by PID $owner; it was not killed" >&2
    stop_status=1
  else
    port_status=$?
    if [[ "$port_status" -ne 1 ]]; then
      echo "ERROR: could not verify that $label port $port is free" >&2
      stop_status=1
    fi
  fi
}

valid_port "$API_PORT" || {
  echo "ERROR: invalid API port in state/config: $API_PORT" >&2
  exit 1
}
valid_port "$FRONTEND_PORT" || {
  echo "ERROR: invalid frontend port in state/config: $FRONTEND_PORT" >&2
  exit 1
}
command -v lsof >/dev/null 2>&1 || {
  echo "ERROR: lsof is required for safe process ownership checks" >&2
  exit 1
}

stop_tracked_process "frontend" "$FRONTEND_PID_FILE" "$FRONTEND_PORT_FILE" "$FRONTEND_START_FILE" "node_modules/.bin/vite" "$FRONTEND_PORT"
stop_tracked_process "api" "$API_PID_FILE" "$API_PORT_FILE" "$API_START_FILE" "backend.main:app" "$API_PORT"
verify_port_free "frontend" "$FRONTEND_PORT"
verify_port_free "api" "$API_PORT"

if [[ "$stop_status" -ne 0 ]]; then
  echo "stack stop incomplete" >&2
  exit "$stop_status"
fi

echo "stack stopped; ports $API_PORT and $FRONTEND_PORT are free"
