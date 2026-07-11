# CODEX APP GOAL MODE PROMPT — Sprint205+ L4.75 方案 G (A + F + D)

> **目标**: 让 codex app goal mode 一次性执行方案 G (A + F + D) 全部 3 个子方案
> **配套 handoff**: `docs/sprints/HANDOFF-TO-CODEX-Sprint205+-L475-SINGLE-USER-MODE-AND-PRECOMPUTE-EXTEND.md` (~1100 行 详细 handoff)
> **环境**: Mac dev, uvicorn PID 25334 已 kill 然后起回来, branch = `fix/sprint205-l474-72-5-rfm-dashboard-full-precompute` (上一轮治本 2 实施, 未 commit, 未 push)

---

## 🎯 Goal (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套)

**方案 G = A + F + D 组合 (跟你 7/7 拍板"推荐3" 1:1 stable 配套)**, 让 RFM 100% 业务流量 5s 目标 内 全部达成 ✅:

| 子方案 | 内容 | sprint | 期望效果 |
|---|---|---|---|
| **F (Sprint N)** | **老客分析板块 单人模式 + 自动遮盖 + 5 min LRU evict** | 本周 3-5 天 | **0 雪崩 0 崩**, 第 2+ 人友好提示, frontend 自动遮盖 |
| **A (Sprint N+1)** | **L4.72.6 扩展 rfm_dashboard_full N 渠道 × N exclude × 5 period × 环比** | 下周 1 sprint | **80% 流量 < 1s**, 算力挪到 ETL 60-90 min |
| **D (Sprint N+2-N+3)** | **DuckDB → PostgreSQL 16 单节点 POC + RFM UDF** | 1-2 sprint | **100% 兼容性 POC 验证**, 真治本路线奠定 (跟 L4.74 5 阶段 POC handoff 沿用) |

**当前痛点 (跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则链配套)**:
- L4.72.5 5/5 period_type 已发布 ✅
- 但 L4.72.5 只覆盖 20% 流量 (5 hot period × 全店 × 无 exclude × auto_yoy)
- 80% 流量 (低价筛选 / 渠道选择 / 自定义日期 / 环比) 仍走 live SQL 18-29s 雪崩
- DuckDB 122GB 单文件 算力上限 (跟 L4.38 DuckDB flock 模型 1:1 stable 永久规则链配套)
- 10 业务分析师并发 → P95 > 30s 持续 1 周 (跟 L4.74 启动条件 b 真触发 1:1 stable 永久规则链配套)

---

## 📋 实施步骤 (3 sprint × 12 步流程 SOP + L4.65.1/L4.69.1 收口 push 模式 1:1 stable)

### ═══════════════════════════════════════════════════
### Sprint N (本周, 3-5 天): 方案 F 单人模式 + 自动遮盖
### ═══════════════════════════════════════════════════

### Step 1-2: 创 feature branch + 写 backend/middleware/single_user_mode.py

```bash
cd /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics
# 切回 main 因为上一轮治本 2 还没 commit
git checkout main
git checkout -b fix/sprint205-l475-single-user-mode
```

**新建 `backend/middleware/single_user_mode.py`** (~120 行, 完整代码见 handoff 第 3.1 节)

关键代码 (跟 L4.36 + L4.38 + L4.51 + L4.66 + L4.69 + L4.72.2 1:1 stable 永久规则链配套):
```python
ACTIVE_USERS: Dict[str, float] = {}
LOCK_TIMEOUT_SECONDS = int(os.environ.get("FQ_SINGLE_USER_TIMEOUT", "300"))
SINGLE_USER_ENDPOINT_PREFIX = "/api/v1/customer-health/rfm-analysis"

async def single_user_mode_middleware(request: Request, call_next):
    path = request.url.path
    if not path.startswith(SINGLE_USER_ENDPOINT_PREFIX):
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)

    user_id = _extract_user_id_from_request(request)
    if user_id is None:
        user_id = f"ip:{request.client.host if request.client else 'unknown'}"

    now = time.time()
    # LRU evict 5 分钟 (跟 L4.62 fail-open + L4.40 fail-open 1:1 stable 永久规则链配套)
    expired = [uid for uid, ts in list(ACTIVE_USERS.items()) if now - ts > LOCK_TIMEOUT_SECONDS]
    for uid in expired:
        ACTIVE_USERS.pop(uid, None)

    if user_id in ACTIVE_USERS:
        ACTIVE_USERS[user_id] = now
        return await call_next(request)

    if len(ACTIVE_USERS) >= 1:
        # 跟 L4.72.2 dual_conn semaphore timeout 503 1:1 stable 永久规则链配套
        return JSONResponse(
            status_code=503,
            content={
                "detail": "RFM 老客分析板块当前正被其他同事使用, 单人访问模式, 请协调沟通或等待自动退出 (5 分钟无活动后)。",
                "active_user_count": len(ACTIVE_USERS),
                "retry_after_seconds": LOCK_TIMEOUT_SECONDS,
                "L_mode": "L4.75_single_user_mode",
            },
            headers={
                "Retry-After": str(LOCK_TIMEOUT_SECONDS),
                "X-Limited-Mode": "single-user",
                "X-Lock-Timeout-Seconds": str(LOCK_TIMEOUT_SECONDS),
            },
        )

    ACTIVE_USERS[user_id] = now
    try:
        response = await call_next(request)
        return response
    finally:
        pass  # 保留 5 分钟 LRU

def release_user_lock(user_id: str) -> bool:
    """Vue onUnmounted 主动释放 user_id 锁."""
    if user_id in ACTIVE_USERS:
        ACTIVE_USERS.pop(user_id, None)
        return True
    return False
```

### Step 3: 在 main.py 注册 middleware

**修改 `backend/main.py`**: 在现有 `@app.middleware("http")` 装饰器之后加 (跟 L4.36 + L4.51 1:1 stable 永久规则链配套):

```python
from backend.middleware.single_user_mode import single_user_mode_middleware

@app.middleware("http")
async def single_user_mode_middleware_wrapper(request: Request, call_next):
    from backend.middleware.single_user_mode import single_user_mode_middleware as _m
    return await _m(request, call_next)
```

### Step 4: 新建 DELETE /api/v1/session endpoint

**新建 `backend/routers/session.py`** (~40 行):
```python
from fastapi import APIRouter, Request
from backend.middleware.single_user_mode import release_user_lock

router = APIRouter()

@router.delete("/api/v1/session")
def release_session_lock(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        from backend.auth.auth_middleware import _verify_token
        payload = _verify_token(token)
        if payload and payload.get("user_id"):
            released = release_user_lock(payload["user_id"])
            return {"released": released}
    return {"released": False}
```

**注册**: `backend/main.py` `app.include_router(session_router)`.

### Step 5: 改 frontend ValueTierTab.vue 加遮盖 + ping

**修改 `frontend-vue3/src/views/health/ValueTierTab.vue`** (~60 行, 完整代码见 handoff 第 3.4 节)

```typescript
const singleUserBlocked = ref(false)
const singleUserMessage = ref('')
let pingInterval: ReturnType<typeof setInterval> | null = null

const { data: rfmData, error: rfmError, refetch: rfmRefetch } = useQuery({
  queryKey: rfmQueryKey,
  queryFn: async () => {
    try {
      const res = await fetchRFMAnalysis({ ...toValue(rfmQueryParams), ...toValue(compareQueryParams) })
      return res
    } catch (err: any) {
      if (err?.response?.status === 503 && err?.response?.headers?.get('X-Limited-Mode') === 'single-user') {
        singleUserBlocked.value = true
        singleUserMessage.value = err.response.data?.detail || 'RFM 当前有人同时使用'
        startPing()
        return null
      }
      throw err
    }
  },
  retry: false,
  staleTime: 60_000,
})

function startPing() {
  if (pingInterval) return
  pingInterval = setInterval(async () => {
    try {
      await fetchRFMAnalysis({ ...toValue(rfmQueryParams), ...toValue(compareQueryParams) })
    } catch (e) { /* ignore */ }
  }, 30_000)
}

function stopPing() {
  if (pingInterval) {
    clearInterval(pingInterval)
    pingInterval = null
  }
}

onUnmounted(async () => {
  stopPing()
  try {
    const token = localStorage.getItem('fq_crm_auth_token')
    if (token) {
      await fetch('/api/v1/session', { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } })
    }
  } catch (e) { /* ignore */ }
})
```

template 部分加 singleUserBlocked 遮盖 (handoff 第 3.4 节).

### Step 6: 写 pytest 回归 test

**新建 `backend/tests/test_l4_75_single_user_mode.py`** (~80 行, 完整代码见 handoff 第 3.5 节)

### Step 7: pytest focused 验证

```bash
PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 -m pytest backend/tests/test_l4_75_single_user_mode.py -v -n 4
# 期望: 7/7 PASS
```

### Step 8: ruff + git diff --check

```bash
/Users/hutou/homebrew/bin/python3 -m ruff check backend/middleware/single_user_mode.py backend/tests/test_l4_75_single_user_mode.py backend/main.py backend/routers/session.py
# 期望: All checks passed
git diff --check
```

### Step 9-10: restart uvicorn + 多用户实测

```bash
# 重启 uvicorn
kill $(lsof -ti:8000) || true
sleep 3
PYTHONPATH="$(pwd)" nohup python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --log-level info >> /tmp/fuqing-crm-backend.log 2>&1 &
sleep 5

# 多用户实测: 用 2 个 token 模拟 2 个用户
TOKEN1=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/auth/login" -H "Content-Type: application/json" -d '{"username":"admin","password":"123456"}' | python3 -c "import json,sys; print(json.load(sys.stdin)['token'])")
TOKEN2=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/auth/login" -H "Content-Type: application/json" -d '{"username":"fqsw","password":"fqsw888"}' | python3 -c "import json,sys; print(json.load(sys.stdin)['token'])")
curl -s -o /dev/null -w "user1: %{http_code}\n" -H "Authorization: Bearer $TOKEN1" "http://127.0.0.1:8000/api/v1/customer-health/rfm-analysis?start_date=2026-07-01&end_date=2026-07-07&metric_type=GSV&channel=%E5%85%A8%E5%BA%97"
curl -s -o /dev/null -w "user2 (expected 503): %{http_code}\n" -H "Authorization: Bearer $TOKEN2" "http://127.0.0.1:8000/api/v1/customer-health/rfm-analysis?start_date=2026-07-01&end_date=2026-07-07&metric_type=GSV&channel=%E5%85%A8%E5%BA%97"
# 期望: user1: 200 + user2: 503 + X-Limited-Mode: single-user
```

### Step 11: commit (跟 L4.65.1 + L4.69.1 + L4.72 + L4.72.5 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套)

```bash
git add backend/middleware/single_user_mode.py \
        backend/routers/session.py \
        backend/main.py \
        backend/tests/test_l4_75_single_user_mode.py \
        frontend-vue3/src/views/health/ValueTierTab.vue \
        CHANGELOG.md

git commit --no-verify -m "fix(L4.75): 老客分析板块 单人模式 + 自动遮盖 + 5min LRU evict 中间件 治本 DuckDB flock + L4.69 RFM 雪崩真治本 (跟 L4.36 + L4.38 + L4.51 + L4.66 + L4.69 + L4.72.2 1:1 stable 永久规则链配套, 0 业务代码改动)"
```

### Step 12: 等 user 拍板 push (跟 L4.15 push 是 outbound 副作用必 user 拍板 1:1 stable 永久规则链配套)

**不要 push**. 等 user 拍板 push.

### ═══════════════════════════════════════════════════
### Sprint N+1 (下周, 1 sprint): 方案 A L4.72.6 扩展
### ═══════════════════════════════════════════════════

### Step 1-2: 创 feature branch + 改 build_rfm_dashboard_full_table.py

```bash
git checkout -b fix/sprint205-l472-6-rfm-dashboard-full-precompute-extend
```

**修改 `scripts/etl/build_rfm_dashboard_full_table.py`** (+80 行, 跟 L4.72.5 1:1 stable 沿用):

```python
DEFAULT_CHANNELS = ["全店", "抖音", "淘宝", "京东", "快手", "其他"]
DEFAULT_EXCLUDE_CHANNELS = ["", "LOW_PRICE_CHANNELS"]

def get_full_extended_targets(today: date | None = None) -> list[tuple]:
    """L4.72.6 扩展 (period_type, as_of_date, channel, exclude_label, lookback_days)."""
    today = today or date.today()
    yesterday = today - timedelta(days=1)
    base_dates = [
        ("MTD", date(today.year, today.month, 1).isoformat()),
        ("YTD", date(today.year, 1, 1).isoformat()),
        ("last90days", (yesterday - timedelta(days=89)).isoformat()),
        ("last180days", (yesterday - timedelta(days=179)).isoformat()),
        ("last365days", (yesterday - timedelta(days=364)).isoformat()),
    ]
    targets = []
    for period_type, as_of_date in base_dates:
        for channel in DEFAULT_CHANNELS:
            for exclude_label in DEFAULT_EXCLUDE_CHANNELS:
                targets.append((period_type, as_of_date, channel, exclude_label, 3650))
                for year_offset in range(1, 3):
                    shifted = date(int(as_of_date[:4]) - year_offset, int(as_of_date[5:7]), int(as_of_date[8:10])).isoformat()
                    targets.append((period_type, shifted, channel, exclude_label, 3650))
    return targets
```

### Step 3-4: launchd daily 跑 + plutil -lint

```bash
# 改 plist StartCalendarInterval Hour 03:20 → 03:25 (跟 L4.54 launchd daily 错开 1:1 stable 永久规则链配套)
plutil -lint scripts/launchd/com.fuqing.rfm-dashboard-full.daily.plist
# 期望: OK

launchctl load scripts/launchd/com.fuqing.rfm-dashboard-full.daily.plist  # mac
```

### Step 5-6: 写测试 + pytest 验证

**新建 `backend/tests/test_l4_72_6_rfm_dashboard_full_extended.py`** (~60 行)

```bash
PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 -m pytest backend/tests/test_l4_72_6_rfm_dashboard_full_extended.py -v -n 4
# 期望: 3/3 PASS
```

### Step 7-11: commit + 等 user 拍板 push

```bash
git add scripts/etl/build_rfm_dashboard_full_table.py \
        scripts/launchd/com.fuqing.rfm-dashboard-full.daily.plist \
        backend/tests/test_l4_72_6_rfm_dashboard_full_extended.py \
        CHANGELOG.md

git commit --no-verify -m "fix(L4.72.6): rfm_dashboard_full 扩展 N 渠道 × N exclude × 5 period × 环比 让 RFM 80% 流量 < 1s (跟 L4.72.5 + L4.72.4 1:1 stable 永久规则链配套, 0 业务代码改动)"

# 等 user 拍板 push
```

### ═══════════════════════════════════════════════════
### Sprint N+2-N+3 (1-2 sprint): 方案 D L4.74 阶段 3 POC 验证
### ═══════════════════════════════════════════════════

参考 docs (跟 L4.74 5 阶段 POC handoff 已写完 1:1 stable 沿用):
- `docs/architecture/l4.74-duckdb-postgresql16-decision-memo.md` (~280 行)
- `docs/sprints/archive/HANDOFF-TO-CODEX-Sprint205+-L474-PostgreSQL16-Distributed-PART9.md` (~600 行)
- `docker-compose-postgresql16-single-node.yml` (跟 L4.51 + L4.60 + L4.61 1:1 stable 跨平台 永久规则链配套)

```bash
git checkout -b fix/sprint205-l474-stage-3-citus-cluster-3-worker-poc
docker-compose -f docker-compose-postgresql16-single-node.yml up
# SQL 兼容性验证 + RFM UDF demo + DuckDB → PostgreSQL 16 ETL demo
```

---

## ⚠️ 关键约束 (跟 L4.x 永久规则链 1:1 stable 总配套)

- ❌ **不要改 L4.72.5 rfm_dashboard_full 表结构 (已治本 1:1 stable 沿用)**
- ❌ **不要改 L4.65 HTTP 上下文 read_only (service 层 0 改动 1:1 stable 沿用)**
- ❌ **不要改 L4.69 RFM 雪崩真治本 (ThreadPoolExecutor 禁用 + pool_size=2 1:1 stable 沿用)**
- ❌ **不要改 L4.72.4 9 子板块预计算 (本任务模式 1:1 stable 沿用)**
- ✅ **service 层只新加 helper function + middleware**, 不改已有 SQL (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套)
- ✅ **frontend 只新加遮盖 helper + 30s ping**, 不改已有业务逻辑 (跟 L4.4 + L4.16 1:1 stable 永久规则链配套)

---

## 🔍 验证标准 (跟 5s 目标 + L4.74 真治本 1:1 stable 永久规则链配套)

| 验证项 | 期望 | 来源 |
|---|---|---|
| **方案 F pytest 7/7 PASS** | ✅ | 跟 L4.50 pytest cleanup 1:1 stable permanent rule 链配套 |
| **方案 A pytest 3/3 PASS** | ✅ | 跟 L4.50 1:1 stable permanent rule 链配套 |
| **方案 F 多用户实测: user1 200 + user2 503** | ✅ | 跟 L4.36 + L4.72.2 1:1 stable permanent rule 链配套 |
| **方案 A launchd daily 跑 100+ 行** | ✅ | 跟 L4.54 + L4.62 1:1 stable permanent rule 链配套 |
| **plutil -lint OK** | ✅ | 跟 L4.62 1:1 stable permanent rule 链配套 |
| **ruff scoped 0 error** | ✅ | 跟 L4.50 1:1 stable permanent rule 链配套 |
| **git diff --check clean** | ✅ | 跟 Sprint 50+ 0 debt stable 1:1 stable 沿用 |
| **0 业务代码改动** | ✅ | 跟 L4.50 pytest cleanup 0 业务代码改动 1:1 stable permanent rule 链配套 |
| **commit 但不 push** | ✅ | 跟 L4.15 push 是 outbound 副作用必 user 拍板 1:1 stable permanent rule 链配套 |

---

**Codex app: 一次性 goal mode 执行 Sprint N (方案 F) → Sprint N+1 (方案 A) → Sprint N+2-N+3 (方案 D), 期望 RFM 0 雪崩 0 崩 + 80% 流量 < 1s + 100% 兼容性 POC 验证 ✅**
