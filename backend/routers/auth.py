"""
Sample CRM - 认证路由

前缀: /api/v1/auth/*
说明: 内网分析系统，简单 token 认证（内存存储，重启后需重新登录）
安全基线: bcrypt 密码哈希 + token TTL(8h) + 登录限速 + 审计日志
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timedelta
from collections import OrderedDict
import re
import secrets
import time
import os
import logging
import threading
import bcrypt

# 确保 .env 已加载（auth.py 可能在其他模块之前被导入）
from dotenv import load_dotenv
load_dotenv()

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Token 配置
# ─────────────────────────────────────────────────────────────
TOKEN_TTL = timedelta(hours=8)

# ─────────────────────────────────────────────────────────────
# 登录限速配置
# - 账号+IP 组合锁定：防止不同 IP 洪泛锁死真实账号
# - per-IP 总限流：限制单 IP 对任意用户名的爆破
# - 有界 OrderedDict + 周期清理：随机用户名洪泛时状态表容量受控
# ─────────────────────────────────────────────────────────────
MAX_FAIL_ATTEMPTS = 5          # 账号+IP 组合最大失败次数
LOCK_DURATION = 15 * 60        # 组合锁定时长（秒）
RATE_LIMIT_WINDOW = 5 * 60     # 计数窗口（秒）
MAX_IP_FAIL_ATTEMPTS = 30      # 单 IP 总失败次数（窗口内）
IP_LOCK_DURATION = 15 * 60     # 单 IP 锁定时长（秒）
LOGIN_STATE_MAX_ENTRIES = 4096 # 每张状态表最大条目（LRU 淘汰）
LOGIN_STATE_CLEANUP_INTERVAL = 60.0  # 周期清理最小间隔（秒）
BCRYPT_MAX_PASSWORD_BYTES = 72
USERNAME_MAX_LEN = 64
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.@-]+$")
# 未知账号也走 bcrypt，抹平时序；固定盐哈希，避免每次 gensalt 开销差异过大。
# cost 必须与真实密码 hash 一致（bcrypt.gensalt() 默认 rounds=12），
# 禁止 rounds=4 等低 cost——否则未知账号 checkpw 明显更快，可被时序枚举。
_DUMMY_BCRYPT_HASH: bytes = bcrypt.hashpw(b"__fq_crm_dummy__", bcrypt.gensalt())

# ─────────────────────────────────────────────────────────────
# 密码配置
#
# 1. 如果设置了 FQ_CRM_PASSWORDS 环境变量：使用指定的账号密码
#    格式: FQ_CRM_PASSWORDS=admin:密码1,fqsw:密码2
# 2. 如果未设置：自动随机生成强密码，打印到控制台
#    用户看到后可以复制到环境变量中固定下来
# ─────────────────────────────────────────────────────────────
def _load_credentials() -> dict[str, str]:
    """加载账号密码，返回 {username: bcrypt_hash}。未配置时随机生成。"""
    env = os.environ.get("FQ_CRM_PASSWORDS", "")

    if env and env.strip():
        raw_creds: dict[str, str] = {}
        for pair in env.split(","):
            pair = pair.strip()
            if ":" in pair:
                user, pwd = pair.split(":", 1)
                raw_creds[user.strip()] = pwd.strip()
        if not raw_creds:
            raise RuntimeError(
                "FQ_CRM_PASSWORDS 已设置但未解析到有效凭据，请检查格式。"
            )
    else:
        # 未配置：自动生成随机强密码
        raw_creds = {
            "admin": secrets.token_urlsafe(12),
            "fqsw": secrets.token_urlsafe(12),
        }
        print("\n" + "=" * 60)
        print("  ⚠️  FQ_CRM_PASSWORDS 未配置，已自动生成随机密码：")
        print()
        print(f"  账号: admin    密码: {raw_creds['admin']}")
        print(f"  账号: fqsw     密码: {raw_creds['fqsw']}")
        print()
        print("  如需固定密码，请在 .env 文件中添加：")
        print(f"  FQ_CRM_PASSWORDS=admin:{raw_creds['admin']},fqsw:{raw_creds['fqsw']}")
        print("=" * 60 + "\n")

    # 启动时一次性哈希（如果已经是 bcrypt 格式则跳过）
    hashed: dict[str, str] = {}
    for user, pwd in raw_creds.items():
        if pwd.startswith(("$2b$", "$2a$", "$2y$")):
            hashed[user] = pwd
        else:
            hashed[user] = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
    return hashed


VALID_CREDENTIALS: dict[str, str] = _load_credentials()

# 内存 token 存储（key=token, value=(username, last_active_at)）
# last_active_at 用于滑动过期：每次请求成功会刷新这个时间
ACTIVE_TOKENS: dict[str, tuple[str, datetime]] = {}

# 登录限速：key = "username\\0ip"，value=(失败次数, 首次失败时间戳, 锁定截止)
# 名称保留 _LOGIN_ATTEMPTS 以兼容 conftest / test_helpers 的 .clear()
_LOGIN_ATTEMPTS: OrderedDict[str, tuple[int, float, float]] = OrderedDict()
# per-IP 总限流（不按账号）
_IP_LOGIN_ATTEMPTS: OrderedDict[str, tuple[int, float, float]] = OrderedDict()
_last_login_state_cleanup: float = 0.0
# FastAPI sync endpoints run in a worker pool.  Account lockout updates and the
# single-session check/evict/mint sequence must be atomic across those workers.
_AUTH_STATE_LOCK = threading.RLock()


# ─────────────────────────────────────────────────────────────
# Pydantic 模型
# ─────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=USERNAME_MAX_LEN)
    password: str = Field(..., min_length=1, max_length=1024)

    @field_validator("username")
    @classmethod
    def _username_charset(cls, v: str) -> str:
        if not USERNAME_PATTERN.fullmatch(v):
            raise ValueError("username contains invalid characters")
        return v


class LoginResponse(BaseModel):
    token: str
    username: str
    is_admin: bool = False


class UserInfo(BaseModel):
    username: str
    is_admin: bool = False


class LogoutResponse(BaseModel):
    success: bool


# ─────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────
def _safe_log_username(username: str) -> str:
    """截断、去换行，避免日志注入/超长用户名污染。"""
    if not username:
        return ""
    cleaned = username.replace("\n", "").replace("\r", "").replace("\t", " ")
    if len(cleaned) > USERNAME_MAX_LEN:
        cleaned = cleaned[:USERNAME_MAX_LEN] + "…"
    return cleaned


def _get_client_ip(request: Request) -> str:
    """提取客户端 IP。

    默认只用 ASGI client host。不可信 X-Forwarded-For 不当作 client IP。
    仅当 FQ_TRUST_PROXY=1（可信反代模式）时才读取 X-Forwarded-For 首跳。
    """
    if os.environ.get("FQ_TRUST_PROXY") == "1":
        xff = request.headers.get("X-Forwarded-For") or request.headers.get(
            "x-forwarded-for"
        )
        if xff:
            first = xff.split(",")[0].strip()
            first = first.replace("\n", "").replace("\r", "")[:64]
            if first:
                return first
    return request.client.host if request.client else "unknown"


def _combo_key(username: str, client_ip: str) -> str:
    return f"{username}\0{client_ip}"


def _lru_set(
    store: OrderedDict[str, tuple[int, float, float]],
    key: str,
    value: tuple[int, float, float],
    max_entries: int | None = None,
) -> None:
    # 运行时读 LOGIN_STATE_MAX_ENTRIES，便于测试 monkeypatch 与热调容量
    limit = LOGIN_STATE_MAX_ENTRIES if max_entries is None else max_entries
    if key in store:
        store.move_to_end(key)
    store[key] = value
    while len(store) > limit:
        store.popitem(last=False)


def _cleanup_login_state_locked(now: float, force: bool = False) -> None:
    """清理过期锁定/窗口记录，控制状态表膨胀。调用方须持有 _AUTH_STATE_LOCK。"""
    global _last_login_state_cleanup
    if not force and (now - _last_login_state_cleanup) < LOGIN_STATE_CLEANUP_INTERVAL:
        return
    _last_login_state_cleanup = now

    def _purge(store: OrderedDict[str, tuple[int, float, float]]) -> None:
        stale: list[str] = []
        for key, (_fail_count, first_fail, lock_until) in store.items():
            if now < lock_until:
                continue
            if now - first_fail > RATE_LIMIT_WINDOW and lock_until <= now:
                stale.append(key)
        for key in stale:
            store.pop(key, None)

    _purge(_LOGIN_ATTEMPTS)
    _purge(_IP_LOGIN_ATTEMPTS)


def _check_rate_limit(username: str, client_ip: str):
    """检查登录限速（IP 总限流 + 账号+IP 组合），超限则抛出 429。"""
    now = time.time()
    _cleanup_login_state_locked(now)

    ip_rec = _IP_LOGIN_ATTEMPTS.get(client_ip)
    if ip_rec:
        _fail_count, first_fail, lock_until = ip_rec
        if now < lock_until:
            _logger.warning(
                "login_rate_limited",
                extra={
                    "event": "login_rate_limited",
                    "scope": "ip",
                    "username": _safe_log_username(username),
                    "client_ip": client_ip,
                },
            )
            raise HTTPException(
                status_code=429,
                detail=(
                    f"登录失败次数过多，请 "
                    f"{max(1, int(lock_until - now) // 60)} 分钟后重试"
                ),
            )
        if now - first_fail > RATE_LIMIT_WINDOW:
            _IP_LOGIN_ATTEMPTS.pop(client_ip, None)

    key = _combo_key(username, client_ip)
    record = _LOGIN_ATTEMPTS.get(key)
    if record:
        _fail_count, first_fail, lock_until = record
        if now < lock_until:
            _logger.warning(
                "login_rate_limited",
                extra={
                    "event": "login_rate_limited",
                    "scope": "combo",
                    "username": _safe_log_username(username),
                    "client_ip": client_ip,
                },
            )
            raise HTTPException(
                status_code=429,
                detail=(
                    f"登录失败次数过多，请 "
                    f"{max(1, int(lock_until - now) // 60)} 分钟后重试"
                ),
            )
        if now - first_fail > RATE_LIMIT_WINDOW:
            _LOGIN_ATTEMPTS.pop(key, None)


def _record_fail(username: str, client_ip: str):
    """记录一次登录失败（账号+IP 组合 + per-IP）。"""
    now = time.time()
    key = _combo_key(username, client_ip)

    record = _LOGIN_ATTEMPTS.get(key)
    if record:
        fail_count, first_fail, lock_until = record
        if now - first_fail > RATE_LIMIT_WINDOW and now >= lock_until:
            fail_count, first_fail, lock_until = 0, now, 0.0
        fail_count += 1
        if fail_count >= MAX_FAIL_ATTEMPTS:
            lock_until = now + LOCK_DURATION
            _logger.warning(
                "login_locked",
                extra={
                    "event": "login_locked",
                    "scope": "combo",
                    "username": _safe_log_username(username),
                    "client_ip": client_ip,
                    "lock_seconds": LOCK_DURATION,
                },
            )
        _lru_set(_LOGIN_ATTEMPTS, key, (fail_count, first_fail, lock_until))
    else:
        _lru_set(_LOGIN_ATTEMPTS, key, (1, now, 0.0))

    ip_rec = _IP_LOGIN_ATTEMPTS.get(client_ip)
    if ip_rec:
        ip_count, ip_first, ip_lock = ip_rec
        if now - ip_first > RATE_LIMIT_WINDOW and now >= ip_lock:
            ip_count, ip_first, ip_lock = 0, now, 0.0
        ip_count += 1
        if ip_count >= MAX_IP_FAIL_ATTEMPTS:
            ip_lock = now + IP_LOCK_DURATION
            _logger.warning(
                "login_locked",
                extra={
                    "event": "login_locked",
                    "scope": "ip",
                    "username": _safe_log_username(username),
                    "client_ip": client_ip,
                    "lock_seconds": IP_LOCK_DURATION,
                },
            )
        _lru_set(_IP_LOGIN_ATTEMPTS, client_ip, (ip_count, ip_first, ip_lock))
    else:
        _lru_set(_IP_LOGIN_ATTEMPTS, client_ip, (1, now, 0.0))


def _record_success(username: str, client_ip: str = ""):
    """登录成功后清除该账号+IP 组合失败记录（不连坐其他 IP）。"""
    if client_ip:
        _LOGIN_ATTEMPTS.pop(_combo_key(username, client_ip), None)
    else:
        prefix = username + "\0"
        for key in [k for k in _LOGIN_ATTEMPTS if k.startswith(prefix)]:
            _LOGIN_ATTEMPTS.pop(key, None)


def _password_to_bytes(password: str) -> bytes | None:
    """UTF-8 编码密码；超过 bcrypt 72 字节返回 None（调用方统一当失败）。"""
    try:
        raw = password.encode("utf-8")
    except UnicodeEncodeError:
        return None
    if len(raw) > BCRYPT_MAX_PASSWORD_BYTES:
        return None
    return raw


def _checkpw_safe(password_bytes: bytes | None, stored_hash: str | None) -> bool:
    """bcrypt.checkpw 包装：捕获 ValueError；未知账号用 dummy hash 抹平时序。"""
    target = stored_hash.encode("utf-8") if stored_hash else _DUMMY_BCRYPT_HASH
    try:
        if password_bytes is None:
            bcrypt.checkpw(b"x" * BCRYPT_MAX_PASSWORD_BYTES, target)
            return False
        return bool(bcrypt.checkpw(password_bytes, target))
    except (ValueError, TypeError):
        return False


def _authenticate_credentials(username: str, password: str, client_ip: str) -> None:
    """共享登录校验：限流 + 凭据验证。已知/未知账号统一 401，不泄露存在性。"""
    if (
        not username
        or len(username) > USERNAME_MAX_LEN
        or not USERNAME_PATTERN.fullmatch(username)
    ):
        raise HTTPException(status_code=401, detail="账号或密码错误")

    with _AUTH_STATE_LOCK:
        _check_rate_limit(username, client_ip)
        stored_hash = VALID_CREDENTIALS.get(username)
        password_bytes = _password_to_bytes(password)
        ok = _checkpw_safe(password_bytes, stored_hash)
        if not ok:
            _logger.warning(
                "login_failed",
                extra={
                    "event": "login_failed",
                    "username": _safe_log_username(username),
                    "client_ip": client_ip,
                    "reason": "invalid_credentials",
                },
            )
            _record_fail(username, client_ip)
            raise HTTPException(status_code=401, detail="账号或密码错误")
        _record_success(username, client_ip)


def _evict_previous_sessions_for_user(username: str) -> int:
    """L4.84 治本: 同账号踢人, 同一账号同时只能 1 个活跃会话.

    遍历 ACTIVE_TOKENS, 删除所有 username 匹配的 token, 强制旧设备重新登录.
    跟 L4.75 v2 IP 排队互补不冲突: L4.75 v2 处理 RFM 路径按 IP 排队,
    L4.84 处理登录路径按账号踢人 (跟 L4.42 + L4.50 + L4.55 + L4.65.1 + L4.69 +
    L4.69.1 + L4.75 1:1 stable 永久规则链配套, 0 业务代码改动累计 Sprint 60+ 55+ 次 1:1 stable 永久规则化沿用).

    Returns: 被踢出的旧 token 数量.
    """
    evicted = 0
    with _AUTH_STATE_LOCK:
        for token, (token_user, _) in list(ACTIVE_TOKENS.items()):
            if token_user == username:
                ACTIVE_TOKENS.pop(token, None)
                evicted += 1
    if evicted > 0:
        _logger.info(f"[auth] 账号 {username} 同账号踢人, 失效 {evicted} 个旧 token")
    return evicted


def _is_account_active(username: str) -> bool:
    """L4.85.3 + L4.85.4 治本: 检查账号是否在最近 3 分钟内有 active token.

    user 7/11 拍板 "5 分钟时间太长了，可以 3 分钟", 全栈统一 3min timeout
    (跟 L4.75 v2 lock_timeout_seconds 3min + login_request.LOGIN_REQUEST_TIMEOUT_SECONDS=180 + NavBar IDLE_TIMEOUT_MS=3min 1:1 stable 永久规则化沿用).

    跟 L4.42 + L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 L4.84 + L4.85 + L4.85.1 + L4.85.2 1:1 stable 永久规则链配套.
    跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用 (跟 login_request._is_account_active 1:1 stable 复用, 0 业务代码改动).

    Bug 修复 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用): 之前 _is_account_active 永远返回 True (因为业务验证 3 件套留的 token 在 ACTIVE_TOKENS 中,
    logout 不会清空所有该 user 的 token). 修复: 用 last_active_at + 3min > now 检查 (跟 L4.75 v2 1:1 stable 永久规则化沿用).
    """
    now = datetime.now()
    with _AUTH_STATE_LOCK:
        for token_user, last_active in ACTIVE_TOKENS.values():
            if token_user == username and (now - last_active) < timedelta(minutes=3):
                return True
    return False


def _verify_token(token: str, sliding: bool = True) -> str | None:
    """验证 token 有效性，返回 username 或 None。
    
    sliding=True 时刷新 last_active_at（滑动过期），用于普通 API 请求。
    sliding=False 时不刷新，用于 /auth/me 等只读检查。
    """
    with _AUTH_STATE_LOCK:
        record = ACTIVE_TOKENS.get(token)
        if not record:
            return None
        username, last_active_at = record
        if datetime.now() - last_active_at > TOKEN_TTL:
            # token 过期，自动清理
            ACTIVE_TOKENS.pop(token, None)
            return None
        if sliding:
            # 滑动续期：刷新最后活跃时间
            ACTIVE_TOKENS[token] = (username, datetime.now())
        return username


def _token_ttl_seconds() -> int:
    """返回 token 剩余有效秒数"""
    return int(TOKEN_TTL.total_seconds())


def is_admin_username(username: str | None) -> bool:
    """Sprint 205+ Admin Upload: 唯一 admin 名单 SSOT (跟 L4.84 + L4.85 1:1 stable 永久规则化沿用).

    行为 (P2-4 修法):
    - username 为 None 或纯空白: False
    - username 不 strip: `"admin"` 命中, `" admin "` 不命中 (大小写敏感)
    - 每次调用动态读 FQ_CRM_ADMINS, 避免 import 缓存污染测试 env (跟 L4.88
      VALID_CREDENTIALS race 1:1 stable 永久规则化沿用)
    - 配置项 FQ_CRM_ADMINS 仍走 strip (允许 " admin , fqsw , " 这种格式),
      已认证 username 走原始字符串精确匹配

    配套 conftest fixture: backend/tests/conftest.py::_reset_fq_crm_admins_env
    autouse 在 test 前后重建 admin 名单环境变量 (当前实现无 module-level cache,
    每次调用动态读 FQ_CRM_ADMINS env var). 跟 FQ_CRM_ADMINS env var 1:1 stable
    永久规则化沿用.

    Returns: bool, True 表示 username 在 FQ_CRM_ADMINS 配置中 (精确匹配).
    """
    # P2-4: username 走原始值精确匹配, 仅 None/纯空白 走 False
    if username is None:
        return False
    # username 是纯空白 → False
    if not username.strip():
        return False
    raw = os.environ.get("FQ_CRM_ADMINS", "")
    if not raw or not raw.strip():
        return False
    admins = frozenset(piece.strip() for piece in raw.split(",") if piece.strip())
    return username in admins


# ─────────────────────────────────────────────────────────────
# 路由
# ─────────────────────────────────────────────────────────────
@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, request: Request):
    """账号密码登录，成功返回 token（含限速保护）"""
    client_ip = _get_client_ip(request)
    _authenticate_credentials(req.username, req.password, client_ip)
    # L4.85.2 治本: 整合 L4.84 path 跟 L4.85 path (跟 user 7/10 拍板 "admin 账号只允许登陆一个人" 1:1 stable 永久规则化沿用)
    # 跟 L4.85 create_login_request 409 模式 1:1 stable 配套, 跟 L4.85.1 1:1 stable 永久规则化沿用
    # e2e 根治 (2026-07-19): FQ_CRM_TEST_MODE=1 时跳过 409，直接踢旧会话再发新 token。
    # 真因: Playwright 每 case 新 context 但同 process 共享 ACTIVE_TOKENS → 第 2 个 case login 409
    # → 停在「申请登录」→ 业务页 toBeVisible 全红。生产默认 0，行为不变。
    _test_mode = os.environ.get("FQ_CRM_TEST_MODE") == "1"
    with _AUTH_STATE_LOCK:
        if _is_account_active(req.username) and not _test_mode:
            raise HTTPException(
                status_code=409,
                detail="账号正在被使用, 请使用申请登录按钮",
            )
        # L4.84 治本: 同账号踢人, 同一账号同时只能 1 个活跃会话, 旧 token 失效强制重新登录
        _evict_previous_sessions_for_user(req.username)
        token = secrets.token_urlsafe(32)
        ACTIVE_TOKENS[token] = (req.username, datetime.now())
    _logger.info(
        f"[auth] 登录成功：{_safe_log_username(req.username)}，IP={client_ip}"
    )

    return {
        "token": token,
        "username": req.username,
        "is_admin": is_admin_username(req.username),
    }


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

    return {
        "username": username,
        "is_admin": is_admin_username(username),
    }


class RefreshResponse(BaseModel):
    token: str
    username: str


@router.post("/refresh", response_model=RefreshResponse)
def refresh_token(request: Request):
    """刷新 token 过期时间（滑动续期），返回相同 token + username"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    token = auth[7:]

    username = _verify_token(token, sliding=True)
    if username is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    return {"token": token, "username": username}


@router.post("/logout", response_model=LogoutResponse)
def logout(request: Request, token: str | None = None):
    """退出登录，使当前 token + 同账号其他 stale token 失效 (跟 L4.84 _evict_previous_sessions_for_user 1:1 stable 复用).

    user 7/11 报"我因该都退出账号了，但是还是要申请登陆" + "Cmd+Q 退出浏览器后, 变成需要申请登录" 真根因:
    - 之前 logout 只删当前 token, 多次登录/refresh 留下 stale token, _is_account_active 3min 检查误判 True → B 端 login 409
    - Cmd+Q 退出浏览器 → frontend JS 全停 → backend ACTIVE_TOKENS 仍有 A token → B login 409
    修复: 复用 _evict_previous_sessions_for_user 踢出同账号所有 stale token + 配套 sendBeacon (token via query).

    L4.85.6 方案 A: sendBeacon 不能设 Authorization header, 所以 logout endpoint 接受 token via query param.
    配套: 方案 D background task evict idle token > 60s (frontend/services/auth_token_evictor.py).

    跟 L4.84 + L4.85.3 + L4.85.4 + L4.85.6 1:1 stable 永久规则链配套, 跟 L4.42 + L4.50 + L4.55 1:1 stable 永久规则化沿用,
    跟你 7/16 离职 0.5-1 天闭环 1:1 stable 永久规则化沿用.
    """
    # L4.85.6 治本: 兼容 Authorization header (正常 logout) + token via query (sendBeacon beforeunload)
    auth = request.headers.get("Authorization", "")
    bearer_token = auth[7:] if auth.startswith("Bearer ") else None
    effective_token = bearer_token or token

    if effective_token:
        with _AUTH_STATE_LOCK:
            record = ACTIVE_TOKENS.pop(effective_token, None)
        if record:
            username = record[0]
            # L4.85.4 治本: 踢出该 user 所有 stale token, 避免 _is_account_active 3min 检查误判 True
            evicted = _evict_previous_sessions_for_user(username)
            _logger.info(f"[auth] 退出登录：{username}，踢出 {evicted} 个 stale token (L4.85.6 sendBeacon 兼容)")
    return {"success": True}
