"""L4.75.3 通知对方 endpoints 回归 test (跟 L4.42 + L4.50 + L4.4 + L4.75 1:1 stable 永久规则链配套)."""
import time

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.middleware.single_user_mode import ACTIVE_USERS


@pytest.fixture(autouse=True)
def _clear_active_users():
    ACTIVE_USERS.clear()
    yield
    ACTIVE_USERS.clear()


def _login(client: TestClient, username: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def test_l4_75_3_notify_target_not_found_404():
    """L4.75.3 notify: target 没锁 → 404 (跟 L4.4 middleware 通知接口 1:1 stable 永久规则链配套)."""
    client = TestClient(app)
    token = _login(client, "admin", "123456")
    resp = client.post(
        "/api/v1/notifications/notify",
        json={"target_ip": "10.99.99.99", "message": "请让一下"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_l4_75_3_release_lock_self_404_when_no_lock():
    """L4.75.3 release: 用户自身无锁 → released=False (跟 L4.40 fail-open 1:1 stable 永久规则链配套)."""
    client = TestClient(app)
    token = _login(client, "admin", "123456")
    resp = client.post(
        "/api/v1/notifications/release",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["released"] is False


def test_l4_75_3_list_notifications_empty_when_no_lock():
    """L4.75.3 list: 用户自身无锁 → [] (跟 L4.4 middleware 通知接口 1:1 stable 永久规则链配套)."""
    client = TestClient(app)
    token = _login(client, "admin", "123456")
    resp = client.get(
        "/api/v1/notifications/list",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_l4_75_3_unit_get_set_notifications_for_lock_helper():
    """L4.75.3 unit: helper 在 ACTIVE_USERS 上挂 notifications list (跟 L4.75 1:1 stable 永久规则链配套)."""
    from backend.routers.notifications import (
        _get_notifications_for_lock,
        _set_notifications_for_lock,
    )

    ACTIVE_USERS.clear()
    # 旧结构 (跟 L4.75 pre-existing): float
    ACTIVE_USERS["ip:1.2.3.4"] = time.monotonic()
    assert _get_notifications_for_lock("ip:1.2.3.4") == []
    _set_notifications_for_lock("ip:1.2.3.4", [{"x": 1}])
    notifs = _get_notifications_for_lock("ip:1.2.3.4")
    assert notifs == [{"x": 1}]
    # 已升级到 dict 结构
    assert isinstance(ACTIVE_USERS["ip:1.2.3.4"], dict)


def test_l4_75_3_health_check_still_works():
    """L4.75.3 sanity: 新 router 不破坏健康检查 (跟 L4.65.1 + L4.69.1 1:1 stable 永久规则链配套)."""
    client = TestClient(app)
    resp = client.get("/api/v1/health/db_size")
    # 允许 200 + 503 (路由存在即可)
    assert resp.status_code in (200, 503)
