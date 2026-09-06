"""Conservative native-engine defaults; no database, dotenv or service startup.

These are DuckDB buffer budgets, NOT process RSS limits. Explicit deployment
settings still need load testing. Read connections to one database share its
buffer budget; an independent cache database requires a separate allowance.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

import psutil

MIB = 1024 ** 2
GIB = 1024 ** 3


def effective_memory_bytes() -> int:
    """Use host RAM, limited by standard Linux cgroup mounts when present.

Unusual/nested container mounts require explicit deployment budgets. Do not
base a connection's config on fluctuating free RAM during individual requests.
"""
    try:
        total = int(psutil.virtual_memory().total)
    except (OSError, ValueError, AttributeError):
        total = 4 * GIB  # Unknown host: a conservative 2 GiB engine allowance.
    if total <= 0:
        total = 4 * GIB
    if sys.platform == "linux":
        for limit_path in (
            Path("/sys/fs/cgroup/memory.max"),
            Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
        ):
            try:
                limit = int(limit_path.read_text(encoding="ascii").strip())
                if limit > 0:
                    total = min(total, limit)
            except (OSError, ValueError):
                pass  # Includes cgroup v2's unbounded "max" value.
    return total


def default_memory_limit(memory_bytes: int | None = None) -> str:
    """Half of detected RAM, capped at 8 GiB; reserve room for Python/OS/cache."""
    total = effective_memory_bytes() if memory_bytes is None else memory_bytes
    return f"{max(1, min(8192, total // (2 * MIB)))}MiB"


def default_cache_memory_limit(memory_bytes: int | None = None) -> str:
    """Small result-cache budget, not another full-size analytics engine."""
    total = effective_memory_bytes() if memory_bytes is None else memory_bytes
    return f"{max(1, min(256, total // (32 * MIB)))}MiB"


def default_threads(cpu_count: int | None = None) -> int:
    """Use at most four engine threads; concurrent users do not each get a CPU pool."""
    if cpu_count is None:
        cpu_count = getattr(os, "process_cpu_count", os.cpu_count)() or 1
    return max(1, min(4, cpu_count // 2))
