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

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON="/Users/hutou/homebrew/bin/python3"
LOG="/tmp/fuqing-etl-manual.log"

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"

# 0. 解析参数 (优先, --help 立即退出, 跳过锁检测)
# 1. 选模式 (命令行参数优先, 无参数则交互选择)
if [ -n "$1" ] && [ "$1" != "--help" ] && [ "$1" != "-h" ]; then
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

# 3. 自动停 uvicorn (释放 DuckDB 锁)
UVICORN_PID=$(lsof -ti :8000 2>/dev/null | head -1)
if [ -n "$UVICORN_PID" ]; then
    echo "  🔄 自动停 uvicorn PID $UVICORN_PID (释放 DuckDB 锁)..."
    kill "$UVICORN_PID" 2>/dev/null
    sleep 2
    if lsof -ti :8000 >/dev/null 2>&1; then
        echo "  ⚠️  uvicorn 未停, 强制 kill..."
        kill -9 "$UVICORN_PID" 2>/dev/null
        sleep 1
    fi
    echo "  ✅ uvicorn 已停"
else
    echo "  ✅ uvicorn 未运行 (无需停)"
fi

# 4. DuckDB 锁最终检测
DUCKDB_LOCK_HOLDER=$(lsof "$PROJECT_ROOT/data/processed/fuqing_crm.duckdb" 2>/dev/null | awk 'NR>1 {print $2}' | sort -u)
if [ -n "$DUCKDB_LOCK_HOLDER" ]; then
    echo "  ❌ DuckDB 锁被以下进程持有: $DUCKDB_LOCK_HOLDER"
    echo "     跑批会 IO Error. 手动 kill 后重试:"
    echo "     lsof -ti $PROJECT_ROOT/data/processed/fuqing_crm.duckdb | xargs kill"
    exit 1
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

# 保险清理: 不管脚本如何退出 (set -e 触发 / 正常完成 / Ctrl+C) 都 kill ticker + ETL 子进程
cleanup_ticker() {
    if [ -n "${TICKER_PID:-}" ]; then
        kill "$TICKER_PID" 2>/dev/null || true
        wait "$TICKER_PID" 2>/dev/null || true
    fi
    # 杀残留的 Python ETL 进程 (防止 Ctrl+C 后 Python 子进程继续持有 DuckDB 锁)
    pkill -f "run_etl.py.*$MODE" 2>/dev/null || true
}
trap cleanup_ticker EXIT INT TERM

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

# 6. 自动重启 uvicorn (不管 ETL 成功失败都重启, 让前端可用)
echo ""
echo "  🔄 自动重启 uvicorn..."
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
nohup "$PYTHON" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 \
    >> /tmp/fuqing-crm-backend.log 2>&1 &
NEW_PID=$!
disown $NEW_PID 2>/dev/null || true
sleep 3
if lsof -ti :8000 >/dev/null 2>&1; then
    echo "  ✅ uvicorn 已重启 (PID $NEW_PID)"
    echo "  前端: http://localhost:5173"
    echo "  API:  http://localhost:8000/docs"
else
    echo "  ⚠️  uvicorn 重启可能失败, 手动检查:"
    echo "    lsof -ti :8000"
fi
echo "============================================================"

if [ $EXIT_CODE -ne 0 ]; then
    exit $EXIT_CODE
fi
