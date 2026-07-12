#!/usr/bin/env python3
"""按行数把 CHANGELOG.md 的旧条目归档到 docs/history/CHANGELOG_HISTORY.md。"""

import os
import re
from pathlib import Path

MAX_LINES = 900
HEADING = re.compile(r"^## (?:Sprint|\[)")


def atomic_write(path: Path, content: str) -> None:
    """在目标文件所在目录写临时文件，再原子替换。"""
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def archive(target_lines: int = MAX_LINES) -> bool:
    changelog_path = Path("CHANGELOG.md")
    history_path = Path("docs/history/CHANGELOG_HISTORY.md")
    lines = changelog_path.read_text(encoding="utf-8").splitlines(keepends=True)
    if len(lines) <= target_lines:
        print(f"CHANGELOG.md 已 <= {target_lines} 行 ({len(lines)} 行)，无需归档")
        return False

    boundaries = [i for i, line in enumerate(lines) if HEADING.match(line)]
    cut_idx = max((i for i in boundaries if i <= target_lines), default=None)
    if cut_idx is None:
        raise ValueError(f"前 {target_lines} 行内找不到可归档的 heading 边界")

    kept = "".join(lines[:cut_idx])
    archived = "".join(lines[cut_idx:]).rstrip() + "\n\n"
    history = history_path.read_text(encoding="utf-8")
    atomic_write(history_path, archived + history)
    atomic_write(changelog_path, kept)
    print(f"归档 {len(lines) - cut_idx} 行，CHANGELOG.md 保留 {cut_idx} 行")
    return True


if __name__ == "__main__":
    archive()
