# ETL Launchd 调度配置

> macOS launchd 定时任务配置文件
> 最后更新：2026-07-26

---

## 概述

本目录包含芙清 CRM ETL 系统的 macOS launchd 模板。ETL 与安全清理可按各自安装手册启用；旧 DuckDB `copy2 + zstd` 备份模板仅供历史追溯，**不得安装或手工触发**。

---

## 配置文件列表

| 文件 | 用途 | 调度时间 | 说明 |
|------|------|----------|------|
| `com.fuqing.etl.daily.plist` | ETL 每日跑批 | 每日 08:30 | 执行 `python3 scripts/run_etl.py --update` |
| `com.fuqing.duckdb-backup.daily.plist` | **LEGACY，不安装** | — | 历史 `copy2 + zstd` 已从脚本移除；该 label 不提供备份能力 |
| `com.fuqing.backup-cleanup.weekly.plist` | 旧备份清理 | 每周日 03:00 | 只在明确存在旧备份时评估，不能替代备份 |
| `com.fuqing.tmp-cleanup.hourly.plist` | 私有临时文件清理 | 每小时 | 仅处理 tracker 登记或项目私有根，删除判断 fail-closed |

---

## 安装方法

### 一键安装（推荐）

```bash
cd "/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics"
bash scripts/etl/scheduler/install_macos.sh
```

> 一键安装脚本不得包含 legacy DuckDB backup/release-check 模板；安装后逐项用 `launchctl list` 核对。

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

# 期望至少核对这些已批准任务；不要以固定数量判断:
# - 0    com.fuqing.tmp-cleanup.hourly
# - 1    com.fuqing.etl.daily

# 查看单个任务详情
launchctl list com.fuqing.etl.daily
```

---

## 日志文件

| 任务 | 日志路径 | 说明 |
|------|----------|------|
| ETL 跑批 | `/tmp/fuqing-etl-scheduler.log` | ETL 跑批输出 |
| 旧备份清理 | `/tmp/fuqing-backup-cleanup.log` | 仅历史 cleanup 日志 |
| 临时文件清理 | `~/Library/Logs/fuqing-subagent-cleanup.log` | 用户私有目录，日志 `0600` |

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

# 禁止手工触发旧 com.fuqing.duckdb-backup.daily
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
- **工作目录**: `/Users/hutou/Desktop/fuqin date/sample-crm-analytics`
- **PYTHONPATH**: 显式设置为项目根目录
- **日志**: stdout/stderr 重定向到 `/tmp/fuqing-etl-scheduler.log`
- **超时**: 无硬超时（ETL 跑批时间不确定）
- **失败处理**: launchd 自动发送系统通知

### com.fuqing.duckdb-backup.daily.plist

- **状态**: **LEGACY / DO NOT INSTALL**
- **原因**: 历史 `shutil.copy2 + zstd` 会制造超大副本且无一致性/恢复演练保证；执行路径现已移除，脚本默认返回 2
- **替代**: 在停写维护窗口按 `docs/maintenance/duckdb-backup-upgrade-checklist.md` 实施 DuckDB 原生一致性副本
- **现有宿主实例**: 先只读核对；卸载/删除必须由 owner 在维护窗口批准

### com.fuqing.backup-cleanup.weekly.plist

- **调度时间**: 每周日 03:00
- **执行命令**: `bash scripts/etl/cleanup_backups.sh`
- **清理策略**: 删除 7 天前的备份文件
- **锁机制**: POSIX lock 防并发

### com.fuqing.tmp-cleanup.hourly.plist

- **调度时间**: 每小时
- **执行命令**: `python3 scripts/etl/cleanup_subagent.py`
- **清理策略**: 仅处理 tracker 登记过期文件或项目专属 `0700` 私有根顶层候选
- **保护机制**: 路径/owner/symlink/hardlink/magic/lsof 多重校验；任何不确定均跳过

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
