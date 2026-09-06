"""One owned read-only B0 computation process. No service, model or subprocess.

The parent retains the authoritative budget and execution record. An inherited
file-description lease spans fork/exec; EOF on the private control pipe exits
an orphan even if its query is still running. Recovery never signals old PIDs.
"""

import fcntl
import json
import os
from pathlib import Path
import re
import resource
import stat
import sys
import threading
import time

from backend.analytics_fixture import SyntheticFixture, private_directory
from backend.contracts.analytics import AnalyticsB0Facts, AnalyticsB0Result
from backend.semantic.analytics_b0 import CONTENT_SHA256, repeat_query, rows_digest
from backend.services.analytics.resource_profile import B0ResourceProfile


def emit(value):
    print(json.dumps(value, ensure_ascii=False, allow_nan=False), flush=True)


def worker_peak_rss_bytes():
    # Linux getrusage preserves pre-exec high water, including the forked
    # supervisor's address space. VmHWM belongs to this exec's memory map.
    # Both are observations, not a kernel-enforced RSS limit.
    if sys.platform == "linux":
        status = Path("/proc/self/status").read_text()
        match = re.search(r"^VmHWM:\s+(\d+)\s+kB$", status, re.MULTILINE)
        if match is None:
            raise RuntimeError("worker memory observation unavailable")
        return int(match[1]) * 1024
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def query_fixture(con, _config):
    rows = con.execute("SELECT order_id, customer_id, channel, paid_on FROM b0_orders ORDER BY order_id LIMIT 126").fetchall()
    if len(rows) != 125 or rows_digest(rows) != CONTENT_SHA256:
        raise ValueError("synthetic contents differ from the registered sample")
    query, params = repeat_query()
    values = con.execute(query, params).fetchone()
    return AnalyticsB0Result(facts=AnalyticsB0Facts(customers=values[0], repeat_customers=values[1], repeat_ratio=values[2]))


def run_child(*, workload=query_fixture, config=None):
    """workload injection is for owned test executables, never a wire option."""
    config = config if config is not None else json.loads(sys.stdin.readline(65537))
    if set(config) != {"binding", "profile", "profile_hash", "fixture", "lease_fd", "temp_dir"}:
        raise ValueError("unknown worker configuration")
    binding = config["binding"]
    if set(binding) != {"execution_id", "run_id", "attempt_id", "step_id"}:
        raise ValueError("incomplete worker binding")
    lease_fd = config["lease_fd"]
    info = os.fstat(lease_fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
        raise ValueError("invalid inherited execution lease")
    fcntl.flock(lease_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    profile = B0ResourceProfile(**config["profile"])
    if profile.digest != config["profile_hash"]:
        raise ValueError("worker resource profile drift")
    temp = private_directory(config["temp_dir"])

    def watch_parent():
        # No signals to guessed PIDs. Closing the pipe also handles a parent
        # crash between spawn and receiving the first child acknowledgement.
        # A daemon blocking in BufferedReader.read would hold its lock during
        # interpreter finalization and abort an otherwise successful worker.
        os.read(sys.stdin.fileno(), 1)
        os._exit(74)

    threading.Thread(target=watch_parent, daemon=True, name="b0-parent-liveness").start()
    started = time.monotonic()
    import duckdb

    fixture = SyntheticFixture(**config["fixture"])
    con = None
    try:
        database = fixture.validate()
        con = duckdb.connect(str(database), read_only=True, config={
            "memory_limit": f"{profile.duckdb_memory_mib}MiB", "threads": profile.duckdb_threads,
            "temp_directory": str(temp), "max_temp_directory_size": f"{profile.worker_temp_mib}MiB",
            "autoload_known_extensions": False,
            "autoinstall_known_extensions": False, "allow_community_extensions": False,
            "allow_persistent_secrets": False,
        })
        # DuckDB refuses setting temp_directory after external access has been
        # disabled, including during connection config application. Establish
        # the private directory first, then lock access/config before any data
        # query or injected workload. Extension autoload/install is already off.
        # On the isolated pinned 1.5.3, connect(config=...) reports this setting but
        # does not enforce the limit in an actual external sort. Reapplying it
        # after instance creation fixes the real engine quota (regression test
        # runs a bounded owned child without relying on the parent stop).
        con.execute("SET max_temp_directory_size = ?", [f"{profile.worker_temp_mib}MiB"])
        con.execute("SET enable_external_access=false")
        con.execute("SET lock_configuration=true")
        settings = dict(con.execute("SELECT name, value FROM duckdb_settings() WHERE name IN (?, ?, ?, ?, ?, ?)",
                                   ["memory_limit", "threads", "max_temp_directory_size", "enable_external_access",
                                    "lock_configuration", "access_mode"]).fetchall())
        emit({"type": "ready", **binding, "profile_hash": profile.digest, "settings": settings,
              "engine_version": duckdb.__version__, "engine_revision": duckdb.__git_revision__})
        result = workload(con, config)
        fixture.validate()  # Detect changed input before making a result visible.
        # A result frame is not exit; the parent waits for the owned process AND
        # the lease before committing this step or freeing any execution slot.
        emit({"type": "result", **binding, "profile_hash": profile.digest, "result": result.model_dump(mode="json")})
    except duckdb.OutOfMemoryException:
        emit({"type": "error", **binding, "code": "RESOURCE_EXCEEDED"})
    except Exception:
        emit({"type": "error", **binding, "code": "TOOL_FAILED"})
    finally:
        if con is not None:
            con.close()
        emit({"type": "closed", **binding, "rss_peak_bytes": worker_peak_rss_bytes(),
              "elapsed_ms": round((time.monotonic() - started) * 1000)})
        # Do not unlock early; the descriptor stays locked until process exit.


if __name__ == "__main__":
    run_child()
