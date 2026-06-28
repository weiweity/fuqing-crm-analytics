"""Sprint 141 ground-truth-lint: 验证 61-90d 周期桶和 sync-agents 精准替换."""

import re
import sys
from pathlib import Path


CHECKS = [
    (
        Path("backend/contracts/sampling.py"),
        "contract has bucket_61_90d",
        r"bucket_61_90d: int = 0",
    ),
    (
        Path("backend/contracts/sampling.py"),
        "contract has full_bucket_61_90d",
        r"full_bucket_61_90d: int = 0",
    ),
    (
        Path("backend/contracts/sampling.py"),
        "QualityFlag descriptions",
        r"code: str = Field\(\.\.\., description=",
    ),
    (
        Path("backend/services/sampling_service.py"),
        "period_sql has total 61-90d bucket",
        r"days_between BETWEEN 61 AND 90 THEN user_id END\) as bucket_61_90d",
    ),
    (
        Path("backend/services/sampling_service.py"),
        "period_sql has full 61-90d bucket",
        r"days_between BETWEEN 61 AND 90 AND spu_type = '正装' THEN user_id END\) as full_bucket_61_90d",
    ),
    (
        Path("frontend-vue3/src/api/sampling.ts"),
        "manual TS API has 61-90d fields",
        r"bucket_61_90d: number[\s\S]*full_bucket_61_90d: number",
    ),
    (
        Path("frontend-vue3/src/views/SamplingView.vue"),
        "SamplingView renders 61-90d bucket",
        r"label: '61-90天'",
    ),
    (
        Path("frontend-vue3/src/views/SamplingView.vue"),
        "SamplingView uses 5 column grid",
        r"grid-cols-5 gap-3",
    ),
    (
        Path("scripts/sync-agents.sh"),
        "sync-agents copies before precise replacements",
        r"cp CLAUDE\.md AGENTS\.md",
    ),
    (
        Path("scripts/sync-agents.sh"),
        "sync-agents only rewrites title line",
        r"if \(\$\. == 1\) \{ s/CLAUDE\\.md/AGENTS.md/g \}",
    ),
]


def run_checks() -> list[str]:
    """返回缺失的 Sprint 141 真值检查项."""
    failures = []
    for file_path, name, pattern in CHECKS:
        if not file_path.exists():
            failures.append(f"{name}: {file_path} not found")
            continue
        text = file_path.read_text(encoding="utf-8")
        if not re.search(pattern, text):
            failures.append(f"{name}: pattern not found in {file_path}")

    sync_text = Path("scripts/sync-agents.sh").read_text(encoding="utf-8")
    if re.search(r"sed[\s\\\n]+.*CLAUDE\\\.md/AGENTS\.md", sync_text):
        failures.append("sync-agents still has global sed CLAUDE.md -> AGENTS.md replacement")
    return failures


if __name__ == "__main__":
    missing = run_checks()
    if missing:
        for failure in missing:
            print(f"FAIL: {failure}")
        sys.exit(1)

    print("PASS: Sprint 141 61-90d 周期桶 + sync-agents 精准替换检查通过")
