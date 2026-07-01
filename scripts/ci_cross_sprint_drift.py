"""Sprint 188 B4: 跨 sprint CI 隐式 fail 自动检测脚手架.

防 Sprint 182→187 累计 5 sprint 隐式 fail 模式复发 (test_subprocess_inherits_pythonpath
100% 在 Linux GitHub Actions runner fail 但 macOS 本地 100% pass). 本脚本对最近 N 个
main commit 重跑特定 pytest test, 跨 commit 验证测试输出无 drift.

设计原则 (跟 L4.32 cwd lock + L4.41 PYTHONPATH 永久规则同位):

1. **不破坏当前 main HEAD**: 用 `git worktree add` 在 /tmp 创建 detached HEAD
   worktree 跑 pytest, 跑完 `git worktree remove` 清. 父仓 git status 始终干净.
2. **超时 + 隔离**: 每个 commit 单独 worktree, 单独 pytest 进程, 失败互不影响.
3. **advisory mode**: 永远 exit 0 (跟 check_e2e_spec_drift.py Sprint 168 模式一致),
   drift 检测结果打到 stdout, 留给 review skill / ground-truth-lint 当参考.

Sprint 188 范围 (~80 行):

- 取最近 N=10 commit SHA + commit message
- 对每个 commit 创建 /tmp worktree + 跑 pytest test path
- 收集每个 commit 的 (sha, returncode, duration_s, output_summary)
- 报告: PASS 数 / FAIL 数 / FAIL commit SHA + message
- advisory: exit 0 永远, 但 FAIL > 0 时打 WARNING

Sprint 188+ 真业务触发时考虑扩展:
- N 改成 30 (跨 sprint 更深)
- 加 --test-path 参数跑多个 test (不只 test_subprocess_inherits_pythonpath)
- 加 --commits N 自定义范围
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# 配置 (跟 scripts/check_e2e_spec_drift.py 风格一致)
# ─────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEST_PATH = (
    "backend/tests/test_fuqing_adhoc_mcp_server.py::TestRunCliSubprocess::"
    "test_subprocess_inherits_pythonpath"
)
DEFAULT_N_COMMITS = 10
TIMEOUT_SECONDS = 60  # 单 test 跑超时 (L4.41 fix 后应 < 1s, 60s 留 headroom)


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run subprocess 返 CompletedProcess (text mode)."""
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def get_recent_commits(n: int = DEFAULT_N_COMMITS) -> list[tuple[str, str]]:
    """返最近 N commit 的 [(sha, message_short), ...] 列表 (newest first).

    用 `git log --pretty=format:'%H %s'` 拿 SHA + first line of commit message.
    """
    result = _run(
        ["git", "log", "--pretty=format:%H %s", f"-{n}", "main"],
        cwd=REPO_ROOT,
        timeout=15,
    )
    if result.returncode != 0:
        print(f"❌ git log failed: rc={result.returncode}, stderr={result.stderr[:300]}")
        return []
    commits: list[tuple[str, str]] = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        # 格式: "<sha> <message>" — SHA 是前 40 hex chars
        sha, _, message = line.partition(" ")
        if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha):
            commits.append((sha, message))
    return commits


def run_pytest_in_worktree(sha: str, test_path: str, worktree_dir: Path) -> tuple[int, float, str]:
    """在 detached HEAD worktree 跑 pytest, 返 (returncode, duration_s, output_tail).

    实现:
    1. `git worktree add <dir> <sha>` (detached HEAD)
    2. PYTHONPATH=. python3 -m pytest <test_path> -v (走真实 Python, 验证 L4.41)
    3. `git worktree remove --force <dir>`
    """
    # 清理残留 worktree (防御 Sprint 188 跑批中断遗留)
    if worktree_dir.exists():
        shutil.rmtree(worktree_dir, ignore_errors=True)

    # 1. 创建 worktree (detached HEAD on <sha>)
    add_proc = _run(
        ["git", "worktree", "add", "--detach", str(worktree_dir), sha],
        cwd=REPO_ROOT,
        timeout=30,
    )
    if add_proc.returncode != 0:
        return (
            -1,
            0.0,
            f"worktree add failed: {add_proc.stderr[:200]}",
        )

    # 2. 跑 pytest (用系统 python3, 跟 GitHub Actions runner 一致)
    start = time.monotonic()
    try:
        pytest_proc = subprocess.run(
            [sys.executable, "-m", "pytest", test_path, "-v", "--no-header"],
            cwd=str(worktree_dir),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            env={"PYTHONPATH": str(worktree_dir), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
        )
        duration = time.monotonic() - start
        output_tail = pytest_proc.stdout[-300:] + pytest_proc.stderr[-200:]
        return pytest_proc.returncode, duration, output_tail
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - start
        return -2, duration, f"TIMEOUT after {TIMEOUT_SECONDS}s"
    finally:
        # 3. 清理 worktree (force 避免 uncommitted file 卡)
        _run(
            ["git", "worktree", "remove", "--force", str(worktree_dir)],
            cwd=REPO_ROOT,
            timeout=30,
        )


def check_drift(
    n_commits: int = DEFAULT_N_COMMITS,
    test_path: str = DEFAULT_TEST_PATH,
) -> int:
    """主入口: 跑跨 sprint drift 检测, advisory 模式永远 exit 0.

    返 0 永远 (跟 scripts/check_e2e_spec_drift.py 风格一致).
    drift 详情打到 stdout 留给 review skill / ground-truth-lint.
    """
    print("=" * 60)
    print("Sprint 188 B4: 跨 sprint CI drift 自动检测 (advisory)")
    print(f"Test: {test_path}")
    print(f"Commits: 最近 {n_commits} on main")
    print("=" * 60)
    print()

    commits = get_recent_commits(n_commits)
    if not commits:
        print("⚠️  无法取 commits (git log 失败), skip")
        return 0

    print(f"扫 {len(commits)} commits, 逐个建 worktree 跑 pytest...")
    print()

    results: list[tuple[str, str, int, float, str]] = []
    # (sha, message, rc, duration, tail)

    with tempfile.TemporaryDirectory(prefix="fq-drift-wt-") as tmp_root:
        tmp_dir = Path(tmp_root)
        for i, (sha, message) in enumerate(commits, start=1):
            short_sha = sha[:8]
            wt_dir = tmp_dir / short_sha
            print(f"[{i}/{len(commits)}] {short_sha} {message[:60]}")
            rc, duration, tail = run_pytest_in_worktree(sha, test_path, wt_dir)
            status = "PASS" if rc == 0 else f"FAIL (rc={rc})"
            print(f"           {status} in {duration:.2f}s")
            if rc != 0:
                print(f"           tail: {tail[:200]!r}")
            results.append((sha, message, rc, duration, tail))

    # 汇总
    print()
    print("=" * 60)
    n_pass = sum(1 for _, _, rc, _, _ in results if rc == 0)
    n_fail = len(results) - n_pass
    print(f"汇总: {n_pass} PASS / {n_fail} FAIL (共 {len(results)} commits)")

    if n_fail > 0:
        print()
        print("⚠️  DRIFT DETECTED (advisory):")
        for sha, message, rc, duration, tail in results:
            if rc != 0:
                print(f"  - {sha[:8]} rc={rc} ({duration:.2f}s): {message[:80]}")
                print(f"      tail: {tail[:150]!r}")
        print()
        print("💡 Sprint 187 真因: test_subprocess_inherits_pythonpath 在 macOS PASS, 但")
        print("   Linux GitHub Actions runner `actions/setup-python@v6` 默认 `PYTHONPATH=.`")
        print("   literal → 子 Python 找不到 backend.services → 100% FAIL.")
        print("   修复: mcp_servers/fuqing_adhoc/server.py:_run_cli 改用 `_PYTHONPATH = _CWD`")
        print("   强制绝对路径, 不 inherit 父进程 (L4.41 永久规则).")
    else:
        print()
        print("✅ 0 drift — 所有 commit 该 test 都 PASS")

    print()
    print("⚠️  Advisory only — exit 0 永远. drift 详情供 review skill 参考.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sprint 188 B4: 跨 sprint CI drift 检测")
    parser.add_argument(
        "--n-commits", type=int, default=DEFAULT_N_COMMITS,
        help=f"最近 N commits (default: {DEFAULT_N_COMMITS})",
    )
    parser.add_argument(
        "--test-path", type=str, default=DEFAULT_TEST_PATH,
        help=f"pytest test path (default: {DEFAULT_TEST_PATH})",
    )
    args = parser.parse_args()
    return check_drift(n_commits=args.n_commits, test_path=args.test_path)


if __name__ == "__main__":
    sys.exit(main())