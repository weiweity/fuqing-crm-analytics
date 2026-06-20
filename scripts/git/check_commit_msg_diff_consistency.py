#!/usr/bin/env python3
"""Warn when a commit message understates a staged, destructive file change."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DELETION_RATIO_THRESHOLD = 0.80
ACTION_RE = re.compile(
    r"^\s*(fix|feat|chore|docs|ci|test|refactor|perf|build)(?:\([^)]+\))?!?:",
    re.IGNORECASE,
)
DELETION_INTENT_RE = re.compile(
    r"\b(delete|remove|drop|rewrite|replace|refactor|deprecat(?:e|ed|ion)|retire)\w*\b"
    r"|删除|移除|重构|重写|替换|弃用|下线",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StagedFileStat:
    path: str
    additions: int
    deletions: int
    old_lines: int

    @property
    def deletion_ratio(self) -> float:
        if self.old_lines <= 0:
            return 0.0
        return min(self.deletions / self.old_lines, 1.0)


def _run_git(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        check=False,
    )


def _old_line_count(path: str) -> int:
    result = _run_git(["show", f"HEAD:{path}"])
    if result.returncode != 0:
        return 0
    content = result.stdout
    return content.count(b"\n") + int(bool(content) and not content.endswith(b"\n"))


def get_staged_file_stats() -> list[StagedFileStat]:
    """Return text-file numstat plus the line count of each HEAD preimage."""
    result = _run_git([
        "-c",
        "core.quotePath=false",
        "diff",
        "--cached",
        "--no-renames",
        "--numstat",
        "-z",
        "--diff-filter=ACMRD",
    ])
    if result.returncode != 0:
        return []

    stats: list[StagedFileStat] = []
    for raw_entry in result.stdout.split(b"\0"):
        if not raw_entry:
            continue
        parts = raw_entry.split(b"\t", 2)
        if len(parts) != 3 or parts[0] == b"-" or parts[1] == b"-":
            continue
        try:
            additions = int(parts[0])
            deletions = int(parts[1])
            path = parts[2].decode("utf-8", errors="surrogateescape")
        except (ValueError, UnicodeDecodeError):
            continue
        stats.append(
            StagedFileStat(
                path=path,
                additions=additions,
                deletions=deletions,
                old_lines=_old_line_count(path),
            )
        )
    return stats


def parse_action(message: str) -> str:
    match = ACTION_RE.search(message)
    return match.group(1).lower() if match else "unspecified"


def message_mentions_path(message: str, path: str) -> bool:
    normalized_message = message.replace("\\", "/").casefold()
    normalized_path = path.replace("\\", "/").casefold()
    return normalized_path in normalized_message or Path(normalized_path).name in normalized_message


def find_warnings(message: str, stats: list[StagedFileStat]) -> list[str]:
    if DELETION_INTENT_RE.search(message):
        return []

    action = parse_action(message)
    warnings: list[str] = []
    for stat in stats:
        if not message_mentions_path(message, stat.path):
            continue
        if stat.deletion_ratio <= DELETION_RATIO_THRESHOLD:
            continue
        warnings.append(
            f"{stat.path}: deleted {stat.deletions}/{stat.old_lines} lines "
            f"({stat.deletion_ratio:.1%}), but action={action!r} and the message "
            "does not state delete/remove/refactor intent"
        )
    return warnings


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("WARN [commit-diff] missing COMMIT_MSG_FILE; consistency check skipped", file=sys.stderr)
        return 0

    try:
        message = Path(args[0]).read_text(encoding="utf-8", errors="replace")
        warnings = find_warnings(message, get_staged_file_stats())
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"WARN [commit-diff] check failed and was skipped: {exc}", file=sys.stderr)
        return 0

    for warning in warnings:
        print(f"WARN [commit-diff] {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
