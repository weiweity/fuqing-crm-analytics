#!/usr/bin/env python3
"""Run backend pytest in fresh-process chunks with a hard RSS circuit breaker."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import time

import psutil


ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "backend" / "tests"


def _rss_tree_bytes(pid: int) -> int:
    try:
        process = psutil.Process(pid)
        processes = [process, *process.children(recursive=True)]
    except psutil.Error:
        return 0
    total = 0
    for item in processes:
        try:
            total += item.memory_info().rss
        except psutil.Error:
            continue
    return total


def _stop_process_tree(process: subprocess.Popen[bytes]) -> None:
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
    except psutil.Error:
        children = []
    for child in children:
        try:
            child.terminate()
        except psutil.Error:
            pass
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        for child in children:
            try:
                child.kill()
            except psutil.Error:
                pass
        process.kill()
        process.wait(timeout=3)


def run(chunk_size: int, rss_limit_gb: float) -> int:
    tests = sorted(TEST_ROOT.glob("test_*.py"))
    limit_bytes = int(rss_limit_gb * 1024**3)
    total_groups = (len(tests) + chunk_size - 1) // chunk_size

    for index in range(0, len(tests), chunk_size):
        group = tests[index:index + chunk_size]
        group_number = index // chunk_size + 1
        print(
            f"[bounded-pytest] group {group_number}/{total_groups} "
            f"files {index + 1}-{index + len(group)}/{len(tests)}",
            flush=True,
        )
        process = subprocess.Popen(
            [sys.executable, "-m", "pytest", *map(str, group), "-x", "-q"],
            cwd=ROOT,
        )
        peak_bytes = 0
        while process.poll() is None:
            rss_bytes = _rss_tree_bytes(process.pid)
            peak_bytes = max(peak_bytes, rss_bytes)
            if rss_bytes > limit_bytes:
                print(
                    f"[bounded-pytest] ABORT group={group_number} "
                    f"rss_gb={rss_bytes / 1024**3:.2f} limit_gb={rss_limit_gb:.2f}",
                    file=sys.stderr,
                    flush=True,
                )
                _stop_process_tree(process)
                return 90
            time.sleep(1)

        print(
            f"[bounded-pytest] group {group_number} rc={process.returncode} "
            f"peak_rss_gb={peak_bytes / 1024**3:.2f}",
            flush=True,
        )
        if process.returncode != 0:
            return int(process.returncode or 1)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk-size", type=int, default=25)
    parser.add_argument("--rss-limit-gb", type=float, default=6.0)
    args = parser.parse_args()
    if args.chunk_size < 1 or args.rss_limit_gb <= 0:
        parser.error("chunk-size and rss-limit-gb must be positive")
    return run(args.chunk_size, args.rss_limit_gb)


if __name__ == "__main__":
    raise SystemExit(main())
