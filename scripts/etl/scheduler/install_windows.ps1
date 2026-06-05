# FIX-M1: Windows install script for Task Scheduler ETL runner
# PRD §4.2: 每日 9 点自动刷新 ETL 数据

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$XmlPath = Join-Path $PSScriptRoot "etl_daily_taskscheduler.xml"
$TaskName = "FuqingETLDaily"
$TaskPath = "\Fuqing"

if (-not (Test-Path $XmlPath)) {
    Write-Error "ERROR: 找不到 $XmlPath"
    exit 1
}

Write-Host "=== 安装 Windows Task Scheduler ETL 调度器 ==="
Write-Host "源: $XmlPath"
Write-Host "任务名: $TaskName"
Write-Host ""

# 1. 读取 XML
$XmlContent = Get-Content $XmlPath -Raw

# 2. 替换项目根路径 (用户可改)
$ProjectRoot = "C:\Users\hutou\Desktop\fuqin date\fuqing-crm-analytics"
$XmlContent = $XmlContent -replace "C:\\Users\\hutou\\Desktop\\fuqin date\\fuqing-crm-analytics", $ProjectRoot

# 3. 卸载旧版本 (如果存在)
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "✓ 卸载旧任务"
}

# 4. 注册新任务
Register-ScheduledTask -TaskName $TaskName `
    -Xml $XmlContent `
    -TaskPath $TaskPath `
    -User "SYSTEM" `
    -Force | Out-Null
Write-Host "✓ Register-ScheduledTask"

# 5. 验证
$task = Get-ScheduledTask -TaskName $TaskName
if ($task) {
    Write-Host "✓ 任务已注册: $($task.TaskPath)\$($task.TaskName)"
    Write-Host "  状态: $($task.State)"
    Write-Host "  下次运行: $($task.NextRunTime)"
} else {
    Write-Error "任务未注册成功"
    exit 1
}

Write-Host ""
Write-Host "=== 卸载方式 ==="
Write-Host "  Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
Write-Host ""
Write-Host "=== 手动跑 1 次 (验证) ==="
Write-Host "  cd '$ProjectRoot'"
Write-Host "  python scripts\run_etl.py --update"
Write-Host ""
Write-Host "=== 看 log (在事件查看器) ==="
Write-Host "  Event Viewer -> Applications and Services Logs -> Microsoft -> Windows -> TaskScheduler"
Write-Host ""
Write-Host "✓ Windows Task Scheduler ETL 调度器安装完成"
