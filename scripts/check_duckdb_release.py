#!/usr/bin/env python3
"""Sprint 16 P0 激活监控 — DuckDB 1.5.4 stable release 检测.

Usage:
    python3 scripts/check_duckdb_release.py

Output (YAML):
    installed: 1.5.4.dev18
    latest_stable: 1.5.3
    latest_dev: 1.5.4.dev18
    1.5.4_stable_released: false
    recommendation: '等 1.5.4 stable release (PyPI 仍 1.5.3)'

PyPI 监控:
    https://pypi.org/pypi/duckdb/json
    stable 出现时 = 1.5.4.x 在 latest 字段
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
    except Exception:
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


def parse_duckdb_version(ver: str) -> tuple:
    """Parse '1.5.4.dev18' → (1, 5, 4, 'dev18')."""
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
    data = get_pypi_duckdb()
    if not data:
        return 1

    info = data.get("info", {})
    latest = info.get("version", "unknown")

    # Find latest dev release
    releases = data.get("releases", {})
    dev_releases = sorted([v for v in releases.keys() if "dev" in v])
    latest_dev = dev_releases[-1] if dev_releases else "none"

    # Check installed
    try:
        import duckdb
        installed = duckdb.__version__
    except ImportError:
        installed = "not installed"

    # Check if 1.5.4 stable exists
    has_154_stable = any(
        v.startswith("1.5.4") and "dev" not in v
        for v in releases.keys()
    )

    print("installed: " + installed)
    print("latest_stable: " + latest)
    print("latest_dev: " + latest_dev)
    print("1.5.4_stable_released: " + str(has_154_stable).lower())

    if has_154_stable:
        print("recommendation: 1.5.4 stable 已 release, 跑 Sprint 16 P0 激活 4 步规避")
    elif "dev18" in latest_dev or latest_dev >= "1.5.4.dev2":
        print("recommendation: 等 1.5.4 stable release (dev18+ 已治根, prod 别装 dev)")
    else:
        print("recommendation: 等 DuckDB 1.5.4 release (PyPI 仍 1.5.3)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
