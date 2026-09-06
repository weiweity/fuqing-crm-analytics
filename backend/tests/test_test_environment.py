"""Regression coverage for isolation and the cost of the real pytest fixtures."""
from __future__ import annotations

import ast
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_plain_pytest_does_not_import_app_or_touch_previous_sessions(tmp_path):
    suite = tmp_path / "suite"
    suite.mkdir()
    shutil.copyfile(ROOT / 'backend/tests/conftest.py', suite / 'conftest.py')
    previous = tmp_path / 'previous-session'
    previous.mkdir()
    sentinel = previous / 'keep.txt'
    sentinel.write_text('owned by a different session')
    (suite / 'test_plain.py').write_text('''
import os, sys
def test_plain():
    assert 'backend.main' not in sys.modules
    assert 'backend.routers.auth' not in sys.modules
    assert 'scripts.etl.cli' not in sys.modules
    assert os.environ['PYTHON_DOTENV_DISABLED'] == '1'
    assert 'not-configured.duckdb' in os.environ['DUCKDB_PATH']
''')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('GIT_', 'FQ_'))}
    env.update(PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1',
               PYTHON_DOTENV_DISABLED='1')
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                             str(suite)], cwd=tmp_path, env=env, capture_output=True,
                            text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert sentinel.read_text() == 'owned by a different session'


def test_credential_fixture_uses_cached_hashes_and_restores_snapshot(monkeypatch):
    import bcrypt
    from backend.tests import conftest as fixtures
    from backend.routers import auth

    expected = dict(fixtures._synthetic_password_hashes())
    original = dict(auth.VALID_CREDENTIALS)

    def forbidden_rehash(*args, **kwargs):
        raise AssertionError('ordinary fixture rehashed credentials')

    monkeypatch.setattr(bcrypt, 'hashpw', forbidden_rehash)
    monkeypatch.setattr(auth, '_load_credentials', forbidden_rehash)
    with pytest.MonkeyPatch.context() as patch:
        fixture = fixtures._reset_fq_crm_credentials_env.__wrapped__(patch)
        next(fixture)
        assert dict(auth.VALID_CREDENTIALS) == expected
        auth.VALID_CREDENTIALS['changed-by-test'] = 'test-only'
        with pytest.raises(StopIteration):
            next(fixture)
    assert auth.VALID_CREDENTIALS == original


def test_cached_hashes_preserve_real_bcrypt_cost_and_passwords():
    import bcrypt
    from backend.tests import conftest as fixtures
    from backend.routers import auth

    hashes = fixtures._synthetic_password_hashes()
    for user, password in (p.split(':', 1) for p in fixtures._TEST_CREDENTIALS_ENV.split(',')):
        assert int(hashes[user].split('$')[2]) == auth.BCRYPT_ROUNDS == 12
        assert bcrypt.checkpw(password.encode(), hashes[user].encode())


def test_archive_detection_without_profile_never_connects(monkeypatch):
    import duckdb
    from backend.tests import conftest as fixtures

    monkeypatch.delenv('FQ_TEST_ARCHIVE_DB', raising=False)
    def forbidden_connect(*args, **kwargs):
        raise AssertionError('implicit database access')
    monkeypatch.setattr(duckdb, 'connect', forbidden_connect)
    assert fixtures._detect_prod_duckdb_available() is False
    assert fixtures._duckdb_lock_holder_pid() is None


def test_test_collection_has_no_top_level_environment_mutations():
    violations = []
    for path in (ROOT / 'backend/tests').glob('test_*.py'):
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.Assign):
                if any(isinstance(target, ast.Subscript) and ast.unparse(target.value) == 'os.environ'
                       for target in node.targets):
                    violations.append(f'{path.name}:{node.lineno}')
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                if ast.unparse(node.value.func) in ('os.environ.setdefault', 'os.environ.update'):
                    violations.append(f'{path.name}:{node.lineno}')
    assert not violations, violations
