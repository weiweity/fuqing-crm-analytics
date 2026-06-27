"""Sprint 139 DQM ground-truth-lint: 检查派样正装拆分 SQL 是否到位."""

import re
from pathlib import Path


SAMPLING_SERVICE = Path("backend/services/sampling_service.py")


def check_posize_split_present() -> list[str]:
    """返回缺失的 Sprint 139 正装拆分检查项."""
    text = SAMPLING_SERVICE.read_text(encoding="utf-8")
    checks = [
        (
            "summary_sql has full split",
            r"COUNT\(DISTINCT CASE WHEN r\.days_between <= 30 AND r\.spu_type = '正装'",
        ),
        (
            "cat_sql has full split",
            r"COUNT\(DISTINCT CASE WHEN r\.spu_type = '正装' THEN r\.user_id END\) as full_repurchase_users",
        ),
        (
            "period_sql has spu_type",
            r"days_between BETWEEN 1 AND 3 AND spu_type = '正装'",
        ),
        (
            "return has period_distribution",
            r"'period_distribution': period_distribution",
        ),
        (
            "return has quality_flags",
            r"'quality_flags': quality_flags",
        ),
        (
            "repurchase CTE has spu_type",
            r"COALESCE\(o\.spu_type, '未知'\) as spu_type",
        ),
    ]

    failures = []
    for name, pattern in checks:
        if not re.search(pattern, text):
            failures.append(f"{name}: pattern not found")
    return failures


if __name__ == "__main__":
    missing = check_posize_split_present()
    if missing:
        for failure in missing:
            print(f"FAIL: {failure}")
        raise SystemExit(1)

    print("PASS: sampling_service.py Sprint 139 正装拆分 6 处全部到位")
