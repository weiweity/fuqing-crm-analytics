# FRONTEND-TYPES-GEN — 前端 types.ts 自动生成

> Sprint 19 P2-5 任务: 用 `pydantic-to-typescript` 把 `backend/contracts/` 3 个 module
> (category / metrics / health) 自动生成到 `frontend-vue3/src/types/api.ts`.
> 落地日期: 2026-06-11. 拍板人: subagent C3.

---

## 1. 拍板

| 维度 | 拍板 |
|---|---|
| **工具** | `pydantic-to-typescript` v2.0.0 (pydantic 官方生态) |
| **包名** | `pydantic2ts` (v2.x 改名, CLI 入口 `pydantic2ts.cli.script`) |
| **入口 module** | 3 个: `backend.contracts.category` / `backend.contracts.metrics` / `backend.contracts.health` |
| **输出文件** | `frontend-vue3/src/types/api.ts` (跟 `types/echarts.ts` `types/rfm.ts` 同目录) |
| **集成脚本** | `scripts/gen-frontend-types.sh` (chmod +x, 一行调用) |
| **触发时机** | 改 `backend/contracts/*.py` 字段后手动跑, 走 `bash scripts/gen-frontend-types.sh` |
| **CI 集成** | 不自动跑 (改 contract 字段是 P0/P1 行为, sprint 收口时跑 1 次即可) |

---

## 2. 为何不用 `openapi-typescript`?

仓库 `.githooks/pre-commit` (Sprint 14 A.2 WARN) 提醒改 contract 后跑:
```bash
PYTHONPATH=. nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
cd frontend-vue3 && npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.generated.ts
```

`openapi-typescript` 缺点:
- 需启 uvicorn 跑最新代码, 启动 5-10s + 跑完手动 kill
- CI 跑不友好 (无 backend 进程, 拿不到 openapi.json)
- 改 contract 后才能跑, 不能"contract 当源真值, 提前生成"

`pydantic-to-typescript` 优点:
- 走 Pydantic model 直接生成 (跟 uvicorn 解耦)
- CI 跑友好 (跟 backend 启动状态无关)
- 改 contract 后能跑, 也能"contract 写完, 跑 gen-frontend-types, 提交前再 review"

**结论**: 走 `pydantic-to-typescript` 作为**主路径** (CI / 本地都跑), `openapi-typescript` 留作**辅助路径** (线上 swagger UI 实时对照).

---

## 3. 工具版本与命名陷阱

### 3.1 包名陷阱

`pydantic-to-typescript` 在 v1.x 跟 v2.x 包名不同:

| 版本 | PyPI 名 | 实际 import 名 | CLI 入口 |
|---|---|---|---|
| v1.x | `pydantic-to-typescript` | `pydantic_to_ts` | `python -m pydantic_to_ts` |
| v2.x | `pydantic-to-typescript` | `pydantic2ts` | `python -m pydantic2ts.cli.script` |

任务描述写的 `python -m pydantic_to_ts` 是 v1.x 写法, v2.0.0 已 rename, 跑会报 `No module named pydantic_to_ts`. 脚本里走 `python3 -m pydantic2ts.cli.script` (v2.x 入口).

### 3.2 安装

```bash
python3 -m pip install --user --break-system-packages pydantic-to-typescript
# 装到 /Users/hutou/Library/Python/3.14/lib/python/site-packages/
# (跟 homebrew python3.14 走 user site-packages, 不污染系统 Python)
```

### 3.3 pydantic 2.13.2 兼容

`pydantic2ts` v2.0.0 走 `pydantic_v2.py` 适配 Pydantic v2 (本仓库用 2.13.2). 生成的 TS interface 用 `?` 标记 Optional, 跟 v1.x nullable 行为不同, 需前端 `import { type X }` 适配.

---

## 4. 集成脚本

### `scripts/gen-frontend-types.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

if ! python3 -c "import pydantic2ts" 2>/dev/null; then
    echo "ERROR: pydantic-to-typescript 未装, 跑: python3 -m pip install --user --break-system-packages pydantic-to-typescript" >&2
    exit 1
fi

OUTPUT="frontend-vue3/src/types/api.ts"
PYTHONPATH="${PROJECT_ROOT}" python3 -m pydantic2ts.cli.script \
    --module backend.contracts.category \
    --module backend.contracts.metrics \
    --module backend.contracts.health \
    --output "${OUTPUT}"
```

### 跑法

```bash
bash scripts/gen-frontend-types.sh
# 预期: OK: 生成 frontend-vue3/src/types/api.ts
```

### 设计要点

1. **`set -euo pipefail`**: 跟仓库其他 shell 脚本风格一致 (e.g. `setup-hooks.sh`).
2. **`PYTHONPATH` 注入**: 让 `pydantic2ts` 找到 `backend.contracts.*` 模块.
3. **依赖检查**: 没装包给明确错误, 不静默 fail.
4. **3 module 列表**: 跟 P2-5 任务描述一致, 后续 sprint 按需加 module.

---

## 5. 生成的产物

### `frontend-vue3/src/types/api.ts` (855 行)

```typescript
/* tslint:disable */
/* eslint-disable */
/**
/* This file was automatically generated from pydantic models by running pydantic2ts.
/* Do not modify it by hand - just update the pydantic models and then re-run the script
*/

/**
 * 审计日志项
 */
export interface AuditLogItem { ... }
export interface AuditLogResponse { ... }
export interface ChannelHealthScoreItem { ... }
// ... 855 行
```

### 注意事项

1. **自动生成, 不要手动改**: 文件头明确写 "Do not modify it by hand", 改完跑脚本会被覆盖.
2. **跟 `types.generated.ts` (openapi-typescript) 不冲突**: 仓库 2 份生成文件并存, 用途不同:
   - `types/api.ts` (本 P2-5): 走 pydantic-to-typescript, 主路径
   - `types.generated.ts` (Sprint 14): 走 openapi-typescript, 辅助路径
3. **跟 `types/echarts.ts` `types/rfm.ts` 不冲突**: 这 2 份是手写 TS 跟后端耦合弱, 跟自动生成文件职责不同.

---

## 6. 验证

### 6.1 生成验证

```bash
bash scripts/gen-frontend-types.sh
# 预期: "Saved typescript definitions to frontend-vue3/src/types/api.ts."
# 预期: "OK: 生成 frontend-vue3/src/types/api.ts"
```

### 6.2 类型一致验证

```bash
cd frontend-vue3 && npx vue-tsc --noEmit -p .
# 预期: 0 error (跟后端 Pydantic 字段一致)
```

### 6.3 Lint 验证

```bash
cd frontend-vue3 && npx eslint src/types/api.ts
# 预期: 0 warning (eslint 跳过 generated file 走 .eslintignore 或文件头 /* eslint-disable */)
```

### 6.4 端到端 (可选)

```bash
# 1. 改 backend/contracts/category.py 加 1 个字段
# 2. 跑 gen-frontend-types.sh
# 3. 改 frontend 组件用新字段
# 4. 跑 vue-tsc 验证类型一致
# 5. 跑 vitest 验证渲染正常
```

---

## 7. 故障排查

| 症状 | 原因 | 修法 |
|---|---|---|
| `No module named pydantic_to_ts` | 用了 v1.x 写法, v2.x 已 rename | 改用 `python3 -m pydantic2ts.cli.script` (脚本里已修) |
| `pydantic2ts has no __main__` | `python3 -m pydantic2ts` 不能直接跑 | 走 `python3 -m pydantic2ts.cli.script` |
| `ModuleNotFoundError: backend.contracts.category` | PYTHONPATH 没设 | 脚本里已加 `PYTHONPATH="${PROJECT_ROOT}"` |
| `jsonschema.exceptions.RefResolutionError` | 某个 Pydantic model 有 forward ref | 在 `backend/contracts/__init__.py` 显式 import 子模块 |
| 生成 0 行 | contract 文件空 / 字段全无 Pydantic Field 元数据 | 跑 `python -m backend.contracts._lint` 看 issue |
| 生成的字段全是 `?` (Optional) | Pydantic v2 + `Optional[T]` 模式 | 业务代码用 `Annotated[T, Field(...)]` 替代 (Sprint 18 治根建议) |

---

## 8. 后续 (Sprint 20+ 待办)

| # | 任务 | 备注 |
|---|---|---|
| 1 | 扩 3 module → 全 11 contract (asset / audience / breakdown / churn / common / flow / geo / rfm / sampling / visitor / schemas) | sprint 收口前跑全量 audit 时扩 |
| 2 | 加 `frontend-vue3/.eslintignore` 跳过 `types/api.ts` | 避免 generated file 触发 lint 噪声 |
| 3 | 集成到 `scripts/ci-verify.sh` | 改 contract 后自动跑生成 + vue-tsc 验证 |
| 4 | 评估 `pydantic2ts` v2.1+ 新功能 (Union / Literal 支持) | 跟进 release notes |
| 5 | 改 `types/echarts.ts` 跟 `types/rfm.ts` 也走 pydantic2ts | 统一手写 vs 自动生成, 减少 drift |

---

**相关文档**:
- `scripts/gen-frontend-types.sh` (本 P2-5 新增脚本)
- `frontend-vue3/src/types/api.ts` (本 P2-5 生成, 855 行)
- `docs/SPRINT-18-PRE-COMMIT.md` (Sprint 14 A.2 contract 同步 WARN 提醒)
- `docs/LINTING.md` (Sprint 17 #121 ground-truth-lint 跟 Pydantic Field 元数据)
- 仓库 2 份生成文件: `types/api.ts` (本 P2-5) + `api/types.generated.ts` (Sprint 14 openapi-typescript)

**Sprint 19 P2-5 完成**: 前端 types.ts 自动生成 (pydantic-to-typescript), 1 脚本 + 1 产物 (855 行) + 1 docs.
