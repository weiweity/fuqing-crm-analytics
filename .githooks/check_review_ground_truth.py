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
  - 黑名单: hex color (#ff00aabb / #ffffff 等带 # 前缀) / 11位手机号 / 15/18位身份证
    → 都不算 evidence (防 false positive 旁路)

用法:
  - 自动: 由 .githooks/pre-commit 调
  - 手动: python3 .githooks/check_review_ground_truth.py [--staged] [--committed] [--files FILE] [--verbose]
  - 测试: pytest backend/tests/test_check_review_ground_truth.py -v

P1-3 二轮 (2026-06-07) — 3 修:
  - B2 NOOP fix: 加 --committed 模式, 跑 git show HEAD:<path> 拉已 commit 文件
    内容, 解决 CI 跑已 commit 文件时 git diff --cached 永远 0 字节的 no-op 问题
  - H1 HEX backdoor fix: 增强 _is_pseudo_sha 黑名单, 加 hex color 模式
    (re.search(r'#[0-9a-f]{6,8}\\b', text)) 排除 "#ff00aabb" 类伪 evidence
  - 已 commit 文件扫: commit 模式 whole_file parse, diff_scope_filter='whole_file'
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
# P1-3 H1 修 (2026-06-07): SHA regex 严格化
#   旧: \b[0-9a-f]{7,40}\b — 误判中国身份证 (18位) / 手机号 (11位) / hex color
#   新: 必须有 git commit/tag/PR 前导 (e.g. "commit a1b2c3d" / "tag v1.0 #abc1234" / "PR #abc1234")
#   黑名单: 11位 全数字 (手机号) / 15位 / 18位 (身份证) — 这些不算 SHA
EVIDENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"git\s+log\b", re.IGNORECASE),
    re.compile(r"git\s+show\b", re.IGNORECASE),
    # 严格 SHA: 7-40 位 hex 且前面必须是 commit/tag/PR/#/@ 等 git 上下文
    re.compile(
        r"(?:commit[:\s]+|tag[:\s]+|PR\s*#?[:\s]*|#|@)\b[0-9a-f]{7,40}\b",
        re.IGNORECASE,
    ),
    re.compile(r"已验证|已确认|已核对|已落地|已合入|已集成|已实现|已存在"),
)


def _is_pseudo_sha(s: str) -> bool:
    """黑名单: 不是真 commit SHA 的伪 evidence.

    P1-3 H1 (2026-06-07): 11位 全数字 (手机号) / 15/18位 (身份证) — 旧 regex
    \b[0-9a-f]{7,40}\b 误判.

    P1-3 二轮 H1 HEX (2026-06-07): hex color (#ff00aabb / #ffffff 等带 # 前缀)
    — "#" 是 SHA regex 的合法前导 (#ff00aabb 8 位 hex 满足 7-40), 但 CSS hex
    color 不是 commit SHA, 必须从 evidence 排除.
    """
    # hex color: # 开头 + 6-8 位 hex (覆盖 #fff #ffffff #ffff 八位带 alpha)
    if re.search(r"#[0-9a-f]{6,8}\b", s, re.IGNORECASE):
        return True
    digits_only = re.sub(r"\D", "", s)
    if len(digits_only) == 11 and digits_only.isdigit():
        return True  # 手机号
    if len(digits_only) in (15, 18) and digits_only.isdigit():
        return True  # 身份证
    return False


def _filter_sha_evidence(text: str) -> str:
    """过滤掉 phone/ID-card/hex-color 假阳性 SHA, 保留真 git commit/tag 上下文."""
    return re.sub(
        r"\b[0-9a-f]{7,40}\b",
        lambda m: m.group(0) if not _is_pseudo_sha(m.group(0)) else "",
        text,
    )


# P1-3 二轮 H1 HEX (2026-06-07): 显式 hex color 模式, 抠掉 evidence 中所有 #xxxxxx
HEX_COLOR_RE = re.compile(r"#[0-9a-f]{6,8}\b", re.IGNORECASE)


def _filter_hex_color_evidence(text: str) -> str:
    """从 evidence 抠掉所有 hex color (#ff00aabb 等), 防 # 前缀 SHA 旁路."""
    return HEX_COLOR_RE.sub("", text)

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


def get_committed_content(path: str) -> str:
    """P1-3 二轮 B2 修: 拉已 commit 文件的完整内容 (git show HEAD:<path>).

    用于 CI 模式: 跑已 commit 文件, 没有 staged diff, 必须直接拿文件内容.

    Returns:
        完整文件内容 (UTF-8 字符串), 失败返空字符串.
    """
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{path}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            return ""
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def parse_whole_file(content: str) -> list[tuple[int, str]]:
    """P1-3 二轮 B2 修: 整文件内容当 added_lines 解析 (committed 模式).

    把每行当 (line_no, content), 用 1-based 行号. 这是 committed 模式的核心:
    没有 diff, 只能扫整文件.
    """
    out: list[tuple[int, str]] = []
    for i, line in enumerate(content.splitlines(), start=1):
        out.append((i, line))
    return out


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


def _find_line_index(added_lines: list[tuple[int, str]], target_lineno: int) -> int:
    """P1-3 四轮 B2 修 (2026-06-07): 在 added_lines 中找 lineno == target_lineno 的真 idx.

    在 committed 模式下, added_lines = 整文件 (e.g. 340 行), 但调用方传的是
    trigger 在 triggers 列表里的 idx — 这俩在长文件里差很大 (triggers 列表 idx
    = 0 时, added_lines idx 可能 = 339). 必须用 lineno 反查真 idx 才能算窗口.

    Returns 0 if not found (graceful default, 不崩).
    """
    for i, (lineno, _) in enumerate(added_lines):
        if lineno == target_lineno:
            return i
    return 0


def find_evidence_nearby(
    added_lines: list[tuple[int, str]],
    trigger_lineno: int,
    window: int = 30,
) -> bool:
    """检查触发词附近 (window 行内) 是否有 evidence.

    在审查文档场景下, "附近" 通常是同段 (3-5 行) 或同表 (10-30 行).
    window=30 是宽松值, 防止跨段落严格匹配导致误伤.

    Args:
        added_lines: list of (line_no, content) tuples.
        trigger_lineno: 触发词的 1-based 行号 (NOT the index in the triggers list).
            P1-3 四轮 B2 修 (2026-06-07): committed 模式下 added_lines = 整文件,
            triggers list idx 与 added_lines idx 不一定一致 (e.g. 末尾 trigger
            triggers idx=0, added_lines idx=339). 必须用 lineno 反查.
        window: how many lines around the trigger to consider.

    P1-3 H1 修 (2026-06-07): SHA 段先过 phone/ID 卡 filter, 排除 11/15/18 位 数字伪 evidence.
    P1-3 H3 修 (2026-06-07): "git log" 字符串出现 + 文件在 git 历史中存在 → 双重验证.
    P1-3 二轮 H1 HEX (2026-06-07): evidence 抠掉 hex color (#ff00aabb 等), 防 # 前缀旁路.
    """
    if not added_lines:
        return False
    # P1-3 四轮 B2 修: 用 lineno 反查真 idx (不是直接用 callers 传进来的 idx)
    real_idx = _find_line_index(added_lines, trigger_lineno)
    start = max(0, real_idx - window)
    end = min(len(added_lines), real_idx + window + 1)
    nearby_text = "\n".join(line for _, line in added_lines[start:end])
    # H1: 先过 phone/ID 卡 filter, 抠掉 11/15/18 位 数字伪 SHA
    filtered_text = _filter_sha_evidence(nearby_text)
    # P1-3 二轮 H1 HEX: 抠掉 hex color (#ff00aabb 等带 # 前缀的 6-8 位 hex)
    filtered_text = _filter_hex_color_evidence(filtered_text)
    for pat in EVIDENCE_PATTERNS:
        if pat.search(filtered_text):
            return True
    return False


def _git_log_produced_output(file_path: str, cwd: str | None = None) -> bool:
    """H3: 真跑 git log 验证 — 文件在 git 历史中存在时, git log 才有输出.

    返回 True = 文件在 git 历史中 (旧文件, agent 真能跑 git log 实证).
    返回 False = 文件是 brand new (agent 写 "git log" 但实际没跑 / 跑空).
    """
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--all", "--", file_path],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            cwd=cwd,
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def has_real_git_evidence(
    added_lines: list[tuple[int, str]],
    trigger_lineno: int,
    file_path: str,
    window: int = 30,
    cwd: str | None = None,
) -> bool:
    """H3 强验证: 'git log' 字符串 + 该文件在 git 历史中真存在 → 双重 evidence.

    仅在 nearby 出现 'git log' / 'git show' 字符串时启用 (cheap case 升级到 real case).
    失败时不阻断, 只把 verdict 降级为 no_real_evidence (commit 仍可过, 但带 warning).

    Args:
        added_lines: list of (line_no, content) tuples.
        trigger_lineno: 触发词的 1-based 行号 (NOT the index in the triggers list).
            P1-3 四轮 B2 修 (2026-06-07): committed 模式下 added_lines = 整文件,
            triggers list idx 与 added_lines idx 不一致, 必须用 lineno 反查真 idx.
        file_path: 用于 git log -- <path> 真跑验证.
        window: 多少行内算 nearby.
        cwd: git log 跑批的工作目录 (默认 None = 当前进程 cwd).

    P1-3 四轮 B2 修 (2026-06-07): trigger_idx → trigger_lineno (跟 find_evidence_nearby
    保持一致, 防止长文件 false negative).
    """
    if not added_lines:
        return False
    # P1-3 四轮 B2 修: 用 lineno 反查真 idx (与 find_evidence_nearby 同款)
    real_idx = _find_line_index(added_lines, trigger_lineno)
    start = max(0, real_idx - window)
    end = min(len(added_lines), real_idx + window + 1)
    nearby_text = "\n".join(line for _, line in added_lines[start:end])
    has_git_string = bool(re.search(r"git\s+(log|show)\b", nearby_text, re.IGNORECASE))
    if not has_git_string:
        return True  # 不依赖 git log 的 evidence 模式 (e.g. SHA + 前导), 直接 pass
    return _git_log_produced_output(file_path, cwd=cwd)


def find_triggers(added_lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Return [(line_no, matched_text), ...] for trigger words in added lines.

    一行可能有多个 trigger (例如 "X 未集成, Y 不存在, 都是占位"), 用 finditer 全部返回.
    """
    triggers: list[tuple[int, str]] = []
    for lineno, content in added_lines:
        for m in TRIGGER_RE.finditer(content):
            triggers.append((lineno, m.group(0)))
    return triggers


def check_file(path: str, committed: bool = False) -> list[tuple[int, str, str]]:
    """检查单个 staged / committed 文件. 返回 [(lineno, trigger, reason), ...] violations.

    reason 是 "no_evidence" (无 evidence) 或 "no_real_evidence" (字符串有但 git log 跑空) 等.

    P1-3 H3 (2026-06-07): 两步验证
      L1 cheap: 触发词附近有 git log / SHA / 已集成 等 evidence 字符串
      L2 real:  真跑 git log --all -- <path>, 验证该文件在 git 历史中真存在
      → expensive case ("写了 git log 但没跑 / 跑空") 仍需 /review skill 人工护航

    P1-3 二轮 B2 (2026-06-07): committed=True 模式
      - 不读 staged diff (CI 跑已 commit 文件, 永远空)
      - 用 git show HEAD:<path> 拉文件内容
      - parse_whole_file 把每行当 added_lines (diff_scope_filter='whole_file')
      - 解决 CI 结构性 no-op 问题
    """
    violations: list[tuple[int, str, str]] = []
    if committed:
        # B2 修: 已 commit 文件模式, 整文件扫
        content = get_committed_content(path)
        if not content.strip():
            return violations
        added_lines = parse_whole_file(content)
    else:
        diff = get_staged_diff(path)
        if not diff.strip():
            return violations
        added_lines = parse_added_lines(diff)
    triggers = find_triggers(added_lines)
    # H3: 用 git 根目录跑 git log (cwd 决定 history 范围, worktree vs main repo 不同)
    git_root = _git_root()
    # P1-3 四轮 B2 修 (2026-06-07): 不传 idx, 改传 trigger 实际 lineno
    # 旧版传 idx (triggers 列表索引) 在 committed 模式下 (added_lines = 整文件)
    # 与 added_lines 真 idx 不一致, 导致长文件末尾 trigger 的 window 滑到文件头,
    # evidence 错误命中 → false negative
    for lineno, trigger in triggers:
        if not find_evidence_nearby(added_lines, lineno):
            violations.append((lineno, trigger, "no_evidence"))
            continue
        # L2 验证 (H3): 有 evidence 字符串, 但 git log 真能跑出输出吗?
        if not has_real_git_evidence(added_lines, lineno, path, cwd=git_root):
            violations.append((lineno, trigger, "no_real_evidence (git log 字符串在, 但跑空 / 跑失败)"))
    return violations


def _git_root() -> str | None:
    """返回 git 仓库根目录 (toplevel), 失败返回 None."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check staged review files for unbacked ground-truth claims")
    parser.add_argument("--staged", action="store_true", default=True, help="Check staged diffs (default)")
    parser.add_argument(
        "--committed",
        action="store_true",
        default=False,
        help="P1-3 二轮 B2: 扫已 commit 文件 (git show HEAD:<path>), 用于 CI 模式",
    )
    parser.add_argument("--files", nargs="*", help="Specific files to check (overrides --staged)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args(argv)

    if os.environ.get("FQA_GROUND_TRUTH_SKIP") == "1":
        print("[skip] FQA_GROUND_TRUTH_SKIP=1, bypass check_review_ground_truth")
        return 0

    files: list[str] = []
    if args.files:
        files = list(args.files)
    elif args.committed:
        # P1-3 四轮 M1 修 (2026-06-07): --committed 没 --files 时自动 fallback
        # 扫 docs/validation-reports/ + docs/飞书版架构文档/ — 匹配 CI workflow 的 scope
        # (lint.yml + nightly.yml ground-truth-lint step 都用这两个 glob).
        # 修前: 静默 no-op (files=[]) → false sense of safety, 开发者手动跑 --committed
        #       以为有保护, 实际没扫任何文件.
        # 修后: 不传 --files 也自动扫 review scope, 跟 CI 行为一致.
        import glob
        fallback_patterns = (
            "docs/validation-reports/*.md",
            "docs/飞书版架构文档/*.md",
        )
        for pat in fallback_patterns:
            files.extend(glob.glob(pat))
        # 按路径排序 → 输出稳定
        files = sorted(set(files))
    else:
        files = [f for f in get_staged_files() if is_review_file(f)]

    if not files:
        if args.committed:
            print("[ok] check_review_ground_truth (--committed): 无 review 文件传入, 跳过")
        else:
            print("[ok] check_review_ground_truth: 无 review-style staged 文件, 跳过")
        return 0

    total_violations = 0
    for path in files:
        violations = check_file(path, committed=args.committed)
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

    if args.committed:
        print(f"[ok] check_review_ground_truth (--committed): 扫了 {len(files)} 个 review 文件, 无未附实证的 ground-truth 声明")
    else:
        print(f"[ok] check_review_ground_truth: 扫了 {len(files)} 个 review 文件, 无未附实证的 ground-truth 声明")
    return 0


if __name__ == "__main__":
    sys.exit(main())
