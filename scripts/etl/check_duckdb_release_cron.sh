#!/bin/bash
# Sprint 20+ P0 daily cron: 检查 DuckDB 1.5.4 stable release
# 输出到 /tmp/fuqing-duckdb-release-check.log (launchd 接管 stdout)
# 1.5.4 stable release 后写 /tmp/fuqing-duckdb-release-stable.flag 触发激活

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG="/tmp/fuqing-duckdb-release-check.log"
FLAG="/tmp/fuqing-duckdb-release-stable.flag"

echo "=== DuckDB release check @ $(date) ===" >> "$LOG"

cd "$REPO_ROOT"
PYTHONPATH="$REPO_ROOT" python3 scripts/check_duckdb_release.py >> "$LOG" 2>&1 || {
  echo "[ERROR] check_duckdb_release.py failed, see $LOG" >> "$LOG"
  exit 1
}

# 检查 1.5.4 stable 是否 release
STABLE_RELEASED=$(PYTHONPATH="$REPO_ROOT" python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT/scripts')
from check_duckdb_release import _check_pypi_duckdb_releases
data = _check_pypi_duckdb_releases()
# latest_stable 形如 1.5.4 (>= 1.5.4 包含 1.5.4/1.5.5/...)
print('yes' if data.get('latest_stable', '').startswith('1.5.4') or
      any(v.startswith('1.5.4') for v in data.get('all_stable_with_1_5_4_prefix', []))
      else 'no')
" 2>/dev/null || echo "no")

if [ "$STABLE_RELEASED" = "yes" ]; then
  if [ ! -f "$FLAG" ]; then
    echo "[ALERT] DuckDB 1.5.4 stable RELEASED! $(date)" >> "$LOG"
    echo "→ 激活 Sprint 16 P0 治根路径: bash scripts/etl/activate_duckdb_1_5_4_stable.sh" >> "$LOG"
    touch "$FLAG"
    # 飞书告警 (用现有 scripts/etl/common/lark.py)
    PYTHONPATH="$REPO_ROOT" python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT')
try:
    from scripts.etl.common.lark import _send_lark_alert
    _send_lark_alert(
        title='🚀 DuckDB 1.5.4 stable released',
        msg='Sprint 20+ P0 激活窗口开启\n\n请跑: bash scripts/etl/activate_duckdb_1_5_4_stable.sh\n\n证据: /tmp/fuqing-duckdb-release-check.log'
    )
except Exception as e:
    print(f'[WARN] lark alert failed: {e}', file=sys.stderr)
" 2>&1 | tee -a "$LOG"
  else
    echo "[INFO] Flag file already exists, stable release confirmed previously" >> "$LOG"
  fi
else
  echo "[INFO] 1.5.4 stable NOT released yet, keep waiting" >> "$LOG"
fi
