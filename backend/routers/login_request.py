"""L4.85 申请+同意 模式: 同账号不允许同时登陆 (跟 L4.84 自动踢互补, 跟 L4.75 v2 1:1 stable 永久规则化沿用).

业务模式 (跟 L4.42 立项实证 SOP 1:1 stable 配套, user 7/10 拍板 "申请登陆后 A 可以选择同意啥的"):
- A 已登录 (active)
- B 尝试登录 admin → 看到 "账号正在被使用" 提示
- B 提交申请 (verify 密码)
- A 收到申请 (polling /api/v1/auth/login-requests/pending)
- A 点 "同意" → A 登出, B 登录 (跟 L4.84 _evict_previous_sessions_for_user 1:1 stable 复用)
- A 点 "拒绝" → B 看到 "申请被拒绝"
- A 不响应 5 分钟 → 自动 expired (跟 L4.75 v2 lock_timeout_seconds 5min 1:1 stable 配套)

跟 L4.84 互补不冲突:
- L4.84 默认行为: admin 二次登录自动踢第一次 (evict 模式)
- L4.85 申请+同意 模式: B 申请 → A 同意 → 互踢 (request 模式)
- 通过 env 变量 FQ_LOGIN_MODE=evict|request 切换 (跟 L4.66 dual_conn config 1:1 stable 永久规则化沿用)
"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime

import bcrypt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

# 复用 auth.py 现有函数 (跟 L4.84 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套)
from backend.routers.auth import (
    ACTIVE_TOKENS,
    VALID_CREDENTIALS,
    _evict_previous_sessions_for_user,
    _get_client_ip,
    _verify_token,
)

router = APIRouter(prefix="/api/v1/auth", tags=["认证-L4.85"])

# 跟 L4.75 v2 lock_timeout_seconds 1:1 stable 配套
LOGIN_REQUEST_TIMEOUT_SECONDS = 300  # 5 分钟


@dataclass
class LoginRequestInfo:
    """L4.85 申请+同意 模式 单条申请记录."""

    request_id: str
    requester_ip: str
    target_username: str  # 申请登录的目标账号 (admin/fqsw)
    created_at: float
    status: str  # "pending" / "approved" / "rejected" / "expired"


# L4.85 状态: key=target_username, value=list of pending requests
# 跟 L4.75 v2 ACTIVE_SESSIONS + QUEUE 1:1 stable 配套
_PENDING_REQUESTS: dict[str, list[LoginRequestInfo]] = {}
_STATE_LOCK = threading.RLock()


# ─────────────────────────────────────────────────────────────
# Pydantic 模型
# ─────────────────────────────────────────────────────────────
class LoginRequestIn(BaseModel):
    username: str
    password: str


class LoginRequestOut(BaseModel):
    request_id: str
    status: str
    message: str


class PendingRequestItem(BaseModel):
    request_id: str
    requester_ip: str
    created_at: float
    status: str
    estimated_wait_seconds: int


class PendingRequestsOut(BaseModel):
    pending: list[PendingRequestItem]


class ApproveRequestOut(BaseModel):
    success: bool
    new_token: str
    username: str


class RejectRequestOut(BaseModel):
    success: bool


class StatusRequestOut(BaseModel):
    """L4.85.1 治本: B 端 polling 检测自己申请状态 (跟 NavBar.vue 1:1 stable 配套)."""

    request_id: str
    status: str  # "pending" / "approved" / "rejected" / "expired"
    new_token: str | None = None  # approved 时返回 (B 端 receive 后写入 sessionStorage)
    username: str | None = None


# ─────────────────────────────────────────────────────────────
# 辅助函数 (跟 L4.75 v2 + L4.84 1:1 stable 配套)
# ─────────────────────────────────────────────────────────────
def _get_current_username_from_token(request: Request) -> str:
    """跟 L4.84 1:1 stable 配套, 从 Authorization header 提取 username."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    token = auth[7:]
    username = _verify_token(token)
    if username is None:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return username


def _evict_expired_requests_locked(now: float) -> None:
    """跟 L4.75 v2 _drop_expired_queue_locked 1:1 stable 配套, 清理超时申请."""
    for username in list(_PENDING_REQUESTS.keys()):
        retained = []
        for r in _PENDING_REQUESTS.get(username, []):
            if r.status == "pending" and now - r.created_at >= LOGIN_REQUEST_TIMEOUT_SECONDS:
                r.status = "expired"
            if r.status == "pending":
                retained.append(r)
        if retained:
            _PENDING_REQUESTS[username] = retained
        else:
            _PENDING_REQUESTS.pop(username, None)


def _is_account_active(username: str) -> bool:
    """跟 L4.84 1:1 stable 配套, 检查账号是否有 active token."""
    return any(
        token_user == username
        for token_user, _ in ACTIVE_TOKENS.values()
    )


# ─────────────────────────────────────────────────────────────
# 4 endpoint (跟 L4.84 + L4.75 v2 1:1 stable 永久规则化沿用)
# ─────────────────────────────────────────────────────────────
@router.post("/login-request", response_model=LoginRequestOut)
def create_login_request(req: LoginRequestIn, request: Request):
    """L4.85 治本: B 申请登录 admin (admin 当前 active).

    流程 (跟 L4.42 立项实证 SOP 1:1 stable 配套):
    1. 验证密码 (跟 L4.84 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套)
    2. 检查账号是否 active (有 token)
    3. 如果不 active → 跟 L4.84 1:1 stable 配套, 返回 409 让 B 走 /login
    4. 如果 active → 创建申请 (pending)
    5. 已有 pending 申请 → 复用 (跟 L4.75 v2 active session 1:1 stable 配套)
    """
    client_ip = _get_client_ip(request)
    now = time.monotonic()

    # 1. 验证密码 (跟 L4.84 1:1 stable 永久规则化沿用)
    if req.username not in VALID_CREDENTIALS:
        raise HTTPException(status_code=401, detail="账号或密码错误")
    stored_hash = VALID_CREDENTIALS[req.username]
    if not bcrypt.checkpw(req.password.encode(), stored_hash.encode()):
        raise HTTPException(status_code=401, detail="账号或密码错误")

    with _STATE_LOCK:
        _evict_expired_requests_locked(now)

        # 2. 检查账号是否 active
        if not _is_account_active(req.username):
            # 不 active → 跟 L4.84 1:1 stable 配套, 让 B 走 /login
            raise HTTPException(
                status_code=409,
                detail="账号当前未激活, 请直接走 /api/v1/auth/login",
            )

        # 3. 已经有 pending 申请? 复用 (跟 L4.75 v2 active session 1:1 stable 配套)
        for existing in _PENDING_REQUESTS.get(req.username, []):
            if existing.status == "pending":
                return LoginRequestOut(
                    request_id=existing.request_id,
                    status="pending",
                    message="已有待处理申请, 请等待当前用户响应",
                )

        # 4. 创建新申请
        request_id = secrets.token_urlsafe(16)
        new_request = LoginRequestInfo(
            request_id=request_id,
            requester_ip=client_ip,
            target_username=req.username,
            created_at=now,
            status="pending",
        )
        _PENDING_REQUESTS.setdefault(req.username, []).append(new_request)
        # L4.85.1 治本: B 端鉴权用 _PENDING_REQUEST_TOKENS 记录 (跟 get_request_status 1:1 stable 永久规则化沿用)
        _PENDING_REQUEST_TOKENS[request_id] = req.username
        return LoginRequestOut(
            request_id=request_id,
            status="pending",
            message=f"账号 {req.username} 正在被使用, 已发送申请给当前用户",
        )


@router.get("/login-requests/pending", response_model=PendingRequestsOut)
def get_pending_requests(request: Request):
    """A 查待处理申请 (A 必须是 active 用户, 跟 L4.84 1:1 stable 配套)."""
    current_username = _get_current_username_from_token(request)
    now = time.monotonic()

    with _STATE_LOCK:
        _evict_expired_requests_locked(now)
        pending = _PENDING_REQUESTS.get(current_username, [])
        return PendingRequestsOut(
            pending=[
                PendingRequestItem(
                    request_id=r.request_id,
                    requester_ip=r.requester_ip,
                    created_at=r.created_at,
                    status=r.status,
                    estimated_wait_seconds=max(
                        0, LOGIN_REQUEST_TIMEOUT_SECONDS - int(now - r.created_at)
                    ),
                )
                for r in pending
                if r.status == "pending"
            ]
        )


@router.post("/login-request/{request_id}/approve", response_model=ApproveRequestOut)
def approve_login_request(request_id: str, request: Request):
    """A 同意 B 的申请 → A 登出, B 登录 (跟 L4.84 _evict_previous_sessions_for_user 1:1 stable 复用)."""
    current_username = _get_current_username_from_token(request)
    now = time.monotonic()

    with _STATE_LOCK:
        _evict_expired_requests_locked(now)

        # 1. 找 request
        pending = _PENDING_REQUESTS.get(current_username, [])
        target = None
        for r in pending:
            if r.request_id == request_id and r.status == "pending":
                target = r
                break
        if target is None:
            raise HTTPException(status_code=404, detail="申请不存在或已处理")

        # 2. 标记 approved + A 登出 (跟 L4.84 _evict_previous_sessions_for_user 1:1 stable 复用)
        target.status = "approved"
        _evict_previous_sessions_for_user(current_username)

        # 3. 给 B 发新 token (跟 L4.84 login() 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套)
        new_token = secrets.token_urlsafe(32)
        ACTIVE_TOKENS[new_token] = (current_username, datetime.now())

        return ApproveRequestOut(
            success=True,
            new_token=new_token,
            username=current_username,
        )


@router.post("/login-request/{request_id}/reject", response_model=RejectRequestOut)
def reject_login_request(request_id: str, request: Request):
    """A 拒绝 B 的申请 (跟 L4.84 1:1 stable 永久规则化沿用, A 不受影响)."""
    current_username = _get_current_username_from_token(request)
    now = time.monotonic()

    with _STATE_LOCK:
        _evict_expired_requests_locked(now)

        pending = _PENDING_REQUESTS.get(current_username, [])
        target = None
        for r in pending:
            if r.request_id == request_id and r.status == "pending":
                target = r
                break
        if target is None:
            raise HTTPException(status_code=404, detail="申请不存在或已处理")

        target.status = "rejected"
        return RejectRequestOut(success=True)


# === L4.85.1 治本: B 端 polling 检测自己申请状态 (跟 plan-eng-review 1:1 stable 永久规则化沿用) ===
# B 端用 request_id + username 鉴权 (B 端没 token, 用 request 创建时的 username)
# 简化方案: B 端发送申请时返回 request_id, B 端轮询此 endpoint
# 实际安全: 加 _pending_request_tokens dict, B 端发送申请时返回 token, B 端轮询时验证
# 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套: 复用 _PENDING_REQUESTS + request_id 作为 B 端鉴权
_PENDING_REQUEST_TOKENS: dict[str, str] = {}  # key=request_id, value=requester_username (B 端鉴权用)


@router.get("/login-request/{request_id}/status", response_model=StatusRequestOut)
def get_request_status(request_id: str, request: Request):
    """L4.85.1 治本: B 端 polling 检测自己申请状态 (跟 NavBar.vue B 端自动跳 1:1 stable 永久规则化沿用).

    流程 (跟 L4.42 立项实证 SOP 1:1 stable 配套, 跟 plan-eng-review 5 维分析 1:1 stable 永久规则化沿用):
    1. B 端发送申请 → 返回 request_id + _PENDING_REQUEST_TOKENS[request_id] = username
    2. B 端 polling 此 endpoint, 用 _PENDING_REQUEST_TOKENS[request_id] 鉴权 (B 端 username 在创建时已记录)
    3. 如果 status == "approved", 返回 new_token (跟 L4.84 _evict_previous_sessions_for_user 1:1 stable 复用, 后端 manage)
    4. B 端 receive new_token → 写入 sessionStorage + router.push('/audience')
    """
    now = time.monotonic()

    with _STATE_LOCK:
        # L4.85.1 治本: status endpoint 不调 _evict_expired_requests_locked (status 只读, 避免把 approved/rejected 的请求也清掉)
        # 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套

        # 用 _PENDING_REQUEST_TOKENS[request_id] 找 B 端 username
        requester_username = _PENDING_REQUEST_TOKENS.get(request_id)
        if requester_username is None:
            raise HTTPException(status_code=404, detail="申请不存在或已过期")

        # 找 request
        pending = _PENDING_REQUESTS.get(requester_username, [])
        target = None
        for r in pending:
            if r.request_id == request_id:
                target = r
                break
        if target is None:
            raise HTTPException(status_code=404, detail="申请不存在或已处理")

        if target.status == "approved":
            # approved 时 generate new_token (跟 approve_login_request 1:1 stable 复用)
            new_token = secrets.token_urlsafe(32)
            ACTIVE_TOKENS[new_token] = (target.target_username, datetime.now())
            # 清理 _PENDING_REQUEST_TOKENS (B 端 receive 后不需要)
            _PENDING_REQUEST_TOKENS.pop(request_id, None)
            return StatusRequestOut(
                request_id=request_id,
                status="approved",
                new_token=new_token,
                username=target.target_username,
            )
        elif target.status == "rejected":
            _PENDING_REQUEST_TOKENS.pop(request_id, None)
            return StatusRequestOut(
                request_id=request_id,
                status="rejected",
            )
        elif target.status == "expired":
            _PENDING_REQUEST_TOKENS.pop(request_id, None)
            return StatusRequestOut(
                request_id=request_id,
                status="expired",
            )
        else:
            # pending
            return StatusRequestOut(
                request_id=request_id,
                status="pending",
            )


# 测试用 reset (跟 L4.50 + L4.65.1 + L4.69.1 + L4.72 + L4.75 v2 1:1 stable 永久规则化沿用)
def _reset_l4_85_state() -> None:
    """Clear L4.85 申请+同意 state for deterministic regression tests."""
    with _STATE_LOCK:
        _PENDING_REQUESTS.clear()
