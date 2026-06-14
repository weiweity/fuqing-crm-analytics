---
name: regen-types
description: 改 backend/contracts/*.py 后, 重新生成 frontend types.ts. 触发条件: 改了 Pydantic schema. 4 步: 1) 启 uvicorn 临时 2) 拿 /openapi.json 3) openapi-typescript 生 types 4) vue-tsc 验 0 错.
disable-model-invocation: false
---

# regen-types — 契约改动后重生成前端 TypeScript 类型

适用场景: 改了 `backend/contracts/*.py` (Pydantic schema 增/删/改字段)。

## 4 步流程

### Step 1: 启动临时 uvicorn 拿 OpenAPI schema

```bash
# 起 uvicorn 占临时端口 8001 (避免跟生产 8000 冲突, 8001 测试完即 kill)
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
export FQ_CRM_PASSWORDS=admin:testpass123
nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 \
  > /tmp/uvicorn-regen.log 2>&1 &
UVICORN_PID=$!
sleep 3

# 验 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/openapi.json
```

### Step 2: openapi-typescript 生成 types

```bash
cd frontend-vue3
curl -s http://localhost:8001/openapi.json > /tmp/openapi.json
npx openapi-typescript /tmp/openapi.json -o src/api/types.generated.ts

# types.ts 是 types.generated.ts 的 copy (历史遗留, 保留)
cp src/api/types.generated.ts src/api/types.ts

# 杀 uvicorn
kill $UVICORN_PID 2>/dev/null
```

### Step 3: 验证 0 错

```bash
cd frontend-vue3
npx vue-tsc -b 2>&1 | tail -20
# 期望: 0 error. 如果有错 → contract 字段名跟前端 type 不一致, 修前端代码
```

### Step 4: commit + push

按 CLAUDE.md 12 步流程走 (review → qa → merge → push → pull → restart)。

## 失败排查

| 错 | 原因 | 修法 |
|---|---|---|
| `openapi-typescript` 命令 not found | 依赖没装 | `cd frontend-vue3 && npm install` |
| vue-tsc 报 `Type 'X' is not assignable to 'Y'` | 前端代码用了错的字段名 | sed 批量替换 `s/oldName/newName/g` |
| types.ts 缺新字段 | regen 没成功 | 检查 `npx openapi-typescript` 输出有无报错 |
| 跑完 uvicorn 杀不掉 | `kill -9` 强制 | `kill -9 $UVICORN_PID` |

## 跟 Sprint 22.5+ P0-2 hook 联动

`.claude/settings.json` 已有 PostToolUse hook, 改 `backend/contracts/*.py` 时会自动打印提醒 "跑 /regen-types"。本 skill 提供完整流程。
