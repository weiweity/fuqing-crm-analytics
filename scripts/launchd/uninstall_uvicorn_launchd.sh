#!/bin/bash
# Sprint 60.2 P3 uvicorn 守护 (2026-06-22): launchctl unload 卸载脚本
#
# 复用 com.fuqing.duckdb-backup.daily.plist 模式 (Sprint 4 P0-2)
#
# 设计:
# 1. launchctl unload (停止 launchd 监控 + kill uvicorn)
# 2. rm plist (清理 ~/Library/LaunchAgents/)
# 3. 验证 port 8000 已释放

set -e

PLIST_DST="$HOME/Library/LaunchAgents/com.fuqing.uvicorn.plist"
LAUNCH_AGENT_LABEL="com.fuqing.uvicorn"

echo "=== [1/3] launchctl unload ==="
if launchctl list | grep -q "$LAUNCH_AGENT_LABEL"; then
    launchctl unload "$PLIST_DST"
    echo "    unload OK"
else
    echo "    (not loaded, skip)"
fi

echo ""
echo "=== [2/3] rm plist ==="
if [ -f "$PLIST_DST" ]; then
    rm "$PLIST_DST"
    echo "    rm OK"
else
    echo "    (plist not found, skip)"
fi

echo ""
echo "=== [3/3] 验证 port 8000 已释放 ==="
sleep 2
REMAINING_PIDS=$(lsof -ti :8000 2>/dev/null || true)
if [ -n "$REMAINING_PIDS" ]; then
    echo "    WARNING: still PIDs on :8000: $REMAINING_PIDS"
    echo "    manual kill needed: kill $REMAINING_PIDS"
else
    echo "    port 8000 free, OK"
fi

echo ""
echo "=== 卸载完成 ==="