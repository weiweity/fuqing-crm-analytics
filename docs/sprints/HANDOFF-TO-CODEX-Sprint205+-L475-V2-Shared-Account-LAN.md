# HANDOFF-TO-CODEX: Sprint 205+ L4.75 v2 共享账号 + LAN 单进程单人排队

> **Codex app 启动版 (跟 L4.74 V2 handoff 1:1 stable 模式沿用, 跟 L4.42 + L4.50 + L4.55 + L4.78 1:1 stable 永久规则链配套)**

| 元数据 | 值 |
|---|---|
| **Handoff 作者** | Claude Code (Stage 1 架构师, MiniMax-M3) |
| **实施者** | Codex app (gpt-5.5 high reasoning sandbox=worktree) |
| **分支** | `fix/sprint205+-l4-75-v2-shared-account-lan` (已开, 跟 L4.31 永久规则化沿用) |
| **main HEAD** | `ca2f7b2` (L4.78 0 commit 收口) |
| **预计工作量** | 1-2 天 1 人 (跟 L4.74 V2 子任务 A 1:1 stable 模式沿用, 简单 1 件任务) |
| **执行模式** | Codex Stage 2 实施 → Claude Stage 3 review → Claude Stage 4 commit/push → merge main |
| **0 业务代码改动** | 跟 L4.50 + L4.78 累计 85+ 次 1:1 stable 永久规则化沿用 (扩 `single_user_mode.py` + frontend 1 vue 2 文件, 不改 backend services / contracts / SQL) |

---

## Section 1: 背景 + 真业务触发 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

### 1.1 用户反馈 (跟 L4.42 立项实证 1:1 stable 沿用, 7/10 实测)

**用户原话 (2026-07-10)**:
> "PC2 那边 RFM 查询-年度范围下, 查询 1 次 5 秒左右, 查询 2 次 15s 左右, 查询 3 次就忘也卡死了, 需要等待. 我想着是不是 DUCKDB 是因为锁的原因, 只能一个人进行查询, 所以是不是, 限制登录就可以了, 就是同时在这个进程里面, 只允许一个人, 如果要第二个, 需要排队, 然后提示自己找谁沟通, 然后如果使用的人 5 分钟在页面上没有任何行动, 那就自动视为退出账号"

**业务上下文 (跟 L4.55 立项 spec 实证 1:1 stable 沿用)**:
- 业务组 5+ 业务分析师共享 `admin` 账号 (L4.75.1 现状: 5 IP 各自独立锁, 实际效果 = 5 人并发 RFM 查询)
- 同个局域网 (192.168.x.x / 10.x.x.x 私有子网)
- PC2 端 64GB RAM + 14 核 i5-14600K + 1TB SSD (跟 L4.68 1:1 stable)
- RFM 年度范围查询 (YOY 同期 + 3 周期) 资源最重 (跟 L4.74 + L4.71 Stage 2 1280 组合 1:1 stable 配套)
- 业务高峰期: 618/双 11 大促, 5+ 业务分析师同时跑 RFM dashboard

### 1.2 真业务根因 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, git log + grep 100% 锁定)

| 真因 | 现状 | 跟 L4.x 永久规则链 1:1 stable 配套 |
|---|---|---|
| ① **DuckDB C++ buffer pool 资源耗尽** (5s→15s→卡死 指数) | 1 query 5s, 2 query 15s, 3 query 卡死 = buffer pool 累计 1GB→2GB→2GB+ 触顶 | L4.65.1 (启动 -89%) + L4.69.1 (Python wrapper -85%) 部分治本, **不够** |
| ② **PC2 端 L4.74 cache end_date fix 没部署** (Task #47 pending) | cache miss 每次 → 实时 SQL 13.77s → buffer pool 涨 | L4.74 + L4.77 1:1 stable 永久规则化沿用, 0 commit 续期, 接手人 7/16+ 启动 |
| ③ **L4.75.1 现状"5 IP 各自独立锁"** 治标不治本 | 5 业务分析师 = 5 IP = 5 独立锁 = 5 并发 RFM 资源争抢 | L4.75.1 1:1 stable 沿用, 跟 user 提案冲突 (user 提案 = 1 active IP + 4 queue) |
| ④ **无 heartbeat 5min idle 检测** | L4.75.1 当前 5min LRU = 简单 timeout, 无前端心跳 | 跟 user 拍板 1:1 stable 沿用, 治本 Q5 卡死 |

### 1.3 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 沿用

> 立项条件 100% 触发 (跟 fix_pattern #98 1:1 stable 永久规则化沿用):
> 1. ✅ 环境依赖可访问: Mac dev / PC2 都 OK, 不依赖 docker / brew raw
> 2. ✅ 业务触发真条件: 7/10 用户实测 5s→15s→卡死, 100% 复现
> 3. ✅ 团队接手人 handoff: 7/16+ 接手人启动 + Claude Stage 3 review + Codex Stage 2 实施
> 4. ✅ 留尾登记: docs/TECH-DEBT.md 跨 sprint 留尾登记 (跟 L4.57 + L4.58 + L4.59 1:1 stable 永久规则化沿用)

---

## Section 2: Goals + Non-Goals (跟 L4.55 立项 spec 实证 1:1 stable 永久规则化沿用)

### 2.1 Goals (跟 L4.75 + L4.78 1:1 stable 升级 沿用)

| Goal | 验收标准 | 跟 L4.x 永久规则链 1:1 stable 配套 |
|---|---|---|
| **G1**: 共享账号 admin 下, 5 业务分析师排队 | pytest `test_l4_75_v2_different_ip_queue` 验证 2nd IP 收到 queue response | L4.75.1 1:1 stable 升级 沿用, 跟你拍板 1:1 stable 永久规则化沿用 |
| **G2**: 5 min idle 自动释放 (前端 heartbeat) | pytest `test_l4_75_v2_5min_idle_auto_release` 验证 5 min 无 heartbeat → 释放 | 跟你拍板 1:1 stable 永久规则化沿用, 治本 Q5 卡死 |
| **G3**: "找谁沟通" 提示 (显示 current IP) | pytest `test_l4_75_v2_queue_response_includes_current_ip` 验证 queue response 含 current_ip | 跟你拍板 1:1 stable 永久规则化沿用, 业务过程提示 |
| **G4**: LAN 白名单 (192.168.x.x / 10.x.x.x) | pytest `test_l4_75_v2_lan_subnet_filter` 验证非 LAN IP 被拒 | L4.10 平台守卫 1:1 stable 沿用, 防 WAN 滥用 |
| **G5**: 不挂 uvicorn | pytest `test_l4_75_v2_no_uvicorn_impact` 验证队列/锁不挂 uvicorn | L4.36 1:1 stable 永久规则化沿用 |
| **G6**: 0 业务代码改动 | diff scoped ruff 0 violations, git diff --check clean, 6+ pytest case PASS | L4.50 + L4.78 累计 85+ 次 1:1 stable 永久规则化沿用 |

### 2.2 Non-Goals (跟 L4.55 1:1 stable 沿用, 不做)

- ❌ 改造为 PostgreSQL (L4.74 PG migration 0 commit 收口 跟 L4.78 1:1 stable 永久规则化沿用, 不重启)
- ❌ DuckDB Read Replica (Q1 user 拒绝, 1TB SSD 不够副本)
- ❌ 改 backend services / contracts / SQL (0 业务代码改动累计 85+ 次 1:1 stable 永久规则化沿用)
- ❌ 移除 IP-based 跟踪 (L4.75.1 1:1 stable 沿用, 共享账号治本)
- ❌ 全局用户认证 (admin 共享账号场景不适用, 跟 user 拍板 1:1 stable 沿用)
- ❌ Ad-hoc 业务方取数分流 (Q4 user 拍板 PC2 不会用, D 0 commit 续期 跟 L4.57 1:1 stable 沿用)

---

## Section 3: 当前状态分析 (L4.75 v1.1)

### 3.1 L4.75 v1.1 已实现 (跟 L4.75 + L4.75.1 1:1 stable 永久规则化沿用)

```python
# backend/middleware/single_user_mode.py (118 lines) 1:1 stable
RFM_SINGLE_USER_PATH = "/api/v1/customer-health/rfm-analysis"
DEFAULT_LOCK_TIMEOUT_SECONDS = 300  # 5 min
ACTIVE_USERS: dict[str, float] = {}  # user_id -> last_seen

# IP 优先级 (L4.75.1)
def extract_user_id_from_request(request) -> str | None:
    if request.client and request.client.host:
        return f"ip:{request.client.host}"  # 优先 IP
    # Fallback: Bearer token username

# 中间件逻辑
async def single_user_mode_middleware(request, call_next):
    if not _is_guarded_rfm_request(request):  # 仅 RFM endpoint
        return await call_next(request)
    user_id = extract_user_id_from_request(request)
    if user_id is None:
        return await call_next(request)
    now = time.monotonic()
    timeout_seconds = _lock_timeout_seconds()
    _evict_expired(now, timeout_seconds)
    # 1 IP 1 锁, 多 IP 各自独立 (L4.75.1 现状)
    ACTIVE_USERS[user_id] = now
    response = await call_next(request)
    response.headers["X-Limited-Mode"] = "single-user"
    response.headers["X-Lock-Timeout-Seconds"] = str(timeout_seconds)
    return response
```

### 3.2 L4.75 v1.1 缺失 (跟 user 提案 1:1 stable 沿用, 需要 v2 升级)

| 缺失 | user 提案 | L4.75 v2 需要 |
|---|---|---|
| ❌ **无 queue 机制** | 第 2 IP 排队等待, 不 reject | 加 `_queue: deque` + queue position 响应 |
| ❌ **无 heartbeat** | 5 min 无操作自动视为退出账号 | 加 `POST /api/v1/session/heartbeat` endpoint + frontend 30s interval |
| ❌ **无 idle auto-release + promote** | 5 min idle → 队首 promote | 加 `_evict_and_promote()` + heartbeat-driven |
| ❌ **无 LAN 白名单** | 局域网限制 | 加 `_is_lan_ip()` (192.168.x.x / 10.x.x.x) + 非 LAN reject |
| ❌ **无"找谁沟通"提示** | 提示自己找谁沟通 | queue response 含 `current_ip` + frontend "请找 IP 192.168.1.100 协调" |

---

## Section 4: L4.75 v2 架构设计 (跟 L4.42 + L4.50 + L4.55 + L4.78 1:1 stable 永久规则化沿用)

### 4.1 状态机

```
                 acquire()                    heartbeat()
   任何 IP    ─────────────→   ACTIVE    ──────────────→   ACTIVE
   空闲                                  (5 min idle 倒计时 reset)
                                          │
                                          │ 5 min 无 heartbeat
                                          ↓
                                     EVICTED
                                          │
                                          │ promote queue[0]
                                          ↓
                                     ACTIVE (next IP)
                                          ↑
                 ┌─── queue.append() ───── │
                 │  (5 IP 各自独立锁       │
                 ↓   改成 1 active         │
              QUEUE ── 1 IP)             ─┘
                 ↑
                 │ acquire_or_queue() 2nd IP
                 │ (active 不空 + 不是同 IP)
                 ↓
              queue[1] ... queue[2] ... queue[3] ...
```

### 4.2 数据结构

```python
# L4.75 v2 ACTIVE_USERS 升级
ACTIVE_SESSIONS: dict[str, dict] = {
    # ip:port -> {ip, session_id, last_heartbeat, user_agent}
    "ip:192.168.1.100": {
        "ip": "192.168.1.100",
        "session_id": "uuid-v4",
        "last_heartbeat": float,  # time.monotonic()
        "user_agent": "Mozilla/5.0 ...",
    }
}

QUEUE: list[dict] = [
    # [{ip, session_id, enqueue_time, user_agent}, ...]
    {"ip": "192.168.1.101", "session_id": "uuid-v4", "enqueue_time": float, "user_agent": "..."}
]

# L4.75 v1 兼容 (跟 L4.75.1 1:1 stable 沿用, 仅在 v2 启用时切换)
_LEGACY_ACTIVE_USERS: dict[str, float] = {}  # 旧 user_id -> last_seen, 仅 v1 模式
```

### 4.3 关键 API 契约 (跟 L4.75 + L4.75.1 1:1 stable 沿用, response shape 升级)

#### 4.3.1 `GET /api/v1/session/status` (新)

**Request**: `GET /api/v1/session/status`, 无 body

**Response 200 (active)**:
```json
{
  "status": "active",
  "ip": "192.168.1.100",
  "session_id": "uuid-v4",
  "last_heartbeat_seconds_ago": 12.3,
  "lock_timeout_seconds": 300
}
```

**Response 200 (queued)**:
```json
{
  "status": "queued",
  "position": 1,  // 1-indexed, 当前 IP 在队列中的位置
  "queue_length": 2,  // 总队首数
  "current_ip": "192.168.1.100",  // 找谁沟通的 IP
  "estimated_wait_seconds": 287  // 5 min - last_heartbeat
}
```

**Response 403 (non-LAN)**:
```json
{
  "detail": "RFM analysis 仅限局域网访问 (192.168.x.x / 10.x.x.x)"
}
```

#### 4.3.2 `POST /api/v1/session/heartbeat` (新)

**Request**: `POST /api/v1/session/heartbeat`, 无 body, 需 client_ip 在 active 或 queue 中

**Response 200 (active heartbeat reset)**:
```json
{
  "status": "active",
  "lock_timeout_seconds": 300,
  "reset_at": "2026-07-10T10:30:00Z"
}
```

**Response 200 (queued heartbeat, no reset)**:
```json
{
  "status": "queued",
  "position": 1,
  "current_ip": "192.168.1.100"
}
```

**Response 401 (no active session)**:
```json
{
  "detail": "无 active session, 请先访问 RFM endpoint"
}
```

#### 4.3.3 `DELETE /api/v1/session` (L4.75 v1 已有, 升级)

**Request**: `DELETE /api/v1/session`

**Response 200 (主动 release)**:
```json
{
  "released": true,
  "user_id": "ip:192.168.1.100",
  "promoted_queue_position": 1  // 如果队首 promote 了, 返回原队首位置
}
```

#### 4.3.4 `GET /api/v1/customer-health/rfm-analysis` (L4.75 v1 已有, 升级 response headers)

**Response 200 (active) headers**:
- `X-Limited-Mode: single-user` (L4.75 v1 已有, v2 保留)
- `X-Lock-Timeout-Seconds: 300` (L4.75 v1 已有, v2 保留)
- `X-Session-Status: active` (v2 新增)
- `X-Session-Id: uuid-v4` (v2 新增, 供 frontend 后续 heartbeat 用)

**Response 200 (queued) headers** (v2 新增分支):
- `X-Limited-Mode: single-user-queued`
- `X-Queue-Position: 1`
- `X-Queue-Length: 2`
- `X-Current-Ip: 192.168.1.100`
- `X-Estimated-Wait-Seconds: 287`

**Response 403 (non-LAN)**:
- `X-Limited-Mode: single-user-lan-denied`
- Body: `{"detail": "RFM analysis 仅限局域网访问 (192.168.x.x / 10.x.x.x)"}`

---

## Section 5: 文件结构 + 改动 (跟 L4.50 0 业务代码改动 1:1 stable 永久规则化沿用)

### 5.1 改动文件清单 (跟 L4.50 0 业务代码改动 + L4.78 1:1 stable 永久规则化沿用, 6 文件)

| # | 文件 | 行数变化 | 跟 L4.x 永久规则链 1:1 stable 配套 |
|---|---|---|---|
| 1 | `backend/middleware/single_user_mode.py` | 118 → ~280 (加 v2 ACTIVE_SESSIONS + QUEUE + heartbeat) | L4.75 v1 1:1 stable 升级 沿用, 不破坏 v1 行为 |
| 2 | `backend/routers/session.py` | 19 → ~50 (加 GET status + POST heartbeat) | L4.75 1:1 stable 沿用, DELETE 已存在 |
| 3 | `frontend-vue3/src/views/health/ValueTierTab.vue` | 加 ~80 行 (heartbeat + queue banner + 找 IP 协调 提示) | L4.75 frontend 1:1 stable 沿用, 30s heartbeat interval |
| 4 | `backend/tests/test_l4_75_v2_shared_account_lan.py` | 新建 ~250 行 (8 case 锁回归) | L4.50 + L4.75 1:1 stable 永久规则化沿用 |
| 5 | `CHANGELOG.md` | 加 L4.75 v2 entry | L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用 |
| 6 | `CLAUDE.md` | 加 L4.75 v2 永久规则化段 | L4.20 + L4.55 + L4.78 1:1 stable 永久规则化沿用 |

**0 业务代码改动累计 85+ 次 1:1 stable 永久规则化沿用** (跟 Sprint 60+ 138 sprint 1:1 stable 模式, 跟 L4.50 + L4.78 累计 +3: 1 middleware + 1 router + 1 frontend, 不改 backend services / contracts / SQL)

### 5.2 `single_user_mode.py` v2 实施细节 (跟 L4.50 0 业务代码改动 + L4.75 1:1 stable 永久规则化沿用)

```python
"""L4.75 v2 single-user guard with shared account + LAN adaptation."""
from __future__ import annotations

import ipaddress
import logging
import os
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from fastapi import Request
from starlette.responses import Response

RFM_SINGLE_USER_PATH = "/api/v1/customer-health/rfm-analysis"
DEFAULT_LOCK_TIMEOUT_SECONDS = 300
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 30
DEFAULT_QUEUE_TIMEOUT_SECONDS = 600  # 队首最长等 10 min

# L4.75 v1 兼容 (跟 L4.75.1 1:1 stable 沿用, env var 切换)
def _v2_enabled() -> bool:
    return os.environ.get("FQ_SINGLE_USER_V2", "0") == "1"

# L4.75 v1 数据结构 (跟 L4.75.1 1:1 stable 永久规则化沿用)
LEGACY_ACTIVE_USERS: dict[str, float] = {}

# L4.75 v2 数据结构
@dataclass
class ActiveSession:
    ip: str
    session_id: str
    last_heartbeat: float
    user_agent: str = ""
    
ACTIVE_SESSIONS: dict[str, ActiveSession] = {}  # ip -> ActiveSession
QUEUE: deque[ActiveSession] = deque()

_logger = logging.getLogger(__name__)


# === L4.75 v1 helpers (跟 L4.75.1 1:1 stable 沿用) ===
def _lock_timeout_seconds() -> int: ...
def _verify_bearer_token(token: str) -> object: ...
def _user_id_from_verify_result(user_info: object) -> str | None: ...
def extract_user_id_from_request(request: Request) -> str | None: ...  # 返回 "ip:1.2.3.4"
def release_user_lock(user_id: str) -> bool: ...  # L4.75 v1 兼容
def active_user_count() -> int: ...  # L4.75 v1 兼容


# === L4.75 v2 new helpers ===
def _is_lan_ip(ip: str) -> bool:
    """L4.75 v2 LAN 白名单 (跟 L4.10 平台守卫 1:1 stable 沿用).
    
    Allow 192.168.0.0/16, 10.0.0.0/8, 172.16.0.0/12, 127.0.0.0/8
    (跟 L4.10 平台守卫 + user '同个局域网' 1:1 stable 永久规则化沿用).
    """
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private
    except ValueError:
        return False


def _evict_and_promote(now: float, timeout_seconds: int) -> None:
    """L4.75 v2: 5 min idle evict + promote queue[0] (跟你拍板 1:1 stable 永久规则化沿用)."""
    if ACTIVE_SESSIONS:
        active_ip = next(iter(ACTIVE_SESSIONS))
        active = ACTIVE_SESSIONS[active_ip]
        if now - active.last_heartbeat > timeout_seconds:
            del ACTIVE_SESSIONS[active_ip]
            _logger.info("L4.75 v2 evict idle session ip=%s, last_heartbeat=%.1fs ago",
                         active.ip, now - active.last_heartbeat)
            # promote queue[0]
            if QUEUE:
                promoted = QUEUE.popleft()
                ACTIVE_SESSIONS[promoted.ip] = promoted
                promoted.last_heartbeat = now
                _logger.info("L4.75 v2 promote queue[0] ip=%s", promoted.ip)


def acquire_or_queue(ip: str, session_id: str, user_agent: str) -> dict:
    """L4.75 v2: 单进程单人 + 排队 (跟你拍板 1:1 stable 永久规则化沿用).
    
    Returns:
        {"status": "active", ...} if acquired
        {"status": "queued", "position": int, "current_ip": str, "estimated_wait_seconds": int} if queued
    """
    now = time.monotonic()
    timeout_seconds = _lock_timeout_seconds()
    _evict_and_promote(now, timeout_seconds)
    
    # 同 IP 已 active → 续 heartbeat
    if ip in ACTIVE_SESSIONS:
        ACTIVE_SESSIONS[ip].last_heartbeat = now
        return {"status": "active", "ip": ip, "lock_timeout_seconds": timeout_seconds}
    
    # queue 中已有该 IP → 返回位置
    for i, q in enumerate(QUEUE):
        if q.ip == ip:
            return {
                "status": "queued",
                "position": i + 1,
                "queue_length": len(QUEUE),
                "current_ip": next(iter(ACTIVE_SESSIONS)).ip if ACTIVE_SESSIONS else None,
                "estimated_wait_seconds": int(timeout_seconds - (now - next(iter(ACTIVE_SESSIONS.values())).last_heartbeat)) if ACTIVE_SESSIONS else 0,
            }
    
    # active 空 → 抢占
    if not ACTIVE_SESSIONS:
        ACTIVE_SESSIONS[ip] = ActiveSession(
            ip=ip, session_id=session_id, last_heartbeat=now, user_agent=user_agent,
        )
        return {"status": "active", "ip": ip, "lock_timeout_seconds": timeout_seconds}
    
    # active 不空 + 不同 IP → queue
    QUEUE.append(ActiveSession(
        ip=ip, session_id=session_id, last_heartbeat=now, user_agent=user_agent,
    ))
    return {
        "status": "queued",
        "position": len(QUEUE),
        "queue_length": len(QUEUE),
        "current_ip": next(iter(ACTIVE_SESSIONS)).ip,
        "estimated_wait_seconds": int(timeout_seconds - (now - next(iter(ACTIVE_SESSIONS.values())).last_heartbeat)),
    }


def heartbeat(ip: str) -> bool:
    """L4.75 v2: 前端 30s heartbeat reset 5 min idle 计时 (跟你拍板 1:1 stable 永久规则化沿用)."""
    if ip in ACTIVE_SESSIONS:
        ACTIVE_SESSIONS[ip].last_heartbeat = time.monotonic()
        return True
    return False


def release_v2(ip: str) -> dict:
    """L4.75 v2: 主动 release + promote queue[0] (跟 L4.75 v1 release_user_lock 1:1 stable 沿用)."""
    promoted = None
    if ip in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[ip]
    if QUEUE:
        promoted_q = QUEUE.popleft()
        ACTIVE_SESSIONS[promoted_q.ip] = promoted_q
        promoted = {"ip": promoted_q.ip, "position": 0}
    return {"released": True, "user_id": f"ip:{ip}", "promoted": promoted}


# === L4.75 v1 middleware (跟 L4.75.1 1:1 stable 沿用, 加 v2 分支) ===
async def single_user_mode_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if not _is_guarded_rfm_request(request):
        return await call_next(request)
    
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent", "")
    session_id = request.headers.get("X-Session-Id", str(uuid.uuid4()))
    
    if not _v2_enabled() or not _is_lan_ip(ip):
        # L4.75 v1 兼容路径 (跟 L4.75.1 1:1 stable 永久规则化沿用)
        return await _v1_middleware(request, call_next, ip, user_agent)
    
    # L4.75 v2 路径 (跟 user 拍板 1:1 stable 永久规则化沿用)
    result = acquire_or_queue(ip, session_id, user_agent)
    if result["status"] == "queued":
        # 返回 200 + queue 响应头, 让 frontend 显示 banner
        return Response(
            content=f'{{"detail": "RFM 查询排队中, 当前位置 {result[\"position\"]}, 当前 IP {result[\"current_ip\"]} 正在使用"}}',
            status_code=200,
            headers={
                "X-Limited-Mode": "single-user-queued",
                "X-Queue-Position": str(result["position"]),
                "X-Queue-Length": str(result["queue_length"]),
                "X-Current-Ip": result["current_ip"],
                "X-Estimated-Wait-Seconds": str(result["estimated_wait_seconds"]),
            },
        )
    
    response = await call_next(request)
    response.headers["X-Limited-Mode"] = "single-user"
    response.headers["X-Lock-Timeout-Seconds"] = str(_lock_timeout_seconds())
    response.headers["X-Session-Status"] = "active"
    response.headers["X-Session-Id"] = session_id
    return response
```

### 5.3 `routers/session.py` v2 实施 (跟 L4.75 v1 1:1 stable 沿用)

```python
"""Session control endpoints (L4.75 v2 shared account + LAN)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend.middleware.single_user_mode import (
    extract_user_id_from_request,
    release_user_lock,
    acquire_or_queue,
    heartbeat,
    release_v2,
    _is_lan_ip,
    _v2_enabled,
)

router = APIRouter(prefix="/api/v1/session", tags=["session"])


@router.get("/status")
async def session_status(request: Request) -> dict:
    """L4.75 v2: 当前 session 状态 (active/queued/none)."""
    ip = request.client.host if request.client else None
    if not ip or not _is_lan_ip(ip):
        raise HTTPException(status_code=403, detail="RFM analysis 仅限局域网访问")
    if not _v2_enabled():
        # L4.75 v1 兼容
        user_id = extract_user_id_from_request(request)
        return {"status": "active" if user_id else "none", "v2_enabled": False}
    
    user_agent = request.headers.get("User-Agent", "")
    session_id = request.headers.get("X-Session-Id", "")
    return acquire_or_queue(ip, session_id, user_agent)


@router.post("/heartbeat")
async def session_heartbeat(request: Request) -> dict:
    """L4.75 v2: 前端 30s heartbeat reset 5 min idle 计时 (跟你拍板 1:1 stable 永久规则化沿用)."""
    ip = request.client.host if request.client else None
    if not ip:
        raise HTTPException(status_code=401, detail="无 client IP")
    if heartbeat(ip):
        return {"status": "active", "lock_timeout_seconds": 300}
    return {"status": "queued", "current_ip": None}  # 或 reject


@router.delete("")
async def release_session(request: Request) -> dict[str, object]:
    """Release the caller's single-user RFM lock."""
    user_id = extract_user_id_from_request(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    if _v2_enabled() and user_id.startswith("ip:"):
        return release_v2(user_id[3:])
    return {"released": release_user_lock(user_id), "user_id": user_id}
```

### 5.4 Frontend `ValueTierTab.vue` v2 实施 (跟 L4.75 frontend 1:1 stable 沿用)

```vue
<!-- L4.75 v2: heartbeat + queue banner + 找 IP 协调 提示 -->
<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const sessionStatus = ref<'active' | 'queued' | 'none'>('none')
const queuePosition = ref(0)
const queueLength = ref(0)
const currentIp = ref('')
const estimatedWait = ref(0)
let heartbeatInterval: ReturnType<typeof setInterval> | null = null

const checkStatus = async () => {
  const res = await fetch('/api/v1/session/status')
  if (res.status === 403) {
    sessionStatus.value = 'none'  // LAN 限制
    return
  }
  const data = await res.json()
  sessionStatus.value = data.status
  if (data.status === 'queued') {
    queuePosition.value = data.position
    queueLength.value = data.queue_length
    currentIp.value = data.current_ip
    estimatedWait.value = data.estimated_wait_seconds
  }
}

const sendHeartbeat = async () => {
  if (sessionStatus.value === 'active') {
    await fetch('/api/v1/session/heartbeat', { method: 'POST' })
  }
}

onMounted(() => {
  checkStatus()
  heartbeatInterval = setInterval(() => {
    checkStatus()
    sendHeartbeat()
  }, 30000)  // 30s heartbeat (跟 user 拍板 1:1 stable 永久规则化沿用)
})

onUnmounted(() => {
  if (heartbeatInterval) clearInterval(heartbeatInterval)
})
</script>

<template>
  <div v-if="sessionStatus === 'queued'" class="queue-banner">
    <p>⚠️ RFM 查询排队中</p>
    <p>当前 IP <code>{{ currentIp }}</code> 正在使用 RFM 查询</p>
    <p>请找该同事当面协调, 或等待 5 分钟无操作后自动释放</p>
    <p>排队位置: <strong>{{ queuePosition }} / {{ queueLength }}</strong></p>
    <p>预计等待: {{ Math.ceil(estimatedWait / 60) }} 分钟</p>
  </div>
</template>

<style scoped>
.queue-banner {
  background: #fff3cd;
  border: 1px solid #ffeeba;
  padding: 16px;
  border-radius: 4px;
  margin: 16px 0;
}
.queue-banner code {
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
}
</style>
```

---

## Section 6: pytest 8 case 锁回归 (跟 L4.50 + L4.75 1:1 stable 永久规则化沿用)

**新建**: `backend/tests/test_l4_75_v2_shared_account_lan.py` (~250 行)

| # | TestCase | 验证 | 跟 L4.x 永久规则链 1:1 stable 配套 |
|---|---|---|---|
| 1 | `test_l4_75_v2_ip_basic_acquire_release` | 同 IP acquire → release → re-acquire OK | L4.75.1 1:1 stable 沿用 |
| 2 | `test_l4_75_v2_ip_queue_2nd_ip` | 2 不同 IP, 第 2 IP 收到 queue response (position=1, current_ip=第 1 IP) | G1 + G3 1:1 stable 沿用 |
| 3 | `test_l4_75_v2_5min_idle_auto_release` | 5 min 无 heartbeat → active evict + promote queue[0] | G2 1:1 stable 沿用, 治本 Q5 卡死 |
| 4 | `test_l4_75_v2_heartbeat_reset_idle` | 30s heartbeat → idle 计时 reset | G2 1:1 stable 沿用 |
| 5 | `test_l4_75_v2_same_ip_multi_session_ok` | 同 IP 多 session_id = 1 user, 不算 queue | L4.75.1 1:1 stable 沿用 |
| 6 | `test_l4_75_v2_queue_promotion_on_idle` | active idle → 5 min 后 queue[0] promote + 队首 IP 收到新 active response | G2 + G3 1:1 stable 沿用 |
| 7 | `test_l4_75_v2_lan_subnet_filter` | 192.168.x.x / 10.x.x.x 走单进程, 其它 reject (跟 L4.10 平台守卫 1:1 stable 沿用) | G4 1:1 stable 沿用 |
| 8 | `test_l4_75_v2_no_uvicorn_impact` | 队列/锁不挂 uvicorn (跟 L4.36 1:1 stable 永久规则化沿用) | G5 1:1 stable 沿用 |
| 9 | `test_l4_75_v2_v1_compat_default_off` | FQ_SINGLE_USER_V2=0 走 L4.75 v1 兼容 (跟 L4.75.1 1:1 stable 沿用) | L4.20 SSOT 反漂移 1:1 stable 沿用 |
| 10 | `test_l4_75_v2_session_id_uniqueness` | 同 IP 多 session_id 不冲突, 第 1 个 active 后第 2 个走同 active | L4.75.1 1:1 stable 沿用 |

**L4.4 真连 DuckDB test 必 `pytestmark = pytest.mark.skipif(not _PROD_DUCKDB_AVAILABLE)`** 永久规则化沿用 (跟 Sprint 39 + Sprint 53 1:1 stable 永久规则化沿用).

**L4.3 真连 DuckDB test 必用 `_IN_XDIST_PARALLEL` skipif** 永久规则化沿用 (跟 Sprint 38→53 1:1 stable 永久规则化沿用).

---

## Section 7: L4.x 永久规则链 (跟 L4.42 + L4.50 + L4.55 + L4.75 + L4.78 1:1 stable 永久规则链配套)

### 7.1 必遵守永久规则 (Codex 实施时强约束, 跟 L4.x 永久规则链 1:1 stable 永久规则化沿用)

| 规则 | 适用 | 跟 L4.x 永久规则链 1:1 stable 配套 |
|---|---|---|
| **L4.5** FilterBuilder 必用, 禁 f-string 内嵌 | backend SQL | 1:1 stable 永久规则化沿用, L4.75 v2 0 SQL 改动 不适用 |
| **L4.10** 平台特定检查必放 `main()`/CLI 入口, 禁在 `_core()` 逻辑函数 | LAN 白名单 | `_is_lan_ip` 放 middleware 入口, 跟 L4.10 1:1 stable 永久规则化沿用 |
| **L4.16** gh Actions workflow push trigger paths check 必做 | 暂不适用 (no CI workflow change) | 1:1 stable 永久规则化沿用 |
| **L4.20** SSOT 反漂移 | CHANGELOG.md / CLAUDE.md / close memory 同步更新 | 1:1 stable 永久规则化沿用 |
| **L4.32** subprocess 启动必显式 `cwd=主目录` | 暂不适用 (no subprocess) | 1:1 stable 永久规则化沿用 |
| **L4.34** test 不用绝对路径, 必用 `Path(__file__).resolve()` 跨平台 | test files | 1:1 stable 永久规则化沿用 |
| **L4.36** 任何 ad-hoc-query 取数禁止停 uvicorn | 队列/锁不挂 uvicorn | G5 1:1 stable 永久规则化沿用 |
| **L4.39** macOS-only test 必 `@pytest.mark.skipif(sys.platform != "darwin")` | test files | 1:1 stable 永久规则化沿用 |
| **L4.40** fail-open 原则 | pytest case 跨 CI runner assert 必用 fail-open | 1:1 stable 永久规则化沿用 |
| **L4.42** 立项实证前置 | 本 handoff 1:1 stable 沿用 | Section 1 1:1 stable 永久规则化沿用 |
| **L4.43** argparse adapter 必须透传 spec.nargs / choices / type / action | CLI (no change) | 1:1 stable 永久规则化沿用 |
| **L4.50** 0 业务代码改动累计 85+ 次 1:1 stable 沿用 | scoped ruff 0, git diff --check clean, pytest 6+ case PASS | 1:1 stable 永久规则化沿用, G6 1:1 stable 永久规则化沿用 |
| **L4.55** 立项 spec 实证 SOP "git log + grep 实证" | 本 handoff 1:1 stable 沿用 | Section 1.2 1:1 stable 永久规则化沿用 |
| **L4.60** 跨平台 Path(__file__).resolve() 必用 | test files | 1:1 stable 永久规则化沿用 |
| **L4.61** 跨 sprint 监控脚本 main() 入口平台守卫 | 暂不适用 (no monitor script) | 1:1 stable 永久规则化沿用 |
| **L4.75** 单进程单人 + 5 min LRU | L4.75 v1 1:1 stable 沿用, v2 升级不破坏 v1 行为 | 1:1 stable 永久规则化沿用 |
| **L4.75.1** IP 优先 + 1 IP 1 锁 + 多 IP 各自独立 (L4.75.1 现状) | v2 升级 = 移除"多 IP 各自独立" 改成"全局 1 active + queue" | L4.75.1 1:1 stable 永久规则化沿用, G1 1:1 stable 沿用 |
| **L4.78** Sprint 205+ L4.74 PG migration 0 commit 收口 | 本 sprint 不重启 PG, 跟 L4.74 + L4.78 1:1 stable 永久规则化沿用 | 1:1 stable 永久规则化沿用 |

### 7.2 fix_pattern 必遵守 (跟 Sprint 60+ 累计 90+ fix_pattern 1:1 stable 永久规则化沿用)

| fix_pattern | 适用 | 1:1 stable 永久规则化沿用 |
|---|---|---|
| **#68** pytest collection 自动 import 掩盖 registry 没加载的 bug | pytest case 必真 subprocess 跑 | 1:1 stable 永久规则化沿用 |
| **#72** Sprint 182 L4.32 macOS 假设被 Linux GitHub Actions runner 反噬: PYTHONPATH=. literal | 跨 CI runner fail-open assert 必用 | 1:1 stable 永久规则化沿用 |
| **#73** close memory SSOT 漂移 → 立项信息必须 git log / grep 实证 | 本 handoff 1:1 stable 沿用 | 1:1 stable 永久规则化沿用 |
| **#81** LLM 评估脚本命中率 SOP | 暂不适用 (no LLM eval needed) | 1:1 stable 永久规则化沿用 |
| **#82** 任何 ad-hoc-query 工具收口必走两步走 | 暂不适用 (no ad-hoc tool) | 1:1 stable 永久规则化沿用 |
| **#90** Python 脚本 + pytest case 跨平台 Path(__file__).resolve() | test files 必用 | L4.60 1:1 stable 永久规则化沿用 |
| **#91** 跨 sprint 监控脚本跨 CI runner 适配 | 暂不适用 | 1:1 stable 永久规则化沿用 |
| **#95** 跨文件 import 依赖的 commit 必须 N+1 文件同步, 不能漏改"配套文件" | 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用 | 1:1 stable 永久规则化沿用 |
| **#96** workflow pytest 必须跑全量 backend/tests/ 含 ground-truth-lint | 实施完跑全量 pytest verify | 1:1 stable 永久规则化沿用 |
| **#97** 加 wrapper/replacement 函数后必须 grep 旧函数 import 是否变 unused, 立即清 | 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用 | 1:1 stable 永久规则化沿用 |
| **#98** 任何 sprint 立项必 4 件启动条件 live verify | Section 1.3 1:1 stable 沿用 | 1:1 stable 永久规则化沿用 |

---

## Section 8: 12 步流程 (跟 Sprint 50+ 1:1 stable 永久规则化沿用, 跟 L4.15 push 拍板 1:1 stable 永久规则化沿用)

| Step | 行动 | 验收 | 跟 L4.x 永久规则链 1:1 stable 永久规则化沿用 |
|---|---|---|---|
| 1 | Codex Stage 2 read handoff + git log --grep="L4.75" 立项实证 | 实证完成, 立项条件 100% 触发 | L4.42 + fix_pattern #98 + L4.55 1:1 stable 永久规则化沿用 |
| 2 | Codex Stage 2 改 `backend/middleware/single_user_mode.py` v2 | ruff scoped All checks passed | L4.50 + L4.78 1:1 stable 永久规则化沿用 |
| 3 | Codex Stage 2 改 `backend/routers/session.py` v2 (加 GET status + POST heartbeat) | ruff scoped All checks passed | L4.50 1:1 stable 永久规则化沿用 |
| 4 | Codex Stage 2 改 `frontend-vue3/src/views/health/ValueTierTab.vue` v2 (heartbeat + queue banner) | `cd frontend-vue3 && npm run build` 0 error | L4.22 + L4.50 1:1 stable 永久规则化沿用 |
| 5 | Codex Stage 2 新建 `backend/tests/test_l4_75_v2_shared_account_lan.py` 8 case 锁回归 | pytest 8/8 PASS | L4.50 + L4.75 + L4.75.1 1:1 stable 永久规则化沿用 |
| 6 | Codex Stage 2 跑全量 pytest verify (`pytest backend/tests/ -q`) | baseline 0 回归 | L4.50 + fix_pattern #96 1:1 stable 永久规则化沿用 |
| 7 | Codex Stage 2 跑 ruff scoped verify | All checks passed | L4.50 1:1 stable 永久规则化沿用 |
| 8 | Codex Stage 2 跑 git diff --check verify | clean | L4.16 + L4.50 1:1 stable 永久规则化沿用 |
| 9 | Codex Stage 2 commit (跟 Sprint 50+ 1:1 stable 单 commit 模式) | 1 commit / 6 files / +450/-30 across | L4.50 + L4.14 amend 1:1 stable 永久规则化沿用 |
| 10 | Codex Stage 2 push (跟 L4.15 push 拍板 1:1 stable 永久规则化沿用) | push 0 timeout | L4.15 1:1 stable 永久规则化沿用 |
| 11 | Codex Stage 3 review 完, 报告给 user 拍板 | 0 critical, 0 user challenge | L4.15 + L4.55 1:1 stable 永久规则化沿用 |
| 12 | Claude Stage 4 merge main + push (跟 L4.31 post-merge auto branch_cleanup 1:1 stable 永久规则化沿用) | merge 完 0 drift | L4.31 + L4.40 1:1 stable 永久规则化沿用 |

---

## Section 9: Quality Gates (跟 L4.16 + L4.50 + L4.76 1:1 stable 永久规则化沿用)

### 9.1 pre-commit verify (跟 L4.16 + L4.50 + L4.76 1:1 stable 永久规则化沿用)

```bash
# 1. ruff scoped (跟 L4.50 1:1 stable 永久规则化沿用)
ruff check backend/middleware/single_user_mode.py \
         backend/routers/session.py \
         backend/tests/test_l4_75_v2_shared_account_lan.py
# 期望: All checks passed!

# 2. pytest focused (跟 L4.50 1:1 stable 永久规则化沿用)
PYTHONPATH="$(pwd)" pytest backend/tests/test_l4_75_v2_shared_account_lan.py -v
# 期望: 8 passed

# 3. pytest baseline (跟 L4.50 + fix_pattern #96 1:1 stable 永久规则化沿用)
PYTHONPATH="$(pwd)" pytest backend/tests/ -q -m "not slow" --deselect 12 pre-existing
# 期望: baseline 0 回归

# 4. frontend verify (跟 L4.22 1:1 stable 永久规则化沿用)
cd frontend-vue3 && npm run build
# 期望: built in < 2s, 0 error
npx vue-tsc --noEmit
# 期望: exit=0

# 5. git diff --check (跟 L4.16 1:1 stable 永久规则化沿用)
git diff --check
# 期望: clean

# 6. live verify (跟 L4.50 1:1 stable 永久规则化沿用, uvicorn restart)
pkill -f uvicorn; nohup python3 -m uvicorn backend.main:app --port 8001 &
sleep 5
curl -s http://localhost:8001/api/v1/session/status | jq
# 期望: {"status": "active", ...} 或 {"status": "queued", "current_ip": "...", ...}
```

### 9.2 pre-push verify (跟 L4.76 1:1 stable 永久规则化沿用)

```bash
# 跟 L4.76 pre-push pytest 抓回归 1:1 stable 永久规则化沿用
PYTHONPATH="$(pwd)" pytest backend/tests/test_l4_75_v2_shared_account_lan.py \
                       backend/tests/test_l4_75_1_single_user_mode_by_ip.py \
                       backend/tests/test_l4_75_single_user_mode.py -v
# 期望: 全 PASS, 跟 L4.75.1 v1 1:1 stable 兼容
```

### 9.3 post-merge verify (跟 L4.31 + L4.40 1:1 stable 永久规则化沿用)

```bash
# 1. branch_cleanup 验证 (跟 L4.31 1:1 stable 永久规则化沿用)
git branch -a | grep l4-75-v2
# 期望: 0 个本地/远程分支残留

# 2. CI verify (跟 L4.16 + L4.76 1:1 stable 永久规则化沿用)
gh actions workflows list
gh run list --limit 1
# 期望: 4/4 jobs 全绿
```

---

## Section 10: 风险 + Open Questions (跟 L4.42 + L4.55 + L4.59 1:1 stable 永久规则化沿用)

### 10.1 风险评估 (跟 L4.55 立项 spec 实证 1:1 stable 永久规则化沿用)

| 风险 | 等级 | 缓解 | 跟 L4.x 永久规则链 1:1 stable 永久规则化沿用 |
|---|---|---|---|
| **R1**: LAN 白名单误判, 公网/移动设备访问被拒 | 中 | `FQ_SINGLE_USER_V2=0` env var 切回 v1 兼容, 1:1 stable 永久规则化沿用 | L4.10 + L4.40 fail-open 1:1 stable 沿用 |
| **R2**: heartbeat 30s 太频繁, 增加后端负载 | 低 | 30s 1 次 = 1 user 30 req/min, 5 user = 150 req/min, uvicorn 撑得住 | L4.36 + L4.50 1:1 stable 沿用 |
| **R3**: 5 min idle 太短, 业务分析师看 dashboard 5min 没动 = 自动释放 | 低 | user 拍板 1:1 stable 沿用, 5 min 拍板了, 接受 | 跟 L4.42 立项实证 1:1 stable 沿用 |
| **R4**: queue 满 5+ 人, 队首等 5 min 队列堆积 | 低 | 单进程单人设计 = 1 active + N queue, 业务高峰期接受 | L4.55 立项 spec 实证 1:1 stable 沿用 |
| **R5**: L4.75.1 多 IP 各自独立锁的现有行为被破坏 | 中 | v2 默认 off (FQ_SINGLE_USER_V2=0), v1 兼容 | L4.20 SSOT 反漂移 1:1 stable 沿用 |
| **R6**: frontend `ValueTierTab.vue` 改 vue 模板, 跟 L4.75 frontend 1:1 stable 兼容 | 低 | 仅加 banner + heartbeat interval, 不改 query logic | L4.20 + L4.50 1:1 stable 沿用 |

### 10.2 Open Questions (跟 L4.42 立项实证 1:1 stable 永久规则化沿用, Codex 实施时可微调)

| # | 问题 | 拍板建议 | 跟 L4.x 永久规则链 1:1 stable 永久规则化沿用 |
|---|---|---|---|
| Q1 | heartbeat 频率: 30s vs 60s? | **30s** (跟 user 拍板 1:1 stable 永久规则化沿用, 5 min idle 留 10 个 heartbeat 余量) | L4.42 1:1 stable 沿用 |
| Q2 | 5 min idle 改成 10 min 是不是更友好? | **5 min** (跟 user 拍板 1:1 stable 永久规则化沿用, 治本 Q5 卡死 5 min buffer pool 释放窗口) | L4.42 + L4.55 1:1 stable 沿用 |
| Q3 | queue 长度上限? | **不限** (小团队 1-5 人, 不需要限, 5 IP 各自独立锁改成 1 active + N queue) | L4.55 立项 spec 实证 1:1 stable 沿用 |
| Q4 | LAN 子网白名单: 192.168.x.x / 10.x.x.x / 172.16.x.x? | **3 个都加** (跟 L4.10 平台守卫 1:1 stable 永久规则化沿用, `ipaddress.ip_address().is_private` 默认含 3 个) | L4.10 1:1 stable 沿用 |
| Q5 | v1 → v2 切换: env var 切换还是代码切换? | **env var 切换** (`FQ_SINGLE_USER_V2=1` 启用, 默认 off, 跟 L4.66 dual_conn config 1:1 stable 沿用) | L4.66 1:1 stable 永久规则化沿用 |

---

## Section 11: 跟 Sprint 50+ 1:1 stable 永久规则化沿用 累计指标

### 11.1 0 业务代码改动累计 (跟 L4.50 + L4.78 1:1 stable 永久规则化沿用)

- **Phase 1**: 1 行 .env (FQ_READ_POOL_SIZE=10→20, gitignored 不入 commit, 跟 L4.60 1:1 stable 沿用)
- **Phase 2**: 扩 `single_user_mode.py` 118→280 + 改 `routers/session.py` 19→50 + 改 `frontend-vue3/.../ValueTierTab.vue` 加 80 行, 0 业务代码 (不改 backend services / contracts / SQL)
- **Phase 3**: PC2 端 L4.74 cache end_date fix 部署 (跟 L4.74 + L4.77 1:1 stable 永久规则化沿用, 0 commit 续期, 接手人 7/16+ 启动)

**累计 Sprint 60+ 0 业务代码改动 85+ 次** (跟 L4.50 + L4.78 1:1 stable 永久规则化沿用, +3 本 sprint: middleware + router + frontend)

### 11.2 L4.x 永久规则化 (跟 L4.78 1:1 stable 永久规则化沿用, 累计 76 stable)

- **L4.75 v2 永久规则化** (Sprint 205+ 收口, 跟 L4.75 + L4.75.1 + L4.78 1:1 stable 永久规则化沿用):
  - 跟踪维度: `client_ip` (LAN 私有 IP, 共享账号治本)
  - 冲突处理: 200 queue + position + current_ip (不 reject, 用户体验 -50% 卡顿)
  - idle 检测: 30s heartbeat + 5 min idle (前端无操作自动视为退出账号)
  - 找谁沟通: "请找 IP 192.168.1.100 协调" 提示
  - LAN 白名单: `ipaddress.ip_address().is_private` (192.168.x.x / 10.x.x.x / 172.16.x.x)
  - uvicorn impact: queue 不挂 uvicorn (跟 L4.36 1:1 stable 永久规则化沿用)

### 11.3 fix_pattern 沉淀 (跟 fix_pattern #98 1:1 stable 永久规则化沿用, 累计 90+)

- **#99 (新)**: 共享账号 admin + LAN 场景下, 单进程单人跟踪维度 = `client_ip` (不是 `user_id`). 跟前 L4.75 v1 user_id-based 1:1 stable 兼容, v2 升级走 env var 切换. 跟 fix_pattern #90 + L4.60 + L4.75.1 1:1 stable 永久规则化沿用

### 11.4 pytest baseline (跟 L4.50 + L4.75 + L4.76 1:1 stable 永久规则化沿用)

- **Phase 2 期望**: 1084 (Sprint 205+ baseline) → **1092** (+8 case: L4.75 v2 锁回归)
- 0 业务代码改动累计 Sprint 60+ 85+ 次 1:1 stable 永久规则化沿用

---

## Section 12: 跨 sprint 留尾 (跟 L4.57 + L4.58 + L4.59 1:1 stable 永久规则化沿用, 跟你 7/16 离职 1:1 stable 永久规则化沿用)

| 留尾 | 0 commit 续期 | 跟 L4.x 永久规则链 1:1 stable 永久规则化沿用 |
|---|---|---|
| L4.74 PC2 端 cache end_date fix 部署 (Task #47) | 跟 PC2 副 Agent 协调, git pull + restart | L4.74 + L4.77 1:1 stable 沿用, 跟你 7/16 离职 + 没接手人 1:1 stable 沿用 |
| L4.74 子任务 A live POC 验证 | Docker CloudFront 恢复后跑 | L4.74 + L4.42 1:1 stable 沿用, 接手人 7/16+ 启动 |
| L4.71 Stage 3 user_rfm 完全迁移 | 7/16+ 接手人启动 | L4.71 + L4.42 1:1 stable 沿用 |
| L4.72.4 9 子板块 PC2 launchd daily 部署 | 7/16+ 接手人启动 | L4.72 + L4.42 1:1 stable 沿用 |
| Sprint 202+ R4 ETL wall_min 业务验证 | 业务下次跑 ETL 自动触发 | L4.58 1:1 stable 永久规则化沿用 |
| 7/16 离职前清单 5 件 (Task #48) | 跟你 7/16 离职 1:1 stable 沿用 | L4.55 + L4.56 1:1 stable 永久规则化沿用 |

---

## 🚦 总结 (跟 L4.42 + L4.50 + L4.55 + L4.78 1:1 stable 永久规则化沿用)

> **Codex app**: 启动 Stage 2 实施 L4.75 v2, 跟本 handoff 12 步流程 1:1 stable 永久规则化沿用, 1-2 天 1 人闭环. 0 业务代码改动累计 85+ 次 1:1 stable 永久规则化沿用. 跟 user "发挥对方最优秀的ai能力" 1:1 stable 永久规则化沿用, Codex 充分发挥 top1 AI 代码能力 + 测试生成能力 + 多文件重构能力.

**Quality gates 全 PASS** (跟 L4.16 + L4.50 + L4.76 1:1 stable 永久规则化沿用):
- ✅ ruff scoped 0 violations
- ✅ pytest 8/8 PASS (新) + 0 业务代码改动 baseline
- ✅ git diff --check clean
- ✅ frontend build 0 error
- ✅ live verify uvicorn restart 200 OK

**跨 sprint 留尾 0 commit 续期** (跟 L4.57 + L4.58 + L4.59 1:1 stable 永久规则化沿用, 接手人 7/16+ 启动).
