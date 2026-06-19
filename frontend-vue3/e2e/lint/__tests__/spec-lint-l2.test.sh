#!/usr/bin/env bash
# Sprint 50+ #S43-L2 regression test.
# 验证 L2 AST parser 对 multiline / nested string 有效, 且不扫注释和普通字符串。
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
LINT="$REPO_ROOT/frontend-vue3/e2e/lint/spec-lint-l2.py"

if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

run_lint() {
  set +e
  "$PYTHON_BIN" "$LINT" "$1" 2>&1
  echo "---EXIT:$?---"
  set -e
}

make_case_dir() {
  local name="$1"
  local dir="$TMPDIR/$name"
  mkdir -p "$dir"
  echo "$dir"
}

# Case 1: clean spec PASS, 注释/字符串里的 waitForTimeout 不误报
CASE_DIR=$(make_case_dir clean)
cat > "$CASE_DIR/clean.spec.ts" <<EOF
import { test, expect } from '@playwright/test';
test('clean', async ({ page }) => {
  // page.waitForTimeout(2000) in comment should not be linted.
  const note = 'expect(items.length).toBe(5); page.waitForTimeout(2000)';
  await expect(page).toBeTruthy();
  expect(note.length > 0).toBe(true);
});
EOF

OUTPUT=$(run_lint "$CASE_DIR")
if echo "$OUTPUT" | grep -q "0 violation" && echo "$OUTPUT" | grep -q "EXIT:0"; then
  echo "✅ Case 1 clean/comment/string PASS"
else
  echo "❌ Case 1 FAIL (expected 0 violation + exit 0):"
  echo "$OUTPUT"
  exit 1
fi

# Case 2: Rule 1 跨多行 catch (L1 grep 漏报)
CASE_DIR=$(make_case_dir multiline-rule1)
cat > "$CASE_DIR/multiline-rule1.spec.ts" <<EOF
import { test, expect } from '@playwright/test';
test('multiline rule 1', () => {
  expect(
    [1, 2, 3, 4, 5].length
  ).toBe(
    5
  );
});
EOF

OUTPUT=$(run_lint "$CASE_DIR")
if echo "$OUTPUT" | grep -q "Rule 1" && echo "$OUTPUT" | grep -q "EXIT:1"; then
  echo "✅ Case 2 Rule 1 跨多行 catch"
else
  echo "❌ Case 2 FAIL (expected Rule 1 violation + exit 1):"
  echo "$OUTPUT"
  exit 1
fi

# Case 3: Rule 2 nested/template string 参数 catch
CASE_DIR=$(make_case_dir template-rule2)
cat > "$CASE_DIR/template-rule2.spec.ts" <<EOF
import { test } from '@playwright/test';
test('template rule 2', async ({ page }) => {
  await page.waitForTimeout(
    \`\${1000}\`
  );
});
EOF

OUTPUT=$(run_lint "$CASE_DIR")
if echo "$OUTPUT" | grep -q "Rule 2" && echo "$OUTPUT" | grep -q "EXIT:1"; then
  echo "✅ Case 3 Rule 2 nested/template string catch"
else
  echo "❌ Case 3 FAIL (expected Rule 2 violation + exit 1):"
  echo "$OUTPUT"
  exit 1
fi

# Case 4: Rule 3 scope-level Authorization WARN, 不阻塞 exit
CASE_DIR=$(make_case_dir scope-rule3)
cat > "$CASE_DIR/scope-rule3.spec.ts" <<EOF
import { test } from '@playwright/test';
test('scope rule 3', async ({ page }) => {
  const resp = await page.request.get('/api/v1/test');
});
EOF

OUTPUT=$(run_lint "$CASE_DIR")
if echo "$OUTPUT" | grep -q "Rule 3" && echo "$OUTPUT" | grep -q "EXIT:0"; then
  echo "✅ Case 4 Rule 3 scope-level warn"
else
  echo "❌ Case 4 FAIL (expected Rule 3 warn + exit 0):"
  echo "$OUTPUT"
  exit 1
fi

# Case 5: Rule 3 变量间接传 headers.Authorization 不误报
CASE_DIR=$(make_case_dir scope-rule3-auth)
cat > "$CASE_DIR/scope-rule3-auth.spec.ts" <<EOF
import { test } from '@playwright/test';
test('scope rule 3 auth', async ({ page }) => {
  const headers = { Authorization: 'Bearer token' };
  const options = { headers };
  const resp = await page.request.get('/api/v1/test', options);
});
EOF

OUTPUT=$(run_lint "$CASE_DIR")
if echo "$OUTPUT" | grep -q "0 violation, 0 warn" && echo "$OUTPUT" | grep -q "EXIT:0"; then
  echo "✅ Case 5 Rule 3 variable Authorization PASS"
else
  echo "❌ Case 5 FAIL (expected 0 warn + exit 0):"
  echo "$OUTPUT"
  exit 1
fi

echo ""
echo "✅ spec-lint-l2 test: 5/5 case pass (Sprint 50+ #S43-L2)"
