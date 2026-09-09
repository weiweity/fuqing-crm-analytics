"""Synthetic runtime endpoints remain restricted to explicit loopback blocks."""
import pytest

from backend.services.analytics.runtime import HostBridge
from backend.services.analytics.runtime_ports import bridge_origin, runtime_port_base


@pytest.mark.parametrize("base", [4315, 4325, 4335])
def test_isolated_block(base):
    origin = bridge_origin({"port_base": base})
    assert HostBridge(origin, "x" * 32).origin == f"http://127.0.0.1:{base + 1}"


@pytest.mark.parametrize("base", [True, "4335", 8000, 65535, None])
def test_invalid_block(base):
    with pytest.raises(ValueError):
        runtime_port_base({"port_base": base})


@pytest.mark.parametrize("origin", ["http://localhost:4336", "http://127.0.0.1:8000", "https://127.0.0.1:4336", "http://127.0.0.1:4336@evil.invalid"])
def test_no_arbitrary_bridge_origin(origin):
    with pytest.raises(ValueError):
        HostBridge(origin, "x" * 32)
