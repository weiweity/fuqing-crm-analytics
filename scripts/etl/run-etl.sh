#!/bin/bash
# 芙清 CRM - ETL 一键跑批脚本 (Sprint 22+)
#
# 用法:
#   ./scripts/etl/run-etl.sh                # 增量 update (推荐, 扫增量数据)
#   ./scripts/etl/run-etl.sh --full         # 强制全量重建
#   ./scripts/etl/run-etl.sh --inc          # 强制增量
#   ./scripts/etl/run-etl.sh --help         # 看 help
#
# 自动处理:
#   1. 跑前自动停 uvicorn (释放 DuckDB 锁)
#   2. 跑 ETL (10-18 min)
#   3. 跑完自动重启 uvicorn (前端加载新数据)
#
# 跑批期间不要中断 (10-18 min), DuckDB 锁会卡其他读写

set -euo pipefail   # Sprint 105 /review 必修: pipefail 防 tee 失败静默, -u 防 unbound variable, 跟 Sprint 32.1 教训一致

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON="/Users/hutou/homebrew/bin/python3"
LOG="/tmp/fuqing-etl-manual.log"

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"

# 0. 解析参数 (优先, --help 立即退出, 跳过锁检测)
# 1. 选模式 (命令行参数优先, 无参数则交互选择)
if [ -n "${1:-}" ] && [ "${1:-}" != "--help" ] && [ "${1:-}" != "-h" ]; then   # Sprint 93.1 L4.7 实战 fix 模式: ${1:-} 替 $1, 防 set -u + 无参数 unbound variable 错
    # 有命令行参数, 直接用
    MODE="$1"
else
    # 无参数, 交互选择
    echo ""
    echo "============================================================"
    echo "芙清 CRM - ETL 跑批"
    echo "============================================================"
    echo ""
    echo "  请选择模式:"
    echo ""
    echo "    1) 增量更新 (默认, 扫新数据 + 淘客 + 状态刷新, 10-18 min)"
    echo "    2) 强制增量 (只跑增量, 数据库必须已有数据, 8-12 min)"
    echo "    3) 全量重建 (DROP+CREATE 表, 从头算, 5-10 min)"
    echo ""
    read -p "  输入 1/2/3 (直接回车=1 增量更新): " CHOICE
    echo ""
    case "$CHOICE" in
        2) MODE="--inc" ;;
        3) MODE="--full" ;;
        *) MODE="--update" ;;
    esac
fi

# help
if [ "$MODE" = "--help" ] || [ "$MODE" = "-h" ]; then
    echo "芙清 CRM - ETL 手动触发"
    echo ""
    echo "用法: $0 [--update|--inc|--full|--help]"
    echo ""
    echo "  --update (默认): 一键增量更新 (ETL + 淘客 + 状态刷新, 10-18 min)"
    echo "  --inc:          强制增量 (数据库必须已有数据, 8-12 min)"
    echo "  --full:         强制全量重建 (DROP+CREATE 表, 5-10 min)"
    echo "  --help:         看这个 help"
    echo ""
    echo "常用流程:"
    echo "  1. 把新 xlsx 放到 data/raw/ 下"
    echo "  2. ./scripts/etl/run-etl.sh    # 交互选模式"
    echo "  3. ./scripts/etl/run-etl.sh --update  # 直接跑增量 (不问)"
    exit 0
fi

# 2. 跑前环境检查
echo "============================================================"
echo "芙清 CRM - ETL 跑批"
echo "============================================================"
echo "  project: $PROJECT_ROOT"
echo "  python:  $PYTHON"
echo "  log:     $LOG"
echo ""

# 保险清理: 不管脚本如何退出 (set -e 触发 / 正常完成 / Ctrl+C) 都 kill ticker + ETL 子进程
# + 如果 plist 已 bootout 但未 bootstrap, 自动恢复, 防 uvicorn 永久失守护.
# 必须在 bootout 前注册, 否则锁检查失败等早退路径会把 plist 永久留在卸载状态.
cleanup_ticker() {
    if [ -n "${TICKER_PID:-}" ]; then
        kill "$TICKER_PID" 2>/dev/null || true
        wait "$TICKER_PID" 2>/dev/null || true
    fi
    # 杀残留的 Python ETL 进程 (防止 Ctrl+C 后 Python 子进程继续持有 DuckDB 锁)
    pkill -f "run_etl.py.*$MODE" 2>/dev/null || true
    if [ -n "${FQ_UVICORN_BOOTED_OUT:-}" ] && [ -z "${FQ_UVICORN_BOOTED_BACK_IN:-}" ]; then
        # Sprint 93.3 L4.7 实战 fix 模式: silent recovery 替代报 'plist 已 bootout' (Claude Code 工具 2m 超时 SIGTERM 误判 + Claude Code 工具把 echo 当 stdout 错)
        launchctl bootstrap "gui/$UID" "$HOME/Library/LaunchAgents/com.fuqing.uvicorn.plist" 2>/dev/null || true
    fi
}
trap cleanup_ticker EXIT INT TERM HUP PIPE QUIT   # Sprint 105 /review 必修: 加 HUP/PIPE/QUIT 5 信号 (SIGHUP/SIGPIPE/SIGQUIT 在某些 bash 不触发 EXIT trap, iTerm2 / VSCode terminal / ssh 断连常见)

# 3. 临时卸载 com.fuqing.uvicorn plist (防 launchd KeepAlive 自动重启)
#    跑完 ETL 后重新 launchctl bootstrap 加载, RunAtLoad=true 会自动启动 uvicorn.
#    之前用 SIGTERM + sleep 2, launchd 会在 ThrottleInterval=5s 后重启新 uvicorn,
#    新进程在 FastAPI startup 打开 DuckDB 锁, 跟 ETL 抢锁 (Sprint 105).
if launchctl list 2>/dev/null | grep -q "com.fuqing.uvicorn"; then
    echo "  🔄 临时卸载 com.fuqing.uvicorn plist (防 launchd KeepAlive 重启)..."
    if launchctl bootout "gui/$UID/com.fuqing.uvicorn" 2>/dev/null; then
        export FQ_UVICORN_BOOTED_OUT=1
        # 等 uvicorn 真正退出 (launchd bootout 异步 SIGTERM, 进程清理是 async, graceful shutdown 1-2s)
        # Sprint 105 /review 必修: bootout-poll wait 防 8 分 30 秒后 ETL step 4 仍被 uvicorn 持锁冲突
        for _wait in 1 2 3 4 5 6 7 8 9 10; do
            if ! lsof -ti :8000 >/dev/null 2>&1; then break; fi
            sleep 1
        done
        echo "  ✅ plist 已卸载, 8000 端口已释放 (wait ${_wait}s), launchd 不再自动重启 uvicorn"
    else
        echo "  ⚠️  launchctl bootout 失败, fallback 到 SIGTERM 杀 uvicorn (旧 Sprint 93 行为, 有 race condition 风险)"
        UVICORN_PID=$(lsof -ti :8000 2>/dev/null | head -1)
        if [ -n "$UVICORN_PID" ]; then
            kill "$UVICORN_PID" 2>/dev/null
            sleep 8
            if lsof -ti :8000 >/dev/null 2>&1; then
                UVICORN_PID=$(lsof -ti :8000 2>/dev/null | head -1)
                kill -9 "$UVICORN_PID" 2>/dev/null
                sleep 2
            fi
        fi
    fi
else
    echo "  ✅ com.fuqing.uvicorn plist 未加载 (无需卸载)"
fi

# 4. DuckDB 锁最终检测 (Sprint 93 L4.7 实战 fix 模式: uvicorn 强制 kill 后 DuckDB 锁可能
# 被残留 Python 进程 (pytest / Codex / other backend) 持有, 之前直接 exit 1 必 user 手动 kill.
# 现在加 auto-kill + retry, 跟 line 82-95 uvicorn kill 模式一致).
DUCKDB_LOCK_HOLDER=$(lsof "$PROJECT_ROOT/data/processed/fuqing_crm.duckdb" 2>/dev/null | awk 'NR>1 {print $2}' | sort -u || true)
if [ -n "$DUCKDB_LOCK_HOLDER" ]; then
    echo "  ⚠️  DuckDB 锁被以下进程持有: $DUCKDB_LOCK_HOLDER (uvicorn 强制 kill 后残留)"
    echo "  🔄 自动 kill DuckDB lock holder..."
    for LOCK_PID in $DUCKDB_LOCK_HOLDER; do
        kill "$LOCK_PID" 2>/dev/null && echo "    ✅ SIGTERM PID $LOCK_PID" || echo "    ⚠️  SIGTERM PID $LOCK_PID 失败"
    done
    sleep 2
    # 重检, 锁没释放就强制 kill -9
    DUCKDB_LOCK_HOLDER=$(lsof "$PROJECT_ROOT/data/processed/fuqing_crm.duckdb" 2>/dev/null | awk 'NR>1 {print $2}' | sort -u || true)
    if [ -n "$DUCKDB_LOCK_HOLDER" ]; then
        echo "  ⚠️  DuckDB 锁未释放, 强制 kill -9..."
        for LOCK_PID in $DUCKDB_LOCK_HOLDER; do
            kill -9 "$LOCK_PID" 2>/dev/null && echo "    ✅ SIGKILL PID $LOCK_PID" || echo "    ⚠️  SIGKILL PID $LOCK_PID 失败"
        done
        sleep 1
    fi
    # 第三次重检, 还持有就放弃 (避免 kill 系统关键进程)
    DUCKDB_LOCK_HOLDER=$(lsof "$PROJECT_ROOT/data/processed/fuqing_crm.duckdb" 2>/dev/null | awk 'NR>1 {print $2}' | sort -u || true)
    if [ -n "$DUCKDB_LOCK_HOLDER" ]; then
        echo "  ❌ DuckDB 锁仍被持有: $DUCKDB_LOCK_HOLDER, 手动 kill 后重试:"
        echo "     lsof -ti $PROJECT_ROOT/data/processed/fuqing_crm.duckdb | xargs kill -9"
        exit 1
    fi
    echo "  ✅ DuckDB 锁已释放"
fi

MODE_NAME="--update → 增量更新"
[ "$MODE" = "--inc" ] && MODE_NAME="--inc → 强制增量"
[ "$MODE" = "--full" ] && MODE_NAME="--full → 全量重建"

echo "  模式: $MODE_NAME"
echo "  开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

# 5. 跑 ETL (所有输出 tee 到日志 + 进度计时器)
START=$(date +%s)
echo "  日志: $LOG"
echo ""

# 后台计时器: 每 30 秒打印一次耗时 (让终端不"沉默")
(
    while true; do
        sleep 30
        NOW=$(date +%s)
        ELAPSED=$(( NOW - START ))
        MINS=$(( ELAPSED / 60 ))
        SECS=$(( ELAPSED % 60 ))
        echo "  ⏱️  已跑 ${MINS} 分 ${SECS} 秒..."
    done
) &
TICKER_PID=$!

# 跑 ETL
"$PYTHON" scripts/run_etl.py "$MODE" 2>&1 | tee -a "$LOG"
EXIT_CODE=${PIPESTATUS[0]}

# 停计时器: 由 trap cleanup_ticker EXIT 统一处理 (见 ticker 启动后)

ELAPSED=$(( $(date +%s) - START ))

echo ""
echo "============================================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "  ✅ ETL 完成 (exit 0, 耗时 ${ELAPSED}s)"
else
    echo "  ❌ ETL 失败 (exit $EXIT_CODE, 耗时 ${ELAPSED}s)"
    echo "  查日志: $LOG"
fi

# 6. 重新加载 com.fuqing.uvicorn plist (RunAtLoad=true 自动启动 uvicorn)
#    不再 nohup 显式启动, 避免跟 plist 自动启动形成两个 uvicorn 抢 8000 端口.
echo ""
echo "  🔄 重新加载 com.fuqing.uvicorn plist (RunAtLoad=true 自动启动)..."
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
if [ -z "${FQ_UVICORN_BOOTED_OUT:-}" ] && launchctl list 2>/dev/null | grep -q "com.fuqing.uvicorn"; then
    # bootout fallback 路径下 plist 仍已加载, 不重复 bootstrap / nohup.
    echo "  ✅ com.fuqing.uvicorn plist 仍由 launchd 接管"
    sleep 3
elif launchctl bootstrap "gui/$UID" "$HOME/Library/LaunchAgents/com.fuqing.uvicorn.plist" 2>/dev/null; then
    unset FQ_UVICORN_BOOTED_OUT
    export FQ_UVICORN_BOOTED_BACK_IN=1
    sleep 3
    if lsof -ti :8000 >/dev/null 2>&1; then
        NEW_UVICORN_PID=$(lsof -ti :8000 2>/dev/null | head -1)
        echo "  ✅ uvicorn 已重启 (PID $NEW_UVICORN_PID, launchd 接管)"
    else
        echo "  ⚠️  plist 加载后 8000 端口仍无监听, 手动检查:"
        echo "    launchctl list | grep com.fuqing.uvicorn"
    fi
else
    echo "  ⚠️  launchctl bootstrap 失败, fallback 到 nohup 显式启动 (旧行为):"
    nohup "$PYTHON" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 \
        >> /tmp/fuqing-crm-backend.log 2>&1 &
    NEW_PID=$!
    disown $NEW_PID 2>/dev/null || true
    sleep 3
    if lsof -ti :8000 >/dev/null 2>&1; then
        export FQ_UVICORN_BOOTED_BACK_IN=1
        echo "  ✅ uvicorn 已重启 (PID $NEW_PID, nohup 接管)"
    else
        echo "  ❌ uvicorn 重启失败, 手动检查: lsof -ti :8000"
    fi
fi
echo "  前端: http://localhost:5173"
echo "  API:  http://localhost:8000/docs"
echo "============================================================"

if [ $EXIT_CODE -ne 0 ]; then
    exit $EXIT_CODE
fi
