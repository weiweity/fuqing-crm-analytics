"""Asset-consuming CI jobs must fetch bytes, not commit LFS pointers."""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("workflow,job_name", [
    ("dsh-b0.yml", "b0-contract-build"),
    ("lint.yml", "frontend"),
    ("lint.yml", "docker-smoke"),
])
def test_asset_consumers_checkout_lfs_without_persisting_credentials(workflow, job_name):
    document = yaml.safe_load((ROOT / ".github/workflows" / workflow).read_text())
    steps = document["jobs"][job_name]["steps"]
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["lfs"] is True
    assert checkout["with"]["persist-credentials"] is False


def test_b0_path_filter_includes_external_assets_and_legacy_seams():
    document = yaml.safe_load((ROOT / ".github/workflows/dsh-b0.yml").read_text())
    # PyYAML's YAML 1.1 loader treats the unquoted Actions key 'on' as True.
    events = document.get("on", document.get(True))
    paths = events["pull_request"]["paths"]
    assert set(paths) >= {
        "frontend-vue3/src/assets/brand/**",
        "frontend-vue3/public/shine-mage-mark.svg",
        "frontend-vue3/src/App.vue",
        "frontend-vue3/src/composables/useFilterSync.ts",
    }
