#!/usr/bin/env bash
# FIX-M1: Mac install script for launchd ETL scheduler
# PRD §4.2: 每日 9 点自动刷新 ETL 数据

set -euo pipefail

PLIST_SRC="$(cd "$(dirname "$0")" && pwd)/com.fuqing.etl.daily.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.fuqing.etl.daily.plist"

if [ ! -f "$PLIST_SRC" ]; then
    echo "ERROR: 找不到 $PLIST_SRC" >&2
    exit 1
fi

echo "=== 安装 Mac launchd ETL 调度器 ==="
echo "源: $PLIST_SRC"
echo "目标: $PLIST_DST"
echo

# 1. 复制 plist
mkdir -p "$HOME/Library/LaunchAgents"
cp "$PLIST_SRC" "$PLIST_DST"
echo "✓ 复制 plist"

# 2. 卸载旧版本 (如果存在)
launchctl unload "$PLIST_DST" 2>/dev/null || true

# 3. 加载新版本
launchctl load "$PLIST_DST"
echo "✓ launchctl load"

# 4. 验证
if launchctl list | grep -q "com.fuqing.etl.daily"; then
    echo "✓ 调度器已注册 (run 'launchctl list | grep fuqing' to verify)"
else
    echo "⚠️  调度器未在 list 中, 检查 launchctl 错误" >&2
    exit 1
fi

echo
echo "=== 卸载方式 ==="
echo "  launchctl unload $PLIST_DST"
echo "  rm $PLIST_DST"
echo
echo "=== 手动跑 1 次 (验证) ==="
echo "  cd '$HOME/Desktop/fuqin date/sample-crm-analytics'"
echo "  PYTHONPATH=\"\$(pwd)\" python3 scripts/run_etl.py --update"
echo
echo "=== 看 log ==="
echo "  tail -f /tmp/fuqing-etl-scheduler.log"
echo
echo "✓ Mac launchd ETL 调度器安装完成"
