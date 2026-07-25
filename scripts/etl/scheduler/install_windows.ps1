# PR3: Windows Task Scheduler ETL 安装 (安全版)
# 硬约束:
#   - 禁止 SYSTEM 跑用户可写仓库
#   - 必须使用专用低权服务账号
#   - 必须使用绝对 venv python 路径
#   - 安装前校验仓库 ACL (Users/Everyone 不可写)
#
# 用法 (管理员 PowerShell):
#   $env:FQ_ETL_SERVICE_USER = ".\fuqing-etl"
#   $env:FQ_ETL_SERVICE_PASSWORD = "<password>"
#   $env:FQ_PROJECT_ROOT = "D:\fuqin-date\fuqing-crm-analytics"
#   .\scripts\etl\scheduler\install_windows.ps1

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$XmlPath = Join-Path $PSScriptRoot "etl_daily_taskscheduler.xml"
$TaskName = "FuqingETLDaily"
$TaskPath = "\Fuqing"

function Write-Banner($msg) { Write-Host "=== $msg ===" -ForegroundColor Cyan }

if (-not (Test-Path $XmlPath)) {
    Write-Error "ERROR: 找不到 $XmlPath"
    exit 1
}

# ── 1. 专用服务账号 (禁止 SYSTEM) ──
$ServiceUser = $env:FQ_ETL_SERVICE_USER
$ServicePassword = $env:FQ_ETL_SERVICE_PASSWORD
if ([string]::IsNullOrWhiteSpace($ServiceUser)) {
    Write-Error @"
ERROR: 必须设置 FQ_ETL_SERVICE_USER (专用低权账号, 禁止 SYSTEM).
示例:
  `$env:FQ_ETL_SERVICE_USER = '.\fuqing-etl'
  `$env:FQ_ETL_SERVICE_PASSWORD = '<password>'
  `$env:FQ_PROJECT_ROOT = 'D:\fuqin-date\fuqing-crm-analytics'
"@
    exit 1
}
if ($ServiceUser -match '(?i)^(SYSTEM|NT AUTHORITY\\SYSTEM|S-1-5-18)$') {
    Write-Error "ERROR: 禁止使用 SYSTEM 账号跑 ETL (用户可写仓库 + 高权 = 横向提权面)."
    exit 1
}
if ([string]::IsNullOrWhiteSpace($ServicePassword)) {
    Write-Error "ERROR: 必须设置 FQ_ETL_SERVICE_PASSWORD"
    exit 1
}

# ── 2. 项目根 + 绝对 venv python ──
$ProjectRoot = if ($env:FQ_PROJECT_ROOT) { $env:FQ_PROJECT_ROOT } else {
    # 默认: 本脚本向上两级 (scripts/etl/scheduler → 仓根)
    (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
}
if (-not (Test-Path $ProjectRoot)) {
    Write-Error "ERROR: 项目根不存在: $ProjectRoot"
    exit 1
}
$ProjectRoot = (Resolve-Path $ProjectRoot).Path

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Error "ERROR: 找不到绝对 venv 路径: $VenvPython (请先 setup.bat 创建 .venv)"
    exit 1
}
$VenvPython = (Resolve-Path $VenvPython).Path

# ── 3. 严格 ACL: Users/Everyone 不得对仓库有写权限 ──
function Test-RepoAclStrict([string]$Root) {
    $acl = Get-Acl -Path $Root
    $bad = @()
    foreach ($ace in $acl.Access) {
        $id = $ace.IdentityReference.Value
        $rights = $ace.FileSystemRights.ToString()
        $isWrite = $rights -match 'Write|Modify|FullControl|CreateFiles|Delete|ChangePermissions|TakeOwnership'
        $isBroad = $id -match '(?i)\\(Users|Everyone|Authenticated Users)$' -or $id -match '^(Everyone|BUILTIN\\Users)$'
        if ($ace.AccessControlType -eq 'Allow' -and $isWrite -and $isBroad) {
            $bad += "$id => $rights"
        }
    }
    return $bad
}

$aclProblems = Test-RepoAclStrict $ProjectRoot
if ($aclProblems.Count -gt 0) {
    Write-Error @"
ERROR: 仓库 ACL 不安全 (用户可写 + 调度器高权 禁止).
问题 ACE:
  $($aclProblems -join "`n  ")
修复建议 (管理员):
  icacls `"$ProjectRoot`" /inheritance:r
  icacls `"$ProjectRoot`" /grant:r `"$ServiceUser`:(OI)(CI)RX`"
  icacls `"$ProjectRoot`" /grant:r `"Administrators:(OI)(CI)F`"
  # data/ 写权限单独给服务账号:
  icacls `"$ProjectRoot\data`" /grant:r `"$ServiceUser`:(OI)(CI)M`"
"@
    exit 1
}

Write-Banner "安装 Windows Task Scheduler ETL (安全版)"
Write-Host "源: $XmlPath"
Write-Host "任务: $TaskPath\$TaskName"
Write-Host "用户: $ServiceUser"
Write-Host "Python: $VenvPython"
Write-Host "项目根: $ProjectRoot"
Write-Host ""

# ── 4. 生成任务 XML (绝对路径 + 低权账号) ──
$XmlContent = Get-Content $XmlPath -Raw -Encoding Unicode
# 兼容 UTF-8 存盘的 XML
if ($XmlContent -notmatch '<Task') {
    $XmlContent = Get-Content $XmlPath -Raw -Encoding UTF8
}

# XML 文本节点 escape (账号/路径可能含 & < > ")
$EscapedUser = [System.Security.SecurityElement]::Escape($ServiceUser)
$EscapedPython = [System.Security.SecurityElement]::Escape($VenvPython)
$EscapedRoot = [System.Security.SecurityElement]::Escape($ProjectRoot)

# Principal: 模板占位 + 兼容旧 SYSTEM / 任意 UserId 节点
# 用 MatchEvaluator 写回, 避免账号/路径中的 $ 被 Regex 替换语法吃掉
$XmlContent = $XmlContent.Replace(
    '<UserId>REPLACE_WITH_FQ_ETL_SERVICE_USER</UserId>',
    "<UserId>$EscapedUser</UserId>")
$XmlContent = $XmlContent.Replace(
    '<UserId>SYSTEM</UserId>',
    "<UserId>$EscapedUser</UserId>")
# 兜底: 仍残留的 <UserId>...</UserId> 统一写成服务账号 (仅替换首次 Principal 内)
$userIdReplaced = $false
$XmlContent = [regex]::Replace($XmlContent, '<UserId>[^<]*</UserId>', {
    param($m)
    if (-not $script:userIdReplaced) {
        $script:userIdReplaced = $true
        return "<UserId>$EscapedUser</UserId>"
    }
    return $m.Value
})

# Command: 显式写成绝对 venv python (勿只匹配字面 <Command>python</Command>)
$XmlContent = [regex]::Replace($XmlContent, '<Command>[^<]*</Command>', {
    param($m) return "<Command>$EscapedPython</Command>"
})

# WorkingDirectory: 项目根绝对路径
$XmlContent = [regex]::Replace($XmlContent, '<WorkingDirectory>[^<]*</WorkingDirectory>', {
    param($m) return "<WorkingDirectory>$EscapedRoot</WorkingDirectory>"
})

# RunLevel: 强制 LeastPrivilege
$XmlContent = $XmlContent.Replace(
    '<RunLevel>HighestAvailable</RunLevel>',
    '<RunLevel>LeastPrivilege</RunLevel>')
if ($XmlContent -notmatch '<RunLevel>LeastPrivilege</RunLevel>') {
    $runLevelReplaced = $false
    $XmlContent = [regex]::Replace($XmlContent, '<RunLevel>[^<]*</RunLevel>', {
        param($m)
        if (-not $script:runLevelReplaced) {
            $script:runLevelReplaced = $true
            return '<RunLevel>LeastPrivilege</RunLevel>'
        }
        return $m.Value
    })
}

# 安装前硬断言: 禁止占位符 / SYSTEM / 非绝对 Command 漏网
if ($XmlContent -match 'REPLACE_WITH_FQ_ETL_SERVICE_USER') {
    Write-Error "ERROR: XML 仍含 REPLACE_WITH_FQ_ETL_SERVICE_USER 占位符, 未写入服务账号."
    exit 1
}
if ($XmlContent -match '(?i)<UserId>\s*(SYSTEM|NT AUTHORITY\\SYSTEM|S-1-5-18)\s*</UserId>') {
    Write-Error "ERROR: XML Principal 仍是 SYSTEM, 禁止安装."
    exit 1
}
if ($XmlContent -notmatch [regex]::Escape("<UserId>$EscapedUser</UserId>")) {
    Write-Error "ERROR: XML 未写入服务账号 UserId=$ServiceUser"
    exit 1
}
if ($XmlContent -notmatch [regex]::Escape("<Command>$EscapedPython</Command>")) {
    Write-Error "ERROR: XML <Command> 未写成绝对 venv python: $VenvPython"
    exit 1
}
if ($XmlContent -match '(?i)<Command>\s*python(\.exe)?\s*</Command>') {
    Write-Error "ERROR: XML <Command> 仍是裸 python, 必须绝对路径."
    exit 1
}

$TempXml = Join-Path $env:TEMP ("fuqing-etl-task-{0}.xml" -f [guid]::NewGuid().ToString('N'))
# Task Scheduler XML 需要 UTF-16 LE
[System.IO.File]::WriteAllText($TempXml, $XmlContent, [System.Text.Encoding]::Unicode)

try {
    $existing = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false
        Write-Host "✓ 卸载旧任务"
    }

    Register-ScheduledTask -TaskName $TaskName `
        -Xml (Get-Content $TempXml -Raw) `
        -TaskPath $TaskPath `
        -User $ServiceUser `
        -Password $ServicePassword `
        -Force | Out-Null
    Write-Host "✓ Register-ScheduledTask (LeastPrivilege + 专用账号)"

    $task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath
    if (-not $task) {
        Write-Error "任务未注册成功"
        exit 1
    }
    Write-Host "✓ 任务已注册: $($task.TaskPath)$($task.TaskName) 状态=$($task.State)"

    # 安装后核对: Principal ≠ SYSTEM
    $principalUser = $null
    try { $principalUser = $task.Principal.UserId } catch { $principalUser = $null }
    if ([string]::IsNullOrWhiteSpace($principalUser)) {
        Write-Warning "无法读取任务 Principal.UserId, 请手动在任务计划程序中核对 ≠ SYSTEM"
    } elseif ($principalUser -match '(?i)^(SYSTEM|NT AUTHORITY\\SYSTEM|S-1-5-18)$') {
        Write-Error "ERROR: 注册后 Principal 仍是 SYSTEM ($principalUser). 请卸载任务并重装."
        exit 1
    } else {
        Write-Host "✓ Principal 核对通过: $principalUser (≠ SYSTEM)"
    }
}
finally {
    Remove-Item -Force -ErrorAction SilentlyContinue $TempXml
}

Write-Host ""
Write-Host "=== 卸载 ==="
Write-Host "  Unregister-ScheduledTask -TaskName $TaskName -TaskPath '$TaskPath' -Confirm:`$false"
Write-Host ""
Write-Host "=== 手动验证 ==="
Write-Host "  & '$VenvPython' '$ProjectRoot\scripts\run_etl.py' --update"
Write-Host "  # 任务计划程序 → \Fuqing\FuqingETLDaily → 常规/安全选项: 运行账户 ≠ SYSTEM"
Write-Host ""
Write-Host "✓ Windows Task Scheduler ETL 安全安装完成"
