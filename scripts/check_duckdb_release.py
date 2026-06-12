#!/usr/bin/env python3
"""Sprint 20+ A' 路径激活监控 — DuckDB 1.6.0 stable release 检测.

Usage:
    python3 scripts/check_duckdb_release.py

Output (YAML):
    installed: 1.5.4.dev18
    latest_stable: 1.5.3
    latest_dev: 1.6.0.dev12
    1.6.0_stable_released: false
    recommendation: '等 1.6.0 stable release (PyPI 仍 1.5.3)'

PyPI 监控:
    https://pypi.org/pypi/duckdb/json
    stable 出现时 = 1.6.0.x 在 latest 字段
"""
import json
import sys
import urllib.request


def get_pypi_duckdb() -> dict:
    """Query PyPI for duckdb package metadata. Falls back to curl if Python SSL fails."""
    import subprocess
    # Try Python urllib first (uses system cert store)
    try:
        with urllib.request.urlopen("https://pypi.org/pypi/duckdb/json", timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        pass  # Fall through to curl
    # Fallback: use system curl (which uses system certs differently)
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "10", "https://pypi.org/pypi/duckdb/json"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
    except Exception as e:
        print(f"[ERROR] PyPI query failed (Python + curl both): {e}", file=sys.stderr)
    return {}


def _check_pypi_duckdb_releases() -> dict:
    """Helper for cron shell-out: returns structured PyPI state.

    Returns:
        dict with keys:
            latest_stable (str): info.version from PyPI
            latest_dev (str): newest *.dev* release, or 'none'
            all_stable_with_1_6_0_prefix (list[str]): stable releases starting with '1.6.0'
            raw (dict): full PyPI payload (for advanced callers)
    """
    data = get_pypi_duckdb()
    if not data:
        return {"latest_stable": "", "latest_dev": "none", "all_stable_with_1_6_0_prefix": [], "raw": {}}

    info = data.get("info", {})
    latest = info.get("version", "unknown")
    releases = data.get("releases", {})

    dev_releases = sorted(v for v in releases.keys() if "dev" in v)
    latest_dev = dev_releases[-1] if dev_releases else "none"

    all_stable_with_1_6_0_prefix = [
        v for v in releases.keys()
        if v.startswith("1.6.0") and "dev" not in v
    ]

    return {
        "latest_stable": latest,
        "latest_dev": latest_dev,
        "all_stable_with_1_6_0_prefix": all_stable_with_1_6_0_prefix,
        "raw": data,
    }


def parse_duckdb_version(ver: str) -> tuple:
    """Parse '1.6.0.dev12' → (1, 6, 0, 'dev12')."""
    parts = ver.split(".")
    major = int(parts[0])
    minor = int(parts[1])
    patch_part = parts[2] if len(parts) > 2 else "0"
    if "dev" in patch_part:
        patch_str, dev_str = patch_part.split("dev")
        patch = int(patch_str) if patch_str else 0
        return (major, minor, patch, f"dev{dev_str}")
    else:
        patch = int(patch_part) if patch_part else 0
        return (major, minor, patch, "")


def main() -> int:
    state = _check_pypi_duckdb_releases()
    if not state.get("raw"):
        return 1

    latest = state["latest_stable"]
    latest_dev = state["latest_dev"]
    has_160_stable = bool(state["all_stable_with_1_6_0_prefix"])

    # Check installed
    try:
        import duckdb
        installed = duckdb.__version__
    except ImportError:
        installed = "not installed"

    print("installed: " + installed)
    print("latest_stable: " + latest)
    print("latest_dev: " + latest_dev)
    print("1.6.0_stable_released: " + str(has_160_stable).lower())

    if has_160_stable:
        print("recommendation: 1.6.0 stable 已 release, 跑 Sprint 20+ A' 路径 4 步激活")
    elif "dev12" in latest_dev or latest_dev >= "1.6.0.dev1":
        print("recommendation: 等 1.6.0 stable release (dev12+ 已治根, prod 别装 dev)")
    else:
        print("recommendation: 等 DuckDB 1.6.0 release (PyPI 仍 " + latest + ")")

    return 0


if __name__ == "__main__":
    sys.exit(main())
