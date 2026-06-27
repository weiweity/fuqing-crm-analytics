#!/usr/bin/env bash
# Sprint 42 spec-lint regression test
# Sprint 24+ P3 教训: 故意破坏验证 test 真 FAIL, 恢复验证 PASS
#
# 验证 spec-lint.sh 3 条规则都真生效:
# - Case 1: clean spec → PASS (0 violation)
# - Case 2: Rule 1 违反 (hardcode 长度) → FAIL
# - Case 3: Rule 2 违反 (waitForTimeout) → FAIL
set -e

LINT="$(cd "$(dirname "$0")/.." && pwd)/spec-lint.sh"
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

mkdir -p "$TMPDIR/frontend-vue3/e2e"
TEST_SPECS_DIR="$TMPDIR/frontend-vue3/e2e"

# 跑 spec-lint 但不中断 set -e (case 2/3 期望 spec-lint exit 1)
run_lint() {
  set +e
  bash "$LINT" --specs-dir "$TEST_SPECS_DIR" 2>&1
  echo "---EXIT:$?---"
  set -e
}

# Case 1: PASS (clean spec)
cat > "$TEST_SPECS_DIR/clean.spec.ts" <<EOF
import { test, expect } from '@playwright/test';
test('clean', async ({ page }) => {
  await expect(page).toBeTruthy();
});
EOF

OUTPUT=$(run_lint)
if echo "$OUTPUT" | grep -q "0 violation" && ! echo "$OUTPUT" | grep -q "EXIT:1"; then
  echo "✅ Case 1 clean PASS"
else
  echo "❌ Case 1 FAIL (expected 0 violation + exit 0):"
  echo "$OUTPUT"
  exit 1
fi

# Case 2: FAIL Rule 1 (hardcode 业务数据长度)
cat > "$TEST_SPECS_DIR/bad-rule1.spec.ts" <<EOF
import { test, expect } from '@playwright/test';
test('bad rule 1', () => {
  expect([1,2,3,4,5].length).toBe(5);
});
EOF

OUTPUT=$(run_lint)
if echo "$OUTPUT" | grep -q "Rule 1" && echo "$OUTPUT" | grep -q "EXIT:1"; then
  echo "✅ Case 2 Rule 1 FAIL (detected + exit 1)"
else
  echo "❌ Case 2 FAIL (expected Rule 1 violation + exit 1):"
  echo "$OUTPUT"
  exit 1
fi

# Case 3: FAIL Rule 2 (waitForTimeout)
cat > "$TEST_SPECS_DIR/bad-rule2.spec.ts" <<EOF
import { test, expect } from '@playwright/test';
test('bad rule 2', async ({ page }) => {
  await page.waitForTimeout(2000);
});
EOF

OUTPUT=$(run_lint)
if echo "$OUTPUT" | grep -q "Rule 2" && echo "$OUTPUT" | grep -q "EXIT:1"; then
  echo "✅ Case 3 Rule 2 FAIL (detected + exit 1)"
else
  echo "❌ Case 3 FAIL (expected Rule 2 violation + exit 1):"
  echo "$OUTPUT"
  exit 1
fi

echo ""
echo "✅ spec-lint test: 3/3 case pass (Sprint 42 #S42-1)"
