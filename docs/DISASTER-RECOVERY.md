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
curl http://localhost:8000/api/v1/health/db_size
# 打开浏览器访问 http://localhost:5173
```

---

## 三、P1 - DuckDB 文件损坏

**症状**:`setup.bat` 在"DuckDB 跨 OS 验证"一步 fail,或运行时报 CatalogException

### 3.1 尝试修复

```powershell
cd D:\fuqin-date\fuqing-crm-analytics
.venv\Scripts\activate
python -c "
import duckdb
# 1. 试 CHECKPOINT(同步 WAL)
con = duckdb.connect('D:/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb')
con.execute('CHECKPOINT')
con.close()
# 2. 试 VACUUM INTO 重整
con = duckdb.connect('D:/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb')
con.execute(\"VACUUM INTO 'D:/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm_v2.duckdb'\")
con.close()
print('重整成功')
"
# 验证 v2 文件 OK 后,替换:
move data\processed\fuqing_crm.duckdb data\processed\fuqing_crm.duckdb.broken
move data\processed\fuqing_crm_v2.duckdb data\processed\fuqing_crm.duckdb
```

### 3.2 从备份恢复

```powershell
# 如果有 NAS 备份
# (假设 NAS 共享路径是 \\NAS-IP\fuqing-backup\)
robocopy \\NAS-IP\fuqing-backup\2026-07-16\fuqing_crm.duckdb D:\fuqin-date\fuqing-crm-analytics\data\processed\fuqing_crm.duckdb /Z
# 验证
.venv\Scripts\python -c "import duckdb; con=duckdb.connect(r'D:/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb', read_only=True); print(con.execute('PRAGMA show_tables').fetchdf().head())"
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

```powershell
# 1. 找最近的备份(从 NAS 或本地)
dir D:\fuqin-date\fuqing-crm-analytics\data\processed\backups 2>nul
# 或者 NAS
dir \\NAS-IP\fuqing-backup\2026-07-1* /b 2>nul
# 2. 选一个最近的备份,恢复
robocopy <备份目录>\fuqing_crm.duckdb D:\fuqin-date\fuqing-crm-analytics\data\processed\fuqing_crm.duckdb /Z
# 3. 验证
curl http://localhost:8000/api/v1/health/db_size
```

---

## 六、备份方案(未来)

**当前阶段不备份**(用户决定)。如果将来要加:

### 6.1 群晖 NAS 备份

```powershell
# 写 backup-to-nas.bat
# (参考 setup.bat 里的 DuckDB VACUUM INTO 段)

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
# 每周日 04:00 同步 D 盘到 E 盘
robocopy D:\fuqin-date E:\fuqin-date-backup /MIR /Z /XA:H
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

### 7.2 重要操作前备份

每次 ETL 跑批前:
```powershell
# 复制 DuckDB 一次(快照)
copy data\processed\fuqing_crm.duckdb data\processed\backups\fuqing_crm_%date:~0,10%.duckdb
```

(可加到 run-etl.bat 开头,自动跑)

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
