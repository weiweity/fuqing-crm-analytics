# 芙清 CRM - 灾难恢复手册

> **本文件给紧急情况用:硬盘坏了 / 系统挂了 / 数据丢了。**

---

## 一、灾难场景分级

| 等级 | 场景 | 恢复时间 | 恢复方法 |
|---|---|---|---|
| **P0** | Windows 系统盘坏(可启动) | 4-8 小时 | 重新装 Windows + 跑 setup.bat |
| **P1** | DuckDB 文件损坏(系统可启动) | 1-2 小时 | 从 NAS / 备份恢复 |
| **P2** | 单个服务挂了(系统可启动) | 5 分钟 | net restart 服务 |
| **P3** | 业务数据需要回滚(ETL 跑错) | 10-30 分钟 | 重新跑 ETL,或恢复 DuckDB |

---

## 二、P0 - 系统盘损坏

**症状**:Windows 起不来 / 蓝屏 / 进不去桌面

**步骤**:

### 2.1 重装 Windows
1. 用 U 盘启动 Windows 安装盘
2. 选"保留个人文件"或"全新安装"
3. 装完后装 Python 3.11 + Node 20 + Git for Windows(参考 README-OPERATIONS)

### 2.2 恢复数据

**如果原 D 盘没坏**(只是系统盘 C 坏了):
- D 盘数据全在,直接装好系统后跑 setup.bat

**如果 D 盘也坏了**(全盘坏):
- 如果有 NAS 备份 → 从 NAS 恢复(看 §3)
- 如果没 NAS 备份 → 联系原负责人,看有没有离线备份

### 2.3 跑 setup.bat

```powershell
# 把数据恢复到 D:\fuqin-date\ 后
cd D:\fuqin-date
.\setup.bat
# 自动:
# - 改 .env 路径
# - 重建 .venv
# - 装前端依赖 + build
# - DuckDB 跨 OS 验证
# - pytest baseline
# - 注册 NSSM 服务
# - 启动 + 健康检查
```

### 2.4 验证

```powershell
curl http://localhost:8000/api/v1/health
# 打开浏览器访问 http://localhost:5173
```

数据库大小、连接池与 Prometheus 指标属于管理员端点。先确认部署机已把独立
`monitor` 账号同时加入 `FQ_CRM_ADMINS` 与 `FQ_CRM_PASSWORDS`，且设置
`FQ_POC_MONITOR_ADMIN_USERNAME=monitor` 和
`FQ_POC_MONITOR_DEDICATED_ACCOUNT=monitor`；禁止复用人工管理员账号。登录后把 Bearer
header 通过 stdin 交给 curl（避免 token 出现在进程参数）：

```powershell
$securePassword = Read-Host "monitor password" -AsSecureString
$monitorPassword = [System.Net.NetworkCredential]::new("", $securePassword).Password
$loginBody = @{
  username = $env:FQ_POC_MONITOR_ADMIN_USERNAME
  password = $monitorPassword
} | ConvertTo-Json
$token = (Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/auth/login `
  -ContentType application/json -Body $loginBody).token
$curlAuth = "header = `"Authorization: Bearer $token`""

$curlAuth | curl.exe --config - http://localhost:8000/api/v1/health/db_size
$curlAuth | curl.exe --config - http://localhost:8000/api/v1/health/pool
$curlAuth | curl.exe --config - http://localhost:8000/api/v1/health/metrics
Remove-Variable token, curlAuth, loginBody, monitorPassword, securePassword
```

---

## 三、P1 - DuckDB 文件损坏

**症状**:`setup.bat` 在"DuckDB 跨 OS 验证"一步 fail,或运行时报 CatalogException

### 3.1 先保全现场，再尝试原生重建

```powershell
cd D:\fuqin-date\fuqing-crm-analytics
.venv\Scripts\activate
# 1. 停 API / ETL，确认没有进程持有 DB/WAL
# 2. 不覆盖原文件；先改名保全现场
move data\processed\fuqing_crm.duckdb data\processed\fuqing_crm.duckdb.broken
```

DuckDB 不支持 SQLite 的 `VACUUM INTO`。如果 `.broken` 文件仍能只读打开，按
[`maintenance/duckdb-backup-upgrade-checklist.md`](maintenance/duckdb-backup-upgrade-checklist.md)
用 `ATTACH ... (READ_ONLY)` + `COPY FROM DATABASE` 创建一个**新文件**；若只读打开也失败，直接走下一节从已验证备份恢复。不要在损坏文件上继续写入或执行 `CHECKPOINT`。

### 3.2 从备份恢复

只允许使用已经按
[`maintenance/duckdb-backup-upgrade-checklist.md`](maintenance/duckdb-backup-upgrade-checklist.md)
完成过恢复演练的备份。复制前必须停止 API、ETL、计划任务及 ad-hoc 写任务，并确认
生产 DB/WAL 没有持锁进程。先复制到候选文件并只读验证，禁止直接覆盖生产文件。

```powershell
$ErrorActionPreference = "Stop"
cd D:\fuqin-date\fuqing-crm-analytics
net stop fuqing-uvicorn
if ($LASTEXITCODE -ne 0) {
  throw "failed to stop fuqing-uvicorn; restore aborted"
}
# 同时暂停本机实际使用的 ETL/备份计划任务；未确认停写不得继续

$source = "\\NAS-IP\fuqing-backup\2026-07-16\fuqing_crm.duckdb"
$db = "D:\fuqin-date\fuqing-crm-analytics\data\processed\fuqing_crm.duckdb"
$candidate = "D:\fuqin-date\fuqing-crm-analytics\data\processed\fuqing_crm.restore-candidate.duckdb"
$stamp = Get-Date -Format yyyyMMddHHmmss
$quarantine = "$db.pre-restore-$stamp"
$failedCandidate = "$db.failed-restore-$stamp"

if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
  throw "verified backup not found: $source"
}
if (Test-Path -LiteralPath $candidate) {
  throw "restore candidate already exists: $candidate"
}
Copy-Item -LiteralPath $source -Destination $candidate

# 对候选文件做新进程只读验证；这里应再补项目登记的 SHA-256、关键表行数和业务日期抽检
.venv\Scripts\python -c "import duckdb; p=r'D:/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.restore-candidate.duckdb'; con=duckdb.connect(p, read_only=True); row=con.execute('SELECT COUNT(*), MAX(pay_time) FROM orders').fetchone(); con.close(); assert row and row[0] > 0 and row[1] is not None, 'orders sanity check failed'; print(row)"
if ($LASTEXITCODE -ne 0) {
  throw "candidate validation failed; production DB was not changed"
}

# 验证成功后才切换；原生产文件留作取证，不删除
$hadCurrent = Test-Path -LiteralPath $db -PathType Leaf
if ($hadCurrent) {
  Move-Item -LiteralPath $db -Destination $quarantine
}
try {
  Move-Item -LiteralPath $candidate -Destination $db
} catch {
  if ($hadCurrent -and -not (Test-Path -LiteralPath $db)) {
    Move-Item -LiteralPath $quarantine -Destination $db
  }
  throw
}

# 用新进程再次验证最终路径，成功后才恢复服务
.venv\Scripts\python -c "import duckdb; p=r'D:/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb'; con=duckdb.connect(p, read_only=True); row=con.execute('SELECT COUNT(*), MAX(pay_time) FROM orders').fetchone(); con.close(); assert row and row[0] > 0 and row[1] is not None, 'orders sanity check failed'; print(row)"
if ($LASTEXITCODE -ne 0) {
  Move-Item -LiteralPath $db -Destination $failedCandidate
  if ($hadCurrent) {
    Move-Item -LiteralPath $quarantine -Destination $db
  }
  throw "final-path validation failed; service remains stopped"
}
net start fuqing-uvicorn
if ($LASTEXITCODE -ne 0) {
  throw "restored DB passed validation, but fuqing-uvicorn failed to start"
}
```

---

## 四、P2 - 单个服务挂了

**症状**:某服务 status = STOPPED,起不来

### 4.1 手动重启

```powershell
# 看哪个挂了
sc query fuqing-uvicorn
sc query fuqing-frontend

# 重启
net stop fuqing-uvicorn && net start fuqing-uvicorn
net stop fuqing-frontend && net start fuqing-frontend
```

### 4.2 还不起来

```powershell
# 看日志
powershell -Command "Get-Content $env:TEMP\fuqing-uvicorn.log -Tail 50"

# 常见原因:
# 1. 端口被占
netstat -ano | findstr :8000
# 找到占用 PID,kill:
taskkill /PID <PID> /F

# 2. Python venv 坏了
# 重新建 venv
cd D:\fuqin-date\fuqing-crm-analytics
rmdir /s /q .venv
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. 前端 node_modules 坏了
cd frontend-vue3
rmdir /s /q node_modules
npm install
npm run build
```

### 4.3 还不行,跑 setup.bat 重装

```powershell
# setup.bat 是幂等的,会清理旧的 venv/node_modules 重建
cd D:\fuqin-date
.\setup.bat
```

---

## 五、P3 - 业务数据回滚

**症状**:ETL 跑了错的数据,业务需要回退

### 5.1 软回滚(快,推荐)

```powershell
# 1. 停 uvicorn
net stop fuqing-uvicorn
# 2. 重新跑 ETL(只读 parquet cache + 原始数据,不破坏现有 DuckDB 太多)
D:\fuqin-date\run-etl.bat --update
# 3. 跑完重启
# (run-etl.bat 末尾会自动重启)
```

### 5.2 硬回滚(从备份恢复)

硬回滚必须完整执行 §3.2 的停写、候选文件复制、只读抽检、保全当前文件、
切换和重启流程。不得因为“文件日期最新”就选择备份；只接受已经登记 SHA-256、
关键表抽检结果并完成恢复演练的恢复点。若没有这种恢复点，停止硬回滚并升级为
P1 数据恢复事件。

---

## 六、备份方案（独立运维项目）

仓库旧 `copy2 + zstd` launchd 模板不构成可恢复备份，禁止直接安装。先按
[`maintenance/duckdb-backup-upgrade-checklist.md`](maintenance/duckdb-backup-upgrade-checklist.md)
完成原生一致性副本和恢复演练，再配置 NAS/离线介质。

### 6.1 群晖 NAS 备份

```powershell
# 写 backup-to-nas.bat：先生成并验证 DuckDB 原生一致性副本，
# 再把已验证副本传输到 NAS；不要热拷贝正在使用的生产 DB。

# 配 Windows Task Scheduler 每日 03:00
$action = New-ScheduledTaskAction -Execute "D:\fuqin-date\backup-to-nas.bat"
$trigger = New-ScheduledTaskTrigger -Daily -At "03:00"
Register-ScheduledTask -TaskName "fuqing-backup-to-nas" -Action $action -Trigger $trigger
```

**保留策略**(NAS 端)写一个 PowerShell 脚本清理:
```powershell
# 每天跑一次,删 7 天前 daily
Get-ChildItem \\NAS-IP\fuqing-backup\ | Where-Object { $_.PSIsContainer -and $_.Name -match "^\d{4}-\d{2}-\d{2}$" } | ForEach-Object {
    $date = [DateTime]::ParseExact($_.Name, "yyyy-MM-dd", $null)
    if ($date -lt (Get-Date).AddDays(-7)) { Remove-Item $_.FullName -Recurse -Force }
}
```

### 6.2 本地二级备份(D 盘 → E 盘)

如果系统有双硬盘(系统盘 C + 数据盘 D + 备份盘 E):
```powershell
# 只复制已经完成原生一致性校验的备份目录，不同步正在使用的生产 DB 目录
$verified = "D:\fuqin-verified-backups\2026-07-16"
$offsite = "E:\fuqin-date-backup\2026-07-16"
robocopy $verified $offsite /E /Z /COPY:DAT
```

---

## 七、预防措施(降低灾难概率)

### 7.1 每周自检

```powershell
# 每周一跑一次(可加到 Task Scheduler)
D:\fuqin-date\ai-help.bat
# 看:
# - [10] 磁盘空间(D 盘 > 50GB)
# - [8] Python / Node / DuckDB 版本(都正常)
# - [9] Git status(无未提交修改)
```

### 7.2 高风险操作前恢复点

升级 DuckDB、修改表结构或执行不可逆数据修复前，必须先安排停写窗口，按
[`maintenance/duckdb-backup-upgrade-checklist.md`](maintenance/duckdb-backup-upgrade-checklist.md)
生成原生一致性副本并完成恢复抽检。禁止在 `run-etl.bat` 开头自动 `copy` 正在使用的
生产 `.duckdb`；没有已验证恢复点时推迟高风险操作。

### 7.3 监控告警(可选)

如果有 NAS,加每天 04:00 大小告警:
```powershell
# 每周一 09:00 跑 disk-check
$size = (Get-Item D:\fuqin-date\fuqing-crm-analytics\data\processed\fuqing_crm.duckdb).Length / 1GB
if ($size -gt 200) { msg * "芙清 CRM DuckDB 超过 200GB,建议清理" }
```

---

## 八、应急联系

| 场景 | 联系人 | 联系方式 |
|---|---|---|
| 任何问题,优先跑 ai-help.bat + 截图发原负责人 | 原负责人 | 微信/飞书 |
| 原负责人联系不上 | 公司 IT | 看 HANDOVER.md |
| 紧急(数据丢了) | 主管 | 看 HANDOVER.md |

**重要**:任何数据丢失场景,**不要做任何操作**,先联系。

---

**最后更新:2026-07-06  |  版本:v0.4.14.43 解耦后**
