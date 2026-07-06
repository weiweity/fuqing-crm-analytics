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
        # Sprint 202+ R7: cleanup_ticker bootstrap-back 后 verify plist 真起来 (launchctl list | grep) 防 race (L4.63)
        launchctl bootstrap "gui/$UID" "$HOME/Library/LaunchAgents/com.fuqing.uvicorn.plist" 2>/dev/null || true
        for _bwait in 1 2 3 4 5; do
            if launchctl list 2>/dev/null | grep -q "com.fuqing.uvicorn"; then break; fi
            sleep 1
        done
        echo "  ✅ cleanup_ticker: plist bootstrap-back OK (wait ${_bwait}s)"
    fi
}
trap cleanup_ticker EXIT INT TERM HUP PIPE QUIT   # Sprint 105 /review 必修: 加 HUP/PIPE/QUIT 5 信号 (SIGHUP/SIGPIPE/SIGQUIT 在某些 bash 不触发 EXIT trap, iTerm2 / VSCode terminal / ssh 断连常见)

# 3. 临时卸载 com.fuqing.uvicorn plist (防 launchd KeepAlive 自动重启)
#    跑完 ETL 后重新 launchctl bootstrap 加载, RunAtLoad=true 会自动启动 uvicorn.
#    之前用 SIGTERM + sleep 2, launchd 会在 ThrottleInterval=5s 后重启新 uvicorn,
#    新进程在 FastAPI startup 打开 DuckDB 锁, 跟 ETL 抢锁 (Sprint 105).
#    Sprint 128 fix #S105-2: cross-user check, 如果 uvicorn 由其他用户启动, 跳过 bootout
_UVICORN_PID=$(lsof -ti :8000 2>/dev/null | head -1)
if [ -n "$_UVICORN_PID" ]; then
    _UVICORN_UID=$(ps -o uid= -p "$_UVICORN_PID" 2>/dev/null | tr -d ' ')
    if [ -n "$_UVICORN_UID" ] && [ "$_UVICORN_UID" != "$UID" ]; then
        echo "  ⚠️  uvicorn (PID $_UVICORN_PID) 由 UID $_UVICORN_UID 启动 (当前 UID $UID), 跳过 bootout, 直接 SIGTERM"
        kill "$_UVICORN_PID" 2>/dev/null
        sleep 3
        if lsof -ti :8000 >/dev/null 2>&1; then
            kill -9 "$(lsof -ti :8000 2>/dev/null | head -1)" 2>/dev/null
            sleep 1
        fi
    fi
fi
if launchctl list 2>/dev/null | grep -q "com.fuqing.uvicorn"; then
    echo "  🔄 临时卸载 com.fuqing.uvicorn plist (防 launchd KeepAlive 重启)..."
    if launchctl bootout "gui/$UID/com.fuqing.uvicorn" 2>/dev/null; then
        export FQ_UVICORN_BOOTED_OUT=1
        # Sprint 202+ R7: uvicorn 真正退出需 4 件 signal 同时 release (L4.63)
        # ① lsof port 8000 为空 ② pgrep 'uvicorn_launchd.py' 无 ③ lsof <DuckDB file> 为空 ④ .duckdb.wal 不存在
        # 单纯 port release 不够: ThrottleInterval=5s + DuckDB WAL flush async + fd close 异步, uvicorn 重启期间 ATTACH read_only 异 config 跟 ETL read_write main 撞锁
        _duckdb_file="${DUCKDB_PATH:-$PROJECT_ROOT/data/processed/fuqing_crm.duckdb}"
        _wait=0; _wait_max=30
        while [ $_wait -lt $_wait_max ]; do
            _port_held=$(lsof -ti :8000 2>/dev/null | head -1)
            _proc_held=$(pgrep -f 'uvicorn_launchd.py' 2>/dev/null | head -1)
            _db_held=$(lsof -ti "$_duckdb_file" 2>/dev/null | head -1)
            _wal_held=""
            [ -f "${_duckdb_file}.wal" ] && _wal_held="yes"
            if [ -z "$_port_held" ] && [ -z "$_proc_held" ] && [ -z "$_db_held" ] && [ -z "$_wal_held" ]; then break; fi
            sleep 1; _wait=$((_wait + 1))
        done
        if [ $_wait -ge $_wait_max ]; then
            echo "  ❌ FATAL R7: uvicorn 未能在 ${_wait_max}s 内彻底退出 (port=${_port_held:-free} proc=${_proc_held:-none} db_lock=${_db_held:-free} wal=${_wal_held:-none}), 拒绝跑 ETL 防 DuckDB 异 config (L4.51 ATTACH read_only → ETL read_write main)"
            exit 1
        fi
        echo "  ✅ plist 已卸载, uvicorn 已死 (wait ${_wait}s, port/proc/db_lock/wal 全 release)"
    else
        # Sprint 202+ R7: SIGTERM fallback 同样必须 verify 4 件 signal 同时 release (L4.63)
        echo "  ⚠️  launchctl bootout 失败, fallback 到 SIGTERM 杀 uvicorn (重试 5 次 × 3s, 4-signal verify, 防 KeepAlive 死循环 + DuckDB 异 config)"
        _duckdb_file="${DUCKDB_PATH:-$PROJECT_ROOT/data/processed/fuqing_crm.duckdb}"
        _sigterm_retry=0
        while [ $_sigterm_retry -lt 5 ]; do
            UVICORN_PID=$(lsof -ti :8000 2>/dev/null | head -1)
            UVICORN_PROC=$(pgrep -f 'uvicorn_launchd.py' 2>/dev/null | head -1)
            DB_LOCK=$(lsof -ti "$_duckdb_file" 2>/dev/null | head -1)
            WAL_HELD=""; [ -f "${_duckdb_file}.wal" ] && WAL_HELD="yes"
            if [ -z "$UVICORN_PID" ] && [ -z "$UVICORN_PROC" ] && [ -z "$DB_LOCK" ] && [ -z "$WAL_HELD" ]; then
                echo "  ✅ uvicorn 全释放 (port/proc/db_lock/wal, SIGTERM retry $_sigterm_retry)"
                break
            fi
            [ -n "$UVICORN_PID" ] && kill "$UVICORN_PID" 2>/dev/null
            sleep 3
            if ! lsof -ti :8000 >/dev/null 2>&1 && [ -z "$(pgrep -f 'uvicorn_launchd.py' 2>/dev/null)" ]; then
                echo "  ✅ uvicorn 已退出 (SIGTERM PID $UVICORN_PID)"
                break
            fi
            # SIGTERM 无效, 用 SIGKILL
            UVICORN_PID=$(lsof -ti :8000 2>/dev/null | head -1)
            [ -n "$UVICORN_PID" ] && kill -9 "$UVICORN_PID" 2>/dev/null
            sleep 2
            _sigterm_retry=$(( _sigterm_retry + 1 ))
        done
        # 最终检查 (4-signal verify)
        if lsof -ti :8000 >/dev/null 2>&1 || pgrep -f 'uvicorn_launchd.py' >/dev/null 2>&1 || lsof -ti "$_duckdb_file" >/dev/null 2>&1 || [ -f "${_duckdb_file}.wal" ]; then
            echo "  ❌ SIGTERM fallback 5 次重试后 4-signal 仍被占用, 手动 kill 后重试:"
            echo "     lsof -ti :8000 | xargs kill -9"
            exit 1
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
