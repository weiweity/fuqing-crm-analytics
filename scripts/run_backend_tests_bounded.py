#!/usr/bin/env python3
"""Run backend pytest in fresh-process chunks with a hard RSS circuit breaker."""
from __future__ import annotations

import argparse
import json
import hashlib
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import time

import psutil


ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "backend" / "tests"


def _rss_tree_bytes(pid: int) -> int:
    try:
        process = psutil.Process(pid)
        processes = [process, *process.children(recursive=True)]
    except psutil.Error:
        return 0
    total = 0
    for item in processes:
        try:
            total += item.memory_info().rss
        except psutil.Error:
            continue
    return total


def _stop_process_tree(process: subprocess.Popen[bytes]) -> None:
    try:
        children = psutil.Process(process.pid).children(recursive=True)
    except psutil.Error:
        children = []
    for child in children:
        try:
            child.terminate()
        except psutil.Error:
            pass
    process.terminate()
    _, alive = psutil.wait_procs(children, timeout=3)
    for child in alive:
        try:
            child.kill()
        except psutil.Error:
            pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def source_identity() -> dict:
    # Evidence is descriptive, never a key that permits skipping checks.
    files = []
    for folder in ('backend', 'scripts/ci', '.githooks'):
        files.extend(p for p in (ROOT / folder).rglob('*')
                     if p.is_file() and p.suffix in {'.py', '.sh'} and '__pycache__' not in p.parts)
    files.extend(ROOT / p for p in ('pyproject.toml', 'requirements-lock.txt',
                                    'scripts/run_backend_tests_bounded.py',
                                    'scripts/ci/pytest_c_class_deselects.txt'))
    digest = hashlib.sha256()
    for path in sorted(set(files)):
        digest.update(str(path.relative_to(ROOT)).encode() + b'\0')
        digest.update(path.read_bytes())
    git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
    return {'head': git.stdout.strip() if git.returncode == 0 else None,
            'python_check_sources_sha256': digest.hexdigest()}


def pytest_args(targets: list[str], junit: Path) -> list[str]:
    # Same selection for local hooks, PR, nightly and weekly. No result reuse.
    sys.path.insert(0, str(ROOT))
    from scripts.ci.pre_push_path_class import load_deselect_nodeids
    deselects = [arg for node in load_deselect_nodeids() for arg in ('--deselect', node)]
    # Disable the optional plugin with pytest's built-in switch. `-n0` itself
    # requires xdist, which is not installed by the CI lockfile.
    return [sys.executable, '-m', 'pytest', *targets, '-x', '-q', '-p', 'no:xdist',
            '-m', 'not slow', '--durations=10', '-p', 'no:cacheprovider',
            # Dump thread stacks while a test is stuck, before the outer
            # process deadline kills it. This does not relax that deadline.
            '-o', 'faulthandler_timeout=60',
            f'--junitxml={junit}', *deselects]


def isolated_env(scratch: Path) -> dict[str, str]:
    # Never forward user passwords, API tokens, dotenv configuration, pytest
    # options or parent-hook Git repository variables into the test process.
    env = {key: value for key, value in os.environ.items()
           if key in {'PATH', 'SYSTEMROOT', 'WINDIR', 'LANG', 'LC_ALL', 'TERM', 'CI'}}
    home = scratch / 'home'
    tmp = scratch / 'tmp'
    home.mkdir()
    tmp.mkdir()
    env.update(HOME=str(home), TMPDIR=str(tmp), TEMP=str(tmp), TMP=str(tmp),
               PYTHONPATH=str(ROOT), PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1',
               PYTHON_DOTENV_DISABLED='1', PYTHONUNBUFFERED='1',
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               FQ_CRM_PASSWORDS='admin:123456,fqsw:fqsw888,testuser:testpass123',
               FQ_CRM_ADMINS='admin', HEALTH_API_KEY='pytest-health-api-key')
    return env


def run(chunk_size: int, rss_limit_gb: float, targets: list[str],
        report_dir: Path, timeout_seconds: float) -> int:
    tests = targets or [str(p.relative_to(ROOT)) for p in sorted([*TEST_ROOT.glob('test_*.py'),
        ROOT / 'backend/contracts/tests/test_competition_c0.py',
        ROOT / 'backend/services/analytics/competition_diagnosis/tests/test_competition_diagnosis.py'])]
    if not tests:
        raise ValueError('no tests selected')
    report_dir.mkdir(parents=True, exist_ok=False)
    report = {'profile': 'synthetic-not-slow', 'started_at': datetime.now(timezone.utc).isoformat(),
              'python': sys.version, 'source': source_identity(), 'targets': tests, 'groups': [], 'returncode': None}
    result_path = report_dir / 'summary.json'
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix='fq-check-') as scratch_dir:
            env = isolated_env(Path(scratch_dir))
            total_groups = (len(tests) + chunk_size - 1) // chunk_size
            for index in range(0, len(tests), chunk_size):
                group = tests[index:index + chunk_size]
                number = index // chunk_size + 1
                print(f'[bounded-pytest] group {number}/{total_groups}: {len(group)} files', flush=True)
                command = pytest_args(group, report_dir / f'group-{number:03d}.xml')
                group_start = time.monotonic()
                process = subprocess.Popen(command, cwd=ROOT, env=env, start_new_session=True)
                peak = 0
                rc = None
                try:
                    while process.poll() is None:
                        rss = _rss_tree_bytes(process.pid)
                        peak = max(peak, rss)
                        if rss > rss_limit_gb * 1024**3:
                            print(f'[bounded-pytest] RSS limit exceeded: {rss_limit_gb} GB', flush=True)
                            rc = 90
                            break
                        if time.monotonic() - group_start > timeout_seconds:
                            print(f'[bounded-pytest] group timeout: {timeout_seconds}s', flush=True)
                            rc = 91
                            break
                        time.sleep(0.2)
                finally:
                    if process.poll() is None:
                        _stop_process_tree(process)
                if rc is None:
                    rc = int(process.returncode or 0)
                row = {'number': number, 'targets': group, 'command': command,
                       'elapsed_seconds': round(time.monotonic() - group_start, 3),
                       'peak_rss_bytes': peak, 'returncode': rc}
                report['groups'].append(row)
                print(f'[bounded-pytest] group {number} rc={rc} time={row["elapsed_seconds"]}s '
                      f'peak_rss_gb={peak / 1024**3:.2f}', flush=True)
                result_path.write_text(json.dumps(report, indent=2) + '\n')
                if rc:
                    report['returncode'] = rc
                    return rc
        report['returncode'] = 0
        return 0
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        result_path.write_text(json.dumps(report, indent=2) + '\n')
        print(f'[bounded-pytest] report: {result_path}', flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('targets', nargs='*', help='explicit backend test files or nodeids')
    parser.add_argument('--chunk-size', type=int, default=25)
    parser.add_argument('--rss-limit-gb', type=float, default=6.0)
    parser.add_argument('--timeout-seconds', type=float, default=900)
    parser.add_argument('--report-dir', type=Path)
    args = parser.parse_args()
    if args.chunk_size < 1 or args.rss_limit_gb <= 0 or args.timeout_seconds <= 0:
        parser.error('chunk-size, rss-limit-gb and timeout-seconds must be positive')
    for target in args.targets:
        path = (ROOT / target.split('::', 1)[0]).resolve()
        if not path.is_relative_to(TEST_ROOT) or not path.is_file() or not path.name.startswith('test_'):
            parser.error(f'not an existing backend test file: {target}')
    directory = args.report_dir or ROOT / '.context/checks' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    return run(args.chunk_size, args.rss_limit_gb, args.targets, directory.resolve(), args.timeout_seconds)


if __name__ == '__main__':
    raise SystemExit(main())
