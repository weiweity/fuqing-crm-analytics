"""Old-customer six-table simplification guardrails for L4.74."""
from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
HEALTH_DIR = ROOT / "backend/services/health"
ENV_FILE = ROOT / ".env"


# CI runner 缺 .env 文件 (跟 L4.5 配置 1:1 stable 永久规则化沿用, 跟 L4.39 macOS-only skipif 1:1 stable 永久规则化沿用)
pytestmark = pytest.mark.skipif(
    not ENV_FILE.exists(),
    reason="CI runner 缺 .env 文件 (跟 L4.5 配置 1:1 stable 永久规则化沿用)",
)


def test_health_services_do_not_reintroduce_thread_pool_executor() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in HEALTH_DIR.glob("*.py"))
    rfm_analysis = (HEALTH_DIR / "rfm_analysis" / "analysis.py").read_text(encoding="utf-8")

    assert "ThreadPoolExecutor" not in combined
    assert "with concurrent.futures.ThreadPoolExecutor" not in rfm_analysis


def test_customer_health_query_router_prefix_is_explicit() -> None:
    text = (ROOT / "backend/middleware/query_router.py").read_text(encoding="utf-8")

    assert '"/api/v1/customer-health/"' in text


def test_env_read_pool_size_is_l4723_ten() -> None:
    text = (ROOT / ".env").read_text(encoding="utf-8")

    assert "FQ_READ_POOL_SIZE=10" in text


def test_precompute_layer_uses_services_instead_of_new_sql() -> None:
    text = (ROOT / "scripts/precompute_old_customer_9_sub_modules.py").read_text(encoding="utf-8")

    assert "backend.services.health.overview:get_overview" in text
    assert "backend.services.health.rfm_analysis:get_rfm_analysis" in text
    assert "FROM orders" not in text
