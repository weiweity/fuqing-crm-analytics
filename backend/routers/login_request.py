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

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

# 复用 auth.py 现有函数 (跟 L4.84 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套)
from backend.routers.auth import (
    ACTIVE_TOKENS,
    _AUTH_STATE_LOCK,
    _authenticate_credentials,
    _evict_previous_sessions_for_user,
    _get_client_ip,
    _is_account_active,
    _verify_token,
    is_admin_username,
)

router = APIRouter(prefix="/api/v1/auth", tags=["认证-L4.85"])

# 跟 L4.75 v2 lock_timeout_seconds 1:1 stable 配套
# user 7/11 拍板 "5 分钟时间太长了，可以 3 分钟", 5min → 3min 全栈统一
LOGIN_REQUEST_TIMEOUT_SECONDS = 180  # 3 分钟 (跟 auth.py _is_account_active 3min + NavBar IDLE_TIMEOUT_MS 3min 1:1 stable)


@dataclass
class LoginRequestInfo:
    """L4.85 申请+同意 模式 单条申请记录."""

    request_id: str
    requester_ip: str
    target_username: str  # 申请登录的目标账号 (admin/fqsw)
    created_at: float
    status: str  # "pending" / "approved" / "rejected" / "expired"
    claim_secret_digest: bytes
    resolved_at: float | None = None
    approved_token: str | None = None


# L4.85 状态: key=target_username, value=list of pending requests
# 跟 L4.75 v2 ACTIVE_SESSIONS + QUEUE 1:1 stable 配套
_PENDING_REQUESTS: dict[str, list[LoginRequestInfo]] = {}
# request_id 只用于关联；B 端必须另带 claim secret 才能查询或领取。
_PENDING_REQUEST_OWNERS: dict[str, str] = {}
_STATE_LOCK = threading.RLock()


# ─────────────────────────────────────────────────────────────
# Pydantic 模型
# ─────────────────────────────────────────────────────────────
class LoginRequestIn(BaseModel):
    username: str
    password: str


class LoginRequestOut(BaseModel):
    request_id: str
    claim_token: str
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
    username: str


class RejectRequestOut(BaseModel):
    success: bool


class StatusRequestOut(BaseModel):
    """L4.85.1 治本: B 端 polling 检测自己申请状态 (跟 NavBar.vue 1:1 stable 配套)."""

    request_id: str
    status: str  # "pending" / "approved" / "rejected" / "expired"
    username: str | None = None


class ClaimRequestOut(BaseModel):
    token: str
    username: str
    is_admin: bool = False


# ─────────────────────────────────────────────────────────────
# 辅助函数 (跟 L4.75 v2 + L4.84 1:1 stable 配套)
# ─────────────────────────────────────────────────────────────
def _get_current_username_from_token(request: Request, sliding: bool = True) -> str:
    """跟 L4.84 1:1 stable 配套, 从 Authorization header 提取 username.

    sliding=False 时不刷新 last_active_at (read-only check, 跟 L4.85.4 1:1 stable 永久规则化沿用).
    polling / status 等 read-only endpoint 必传 sliding=False, 避免用户离开工位后 polling 持续续期
    → _is_account_active 永远 True → B 端 login 409 卡申请登录.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    token = auth[7:]
    username = _verify_token(token, sliding=sliding)
    if username is None:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return username


def _claim_secret_digest(claim_secret: str) -> bytes:
    return hashlib.sha256(claim_secret.encode()).digest()


def _claim_secret_from_request(request: Request) -> str:
    claim_secret = request.headers.get("X-Login-Claim", "")
    if not claim_secret or len(claim_secret) > 256:
        raise HTTPException(status_code=404, detail="申请不存在或已过期")
    return claim_secret


def _find_claim_request_locked(request_id: str, request: Request) -> LoginRequestInfo:
    owner = _PENDING_REQUEST_OWNERS.get(request_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="申请不存在或已过期")
    target = next(
        (item for item in _PENDING_REQUESTS.get(owner, []) if item.request_id == request_id),
        None,
    )
    if target is None:
        raise HTTPException(status_code=404, detail="申请不存在或已过期")
    supplied = _claim_secret_digest(_claim_secret_from_request(request))
    if not secrets.compare_digest(supplied, target.claim_secret_digest):
        raise HTTPException(status_code=404, detail="申请不存在或已过期")
    return target


def _evict_expired_requests_locked(now: float) -> None:
    """跟 L4.75 v2 _drop_expired_queue_locked 1:1 stable 配套, 清理超时申请."""
    for username in list(_PENDING_REQUESTS.keys()):
        retained: list[LoginRequestInfo] = []
        for r in _PENDING_REQUESTS.get(username, []):
            if r.status == "pending" and now - r.created_at >= LOGIN_REQUEST_TIMEOUT_SECONDS:
                r.status = "expired"
                r.resolved_at = now
            terminal_expired = (
                r.resolved_at is not None
                and now - r.resolved_at >= LOGIN_REQUEST_TIMEOUT_SECONDS
            )
            if terminal_expired:
                _PENDING_REQUEST_OWNERS.pop(r.request_id, None)
                continue
            retained.append(r)
        if retained:
            _PENDING_REQUESTS[username] = retained
        else:
            _PENDING_REQUESTS.pop(username, None)

# ─────────────────────────────────────────────────────────────
# 6 endpoints (create/pending/approve/reject/status/claim)
# ─────────────────────────────────────────────────────────────
@router.post("/login-request", response_model=LoginRequestOut)
def create_login_request(req: LoginRequestIn, request: Request, response: Response):
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

    # 跟普通 login 共用账号级失败计数和 15 分钟锁定，禁止弱验证旁路。
    _authenticate_credentials(req.username, req.password, client_ip)

    with _STATE_LOCK:
        _evict_expired_requests_locked(now)

        # 2. 检查账号是否 active
        if not _is_account_active(req.username):
            # 不 active → 跟 L4.84 1:1 stable 配套, 让 B 走 /login
            raise HTTPException(
                status_code=409,
                detail="账号当前未激活, 请直接走 /api/v1/auth/login",
            )

        claim_secret = secrets.token_urlsafe(32)
        claim_digest = _claim_secret_digest(claim_secret)

        # 同一 IP 重试时轮换 claim secret 并复用申请，避免重复弹窗。
        for existing in _PENDING_REQUESTS.get(req.username, []):
            if existing.status == "pending" and existing.requester_ip == client_ip:
                existing.claim_secret_digest = claim_digest
                # 新 claim secret 等同一次新的申请凭据；同步刷新服务端 TTL，
                # 与 B 端重新显示的 180 秒倒计时保持一致 (跟 LOGIN_REQUEST_TIMEOUT_SECONDS=180 1:1 stable)。
                existing.created_at = now
                response.headers["Cache-Control"] = "no-store"
                return LoginRequestOut(
                    request_id=existing.request_id,
                    claim_token=claim_secret,
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
            claim_secret_digest=claim_digest,
        )
        _PENDING_REQUESTS.setdefault(req.username, []).append(new_request)
        _PENDING_REQUEST_OWNERS[request_id] = req.username
        response.headers["Cache-Control"] = "no-store"
        return LoginRequestOut(
            request_id=request_id,
            claim_token=claim_secret,
            status="pending",
            message=f"账号 {req.username} 正在被使用, 已发送申请给当前用户",
        )


@router.get("/login-requests/pending", response_model=PendingRequestsOut)
def get_pending_requests(request: Request):
    """A 查待处理申请 (A 必须是 active 用户, 跟 L4.84 1:1 stable 配套).

    L4.85.4 治本: sliding=False, read-only check 不刷新 last_active_at.
    修复 user 7/11 报"我离开工位 polling 仍跑" → _is_account_active 永远 True → B 端 login 409.
    跟 L4.85.4 + L4.85.3 1:1 stable 永久规则化沿用.
    """
    current_username = _get_current_username_from_token(request, sliding=False)
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
        target.resolved_at = now
        _evict_previous_sessions_for_user(current_username)

        return ApproveRequestOut(
            success=True,
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
        target.resolved_at = now
        return RejectRequestOut(success=True)


@router.get("/login-request/{request_id}/status", response_model=StatusRequestOut)
def get_request_status(request_id: str, request: Request):
    """B 用独占 claim secret 幂等查询状态；GET 不创建或领取会话。"""
    now = time.monotonic()
    with _STATE_LOCK:
        _evict_expired_requests_locked(now)
        target = _find_claim_request_locked(request_id, request)
        return StatusRequestOut(
            request_id=request_id,
            status=target.status,
            username=target.target_username if target.status == "approved" else None,
        )


@router.post("/login-request/{request_id}/claim", response_model=ClaimRequestOut)
def claim_login_request(request_id: str, request: Request, response: Response):
    """B 原子领取批准后的会话；相同 claim 可安全重试并拿到同一 token。"""
    now = time.monotonic()
    with _STATE_LOCK:
        _evict_expired_requests_locked(now)
        target = _find_claim_request_locked(request_id, request)
        if target.status == "pending":
            raise HTTPException(status_code=409, detail="申请仍在等待处理")
        if target.status == "rejected":
            raise HTTPException(status_code=409, detail="申请已被拒绝")
        if target.status == "expired":
            raise HTTPException(status_code=410, detail="申请已过期, 请重新申请")

        with _AUTH_STATE_LOCK:
            if target.approved_token is not None:
                if target.approved_token not in ACTIVE_TOKENS:
                    raise HTTPException(status_code=410, detail="登录授权已失效, 请重新申请")
                token = target.approved_token
            else:
                _evict_previous_sessions_for_user(target.target_username)
                token = secrets.token_urlsafe(32)
                target.approved_token = token
                # 给首次领取后的丢包重试保留完整 claim TTL。
                target.resolved_at = now
                ACTIVE_TOKENS[token] = (target.target_username, datetime.now())

        response.headers["Cache-Control"] = "no-store"
        return ClaimRequestOut(
            token=token,
            username=target.target_username,
            is_admin=is_admin_username(target.target_username),
        )


# 测试用 reset (跟 L4.50 + L4.65.1 + L4.69.1 + L4.72 + L4.75 v2 1:1 stable 永久规则化沿用)
def _reset_l4_85_state() -> None:
    """Clear L4.85 申请+同意 state for deterministic regression tests."""
    with _STATE_LOCK:
        _PENDING_REQUESTS.clear()
        _PENDING_REQUEST_OWNERS.clear()
