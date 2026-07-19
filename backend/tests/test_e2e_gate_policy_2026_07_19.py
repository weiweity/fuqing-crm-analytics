"""e2e 门禁分层契约 (2026-07-19): PR 不挡 + 可选极简 smoke.

可合并 = lint + test（lint.yml）。
浏览器 e2e 仅 e2e-smoke.yml（workflow_dispatch / schedule），不挡 PR merge。
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LINT_YML = ROOT / ".github" / "workflows" / "lint.yml"
SMOKE_YML = ROOT / ".github" / "workflows" / "e2e-smoke.yml"
REQ_E2E = ROOT / "requirements-e2e.txt"
REQ_LOCK = ROOT / "requirements-lock.txt"

# ML / OCR 大包：禁止作为 e2e-smoke 依赖（减重 SSOT）
_FORBIDDEN_E2E_DEPS = (
    "torch",
    "torchvision",
    "paddleocr",
    "paddlex",
    "easyocr",
    "sentence-transformers",
    "scrapling",
    "opencv-python",
    "onnxruntime",
)


def _load_yaml(path: Path) -> dict:
    assert path.is_file(), f"missing workflow: {path}"
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), f"invalid yaml: {path}"
    return data


class TestPrCiNoBlockingE2e:
    def test_lint_yml_has_no_e2e_job(self) -> None:
        wf = _load_yaml(LINT_YML)
        jobs = list(wf.get("jobs", {}).keys())
        assert "e2e" not in jobs, f"PR CI 不得含 blocking e2e job, 实际 jobs={jobs}"
        assert "lint" in jobs and "test" in jobs and "ground-truth-lint" in jobs
        assert len(jobs) == 3, f"PR CI 应为 3 jobs (lint/gt/test), 实际 {jobs}"

    def test_lint_yml_text_has_no_playwright_step(self) -> None:
        text = LINT_YML.read_text(encoding="utf-8")
        assert "playwright test" not in text
        assert "npx playwright" not in text

    def test_lint_yml_triggers_on_pr_and_push(self) -> None:
        wf = _load_yaml(LINT_YML)
        on = wf.get("on") or wf.get(True)  # yaml may parse 'on' as True
        # PyYAML 有时把 on: 解析成 True key
        if on is None and True in wf:
            on = wf[True]
        assert on is not None
        assert "pull_request" in on or on.get("pull_request") is not None or "pull_request" in str(on)


class TestOptionalE2eSmoke:
    def test_smoke_workflow_exists_and_not_on_pr(self) -> None:
        wf = _load_yaml(SMOKE_YML)
        on = wf.get("on") or wf.get(True)
        assert on is not None
        on_keys = set(on.keys()) if isinstance(on, dict) else set()
        assert "workflow_dispatch" in on_keys, "smoke 必须可手动触发"
        assert "schedule" in on_keys, "smoke 必须有 nightly schedule"
        assert "pull_request" not in on_keys, "smoke 不得挂 pull_request（否则挡 PR）"
        # push 也不默认挡 main PR 路径；允许无 push 或仅不在 lint 路径
        assert "push" not in on_keys

    def test_smoke_job_uses_minimal_requirements_e2e(self) -> None:
        text = SMOKE_YML.read_text(encoding="utf-8")
        assert "requirements-e2e.txt" in text
        assert "requirements-lock.txt" not in text, "smoke 禁止装全量 lock"
        assert REQ_E2E.is_file()

    def test_requirements_e2e_excludes_ml_ocr_stack(self) -> None:
        # 只扫依赖声明行（name==ver / name>=），忽略注释里的「禁止 torch」字样
        dep_names: set[str] = set()
        for line in REQ_E2E.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            name = s.split("==")[0].split(">=")[0].split("<")[0].split("[")[0].strip()
            dep_names.add(name.lower())
        for pkg in _FORBIDDEN_E2E_DEPS:
            assert pkg.lower() not in dep_names, f"requirements-e2e.txt 禁止声明 {pkg}"
        lock = REQ_LOCK.read_text(encoding="utf-8").lower()
        assert "torch==" in lock  # 对照：全量 lock 仍重

    def test_smoke_runs_login_shell_only(self) -> None:
        text = SMOKE_YML.read_text(encoding="utf-8")
        assert "e2e/login.spec.ts" in text or "login.spec.ts" in text
        # 不得默认跑全量 playwright test 无路径限定
        assert "playwright test e2e/login.spec.ts" in text or (
            "playwright test" in text and "login.spec.ts" in text
        )
        assert "category-detail" not in text
        assert "grep-invert" not in text  # 旧全量排除模式不应出现在 smoke

    def test_smoke_env_schema_test_and_test_mode(self) -> None:
        text = SMOKE_YML.read_text(encoding="utf-8")
        assert any(
            line.strip() == "FQ_DB_MODE: schema_test" for line in text.splitlines()
        )
        assert "FQ_CRM_TEST_MODE" in text and "1" in text
        assert "e2e_duckdb.duckdb" in text
        assert "seed_e2e_duckdb.py" in text
        assert "data/processed/fuqing_crm.duckdb" not in text
        assert "{1..60}" in text  # uvicorn readiness

    def test_smoke_has_playwright_cache(self) -> None:
        text = SMOKE_YML.read_text(encoding="utf-8")
        assert "ms-playwright" in text or "playwright" in text.lower()
        assert "actions/cache" in text
