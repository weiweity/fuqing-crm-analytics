#!/bin/bash
# Sprint 60.2 P3 uvicorn 守护 (2026-06-22): launchctl load 安装脚本
#
# 复用 com.fuqing.duckdb-backup.daily.plist 模式 (Sprint 4 P0-2)
#
# 设计:
# 1. 先 kill 当前 PID 9986 (手工 uvicorn 进程, 让 launchd 接管)
# 2. cp plist 到 ~/Library/LaunchAgents/
# 3. launchctl unload (防御: 旧版本残留)
# 4. launchctl load -w (注册 + 启用)
# 5. 等 30s, 验证 uvicorn 启动
# 6. 输出 launchctl list 状态 + curl /api/v1/health
#
# 注意: plist 用 python3 (不是 bash), 避开 macOS launchd sandbox deny bash 读 Desktop

set -e

REPO_ROOT="/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics"
PLIST_SRC="$REPO_ROOT/scripts/launchd/com.fuqing.uvicorn.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.fuqing.uvicorn.plist"
LAUNCH_AGENT_LABEL="com.fuqing.uvicorn"

echo "=== [1/6] kill 当前 uvicorn PID 9986 (让 launchd 接管) ==="
EXISTING_PIDS=$(lsof -ti :8000 2>/dev/null || true)
if [ -n "$EXISTING_PIDS" ]; then
    echo "    killing PIDs: $EXISTING_PIDS"
    kill $EXISTING_PIDS 2>/dev/null || true
    sleep 2
    # 强 kill 兜底
    EXISTING_PIDS=$(lsof -ti :8000 2>/dev/null || true)
    if [ -n "$EXISTING_PIDS" ]; then
        echo "    SIGKILL PIDs: $EXISTING_PIDS"
        kill -9 $EXISTING_PIDS 2>/dev/null || true
        sleep 1
    fi
else
    echo "    no uvicorn on :8000, skip kill"
fi

echo ""
echo "=== [2/6] cp plist 到 ~/Library/LaunchAgents/ ==="
cp "$PLIST_SRC" "$PLIST_DST"
ls -la "$PLIST_DST"

echo ""
echo "=== [3/6] launchctl unload (防御: 旧版本残留) ==="
launchctl unload "$PLIST_DST" 2>/dev/null || echo "    (no prior load, ok)"

echo ""
echo "=== [4/6] launchctl load -w ==="
launchctl load -w "$PLIST_DST"
echo "    load OK"

echo ""
echo "=== [5/6] 等 5s, 验证 launchctl list ==="
sleep 5
launchctl list | grep "$LAUNCH_AGENT_LABEL" || echo "    WARNING: not in launchctl list yet"

echo ""
echo "=== [6/6] 等 30s, 验证 uvicorn 启动 + /api/v1/health ==="
echo "    waiting 30s..."
sleep 30

echo ""
echo "--- launchctl list ---"
launchctl list | grep "$LAUNCH_AGENT_LABEL" || echo "    WARNING: not in launchctl list"

echo ""
echo "--- uvicorn process ---"
ps -ef | grep -E "uvicorn backend.main" | grep -v grep || echo "    WARNING: no uvicorn process"

echo ""
echo "--- /api/v1/health ---"
HTTP_CODE=$(curl -s -o /tmp/uvicorn_health.json -w "%{http_code}" "http://localhost:8000/api/v1/health" || echo "000")
echo "    HTTP $HTTP_CODE"
cat /tmp/uvicorn_health.json 2>/dev/null | head -5
echo ""

echo ""
echo "=== 安装完成 ==="
echo "验证命令:"
echo "  launchctl list | grep $LAUNCH_AGENT_LABEL"
echo "  curl http://localhost:8000/api/v1/health"
echo "  tail -f /tmp/fuqing-uvicorn-launchd.log"