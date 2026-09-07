"""Asset-consuming CI jobs must fetch bytes, not commit LFS pointers."""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("workflow,job_name", [
    ("lint.yml", "b0-contract-build"),
    ("lint.yml", "frontend"),
    ("lint.yml", "docker-smoke"),
    ("dsh-b0.yml", "b0-contract-build"),
])
def test_asset_consumers_checkout_lfs_without_persisting_credentials(workflow, job_name):
    document = yaml.safe_load((ROOT / ".github/workflows" / workflow).read_text())
    steps = document["jobs"][job_name]["steps"]
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["lfs"] is True
    assert checkout["with"]["persist-credentials"] is False


@pytest.mark.parametrize('path', [
    'frontend-vue3/src/assets/brand/logo.png',
    'frontend-vue3/public/shine-mage-mark.svg',
    'frontend-vue3/src/App.vue',
    'frontend-vue3/src/composables/useFilterSync.ts',
])
def test_b0_path_filter_includes_external_assets_and_legacy_seams(path):
    from scripts.ci.pre_push_path_class import verification_plan
    document = yaml.safe_load((ROOT / '.github/workflows/lint.yml').read_text())
    events = document.get('on', document.get(True))
    assert 'pull_request' in events
    assert document['jobs']['changes']['uses'] == './.github/workflows/check-plan.yml'
    assert "needs.changes.outputs.b0 == 'true'" in document['jobs']['b0-contract-build']['if']
    dispatch = yaml.safe_load((ROOT / '.github/workflows/dsh-b0.yml').read_text())
    dispatch_on = dispatch.get('on', dispatch.get(True))
    assert 'pull_request' not in dispatch_on
    assert 'workflow_dispatch' in dispatch_on
    assert 'changes' not in dispatch['jobs']
    assert verification_plan([path])['b0'] is True
