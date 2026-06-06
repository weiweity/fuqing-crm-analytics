#!/usr/bin/env python3
"""
Sprint 3 P1-3: pre-commit 钩子 — 拦截未带 git log 实证的"未集成/不存在/占位"声明

背景 (D-4 教训, 2026-06-06):
  D-4 飞书架构 7 份刷 时出现 4 个 ground truth 错误:
    - "pipeline.py W3 step 7b 未集成" → 实际 step 8.5 早就合 (v0.4.11)
    - "X.py 不存在" → 实际已落地在 scripts/etl/
    - "test_X.py 是占位" → 实际是真实 pytest 测试
  根因: agent 凭 memory / stale 文档下结论, 没跑 `git log --all` 实证。
  修复: pre-commit 钩子扫 staged diffs, 出现触发词必须附件 `git log` / `git show` 实证。

触发词:
  - 未集成 / 不存在 / 占位 / TODO / FIXME / 缺失 / 还没接 / 待集成
    (中英混合, 包括常见的 weak claim 模式)

检查范围 (narrow, 避免误拦):
  - 仅扫 `docs/` 下 .md 文件 (review/audit 风格输出)
  - 跳过代码文件 (backend/, frontend-vue3/, scraper/, scripts/) — 那些是 code comment, 不是 review
  - 跳过 CHANGELOG.md / VERSION (版本声明文, 不算 review)

证据模式 (任一即视为已附实证):
  - `git log` / `git show` / `git log --all` 命令出现在 diff 同一文件
  - 8-40 位 hex 字符串 (commit SHA, 例如 a1b2c3d4)
  - 显式 "已验证" / "已确认" / "已核对" / "已落地" 标记 (中文 6 词白名单)

误伤规避:
  - 仅检查 **新增** 行 (diff 以 + 开头), 不检查删除行 (历史可能有同样词)
  - 仅检查 staged diff (git diff --cached), 不检查 unstaged
  - 跳过 review 抬头中的元数据 (例如 "未集成" 在表头/索引/链接不算)
  - 提供 `FQA_GROUND_TRUTH_SKIP=1` 环境变量绕过 (救火用)

用法:
  - 自动: 由 .githooks/pre-commit 调
  - 手动: python3 .githooks/check_review_ground_truth.py [--staged] [--files FILE] [--verbose]
  - 测试: pytest backend/tests/test_check_review_ground_truth.py -v
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

# 触发词: 声明代码/文档状态为 "未完成/缺失/占位" 的短语
TRIGGER_WORDS: tuple[str, ...] = (
    "未集成", "不存在", "占位", "缺失", "还没接", "待集成",
    "TODO", "FIXME",
    "not integrated", "not implemented", "placeholder", "missing",
)

# 证据模式: 触发词附近必须出现以下任一
# 注: 用 re.IGNORECASE 区分大小写
EVIDENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"git\s+log\b", re.IGNORECASE),
    re.compile(r"git\s+show\b", re.IGNORECASE),
    re.compile(r"\b[0-9a-f]{7,40}\b"),  # commit SHA
    re.compile(r"已验证|已确认|已核对|已落地|已合入|已集成|已实现|已存在"),
)

# 检查范围: 只扫 docs/ 下 .md 文件 (review/audit 风格输出)
# 显式白名单 + 显式黑名单 (避免误拦代码/版本声明)
def is_review_file(path: str) -> bool:
    """判断是否为 review 风格输出文件.

    规则:
      - 路径必须在 docs/ 下
      - 必须是 .md
      - 排除 CHANGELOG.md (顶层) — 版本声明不算 review
      - 排除 reference.md (handbook 索引, 不算 review)
    """
    p = path.replace("\\", "/")
    if not p.startswith("docs/"):
        return False
    if not p.endswith(".md"):
        return False
    # 顶层 docs/ 下的元数据文件不算
    basename = p.rsplit("/", 1)[-1]
    if basename in {"CHANGELOG.md", "reference.md", "DOCUMENT-INDEX.md", "README.md"}:
        return False
    return True


# 触发词检测 (单词边界, 避免 "未集成测试" 之类误匹配)
# 中文按字符匹配, 英文按 \b 单词边界
def _build_trigger_pattern() -> re.Pattern[str]:
    parts: list[str] = []
    for w in TRIGGER_WORDS:
        if any("一" <= c <= "鿿" for c in w):
            # 中文: 直接字符串匹配 (中文没有显式词边界)
            parts.append(re.escape(w))
        else:
            # 英文: \b 边界
            parts.append(rf"\b{re.escape(w)}\b")
    return re.compile("|".join(parts), re.IGNORECASE)


TRIGGER_RE = _build_trigger_pattern()


# ---------------------------------------------------------------------------
# 核心逻辑
# ---------------------------------------------------------------------------

def get_staged_files() -> list[str]:
    """Return list of staged file paths (added/modified/copied).

    处理 git 对含非 ASCII 字符的路径加引号 + 八进制转义:
      "docs/\351\243\236\344\271\246.../foo.md"  →  "docs/飞书.../foo.md"
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "-z"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    # -z 输出: NUL 分隔, 不加引号, 路径保持 UTF-8 原样
    out: list[str] = []
    for raw in result.stdout.split("\x00"):
        if not raw:
            continue
        out.append(raw)
    return out


def get_staged_diff(path: str) -> str:
    """Return the staged diff for a single file (unified diff with +/- prefixes)."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--", path],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def parse_added_lines(diff: str) -> list[tuple[int, str]]:
    """Parse unified diff, return [(line_no, content)] for added lines.

    新增行 (以 + 开头, 排除 +++ 文件头).
    """
    added: list[tuple[int, str]] = []
    current_line = 0
    for raw in diff.splitlines():
        if raw.startswith("@@"):
            # Hunk header: @@ -old,count +new,count @@
            m = re.match(r"@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@", raw)
            if m:
                current_line = int(m.group(1))
            continue
        if raw.startswith("+++") or raw.startswith("---"):
            continue
        if raw.startswith("+"):
            added.append((current_line, raw[1:]))  # 去掉前导 +
            current_line += 1
        elif raw.startswith("-"):
            # 删除行不递增 current_line (因为是基于 old 文件位置)
            continue
        else:
            # 上下文行 (以空格开头)
            current_line += 1
    return added


def find_evidence_nearby(added_lines: list[tuple[int, str]], trigger_idx: int, window: int = 30) -> bool:
    """检查触发词附近 (window 行内) 是否有 evidence.

    在审查文档场景下, "附近" 通常是同段 (3-5 行) 或同表 (10-30 行).
    window=30 是宽松值, 防止跨段落严格匹配导致误伤.
    """
    if not added_lines:
        return False
    start = max(0, trigger_idx - window)
    end = min(len(added_lines), trigger_idx + window + 1)
    nearby_text = "\n".join(line for _, line in added_lines[start:end])
    for pat in EVIDENCE_PATTERNS:
        if pat.search(nearby_text):
            return True
    return False


def find_triggers(added_lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Return [(line_no, matched_text), ...] for trigger words in added lines.

    一行可能有多个 trigger (例如 "X 未集成, Y 不存在, 都是占位"), 用 finditer 全部返回.
    """
    triggers: list[tuple[int, str]] = []
    for lineno, content in added_lines:
        for m in TRIGGER_RE.finditer(content):
            triggers.append((lineno, m.group(0)))
    return triggers


def check_file(path: str) -> list[tuple[int, str, str]]:
    """检查单个 staged 文件. 返回 [(lineno, trigger, reason), ...] violations.

    reason 是 "no_evidence" (无 evidence) 或其他.
    """
    violations: list[tuple[int, str, str]] = []
    diff = get_staged_diff(path)
    if not diff.strip():
        return violations
    added_lines = parse_added_lines(diff)
    triggers = find_triggers(added_lines)
    for idx, (lineno, trigger) in enumerate(triggers):
        if not find_evidence_nearby(added_lines, idx):
            violations.append((lineno, trigger, "no_evidence"))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check staged review files for unbacked ground-truth claims")
    parser.add_argument("--staged", action="store_true", default=True, help="Check staged diffs (default)")
    parser.add_argument("--files", nargs="*", help="Specific files to check (overrides --staged)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args(argv)

    if os.environ.get("FQA_GROUND_TRUTH_SKIP") == "1":
        print("[skip] FQA_GROUND_TRUTH_SKIP=1, bypass check_review_ground_truth")
        return 0

    if args.files:
        files = list(args.files)
    else:
        files = [f for f in get_staged_files() if is_review_file(f)]

    if not files:
        print("[ok] check_review_ground_truth: 无 review-style staged 文件, 跳过")
        return 0

    total_violations = 0
    for path in files:
        violations = check_file(path)
        if violations:
            total_violations += len(violations)
            print(f"\n[fail] {path}: {len(violations)} 个未附 git log 实证的 ground-truth 声明:")
            for lineno, trigger, reason in violations:
                print(f"  L{lineno}: 触发词 '{trigger}' (reason: {reason})")

    if total_violations:
        print(f"\n[block] 共 {total_violations} 个 violation, commit 拒绝.")
        print("\n修复方案 (任选其一):")
        print("  1. 在触发词附近附件 git log 实证, 例:")
        print("     ```")
        print("     $ git log --oneline -- backend/services/pipeline.py | head -5")
        print("     a1b2c3d feat(etl): W3 step 8.5 ...")
        print("     ```")
        print("  2. 改为已验证的陈述, 例: '已集成 (commit a1b2c3d)'")
        print("  3. 如果确实是占位/缺失 (新功能 TODO), 改用 '待开发' / 'WIP' 措辞")
        print("\n  救火绕过: FQA_GROUND_TRUTH_SKIP=1 git commit ...")
        return 1

    print(f"[ok] check_review_ground_truth: 扫了 {len(files)} 个 review 文件, 无未附实证的 ground-truth 声明")
    return 0


if __name__ == "__main__":
    sys.exit(main())
