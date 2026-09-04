#!/usr/bin/env bash
set -euo pipefail
pkill -TERM -f "uvicorn backend.main:app" 2>/dev/null || true
pkill -TERM -f "fuqing-crm-analytics/frontend-vue3.*vite" 2>/dev/null || true
pkill -TERM -f "frontend-vue3/node_modules/.bin/vite" 2>/dev/null || true
sleep 1
pkill -KILL -f "uvicorn backend.main:app" 2>/dev/null || true
echo "stack stopped"
