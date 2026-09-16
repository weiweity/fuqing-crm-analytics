"""L4.85.6 方案 D: 后端 background task evict idle token.

user 7/11 报 Bug #2: 'A 运营登录后退出 (Cmd+Q), B 运营 20 秒后再次登录, 提示申请登录, 但当前已经没人看板'

真根因 (跟 L4.42 立项实证 SOP 1:1 stable):
- A Cmd+Q 退出浏览器 → frontend JS 全停
- backend ACTIVE_TOKENS[tokenA] 仍在内存 dict
- last_active_at 永远停止滑动 (前端不再发请求)
- _is_account_active 检查 last_active_at < 3min → True → B login 409

治本 (跟 L4.42 + L4.50 + L4.55 + L4.85.x 1:1 stable 永久规则链配套):
- background task 每 30s 扫 ACTIVE_TOKENS → evict last_active_at > IDLE_THRESHOLD_SECONDS 的 token
- 浏览器不在 unload 生命周期登出，避免刷新和站内导航误销毁 token
- 本模块统一处理关页、断网与进程退出后的幽灵会话；默认 idle 8h（FQ_AUTH_IDLE_SECONDS），最多再延迟一个扫描间隔

跟 L4.72 RFM cache precompute 1:1 stable 模式 (后台 task + 定期扫).
跟 L4.50 0 业务代码改动 累计 95+ 次 1:1 stable 永久规则链配套.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
import os

from backend.routers.auth import ACTIVE_TOKENS, _AUTH_STATE_LOCK

_logger = logging.getLogger(__name__)

# 跟 L4.75 v2 lock_timeout_seconds 5min 1:1 stable 永久规则化沿用
# 但治本 Bug #2: user 7/11 期望 A 关浏览器后 B 立即能 login
# 默认 8h；前端 idle 登出已关闭，幽灵会话由本 evictor 回收
DEFAULT_IDLE_SECONDS = 28800


def parse_idle_seconds(raw: str | None) -> int:
    try:
        value = int((raw or "").strip() or str(DEFAULT_IDLE_SECONDS))
    except ValueError:
        return DEFAULT_IDLE_SECONDS
    return max(1, value)


IDLE_THRESHOLD_SECONDS = parse_idle_seconds(os.environ.get("FQ_AUTH_IDLE_SECONDS"))

# 跟 L4.72 RFM cache precompute 1:1 stable 永久规则化沿用
SCAN_INTERVAL_SECONDS = 30  # 每 30 秒扫一次


def evict_idle_tokens(idle_threshold_seconds: int = IDLE_THRESHOLD_SECONDS) -> int:
    """同步 evict ACTIVE_TOKENS 中 idle token.

    user 7/11 报 Bug #2 治本核心 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用):
    - A Cmd+Q → frontend JS 全停 → ACTIVE_TOKENS[tokenA] 仍在
    - last_active_at 超过 idle_threshold_seconds → A token 已无效 (前端已死)
    - evict → ACTIVE_TOKENS 删除 → B 端 login 不再 409

    Returns: 被 evict 的 token 数.
    """
    now = datetime.now()
    threshold = timedelta(seconds=idle_threshold_seconds)
    evicted_tokens: list[str] = []

    with _AUTH_STATE_LOCK:
        for token, (username, last_active) in list(ACTIVE_TOKENS.items()):
            if (now - last_active) >= threshold:
                evicted_tokens.append(f"{username}:{token[:8]}...")
                ACTIVE_TOKENS.pop(token, None)

    if evicted_tokens:
        _logger.info(
            f"[auth-evictor] evict {len(evicted_tokens)} idle token(s) > {idle_threshold_seconds}s: "
            + ", ".join(evicted_tokens[:5])
            + ("..." if len(evicted_tokens) > 5 else "")
        )

    return len(evicted_tokens)


async def evict_idle_tokens_periodically(stop_event: asyncio.Event) -> None:
    """async background task: 定期调 evict_idle_tokens.

    跟 L4.72 RFM cache precompute 1:1 stable 永久规则化沿用 (后台 asyncio task).
    跟 L4.69.1 finally 块 gc.collect + del conn 1:1 stable 永久规则化沿用 (stop_event 优雅退出).
    """
    _logger.info(
        f"[auth-evictor] 启动 background task, 每 {SCAN_INTERVAL_SECONDS}s 扫 ACTIVE_TOKENS, "
        f"idle > {IDLE_THRESHOLD_SECONDS}s evict"
    )
    try:
        while not stop_event.is_set():
            try:
                evict_idle_tokens()
            except Exception as e:
                # L4.40 fail-open 1:1 stable: 任何异常 exit 0, 不阻 commit
                _logger.error(f"[auth-evictor] evict 异常 (fail-open): {e}")

            try:
                # 用 wait_for + stop_event 实现可中断 sleep
                await asyncio.wait_for(stop_event.wait(), timeout=SCAN_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                # 超时 = 一个周期结束, 继续下个周期
                pass
    finally:
        _logger.info("[auth-evictor] background task 退出")
