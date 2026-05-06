#!/bin/bash
# 芙清 CRM - Vue3 前端一键启动（macOS）
# 启动后端 API (端口 8000) + Vue3 前端 (端口 5173)

PROJECT_DIR="/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
cd "$PROJECT_DIR"

echo "启动 FastAPI 后端 (端口8000)..."
nohup PYTHONPATH="$PROJECT_DIR" ~/.workbuddy/binaries/python/envs/default/bin/python backend/main.py > /tmp/fuqin-crm-backend.log 2>&1 &
BACKEND_PID=$!
echo "后端 PID: $BACKEND_PID"

sleep 2

echo "启动 Vue3 前端 (端口5173)..."
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3"
nohup npm run dev > /tmp/fuqin-crm-frontend-vue3.log 2>&1 &
FRONTEND_PID=$!
echo "前端 PID: $FRONTEND_PID"

echo ""
echo "✅ 所有服务已启动！"
echo "  - 后端API:  http://localhost:8000"
echo "  - 前端:     http://localhost:5173"
echo ""
echo "日志位置:"
echo "  - 后端: /tmp/fuqin-crm-backend.log"
echo "  - 前端: /tmp/fuqin-crm-frontend-vue3.log"
echo ""
echo "停止服务: kill $BACKEND_PID $FRONTEND_PID"
