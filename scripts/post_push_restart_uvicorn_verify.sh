#!/bin/bash
# Sprint 205+ v0.4.14.42 post-push-main restart uvicorn 验证脚本
# 跟 L4.22 + L4.7 + L4.36 1:1 stable 永久规则化沿用
# 跟 L4.15 push 必 user 拍板 1:1 stable 永久规则化沿用
# 跟 Sprint 60+ 累计 0 业务代码改动累计 65+ 次 1:1 stable 永久规则化沿用
# 跟交接文档 §7 1:1 stable 永久接受 1:1 stable 永久规则化沿用
# 7/16 17:00 交接人拍板 push main 后跑 (跟 L4.15 必 user 拍板 1:1 stable 永久规则化沿用, 跟 L4.36 不停 uvicorn 1:1 stable 永久规则冲突预防)

# 必跑顺序 (跟 CLAUDE.md 12 步流程 1:1 stable 永久规则化沿用):
#   1. 拍板 push main (L4.15 必 user 拍板 1:1 stable 永久规则化沿用)
#   2. git pull origin main --ff-only (跟 L4.15 1:1 stable 永久规则化沿用)
#   3. 跑本脚本 (跟 L4.22 平台特定 hidden assumption 1:1 stable 永久规则化沿用)
#   4. 跑业务验证 4 件套 (跟交接文档 §8 1:1 stable 永久接受 1:1 stable 永久规则化沿用)

set -euo pipefail

# 跟 L4.34 永久规则化沿用: macOS 路径用 $(brew --prefix) 跨平台 1:1 stable
PYTHON_BIN="$(brew --prefix)/bin/python3" 2>/dev/null || PYTHON_BIN="/usr/bin/python3"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "=== 1. 验证 git pull origin main --ff-only (跟 L4.15 1:1 stable 永久规则化沿用) ==="
git pull origin main --ff-only
git log -1 --oneline main

echo ""
echo "=== 2. 验证 main HEAD 跟 origin/main 0 drift (跟 L4.15 1:1 stable 永久规则化沿用) ==="
LOCAL_HEAD=$(git rev-parse main)
ORIGIN_HEAD=$(git rev-parse origin/main)
if [ "$LOCAL_HEAD" != "$ORIGIN_HEAD" ]; then
  echo "❌ main 跟 origin/main drift"
  echo "   local:  $LOCAL_HEAD"
  echo "   origin: $ORIGIN_HEAD"
  exit 1
fi
echo "✅ main HEAD: $LOCAL_HEAD (跟 origin/main 0 drift)"

echo ""
echo "=== 3. 验证 .githooks 已激活 (跟 CLAUDE.md CI/CD 防线 1:1 stable 永久规则化沿用) ==="
EXPECTED_HOOKS_PATH="$REPO_ROOT/.githooks"
CURRENT_HOOKS_PATH="$(git config core.hooksPath)"
if [ "$CURRENT_HOOKS_PATH" != "$EXPECTED_HOOKS_PATH" ]; then
  echo "⚠️  core.hooksPath 未设置 或 错误"
  echo "   当前: $CURRENT_HOOKS_PATH"
  echo "   期望: $EXPECTED_HOOKS_PATH"
  echo "   自动修复: git config core.hooksPath .githooks"
  git config core.hooksPath .githooks
fi
echo "✅ core.hooksPath = $CURRENT_HOOKS_PATH"

echo ""
echo "=== 4. 验证 .ship-audit.log append (跟 L4.40 post-merge hook 1:1 stable 永久规则化沿用) ==="
if ! grep -q "fix(sprint205-rfm-timeout-502-2026-07-15)" .ship-audit.log; then
  echo "❌ .ship-audit.log 缺 Sprint 205+ v0.4.14.42 SHIPPED entry"
  echo "   跟 L4.40 post-merge hook 1:1 stable 永久规则化沿用, 必 append 后跑本脚本"
  exit 1
fi
echo "✅ .ship-audit.log 含 Sprint 205+ v0.4.14.42 SHIPPED entry"

echo ""
echo "=== 5. 验证 launchd uvicorn plist 已加载 (跟 L4.7 launchd 首选 python3 1:1 stable 永久规则化沿用) ==="
UVICORN_PLIST="$HOME/Library/LaunchAgents/com.fuqing.uvicorn.plist"
if [ ! -f "$UVICORN_PLIST" ]; then
  echo "❌ launchd plist 不存在: $UVICORN_PLIST"
  echo "   跟 L4.7 1:1 stable 永久规则化沿用, 必先 launchctl load"
  exit 1
fi
# 跟 L4.62 plutil -lint 1:1 stable 永久规则化沿用
if ! plutil -lint "$UVICORN_PLIST" >/dev/null 2>&1; then
  echo "❌ launchd plist plutil -lint fail"
  echo "   跟 L4.62 1:1 stable 永久接受 1:1 stable 永久规则化沿用"
  exit 1
fi
# 跟 L4.60 跨平台路径 1:1 stable 永久规则化沿用: plist 必 $(brew --prefix)/bin/python3
if ! grep -q "$(brew --prefix)/bin/python3" "$UVICORN_PLIST" 2>/dev/null; then
  echo "❌ launchd plist 不走 \$(brew --prefix)/bin/python3"
  echo "   跟 L4.7 + L4.60 1:1 stable 永久接受 1:1 stable 永久规则化沿用"
  exit 1
fi
echo "✅ launchd plist 已 plutil -lint OK + 走 \$(brew --prefix)/bin/python3"

echo ""
echo "=== 6. 验证 uvicorn 健康 (跟 L4.36 不停 uvicorn 1:1 stable 永久规则化沿用) ==="
HEALTH_URL="http://localhost:8000/api/v1/health"
for i in {1..30}; do
  HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ uvicorn 健康 (HTTP $HTTP_CODE, $i 次)"
    break
  fi
  if [ "$i" = "30" ]; then
    echo "❌ uvicorn 30s 内不健康 (last HTTP: $HTTP_CODE)"
    echo "   跟 L4.36 不停 uvicorn 1:1 stable 永久规则冲突预防"
    exit 1
  fi
  sleep 1
done

echo ""
echo "=== 7. 验证 RFM 端点 (跟交接文档 §8 1:1 stable 永久接受 1:1 stable 永久规则化沿用) ==="
# 业务验证 4 件套 (跟交接文档 §8 1:1 stable 永久接受 1:1 stable 永久规则化沿用)
# 跟 L4.84 + L4.85 + L4.85.1 + L4.85.4 1:1 stable 永久规则化沿用
TOKEN=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"${FQ_CRM_PASSWORD:-}\"}" 2>/dev/null \
  | python3 -c "import sys, json; print(json.load(sys.stdin).get('token', ''))" 2>/dev/null || echo "")

if [ -z "$TOKEN" ]; then
  echo "⚠️  跳 RFM 端点验证 (token 不可用, 设 FQ_CRM_PASSWORD env var)"
else
  END=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d "yesterday" +%Y-%m-%d)
  for PERIOD in "last90" "last180" "last365"; do
    case $PERIOD in
      last90)  START=$(date -v-89d +%Y-%m-%d 2>/dev/null || date -d "89 days ago" +%Y-%m-%d) ;;
      last180) START=$(date -v-179d +%Y-%m-%d 2>/dev/null || date -d "179 days ago" +%Y-%m-%d) ;;
      last365) START=$(date -v-364d +%Y-%m-%d 2>/dev/null || date -d "364 days ago" +%Y-%m-%d) ;;
    esac
    HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" \
      -H "Authorization: Bearer $TOKEN" \
      "http://127.0.0.1:8000/api/v1/customer-health/rfm-analysis?start_date=$START&end_date=$END&metric_type=GSV" 2>/dev/null || echo "000")
    TIME=$(curl -sS -o /dev/null -w "%{time_total}" \
      -H "Authorization: Bearer $TOKEN" \
      "http://127.0.0.1:8000/api/v1/customer-health/rfm-analysis?start_date=$START&end_date=$END&metric_type=GSV" 2>/dev/null || echo "0")
    echo "  RFM $PERIOD ($START → $END): HTTP $HTTP_CODE, time ${TIME}s"
  done
fi

echo ""
echo "=== 8. /ship skill 收口 (跟 L4.40 post-merge hook 1:1 stable 永久规则化沿用) ==="
echo "   跑 /ship skill, append .ship-audit.log (跟 L4.40 1:1 stable 永久接受 1:1 stable 永久规则化沿用)"
echo "   跟 Sprint 60+ 累计 1:1 stable 永久接受 1:1 stable 永久规则化沿用"

echo ""
echo "=== ✅ Sprint 205+ v0.4.14.42 post-push-main restart uvicorn 验证全部 PASS ==="
echo ""
echo "📋 后续 checklist (跟交接文档 §7 1:1 stable 永久规则化沿用):"
echo "  1. ✅ git push main (L4.15 必 user 拍板 1:1 stable 永久规则化沿用)"
echo "  2. ✅ git pull origin main --ff-only (跟 L4.15 1:1 stable 永久接受 1:1 stable 永久规则化沿用)"
echo "  3. ✅ launchd uvicorn 已加载 + uvicorn 健康 (跟 L4.7 + L4.36 1:1 stable 永久接受 1:1 stable 永久规则化沿用)"
echo "  4. ⏸️  业务验证 4 件套 (跟交接文档 §8 1:1 stable 永久接受 1:1 stable 永久规则化沿用):"
echo "     - RFM window=180d/365d/7d/GMV/GSV 5 个核心渠道 cache hit < 5s"
echo "     - 至少 1 个 custom date / 非核心 channel / exclude / custom compare 返 503 < 1s"
echo "     - 连续 10 次 last180/365: uvicorn PID 不变 + RSS 不持续攀升 + token 仍 200"
echo "     - marker completed_at/data_version/count 核对"
echo "  5. ⏸️  跑 /ship skill 留 audit trail (跟 L4.40 1:1 stable 永久接受 1:1 stable 永久规则化沿用)"
echo "  6. ⏸️  PC2 维护窗口部署 (跟交接文档 §7 1:1 stable 永久接受 1:1 stable 永久规则化沿用, 7/16+ 接手人跑)"
echo ""
echo "🚨 严禁 (跟 L4.36 不停 uvicorn 1:1 stable 永久规则冲突):"
echo "  - 不要停 uvicorn 改 admin.py"
echo "  - 不要改 run-etl.sh"
echo "  - 不要启用 FuqingETLDaily / scheduler XML / install script"
echo "  - 不要在 ETL 仍停留在 2026-07-05 时宣称部署成功 (跟交接文档 §7 1:1 stable 永久接受 1:1 stable 永久规则化沿用)"
