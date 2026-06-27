#!/usr/bin/env bash
# Sprint 50+ #S43-L2: L2 AST parser + L1 fallback wrapper.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
L2_SCRIPT="$SCRIPT_DIR/spec-lint-l2.py"
L1_SCRIPT="$SCRIPT_DIR/spec-lint.sh"

if [ -n "${FQ_SPEC_LINT_PYTHON:-}" ]; then
  PYTHON_CANDIDATES=("$FQ_SPEC_LINT_PYTHON")
elif [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PYTHON_CANDIDATES=("$REPO_ROOT/.venv/bin/python" python3)
else
  PYTHON_CANDIDATES=(python3)
fi

for PYTHON_BIN in "${PYTHON_CANDIDATES[@]}"; do
  if command -v "$PYTHON_BIN" >/dev/null 2>&1 && "$PYTHON_BIN" -c "import tree_sitter, tree_sitter_typescript" >/dev/null 2>&1; then
    exec "$PYTHON_BIN" "$L2_SCRIPT" "$@"
  fi
done

echo "⚠️  spec-lint-l2 fallback to L1 (tree-sitter 不可用)"

if [ "${1:-}" != "--specs-dir" ] && [ -n "${1:-}" ] && [ -d "$1" ]; then
  exec bash "$L1_SCRIPT" --specs-dir "$1"
fi

exec bash "$L1_SCRIPT" "$@"
