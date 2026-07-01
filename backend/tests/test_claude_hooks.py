"""
Tests for Claude Code hooks defined in .claude/settings.json.

Covers:
  - PreToolUse hooks (Edit|Write + Bash, Sprint 178)
  - PostToolUse hooks (Edit|Write + Bash, Sprint 22.5+ / Sprint 175 / Sprint 177)
  - SessionStart + Stop hooks (Sprint 178 session boundary protection)

These tests invoke the same inline python commands the hooks use, pipe
mocked stdin JSON, and assert on exit codes.

Important: the inline hooks use re.match (anchors at start only). They
actually match for relative / shallow paths. For deep absolute paths the
regex fails to bind `$` after a long prefix — that's a documented quirk
this test captures so behavior changes are intentional.
"""

import json
import re
import subprocess
import sys
import textwrap

import pytest

# Inline commands copied verbatim from .claude/settings.json (Sprint 178)
# NOTE: settings.json uses `\$` in the regex; in JSON that's just `$`
# (backslash-dollar has no JSON escape meaning), which is what Python sees.
EDIT_WRITE_BLOCK_ENV_CMD = (
    "python3 -c "
    "\"import sys, json, re; "
    "d=json.loads(sys.stdin.read() or '{}'); "
    "p=d.get('tool_input',{}).get('file_path',''); "
    "bad = re.match(r'(^|/)(.env|.env.local|.env..*.local|data/processed/.*.duckdb)$', p); "
    "sys.exit(2 if bad else 0)\""
)

BASH_BLOCK_DANGEROUS_CMD = textwrap.dedent(
    """
    python3 -c "
    import sys, json, re
    d = json.loads(sys.stdin.read() or '{}')
    cmd = d.get('tool_input', {}).get('command', '')
    forbidden = [
        r'\\bgit\\s+push\\s+.*--force\\b',
        r'\\bgit\\s+push\\s+.*-f\\b(?!or)',
        r'\\brm\\s+-rf?\\s+/\\b',
        r'\\bmkfs\\b',
        r':\\(\\)\\s*\\{\\s*:\\|:\\s*&\\s*\\};:',
        r'\\bdd\\s+if=/dev/(zero|random|urandom)\\s+of=/dev/(sda|nvme|disk)\\b',
        r'\\bchmod\\s+-R\\s+777\\s+/\\b',
    ]
    for pat in forbidden:
        if re.search(pat, cmd):
            print(f'[Sprint 178 PreToolUse Bash] dangerous command blocked: {pat}')
            print(f'   command: {cmd[:200]}')
            sys.exit(2)
    "
    """
).strip()

# Inline command copied verbatim from .claude/settings.json PostToolUse Edit|Write
# (Sprint 22.5+ P0 hooks + Sprint 175 contract reminder). The hook:
#   1) if file_path ends with '.py' → run `ruff check <path>` (silent fail)
#   2) if file_path matches backend/contracts/*.py → print regen-types reminder
#   3) else → no-op, exit 0
# We embed the hook body as a heredoc-style file write + `python3 <tmpfile>`
# because shell-level single/double-quote nesting for `python3 -c "..."`
# inside `subprocess.run(..., shell=True)` is fragile (the test harness's
# shell strips one layer of quotes). Using a temp .py file gives us a
# verbatim port of the hook source — any change to settings.json's hook
# body should also update POST_TOOL_USE_EDIT_WRITE_BODY below.
POST_TOOL_USE_EDIT_WRITE_BODY = '''import sys, json, re, subprocess
d = json.loads(sys.stdin.read() or '{}')
p = d.get('tool_input', {}).get('file_path', '')
if p.endswith('.py'):
    try:
        subprocess.run(['ruff', 'check', p], check=False, timeout=30)
    except Exception:
        pass
if re.search(r'backend/contracts/.*\\.py$', p):
    print('[contract 改动] 提醒: 跑 /regen-types 重新生成 frontend types.ts')
'''


def _run_inline_python(body: str, payload: dict, timeout: int = 15):
    """Write `body` to a tmp .py file and execute it with the JSON payload
    piped to stdin. Mirrors how Claude Code invokes inline `python3 -c`
    hooks (stdin = tool_input JSON), but uses a file instead of `-c`
    to dodge shell-quoting fragility in subprocess.run(shell=True).
    """
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(body)
        result = subprocess.run(
            [sys.executable if False else "python3", path],  # explicit python3
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return result
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

# Inline command copied verbatim from .claude/settings.json PostToolUse Bash
# (Sprint 177 L4.8 hook). On `git push origin main`, runs
# scripts/branch_cleanup.py with 90s timeout. Silent skip on rc!=0.
POST_TOOL_USE_BASH_BODY = '''import sys, json, re, subprocess
d = json.loads(sys.stdin.read() or '{}')
cmd = d.get('tool_input', {}).get('command', '')
if re.search(r'git\\s+push\\s+origin\\s+main', cmd):
    try:
        result = subprocess.run(
            ['python3', 'scripts/branch_cleanup.py'],
            capture_output=True, text=True, timeout=90
        )
        if result.returncode == 0:
            print('[Sprint 177 L4.8 hook] branch_cleanup 完成:')
            print(result.stdout[-1500:])
        else:
            print(f'[Sprint 177 L4.8 hook] branch_cleanup silent skip (rc={result.returncode})')
    except subprocess.TimeoutExpired:
        print('[Sprint 177 L4.8 hook] branch_cleanup timeout (90s) silent skip')
    except Exception as e:
        print(f'[Sprint 177 L4.8 hook] branch_cleanup error: {e}')
'''


def _run_hook(cmd: str, payload: dict) -> int:
    """Run an inline python hook with JSON piped to stdin, return exit code."""
    result = subprocess.run(
        cmd,
        input=json.dumps(payload),
        text=True,
        shell=True,
        capture_output=True,
        timeout=15,
    )
    return result.returncode


class TestPreToolUseHooks:
    """Test the two PreToolUse hooks in .claude/settings.json."""

    # ---- CASE 1: Edit|Write hook blocks .env / .duckdb files ----
    #
    # The hook regex uses re.match + `(^|/)` group + `$` end anchor.
    # re.match anchors at start, so `(^|/)` matches the leading `/` of a
    # deep path, but then the regex engine tries to match `\.env$`
    # IMMEDIATELY after that leading `/`, which fails because the next
    # chars are `Users/...`. Only paths where `.env` is at the very start
    # (`.env`, `/.env`) trigger blocking. This is the hook's actual
    # behavior — we test both shapes to lock it down.

    def test_pre_tool_use_edit_write_blocks_relative_env_file(self):
        """Hook MUST exit 2 when file_path is exactly '.env'."""
        payload = {"tool_input": {"file_path": ".env"}}
        rc = _run_hook(EDIT_WRITE_BLOCK_ENV_CMD, payload)
        assert rc == 2, f"expected exit 2 (block) for '.env', got {rc}"

    def test_pre_tool_use_edit_write_blocks_root_env_file(self):
        """Hook MUST exit 2 when file_path is '/.env'."""
        payload = {"tool_input": {"file_path": "/.env"}}
        rc = _run_hook(EDIT_WRITE_BLOCK_ENV_CMD, payload)
        assert rc == 2, f"expected exit 2 (block) for '/.env', got {rc}"

    def test_pre_tool_use_edit_write_blocks_relative_duckdb(self):
        """Hook MUST exit 2 for relative 'data/processed/*.duckdb'."""
        payload = {"tool_input": {"file_path": "data/processed/fuqing_crm.duckdb"}}
        rc = _run_hook(EDIT_WRITE_BLOCK_ENV_CMD, payload)
        assert rc == 2, f"expected exit 2 (block) for relative .duckdb, got {rc}"

    def test_pre_tool_use_edit_write_allows_normal_py_file(self):
        """Sanity: regular .py file is allowed (exit 0)."""
        payload = {
            "tool_input": {
                "file_path": "/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/backend/services/orders.py"
            }
        }
        rc = _run_hook(EDIT_WRITE_BLOCK_ENV_CMD, payload)
        assert rc == 0, f"expected exit 0 (allow) for .py, got {rc}"

    def test_pre_tool_use_edit_write_breaks_with_broken_regex(self):
        """破坏 → 验证 → 恢复 loop: replace regex with one that matches
        nothing. Then '.env' (which the real hook blocks) MUST slip
        through with exit 0. Proves the regex is what actually blocks.
        """
        broken_cmd = (
            "python3 -c "
            "\"import sys, json, re; "
            "d=json.loads(sys.stdin.read() or '{}'); "
            "p=d.get('tool_input',{}).get('file_path',''); "
            "bad = re.match(r'NO_MATCH_PATTERN_XYZ_12345', p); "
            "sys.exit(2 if bad else 0)\""
        )
        payload = {"tool_input": {"file_path": ".env"}}
        rc = _run_hook(broken_cmd, payload)
        assert rc == 0, (
            f"破坏验证 FAIL: broken regex 期望让 '.env' 漏过 (exit 0), got {rc}. "
            f"如果 rc==2 说明 broken regex 仍命中, 测试不可信"
        )

    # ---- CASE 2: Bash hook blocks dangerous commands ----
    #
    # Trailing `\b` in the hook regex requires a word char after `/`.
    # End-of-string is NOT a word boundary, so `rm -rf /` and `chmod -R
    # 777 /` (lone `/`) are NOT blocked by the actual hook. We test
    # patterns the hook DOES block, plus the two edge cases as
    # documented anti-coverage (exit 0 reveals the hook gap).

    @pytest.mark.parametrize(
        "dangerous_cmd",
        [
            "git push origin main --force",
            "git push origin main -f",
            "rm -rf /tmp",          # hook blocks this (trailing word char)
            "mkfs.ext4 /dev/sda1",
            ":(){ :|:& };:",
            "dd if=/dev/zero of=/dev/sda",
            "chmod -R 777 /tmp",    # hook blocks this (trailing word char)
        ],
    )
    def test_pre_tool_use_bash_blocks_dangerous_commands(self, dangerous_cmd):
        """Dangerous patterns the hook regex actually matches must exit 2."""
        payload = {"tool_input": {"command": dangerous_cmd}}
        rc = _run_hook(BASH_BLOCK_DANGEROUS_CMD, payload)
        assert rc == 2, (
            f"expected exit 2 (block) for '{dangerous_cmd}', got {rc}"
        )

    @pytest.mark.parametrize(
        "edge_cmd",
        [
            "rm -rf /",           # trailing \b fails at EOL → NOT blocked
            "chmod -R 777 /",     # same root-cause
        ],
    )
    def test_pre_tool_use_bash_documents_lone_slash_gap(self, edge_cmd):
        """Document the hook's trailing-\\b gap: lone '/' at EOL is NOT blocked.
        If this assertion ever flips to rc==2, the hook was fixed.

        Sprint 180 follow-up: 2 inline python regex bug (deep path + 裸 / 结尾)
        留 Sprint 181 单独 sprint 治根. 当前 test documents the gap.
        """
        payload = {"tool_input": {"command": edge_cmd}}
        rc = _run_hook(BASH_BLOCK_DANGEROUS_CMD, payload)
        assert rc == 0, (
            f"edge case unexpectedly blocked (rc={rc}); "
            f"if intentionally fixed, move '{edge_cmd}' to blocks test"
        )

    def test_pre_tool_use_bash_allows_safe_push(self):
        """Safe 'git push origin main' (no --force/-f) must be allowed (exit 0)."""
        payload = {"tool_input": {"command": "git push origin main"}}
        rc = _run_hook(BASH_BLOCK_DANGEROUS_CMD, payload)
        assert rc == 0, f"expected exit 0 (allow) for safe push, got {rc}"

    def test_pre_tool_use_bash_allows_normal_ls(self):
        """Sanity: plain `ls -la` is allowed."""
        payload = {"tool_input": {"command": "ls -la"}}
        rc = _run_hook(BASH_BLOCK_DANGEROUS_CMD, payload)
        assert rc == 0, f"expected exit 0 (allow) for ls, got {rc}"


class TestPostToolUseHooks:
    """Test the two PostToolUse hooks in .claude/settings.json.

    CASE 3: Edit|Write hook → ruff check on .py files (silent fail)
    CASE 4: Bash hook → branch_cleanup.py on `git push origin main`
    """

    # ---- CASE 3: Edit|Write PostToolUse hook runs ruff on .py ----
    #
    # The hook ends with an implicit `sys.exit(0)` (last expression is the
    # print on contract path; otherwise the script falls through). ruff
    # failures MUST NOT bubble up — the try/except wraps it as silent skip.
    # We monkeypatch subprocess.run in the hook's own python subprocess is
    # NOT feasible (it's a fresh process), so instead we verify by:
    #   (a) exit code is 0 (silent-fail contract)
    #   (b) stderr is empty (no exception leak)
    #   (c) running the SAME inline command against a known-bad .py file
    #       still exits 0 (ruff finding → swallowed)
    #
    # To prove ruff actually got invoked (not just that the hook is a
    # no-op), we use a path that DOES end with .py but that ruff will
    # reject — if ruff runs, we know the hook reached the subprocess line;
    # if it didn't run, the bad file would never be checked and the hook
    # would still exit 0. So we additionally spy on `ruff` by patching
    # PATH to a wrapper that records the call.

    def test_post_tool_use_edit_write_runs_ruff_on_py(self, tmp_path, monkeypatch):
        """Hook MUST run `ruff check <path>` on .py files and exit 0.

        Verifies:
          1. exit code 0 (silent fail contract)
          2. stderr empty (no exception leak)
          3. ruff is actually invoked (spy via PATH wrapper)
        """
        # Spy: replace `ruff` on PATH with a shell wrapper that records
        # the call and exits 0. The hook invokes `['ruff', 'check', p]`
        # via subprocess.run, which searches PATH.
        import os

        spy_dir = tmp_path / "ruff_spy"
        spy_dir.mkdir()
        spy_log = spy_dir / "ruff_called.log"
        spy_script = spy_dir / "ruff"
        spy_script.write_text(
            "#!/bin/sh\n"
            f"echo \"ruff $@\" >> {spy_log}\n"
            "exit 0\n"
        )
        spy_script.chmod(0o755)
        monkeypatch.setenv(
            "PATH",
            f"{spy_dir}{os.pathsep}" + os.environ.get("PATH", ""),
        )

        payload = {
            "tool_input": {
                "file_path": "/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/backend/__init__.py"
            }
        }
        result = _run_inline_python(POST_TOOL_USE_EDIT_WRITE_BODY, payload)
        assert result.returncode == 0, (
            f"期望 hook exit 0 (silent fail), got rc={result.returncode}; "
            f"stderr={result.stderr!r}"
        )
        assert result.stderr == "", (
            f"期望 hook stderr 空 (silent fail 不抛错), got stderr={result.stderr!r}"
        )
        log_content = spy_log.read_text()
        assert "ruff" in log_content, (
            f"期望 ruff spy 记录到调用, log={log_content!r}; "
            f"说明 hook 没真正跑 ruff, 测试不可信"
        )
        assert "backend/__init__.py" in log_content, (
            f"期望 ruff 被调用时传入 backend/__init__.py, log={log_content!r}"
        )

    def test_post_tool_use_edit_write_silences_ruff_failure(self, tmp_path, monkeypatch):
        """Hook MUST swallow ruff failures (exit non-zero → hook still rc=0)."""
        import os

        spy_dir = tmp_path / "ruff_failing_spy"
        spy_dir.mkdir()
        spy_script = spy_dir / "ruff"
        spy_script.write_text("#!/bin/sh\nexit 1\n")
        spy_script.chmod(0o755)
        monkeypatch.setenv(
            "PATH",
            f"{spy_dir}{os.pathsep}" + os.environ.get("PATH", ""),
        )

        payload = {
            "tool_input": {
                "file_path": "/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/backend/services/orders.py"
            }
        }
        result = _run_inline_python(POST_TOOL_USE_EDIT_WRITE_BODY, payload)
        assert result.returncode == 0, (
            f"期望 hook 静默吞 ruff 失败 (rc=0), got rc={result.returncode}; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    def test_post_tool_use_edit_write_contract_reminder(self, tmp_path, monkeypatch):
        """Hook MUST print regen-types reminder when file is in backend/contracts/."""
        import os

        spy_dir = tmp_path / "ruff_stub"
        spy_dir.mkdir()
        (spy_dir / "ruff").write_text("#!/bin/sh\nexit 0\n")
        (spy_dir / "ruff").chmod(0o755)
        monkeypatch.setenv(
            "PATH",
            f"{spy_dir}{os.pathsep}" + os.environ.get("PATH", ""),
        )

        payload = {
            "tool_input": {
                "file_path": "/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/backend/contracts/schemas.py"
            }
        }
        result = _run_inline_python(POST_TOOL_USE_EDIT_WRITE_BODY, payload)
        assert result.returncode == 0
        assert "regen-types" in result.stdout or "重新生成" in result.stdout, (
            f"期望 hook 提示 regen-types 提醒, stdout={result.stdout!r}"
        )

    # ---- CASE 4: Bash PostToolUse hook triggers branch_cleanup.py ----
    #
    # The hook runs the real scripts/branch_cleanup.py subprocess on
    # `git push origin main`. We mock the *subprocess.run inside the
    # hook* by replacing scripts/branch_cleanup.py with a recording stub
    # that writes its argv to a file. This proves:
    #   (a) the regex `git push origin main` matches our payload
    #   (b) the hook calls subprocess.run with
    #       ['python3', 'scripts/branch_cleanup.py']
    #   (c) the hook exits 0 (silent fail even if branch_cleanup fails)

    def test_post_tool_use_bash_branch_cleanup_on_push_main(self, tmp_path, monkeypatch):
        """Hook MUST trigger branch_cleanup.py on `git push origin main`.

        Strategy: create a fake repo layout in tmp_path (scripts/
        branch_cleanup.py stub), chdir there, run the hook. The stub
        writes a sentinel log proving it was actually invoked.
        """
        fake_repo = tmp_path / "fake_repo"
        (fake_repo / "scripts").mkdir(parents=True)
        log_path = tmp_path / "branch_cleanup_invoked.log"
        stub = fake_repo / "scripts" / "branch_cleanup.py"
        stub.write_text(
            "import sys\n"
            f"open({str(log_path)!r}, 'w').write('CALLED argv=' + repr(sys.argv) + ' ok')\n"
            "sys.exit(0)\n"
        )
        monkeypatch.chdir(fake_repo)

        payload = {"tool_input": {"command": "git push origin main --no-verify"}}
        result = _run_inline_python(POST_TOOL_USE_BASH_BODY, payload, timeout=30)

        assert result.returncode == 0, (
            f"期望 hook exit 0, got rc={result.returncode}; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        # Stub must have been invoked — proves regex matched AND
        # subprocess.run(['python3', 'scripts/branch_cleanup.py']) ran.
        assert log_path.exists(), (
            f"期望 stub scripts/branch_cleanup.py 被 hook 调用, "
            f"但 {log_path} 不存在; 说明 hook 没真跑 subprocess.run"
        )
        log_content = log_path.read_text()
        assert "CALLED" in log_content, (
            f"期望 stub 写 'CALLED' 标记, got {log_content!r}"
        )
        # Bonus: hook's own logging line should appear in stdout.
        assert "branch_cleanup" in result.stdout, (
            f"期望 hook stdout 含 'branch_cleanup' 子串, stdout={result.stdout!r}"
        )

    def test_post_tool_use_bash_skips_branch_cleanup_on_unrelated_command(self):
        """Hook MUST NOT trigger branch_cleanup.py on non-push-main commands."""
        for cmd in ["git status", "ls -la", "git push origin feature/foo", "git push"]:
            payload = {"tool_input": {"command": cmd}}
            result = _run_inline_python(POST_TOOL_USE_BASH_BODY, payload)
            assert result.returncode == 0, (
                f"期望 hook exit 0 for '{cmd}', got rc={result.returncode}"
            )
            assert "branch_cleanup" not in result.stdout, (
                f"期望 hook 不调用 branch_cleanup for '{cmd}', "
                f"stdout={result.stdout!r} (regex 误命中)"
            )


class TestSessionLifecycleHooks:
    """Test SessionStart + Stop hooks in .claude/settings.json.

    CASE 5: SessionStart hook runs scripts/session_start_check.py
    CASE 6: Stop hook runs scripts/session_close_check.py

    Both hooks use the inline shell pattern `python3 <script> || true`,
    which means the hook always exits 0 (silent fail) even if the script
    itself fails. We verify by running the real hook command (not a mock)
    in a tmp cwd where we shadow the target script with a recording stub.
    """

    # ---- CASE 5: SessionStart hook runs session_start_check.py ----
    #
    # The hook in .claude/settings.json SessionStart is literally:
    #     python3 scripts/session_start_check.py || true
    # We mimic this by running the SAME shell command via subprocess.run
    # with shell=True, but with CWD set to a tmp dir where
    # scripts/session_start_check.py is a stub that writes a sentinel
    # log. This proves:
    #   (a) exit code is 0 (the `|| true` tail guarantees it)
    #   (b) scripts/session_start_check.py was actually invoked (sentinel
    #       log exists)
    #   (c) stdin JSON `{}` is accepted (hook doesn't choke on empty input)

    def test_session_start_hook_runs_session_start_check(self, tmp_path, monkeypatch):
        """SessionStart hook MUST run scripts/session_start_check.py and exit 0.

        期望: hook 跑 scripts/session_start_check.py, exit code 0 (silent
        fail, || true 兜底).
        实现: subprocess.run 'python3 scripts/session_start_check.py || true'.
        验证: scripts/session_start_check.py 实际跑 (subprocess 调用, exit 0).
        """
        # Build a fake repo layout in tmp_path so the relative path
        # `scripts/session_start_check.py` resolves to OUR stub, not the
        # real one. The real script may do heavy work (git status, etc.);
        # the stub just records invocation and exits 0.
        fake_repo = tmp_path / "fake_repo_start"
        scripts_dir = fake_repo / "scripts"
        scripts_dir.mkdir(parents=True)
        log_path = tmp_path / "session_start_invoked.log"
        stub = scripts_dir / "session_start_check.py"
        stub.write_text(
            "import sys\n"
            f"open({str(log_path)!r}, 'w').write("
            "'CALLED session_start_check argv=' + repr(sys.argv) + ' ok')\n"
            "sys.exit(0)\n"
        )
        monkeypatch.chdir(fake_repo)

        # Replicate the exact shell command from .claude/settings.json.
        cmd = "python3 scripts/session_start_check.py || true"
        result = subprocess.run(
            cmd,
            input="{}",  # SessionStart hooks receive `{}` JSON on stdin
            text=True,
            shell=True,
            capture_output=True,
            timeout=15,
            cwd=str(fake_repo),
        )

        assert result.returncode == 0, (
            f"期望 hook exit 0 (|| true 兜底), got rc={result.returncode}; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        # Stub must have been invoked — proves the hook reached
        # `python3 scripts/session_start_check.py` (not just no-op'd).
        assert log_path.exists(), (
            f"期望 stub scripts/session_start_check.py 被 hook 调用, "
            f"但 {log_path} 不存在; 说明 hook 没真跑脚本, || true 直接吞了"
        )
        log_content = log_path.read_text()
        assert "CALLED" in log_content, (
            f"期望 stub 写 'CALLED' 标记, got {log_content!r}"
        )

    # ---- CASE 6: Stop hook runs session_close_check.py ----
    #
    # The hook in .claude/settings.json Stop is literally:
    #     python3 scripts/session_close_check.py || true
    # Same pattern as CASE 5: shadow the target script with a recording
    # stub in a tmp cwd, run the hook command, assert exit 0 + sentinel.

    def test_stop_hook_runs_session_close_check(self, tmp_path, monkeypatch):
        """Stop hook MUST run scripts/session_close_check.py and exit 0.

        期望: hook 跑 scripts/session_close_check.py, exit code 0 (silent
        fail, || true 兜底).
        实现: subprocess.run 'python3 scripts/session_close_check.py || true'.
        验证: scripts/session_close_check.py 实际跑 (subprocess 调用, exit 0).
        """
        fake_repo = tmp_path / "fake_repo_stop"
        scripts_dir = fake_repo / "scripts"
        scripts_dir.mkdir(parents=True)
        log_path = tmp_path / "session_close_invoked.log"
        stub = scripts_dir / "session_close_check.py"
        stub.write_text(
            "import sys\n"
            f"open({str(log_path)!r}, 'w').write("
            "'CALLED session_close_check argv=' + repr(sys.argv) + ' ok')\n"
            "sys.exit(0)\n"
        )
        monkeypatch.chdir(fake_repo)

        # Replicate the exact shell command from .claude/settings.json.
        cmd = "python3 scripts/session_close_check.py || true"
        result = subprocess.run(
            cmd,
            input="{}",  # Stop hooks receive `{}` JSON on stdin
            text=True,
            shell=True,
            capture_output=True,
            timeout=15,
            cwd=str(fake_repo),
        )

        assert result.returncode == 0, (
            f"期望 hook exit 0 (|| true 兜底), got rc={result.returncode}; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        # Stub must have been invoked — proves the hook reached
        # `python3 scripts/session_close_check.py`.
        assert log_path.exists(), (
            f"期望 stub scripts/session_close_check.py 被 hook 调用, "
            f"但 {log_path} 不存在; 说明 hook 没真跑脚本, || true 直接吞了"
        )
        log_content = log_path.read_text()
        assert "CALLED" in log_content, (
            f"期望 stub 写 'CALLED' 标记, got {log_content!r}"
        )


# Inline command copied verbatim from .claude/settings.json UserPromptSubmit
# (Sprint 67 L4.12 留尾 SSOT 治理). Hook body is literally:
#     python3 scripts/check_remaining_tasks.py || true
# The matcher `剩余任务|留尾|backlog|todo|剩余待办` is enforced by Claude Code
# (NOT by this hook body); we test the matcher via Python re.search against
# a representative prompt, plus the script invocation via stub shadowing.
USER_PROMPT_SUBMIT_MATCHER = r"剩余任务|留尾|backlog|todo|剩余待办"


class TestUserPromptSubmitHook:
    """Test UserPromptSubmit hook in .claude/settings.json (Sprint 67 L4.12).

    CASE 7: matcher `剩余任务|留尾|backlog|todo|剩余待办` matches representative
            prompts (regex-only check — Claude Code itself enforces matcher
            gating before invoking the hook body). Plus, when the body
            fires, it MUST run `python3 scripts/check_remaining_tasks.py || true`
            (silent-fail contract, exit 0) — we verify via stub shadowing.
    """

    def test_user_prompt_submit_matcher_matches_representative_prompts(self):
        """Matcher regex MUST hit all 5 触发词.

        期望: `re.search` 对每个 触发词 命中, 验证 .claude/settings.json
        里写的 matcher 跟实际 Sprint 67 L4.12 触发词一致.
        """
        prompts = [
            "剩余任务",                # 单 token
            "查一下留尾",               # 子串
            "backlog 状态",            # 英文
            "fix this todo",            # 英文子串
            "看看剩余待办清单",          # 复合
            "看下剩余任务跟留尾",        # 多触发词
        ]
        for prompt in prompts:
            assert re.search(USER_PROMPT_SUBMIT_MATCHER, prompt), (
                f"期望 matcher 命中 prompt={prompt!r}, "
                f"regex={USER_PROMPT_SUBMIT_MATCHER!r}; "
                f"如果不命中, 改 .claude/settings.json matcher regex"
            )

    def test_user_prompt_submit_matcher_rejects_unrelated_prompts(self):
        """Matcher MUST NOT hit 无关 prompt (Sprint 4.21 SSOT 验证配套)."""
        unrelated = [
            "查询复购率",
            "看一下 03 板块",
            "导出 Excel",
            "redeploy uvicorn",
            "今天天气怎么样",
        ]
        for prompt in unrelated:
            assert not re.search(USER_PROMPT_SUBMIT_MATCHER, prompt), (
                f"期望 matcher 不命中无关 prompt={prompt!r}, "
                f"regex={USER_PROMPT_SUBMIT_MATCHER!r}; "
                f"如果命中, matcher 太宽, 误触发"
            )

    def test_user_prompt_submit_runs_check_remaining_tasks(self, tmp_path, monkeypatch):
        """Hook body MUST run scripts/check_remaining_tasks.py (|| true 兜底).

        期望:
          - UserPromptSubmit 触发 (mock stdin JSON 含 '剩余任务 留尾 backlog todo 剩余待办')
          - hook 跑 scripts/check_remaining_tasks.py (subprocess 调用)
          - exit code 0 (silent fail, || true 兜底)
          - matcher regex 验证 prompt 含 触发词

        实现: subprocess.run 跑 `python3 scripts/check_remaining_tasks.py || true`,
        cwd = fake_repo (含 scripts/check_remaining_tasks.py stub), 模拟
        Claude Code 注入 stdin JSON.
        """
        fake_repo = tmp_path / "fake_repo_user_prompt"
        scripts_dir = fake_repo / "scripts"
        scripts_dir.mkdir(parents=True)
        log_path = tmp_path / "check_remaining_tasks_invoked.log"
        stub = scripts_dir / "check_remaining_tasks.py"
        stub.write_text(
            "import sys\n"
            f"open({str(log_path)!r}, 'w').write("
            "'CALLED check_remaining_tasks argv=' + repr(sys.argv) + ' ok')\n"
            "sys.exit(0)\n"
        )
        monkeypatch.chdir(fake_repo)

        # 模拟 UserPromptSubmit 注入的 stdin JSON (Claude Code 实际格式)
        prompt = "剩余任务 留尾 backlog todo 剩余待办"
        payload = {"prompt": prompt}

        # 1) Matcher regex 必须命中 (Claude Code 决定是否 invoke hook body)
        assert re.search(USER_PROMPT_SUBMIT_MATCHER, prompt), (
            f"前置条件 FAIL: matcher 不命中 prompt={prompt!r}, "
            f"regex={USER_PROMPT_SUBMIT_MATCHER!r}"
        )

        # 2) Replicate hook body verbatim from .claude/settings.json
        cmd = "python3 scripts/check_remaining_tasks.py || true"
        result = subprocess.run(
            cmd,
            input=json.dumps(payload),  # UserPromptSubmit 注入 prompt 到 stdin
            text=True,
            shell=True,
            capture_output=True,
            timeout=15,
            cwd=str(fake_repo),
        )

        # 3) Exit code 0 (silent fail contract via || true)
        assert result.returncode == 0, (
            f"期望 hook exit 0 (|| true 兜底), got rc={result.returncode}; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        # 4) Stub must have been invoked — proves hook reached
        #    `python3 scripts/check_remaining_tasks.py`
        assert log_path.exists(), (
            f"期望 stub scripts/check_remaining_tasks.py 被 hook 调用, "
            f"但 {log_path} 不存在; 说明 hook 没真跑脚本, || true 直接吞了"
        )
        log_content = log_path.read_text()
        assert "CALLED" in log_content, (
            f"期望 stub 写 'CALLED' 标记, got {log_content!r}"
        )


class TestClaudeHooksRegression:
    """Sprint 179.1 真因锁回归 — 防止 CI F401 跨 sprint 复发.

    CASE 8 (Sprint 179.1 真因锁回归):
      - 目的: 防 Sprint 179.1 跨 sprint 复发 (CI 5+ 天阻塞,
              root cause = backend/tests/test_branch_cleanup.py:11
              'import sys' unused F401 fail). Sprint 179.1 commit
              3f2a90a 修复后, regression test 锁住 future 不会再
              'unused import' 复发.
      - 静态分析: ruff check --select F401 backend/tests/
              backend/services/sampling_service.py backend/contracts/sampling.py
      - 期望: 0 F401 (unused-import) errors
      - 故意破坏: 在 backend/tests/test_claude_hooks.py 末尾加 1 行
              'import os' (没用), 期望 ruff F401 FAIL, 然后恢复
    """

    # Sprint 179.1 回归 scope (3 处历史 F401 fail 高发区, 跟 commit
    # 3f2a90a 修复路径一致). 任何新增 backend/tests/*.py 必须保持 F401
    # clean.
    F401_TARGETS = [
        "backend/tests/",
        "backend/services/sampling_service.py",
        "backend/contracts/sampling.py",
    ]

    def test_claude_hooks_no_unused_imports_baseline(self):
        """Baseline: ruff F401 静态分析 0 errors (Sprint 179.1 修复后).

        期望: ruff check --select F401 <3 targets> exit 0.
        实现: subprocess.run ruff + parse stdout, 验证 stdout 为空.
        """
        cmd = ["ruff", "check", "--select", "F401", *self.F401_TARGETS]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Sprint 179.1 复发 FAIL: F401 baseline 不干净, rc={result.returncode}; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}; "
            f"scope={self.F401_TARGETS}"
        )
        # stdout 应该为空 (无 violation = 无输出)
        # ruff 在 --select 模式下只报 F401; 没有 violation 时 stdout 完全空
        assert "F401" not in result.stdout, (
            f"期望 stdout 不含 'F401' (代表 0 violations), "
            f"got stdout={result.stdout!r}"
        )

    def test_claude_hooks_no_unused_imports_breaks_when_os_imported(self):
        """破坏 → 验证 → 恢复 loop: 加 unused 'import os' → ruff F401 FAIL.

        目的: 证明 test_claude_hooks_no_unused_imports_baseline 真的能
        抓到 F401 violation (不只是 no-op 永远 PASS).
        实现:
          1. 在 backend/tests/test_claude_hooks.py 末尾 append 'import os'
          2. 跑 ruff F401, 期望 rc != 0 且 stdout 含 F401
          3. (用 try/finally 保证恢复, 不污染仓库)
        """
        target_file = (
            "/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/"
            "backend/tests/test_claude_hooks.py"
        )
        original = None
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                original = f.read()
            # Append unused import on its own line (Sprint 179.1 真因 1:1)
            with open(target_file, "a", encoding="utf-8") as f:
                f.write("\nimport os  # unused: Sprint 179.1 regression test\n")

            # Run ruff F401 against JUST this file (破坏范围最小化)
            cmd = ["ruff", "check", "--select", "F401", target_file]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # 期望破坏验证: rc != 0 + stdout 含 F401 + 含 'import os' 提示
            assert result.returncode != 0, (
                f"破坏验证 FAIL: 加 'import os' 后 ruff 应该 FAIL, "
                f"got rc={result.returncode}; "
                f"stdout={result.stdout!r}; "
                f"说明 baseline 测试不可信, ruff 没真跑"
            )
            assert "F401" in result.stdout, (
                f"破坏验证 FAIL: ruff 报错了但不是 F401, "
                f"stdout={result.stdout!r}"
            )
            assert "import os" in result.stdout or "os" in result.stdout, (
                f"破坏验证 FAIL: ruff 没指出 'import os' 违规, "
                f"stdout={result.stdout!r}"
            )
        finally:
            # 恢复: 严格只删最后 1 行 ('\nimport os  # ...\n'), 防止误改
            if original is not None:
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(original)
            # Verify recovery: ruff F401 应该恢复 PASS
            verify_cmd = ["ruff", "check", "--select", "F401", target_file]
            verify_result = subprocess.run(
                verify_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert verify_result.returncode == 0, (
                f"恢复验证 FAIL: 删 'import os' 后 ruff 仍 FAIL, "
                f"rc={verify_result.returncode}; "
                f"stdout={verify_result.stdout!r} stderr={verify_result.stderr!r}; "
                f"破坏测试可能误改了原文件"
            )
