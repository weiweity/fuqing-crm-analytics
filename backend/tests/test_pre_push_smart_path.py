"""Track A 2026-07-19: pre-push smart path + C-class deselect SSOT lock regression.

Covers:
1. deselect SSOT has exactly 7 C-class nodeids (sampling 3 + W4 4)
2. path classifier: skip / ruff / full
3. deselect shell helper emits 7 --deselect pairs
4. pre-push / classifier scripts are syntactically valid
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER = REPO_ROOT / "scripts" / "ci" / "pre_push_path_class.py"
DESELECT_TXT = REPO_ROOT / "scripts" / "ci" / "pytest_c_class_deselects.txt"
DESELECT_SH = REPO_ROOT / "scripts" / "ci" / "pytest_deselect_args.sh"
PRE_PUSH = REPO_ROOT / ".githooks" / "pre-push"

EXPECTED_C7 = [
    "backend/tests/test_etl_sample_received_at.py::TestSampleReceivedAtPhase1::test_sampling_service_falls_back_to_pay_time",
    "backend/tests/test_sampling_roi_yoy.py::test_roi_mom_compare_tuple",
    "backend/tests/test_sampling_roi_yoy.py::test_roi_yoy_pct_pp_contract_types",
    "backend/tests/test_w4_t7_integration.py::TestW4T7ActualRun::test_a_w4_t7_actual_run",
    "backend/tests/test_w4_t7_integration.py::TestW4Idempotency::test_b_w4_idempotency",
    "backend/tests/test_w4_t7_integration.py::TestW4VersionIncrement::test_c_w4_version_increment",
    "backend/tests/test_w4_t7_integration.py::TestW4DataQuality::test_d_w4_data_quality",
]


def _load_classifier():
    spec = importlib.util.spec_from_file_location("pre_push_path_class", CLASSIFIER)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def path_class():
    return _load_classifier()


class TestDeselectSSOT:
    def test_ssot_file_exists(self):
        assert DESELECT_TXT.is_file(), f"missing SSOT: {DESELECT_TXT}"

    def test_exactly_7_c_class_nodeids(self, path_class):
        nodeids = path_class.load_deselect_nodeids(DESELECT_TXT)
        assert len(nodeids) == 7, f"expected 7 C-class, got {len(nodeids)}: {nodeids}"
        assert nodeids == EXPECTED_C7

    def test_no_a1_a2_leftovers(self, path_class):
        """pre-push used to deselect w2/rfm_cache — must not return in SSOT."""
        text = DESELECT_TXT.read_text(encoding="utf-8")
        banned = (
            "test_w2_manifest",
            "test_rfm_cache_drop_recreate",
            "test_rfm_cache_write_conn",
            "test_w7_memory_limit",
            "test_startup_validation",
            "test_sampling_sprint139",
            "test_sampling_sprint141",
        )
        for b in banned:
            assert b not in text, f"A1/A2/B leftover in SSOT: {b}"

    def test_deselect_shell_emits_7_pairs(self):
        r = subprocess.run(
            ["bash", str(DESELECT_SH)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert r.returncode == 0, r.stderr
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        # alternating --deselect / nodeid
        flags = [ln for ln in lines if ln == "--deselect"]
        nodeids = [ln for ln in lines if ln != "--deselect"]
        assert len(flags) == 7
        assert len(nodeids) == 7
        assert nodeids == EXPECTED_C7


class TestPathClassify:
    def test_docs_only_skip(self, path_class):
        assert path_class.classify_paths(["docs/TECH-DEBT.md", "CHANGELOG.md"]) == "skip"
        assert path_class.classify_paths(["HANDOFF.md", "STATUS.md"]) == "skip"
        assert path_class.classify_paths(["CLAUDE.md", "README.md"]) == "skip"

    def test_services_full(self, path_class):
        assert path_class.classify_paths(["backend/services/churn.py"]) == "full"
        assert path_class.classify_paths(["backend/main.py"]) == "full"
        assert path_class.classify_paths(["requirements-lock.txt"]) == "full"
        assert path_class.classify_paths(["backend/routers/api.py"]) == "full"
        assert path_class.classify_paths(["backend/middleware/auth.py"]) == "full"
        assert path_class.classify_paths(["backend/db/database.py"]) == "full"

    def test_tests_only_scoped(self, path_class):
        assert path_class.classify_paths(["backend/tests/test_foo.py"]) == "scoped"
        assert (
            path_class.classify_paths(
                ["backend/tests/test_a.py", "docs/TECH-DEBT.md"]
            )
            == "scoped"
        )
        assert (
            path_class.classify_paths(
                ["backend/tests/test_a.py", "backend/services/x.py"]
            )
            == "full"
        )

    def test_scoped_targets(self, path_class):
        targets = path_class.scoped_pytest_targets(
            ["backend/tests/test_a.py", "docs/a.md", "backend/tests/x.json"]
        )
        assert targets == ["backend/tests/test_a.py"]

    def test_scripts_only_ruff(self, path_class):
        assert path_class.classify_paths(["scripts/ci/pre_push_path_class.py"]) == "ruff"
        assert path_class.classify_paths([".githooks/pre-push"]) == "ruff"
        assert path_class.classify_paths(
            ["scripts/branch_cleanup.py", "docs/foo.md"]
        ) == "ruff"

    def test_mixed_docs_and_service_full(self, path_class):
        assert (
            path_class.classify_paths(
                ["docs/a.md", "backend/services/x.py"]
            )
            == "full"
        )

    def test_frontend_only_skip(self, path_class):
        assert (
            path_class.classify_paths(
                ["frontend-vue3/src/App.vue", "frontend-vue3/src/types.ts"]
            )
            == "skip"
        )

    def test_empty_defaults_full(self, path_class):
        assert path_class.classify_paths([]) == "full"

    def test_cli_files_from_stdin(self):
        r = subprocess.run(
            [sys.executable, str(CLASSIFIER), "--files-from", "-"],
            input="docs/a.md\nCHANGELOG.md\n",
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert r.returncode == 0
        assert r.stdout.strip() == "skip"

    def test_cli_list_deselects(self):
        r = subprocess.run(
            [sys.executable, str(CLASSIFIER), "--list-deselects"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert r.returncode == 0
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        assert lines == EXPECTED_C7


class TestPrePushScript:
    def test_pre_push_bash_syntax(self):
        r = subprocess.run(
            ["bash", "-n", str(PRE_PUSH)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert r.returncode == 0, r.stderr

    def test_deselect_sh_bash_syntax(self):
        r = subprocess.run(
            ["bash", "-n", str(DESELECT_SH)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert r.returncode == 0, r.stderr

    def test_classifier_py_compile(self):
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", str(CLASSIFIER)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert r.returncode == 0, r.stderr

    def test_pre_push_uses_ssot_not_hardcoded_a1(self):
        text = PRE_PUSH.read_text(encoding="utf-8")
        assert "pytest_deselect_args.sh" in text or "pytest_c_class_deselects" in text
        assert "test_rfm_cache_drop_recreate" not in text
        assert "test_w2_manifest" not in text
        assert "pre_push_path_class.py" in text

    def test_pre_push_skips_branch_delete_only(self):
        """Regression: git push --delete must not fall through to full pytest."""
        text = PRE_PUSH.read_text(encoding="utf-8")
        assert "SAW_UPDATE" in text
        assert "SAW_DELETE" in text
        assert "Branch delete only" in text
        assert "FQ_PRE_PUSH_SKIP" in text

    def test_delete_only_simulation_exits_0_fast(self):
        """Feed pre-push stdin with delete-only refs; must exit 0 without long pytest."""
        import os

        zero = "0" * 40
        # local_sha=0 → remote branch delete protocol
        stdin = (
            f"refs/heads/dead {zero} "
            f"refs/heads/dead abcdef0123456789abcdef0123456789abcdef01\n"
        )
        env = os.environ.copy()
        env.pop("FQ_PRE_PUSH_SKIP", None)
        env.pop("FQ_PRE_PUSH_MODE", None)
        r = subprocess.run(
            ["bash", str(PRE_PUSH)],
            cwd=str(REPO_ROOT),
            input=stdin,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert "delete" in r.stdout.lower() or "skip" in r.stdout.lower()
        # must not start full suite
        assert "Running full pytest" not in r.stdout
