@echo off
chcp 65001 >nul
title 芙清CRM服务

cd /d D:\fuqing-crm-analytics

:: 拉取最新代码（静默，不阻塞）
git pull origin main

:: 启动后端API（端口8001）
start "芙清CRM-后端" /min cmd /c "cd /d D:\fuqing-crm-analytics && set PYTHONPATH=D:\fuqing-crm-analytics && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001"

:: 等后端启动
timeout /t 3 /nobreak >nul

:: 启动前端服务（端口5173，serve静态文件）
start "芙清CRM-前端" /min cmd /c "cd /d D:\fuqing-crm-analytics\frontend-vue3 && npx serve dist -l 5173 -s"

echo.
echo ========================================
echo   芙清CRM服务已启动
echo   前端: http://localhost:5173
echo   后端: http://localhost:8001
echo   同事访问: http://192.168.100.39:5173
echo ========================================
echo.
echo 关闭此窗口不会停止服务
echo 要停止服务请关闭后端和前端的命令行窗口
echo.
pause
