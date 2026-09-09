#!/usr/bin/env python3
"""Read-only, single-user baseline of an explicitly owned synthetic HTTP instance."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

import psutil

ROOT = Path(__file__).resolve().parents[2]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, choices=[18082, 18083], required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ["COMPETITION_HTTP_TOKEN"]
    process = psutil.Process(args.pid)
    if Path(process.cwd()).resolve() != ROOT:
        raise SystemExit("HTTP PID must belong to this checkout")
    sockets = process.net_connections(kind="inet")
    if not any(s.status == psutil.CONN_LISTEN and s.laddr.ip == "127.0.0.1"
               and s.laddr.port == args.port for s in sockets):
        raise SystemExit("PID is not the selected loopback HTTP listener")
    opener = build_opener(NoRedirect())
    base = f"http://127.0.0.1:{args.port}/api/v1/analytics/competition"
    headers = {"Authorization": f"Bearer {token}"}
    with opener.open(Request(base + "/boards", headers=headers), timeout=5) as response:
        inventory = json.load(response)
    boards = inventory if isinstance(inventory, list) else inventory["items"]
    if not boards:
        raise SystemExit("Create a synthetic board through the product before benchmarking")
    board_id = boards[0]["board_id"]
    report = {
        "schema_version": "competition-http-baseline/v1",
        "at": datetime.now(timezone.utc).isoformat(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "scope": "existing synthetic candidate; not archived business data or model latency",
        "platform": platform.platform(), "python": platform.python_version(),
        "cpu_count": os.cpu_count(), "concurrency": 1,
        "requests_per_path": 30, "timeout_seconds": 5, "cache": "warm; no cache flush",
        "board_count": len(boards), "process_pid": args.pid,
        "rss_method": "sampled before and after every request, not continuous peak",
        "slo_status": "BASELINE_ONLY; thresholds not yet accepted",
        "scenarios": [],
    }
    for path in ("/results", "/boards", f"/boards/{board_id}"):
        samples = []
        for index in range(30):
            before = process.memory_info().rss
            started = time.perf_counter()
            status, size, failure = None, 0, None
            try:
                with opener.open(Request(base + path, headers=headers), timeout=5) as response:
                    status = response.status
                    payload = response.read(2 * 1024 * 1024 + 1)
                    size = len(payload)
                    if size > 2 * 1024 * 1024:
                        raise ValueError("response exceeds baseline bound")
                    json.loads(payload)
            except HTTPError as error:
                status, failure = error.code, "HTTPError"
            except Exception as error:
                failure = type(error).__name__
            elapsed = (time.perf_counter() - started) * 1000
            samples.append({"arrival": index + 1, "status": status, "failure": failure,
                            "elapsed_ms": round(elapsed, 3), "response_bytes": size,
                            "rss_bytes": max(before, process.memory_info().rss)})
            time.sleep(0.05)
        times = sorted(row["elapsed_ms"] for row in samples)
        report["scenarios"].append({
            "path": path, "arrivals": len(samples),
            "successes": sum(row["status"] == 200 and row["failure"] is None for row in samples),
            "p50_ms": times[math.ceil(len(times) * .5) - 1],
            "p95_ms": times[math.ceil(len(times) * .95) - 1], "max_ms": max(times),
            "sampled_peak_rss_bytes": max(row["rss_bytes"] for row in samples),
            "queue_compute_output_breakdown": "unavailable; end-to-end measured",
            "samples": samples,
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps({**report, "scenarios": [
        {key: value for key, value in row.items() if key != "samples"}
        for row in report["scenarios"]]}, ensure_ascii=False, indent=2))
    return 0 if all(row["successes"] == row["arrivals"] for row in report["scenarios"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
