"""
Sprint 66 P0 治根: lint.yml e2e job 必须设 FQ_DB_MODE=schema_test

反向教训: Sprint 63 P1b 只改了 .github/workflows/e2e.yml (独立 e2e workflow),
但 CI workflow 的 e2e job 在 .github/workflows/lint.yml line 67 也需要 FQ_DB_MODE=schema_test.
Sprint 64+65 CI test+e2e 双 FAILURE 5+sprint 复发.

Sprint 123 R2 CI 跑 e2e (Sprint 34 候选 4) 集成: e2e.yml 删, e2e job 移到 lint.yml.
Sprint 123 必修 2 真因真修 2/3: test 改读 lint.yml 验证 e2e job 仍含 FQ_DB_MODE=schema_test.

治根: lint CI yml 文件强制 e2e job 含 FQ_DB_MODE=schema_test.

CI 留尾 ROI 重评 (CLAUDE.md L5.1): 治本 < 1 天闭环 + 0 复发 → 治本.
这个 lint 0.1d 闭环, 防下次 lint.yml 改回忘了 env 又复发.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


# Sprint 96.5 必修 2 真因真修 (7 sprint 完整链路全闭环, 跟 Sprint 88+92+92.1 模式 2 sprint 延展):
# Sprint 96.4 删 lint.yml e2e job 整段 (跟 Sprint 32.1 留尾 advisory 一致, e2e.yml 独立 workflow 4m26s 跑通),
# 2 个 lint.yml e2e job 相关 test 必修 2 误诊真因真发现 (e2e job 删了, test 找不到了 FQ_DB_MODE + e2e_duckdb.duckdb).
# 必修 2 真因真修 (Sprint 96.5): 删 2 个 lint.yml e2e job 相关 test 整段, 保留 e2e.yml 独立 workflow 相关 test (e2e.yml 4m26s 跑通).
#
# Sprint 123 必修 2 真因真修 2/3: e2e.yml 删, e2e job 移到 lint.yml, 1 个 test_ci_workflows_fq_db_mode.py 必修 2 真因真修
# 改读 lint.yml 验证 e2e job 仍含 FQ_DB_MODE=schema_test (跟 test_ci_e2e_env_config.py 同步).
def test_e2e_yml_e2e_job_sets_fq_db_mode_schema_test():
    """lint.yml e2e job env 必须含 FQ_DB_MODE=schema_test (Sprint 66 P0 + Sprint 123 集成).

    Sprint 123 集成后: e2e.yml 删, e2e job 移到 lint.yml. test 改读 lint.yml.
    防再发: Sprint 63 P1b 修了独立 e2e workflow 但漏 CI workflow 的 e2e job (在 lint.yml).
    """
    lint_yml = (ROOT / ".github" / "workflows" / "lint.yml").read_text()
    assert any(
        line.strip() == "FQ_DB_MODE: schema_test"
        for line in lint_yml.splitlines()
    ), (
        "lint.yml e2e job env 必须设 FQ_DB_MODE=schema_test (Sprint 66 P0 + Sprint 123 集成). "
        "缺这个 env 会导致 Sprint 61 fail-fast 默认 production raise, "
        "uvicorn 60s 起不来, e2e exit 1."
    )