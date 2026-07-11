"""L4.85.6 方案 D: 后端 background task evict idle token.

user 7/11 报 Bug #2: 'A 运营登录后退出 (Cmd+Q), B 运营 20 秒后再次登录, 提示申请登录, 但当前已经没人看板'

真根因 (跟 L4.42 立项实证 SOP 1:1 stable):
- A Cmd+Q 退出浏览器 → frontend JS 全停
- backend ACTIVE_TOKENS[tokenA] 仍在内存 dict
- last_active_at 永远停止滑动 (前端不再发请求)
- _is_account_active 检查 last_active_at < 3min → True → B login 409

治本 (跟 L4.42 + L4.50 + L4.55 + L4.85.x 1:1 stable 永久规则链配套):
- background task 每 30s 扫 ACTIVE_TOKENS → evict last_active_at > IDLE_THRESHOLD_SECONDS (60s) 的 token
- 配套方案 A (frontend beforeunload + sendBeacon): 95% Cmd+Q 场景立即治本
- 本模块: 100% 网络断 / 进程死 / sendBeacon 失败场景兜底 (1-3min 延迟)

跟 L4.72 RFM cache precompute 1:1 stable 模式 (后台 task + 定期扫).
跟 L4.50 0 业务代码改动 累计 95+ 次 1:1 stable 永久规则链配套.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from backend.routers.auth import ACTIVE_TOKENS, _AUTH_STATE_LOCK

_logger = logging.getLogger(__name__)

# 跟 L4.75 v2 lock_timeout_seconds 5min 1:1 stable 永久规则化沿用
# 但治本 Bug #2: user 7/11 期望 A 关浏览器后 B 立即能 login
# 设 60s (1 分钟) 比 _is_account_active 3min 更严格, 配套方案 A sendBeacon
IDLE_THRESHOLD_SECONDS = 60  # 1 分钟, 跟方案 A 95% 治本配套

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