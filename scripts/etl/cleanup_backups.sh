#!/bin/bash
# ============================================================================
# 芙清 CRM - backups/ 目录 7 天保留清理
#
# 背景（2026-06-05 治理）:
#   - data/processed/backups/ 当前仅 1 个 .parquet（1.1MB, 5/15 22:53），
#     无清理机制，长时间累积会占用磁盘
#   - Layer 4 of 4：数据生命周期治理
#
# 规则:
#   - .parquet / .duckdb 文件 mtime > 7 天的删除
#   - 软失败：单文件 rm 失败不阻塞（只 print warning 到 stderr）
#   - 跑完输出 plain-text 状态到 /tmp/fuqing-backup-cleanup.log 供 launchd 监控
#     （launchd 不解析 JSON 也不消费输出，仅靠 exit code 判断成败）
#
# 安装:
#   cp ~/Desktop/fuqin\ date/fuqing-crm-analytics/scripts/etl/cleanup_backups.sh /usr/local/bin/
#   chmod +x /usr/local/bin/cleanup_backups.sh
#   cp ~/Desktop/fuqin\ date/fuqing-crm-analytics/scripts/etl/launchd/com.fuqing.backup-cleanup.weekly.plist ~/Library/LaunchAgents/
#   launchctl load ~/Library/LaunchAgents/com.fuqing.backup-cleanup.weekly.plist
# ============================================================================

# 严格模式 + pipefail（F26 修复：避免 find 失败被 | while 掩盖）
set -euo pipefail

# 显式 PATH（F17 修复：launchd 启动的 shell 默认 PATH 只有 /usr/bin:/bin，
# 缺 GNU coreutils / homebrew 工具如 gawk / gstat）
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# 并发保护（F18 修复：launchd 配错一天跑两次时锁防双进程）
# macOS 没 flock 命令，用 mkdir-based lock（POSIX 兼容）
LOCK_DIR="/tmp/fuqing-backup-cleanup.lock.d"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] SKIP: another instance holds $LOCK_DIR" \
        | tee -a /tmp/fuqing-backup-cleanup.log
    exit 0
fi
# trap 确保任何退出路径都释放锁
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

BACKUP_DIR="/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/data/processed/backups"
LOG_FILE="/tmp/fuqing-backup-cleanup.log"
RETENTION_DAYS=7
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# 1. 检查目录存在
if [[ ! -d "$BACKUP_DIR" ]]; then
    echo "[$TIMESTAMP] SKIP: $BACKUP_DIR 不存在" | tee -a "$LOG_FILE"
    exit 0
fi

# 2. 统计清理前（F20 修复：不吞 find 错误，显式判断）
BEFORE_COUNT=$(find "$BACKUP_DIR" -type f \( -name "*.parquet" -o -name "*.duckdb" \) 2>&1 | tee /dev/stderr | wc -l | tr -d ' ') || {
    echo "[$TIMESTAMP] ERROR: find failed on $BACKUP_DIR" | tee -a "$LOG_FILE"
    exit 1
}
BEFORE_BYTES=$(find "$BACKUP_DIR" -type f \( -name "*.parquet" -o -name "*.duckdb" \) -exec stat -f "%z" {} + 2>/dev/null | awk '{s+=$1} END {print s+0}')

# 3. 清理 7 天前的文件（软失败：rm 失败只 log 不 exit）
DELETED_NAMES=()
while IFS= read -r f; do
    if rm -f "$f" 2>/dev/null; then
        DELETED_NAMES+=("$(basename "$f")")
    else
        echo "[$TIMESTAMP] WARN: rm failed: $f" | tee -a "$LOG_FILE" >&2
    fi
done < <(find "$BACKUP_DIR" -type f \( -name "*.parquet" -o -name "*.duckdb" \) -mtime +$RETENTION_DAYS 2>/dev/null)

# 4. 统计清理后
AFTER_COUNT=$(find "$BACKUP_DIR" -type f \( -name "*.parquet" -o -name "*.duckdb" \) 2>/dev/null | wc -l | tr -d ' ')
AFTER_BYTES=$(find "$BACKUP_DIR" -type f \( -name "*.parquet" -o -name "*.duckdb" \) -exec stat -f "%z" {} + 2>/dev/null | awk '{s+=$1} END {print s+0}')

# 5. 输出结果（plain text，launchd 仅看 exit code）
BEFORE_MB=$((BEFORE_BYTES / 1024 / 1024))
AFTER_MB=$((AFTER_BYTES / 1024 / 1024))
DELETED_COUNT=$((BEFORE_COUNT - AFTER_COUNT))
DELETED_MB=$((BEFORE_MB - AFTER_MB))

SUMMARY="[$TIMESTAMP] backups cleanup: before=$BEFORE_COUNT files/${BEFORE_MB}MB → after=$AFTER_COUNT files/${AFTER_MB}MB, deleted=$DELETED_COUNT files/${DELETED_MB}MB"
if [[ ${#DELETED_NAMES[@]} -gt 0 ]]; then
    SUMMARY="$SUMMARY | files: ${DELETED_NAMES[*]}"
fi
echo "$SUMMARY" | tee -a "$LOG_FILE"

# trap EXIT 会自动 rmdir 锁目录
