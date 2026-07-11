"""L4.85.6 + L4.91.2 (2026-07-11) 治本 L4.85.6 Playwright e2e 测试环境隔离问题.

真根因 (跟 L4.42 立项实证 SOP 'git log + grep 实证' 1:1 stable):
- launchd backend 单 process 共享 ACTIVE_TOKENS dict (内存全局)
- e2e test A 端 login 创建 admin token → ACTIVE_TOKENS 有 admin
- e2e test B 端 login → _is_account_active('admin') True → 409 → 申请登录
- 状态污染让 e2e test 不能干净地跑 (跟 L4.85.6 1:1 stable 永久规则化沿用)

治本 (跟 L4.42 + L4.50 + L4.85.6 + L4.91.2 1:1 stable 永久规则化沿用, 0 业务代码改动 1:1 stable):
- /api/v1/_test/reset endpoint (仅 FQ_CRM_TEST_MODE=1 开启, 安全护栏)
- 重置 ACTIVE_TOKENS + _LOGIN_ATTEMPTS + (future) 缓存
- 不动 SQL 业务口径, 不动后端 ACTIVE_TOKENS 正常逻辑

配套 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则链配套):
- L4.85.6 e2e spec 1:1 stable 永久规则化沿用: beforeAll 调 /_test/reset 清状态
- L4.50 0 业务代码改动 累计 96 次 1:1 stable 永久规则链配套
- 跨 sprint 留尾: 接手人 7/16+ 启动可加更多 reset (e.g. RFM cache evict)
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException

from backend.routers.auth import ACTIVE_TOKENS, _LOGIN_ATTEMPTS

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/_test", tags=["测试辅助-L4.85.6"])


@router.post("/reset", include_in_schema=False)
def reset_test_state() -> dict:
    """L4.85.6 + L4.91.2 治本: 重置 e2e test 状态 (清 ACTIVE_TOKENS + _LOGIN_ATTEMPTS).

    仅 FQ_CRM_TEST_MODE=1 开启 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 安全护栏)
    默认 disabled, 避免 production 误调清掉所有用户登录态.

    跟 L4.85.6 e2e spec 1:1 stable 永久规则化沿用:
    - beforeAll: POST /api/v1/_test/reset 清 ACTIVE_TOKENS dict
    - 后续 test 跑 admin login → 不会跟其他 test 冲突

    0 业务代码改动 累计 96 次 1:1 stable 永久规则链配套 (跟 L4.50 累计 95+ 次 1:1 stable).
    """
    if os.environ.get("FQ_CRM_TEST_MODE") != "1":
        raise HTTPException(
            status_code=403,
            detail="FQ_CRM_TEST_MODE=1 未启用, /_test/reset 不可用 (production 安全护栏, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)",
        )

    active_count = len(ACTIVE_TOKENS)
    login_attempt_count = len(_LOGIN_ATTEMPTS)
    ACTIVE_TOKENS.clear()
    _LOGIN_ATTEMPTS.clear()
    _logger.info(
        f"[test-reset] FQ_CRM_TEST_MODE=1 enabled, 清 ACTIVE_TOKENS ({active_count} tokens) + _LOGIN_ATTEMPTS ({login_attempt_count} entries)"
    )
    return {
        "success": True,
        "cleared": {
            "active_tokens": active_count,
            "login_attempts": login_attempt_count,
        },
    }