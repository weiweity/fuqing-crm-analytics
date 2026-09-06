"""The commit gate reads Git index blobs; unrelated/unstaged files cannot change it."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/check_l4_91_excel_export_ssot.py'


@pytest.fixture
def index_repo(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    def git(*args):
        return subprocess.run(['git', *args], cwd=tmp_path, env=env,
                              capture_output=True, text=True, check=True)
    git('init', '-b', 'main')
    views = tmp_path / 'frontend-vue3/src/views'
    views.mkdir(parents=True)
    def lint(*args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=tmp_path,
                              env=env, text=True, capture_output=True, timeout=10)
    return views, git, lint


@pytest.mark.parametrize('source,rule', [
    ("import XLSX from 'xlsx'", 'R1'),
    ('const cell = { f: "=1+1" }', 'R2'),
    ('const value = row.old_ratio * 100', 'R3'),
    ("const cols: XlsxColumn[] = [\n{ header: '同比', key: 'gsv_yoy' },\n]", 'R4'),
])
def test_staged_violation_is_not_hidden_by_unstaged_fix(index_repo, source, rule):
    views, git, lint = index_repo
    view = views / 'Changed.vue'
    view.write_text(source)
    git('add', 'frontend-vue3/src/views/Changed.vue')
    view.write_text('<template>clean working copy</template>')
    result = lint('--staged')
    assert result.returncode == 1 and rule in result.stdout


def test_unrelated_legacy_and_unstaged_changes_remain_in_full_audit(index_repo):
    views, git, lint = index_repo
    (views / 'Legacy.vue').write_text("import XLSX from 'xlsx'")
    git('add', '.')
    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test',
        'commit', '-m', 'existing legacy fixture')
    clean = views / 'Changed.vue'
    clean.write_text('<template>clean staged view</template>')
    git('add', 'frontend-vue3/src/views/Changed.vue')
    clean.write_text("import XLSX from 'xlsx'")
    assert lint('--staged').returncode == 0
    audit = lint('--views-root', str(views))
    assert audit.returncode == 1 and '2 violations' in audit.stdout


def test_staged_rename_is_checked_and_missing_git_fails_closed(index_repo, tmp_path):
    views, git, lint = index_repo
    outside = tmp_path / 'legacy.ts'
    outside.write_text("import XLSX from 'xlsx'")
    git('add', '.')
    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test',
        'commit', '-m', 'fixture outside view scope')
    git('mv', 'legacy.ts', 'frontend-vue3/src/views/New.ts')
    assert lint('--staged').returncode == 1
    outside_git = subprocess.run([sys.executable, str(SCRIPT), '--staged'],
                                 cwd=tmp_path.parent, capture_output=True, text=True, timeout=10)
    assert outside_git.returncode == 2
