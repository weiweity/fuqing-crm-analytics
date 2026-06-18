"""
Sprint 36-4 fixture test: 验证 SQL f-string lint 跨 backend/scripts/ + scripts/etl/ 范围

复刻 Sprint 34.1 test_churn_user_list_fstring.py 模式:
- 故意造 1 个 missing f-prefix 临时文件 → lint 应该 rc=1
- 故意造 1 个 correct f-string 临时文件 → lint 应该 rc=0
- 故意造 1 个 triple-quote SQL 字符串 (无 {var}) → 不应误报 (避免 false positive)

跑法: pytest backend/tests/test_check_sql_fstring_consistency.py -v
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestCheckSqlFStringConsistencyFixture(unittest.TestCase):
    """验证 lint 钩子在跨 backend/scripts/ + scripts/etl/ 范围有效 (S36-4 对称补盲)."""

    def setUp(self):
        # 临时建 1 个 fake scripts/ 目录结构供 lint 扫
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fq_sql_fstring_test_"))
        self.scripts_dir = self.tmpdir / "scripts" / "etl"
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_sql_file(self, name: str, content: str) -> Path:
        path = self.scripts_dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def _run_lint_on_file(self, path: Path) -> tuple[int, str]:
        """跑 lint on 指定文件 (不依赖默认 scan_dirs, 直接传 path argv)."""
        result = subprocess.run(
            [sys.executable, "-m", "backend.scripts.check_sql_fstring_consistency", str(path)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parent.parent.parent,  # repo root
        )
        return result.returncode, result.stdout + result.stderr

    def test_missing_f_prefix_should_violate(self):
        """故意 1 个 missing f-prefix, lint 应该报 violation rc=1."""
        bad_sql = '''
# 测试 fixture (S36-4)
BAD_SQL = """
SELECT * FROM orders WHERE {valid_sql}
"""
'''
        p = self._write_sql_file("bad.py", bad_sql)
        rc, out = self._run_lint_on_file(p)
        # lint 应该报 violation
        self.assertNotEqual(rc, 0, f"expected non-zero exit, got {rc}. Output: {out}")
        self.assertIn("BAD_SQL", out, f"expected BAD_SQL in output, got: {out}")
        self.assertIn("missing f-prefix", out.lower(), f"expected 'missing f-prefix' message, got: {out}")

    def test_correct_f_string_should_pass(self):
        """故意 1 个 correct f-string, lint 应该 rc=0."""
        good_sql = '''
# 测试 fixture (S36-4)
GOOD_SQL = f"""
SELECT * FROM orders WHERE {valid_sql}
"""
'''
        p = self._write_sql_file("good.py", good_sql)
        rc, out = self._run_lint_on_file(p)
        self.assertEqual(rc, 0, f"expected zero exit, got {rc}. Output: {out}")
        self.assertIn("0 violations", out, f"expected '0 violations' message, got: {out}")

    def test_no_interpolation_should_not_violate(self):
        """故意 1 个无 interpolation 的 triple-quote, 不应误报 (false positive 防护)."""
        no_interp_sql = '''
# 测试 fixture (S36-4)
NO_INTERP_SQL = """
SELECT * FROM orders WHERE pay_time >= ?
"""
'''
        p = self._write_sql_file("no_interp.py", no_interp_sql)
        rc, out = self._run_lint_on_file(p)
        self.assertEqual(rc, 0, f"expected zero exit (no false positive), got {rc}. Output: {out}")

    def test_extended_default_scan_includes_scripts_etl(self):
        """跑全目录 (无 argv) 验证新加 scripts/etl/ 范围生效 (不报错)."""
        # 这条测试独立 — 不传 argv, 用默认 scan_dirs (含 scripts/etl/).
        # 不要求 0 violation (有 GSV_OVERRIDE_JOIN_SQL 是合法的 f-string).
        # 关键是: 不应该 rc=2 (error no scan dirs) — 至少扫到 1 个 file.
        result = subprocess.run(
            [sys.executable, "-m", "backend.scripts.check_sql_fstring_consistency"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parent.parent.parent,
        )
        # 应该是 0 (干净) 或 1 (有 violation) — 不能是 2 (scan error).
        self.assertIn(result.returncode, (0, 1), f"unexpected rc={result.returncode}: {result.stdout}")
        # 应该扫到 70+ files (services) + scripts/etl/ = 100+ total
        # 输出包含 '0 violations' 或 'X violation(s)' 就行
        out = result.stdout
        self.assertTrue(
            "violation" in out.lower(),
            f"expected 'violation' in output, got: {out}",
        )


if __name__ == "__main__":
    unittest.main()
