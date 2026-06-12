#!/bin/bash
# ============================================================================
# 芙清 CRM - backups/ 目录 3 阶段清理 (mtime 7d + count cap 3 + size cap 100GB)
#
# 背景（2026-06-12 治理）:
#   - Sprint 4 P0-2 时期 (2026-06-05) 加了 7 天 mtime 保留, 周日 03:00 跑
#   - 但 2026-06-12 实测: data/processed/backups/ 有 3 个 27+31+35=93GB 备份
#     全部在 7 天内, weekly cleanup 永远不删, 累积爆磁盘
#   - 加 cap 机制: count cap (N=3) + size cap (100GB) 跟 7 天保留组合
#   - Layer 4 of 4 → 增强为 Layer 4b: 数据生命周期治理 + 容量天花板
#   - 修复: 原脚本 glob 只匹配 *.parquet/*.duckdb, 漏了 *.zst (Sprint 4 backup_duckdb.py
#     实际产 *.duckdb.zst, 7 天保留原 0 匹配, 实际失效)
#
# 规则（三阶段顺序执行, 每阶段独立 try/catch 软失败）:
#   阶段 1 (现有): mtime > 7 天 → 删除                    (Sprint 4 P0-2)
#   阶段 2 (新增): 按 mtime 倒序保留最近 N=3 个, 超出 → 删除
#   阶段 3 (新增): 总大小 > 100GB → 按 mtime 正序删最旧直到 < 100GB
#
# 设计权衡:
#   - 三阶段顺序而非"任一条件触发": 阶段 1 先清过期 (最廉价), 阶段 2 再保底
#     数量, 阶段 3 最后兜底容量. 顺序确保"先清最该清的"
#   - 阶段 2 N=3: 跟当前实际 (3 个 backup) 持平, 不立即触发, 给 +1 缓冲
#   - 阶段 3 100GB: 当前 ~93GB, 加 7GB 缓冲; 再翻倍才到 200GB 才再清
#   - 软失败: 单文件 rm 失败不阻塞 (只 print warning 到 stderr)
#   - 跑完输出 plain-text 状态到 /tmp/fuqing-backup-cleanup.log 供 launchd 监控
#     (launchd 不解析 JSON 也不消费输出, 仅靠 exit code 判断成败)
#
# 安装 (沿用 Sprint 4 P0-2 文档):
#   cp ~/Desktop/fuqin\ date/fuqing-crm-analytics/scripts/etl/cleanup_backups.sh /usr/local/bin/
#   chmod +x /usr/local/bin/cleanup_backups.sh
#   cp ~/Desktop/fuqin\ date/fuqing-crm-analytics/scripts/etl/launchd/com.fuqing.backup-cleanup.weekly.plist ~/Library/LaunchAgents/
#   launchctl load ~/Library/LaunchAgents/com.fuqing.backup-cleanup.weekly.plist
#
# Dry-run (新增, 用于测试):
#   bash scripts/etl/cleanup_backups.sh --dry-run
#   打印三阶段会删哪些文件 + 释放多少空间, 不真删
# ============================================================================

# 严格模式 + pipefail (F26 修复: 避免 find 失败被 | while 掩盖)
set -euo pipefail

# 显式 PATH (F17 修复: launchd 启动的 shell 默认 PATH 只有 /usr/bin:/bin,
# 缺 GNU coreutils / homebrew 工具如 gawk / gstat)
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# 解析参数 (--dry-run flag)
DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        -h|--help)
            echo "Usage: $0 [--dry-run]"
            echo "  --dry-run  打印会删哪些文件, 不真删 (用于测试 cap 机制)"
            exit 0
            ;;
    esac
done

# 并发保护 (F18 修复: launchd 配错一天跑两次时锁防双进程)
# macOS 没 flock 命令, 用 mkdir-based lock (POSIX 兼容)
LOCK_DIR="/tmp/fuqing-backup-cleanup.lock.d"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] SKIP: another instance holds $LOCK_DIR" \
        | tee -a /tmp/fuqing-backup-cleanup.log
    exit 0
fi
# trap 确保任何退出路径都释放锁 + 清理临时文件
TMP_TRIPLE=""
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true; [[ -n "$TMP_TRIPLE" ]] && rm -f "$TMP_TRIPLE" 2>/dev/null || true' EXIT

BACKUP_DIR="/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/data/processed/backups"
LOG_FILE="/tmp/fuqing-backup-cleanup.log"
RETENTION_DAYS=7
KEEP_RECENT_COUNT=3      # 阶段 2: 保留最近 N 个
MAX_TOTAL_BYTES=$((100 * 1024 * 1024 * 1024))  # 阶段 3: 100GB cap
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# rm 包装: 兼容 --dry-run
# dry-run 模式: 仅 echo, 不 append DELETED_NAMES (避免跨阶段重复 + 误以为会真删)
do_rm() {
    local f="$1"
    if [[ "$DRY_RUN" == "true" ]]; then
        local sz
        sz=$(stat -f "%z" "$f" 2>/dev/null | awk '{printf "%.1f MB", $1/1024/1024}')
        echo "  [DRY-RUN] would delete: $f ($sz)"
        return 1  # 1 = "未真删", 让调用方跳过 DELETED_NAMES append + STAGE_N_DELETED++
    fi
    if rm -f "$f" 2>/dev/null; then
        return 0
    else
        echo "[$TIMESTAMP] WARN: rm failed: $f" | tee -a "$LOG_FILE" >&2
        return 1
    fi
}

# 0. 检查目录存在
if [[ ! -d "$BACKUP_DIR" ]]; then
    echo "[$TIMESTAMP] SKIP: $BACKUP_DIR 不存在" | tee -a "$LOG_FILE"
    exit 0
fi

# 1. 统计清理前 (F20 修复: 不吞 find 错误, 显式判断)
# glob 包含 .zst (Sprint 4 backup_duckdb.py 产 .duckdb.zst, 原脚本漏匹配 → 7 天保留失效)
# F20 修复: 不吞 find 错误, 显式判断
# 用 FIND_ERR 临时文件捕获 find 的 stderr (非输出), 避免污染 dry-run 时 stdout
FIND_ERR=$(mktemp -t fuqing-backup-find.XXXXXX)
BEFORE_COUNT=$(find "$BACKUP_DIR" -type f \( -name "*.parquet" -o -name "*.duckdb" -o -name "*.zst" \) 2>"$FIND_ERR" | wc -l | tr -d ' ')
if [[ -s "$FIND_ERR" ]]; then
    echo "[$TIMESTAMP] ERROR: find failed on $BACKUP_DIR: $(cat "$FIND_ERR")" | tee -a "$LOG_FILE"
    rm -f "$FIND_ERR"
    exit 1
fi
rm -f "$FIND_ERR"
BEFORE_BYTES=$(find "$BACKUP_DIR" -type f \( -name "*.parquet" -o -name "*.duckdb" -o -name "*.zst" \) -exec stat -f "%z" {} + 2>/dev/null | awk '{s+=$1} END {print s+0}')

DELETED_NAMES=()
WOULD_DELETE_NAMES=()  # dry-run 时收集, 不进 DELETED_NAMES (避免跨阶段重复)

# ============================================================================
# 阶段 1 (Sprint 4 P0-2): mtime > 7 天 → 删除
# ============================================================================
[[ "$DRY_RUN" == "true" ]] && echo "[阶段 1: mtime > ${RETENTION_DAYS} 天]"
STAGE1_DELETED=0
while IFS= read -r f; do
    if do_rm "$f"; then
        DELETED_NAMES+=("$(basename "$f")")
        STAGE1_DELETED=$((STAGE1_DELETED + 1))
    fi
done < <(find "$BACKUP_DIR" -type f \( -name "*.parquet" -o -name "*.duckdb" -o -name "*.zst" \) -mtime +$RETENTION_DAYS 2>/dev/null)

# ============================================================================
# 阶段 2 (Sprint 20 新增): 按 mtime 倒序保留最近 N=3 个, 超出 → 删除
# ============================================================================
[[ "$DRY_RUN" == "true" ]] && echo "" && echo "[阶段 2: 保留最近 ${KEEP_RECENT_COUNT} 个]"
STAGE2_DELETED=0
# stat -f "%m %N" → "mtime name", sort -rn 倒序 (新→旧), awk 去 mtime 留 name
# 用 while-loop 替代 mapfile (macOS bash 3.2 无 mapfile, F17 教训)
ALL_FILES_ARR=()
while IFS= read -r f; do
    [[ -n "$f" ]] && ALL_FILES_ARR+=("$f")
done < <(find "$BACKUP_DIR" -type f \( -name "*.parquet" -o -name "*.duckdb" -o -name "*.zst" \) -exec stat -f "%m %N" {} + 2>/dev/null | sort -rn | awk '{$1=""; sub(/^ /, ""); print}')
TOTAL_FILES=${#ALL_FILES_ARR[@]}
if [[ $TOTAL_FILES -gt $KEEP_RECENT_COUNT ]]; then
    # 跳过前 N 个 (最新), 从第 N+1 个开始删
    i=$KEEP_RECENT_COUNT
    while [[ $i -lt $TOTAL_FILES ]]; do
        f="${ALL_FILES_ARR[$i]}"
        if do_rm "$f"; then
            DELETED_NAMES+=("$(basename "$f")")
            STAGE2_DELETED=$((STAGE2_DELETED + 1))
        fi
        i=$((i + 1))
    done
fi

# ============================================================================
# 阶段 3 (Sprint 20 新增): 总大小 > 100GB → 按 mtime 正序删最旧直到 ≤ 100GB
# 逻辑: 阶段 1+2 后若总大小仍超 cap, 从最旧的备份开始删, 删到剩余 ≤ cap 为止.
#       这样始终优先保留最新备份, 只在容量 ceiling 被突破时才牺牲旧备份.
# ============================================================================
[[ "$DRY_RUN" == "true" ]] && echo "" && echo "[阶段 3: 总大小 > $((MAX_TOTAL_BYTES / 1024 / 1024 / 1024))GB → 删最旧]"
STAGE3_DELETED=0
# 用临时文件存 (mtime size name) 三元组按 mtime 正序 (旧→新), 避免 name 空格问题
TMP_TRIPLE=$(mktemp -t fuqing-backup-cleanup.XXXXXX)
find "$BACKUP_DIR" -type f \( -name "*.parquet" -o -name "*.duckdb" -o -name "*.zst" \) -exec stat -f "%m %z %N" {} + 2>/dev/null | sort -n > "$TMP_TRIPLE"

# 阶段 1+2 后的当前总大小 (阶段 3 开始时统计; dry-run 用虚拟累计避免死循环)
CURRENT_TOTAL=$(awk '{s+=$2} END {print s+0}' "$TMP_TRIPLE")
VIRTUAL_TOTAL=$CURRENT_TOTAL
while IFS= read -r line && [[ $VIRTUAL_TOTAL -gt $MAX_TOTAL_BYTES ]]; do
    size=$(echo "$line" | awk '{print $2}')
    name=$(echo "$line" | awk '{$1=""; $2=""; sub(/^  /, ""); print}')
    if do_rm "$name"; then
        DELETED_NAMES+=("$(basename "$name")")
        STAGE3_DELETED=$((STAGE3_DELETED + 1))
        CURRENT_TOTAL=$((CURRENT_TOTAL - size))
    fi
    VIRTUAL_TOTAL=$((VIRTUAL_TOTAL - size))
done < "$TMP_TRIPLE"

# 4. 统计清理后
AFTER_COUNT=$(find "$BACKUP_DIR" -type f \( -name "*.parquet" -o -name "*.duckdb" -o -name "*.zst" \) 2>/dev/null | wc -l | tr -d ' ')
AFTER_BYTES=$(find "$BACKUP_DIR" -type f \( -name "*.parquet" -o -name "*.duckdb" -o -name "*.zst" \) -exec stat -f "%z" {} + 2>/dev/null | awk '{s+=$1} END {print s+0}')

# 5. 输出结果 (plain text, launchd 仅看 exit code)
BEFORE_MB=$((BEFORE_BYTES / 1024 / 1024))
AFTER_MB=$((AFTER_BYTES / 1024 / 1024))
DELETED_COUNT=$((BEFORE_COUNT - AFTER_COUNT))
DELETED_MB=$((BEFORE_MB - AFTER_MB))

if [[ "$DRY_RUN" == "true" ]]; then
    SUMMARY="[DRY-RUN] backups cleanup: before=$BEFORE_COUNT files/${BEFORE_MB}MB → after=$AFTER_COUNT files/${AFTER_MB}MB, would_delete=$DELETED_COUNT files/${DELETED_MB}MB"
else
    SUMMARY="[$TIMESTAMP] backups cleanup: before=$BEFORE_COUNT files/${BEFORE_MB}MB → after=$AFTER_COUNT files/${AFTER_MB}MB, deleted=$DELETED_COUNT files/${DELETED_MB}MB (s1=$STAGE1_DELETED/s2=$STAGE2_DELETED/s3=$STAGE3_DELETED)"
fi
[[ ${#DELETED_NAMES[@]} -gt 0 ]] && SUMMARY="$SUMMARY | files: ${DELETED_NAMES[*]}"
echo "$SUMMARY" | tee -a "$LOG_FILE"

# trap EXIT 会自动 rmdir 锁目录 + 删 TMP_TRIPLE
