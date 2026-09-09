"""Historical exemption verifies Git bytes, never only directory names."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("frozen_ground_truth", ROOT / ".githooks/check_review_ground_truth.py")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def test_frozen_snapshot_requires_indexed_manifest_and_bytes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], check=True)
    relative = checker.FROZEN_PLAN + "plan-snapshot/docs/plan.md"
    source = tmp_path / relative
    source.parent.mkdir(parents=True)
    source.write_text("历史：接口不存在\n")
    manifest = tmp_path / checker.FROZEN_PLAN / "PLAN-SNAPSHOT-FILES.sha256"
    manifest.write_text(hashlib.sha256(source.read_bytes()).hexdigest() + "  docs/plan.md\n")
    monkeypatch.setattr(checker, "FROZEN_PLAN_MANIFEST_SHA", hashlib.sha256(manifest.read_bytes()).hexdigest())
    subprocess.run(["git", "add", "."], check=True)
    assert checker.verified_frozen_plan(relative)
    assert not checker.verified_frozen_plan("docs/current.md")
    source.write_text("当前未经验证的声明\n")
    assert checker.verified_frozen_plan(relative), "staged check reads index, not unstaged bytes"
    subprocess.run(["git", "add", "."], check=True)
    assert not checker.verified_frozen_plan(relative)
    manifest.write_text(hashlib.sha256(source.read_bytes()).hexdigest() + "  docs/plan.md\n")
    subprocess.run(["git", "add", "."], check=True)
    assert not checker.verified_frozen_plan(relative), "a new manifest cannot bless edited history"
