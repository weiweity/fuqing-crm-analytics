#!/usr/bin/env python3
"""session_start_check.py — Sprint 178+ SessionStart hook

Claude Code session 启动时自动检查:
1. MEMORY.md 大小 vs 24.4KB L4.13 limit
2. main HEAD 跟 origin/main drift
3. .githooks 是否激活
4. 当前分支未提交修改

不阻塞 session, 仅提示 (跟 Sprint 67 UserPromptSubmit hook 模式 stable).
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, str(e)


def main() -> int:
    print("\n=== Sprint 178 SessionStart 检查 ===")

    # 1. MEMORY.md 大小
    mem_path = Path.home() / ".claude" / "projects" / "-Users-hutou" / "memory" / "MEMORY.md"
    if mem_path.exists():
        size = mem_path.stat().st_size
        limit = 24_576  # 24.4KB L4.13
        pct = size / limit * 100
        marker = "🚨" if size > limit else ("⚠️" if size > 17_100 else "✅")
        print(f"  {marker} MEMORY.md: {size} bytes ({pct:.1f}% of 24.4KB L4.13 limit)")
        if size > limit:
            print("     → 跑 Sprint 178 dedupe SOP: 删旧 sprint 指针")
    else:
        print("  ⚠️  MEMORY.md not found")

    # 2. main drift
    rc, out = run(["git", "rev-parse", "--verify", "main"])
    if rc == 0:
        local_main = out.strip()
    else:
        local_main = "?"
    rc2, out2 = run(["git", "rev-parse", "--verify", "origin/main"])
    if rc2 == 0:
        remote_main = out2.strip()
    else:
        remote_main = "?"
    if local_main == remote_main and local_main != "?":
        print(f"  ✅ main HEAD = origin/main = {local_main[:7]} (0 drift)")
    elif local_main != "?" and remote_main != "?":
        print(f"  ⚠️  main drift: local {local_main[:7]} vs origin {remote_main[:7]}")

    # 3. .githooks 激活
    rc, out = run(["git", "config", "core.hooksPath"])
    hooks_path = out.strip() if rc == 0 else ""
    expected = ".githooks"  # git config 存的是相对 git toplevel 的相对路径
    # 兼容绝对路径 (老版本可能存绝对)
    if hooks_path in (expected, str(REPO_ROOT / ".githooks")):
        print(f"  ✅ core.hooksPath = {hooks_path}")
    elif "/pytest-of-" in hooks_path or hooks_path.endswith("/.git/hooks"):
        print(f"  🚨 core.hooksPath 被污染: {hooks_path}")
        print("     → 自动恢复: git config core.hooksPath .githooks")
        run(["git", "config", "--unset", "core.hooksPath"])
        run(["git", "config", "core.hooksPath", ".githooks"])
    else:
        print(f"  ⚠️  core.hooksPath 异常: {hooks_path}")
        print(f"     → 期望: {expected}")

    # 4. 当前分支未提交
    rc, out = run(["git", "status", "--porcelain"])
    if rc == 0 and out.strip():
        lines = out.strip().split("\n")
        print(f"  ⚠️  {len(lines)} 个 uncommitted 改动 (CLAUDE.md §0 强制: main 上禁止 commit)")
    else:
        print("  ✅ 无未提交改动")

    # 5. workbuddy skills → ~/.claude/skills 对称软链 (L4.35)
    _verify_skill_symlinks()

    print("=== SessionStart 完成 ===\n")
    return 0


def _verify_skill_symlinks() -> None:
    """验证 ~/.workbuddy/skills/<name>/SKILL.md 是软链 → ~/.claude/skills/<name>/SKILL.md (L4.35).

    fail-open: 任何不符合仅 print warning, 不 raise (跟 Sprint 67 F2a UserPromptSubmit hook 同模式).
    跟 L4.13 (MEMORY.md size) + L4.20 (SSOT 反漂移) 永久规则配套, 防止 SSOT 漂移复发.

    Sprint 189 升级: 只对双端都有的 skill 校验, 跳过 workbuddy-only / claude-only.
    之前 106 个 false positive 报 drift, 因为 Claude Code 端没对应 SKILL.md.
    WorkBuddy 生态独占 skill (brainstorming/pdf/xlsx/amazon 等) 不需要软链同步.
    """
    wb_root = Path.home() / ".workbuddy" / "skills"
    claude_root = Path.home() / ".claude" / "skills"
    if not wb_root.is_dir() or not claude_root.is_dir():
        return  # 缺一个目录就跳过, 不阻塞 session
    ok = 0
    miss = 0
    skipped_only_one_side = 0
    for name in sorted(os.listdir(str(wb_root))):
        if name.startswith(".") or name.endswith(".zip") or name.endswith(".json"):
            continue
        wb_skill_md = wb_root / name / "SKILL.md"
        claude_skill_md = claude_root / name / "SKILL.md"
        # Sprint 189 fix: 跳过双端之一缺 SKILL.md 的 skill (workbuddy-only / claude-only)
        if not wb_skill_md.exists() and not os.path.islink(str(wb_skill_md)):
            continue  # workbuddy 没 SKILL.md, 不是被治理对象
        if not claude_skill_md.exists() and not os.path.islink(str(claude_skill_md)):
            skipped_only_one_side += 1
            continue  # claude 端没对应 SKILL.md, 不是双端 SSOT, 跳过 (workbuddy 生态独占)
        try:
            link_mode = os.lstat(str(wb_skill_md)).st_mode & 0o170000
        except OSError as exc:
            print(f"  ⚠️  L4.35 skill SSOT drift: {name}/SKILL.md lstat 失败: {exc}")
            miss += 1
            continue
        if link_mode != 0o120000:
            print(f"  ⚠️  L4.35 skill SSOT drift: {name}/SKILL.md mode {oct(link_mode)} 不是 0o120000 软链")
            miss += 1
            continue
        wb_real = os.path.realpath(str(wb_skill_md))
        claude_real = os.path.realpath(str(claude_skill_md))
        if wb_real != claude_real:
            print(f"  ⚠️  L4.35 skill SSOT drift: {name}/SKILL.md realpath={wb_real} (期望 {claude_real})")
            miss += 1
            continue
        try:
            if wb_skill_md.read_bytes() != claude_skill_md.read_bytes():
                print(f"  ⚠️  L4.35 skill SSOT drift: {name}/SKILL.md 字节内容不一致")
                miss += 1
                continue
        except OSError as exc:
            print(f"  ⚠️  L4.35 skill SSOT drift: {name}/SKILL.md 字节校验失败: {exc}")
            miss += 1
            continue
        ok += 1
    if ok or miss:
        print(f"  ℹ️  L4.35 skill symlink: {ok} OK / {miss} drift (skip {skipped_only_one_side} workbuddy-only / claude-only)")


if __name__ == "__main__":
    sys.exit(main())
