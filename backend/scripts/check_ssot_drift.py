#!/usr/bin/env python3
"""检查 ``留尾 #`` 的 ✅ 闭环 / 📋 推后状态、真实 commit 证据和状态回退."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOCS_ROOT = REPO_ROOT / "docs" / "sprints"
MARKER = "<!-- L4.20-CLOSE-MEMORY -->"
STATUS_CLOSED = "✅ 闭环"
STATUS_DEFERRED = "📋 推后"

RECORD_RE = re.compile(
    r"^\s*-\s*"
    r"(?P<tail>留尾\s*#[^|]+?)\s*\|\s*"
    r"(?P<status>✅\s*闭环|📋\s*推后)\s*\|\s*"
    r"fix_sprint=(?P<fix_sprint>[^|]+?)\s*\|\s*"
    r"commit=`?(?P<commit>[0-9a-fA-F]{7,40}|-)`?\s*\|\s*"
    r"evidence=(?P<evidence>.+?)\s*$"
)
SPRINT_RE = re.compile(r"Sprint(?P<number>\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class CloseMemoryRecord:
    tail: str
    status: str
    fix_sprint: str
    commit: str
    evidence: str
    path: Path
    line: int
    document_sprint: int

    @property
    def location(self) -> str:
        return f"{self.path}:{self.line}"


def _document_sprint(path: Path) -> int:
    match = SPRINT_RE.search(path.name)
    return int(match.group("number")) if match else -1


def _normalize_status(raw: str) -> str:
    compact = re.sub(r"\s+", "", raw)
    return {"✅闭环": STATUS_CLOSED, "📋推后": STATUS_DEFERRED}.get(
        compact, raw.strip()
    )


def parse_close_memory(path: Path) -> tuple[list[CloseMemoryRecord], list[str]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    records: list[CloseMemoryRecord] = []
    errors: list[str] = []
    in_close_memory = False

    for line_number, line in enumerate(lines, 1):
        if MARKER in line:
            in_close_memory = True
            continue
        if not in_close_memory or "留尾 #" not in line:
            continue

        match = RECORD_RE.match(line)
        if not match:
            errors.append(
                f"{path}:{line_number}: 留尾 # 未按 L4.20 标记 "
                f"{STATUS_CLOSED} / {STATUS_DEFERRED} + commit SHA"
            )
            continue

        records.append(
            CloseMemoryRecord(
                tail=re.sub(r"\s+", " ", match.group("tail")).strip(),
                status=_normalize_status(match.group("status")),
                fix_sprint=match.group("fix_sprint").strip(),
                commit=match.group("commit").lower(),
                evidence=match.group("evidence").strip(),
                path=path,
                line=line_number,
                document_sprint=_document_sprint(path),
            )
        )

    return records, errors


def _commit_exists(repo_root: Path, sha: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def validate_records(records: list[CloseMemoryRecord], repo_root: Path) -> list[str]:
    errors: list[str] = []

    for record in records:
        if not record.evidence:
            errors.append(f"{record.location}: 缺 evidence")

        if record.status == STATUS_CLOSED:
            if record.commit == "-":
                errors.append(f"{record.location}: {STATUS_CLOSED} 缺修复 commit SHA")
            elif not _commit_exists(repo_root, record.commit):
                errors.append(
                    f"{record.location}: commit {record.commit} 不是仓库中的真实 commit"
                )
            if record.fix_sprint == "-":
                errors.append(f"{record.location}: {STATUS_CLOSED} 缺 fix_sprint")
        elif record.status == STATUS_DEFERRED:
            if record.commit != "-":
                errors.append(
                    f"{record.location}: {STATUS_DEFERRED} 应使用 commit=-，避免伪造真修"
                )
        else:
            errors.append(f"{record.location}: 未知状态 {record.status!r}")

    by_tail: dict[str, list[CloseMemoryRecord]] = {}
    for record in records:
        by_tail.setdefault(record.tail, []).append(record)

    for tail, history in by_tail.items():
        closed: CloseMemoryRecord | None = None
        for record in sorted(
            history, key=lambda item: (item.document_sprint, str(item.path), item.line)
        ):
            if record.status == STATUS_CLOSED:
                closed = record
            elif closed is not None:
                errors.append(
                    f"{record.location}: SSOT 漂移：{tail} 已在 "
                    f"{closed.location} {STATUS_CLOSED}，后续不得回退为 {STATUS_DEFERRED}"
                )

    return errors


def check_docs(docs_root: Path, repo_root: Path) -> tuple[list[CloseMemoryRecord], list[str]]:
    records: list[CloseMemoryRecord] = []
    errors: list[str] = []

    if not docs_root.exists():
        return [], [f"{docs_root}: docs root 不存在"]

    for path in sorted(docs_root.rglob("*.md")):
        parsed, parse_errors = parse_close_memory(path)
        records.extend(parsed)
        errors.extend(parse_errors)

    if not records:
        errors.append(f"{docs_root}: 未找到结构化 {MARKER} 留尾记录，lint 拒绝 no-op")
    errors.extend(validate_records(records, repo_root))
    return records, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L4.20 close-memory SSOT drift lint")
    parser.add_argument("--docs-root", type=Path, default=DEFAULT_DOCS_ROOT)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)

    records, errors = check_docs(args.docs_root, args.repo_root)
    if errors:
        print(f"❌ Found {len(errors)} close-memory SSOT drift violations:")
        for error in errors:
            print(f"  {error}")
        return 1

    closed = sum(record.status == STATUS_CLOSED for record in records)
    deferred = sum(record.status == STATUS_DEFERRED for record in records)
    detail = f"{len(records)} records ({closed} {STATUS_CLOSED}, {deferred} {STATUS_DEFERRED})"
    print(f"✅ SSOT drift lint passed: {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
