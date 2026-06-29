"""Sprint 168 ground-truth-lint: e2e spec 跟 UI 文字一致性检查.

防 Sprint 161 治本 18 sprint 滞后 stable 模式复发. Sprint 144-160 累计 18
sprint 改 UI (SamplingView 等) 但 e2e spec 断言停留在旧文字, 跨 sprint 没人
同步断言, 直到 Sprint 161 真因修. L4.23 永久规则: 任何 e2e spec 文案断言必
跟当前 UI 实际渲染一致.

本脚本扫:
- ``frontend-vue3/src/views/*.vue`` 的 h1/h2/h3 标题 + 中文 visible 文字节点
- ``frontend-vue3/e2e/*.spec.ts`` 的 ``getByText('X')`` / ``getByRole('button', { name: 'X' })`` 断言

输出两类 drift:
- UI 删了但 spec 还断言 (Sprint 161 line 168 漂移模式)
- spec 没断言但 UI 新出现 (新增 KPI 卡 / section 漂移, advisory)

advisory mode: exit 0 + 打印 warning (跟 L4.5 advisory 模式一致), 不阻塞
跑批, 留给 review skill 当 ground-truth-lint 参考.

跟 L4.7 模式 stable (跟 ``backend/scripts/check_sql_fstring_consistency.py``
Sprint 34.1 / ``backend/scripts/check_channel_alias.py`` Sprint 60.1 一致):
ground-truth-lint hook 防 AI 写 typo 5+ 天未发现.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VIEWS_DIR = REPO_ROOT / "frontend-vue3" / "src" / "views"
SPECS_DIR = REPO_ROOT / "frontend-vue3" / "e2e"

# 扫的 views (跟 e2e spec 对齐: sampling / category / category-detail /
# customer-health / audience-daily-trend / market-focus / login)
VIEW_FILES = [
    "SamplingView.vue",
    "CategoryView.vue",
    "CategoryDetailView.vue",
    "CustomerHealthView.vue",
    "AudienceView.vue",
    "MarketFocusView.vue",
    "LoginView.vue",
]

SPEC_FILES = [
    "sampling.spec.ts",
    "category.spec.ts",
    "category-detail.spec.ts",
    "customer-health.spec.ts",
    "audience-daily-trend.spec.ts",
    "market-focus.spec.ts",
    "login.spec.ts",
]

# 中文 / 英文混合文字节点, 长度 >= 2 才算 drift 候选 (防单字符/标点误报)
MIN_TEXT_LEN = 2
# 排除通用词 (导航/路由/loading 等, 太通用, 误报率高)
IGNORE_WORDS = {
    "首页",
    "登录",
    "登 录",
    "退出",
    "加载",
    "加载中",
    "暂无数据",
    "更多",
    "查看更多",
    "搜索",
    "确认",
    "取消",
    "关闭",
    "返回",
    "导出",
    "刷新",
    "重置",
    "返回品类看板",
    "派样看板",  # nav title 通用
    "品类看板",  # nav title 通用
    "人群看板",  # nav title 通用
    "市场对焦",  # nav title 通用
}


def _extract_view_text(view_path: Path) -> set[str]:
    """从 .vue 抽 h1/h2/h3 标题 + section-title + 中文 visible 文字节点.

    简化版: 用 regex 抓 h1/h2/h3 标签内的中文文字, 跳过 <script> 块.
    """
    if not view_path.exists():
        return set()
    content = view_path.read_text(encoding="utf-8")

    # 删 <script> 块避免 JS 字符串误报
    content_no_script = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)

    # 抽 h1/h2/h3/h4 内的中文文字 (含 <span>...</span> 文字, e.g. <span>04</span>派样明细)
    heading_texts: set[str] = set()
    for match in re.finditer(
        r"<\s*h[1-4][^>]*>(.*?)</\s*h[1-4]\s*>",
        content_no_script,
        flags=re.DOTALL,
    ):
        inner = match.group(1)
        # 抽中文字符串 (e.g. "派样明细" / "回购周期分布" / "总览")
        for ch in re.findall(r"[一-鿿][一-鿿\w\s]*", inner):
            text = ch.strip()
            if len(text) >= MIN_TEXT_LEN:
                heading_texts.add(text)

    # 抽 section-title 内的文字 (Sprint 158+ 改用 class="section-title")
    for match in re.finditer(
        r'class="section-title"[^>]*>(.*?)</\s*h[1-4]\s*>',
        content_no_script,
        flags=re.DOTALL,
    ):
        inner = match.group(1)
        for ch in re.findall(r"[一-鿿][一-鿿\w\s]*", inner):
            text = ch.strip()
            if len(text) >= MIN_TEXT_LEN:
                heading_texts.add(text)

    # 抽 .card-title / .n-card-header__main 等可见文字
    for match in re.finditer(
        r'class="[^"]*card-title[^"]*"[^>]*>(.*?)</',
        content_no_script,
        flags=re.DOTALL,
    ):
        inner = match.group(1)
        for ch in re.findall(r"[一-鿿][一-鿿\w\s]*", inner):
            text = ch.strip()
            if len(text) >= MIN_TEXT_LEN:
                heading_texts.add(text)

    return heading_texts - IGNORE_WORDS


def _extract_spec_assertions(spec_path: Path) -> set[str]:
    """从 .spec.ts 抽 ``getByText('X')`` / ``getByRole(..., { name: 'X' })`` 断言."""
    if not spec_path.exists():
        return set()
    content = spec_path.read_text(encoding="utf-8")

    texts: set[str] = set()

    # getByText('X') / getByText("X") / .filter({ hasText: 'X' })
    for match in re.finditer(
        r"""(?:getByText|hasText|getByRole\([^)]*name\s*:\s*)\s*['"]([^'"]+)['"]""",
        content,
    ):
        text = match.group(1).strip()
        if len(text) >= MIN_TEXT_LEN:
            texts.add(text)

    return texts - IGNORE_WORDS


def _view_key(view_file: str) -> str:
    """view 文件名 → spec 名 (sampling 等)."""
    base = view_file.replace("View.vue", "").lower()
    return {
        "sampling": "sampling",
        "categorydetail": "category-detail",
        "category": "category",
        "customerhealth": "customer-health",
        "audience": "audience-daily-trend",
        "marketfocus": "market-focus",
        "login": "login",
    }.get(base, base)


def check_drift(view_files: list[str] | None = None, spec_files: list[str] | None = None) -> int:
    """主入口: 返回 0 (no drift) 或 0 + warning printout (advisory mode).

    实际永远 return 0 (advisory), 警告打到 stdout. 留给 review skill 当
    ground-truth 参考. Sprint 161 治本模式: drift 出现不一定立刻坏, 但
    必须有 reviewer 决策同步.
    """
    if view_files is None:
        view_files = VIEW_FILES
    if spec_files is None:
        spec_files = SPEC_FILES

    # 按 view → spec 对齐扫
    pairs: list[tuple[str, str]] = []
    for view_file in view_files:
        spec_key = _view_key(view_file)
        spec_file = f"{spec_key}.spec.ts"
        if spec_file in spec_files:
            pairs.append((view_file, spec_file))

    total_stale = 0  # UI 删了 spec 还断言
    total_missing = 0  # spec 没断言 UI 新出现

    print("Sprint 168 e2e spec drift check (advisory, exit 0)")
    print(f"扫 {len(pairs)} view↔spec pairs")
    print()

    drift_details: list[str] = []

    for view_file, spec_file in pairs:
        view_path = VIEWS_DIR / view_file
        spec_path = SPECS_DIR / spec_file

        view_texts = _extract_view_text(view_path)
        spec_texts = _extract_spec_assertions(spec_path)

        # UI 删了 spec 还断言 (Sprint 161 line 168 模式)
        stale = spec_texts - view_texts
        # spec 没断言 UI 新出现 (新增 KPI 卡漂移, advisory)
        missing = view_texts - spec_texts

        if stale:
            total_stale += len(stale)
            drift_details.append(
                f"  ⚠️  {view_file} ↔ {spec_file}: spec 断言 {len(stale)} 个 UI 已删文字\n"
                + "\n".join(f"    - '{t}'" for t in sorted(stale))
            )

        if missing:
            total_missing += len(missing)
            drift_details.append(
                f"  ℹ️  {view_file} ↔ {spec_file}: UI 新增 {len(missing)} 个未断言文字 (advisory)\n"
                + "\n".join(f"    - '{t}'" for t in sorted(missing))
            )

    if drift_details:
        print("=".center(60, "="))
        print(f"DRIFT DETECTED: {total_stale} stale + {total_missing} missing (advisory)")
        print("=".center(60, "="))
        for detail in drift_details:
            print(detail)
        print()
        print("⚠️  Advisory only — exit 0. review skill 必查 stale 项.")
        print("    Sprint 161 真因: spec 断言 '品类回购明细' 但 UI 早改名.")
        print("    L4.23 永久规则: e2e spec 断言必跟 UI 实际渲染一致.")
    else:
        print("✅ 0 drift detected — view ↔ spec 文字一致")

    # advisory mode 永远 exit 0
    return 0


def main() -> int:
    return check_drift()


if __name__ == "__main__":
    sys.exit(main())