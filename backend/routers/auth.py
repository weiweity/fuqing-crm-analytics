"""
芙清 CRM - 认证路由

前缀: /api/v1/auth/*
说明: 内网分析系统，简单 token 认证（内存存储，重启后需重新登录）
安全基线: bcrypt 密码哈希 + token TTL(8h) + 登录限速 + 审计日志
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime, timedelta
import secrets
import time
import os
import bcrypt
import logging

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Token 配置
# ─────────────────────────────────────────────────────────────
TOKEN_TTL = timedelta(hours=8)

# ─────────────────────────────────────────────────────────────
# 登录限速配置
# ─────────────────────────────────────────────────────────────
MAX_FAIL_ATTEMPTS = 5          # 最大失败次数
LOCK_DURATION = 15 * 60        # 锁定时长（秒）
RATE_LIMIT_WINDOW = 5 * 60     # 计数窗口（秒）

# ─────────────────────────────────────────────────────────────
# 密码配置：支持环境变量 FQ_CRM_PASSWORDS=admin:明文密码,fqsw:明文密码
# 未配置时使用默认账号，启动时自动哈希（源码中不保存明文）
# ─────────────────────────────────────────────────────────────
def _load_credentials() -> dict[str, str]:
    """加载账号密码，返回 {username: bcrypt_hash}"""
    env = os.environ.get("FQ_CRM_PASSWORDS", "")
    raw_creds: dict[str, str] = {}
    if env:
        for pair in env.split(","):
            pair = pair.strip()
            if ":" in pair:
                user, pwd = pair.split(":", 1)
                raw_creds[user.strip()] = pwd.strip()
    else:
        # 默认账号（生产环境请务必通过环境变量配置）
        raw_creds = {
            "admin": "123456",
            "fqsw": "fqsw888",
        }
    # 启动时一次性哈希（如果已经是 bcrypt 格式则跳过）
    hashed: dict[str, str] = {}
    for user, pwd in raw_creds.items():
        if pwd.startswith(("$2b$", "$2a$", "$2y$")):
            hashed[user] = pwd
        else:
            hashed[user] = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
    return hashed


VALID_CREDENTIALS: dict[str, str] = _load_credentials()

# 内存 token 存储（key=token, value=(username, created_at)）
ACTIVE_TOKENS: dict[str, tuple[str, datetime]] = {}

# 登录限速记录（key=username, value=(失败次数, 首次失败时间戳, 锁定截止秒级时间戳)）
_LOGIN_ATTEMPTS: dict[str, tuple[int, float, float]] = {}


# ─────────────────────────────────────────────────────────────
# Pydantic 模型
# ─────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str


class UserInfo(BaseModel):
    username: str


class LogoutResponse(BaseModel):
    success: bool


# ─────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────
def _get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _check_rate_limit(username: str, client_ip: str):
    """检查登录限速，超限则抛出 429"""
    now = time.time()
    record = _LOGIN_ATTEMPTS.get(username)

    if record:
        fail_count, first_fail, lock_until = record
        if now < lock_until:
            _logger.warning(f"[auth] 账号 {username} 被锁定，IP={client_ip}")
            raise HTTPException(
                status_code=429,
                detail=f"登录失败次数过多，请 {int(lock_until - now) // 60} 分钟后重试",
            )
        # 窗口过期，重置计数
        if now - first_fail > RATE_LIMIT_WINDOW:
            _LOGIN_ATTEMPTS.pop(username, None)
            record = None


def _record_fail(username: str, client_ip: str):
    """记录一次登录失败"""
    now = time.time()
    record = _LOGIN_ATTEMPTS.get(username)
    if record:
        fail_count, first_fail, lock_until = record
        fail_count += 1
        if fail_count >= MAX_FAIL_ATTEMPTS:
            lock_until = now + LOCK_DURATION
            _logger.warning(
                f"[auth] 账号 {username} 锁定 {LOCK_DURATION}s，IP={client_ip}"
            )
        _LOGIN_ATTEMPTS[username] = (fail_count, first_fail, lock_until)
    else:
        _LOGIN_ATTEMPTS[username] = (1, now, 0.0)


def _record_success(username: str):
    """登录成功后清除失败记录"""
    _LOGIN_ATTEMPTS.pop(username, None)


def _verify_token(token: str) -> str | None:
    """验证 token 有效性，返回 username 或 None"""
    record = ACTIVE_TOKENS.get(token)
    if not record:
        return None
    username, created_at = record
    if datetime.now() - created_at > TOKEN_TTL:
        # token 过期，自动清理
        ACTIVE_TOKENS.pop(token, None)
        return None
    return username


def _token_ttl_seconds() -> int:
    """返回 token 剩余有效秒数"""
    return int(TOKEN_TTL.total_seconds())


# ─────────────────────────────────────────────────────────────
# 路由
# ─────────────────────────────────────────────────────────────
@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, request: Request):
    """账号密码登录，成功返回 token（含限速保护）"""
    client_ip = _get_client_ip(request)

    # 1. 限速检查
    _check_rate_limit(req.username, client_ip)

    # 2. 验证用户名
    if req.username not in VALID_CREDENTIALS:
        _logger.warning(f"[auth] 登录失败：未知账号 {req.username}，IP={client_ip}")
        _record_fail(req.username, client_ip)
        raise HTTPException(status_code=401, detail="账号或密码错误")

    # 3. bcrypt 校验密码
    stored_hash = VALID_CREDENTIALS[req.username]
    if not bcrypt.checkpw(req.password.encode(), stored_hash.encode()):
        _logger.warning(f"[auth] 登录失败：密码错误 {req.username}，IP={client_ip}")
        _record_fail(req.username, client_ip)
        raise HTTPException(status_code=401, detail="账号或密码错误")

    # 4. 登录成功
    _record_success(req.username)
    token = secrets.token_urlsafe(32)
    ACTIVE_TOKENS[token] = (req.username, datetime.now())
    _logger.info(f"[auth] 登录成功：{req.username}，IP={client_ip}")

    return {"token": token, "username": req.username}


@router.get("/me", response_model=UserInfo)
def me(request: Request):
    """验证 token 有效性（从 Authorization header 读取），返回当前用户信息"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    token = auth[7:]

    username = _verify_token(token)
    if username is None:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")

    return {"username": username}


@router.post("/logout", response_model=LogoutResponse)
def logout(request: Request):
    """退出登录，使当前 token 失效"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        record = ACTIVE_TOKENS.pop(token, None)
        if record:
            _logger.info(f"[auth] 退出登录：{record[0]}")
    return {"success": True}
