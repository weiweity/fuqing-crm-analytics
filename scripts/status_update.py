#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
status_update.py — Sprint 59 #6 STATUS.md 4 字段自动抓取 (90 行 stdlib)

闭环 Sprint 24-58 累计 35 次手改 STATUS.md 错 3 次痛点.
抓 4 字段: pytest collected / pytest skipped / 当前债数 / 最近 sprint.
不用 grep -oP (Mac BSD grep 兼容 Codex #17), 全部 Python re.
--check exit 0/1, --apply atomic write (tmp + mv, Codex #13) exit 0/2.

退出码: 0=对齐 1=需更新 2=抓取失败/marker异常.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS_MD = Path(os.environ.get("STATUS_MD", str(ROOT / "STATUS.md")))
TECH_DEBT_MD = ROOT / "docs" / "TECH-DEBT.md"
START, END = "<!-- STATUS-AUTO-START -->", "<!-- STATUS-AUTO-END -->"
RE_COLLECTED = re.compile(r"(\d+)\s+tests?\s+collected")
RE_SKIPPED = re.compile(r"(\d+)\s+skipped")
RE_DEBT = re.compile(r"当前债数\*?\*?[::]\s*(\d+)\s*条?")
RE_SPRINT = re.compile(r"Sprint\s+(\d+)\b", re.I)


def _run(cmd, cwd, timeout=60):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout {timeout}s"
    except FileNotFoundError as e:
        return 127, "", str(e)


def collect_pytest():
    """Return (collected, skipped, warnings). 跑 pytest --co -q 抓测试数."""
    warnings = []
    rc, out, err = _run(
        ["python3", "-m", "pytest", "--co", "-q", "backend/tests/"],
        cwd=ROOT, timeout=120,
    )
    m = RE_COLLECTED.search(out)
    collected = m.group(1) if m else "?"
    if not m:
        warnings.append(f"pytest collected pattern not matched (rc={rc})")
    m = RE_SKIPPED.search(out)
    # pytest --co 默认 0 skipped 时不打印 "X skipped" 行, 视作 0 (合法状态)
    skipped = m.group(1) if m else "0"
    if not m:
        warnings.append("pytest skipped pattern not matched (assume 0)")
    return collected, skipped, warnings


def collect_debt():
    """读 docs/TECH-DEBT.md 抓 '当前债数: N 条'."""
    warnings = []
    if not TECH_DEBT_MD.exists():
        return "?", [f"{TECH_DEBT_MD} not found"]
    text = TECH_DEBT_MD.read_text(encoding="utf-8")
    m = RE_DEBT.search(text)
    if not m:
        return "?", ["当前债数 pattern not matched"]
    return m.group(1), warnings


def collect_recent_sprint():
    """git log --since 30d -- CHANGELOG.md 抓最近 sprint number."""
    warnings = []
    rc, out, err = _run(
        ["git", "log", "--since=30 days ago", "--oneline", "--", "CHANGELOG.md"],
        cwd=ROOT, timeout=30,
    )
    if rc != 0:
        return "?", [f"git log failed rc={rc}: {err.strip()}"]
    for line in out.splitlines():
        m = RE_SPRINT.search(line)
        if m:
            return f"Sprint {m.group(1)}", warnings
    return "?", ["no Sprint pattern in git log"]


def build_block(v):
    """Build the auto-update block content (with trailing \\n for atomic write)."""
    return (
        f"{START}\n"
        f"| pytest collected | **{v['pytest_collected']}** | Sprint 59 自动抓 |\n"
        f"| pytest skipped | **{v['pytest_skipped']}** | Sprint 59 自动抓 |\n"
        f"| 当前债数 | **{v['debt']}** | Sprint 59 自动抓 |\n"
        f"| 最近 sprint | **{v['recent_sprint']}** | Sprint 59 自动抓 |\n"
        f"{END}\n"
    )


def find_block(text):
    """Return (start, end_after_marker) of marker block, or None if invalid/duplicate."""
    s, e = text.find(START), text.find(END)
    if s == -1 or e == -1 or e <= s:
        return None
    if text.find(START, s + 1) != -1 or text.find(END, e + 1) != -1:
        return None
    return s, e + len(END)


def main():
    parser = argparse.ArgumentParser()
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not STATUS_MD.exists():
        print(f"ERROR: {STATUS_MD} not found", file=sys.stderr)
        return 2
    text = STATUS_MD.read_text(encoding="utf-8")
    pos = find_block(text)
    if pos is None:
        # 区分缺失 vs 重复 vs 顺序错
        if START not in text:
            print(f"ERROR: {START} marker missing", file=sys.stderr)
        elif text.count(START) > 1:
            print("ERROR: duplicate START marker", file=sys.stderr)
        elif text.count(END) > 1:
            print("ERROR: duplicate END marker", file=sys.stderr)
        else:
            print("ERROR: marker pair invalid (END before START)", file=sys.stderr)
        return 2

    # 抓 4 字段
    c, s, w1 = collect_pytest()
    d, w2 = collect_debt()
    sp, w3 = collect_recent_sprint()
    v = {"pytest_collected": c, "pytest_skipped": s, "debt": d, "recent_sprint": sp}
    new_block = build_block(v)

    for w in w1 + w2 + w3:
        print(f"WARNING: {w}", file=sys.stderr)

    s_pos, e_pos = pos
    current = text[s_pos:e_pos]
    if current == new_block.rstrip("\n"):
        print("OK: STATUS.md auto-block is up to date")
        return 0
    if args.check:
        print("DIFF: STATUS.md auto-block needs update")
        print("--- current ---")
        print(current)
        print("--- expected ---")
        print(new_block.rstrip("\n"))
        return 1

    # --apply atomic write
    new_text = text[:s_pos] + new_block + text[e_pos:]
    if e_pos < len(text) and text[e_pos] == "\n":
        new_text = text[:s_pos] + new_block + text[e_pos + 1:]
    try:
        fd, tmp = tempfile.mkstemp(prefix=".STATUS.md.", suffix=".tmp", dir=str(STATUS_MD.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(new_text)
            os.replace(tmp, STATUS_MD)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError as e:
        print(f"ERROR: atomic write failed: {e}", file=sys.stderr)
        return 2
    print(f"OK: updated (collected={c} skipped={s} debt={d} sprint={sp})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
