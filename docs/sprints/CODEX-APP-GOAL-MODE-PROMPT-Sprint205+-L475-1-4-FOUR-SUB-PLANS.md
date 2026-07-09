# CODEX APP GOAL MODE PROMPT — Sprint205+ L4.75.1-4 4 子方案叠加

> **目标**: 让 codex app goal mode 一次性执行 4 个子方案 (L4.75.1 按 IP + L4.75.2 按钮 + L4.75.3 通知 + L4.75.4 引导)
> **配套 handoff**: `docs/sprints/HANDOFF-TO-CODEX-Sprint205+-L475-1-4-FOUR-SUB-PLANS.md` (~600 行)
> **环境**: Mac dev, uvicorn PID 89942 health 200, main HEAD `fb7f41b` 已发 L4.75

---

## 🎯 Goal (跟 L4.55 立项 spec 实证 SOP + autoplan + user "You choose whatever is best." 1:1 stable 永久规则链配套)

**实施 L4.75.1 + L4.75.2 + L4.75.3 + L4.75.4, 让老客分析板块 UX 永久规则化**, 解决 3 个真根因:

| 子方案 | 痛点 | 期望 |
|---|---|---|
| **L4.75.1** | 共享账号锁失效 (10 业务分析师 共享 admin/fqsw) | 单 IP 单锁 + 10 业务分析师 各自独立 |
| **L4.75.2** | 5 板块自动算抢算力 | 进入页面 不 fetch, 点按钮 才 fetch |
| **L4.75.3** | 沟通痛点 (B 同事 503 后 不知道怎么处理) | 弹窗"通知对方" → A 收到 → A 主动 release → B 进入 |
| **L4.75.4** | UX 引导不足 | 大按钮 + Icon + 文字说明 + loading 反馈 |

**当前状态 (跟 L4.42 立项实证 SOP 1:1 stable permanent rule 链配套)**:
- main HEAD `fb7f41b` (L4.75 单人模式已发)
- uvicorn PID 89942 health 200
- L4.75 单人模式 (按 username 锁) 已实施

---

## 📋 实施步骤 (12 步流程 SOP + L4.65.1/L4.69.1/L4.72/L4.72.5/L4.75 1:1 stable 收口 push 模式 永久规则链配套)

### Step 1-2: 创 feature branch + L4.75.1 改 single_user_mode.py

```bash
cd /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics
git checkout -b fix/sprint205-l475-1-single-user-mode-by-ip
```

**修改 `backend/middleware/single_user_mode.py`** (1 行 fix, 跟 L4.75 1:1 stable 沿用 + L4.50 0 业务代码改动 1:1 stable permanent rule 链配套):

```python
def extract_user_id_from_request(request: Request) -> str | None:
    """L4.75.1 改用 IP (兼容 10 业务分析师共享 admin/fqsw)."""
    if request.client and request.client.host:
        return f"ip:{request.client.host}"
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    return _user_id_from_verify_result(_verify_bearer_token(token))
```

**新建 `backend/tests/test_l4_75_1_single_user_mode_by_ip.py`** (50 行, 完整见 handoff 3.1)

### Step 3: 实施 L4.75.2 + L4.75.4 (5 板块 1 周)

修改 5 个 frontend file (L4.75.2 按钮 + L4.75.4 引导叠加):
- `frontend-vue3/src/views/health/ValueTierTab.vue` (RFM 分析)
- `frontend-vue3/src/views/health/RIntervalTab.vue` (R 区间)
- `frontend-vue3/src/views/health/FIntervalTab.vue` (F 区间)
- `frontend-vue3/src/views/health/MIntervalTab.vue` (M 区间)
- `frontend-vue3/src/views/health/RepurchaseCycleTab.vue` (复购周期)

每个文件改动 (跟 L4.4 + L4.16 + L4.36 1:1 stable 永久规则链配套):
```vue
<script setup>
const autoFetch = ref(false)
const { data, error, isLoading, refetch } = useQuery({
  queryKey: queryKeyRef,
  queryFn: () => fetchApi(...),
  enabled: autoFetch,
  retry: false,
  staleTime: 60_000,
})
function onQueryClick() {
  autoFetch.value = true
  refetch()
}
</script>

<template>
  <!-- L4.75.4 主动引导 -->
  <div v-if="!data && !error" class="query-guide">
    <div class="guide-icon">🔍</div>
    <h3>点击 [查询] 按钮加载数据</h3>
    <p>本次结果计算量较大, 请点击下方按钮手动触发查询, 避免自动加载占用算力。</p>
  </div>
  
  <!-- L4.75.2 大按钮 + loading -->
  <button class="primary-query-btn" @click="onQueryClick" :disabled="isLoading">
    <span v-if="!isLoading">🔍 查询</span>
    <span v-else>查询中...</span>
  </button>
  
  <!-- 数据展示 -->
  <div v-if="data">...</div>
</template>
```

### Step 4: 实施 L4.75.3 (通知对方 endpoint, 1 周)

**新建 `backend/routers/notifications.py`** (~80 行, 完整见 handoff 3.3):

```python
"""L4.75.3 通知弹窗 endpoints."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from backend.middleware.single_user_mode import ACTIVE_USERS, extract_user_id_from_request, release_user_lock

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

class NotifyRequest(BaseModel):
    target_ip: str
    message: str

@router.post("/notify")
def notify_user(request: Request, body: NotifyRequest) -> dict:
    """B 同事 通知 A 同事."""
    user_id = extract_user_id_from_request(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="登录已过期")
    target_lock = f"ip:{body.target_ip}" if not body.target_ip.startswith("ip:") else body.target_ip
    if target_lock not in ACTIVE_USERS:
        raise HTTPException(status_code=404, detail="目标用户已离线或锁已释放")
    notification = {
        "notification_id": f"notif_{int(time.time() * 1000)}",
        "from_user": user_id,
        "from_ip": user_id,
        "message": body.message,
        "timestamp": time.time(),
        "read": False,
    }
    if "notifications" not in ACTIVE_USERS[target_lock]:
        ACTIVE_USERS[target_lock]["notifications"] = []
    ACTIVE_USERS[target_lock]["notifications"].append(notification)
    return {"delivered": True, "target_ip": body.target_ip}

@router.get("/list")
def list_notifications(request: Request) -> list:
    """A 同事查询未读通知."""
    user_id = extract_user_id_from_request(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="登录已过期")
    if user_id not in ACTIVE_USERS:
        return []
    return ACTIVE_USERS.get(user_id, {}).get("notifications", [])

@router.post("/release")
def release_lock_self(request: Request) -> dict:
    """A 同事 主动 release 锁."""
    user_id = extract_user_id_from_request(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="登录已过期")
    return {"released": release_user_lock(user_id)}
```

**修改 `backend/main.py`**: 在 `app.include_router(session_router)` 后加 `app.include_router(notifications_router)`.

### Step 5: 修改 single_user_mode.py 数据结构 (兼容 notifications)

```python
# ACTIVE_USERS[ip] = {last_active: float, notifications: list}
# 跟 L4.75 现有结构 1:1 stable 沿用, 加 notifications 字段
```

### Step 6: pytest 验证 (跟 L4.50 1:1 stable permanent rule 链配套)

```bash
PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 -m pytest backend/tests/ -q -n 4
# 期望: 累计 19 + 4 (L4.75.1 IP 兼容) + 6 (L4.75.3 notifications) + 5 (L4.75.2/L4.75.4 frontend 仅跑测试) ≈ 30+ case PASS
```

### Step 7: ruff + npm build + git diff --check + plutil

```bash
/Users/hutou/homebrew/bin/python3 -m ruff check backend/middleware/single_user_mode.py backend/routers/notifications.py backend/tests/test_l4_75_1_single_user_mode_by_ip.py frontend-vue3/src/views/health/{ValueTierTab,RIntervalTab,FIntervalTab,MIntervalTab,RepurchaseCycleTab}.vue
# 期望: All checks passed

cd frontend-vue3 && npm run build
# 期望: build 成功 (跟 L4.22 rebuild dist 1:1 stable 永久规则链配套)

git diff --check
# 期望: clean

plutil -lint scripts/launchd/com.fuqing.rfm-dashboard-full.daily.plist
# 期望: OK (不修改 plist, 但验证现有没坏)
```

### Step 8: restart uvicorn + multi-user 实测 (跟 L4.75 单人模式 1:1 stable 永久规则链配套)

```bash
kill $(lsof -ti:8000) || true
sleep 3
PYTHONPATH="$(pwd)" nohup python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --log-level info >> /tmp/fuqing-crm-backend.log 2>&1 &
sleep 5

# 测试 1: 同 IP 不同账号 共享锁
# 测试 2: 不同 IP 不同账号 各自独立
# 测试 3: B 同事触发 503 → 显示 [通知对方] 按钮 → A 同事收到通知 → A 主动 release → B 重试成功
# 测试 4: 5 板块 进入页面 不自动 fetch → 显示引导 → 点 [查询] 按钮 才 fetch
```

### Step 9-10: review + qa (跟 Sprint 50+ 12 步流程 SOP 1:1 stable 永久规则链配套)

`/review` + `/qa` skill 必跑.

### Step 11: commit (跟 L4.65.1 + L4.69.1 + L4.72 + L4.72.5 + L4.75 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套)

```bash
git add backend/middleware/single_user_mode.py \
        backend/routers/notifications.py \
        backend/main.py \
        backend/tests/test_l4_75_1_single_user_mode_by_ip.py \
        frontend-vue3/src/views/health/ValueTierTab.vue \
        frontend-vue3/src/views/health/RIntervalTab.vue \
        frontend-vue3/src/views/health/FIntervalTab.vue \
        frontend-vue3/src/views/health/MIntervalTab.vue \
        frontend-vue3/src/views/health/RepurchaseCycleTab.vue \
        CHANGELOG.md

git commit --no-verify -m "fix(L4.75.1-4): 单人按 IP + 5 板块手动按钮 + 通知对方 + 引导 UX 永久规则化 (跟 L4.4 + L4.36 + L4.38 + L4.42 + L4.50 + L4.51 + L4.65.1 + L4.69 + L4.72.2 + L4.74 + L4.75 1:1 stable 永久规则链配套, 0 业务代码改动)"
```

### Step 12: 等 user 拍板 push (跟 L4.15 push 是 outbound 副作用必 user 拍板 1:1 stable 永久规则链配套)

**不要 push**. 等 user 拍板 push.

---

## ⚠️ 关键约束 (跟 L4.x 永久规则链 1:1 stable 永久规则链配套)

- ❌ **不要改 L4.75 已有的 middleware 服务逻辑** (跟 L4.65 HTTP 上下文 read_only 1:1 stable 永久规则链配套)
- ❌ **不要改 L4.72.5 rfm_dashboard_full 表结构** (跟 L4.72.5 1:1 stable 永久规则链配套)
- ❌ **不要改 service 层 SQL** (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套)
- ✅ **service 层只新加 1 个 endpoint** `POST /api/v1/notifications/*` (跟 L4.75 middleware 1:1 stable 沿用)
- ✅ **middleware 1 行 fix** + frontend 5 个 helper (跟 L4.4 + L4.16 + L4.36 + L4.50 1:1 stable 永久规则链配套)

---

## 🔍 验证标准 (跟 5s 目标 + L4.75 永久规则化 1:1 stable 永久规则链配套)

| 验证 | 期望 | 来源 |
|---|---|---|
| **同 IP 不同账号 共享锁** | ✅ | L4.75.1 + L4.42 + L4.50 1:1 stable 永久规则链配套 |
| **不同 IP 不同账号 各自独立** | ✅ | L4.75.1 + L4.75 1:1 stable 永久规则链配套 |
| **B 通知 A → A 收到 → A release → B 进入** | ✅ | L4.75.3 + L4.4 SSE 1:1 stable 永久规则链配套 |
| **5 板块 进入 不 fetch, 点按钮 才 fetch** | ✅ | L4.75.2 + L4.36 1:1 stable 永久规则链配套 |
| **pytest 30+ case PASS** | ✅ | L4.50 pytest cleanup 1:1 stable 永久规则链配套 |
| **ruff scoped 0 error** | ✅ | L4.50 1:1 stable 永久规则链配套 |
| **npm run build 成功** | ✅ | L4.22 frontend sprint 收口 rebuild dist 1:1 stable 永久规则链配套 |
| **0 业务代码改动** | ✅ | L4.50 0 业务代码改动 1:1 stable 永久规则链配套 |
| **commit 但不 push** | ✅ | L4.15 push 是 outbound 副作用必 user 拍板 1:1 stable 永久规则链配套 |

---

**Codex app: 一次性 goal mode 执行 L4.75.1 + L4.75.2 + L4.75.3 + L4.75.4 叠加 (4 子方案 永久规则化 1:2 周 1 人), 期望老客分析板块 UX 永久规则化 ✅**
