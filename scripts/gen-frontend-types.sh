#!/usr/bin/env bash
# Sprint 19 P2-5: 前端 types 自动生成脚本
#
# 用途: 把 backend/contracts/ 下的 Pydantic model 自动生成成 frontend-vue3/src/types/api.ts
# 工具: pydantic-to-typescript (v2.x 改名为 pydantic2ts, 入口 pydantic2ts.cli.script)
# 触发: 改 backend/contracts/*.py 字段后手动跑, 同步前端类型
#
# 安装 (一次性):
#   python3 -m pip install --user --break-system-packages pydantic-to-typescript
#
# 用法:
#   bash scripts/gen-frontend-types.sh
#
# 拍板: 走 pydantic-to-typescript (pydantic 官方生态, 跟 v2 兼容),
#       不走 openapi-typescript (需启 uvicorn 跑最新代码, CI 跑有副作用).
#       详见 docs/FRONTEND-TYPES-GEN.md (Sprint 19 P2-5).

set -euo pipefail

# 项目根 (脚本位置相对)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

# 检查依赖
if ! python3 -c "import pydantic2ts" 2>/dev/null; then
    echo "ERROR: pydantic-to-typescript 未装, 跑: python3 -m pip install --user --break-system-packages pydantic-to-typescript" >&2
    exit 1
fi

# 生成
# 注: pydantic2ts v2.x 包名是 pydantic2ts (不是 pydantic_to_ts), CLI 入口
# pydantic2ts.cli.script (不是 -m pydantic2ts, 因为它没有 __main__.py)
OUTPUT="frontend-vue3/src/types/api.ts"
PYTHONPATH="${PROJECT_ROOT}" python3 -m pydantic2ts.cli.script \
    --module backend.contracts.category \
    --module backend.contracts.metrics \
    --module backend.contracts.health \
    --output "${OUTPUT}"

echo ""
echo "OK: 生成 ${OUTPUT}"
echo "下一步: 跑 cd frontend-vue3 && npx vue-tsc --noEmit 验证类型一致"
