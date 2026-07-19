#!/usr/bin/env bash
# Emit pytest --deselect flags from C-class SSOT file (one line = one nodeid).
# Usage:
#   mapfile -t args < <(bash scripts/ci/pytest_deselect_args.sh)
#   pytest backend/tests/ -q -m "not slow" "${args[@]}"
# Or:
#   eval "pytest backend/tests/ -q -m \"not slow\" $(bash scripts/ci/pytest_deselect_args.sh)"
#
# Track A 2026-07-19: shared by pre-push + lint.yml + nightly.yml

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSOT="${SCRIPT_DIR}/pytest_c_class_deselects.txt"

if [[ ! -f "$SSOT" ]]; then
  echo "ERROR: deselect SSOT missing: $SSOT" >&2
  exit 1
fi

while IFS= read -r line || [[ -n "$line" ]]; do
  # strip CR (Windows) and trailing spaces
  line="${line//$'\r'/}"
  # skip blank + comments
  [[ -z "${line//[[:space:]]/}" ]] && continue
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  # emit as two argv tokens on one line for mapfile consumers
  printf -- '--deselect\n%s\n' "$line"
done < "$SSOT"
