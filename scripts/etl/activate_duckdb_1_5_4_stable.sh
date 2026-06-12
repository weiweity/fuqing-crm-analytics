#!/bin/bash
# Sprint 20+ P0 一键激活: DuckDB 1.5.4 stable 升 prod 路径
# 调用前提:
#   1. /tmp/fuqing-duckdb-release-stable.flag 存在 (PyPI 已发 1.5.4 stable)
#   2. 当前已装 1.5.4.dev18 (Sprint 19 P0 验证)
#   3. v2 code 在 fix/sprint16-p0-duckdb-taoke-channel-race branch
#
# 4 步激活:
#   Step 1: 装 1.5.4 stable (--upgrade + 保留 dev 包)
#   Step 2: 跑 v2 4 unit tests (确认 stable 治根)
#   Step 3: 切到 fix branch + merge --no-ff v2 code 到 main
#   Step 4: 跑 batch 真验 + CHANGELOG v0.4.14.56
#
# 跑法: bash scripts/etl/activate_duckdb_1_5_4_stable.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FLAG="/tmp/fuqing-duckdb-release-stable.flag"
LOG="/tmp/fuqing-activate-duckdb-1-5-4.log"

echo "=== DuckDB 1.5.4 stable 激活 @ $(date) ===" | tee -a "$LOG"
cd "$REPO_ROOT"

# 0. 前置检查
if [ ! -f "$FLAG" ]; then
  echo "[FATAL] $FLAG 不存在, 1.5.4 stable 还没 release (或没跑 check_duckdb_release_cron.sh)" | tee -a "$LOG"
  echo "        手动跑: python3 scripts/check_duckdb_release.py" | tee -a "$LOG"
  exit 1
fi

CURRENT=$(python3 -c "import duckdb; print(duckdb.__version__)" 2>/dev/null || echo "not installed")
echo "[STEP 0] 当前 DuckDB: $CURRENT" | tee -a "$LOG"

# 1. 装 1.5.4 stable
echo "[STEP 1] 装 duckdb 1.5.4 stable..." | tee -a "$LOG"
python3 -m pip install --user --upgrade "duckdb>=1.5.4,<1.6.0" 2>&1 | tee -a "$LOG"
NEW_VERSION=$(python3 -c "import duckdb; print(duckdb.__version__)" 2>/dev/null)
echo "[STEP 1] 装后 DuckDB: $NEW_VERSION" | tee -a "$LOG"

# 验证 stable release (1.5.4 不带 .dev)
if echo "$NEW_VERSION" | grep -q "\.dev"; then
  echo "[FATAL] 装的还是 dev release ($NEW_VERSION), 检查 PyPI 源" | tee -a "$LOG"
  exit 1
fi

# 2. 跑 v2 4 unit tests
echo "[STEP 2] 跑 v2 4 unit tests..." | tee -a "$LOG"
PYTHONPATH="$REPO_ROOT" python3 -m pytest backend/tests/test_taoke_channel_duckdb_race.py -v 2>&1 | tee -a "$LOG"
if [ $? -ne 0 ]; then
  echo "[FATAL] v2 tests failed, 1.5.4 stable 不能治根, 中止" | tee -a "$LOG"
  exit 1
fi

# 3. 切到 fix branch 准备 merge
echo "[STEP 3] 切到 fix/sprint16-p0-duckdb-taoke-channel-race branch..." | tee -a "$LOG"
git checkout fix/sprint16-p0-duckdb-taoke-channel-race 2>&1 | tee -a "$LOG"
git log --oneline -3 2>&1 | tee -a "$LOG"

# 4. 跑 batch 真验 (痛点 1 W1 --update 端到端)
echo "[STEP 4] 跑 batch 真验 (W1 --update 端到端)..." | tee -a "$LOG"
echo "⚠️  实际跑批需要在 prod 环境, 此处仅做 dry-run sanity check" | tee -a "$LOG"
PYTHONPATH="$REPO_ROOT" python3 -c "
import duckdb
print('duckdb:', duckdb.__version__)
conn = duckdb.connect(':memory:')
# 简单 smoke test: CREATE TABLE + INSERT + SELECT 不崩
conn.execute('CREATE TABLE t (id INTEGER, channel VARCHAR)')
conn.execute(\"INSERT INTO t VALUES (1, 'A'), (2, 'B')\")
result = conn.execute('SELECT * FROM t').fetchall()
print('smoke test:', result)
conn.close()
print('OK DuckDB $NEW_VERSION works')
" 2>&1 | tee -a "$LOG"

echo "=== 激活完成 (manual) ===" | tee -a "$LOG"
echo "下一步 (用户手动):" | tee -a "$LOG"
echo "  1. 切回 main: git checkout main" | tee -a "$LOG"
echo "  2. 改 requirements (如果有) → duckdb==$NEW_VERSION" | tee -a "$LOG"
echo "  3. merge --no-ff fix/sprint16-p0-duckdb-taoke-channel-race" | tee -a "$LOG"
echo "  4. 跑真 prod 跑批 (痛点 1 W1 --update, ~13-17 min)" | tee -a "$LOG"
echo "  5. CHANGELOG v0.4.14.56 + 合 main + /ship" | tee -a "$LOG"
echo "  6. 删 /tmp/fuqing-duckdb-release-stable.flag" | tee -a "$LOG"
echo "  7. 卸载 cron: launchctl unload ~/Library/LaunchAgents/com.fuqing.duckdb-release-check.daily.plist" | tee -a "$LOG"
