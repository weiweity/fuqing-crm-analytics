#!/usr/bin/env bash
# spec-lint: e2e spec 写法 lint (Sprint 42 #S42-1)
# 3 条规则防 Sprint 41.5/41.6/41.9 类实战 fix 复发
# 跟 ground-truth-lint 一样 non-blocking 起步, 1-2 sprint 观察 false positive 率
#
# 关联:
# - docs/operating/ci-defense-playbook.md(预防层 + 4 条原则)
# - docs/operating/ci-e2e-history.md(CI e2e 实施历程, 实战教训)
# - CLAUDE.md L5.2(spec 写法原则)
#
# 用法:
#   bash spec-lint.sh                          # 默认扫 frontend-vue3/e2e/*.spec.ts
#   bash spec-lint.sh --specs-dir <path>       # 自定义目录(测试用)
set -e

# 默认 specs-dir
SPECS_DIR="frontend-vue3/e2e"
if [ "$1" = "--specs-dir" ] && [ -n "$2" ]; then
  SPECS_DIR="$2"
fi

VIOLATIONS=0
WARNS=0
SPECS_CHECKED=0

for spec in $(find "$SPECS_DIR" -name '*.spec.ts' -not -path '*/node_modules/*' -not -path '*/screenshots/*' 2>/dev/null); do
  SPECS_CHECKED=$((SPECS_CHECKED+1))

  # Rule 1: 不 hardcode 业务数据长度 (e.g. expect(arr.length).toBe(5))
  if grep -nE 'expect\([^)]*\.length\)\.toBe\([0-9]+\)' "$spec" 2>/dev/null; then
    echo "❌ $spec: Rule 1 - hardcode 业务数据长度 (用 length > 0 替, Sprint 41.6 教训)"
    VIOLATIONS=$((VIOLATIONS+1))
  fi

  # Rule 2: 不 waitForTimeout 死等 (用 waitForSelector / expect.toBeVisible 替)
  if grep -nE 'waitForTimeout\([0-9]+\)' "$spec" 2>/dev/null; then
    echo "❌ $spec: Rule 2 - waitForTimeout 死等 (用 waitForSelector 替, Sprint 41.8/41.9 教训)"
    VIOLATIONS=$((VIOLATIONS+1))
  fi

  # Rule 3: page.request 不带 Authorization WARN (Rule 3 = WARN 不 FAIL, 防 login.spec.ts 误报)
  REQ_LINES=$(grep -nE 'page\.request\.(get|post|put|delete)' "$spec" 2>/dev/null || true)
  if [ -n "$REQ_LINES" ]; then
    # grep -c 找不到时 exit 1, 但 stdout 仍输出 "0", 用 2>/dev/null 抑制 + tr 清空
    HAS_AUTH=$(grep -c 'Authorization' "$spec" 2>/dev/null | tr -d '\n' || true)
    HAS_AUTH=${HAS_AUTH:-0}
    if [ -z "$HAS_AUTH" ] || [ "$HAS_AUTH" = "0" ]; then
      echo "⚠️  $spec: Rule 3 - page.request 缺 Authorization (Sprint 41.5 教训, 加 { headers: { Authorization: ... } })"
      WARNS=$((WARNS+1))
    fi
  fi
done

if [ $VIOLATIONS -eq 0 ]; then
  echo "✅ spec-lint: 0 violation, $WARNS warn ($SPECS_CHECKED spec checked)"
  exit 0
fi

# Violations found
if [ "$1" = "--advisory" ] || [ "$2" = "--advisory" ]; then
  # 起步 advisory 模式 (Sprint 42 #S42-1): violations 报告 + warn, exit 0
  # 1-2 sprint 观察 false positive 率后再改 blocking
  echo "⚠️  spec-lint: $VIOLATIONS violations, $WARNS warn ($SPECS_CHECKED spec checked) [advisory mode, exit 0]"
  exit 0
fi

echo "❌ spec-lint: $VIOLATIONS violations, $WARNS warn ($SPECS_CHECKED spec checked)"
exit 1
