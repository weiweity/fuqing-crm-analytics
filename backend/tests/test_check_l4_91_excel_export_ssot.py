"""
L4.91 SSOT 反漂移 ground-truth-lint 锁回归 (跟 L4.19 + L4.34.1 + L4.40 + L4.50 + L4.59 + L4.91 1:1 stable 永久规则化沿用)

4 件 L4.91 规则回归测试 (跟 L4.91 PR0 kind enum + assertNotFormula + frontend 0 处散落 *100 + YOY 列 kind enum 1:1 stable 永久规则化沿用):
- R1: no-raw-xlsx-bypass
- R2: no-excel-formula-write
- R3: no-frontend-times-100
- R4: yoy-kind-required

每件规则 1+1 case: 故意造 1 个 violation + 故意造 1 个 compliant, 验证 lint 命中/不命中.

跟 Sprint 34.1 test_churn_user_list_fstring.py + Sprint 36-4 test_check_sql_fstring_consistency.py 1:1 stable 永久规则化沿用.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LINTER = REPO_ROOT / "backend" / "scripts" / "check_l4_91_excel_export_ssot.py"


class TestL491ExcelExportSsotLint(unittest.TestCase):
    """L4.91 SSOT 反漂移 ground-truth-lint 4 件规则锁回归 (跟 L4.91 + L4.50 1:1 stable 永久规则化沿用)."""

    def setUp(self):
        # 临时建 1 个 fake frontend-vue3/src/views/ 目录结构供 lint 扫
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fq_l4_91_lint_test_"))
        self.views_dir = self.tmpdir / "frontend-vue3" / "src" / "views"
        self.views_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_vue_file(self, name: str, content: str) -> Path:
        path = self.views_dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def _run_lint(self) -> tuple[int, str]:
        """跑 lint on 临时 views 目录 (跟 L4.34.1 + L4.59 1:1 stable 永久规则化沿用)."""
        result = subprocess.run(
            [sys.executable, str(LINTER), "--views-root", str(self.views_dir)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        return result.returncode, result.stdout + result.stderr

    # R1: no-raw-xlsx-bypass
    def test_r1_raw_xlsx_import_should_violate(self):
        """故意 1 个 raw 'xlsx' import, lint 应该报 violation."""
        self._write_vue_file("TestView.vue", '''
<script setup lang="ts">
import { ref } from 'vue'
import { exportToXlsx } from '@/utils/exportXlsx'
import XLSX from 'xlsx'  // L4.91 R1 violation: raw xlsx
</script>
''')
        rc, output = self._run_lint()
        self.assertEqual(rc, 1, f"lint 应该 rc=1, 实际 {rc}, output: {output}")
        self.assertIn("R1:no-raw-xlsx-bypass", output, f"应报 R1 violation, output: {output}")

    def test_r1_xlsx_js_style_should_not_violate(self):
        """故意 1 个 compliant (用 xlsx-js-style 走 SSOT), lint 不报."""
        self._write_vue_file("TestView.vue", '''
<script setup lang="ts">
import { ref } from 'vue'
import { exportToXlsx } from '@/utils/exportXlsx'
// 正确: 用 SSOT, 不直接 import 'xlsx'
</script>
''')
        rc, output = self._run_lint()
        self.assertEqual(rc, 0, f"lint 应该 rc=0, 实际 {rc}, output: {output}")
        self.assertNotIn("R1:no-raw-xlsx-bypass", output)

    # R2: no-excel-formula-write
    def test_r2_excel_formula_object_should_violate(self):
        """故意 1 个 Excel 公式对象, lint 应该报 violation."""
        self._write_vue_file("TestView.vue", '''
<script setup lang="ts">
const cell = { t: 'n', f: "=B1-C1" }  // L4.91 R2 violation: Excel 公式对象
</script>
''')
        rc, output = self._run_lint()
        self.assertEqual(rc, 1, f"lint 应该 rc=1, 实际 {rc}, output: {output}")
        self.assertIn("R2:no-excel-formula-write", output, f"应报 R2 violation, output: {output}")

    def test_r2_string_value_with_equals_should_not_violate(self):
        """故意 1 个 compliant (字符串以 = 开头但不是公式), lint 不报 (R2 专门针对 {f:'=...'} 对象)."""
        # 实际: 我们的 regex 不会误报普通 string
        self._write_vue_file("TestView.vue", '''
<script setup lang="ts">
const note = "请使用 = 符号"
</script>
''')
        rc, output = self._run_lint()
        self.assertNotIn("R2:no-excel-formula-write", output)

    # R3: no-frontend-times-100
    def test_r3_frontend_times_100_yoy_should_violate(self):
        """故意 1 个 frontend *100 on YOY field, lint 应该报 violation."""
        self._write_vue_file("TestView.vue", '''
<script setup lang="ts">
import { computed } from 'vue'
const gsv_yoy_display = computed(() => row.gsv_yoy * 100)  // L4.91 R3 violation
</script>
''')
        rc, output = self._run_lint()
        self.assertEqual(rc, 1, f"lint 应该 rc=1, 实际 {rc}, output: {output}")
        self.assertIn("R3:no-frontend-times-100", output, f"应报 R3 violation, output: {output}")

    def test_r3_compliant_display_should_not_violate(self):
        """故意 1 个 compliant (用 YOYGuard 组件), lint 不报."""
        self._write_vue_file("TestView.vue", '''
<script setup lang="ts">
import { YOYGuard } from '@/components/YOYGuard.vue'
// 正确: 复用 YOYGuard 组件, 不直接 *100
</script>
''')
        rc, output = self._run_lint()
        self.assertNotIn("R3:no-frontend-times-100", output)

    # R4: yoy-kind-required
    def test_r4_yoy_column_missing_kind_should_violate(self):
        """故意 1 个 YOY 列缺 kind enum, lint 应该报 violation."""
        self._write_vue_file("TestView.vue", '''
<script setup lang="ts">
import type { XlsxColumn } from '@/utils/exportXlsx'
const cols: XlsxColumn[] = [
  { header: 'GSV YOY', key: 'gsv_yoy', numFmt: '0.00' },  // L4.91 R4 violation: YOY 列缺 kind
]
</script>
''')
        rc, output = self._run_lint()
        self.assertEqual(rc, 1, f"lint 应该 rc=1, 实际 {rc}, output: {output}")
        self.assertIn("R4:yoy-kind-required", output, f"应报 R4 violation, output: {output}")

    def test_r4_yoy_column_with_kind_should_not_violate(self):
        """故意 1 个 compliant (YOY 列有 kind enum), lint 不报."""
        self._write_vue_file("TestView.vue", '''
<script setup lang="ts">
import type { XlsxColumn } from '@/utils/exportXlsx'
const cols: XlsxColumn[] = [
  { header: 'GSV YOY', key: 'gsv_yoy', kind: 'yoy_pct' },  // 正确
]
</script>
''')
        rc, output = self._run_lint()
        self.assertNotIn("R4:yoy-kind-required", output)

    # 综合: clean file 0 violations
    def test_clean_file_zero_violations(self):
        """故意 1 个 clean file, lint rc=0, 0 violations."""
        self._write_vue_file("CleanView.vue", '''
<script setup lang="ts">
import { ref } from 'vue'
import { exportToXlsx } from '@/utils/exportXlsx'
import type { XlsxColumn } from '@/utils/exportXlsx'

const cols: XlsxColumn[] = [
  { header: '渠道', key: 'channel', kind: 'text' },
  { header: 'GSV', key: 'gsv', kind: 'number', numFmt: '¥#,##0' },
  { header: 'GSV YOY', key: 'gsv_yoy', kind: 'yoy_pct' },
]
</script>
''')
        rc, output = self._run_lint()
        self.assertEqual(rc, 0, f"clean file 应该 rc=0, 实际 {rc}, output: {output}")
        self.assertIn("✅ 0 violations", output, f"应输出 0 violations, output: {output}")


if __name__ == "__main__":
    unittest.main()
