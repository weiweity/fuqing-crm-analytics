#!/usr/bin/env bash
# Sprint 18 #142 — 验证 pre-commit ground-truth-lint hook 触发.
#
# 流程:
#   1. 跑 baseline lint 看 issue 数
#   2. 故意改 1 个 contract 字段, 让它违规
#   3. 跑 pre-commit framework (或 fallback 直接跑 entry)
#   4. 验 hook 拦到 (exit 1)
#   5. revert 改动
#   6. 验 hook 通过 (exit 0)
#
# 用法:
#   cd <repo-root>
#   bash scripts/test-precommit.sh
#
# 退出码:
#   0 全部验证通过
#   1 hook 没拦到 bad change
#   2 pre-commit framework 未装 + 直接跑 lint entry 也失败

set -euo pipefail

# 强制从 repo root 跑 (pre-commit framework 默认 cwd 是 git root)
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "=== Sprint 18 #142 — pre-commit ground-truth-lint hook 验证 ==="
echo ""
echo "REPO_ROOT: $REPO_ROOT"
echo "BRANCH:    $(git branch --show-current)"
echo ""

# === Step 1: baseline lint ===
echo "--- Step 1: baseline lint ---"
LINT_OUTPUT=$(python3 -m backend.contracts._lint 2>&1 || true)
LINT_RC=$?
LINT_ISSUE_COUNT=$(echo "$LINT_OUTPUT" | grep -cE "^\[ERROR\]" || true)
echo "lint exit: $LINT_RC, issue count: $LINT_ISSUE_COUNT"
echo ""

# === Step 2: 故意制造 1 个 R1 违规 ===
echo "--- Step 2: 故意制造 1 个 R1 违规 (改 backend/contracts/category.py 加 1 个裸 float _ratio 字段) ---"

# 找 1 个安全 contract 文件做 monkey patch
TARGET="backend/contracts/category.py"
BACKUP="${TARGET}.test-precommit.bak"

# 备份
cp "$TARGET" "$BACKUP"

# 在文件末尾追加 1 个 BaseModel 子类含 1 个裸 float _ratio 字段 (触发 R1)
cat >> "$TARGET" <<'PY_EOF'


# Sprint 18 #142 test-precommit — 故意制造 R1 违规 (裸 float _ratio 字段)
class TestPrecommitR1Violation(BaseModel):
    bad_field_ratio: float = 0.42  # BAD: 字段名以 _ratio 结尾, 必须 RatioField
PY_EOF

echo "已注入 R1 违规到 $TARGET (备份在 $BACKUP)"
echo ""

# === Step 3: 跑 hook entry ===
echo "--- Step 3: 跑 hook entry (python -m backend.contracts._lint) ---"
# 临时关 set -e: issue > 0 时 _lint 返 1, 我们要捕获这个 rc 不是失败
set +e
HOOK_OUTPUT=$(python3 -m backend.contracts._lint 2>&1)
HOOK_RC=$?
set -e
HOOK_ISSUE_COUNT=$(echo "$HOOK_OUTPUT" | grep -cE "^\[ERROR\]" || true)
echo "hook exit: $HOOK_RC, issue count: $HOOK_ISSUE_COUNT"
echo ""

# === Step 4: 验 hook 拦到 ===
echo "--- Step 4: 验 hook 拦到 (期望 exit=1, issue count > baseline) ---"
if [ "$HOOK_RC" -ne 1 ]; then
  echo "FAIL: hook 没拦到 bad change (期望 exit=1, 实际 exit=$HOOK_RC)"
  cp "$BACKUP" "$TARGET"
  rm "$BACKUP"
  exit 1
fi
if [ "$HOOK_ISSUE_COUNT" -le "$LINT_ISSUE_COUNT" ]; then
  echo "FAIL: hook issue count ($HOOK_ISSUE_COUNT) 没比 baseline ($LINT_ISSUE_COUNT) 多"
  echo "   说明 R1 违规没触发新 issue"
  cp "$BACKUP" "$TARGET"
  rm "$BACKUP"
  exit 1
fi
echo "PASS: hook 拦到 bad change (baseline=$LINT_ISSUE_COUNT, after=$HOOK_ISSUE_COUNT, delta=$((HOOK_ISSUE_COUNT - LINT_ISSUE_COUNT)))"
echo ""

# === Step 5: revert 改动 ===
echo "--- Step 5: revert 改动 ---"
cp "$BACKUP" "$TARGET"
rm "$BACKUP"
echo "已 restore $TARGET (删 $BACKUP)"
echo ""

# === Step 6: 验 hook 通过 ===
echo "--- Step 6: 验 hook 通过 (期望 issue count = baseline) ---"
FINAL_OUTPUT=$(python3 -m backend.contracts._lint 2>&1 || true)
FINAL_RC=$?
FINAL_ISSUE_COUNT=$(echo "$FINAL_OUTPUT" | grep -cE "^\[ERROR\]" || true)
echo "final exit: $FINAL_RC, issue count: $FINAL_ISSUE_COUNT"
echo ""

if [ "$FINAL_ISSUE_COUNT" -ne "$LINT_ISSUE_COUNT" ]; then
  echo "FAIL: revert 后 issue count ($FINAL_ISSUE_COUNT) != baseline ($LINT_ISSUE_COUNT)"
  exit 1
fi
echo "PASS: revert 后 issue count 跟 baseline 一致"
echo ""

# === Step 7 (可选): 跑 pre-commit framework ===
if command -v pre-commit >/dev/null 2>&1; then
  echo "--- Step 7: 跑 pre-commit framework (--all-files) ---"
  if pre-commit run contract-ground-truth-lint --all-files 2>&1; then
    echo "PASS: pre-commit framework 跑 contract hook 成功"
  else
    echo "INFO: pre-commit framework hook 失败 (期望, baseline 还有 $LINT_ISSUE_COUNT issue)"
    echo "   Sprint 18 #141 治根后会 pass"
  fi
else
  echo "--- Step 7: pre-commit framework 未装, 跳过 ---"
  echo "   装: pipx install pre-commit"
  echo "   然后跑: pre-commit run contract-ground-truth-lint --all-files"
fi
echo ""

echo "=== 验证完成 ==="
echo ""
echo "总结:"
echo "  baseline issue:    $LINT_ISSUE_COUNT"
echo "  bad change issue:  $HOOK_ISSUE_COUNT (期望 > baseline)"
echo "  revert issue:      $FINAL_ISSUE_COUNT (期望 = baseline)"
echo ""
echo "  hook 拦到违规:     YES (Sprint 18 #142 期望行为)"
echo "  revert 后复原:     YES"
echo ""
if [ "$LINT_ISSUE_COUNT" -eq 0 ]; then
  echo "  当前状态: lint 0 issue (Sprint 18 #141 已合 #142 # 期望完美闭环)"
else
  echo "  当前状态: lint $LINT_ISSUE_COUNT issue (#141 治根后会降到 0, #142 hook 拦到期望)"
fi
echo ""
echo "退出码 0"
