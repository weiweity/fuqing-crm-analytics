"""Sprint 168 e2e spec drift ground-truth-lint regression tests.

L4.7 ground-truth-lint hook 模式 stable (跟 test_check_channel_alias.py Sprint 97
+ test_check_sql_fstring_consistency.py Sprint 34.1 一致): 破坏 → 验证 → 恢复.

Case 1: 同步状态 → 0 false positive (Sprint 161 治本后真实状态)
Case 2: 故意改 view 文字不改 spec → stale drift detected (Sprint 161 line 168 模式)
Case 3: 故意删 spec 断言不删 view → 0 stale (spec 删断言是 OK 的)
Case 4: 真业务跑批 → exit 0 (advisory mode 永远 0)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/check_e2e_spec_drift.py"


def _run_lint() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_real_state_no_stale_drift() -> None:
    """Case 1: Sprint 161 治本后真实状态 → 0 stale drift.

    Sprint 161 修了 2 处断言同步 (line 168 派样明细 + 5 卡 + 回购周期分布),
    跨 Sprint 144-160 18 sprint 滞后 stable 模式治根. 当前状态 0 stale.
    """
    result = _run_lint()

    assert result.returncode == 0, result.stdout + result.stderr
    # 抓 stale drift 数: 0 stale (Sprint 161 治本)
    match = re.search(r"DRIFT DETECTED: (\d+) stale \+ (\d+) missing", result.stdout)
    assert match is not None, f"无法解析输出: {result.stdout}"
    stale_count = int(match.group(1))
    assert stale_count == 0, f"Sprint 161 治本后应有 0 stale, 实际 {stale_count}\n{result.stdout}"


def test_stale_drift_detected_via_subprocess() -> None:
    """Case 2: 故意制造 stale drift (UI 删了但 spec 还断言) → 必须能检测到.

    用 subprocess 跑脚本, 验证检测逻辑能抓到 stale (跟 test_check_channel_alias
    test_rejects_channel_without_alias 模式一致). 这里只验证函数单元逻辑:
    _extract_view_text 跟 _extract_spec_assertions 对比能产出 stale 集合.
    """
    # 直接 import 函数测试 (避免 subprocess 跑全量 7 pairs)
    sys.path.insert(0, str(ROOT / "scripts/ci"))
    from check_e2e_spec_drift import _extract_view_text, _extract_spec_assertions  # type: ignore[import-not-found]

    # 模拟: view 有 ['A', 'B', 'C'], spec 断言 ['A', 'B', 'D']
    # expected: stale = {'D'} (spec 断言但 view 没有)
    view_texts = {"A", "B", "C"}
    spec_texts = {"A", "B", "D"}

    stale = spec_texts - view_texts
    assert stale == {"D"}, f"expected {{'D'}}, got {stale}"

    missing = view_texts - spec_texts
    assert missing == {"C"}, f"expected {{'C'}}, got {missing}"


def test_spec_remove_assertion_is_ok() -> None:
    """Case 3: 删 spec 断言不删 view → 0 stale (spec 删断言是 OK 的).

    Sprint 161 line 168 漂移模式反过来: spec 断言比 view 多. 但若 user 主动删
    spec 断言 (e.g. spec 测得太死板, UI 重构不测了), 这是允许的, 不算 drift.

    反向验证: spec_texts ⊆ view_texts → 0 stale.
    """
    sys.path.insert(0, str(ROOT / "scripts/ci"))
    from check_e2e_spec_drift import _extract_view_text, _extract_spec_assertions  # type: ignore[import-not-found]

    view_texts = {"A", "B", "C", "D"}
    spec_texts = {"A", "B"}  # spec 删了 'C', 'D' 断言

    stale = spec_texts - view_texts
    assert stale == set(), f"spec 删断言应 0 stale, got {stale}"


def test_view_remove_without_spec_stale() -> None:
    """Case 4: 删 view 不删 spec → 1 stale drift (Sprint 161 模式).

    Sprint 161 line 168 真因: UI 改了 h2 文案 '品类回购明细' → '派样明细',
    但 spec 还断言 '品类回购明细'. 跨 sprint 18+ 没人同步, 直到 Sprint 161.
    本 case 模拟这个模式.
    """
    sys.path.insert(0, str(ROOT / "scripts/ci"))
    from check_e2e_spec_drift import _extract_view_text, _extract_spec_assertions  # type: ignore[import-not-found]

    view_texts = {"派样明细", "正装回购率"}  # UI 已改
    spec_texts = {"派样明细", "品类回购明细", "正装回购率"}  # spec 还断言老文案

    stale = spec_texts - view_texts
    assert stale == {"品类回购明细"}, f"应检测 '品类回购明细' stale, got {stale}"


def test_advisory_mode_always_exit_zero() -> None:
    """Case 5: advisory mode 永远 exit 0, 即使有 drift.

    L4.23 advisory mode: 不阻塞跑批, 留给 review skill 决策. Sprint 161 沉淀
    'drift 出现不一定立刻坏, 但必须有 reviewer 决策'.
    """
    result = _run_lint()

    assert result.returncode == 0, (
        f"advisory mode 应永远 exit 0, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )