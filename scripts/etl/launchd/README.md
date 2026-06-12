# ETL Launchd 调度配置

> macOS launchd 定时任务配置文件
> 最后更新：2026-06-07

---

## 概述

本目录包含芙清 CRM ETL 系统的 macOS launchd 定时任务配置文件。这些 plist 文件用于自动执行 ETL 跑批、数据备份和清理任务。

---

## 配置文件列表

| 文件 | 用途 | 调度时间 | 说明 |
|------|------|----------|------|
| `com.fuqing.etl.daily.plist` | ETL 每日跑批 | 每日 08:30 | 执行 `python3 scripts/run_etl.py --update` |
| `com.fuqing.duckdb-backup.daily.plist` | DuckDB 每日备份 | 每日 03:30 | 55GB DuckDB 备份 + zstd 压缩 |
| `com.fuqing.backup-cleanup.weekly.plist` | 备份清理 | 每周日 03:00 | 清理 7 天前的备份文件 |
| `com.fuqing.tmp-cleanup.hourly.plist` | 临时文件清理 | 每小时 | 清理 /tmp 下的孤儿文件 |

---

## 安装方法

### 一键安装（推荐）

```bash
cd "/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics"
bash scripts/etl/scheduler/install_macos.sh
```

### 手动安装

```bash
# 1. 复制 plist 到 LaunchAgents
cp scripts/etl/launchd/com.fuqing.etl.daily.plist ~/Library/LaunchAgents/

# 2. 加载任务
launchctl load ~/Library/LaunchAgents/com.fuqing.etl.daily.plist

# 3. 验证
launchctl list | grep fuqing
```

---

## 卸载方法

```bash
# 卸载单个任务
launchctl unload ~/Library/LaunchAgents/com.fuqing.etl.daily.plist
rm ~/Library/LaunchAgents/com.fuqing.etl.daily.plist

# 卸载所有任务
for f in ~/Library/LaunchAgents/com.fuqing.*.plist; do
  launchctl unload "$f"
  rm "$f"
done
```

---

## 调度状态查询

```bash
# 查看所有 fuqing 任务
launchctl list | grep fuqing

# 期望输出（4 个任务）:
# - 126  com.fuqing.backup-cleanup.weekly
# - 0    com.fuqing.tmp-cleanup.hourly
# - 0    com.fuqing.duckdb-backup.daily
# - 1    com.fuqing.etl.daily

# 查看单个任务详情
launchctl list com.fuqing.etl.daily
```

---

## 日志文件

| 任务 | 日志路径 | 说明 |
|------|----------|------|
| ETL 跑批 | `/tmp/fuqing-etl-scheduler.log` | ETL 跑批输出 |
| DuckDB 备份 | `/tmp/fuqing-backup-cleanup.log` | 备份和清理日志 |
| 临时文件清理 | `/tmp/fuqing-subagent-cleanup.log` | subagent 清理日志 |

```bash
# 查看 ETL 跑批日志
tail -f /tmp/fuqing-etl-scheduler.log

# 查看备份日志
tail -f /tmp/fuqing-backup-cleanup.log
```

---

## 调试技巧

### 手动触发任务

```bash
# 手动触发 ETL 跑批
launchctl start com.fuqing.etl.daily

# 手动触发备份
launchctl start com.fuqing.duckdb-backup.daily
```

### 强制重新加载

```bash
# 卸载后重新加载
launchctl unload ~/Library/LaunchAgents/com.fuqing.etl.daily.plist
launchctl load ~/Library/LaunchAgents/com.fuqing.etl.daily.plist
```

### 检查 plist 语法

```bash
# 验证 plist 格式
plutil -lint ~/Library/LaunchAgents/com.fuqing.etl.daily.plist
```

---

## 配置说明

### com.fuqing.etl.daily.plist

- **调度时间**: 每日 08:30
- **执行命令**: `python3 scripts/run_etl.py --update`
- **工作目录**: `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics`
- **PYTHONPATH**: 显式设置为项目根目录
- **日志**: stdout/stderr 重定向到 `/tmp/fuqing-etl-scheduler.log`
- **超时**: 无硬超时（ETL 跑批时间不确定）
- **失败处理**: launchd 自动发送系统通知

### com.fuqing.duckdb-backup.daily.plist

- **调度时间**: 每日 03:30（错开 ETL 跑批时间）
- **执行命令**: `python3 scripts/etl/backup_duckdb.py`
- **备份策略**: shutil.copy2 + zstd 压缩
- **压缩比**: 55GB → 21GB（38.2%）
- **保留策略**: 7 天（由 weekly cleanup 兜底）

### com.fuqing.backup-cleanup.weekly.plist

- **调度时间**: 每周日 03:00
- **执行命令**: `bash scripts/etl/cleanup_backups.sh`
- **清理策略**: 删除 7 天前的备份文件
- **锁机制**: POSIX lock 防并发

### com.fuqing.tmp-cleanup.hourly.plist

- **调度时间**: 每小时
- **执行命令**: `python3 scripts/etl/cleanup_subagent.py`
- **清理策略**: 删除 1h+ 1GB+ 的非白名单文件
- **保护机制**: 排除项目根目录和白名单前缀

---

## 注意事项

1. **首次安装前**: 必须先 `cp .env.example .env` 并配置 `NOTIFY_OPEN_IDS`
2. **Python 路径**: plist 显式设置 `PYTHONPATH`，确保 ETL 脚本能正确导入模块
3. **工作目录**: plist 显式设置 `WorkingDirectory`，确保相对路径正确
4. **日志轮转**: 日志文件会持续增长，建议定期清理或配置 logrotate
5. **系统睡眠**: macOS 睡眠时 launchd 会暂停任务，唤醒后自动恢复

---

## 相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| ETL 调度器文档 | `scripts/etl/scheduler/README.md` | 调度器设计和安装说明 |
| 磁盘治理文档 | `docs/operations/cleanup.md` | 6 层防护详细说明 |
| 运维交接文档 | `docs/reference.md` | 运维操作指南 |

---

*此文件由 AI 维护，最后更新：2026-06-07*
