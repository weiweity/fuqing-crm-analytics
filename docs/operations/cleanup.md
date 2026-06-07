# 芙清 CRM — 6 层磁盘治理 (cleanup)

> 文档版本: 2026-06-07 Sprint 7 P2 收口
> 适用版本: v0.4.14.11+ (Sprint 4 + Sprint 5 + Sprint 6 全部防护已落地)
> 作者: Claude Opus 4.8 (sprint7 P2 subagent 1)
> 前置文档: `docs/handoff-2026-06-05.md`, `docs/SPRINT-7-PLAN.md`

---

## TL;DR

芙清 CRM 经历 6/1-6/4 调试期间 `/private/tmp` 累积 **7 个 38-44GB 的 duckdb 孤儿** (349GB 污染, 磁盘 22%→53%) 后, 6/5 Sprint 1 治理落地 4 层防护, Sprint 4 P0-2 加 5 层 DuckDB 每日备份, **Sprint 6 P0-3 (2026-06-07) 加第 6 层 hourly subagent 兜底** (教训: 5 层防护因 `FQ_TMP_PREFIXES` 白名单设计, 拦不住 subagent 走手动 `shutil.copy2` 复制 55GB × 8 = 440GB 在 `/private/tmp/p0_3_dive/`).

**当前状态**: 6 层防护全部 loaded, 磁盘恢复 22% 占用, `/private/tmp` 只剩 3 个 1-3MB 仿真副本.

---

## 1. 6 层防护总览

| # | 层 | 路径 | 触发时机 | 工作原理 | 容量阈值 |
|---|---|---|---|---|---|
| 1 | **atexit 钩子** (Sprint 1 治理) | `scripts/etl/cli.py:_cleanup_fq_tmp_orphans` | ETL 进程退出时 (atexit.register 在 main() 入口) | `FQ_TMP_PREFIXES` 白名单扫 `/private/tmp`, 24h+ / 5 文件 / 100GB cap, marker 异常退出检测, symlink 跳过, 软失败 + 持久日志 | 24h+ / 5 文件 / 100GB |
| 2 | **zshrc 告警** (Sprint 1 治理) | `~/.zshrc:_check_fq_tmp_orphans` | 每次 zsh 启动 (precmd hook) | 扫 `/private/tmp` 下 1GB+ `.duckdb`, 50GB+ 告警. **只告警不删** (避免误删活文件) | 50GB+ 告警 |
| 3 | **workbuddy cache** (Sprint 1 治理) | `~/.workbuddy/cache/fq-etl-validation/` | 调试时主动 cp | 30 天 TTL, 时间戳命名 (`{session}_{step}_{ts}.duckdb`), 不污染 /tmp | 30 天 TTL |
| 4 | **launchd weekly cleanup** (Sprint 1 治理) | `scripts/etl/cleanup_backups.sh` + `com.fuqing.backup-cleanup.weekly.plist` | 每周日 03:00 (StartCalendarInterval Weekday=0 Hour=3) | `data/processed/backups/` 下 mtime > 7 天的 `.parquet` / `.duckdb` 清理, mkdir-based lock 防双跑 | 7 天保留 |
| 5 | **launchd daily backup** (Sprint 4 P0-2) | `scripts/etl/backup_duckdb.py` + `com.fuqing.duckdb-backup.daily.plist` | 每日 03:30 (StartCalendarInterval Hour=3 Minute=30) | `shutil.copy2` + zstd 压缩: 55GB DuckDB → 21GB, 7 天保留由 Layer 4 兜底 | 55GB → 21GB |
| 6 | **launchd hourly subagent cleanup** (Sprint 6 P0-3) | `scripts/etl/cleanup_subagent.py` + `com.fuqing.tmp-cleanup.hourly.plist` | 每 1 小时 (StartInterval=3600, RunAtLoad=true) | 扫 `/private/tmp` + `/tmp` 下 1h+ 1GB+ 非白名单, 排除项目根 + Layer 1 状态文件 + 代码扩展名, 5 文件 / 100GB cap. **兜底 subagent 走手动 `shutil.copy2` 漏出来的非 fq_ 前缀孤儿** | 1h+ / 1GB+ / 5 文件 / 100GB |

**关键设计**:
- **Layer 1+2+3 是 /tmp 路径** (Sprint 1 治理核心, 清理频率: ETL 退出 + zsh 启动 + 调试主动)
- **Layer 4+5 是 data 目录 + 备份灾备** (Sprint 1+4 落地, 清理/备份频率: 周 + 日)
- **Layer 6 是 subagent 路径兜底** (Sprint 6 P0-3 教训驱动, 频率: 小时级)
- 6 层防护独立运行互不依赖, 任何 1 层失效其余层仍兜底

---

## 2. 各层详细说明

### 2.1 Layer 1: atexit 钩子 (主防线)

| 项 | 值 |
|---|---|
| 代码 | `scripts/etl/cli.py:_cleanup_fq_tmp_orphans()` |
| 注册点 | `cli.py:612` (`atexit.register(_cleanup_fq_tmp_orphans)`) |
| 触发 | ETL 进程退出 (正常 + 异常 atexit 都会跑, 但 kill -9 不触发) |
| 白名单 | `FQ_TMP_PREFIXES = ("/private/tmp/_fq_ro*", "/private/tmp/fuqing_*")` |
| 常量 | `_FQ_TMP_MAX_DELETE_PER_RUN=5`, `_FQ_TMP_MAX_DELETE_BYTES_PER_RUN=100GB`, `_FQ_TMP_MIN_AGE_HOURS=24` |
| Marker | `/tmp/fuqing-etl-marker.json` (F3 修复: main() 入口写, atexit 删, 缺失=上次异常退出) |
| Log | `/tmp/fuqing-tmp-cleanup.log` (软失败, 失败只 log 不 raise) |
| CLI 入口 | `python3 scripts/etl/cli.py --cleanup-tmp` (紧急手动触发) |

**F3 marker 协议** (不要 rm):
- marker 在 `cli.py:607 _write_fq_etl_marker()` 写
- marker 在 `_cleanup_fq_tmp_orphans()` 入口读, 缺失=保守模式清理 + 日志标注 "上次异常退出"
- marker 在 cleanup 退出时删 (不论原本是否存在)
- **运维不要 rm 这个文件**, 删了下次 cleanup 会误判"上次异常退出"

---

### 2.2 Layer 2: zshrc 告警 (人因防线)

| 项 | 值 |
|---|---|
| 函数 | `~/.zshrc:_check_fq_tmp_orphans` |
| 注册点 | `~/.zshrc:47` (`precmd_functions+=(_check_fq_tmp_orphans)`) |
| 触发 | 每个 zsh 提示符前 (precmd hook) |
| 范围 | `/private/tmp` 下 1GB+ `.duckdb` |
| 阈值 | 50GB 占用告警 (53687091200 bytes) |
| 行为 | **只告警, 不删** (避免误删活文件) |
| 提示 | `[fq-alert] /private/tmp 下 .duckdb 孤儿占用 ${total_gb}GB（阈值 50GB）` + 列出文件 + 清理命令 |

**为什么只告警**: 删除活文件会破坏正在跑批的 ETL 进程, 告警让人判断后再处理.

---

### 2.3 Layer 3: workbuddy cache (调试便捷)

| 项 | 值 |
|---|---|
| 路径 | `~/.workbuddy/cache/fq-etl-validation/` |
| 触发 | 调试时主动 cp 持久化 (subagent 调试 / IDE debugging) |
| 命名 | `{session}_{step}_{ts}.duckdb` (时间戳避免冲突) |
| TTL | 30 天 |
| 协议 | 见 `~/.workbuddy/cache/fq-etl-validation/README.md` (Sprint 1 治理落地) |
| 优势 | 不污染 /tmp, 可追溯, 重跑 ETL 不用重做 |

---

### 2.4 Layer 4: launchd weekly cleanup (data 目录治理)

| 项 | 值 |
|---|---|
| 脚本 | `scripts/etl/cleanup_backups.sh` |
| Plist | `scripts/etl/launchd/com.fuqing.backup-cleanup.weekly.plist` |
| 调度 | 每周日 03:00 (StartCalendarInterval Weekday=0 Hour=3 Minute=0) |
| 范围 | `data/processed/backups/` 下 `.parquet` + `.duckdb` |
| 规则 | mtime > 7 天删除 |
| 锁 | `/tmp/fuqing-backup-cleanup.lock.d` (mkdir-based, POSIX 兼容, macOS 无 flock) |
| Log | `/tmp/fuqing-backup-cleanup.log` (plain text, launchd 只看 exit code) |
| 软失败 | 单文件 rm 失败只 log warning, 不 exit 1 |

**安装**:
```bash
cp scripts/etl/cleanup_backups.sh /usr/local/bin/
chmod +x /usr/local/bin/cleanup_backups.sh
cp scripts/etl/launchd/com.fuqing.backup-cleanup.weekly.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.fuqing.backup-cleanup.weekly.plist
```

---

### 2.5 Layer 5: launchd daily backup (Sprint 4 P0-2)

| 项 | 值 |
|---|---|
| 脚本 | `scripts/etl/backup_duckdb.py` |
| Plist | `scripts/etl/launchd/com.fuqing.duckdb-backup.daily.plist` |
| 调度 | 每日 03:30 (StartCalendarInterval Hour=3 Minute=30, 错开 Layer 4 周日 03:00) |
| 范围 | `data/processed/fact_rfm.duckdb` 复制到 `data/processed/backups/` |
| 压缩 | `shutil.copy2` + zstd (55GB → 21GB, 压缩比 ~2.6x) |
| 保留 | 7 天 (由 Layer 4 兜底清理) |
| Log | `/tmp/fuqing-duckdb-backup.log` |

**为什么是 daily + 7 天保留**: data 灾备, 万一 ETL 跑批写错或磁盘损坏可回滚. 7 天覆盖周日-周六完整周.

---

### 2.6 Layer 6: launchd hourly subagent cleanup (Sprint 6 P0-3)

| 项 | 值 |
|---|---|
| 脚本 | `scripts/etl/cleanup_subagent.py` |
| Plist | `scripts/etl/launchd/com.fuqing.tmp-cleanup.hourly.plist` |
| 调度 | 每 1 小时 (StartInterval=3600, RunAtLoad=true) |
| 范围 | `/private/tmp` + `/tmp` 下 1h+ 1GB+ 非白名单文件 |
| 白名单 | `FQ_TMP_PREFIXES` 留给 Layer 1 (`_fq_ro*`, `fuqing_*`) |
| 保护名单 | Layer 1 状态文件 (log/marker/lock) + Layer 6 自身 log + project root |
| 排除扩展名 | `.py .sh .json .log .txt .md .yml .yaml .toml .lock .pid` |
| 常量 | `_MAX_DELETE_PER_RUN=5`, `_MAX_DELETE_BYTES_PER_RUN=100GB`, `_MIN_AGE_HOURS=1`, `_MIN_SIZE_BYTES=1GB` |
| 软失败 | OSError 不 raise, 只 log `/tmp/fuqing-subagent-cleanup.log` |
| symlink | 跳过 (跟 Layer 1 一致, 保守) |
| CLI 入口 | `python3 scripts/etl/cleanup_subagent.py [--dry-run]` |

**为什么需要 Layer 6** (Sprint 5 deep dive 教训):
- Sprint 5 deep dive subagent 跑 5 真实验时, 走手动 `shutil.copy2` 复制 production 55GB × 8 = 440GB 到 `/private/tmp/p0_3_dive/`
- 5 层防护全没拦: Layer 1-5 是 ETL 跑批路径设计 (`FQ_TMP_PREFIXES` 白名单), subagent 路径不触发
- Layer 6 不依赖白名单, 主动扫所有 1h+ 1GB+ 巨型文件, 排除项目根, 兜底 subagent 漏出来的非 fq_ 前缀孤儿

---

## 3. 紧急清理命令

### 3.1 Layer 1 紧急触发 (CLI 入口)

```bash
# 清理 /private/tmp 下 fq_ 系列孤儿 (24h+ / 5 文件 / 100GB cap)
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
PYTHONPATH="$(pwd)" python3 scripts/etl/cli.py --cleanup-tmp

# 行为:
# 1. 显式 unregister atexit (避免 sys.exit 触发第二次 cleanup)
# 2. 调 _cleanup_fq_tmp_orphans() 跑清理
# 3. 打印 "完成：删除 N 个文件"
# 4. 提示 "审计日志：/tmp/fuqing-tmp-cleanup.log"
# 5. sys.exit(0) 退出
```

### 3.2 Layer 6 紧急触发 (subagent 路径)

```bash
# 扫 /private/tmp + /tmp 下 1h+ 1GB+ 非白名单 (含 dry-run 模式)
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
PYTHONPATH="$(pwd)" python3 scripts/etl/cleanup_subagent.py

# 只扫描不删 (供测试 / 运维验证用)
PYTHONPATH="$(pwd)" python3 scripts/etl/cleanup_subagent.py --dry-run

# 输出 JSON: {deleted_count, freed_bytes, errors, candidates_scanned, dry_run}
```

### 3.3 Layer 4 紧急触发 (data 目录)

```bash
# 手动跑 Layer 4 (绕过 launchd 调度)
bash /usr/local/bin/cleanup_backups.sh
# 或在 repo 内:
bash scripts/etl/cleanup_backups.sh

# 行为: 扫 data/processed/backups/ 下 mtime > 7 天的 .parquet / .duckdb 删除
# 输出: "[TIMESTAMP] backups cleanup: before=N files/XMB → after=N files/YMB, deleted=N files/ZMB"
```

### 3.4 Layer 5 紧急触发 (DuckDB 备份)

```bash
# 手动跑 Layer 5
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 scripts/etl/backup_duckdb.py

# 行为: shutil.copy2 复制 + zstd 压缩, 55GB → 21GB, 输出到 data/processed/backups/
```

### 3.5 手动 rm (应急, **仅在所有 CLI 失败时**)

```bash
# ⚠️ 警告: 手动 rm 不会写审计日志, 不受 cap 保护, 慎用
# Layer 1 白名单:
rm -f /private/tmp/_fq_ro*.duckdb /private/tmp/fuqing_*.duckdb

# Layer 2 提示的清理命令 (来自 ~/.zshrc):
rm /private/tmp/{_fq_ro,_fq_ro2,fuqing_*}.duckdb /private/tmp/claude-501/tmp*.duckdb

# 严禁 rm (见 §5 重要协议):
#   - /tmp/fuqing-etl-marker.json (F3 marker)
#   - /private/tmp/_fq_* (Layer 1 自动处理, 强删留 marker 孤儿)
#   - /Library/Caches/ms-playwright/chromium_headless_shell-1208/ (gstack browse 唯一可用 headless shell)
```

---

## 4. launchd 调度状态

### 4.1 4 个服务的 plist 装载期望

| # | Label | 调度 | 脚本 | 状态期望 |
|---|---|---|---|---|
| 1 | `com.fuqing.backup-cleanup.weekly` | 每周日 03:00 | `cleanup_backups.sh` | loaded + exit 0 |
| 2 | `com.fuqing.duckdb-backup.daily` | 每日 03:30 | `backup_duckdb.py` | loaded + exit 0 |
| 3 | `com.fuqing.tmp-cleanup.hourly` | 每 1 小时 (StartInterval=3600) | `cleanup_subagent.py` | loaded + exit 0 |
| 4 | (历史) `com.fuqing.etl.daily` | 每日 08:30 | ETL 跑批 | **已废弃**, Sprint 5 后改为手动触发 |

**注**: 实际 launchd list 应有 **3 行** (Layer 4 + 5 + 6), 第 4 个 ETL daily 已废弃 (走 12 步流程手动跑). 如果 handoff 文档说"4 行"是 6/5 Sprint 1 治理时的状态, **当前期望 3 行** (weekly + daily backup + hourly).

### 4.2 状态查询命令

```bash
# 查询所有 fuqing 服务
launchctl list | grep fuqing
# 期望输出 (3 行):
# -        0       com.fuqing.backup-cleanup.weekly
# -        0       com.fuqing.duckdb-backup.daily
# -        0       com.fuqing.tmp-cleanup.hourly

# PID 列: 最近一次跑的 PID
# Status 列: 0 = 上次 exit 0, 非 0 = 失败

# 查看具体服务详情
launchctl list com.fuqing.tmp-cleanup.hourly

# 手动 trigger (立即跑一次, 不等调度)
launchctl kickstart -k gui/$(id -u)/com.fuqing.tmp-cleanup.hourly

# 卸载 + 重新装载 (调试时用)
launchctl unload ~/Library/LaunchAgents/com.fuqing.tmp-cleanup.hourly.plist
launchctl load ~/Library/LaunchAgents/com.fuqing.tmp-cleanup.hourly.plist
```

### 4.3 plist 文件路径

所有 plist 源文件在 repo 内, 装载时 cp 到 `~/Library/LaunchAgents/`:

| plist 源文件 | 装载目标 |
|---|---|
| `scripts/etl/launchd/com.fuqing.backup-cleanup.weekly.plist` | `~/Library/LaunchAgents/` |
| `scripts/etl/launchd/com.fuqing.duckdb-backup.daily.plist` | `~/Library/LaunchAgents/` |
| `scripts/etl/launchd/com.fuqing.tmp-cleanup.hourly.plist` | `~/Library/LaunchAgents/` |

---

## 5. 重要协议 (不要违反)

### 5.1 严禁 rm 的文件

| 路径 | 原因 | 处理方式 |
|---|---|---|
| `/tmp/fuqing-etl-marker.json` | **F3 marker**, Layer 1 异常退出检测依据, 删了下次 cleanup 误判"上次异常退出" | Layer 1 自动管理 (写/读/删), 运维不动 |
| `/private/tmp/_fq_ro*.duckdb` / `fuqing_*.duckdb` | Layer 1 白名单内, atexit 自动处理 (24h+ 才删), 强删会留 marker 孤儿 + 审计日志断档 | 等 Layer 1 自动清, 紧急用 `--cleanup-tmp` CLI |
| `/private/tmp/claude-501/tmp*.duckdb` | 调试残留, Layer 2 zshrc 告警会列出, 强删可能误伤活文件 | 优先用 `--cleanup-tmp` 走 cap 清理 |
| `/Library/Caches/ms-playwright/chromium_headless_shell-1208/` | gstack browse 唯一可用的 headless shell, 删了 /qa 跑不动 | 严禁 rm, 升 playwright 版本用 `playwright install` 不要 `--force` |
| `/Users/hutou/Desktop/fuqin date/` (整个项目根) | Layer 6 排除路径, 业务文件, 不会误删 | 严禁 Layer 6 涉及, 实际保护名单已写死 |
| `~/.workbuddy/cache/fq-etl-validation/` 30 天内文件 | Layer 3 主动 cp 持久化, 重跑 ETL 不用重做 | 30 天后 Layer 3 自动清 |

### 5.2 F3 marker 协议

- **写入**: `cli.py:607 _write_fq_etl_marker()` 在 main() 入口写 (atexit.register 之前)
- **读取**: `_cleanup_fq_tmp_orphans()` 入口读
- **删除**: cleanup 退出时删 (不论原本是否存在)
- **运维**: 不要 rm `/tmp/fuqing-etl-marker.json`
- **缺失语义**: 上次 ETL 异常退出 (kill -9 / os._exit / OOM killer)
- **存在语义**: 正常 ETL 退出
- **清理行为**: 不论 marker 状态都按 cap 清理, 只是日志标注不同 (保守模式 vs 正常模式)

### 5.3 /private/tmp 与 /tmp 关系 (macOS)

- macOS 上 `/tmp` 是 `/private/tmp` 的 symlink
- Layer 1 只扫 `/private/tmp/_fq_ro*` / `/private/tmp/fuqing_*` (显式, 不依赖 symlink)
- Layer 6 扫 `_SCAN_ROOTS = ("/private/tmp", "/tmp")` 两个根, 用 `os.path.realpath()` 去重 (避免同一文件扫两次)
- **不要 rm `/private/tmp/_fq_*` 强制清理**: Layer 1 会处理, 强删会留 marker 孤儿

### 5.4 ms-playwright 缓存 (gstack browse)

- 路径: `/Library/Caches/ms-playwright/chromium_headless_shell-1208/`
- 版本: Chrome Headless Shell 145.0.7632.6 (1208 build)
- 用途: gstack browse 内嵌 playwright 1.58.0, `/qa` 跑网站 dogfooding 唯一可用
- **严禁 rm**, pip 装更高 playwright 版本不影响, 只 `playwright install` 时小心别 `--force` 覆盖 1208 binary
- 教训: 6/5 治理时 investigate 修复 gstack browse 版本 mismatch, 手动 curl 装 1208 修好

---

## 6. 审计与状态查询 (6 个 log 路径)

| # | 路径 | 写入方 | 内容 | 容量增长 | 监控方式 |
|---|---|---|---|---|---|
| 1 | `/tmp/fuqing-tmp-cleanup.log` | Layer 1 `_cleanup_fq_tmp_orphans()` | atexit 清理记录: marker 状态 + 删除文件清单 + 容量释放 | ~60KB+ 持续增长 | `tail -f` + grep "DELETED" |
| 2 | `/tmp/fuqing-backup-cleanup.log` | Layer 4 `cleanup_backups.sh` | weekly 清理 summary: before/after count+MB + deleted 文件名 | 每周 ~1KB | `tail -f` 每周日 03:00 后看 |
| 3 | `/tmp/fuqing-duckdb-backup.log` | Layer 5 `backup_duckdb.py` | daily 备份记录: 源文件 size + 压缩后 size + 耗时 | 每日 ~1KB | `tail -f` 每日 03:30 后看 |
| 4 | `/tmp/fuqing-subagent-cleanup.log` | Layer 6 `cleanup_subagent.py` + plist stdout/stderr | hourly 扫描: candidates 清单 + DELETED 记录 + 错误 | 小时级 ~1KB/次 | `tail -f` + grep "DELETED\|ERROR" |
| 5 | `/tmp/fuqing-backup-cleanup.lock.d/` | Layer 4 mkdir-based lock | 防双跑锁目录, 跑完 rmdir | 临时, 不累积 | `ls -la /tmp/fuqing-*.lock.d/` |
| 6 | `/tmp/fuqing-etl-marker.json` | Layer 1 `_write_fq_etl_marker()` | F3 marker, 写入时间 + PID | 临时 (ETL 运行时存在, 退出时删) | `cat /tmp/fuqing-etl-marker.json` |

**查询命令速查**:

```bash
# 1. Layer 1 清理记录
tail -20 /tmp/fuqing-tmp-cleanup.log
grep "DELETED" /tmp/fuqing-tmp-cleanup.log | tail -10

# 2. Layer 4 weekly summary
tail -10 /tmp/fuqing-backup-cleanup.log
grep "deleted=" /tmp/fuqing-backup-cleanup.log | tail -4

# 3. Layer 5 daily backup
tail -10 /tmp/fuqing-duckdb-backup.log

# 4. Layer 6 hourly subagent
tail -30 /tmp/fuqing-subagent-cleanup.log
grep -E "DELETED|ERROR|cap hit" /tmp/fuqing-subagent-cleanup.log | tail -20

# 5. Layer 4 lock (应该不存在, 存在 = 进程跑飞)
ls -la /tmp/fuqing-backup-cleanup.lock.d/ 2>/dev/null && echo "WARN: lock 残留" || echo "OK: 无 lock"

# 6. Layer 1 marker (应该不存在, 存在 = ETL 在跑)
cat /tmp/fuqing-etl-marker.json 2>/dev/null && echo "WARN: marker 存在" || echo "OK: 无 marker"
```

---

## 7. Sprint 5 deep dive 教训 (Layer 6 存在的原因)

### 7.1 事件回顾

| 时间 | 事件 |
|---|---|
| 2026-06-06 上午 | Sprint 5 deep dive, subagent 跑 5 真实验, 每次走手动 `shutil.copy2` 复制 production 55GB duckdb |
| 2026-06-06 下午 | 5 次实验结束, `/private/tmp/p0_3_dive/` 累积 55GB × 8 = 440GB 巨型 duckdb (含中间态) |
| 2026-06-06 下午 | **5 层防护全没拦**: Layer 1-5 是 ETL 跑批路径设计, `FQ_TMP_PREFIXES` 白名单只覆盖 `_fq_ro*` / `fuqing_*`, subagent 走手动 shutil.copy2 用 `p0_3_dive/` 命名, 不在白名单 |
| 2026-06-06 晚 | 5 层防护失效教训总结, Sprint 6 P0-3 提案: 加第 6 层兜底 |
| 2026-06-07 | Sprint 6 P0-3 commit `6423b9b feat(cleanup): sprint6 P0-3 5 层 → 6 层防护 (cleanup_subagent.py + launchd hourly)` |

### 7.2 5 层失效原因分析

| 层 | 为什么失效 |
|---|---|
| Layer 1 (atexit) | ETL 退出时跑, subagent 调试过程 ETL 不退出; 且 `FQ_TMP_PREFIXES` 白名单不含 `p0_3_dive` |
| Layer 2 (zshrc) | 50GB+ 才告警, 440GB 会告警但只告警不删, 等待人工 |
| Layer 3 (workbuddy) | subagent 主动 cp 才用, deep dive 走 shutil.copy2 不走 workbuddy |
| Layer 4 (weekly) | 扫 `data/processed/backups/`, 不扫 `/private/tmp` |
| Layer 5 (daily backup) | 复制 production duckdb 到 backups, 不清理 /tmp |

### 7.3 Layer 6 设计原则 (针对教训)

1. **不依赖白名单**: 扫所有 1GB+ 巨型文件, 排除名单用 `_PROTECTED_BASENAMES` (白名单反模式)
2. **hourly 高频**: 比 weekly/daily 频, 兜底 subagent 长跑任务 (8h+ 实验也能在 1h 后清)
3. **1h+ 1GB+ 严苛阈值**: 比 Layer 1 的 24h 严, 1h 是 subagent 跑完的合理缓冲 (不会误删活文件, 因为活文件 1h 内 mtime 会更新)
4. **排除项目根**: `_EXCLUDE_PATH_PREFIXES = ("/Users/hutou/Desktop/fuqin date",)` 防止误删业务文件
5. **保护 Layer 1 状态文件**: `fuqing-tmp-cleanup.log`, `fuqing-etl-marker.json`, `fuqing-subagent-cleanup.log` 等
6. **软失败**: OSError 不 raise, 漏扫一个文件不影响其他
7. **dry-run 模式**: `--dry-run` 只扫不删, 供测试 / 运维验证用

### 7.4 后续避免类似问题

- ✅ 任何 ETL 路径外的"复制 production 数据"操作, 应主动走 workbuddy cache (Layer 3), 不用 shutil.copy2 到 /tmp
- ✅ subagent 调试应在脚本入口加 `atexit.register(cleanup_local_tmp)` 跟 Layer 1 一致
- ✅ 大文件调试 (>= 1GB) 应放项目根 `data/staging/` 不放 /tmp
- ✅ launchd hourly 是兜底 (Layer 6), 不应替代 Layer 1-5 主动清理

---

## 8. 容量监控与告警阈值

| 指标 | 正常 | 告警 | 紧急 | 处理 |
|---|---|---|---|---|
| `/private/tmp` 总占用 | < 5GB | 5-50GB | > 50GB | Layer 2 告警, 跑 `--cleanup-tmp` |
| `/private/tmp` 下 1GB+ `.duckdb` 总和 | < 1GB | 1-50GB | > 50GB | Layer 2 告警, 跑 `--cleanup-tmp` |
| `data/processed/backups/` 总占用 | < 30GB | 30-100GB | > 100GB | Layer 4 weekly 自动清, 失败看 `/tmp/fuqing-backup-cleanup.log` |
| 磁盘总占用 | < 50% | 50-80% | > 80% | 跑 `df -h` 定位大目录, 紧急用 6 层防护 |
| Layer 6 candidates_scanned (hourly) | 0-2 | 3-5 (cap 边缘) | > 5 (cap 命中) | 看 `/tmp/fuqing-subagent-cleanup.log` cap hit 频率 |

**监控命令**:

```bash
# 磁盘总占用
df -h /

# /tmp 占用
du -sh /private/tmp 2>/dev/null
df -h /private/tmp

# /tmp 下 1GB+ 巨型文件
find /private/tmp -maxdepth 2 -size +1G 2>/dev/null

# backups 占用
du -sh "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/data/processed/backups" 2>/dev/null

# Layer 6 最近 24h 清理记录
grep "$(date -u +%Y-%m-%d)" /tmp/fuqing-subagent-cleanup.log | tail -30

# launchd 服务状态
launchctl list | grep fuqing
```

---

## 9. 接手者必做 (follow-up)

| # | 事项 | 状态 | 说明 |
|---|---|---|---|
| 1 | 监控 Layer 6 hourly 命中率 | 持续 | 每周看 `/tmp/fuqing-subagent-cleanup.log` 是否有 `cap hit`, 高频说明 subagent 路径需治理 |
| 2 | 季度审计 6 层防护 | 建议 Q3 2026 | `launchctl list \| grep fuqing` 确认 3 行, 6 个 log 都有内容, /tmp 占用 < 5GB |
| 3 | F6 (cross-volume move) | 文档化为 future work | Layer 1 用 `os.remove` 不支持跨卷移动, 暂不实现 (等下次有 user 报跨盘慢) |
| 4 | README "运维安全 / 磁盘治理" 章节 | 完成 (见 `README.md` 第 137 行) | 6 层防护原理图 + 紧急命令 + launchd 状态 + log 路径 |
| 5 | CI step 加 `pytest tests/test_wo_cleanup_orphans.py` | 建议 | 18 个 pytest 含 F3 marker 测试, 当前在 pre-commit hooks |

---

## 10. 关键文件路径索引

### 代码 (在 repo 内)

| 路径 | 作用 |
|---|---|
| `scripts/etl/cli.py` | Layer 1 atexit 钩子 (`_cleanup_fq_tmp_orphans()`, `_write_fq_etl_marker()`, `--cleanup-tmp` CLI) |
| `scripts/etl/cleanup_backups.sh` | Layer 4 weekly shell |
| `scripts/etl/backup_duckdb.py` | Layer 5 daily 备份 |
| `scripts/etl/cleanup_subagent.py` | Layer 6 hourly subagent 兜底 |
| `scripts/etl/launchd/com.fuqing.backup-cleanup.weekly.plist` | Layer 4 调度 |
| `scripts/etl/launchd/com.fuqing.duckdb-backup.daily.plist` | Layer 5 调度 |
| `scripts/etl/launchd/com.fuqing.tmp-cleanup.hourly.plist` | Layer 6 调度 |
| `backend/tests/test_wo_cleanup_orphans.py` | 18 个 pytest (含 F3 marker 测试) |

### 文档 (在 repo 内)

| 路径 | 作用 |
|---|---|
| `docs/operations/cleanup.md` | **本文档** (6 层防护运维手册) |
| `docs/handoff-2026-06-05.md` | 6/5 Sprint 1 治理 handoff (4 层防护时点) |
| `docs/SPRINT-7-PLAN.md` | Sprint 7 计划 (含 P2 6 层防护文档化) |
| `CLAUDE.md` | 12 步流程 + 6 层防护总览 (第 137 行附近) |
| `CHANGELOG.md` | v0.4.5 + v0.4.6 + v0.4.6.1 + v0.4.14.11 + v0.4.14.12 source of truth |
| `README.md` | 第 137 行 "运维安全 / 磁盘治理" 段 |

### 个人配置 (不在 repo)

| 路径 | 作用 |
|---|---|
| `~/.zshrc` | Layer 2 告警函数 (`_check_fq_tmp_orphans`) |
| `~/.workbuddy/cache/fq-etl-validation/README.md` | Layer 3 规范 |
| `~/Library/LaunchAgents/com.fuqing.*.plist` | launchd 装载副本 (3 个) |

### 运行时产物 (在 /tmp)

| 路径 | 作用 | 预期状态 |
|---|---|---|
| `/tmp/fuqing-tmp-cleanup.log` | Layer 1 审计日志 | 持续增长 ~60KB+ |
| `/tmp/fuqing-backup-cleanup.log` | Layer 4 weekly 日志 | 每周日 03:00 后有 1 条 |
| `/tmp/fuqing-duckdb-backup.log` | Layer 5 daily 日志 | 每日 03:30 后有 1 条 |
| `/tmp/fuqing-subagent-cleanup.log` | Layer 6 hourly 日志 | 每小时有 1 条 |
| `/tmp/fuqing-backup-cleanup.lock.d/` | Layer 4 lock 目录 | 跑时存在, 跑完 rmdir |
| `/tmp/fuqing-etl-marker.json` | Layer 1 F3 marker | ETL 跑时存在, 退出时删 |
| `/private/tmp/*.duckdb` | fq_ 系列 | 只剩 3 个 1-3MB 仿真副本 |

---

## 11. 一句话总结

**芙清 CRM 6 层防护 = 4 层 ETL 路径 (Layer 1 atexit + 2 zshrc + 3 workbuddy + 4 weekly data) + 1 层数据灾备 (Layer 5 daily backup) + 1 层 subagent 路径兜底 (Layer 6 hourly). Sprint 5 deep dive 教训驱动 Layer 6 落地, 兜底 subagent 走手动 shutil.copy2 漏出来的非 fq_ 前缀巨型孤儿, 6 层独立运行互不依赖, 任何 1 层失效其余层仍兜底.**

---

## 附录 A: 6 层防护 vs handoff 4 层防护差异

| 维度 | handoff-2026-06-05 (4 层) | 本文档 (6 层) |
|---|---|---|
| 防护层数 | 4 (Layer 1-4) | 6 (Layer 1-6) |
| 调度 | ETL 退出 + zsh 启动 + 调试主动 + 周日 weekly | + 每日 daily backup + 每小时 hourly subagent |
| Subagent 路径 | ❌ 无防护 (5 层失效教训) | ✅ Layer 6 兜底 |
| 容量阈值 | 24h+ / 50GB+ / 30 天 / 7 天 | + 1h+ / 1GB+ (Layer 6) |
| 防护范围 | fq_ 白名单 (`_fq_ro*` / `fuqing_*`) | + 所有 1GB+ 巨型文件 (Layer 6 排除项目根) |
| 数据灾备 | ❌ 无 | ✅ Layer 5 daily backup + zstd 压缩 |
| 落地 commit | 4 个 (`cd71c68` / `db70b75` / `5e64ba3` / `797b769`) | + 2 个 (`6423b9b` Sprint 6 P0-3 + Sprint 4 P0-2 backup) |

## 附录 B: 紧急情况速查

| 情况 | 现象 | 处理 |
|---|---|---|
| 磁盘突然 100% | `df -h /` 看占用 | `du -sh /private/tmp/*` 找大文件, 跑 Layer 1 + 6 紧急命令 |
| Layer 1 没自动清 | `/tmp/fuqing-tmp-cleanup.log` 无新记录 | 检查 marker 是否残留 (`/tmp/fuqing-etl-marker.json`), 跑 `--cleanup-tmp` 强制 |
| Layer 6 没自动清 | `/tmp/fuqing-subagent-cleanup.log` 无新记录 | `launchctl list \| grep fuqing.tmp-cleanup` 看 loaded, `launchctl kickstart` 手动 trigger |
| launchd 服务消失 | `launchctl list \| grep fuqing` < 3 行 | 重新 `cp` + `launchctl load` 装载 plist |
| `/tmp` 50GB+ | Layer 2 告警打印 | 跑 Layer 1 + 6 紧急命令, 调查源头 (subagent 调试?) |
| 备份失败 | `/tmp/fuqing-duckdb-backup.log` 报错 | 检查 `data/processed/fact_rfm.duckdb` 是否被 lock, 手动跑 `backup_duckdb.py` |
| weekly 没跑 | 周一没新 `/tmp/fuqing-backup-cleanup.log` 记录 | 检查 `com.fuqing.backup-cleanup.weekly` loaded, 手动跑 `cleanup_backups.sh` |

---

> 文档结束。如有疑问先查 `CHANGELOG.md`, 再查 `CLAUDE.md` 12 步流程, 最后问 user。
