#!/bin/bash
# 芙清 CRM - ETL 手动触发脚本 (Sprint 10 之后)
#
# 背景: Sprint 10 之前用 launchd 每天 8:30 定时跑 (com.fuqing.etl.daily), 但实际
# 原始数据晚到 (8:30 经常没新数据), launchd 自动跑没意义. Sprint 10 改成手动触发.
#
# 用法:
#   ./scripts/etl/run-etl.sh                # 增量 update (推荐, 扫增量数据)
#   ./scripts/etl/run-etl.sh --full         # 强制全量重建
#   ./scripts/etl/run-etl.sh --inc          # 强制增量
#   ./scripts/etl/run-etl.sh --help         # 看 help
#
# 跑前必读:
#   - uvicorn 持 DuckDB 文件锁, 跑前 kill uvicorn PID 避免 IO Error:
#     lsof -ti :8000 | xargs kill
#   - 跑完建议重启 uvicorn 让前端加载新数据:
#     export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
#     PYTHONPATH=. nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 \
#       >> /tmp/fuqing-crm-backend.log 2>&1 &
#   - 跑批期间不要中断 (10-15 min), DuckDB 锁会卡其他读写
#   - 跑批日志 / 6 道门禁 / W3 6 断言 / W4 fact_rfm 增量 都在脚本 stdout
#
# 为什么不用 launchd:
#   - 原始数据晚到, 8:30 跑经常没新数据, 浪费跑批 + 容易撞 uvicorn
#   - 手动触发可以在加完 xlsx 后立即跑, 数据新鲜度最高
#   - 用户(PM) 方便操作, 不需要理解 launchd / cron

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON="/Users/hutou/homebrew/bin/python3"
LOG="/tmp/fuqing-etl-manual.log"

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"

# 0. 解析参数 (优先, --help 立即退出, 跳过锁检测)
MODE="${1:---update}"
if [ "$MODE" = "--help" ] || [ "$MODE" = "-h" ]; then
    echo "芙清 CRM - ETL 手动触发 (Sprint 10+)"
    echo ""
    echo "用法: $0 [--update|--inc|--full|--help]"
    echo ""
    echo "  --update (默认): 一键增量更新 (ETL + 淘客 + 状态刷新, 10-15 min)"
    echo "  --inc:          强制增量 (数据库必须已有数据)"
    echo "  --full:         强制全量重建 (DROP+CREATE 表, 5-10 min)"
    echo "  --help:         看这个 help"
    echo ""
    echo "zsh alias 推荐 (加到 ~/.zshrc):"
    echo "  alias fuqing-etl='/Users/hutou/Desktop/fuqin\\ date/sample-crm-analytics/scripts/etl/run-etl.sh'"
    echo "  alias fuqing-restart='lsof -ti :8000 | xargs kill; export HEALTH_API_KEY=\$(python3 -c \"import secrets; print(secrets.token_urlsafe(32))\"); cd \"/Users/hutou/Desktop/fuqin date/sample-crm-analytics\" && PYTHONPATH=\$(pwd) nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 >> /tmp/fuqing-crm-backend.log 2>&1 & '"
    echo ""
    echo "常用流程:"
    echo "  1. 把新 xlsx 放到 data/raw/ 下"
    echo "  2. fuqing-etl          # 一键跑增量"
    echo "  3. fuqing-restart      # 重启 uvicorn 加载新数据"
    exit 0
fi

# 1. 跑前环境检查
echo "============================================================"
echo "芙清 CRM - ETL 手动触发 (Sprint 10+)"
echo "============================================================"
echo "  project: $PROJECT_ROOT"
echo "  python:  $PYTHON"
echo "  log:     $LOG"
echo ""

# 2. uvicorn 持锁检测
UVICORN_PID=$(lsof -ti :8000 2>/dev/null | head -1)
if [ -n "$UVICORN_PID" ]; then
    echo "  ⚠️  uvicorn PID $UVICORN_PID 持 DuckDB 锁, 跑批期间前端会断"
    echo "     建议先 kill: lsof -ti :8000 | xargs kill"
    echo ""
fi

# 3. DuckDB 锁检测 (跟 uvicorn 同一文件)
DUCKDB_LOCK_HOLDER=$(lsof "$PROJECT_ROOT/data/processed/sample_crm.duckdb" 2>/dev/null | awk 'NR>1 {print $2}' | sort -u)
if [ -n "$DUCKDB_LOCK_HOLDER" ]; then
    echo "  ⚠️  DuckDB 锁被以下进程持有: $DUCKDB_LOCK_HOLDER"
    echo "     跑批会 IO Error. 建议先 kill:"
    echo "     lsof -ti $PROJECT_ROOT/data/processed/sample_crm.duckdb | xargs kill"
    echo ""
    read -p "  按 Enter 继续 (有锁), Ctrl+C 中断: "
fi

echo "  模式: $MODE"
echo "  开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

# 5. 跑 ETL
START=$(date +%s)
"$PYTHON" scripts/run_etl.py "$MODE" 2>&1 | tee "$LOG"
EXIT_CODE=${PIPESTATUS[0]}
ELAPSED=$(( $(date +%s) - START ))

echo ""
echo "============================================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "  ✅ ETL 完成 (exit 0, 耗时 ${ELAPSED}s)"
    echo ""
    echo "  下一步: 重启 uvicorn 让前端加载新数据"
    echo "    lsof -ti :8000 | xargs kill"
    echo "    export HEALTH_API_KEY=\$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    echo "    PYTHONPATH=. nohup python3 -m uvicorn backend.main:app \\"
    echo "      --host 0.0.0.0 --port 8000 >> /tmp/fuqing-crm-backend.log 2>&1 &"
else
    echo "  ❌ ETL 失败 (exit $EXIT_CODE, 耗时 ${ELAPSED}s)"
    echo "  查日志: $LOG"
    exit $EXIT_CODE
fi
echo "============================================================"
