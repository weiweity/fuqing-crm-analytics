#!/usr/bin/env python3
"""check_remaining_tasks.py — Sprint 67 留尾 SSOT 治理 (L4.12 配套)

极简: grep docs/TECH-DEBT.md 所有 "- 📋" bullet, 排除 "- ✅" 已闭环.
Fail-open: 任何异常 exit 0 + stderr warn, 不阻塞 session 启动.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ITEM_RE = re.compile(r"^- 📋 \*\*([^*]+)\*\*[::]?\s*(.*)$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tech-debt", help="TECH-DEBT.md 路径 (default: repo/docs/TECH-DEBT.md)")
    args = parser.parse_args()
    td = Path(args.tech_debt) if args.tech_debt else REPO / "docs" / "TECH-DEBT.md"
    try:
        if not td.exists():
            print(json.dumps({"remaining": [], "warning": f"{td} not found"}, ensure_ascii=False))
            return 0
        items = []
        for line in td.read_text(encoding="utf-8").splitlines():
            m = ITEM_RE.match(line.lstrip())
            if m:
                items.append({"title": m.group(1).strip(), "desc": m.group(2).strip()[:200]})
        print(json.dumps({"remaining": items, "fetched_at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(f"[check_remaining_tasks] warn: {type(e).__name__}: {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
