#!/usr/bin/env bash
# Sync ops monitor plists into ~/Library/LaunchAgents and (re)bootstrap.
# L4.7: agents call python3 scripts, not bash for the monitor body.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$REPO_ROOT/scripts/launchd"
DEST="${HOME}/Library/LaunchAgents"
UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}"

PLISTS=(
  com.fuqing.pre-existing-fail-monitor.weekly.plist
  com.fuqing.memory-size-monitor.weekly.plist
  com.fuqing.adhoc-hitrate-monitor.weekly.plist
  com.fuqing.clickhouse-poc-monitor.weekly.plist
  com.fuqing.db-size-alert.daily.plist
)

mkdir -p "$DEST"

for name in "${PLISTS[@]}"; do
  src="$SRC/$name"
  dst="$DEST/$name"
  if [[ ! -f "$src" ]]; then
    echo "ERROR: missing $src" >&2
    exit 1
  fi
  # Must point at scripts/ops/
  if ! grep -q 'scripts/ops/' "$src"; then
    echo "ERROR: $src does not reference scripts/ops/" >&2
    exit 1
  fi
  label="${name%.plist}"
  # bootout if loaded (ignore errors)
  launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
  launchctl bootout "$DOMAIN" "$dst" 2>/dev/null || true
  cp "$src" "$dst"
  # bootstrap
  if ! launchctl bootstrap "$DOMAIN" "$dst" 2>/dev/null; then
    # older fallback
    launchctl unload "$dst" 2>/dev/null || true
    launchctl load "$dst" 2>/dev/null || true
  fi
  echo "installed: $dst"
done

echo "OK install_launchagents: ${#PLISTS[@]} plists synced to $DEST"
