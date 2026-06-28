"""Sprint 140 ground-truth-lint: 验证 SamplingChannelSummary 旧窗口字段 0 残留."""

import re
import sys
from pathlib import Path


OLD_FIELD_PATTERNS = [
    r"repurchase_users_7d",
    r"repurchase_users_60d",
    r"repurchase_gsv_7d",
    r"repurchase_gsv_60d",
    r"repurchase_aus_7d",
    r"repurchase_aus_60d",
    r"repurchase_rate_7d",
    r"repurchase_rate_60d",
    r"repurchase_users_30d",
    r"repurchase_gsv_30d",
    r"repurchase_aus_30d",
    r"repurchase_rate_30d",
    r"full_repurchase_users_30d",
    r"full_repurchase_gsv_30d",
    r"full_repurchase_aus_30d",
    r"full_repurchase_rate_30d",
    r"nonfull_repurchase_users_30d",
    r"nonfull_repurchase_gsv_30d",
    r"nonfull_repurchase_aus_30d",
]

FILES_TO_CHECK = [
    Path("backend/contracts/sampling.py"),
    Path("frontend-vue3/src/api/sampling.ts"),
    Path("frontend-vue3/src/views/SamplingView.vue"),
]


def check_no_old_fields() -> list[str]:
    """返回仍残留旧窗口字段的检查项."""
    failures = []
    for file_path in FILES_TO_CHECK:
        if not file_path.exists():
            continue
        text = file_path.read_text(encoding="utf-8")
        for pattern in OLD_FIELD_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                failures.append(f"{file_path}: pattern {pattern} found {len(matches)} times")
    return failures


if __name__ == "__main__":
    failures = check_no_old_fields()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        sys.exit(1)

    print(f"PASS: Sprint 140 统一字段完成，{len(OLD_FIELD_PATTERNS)} 个旧字段名 0 残留")
