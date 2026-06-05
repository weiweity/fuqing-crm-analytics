# Handoff 2026-06-05 Errata (v0.4.6.2)

## 目的
补 handoff-2026-06-05.md 文档失真 + 缺漏。不改 handoff 主干 (保留 6/5 事件快照语义)。本 errata 是 handoff 唯一勘误来源, 4 层架构有 §3.1 映射表作实操地图。

## Quick links
- §3.1 4 层 ↔ 17 issues 映射表 (索引核心, 后续章节引用 F# 编号)
- §7 禁令路径勘误
- §8 路径 + 运行时产物补
- 附录 A SHA 错位
- 附录 B 数字对齐

## §3.1 4 层 ↔ 17 issues 映射表
| Layer | 路径 | 防护问题 | F 编号 | 修复 commit |
|---|---|---|---|---|
| 1. atexit 钩子 | scripts/etl/cli.py:_cleanup_fq_tmp_orphans | 24h+ 旧文件残留 | F1/F2/F4/F5/F8/F11/F12/F13/F16 | cd71c68 |
| 1. atexit 钩子 | scripts/etl/cli.py:_write_fq_etl_marker | kill -9 不触发 atexit | F3 (HIGH) | 797b769 |
| 1. atexit 钩子 | scripts/etl/cli.py:_collect_fq_tmp_orphans | symlink 误报 | F7 (MEDIUM) | 797b769 |
| 1. atexit 钩子 | (deferred) | mtime 可 touch -t 改写 | F6 (LOW) | deferred to future |
| 2. zshrc 告警 | ~/.zshrc:_check_fq_tmp_orphans | 50GB+ 占用不告警 | — | (handoff §3) |
| 3. workbuddy cache | ~/.workbuddy/cache/fq-etl-validation/ | 调试副本污染 /tmp | — | (handoff §3) |
| 4. launchd backups | scripts/etl/cleanup_backups.sh | backups/ 7 天保留 | F17/F18/F19/F20/F23/F26/F27 | 48f7f31 |
| 4. launchd backups | scripts/etl/launchd/com.fuqing.backup-cleanup.weekly.plist | launchd 调度 | F18/F19 | 48f7f31 |

## §4 系统状态补 (handoff §4 之后的勘误)
- handoff 表格说"3 个 1-3MB 仿真副本", 实际 6/5 18:00 验证时 /tmp 下还有:
  - /private/tmp/claude-501/ 39M (pytest tmpdir, Layer 1 不扫, 文档化不修)
  - /tmp/fuqing-backup-cleanup.lock 0B (Layer 4 锁, 异常退出遗留)
  - /tmp/fuqing-backup-cleanup.log 390B (Layer 4 日志, 正常)
- 实际磁盘: 12Gi/702Gi (2%, APFS 系统卷), handoff 写的 22% 是另一 mount point

## §7 禁令勘误
- 禁令 #1 路径错: handoff 写 /Library/Caches/ms-playwright/chromium_headless_shell-1208/, 实际是 ~/Library/Caches/ms-playwright/chromium_headless_shell-{1208,1223}/
- 禁令协议 (README 运维章节已写): 删前先 find ~/Library/Caches/ms-playwright/ -name 'headless_shell*' 确认无活跃进程 + 备份 cat ~/Library/Caches/ms-playwright/.links 记录

## §8 路径索引补
- com.fuqing.etl.daily.plist 源文件位置: scripts/etl/scheduler/com.fuqing.etl.daily.plist (非 handoff 暗示的 launchd/)
- 含 install_macos.sh + install_windows.ps1 + etl_daily_taskscheduler.xml (Windows 任务计划器版本)
- 源 launchd plist 仍 loaded: launchctl list | grep com.fuqing.etl.daily
- com.fuqing.backup-cleanup.weekly.plist 位置: scripts/etl/launchd/com.fuqing.backup-cleanup.weekly.plist (handoff 写的对)

## §8 运行时产物表补
- /tmp/fuqing-etl-health.json — WO-4 SRE 0 飞书 0 代码状态查询入口 (handoff 漏列)
- /tmp/fuqing-backup-cleanup.lock — Layer 4 锁文件
- /tmp/fuqing-backup-cleanup.log — Layer 4 执行日志

## 附录 A SHA 错位勘误
handoff 附录 A 6 个 SHA 有 2 处错, 正确归属:

| handoff 写 | 实际 |
|---|---|
| 5e64ba3 = v0.4.5 含 13 个 AUTO-FIX | 5e64ba3 = "Merge feature/wo-fix-f3-f7-atexit-limitations into main" (v0.4.6 合并) |
| 48f7f31 = Layer 3 workbuddy cache 协议 | 48f7f31 = "backups/ 7 天保留清理 + launchd 周日 3 点 (WO-x Layer 4)" |

正确版本归属:
- v0.4.5: db70b75 (merge) + cd71c68 (Layer 1) + 48f7f31 (Layer 4)
- v0.4.6: 5e64ba3 (merge) + 797b769 (F3+F7)
- v0.4.6.1: df5d250 (doc sync)
- v0.4.6.2: 本 errata (本 commit)

## 附录 B 数字对齐
- handoff 8 节写"18 个 pytest", 实际 test_wo_cleanup_orphans.py 20 个 test functions:
  - 12 cleanup 基础 (TestCleanupFqTmpOrphans + TestCleanupFqTmpConstants)
  - 3 F3 marker (TestF3MarkerAndF7Symlink::test_f3_*)
  - 3 F7 symlink (TestF3MarkerAndF7Symlink::test_f7_* + constants)
  - 2 --cleanup-tmp CLI (TestCleanupTmpFlag, v0.4.7 加)
- handoff 第 5 节 17/18/19 数字矛盾: 标题 17 = stats 18 (13+4+1) = 明细 19 (16+2+1) — 以标题 17 为 ground truth: 13 AUTO-FIX + 3 文档化 + 1 future = 17
- F6 描述统一: CHANGELOG v0.4.6 L29 写"mtime 改 flock/lsof/marker deferred", handoff 写"cross-volume move deferred" — 以 CHANGELOG 为准 (F6 实际是 mtime 不可靠的 future work, 非 cross-volume)

## §9 卫生段
- 6/5 18:00 清 /tmp/dmp_* 跨项目残留 ~1MB (DMP 达摩盘项目数据, 与 fuqing-crm 防护命名空间隔离, atexit 不扫 dmp_*, 安全 NO-OP)
- /tmp/claude-501 39M 长期残留: 保持 FQ_TMP_PREFIXES 白名单最小化, 不扩, 文档化不修
- cleanup_backups.sh stale 锁: 本 errata PR 合入 trap EXIT fix, 下次不再 0B 锁遗留

## 自我维护条款
- 未来 SHA 不在本附录 A → 说明 handoff 已更新, 本 errata 同步 bump
- Layer 边界变更 → 同步 §3.1 映射表
- 6/5 当日后续治理 → 起新 handoff-YYYY-MM-DD.md + 配套 errata
