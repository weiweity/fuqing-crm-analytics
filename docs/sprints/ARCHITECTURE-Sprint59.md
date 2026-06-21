# Sprint 59 收割季 ARCHITECTURE (v0.4.14.143 设计, 2026-06-21, Codex review 吸收版)

> **Sprint 58 留尾 4 项 → Sprint 59 收割季 3 项** (基于 Codex review 24 个问题简化, 1.0d 工作量, 从原计划 1.5d 缩短). 留 Sprint 60+ 1 项 (#3 50m scale 调研).
>
> **Codex review 反馈摘要**: 24 个问题覆盖 pytest collection 不可信 / git HEAD 自指悖论 / CHANGELOG 双阈值漂移 / audit lint regex 弱 / 合并顺序矛盾 / 3 worktree 编排过度 / #8 跳过 review 错分类 / 战略误判 (删 lint). 本 ARCHITECTURE 吸收 P0 + P1 + 战略收缩 (#24).

## Context

Sprint 58 收口后留尾 4 项. Codex review 指出原计划 1.5d 收割季范围过大 + 多个阻断级问题. 简化后 3 项 1.0d:

- **#6 STATUS.md 自动化** (0.5d, Claude 主跑): 只抓**稳定字段** (pytest collected + skipped + 当前债数 + 最近 sprint), 删 HEAD/分支数/passed/failed (Codex #1, #2, #15, #21)
- **#5 CHANGELOG 按行数归档** (0.3d, Codex 跑): 单一规则 ≤ 900 行, 脚本按行数归档 (Codex #6, #7, #8, #22)
- **#8 audit 措辞 SOP only** (0.2d, Codex 跑): 删 lint script (Codex #3, #5, #18, #23, #24), 只写 30 行 SOP + 5 对反例正例

**核心约束** (跨 sprint 实战沉淀, CLAUDE.md L1-L5 永久规则):
- 不在 main 直接改代码, 走 12 步流程
- commit 前 review, push 前 pytest, merge 前 qa
- pre-commit 走 .githooks (轻量零依赖 9 件 lint)
- 本地即生产, merge 后 pull + restart uvicorn
- 永远不破坏 import path

---

## Codex review 24 个问题吸收状态

| # | 类型 | 问题 | 决策 |
|---|------|------|------|
| 1 | 阻断 | pytest --collect-only 不能生成 passed/failed | ✅ 删 passed/failed, 只留 collected + skipped |
| 2 | 阻断 | git HEAD 自指悖论 | ✅ 删 git HEAD |
| 3 | 阻断 | audit lint regex 弱 | ✅ 删 lint script |
| 4 | 阻断 | N=20 误报率验证没用 lint | ✅ 删 (跟 #3 一起) |
| 5 | 阻断 | lint 0.5d 清零不现实 | ✅ 删 lint |
| 6 | 阻断 | CHANGELOG 4 entry 不够 34→25 | ✅ 改按行数 ≤ 900 单一规则 |
| 7 | 阻断 | CHANGELOG 选择规则冲突 | ✅ 统一按行数 |
| 8 | 阻断 | 验收阈值漂移 900 vs 1000 | ✅ 统一 ≤ 900 行 |
| 9 | 流程 | 合并顺序文字+代码块矛盾 | ✅ 统一 `#5 → #6 → #8` |
| 10 | 流程 | 冲突分析漏 .githooks + CHANGELOG | ✅ 加冲突矩阵 |
| 11 | 流程 | 3 worktree 并行是假的 | ✅ 改 wt-01 + wt-02 并行, wt-03 串行 |
| 12 | 流程 | #8 不是纯文档不该跳过 review | ✅ #8 加 ④ review |
| 13 | 流程 | #6 拒绝 unit test | ✅ 加 3 case regression test |
| 14 | 流程 | advisory hook 无 staged-file gating | ✅ 删 advisory hook, 改手动跑 |
| 15 | 口径 | 分支数不是项目状态 | ✅ 删 |
| 16 | 口径 | 最近 sprint 取 CHANGELOG 第一条 | ✅ 改用 git log --since 30d |
| 17 | 口径 | grep -oP macOS BSD 不可用 | ✅ 改 Python re 或 ggrep |
| 18 | 口径 | lint 缺失文件 silent | ✅ 删 lint (跟 #3 一起) |
| 19 | 口径 | 文档口径冲突 754/1 vs 17 skipped | ✅ 统一 754/1 = 当前 pytest |
| 20 | 口径 | VERSION bump 不明确 | ✅ Stage 4 收口时明确 v0.4.14.143 |
| 21 | 战略 | STATUS 抓易变数据 | ✅ 删 HEAD/分支数 (跟 #2 + #15) |
| 22 | 战略 | CHANGELOG 双阈值 | ✅ 单一规则 ≤ 900 行 |
| 23 | 战略 | 关键词 regex 推动骗过正则 | ✅ 删 regex |
| 24 | 战略 | 整体范围过大 | ✅ 删 #8 lint, 收 1.0d |

---

## 范围 (3 项, 1.0d, 简化版)

### #6 STATUS.md 自动化 (0.5d, Claude 主跑)

**抓取字段** (Codex 反馈 #1 + #2 + #15 + #21 删 HEAD/分支数/passed/failed):

| 字段 | 抓取源 | 失败行为 |
|------|--------|---------|
| `pytest collected` | `python3 -m pytest --co -q 2>/dev/null` + re `(\d+) tests collected` | 抓不到用 `?` |
| `pytest skipped` | 同上 + re `(\d+) skipped` | 同上 |
| `当前债数` | 读 `docs/TECH-DEBT.md` "当前债数" 行 (Python re, 不 grep -oP) | 抓不到用 `?` |
| `最近 sprint` | `git log --since='30 days ago' --oneline -- CHANGELOG.md` 找最近 Sprint entry | 抓不到用 `?` |

**STATUS.md 占位符格式** (精简, 删 HEAD/分支数):
```markdown
<!-- STATUS-AUTO-START -->
| pytest collected | **754** | Sprint 59 自动抓 |
| pytest skipped | **1** | Sprint 59 自动抓 |
| 当前债数 | **0** | Sprint 59 自动抓 |
| 最近 sprint | **Sprint 58** | Sprint 59 自动抓 |
<!-- STATUS-AUTO-END -->
```

**Unit test** (Codex #13 必加, 3 case):
```python
# backend/tests/test_status_update.py
def test_marker_missing_raises():
    """STATUS.md 缺 <!-- STATUS-AUTO-START --> 标记时 raise"""

def test_marker_duplicate_raises():
    """STATUS.md 有多个 <!-- STATUS-AUTO-START --> 标记时 raise"""

def test_pytest_output_change_adapts():
    """pytest 输出格式变化时, status_update.py 不崩溃 (warning + '?')"""
```

**Mac 兼容** (Codex #17): 不用 `grep -oP` (macOS BSD grep 不支持), 用 Python `re` 模块.

**Advisory hook 删** (Codex #14): 改手动跑 `--check` 在 Stage 3 review 时.

### #5 CHANGELOG 按行数归档 (0.3d, Codex 跑)

**单一规则** (Codex #6, #7, #8, #22): CHANGELOG.md ≤ **900 行** (Sprint 56 1000 行阈值的缩紧版).

**当前状态**: 1337 行 / 34 entry (Sprint 58 后)
**目标**: ≤ 900 行 / 不卡 entry 数

**脚本化归档** (跟 Sprint 56 模式一致, 1 个 `archive_changelog.py` script):

```python
#!/usr/bin/env python3
"""scripts/archive_changelog.py — 把 CHANGELOG.md 老段按行数归档到 CHANGELOG_HISTORY.md"""
import re
from pathlib import Path

MAX_LINES = 900

def archive(target_lines: int = MAX_LINES):
    changelog = Path("CHANGELOG.md").read_text()
    history = Path("CHANGELOG_HISTORY.md").read_text()

    lines = changelog.splitlines(keepends=True)
    if len(lines) <= target_lines:
        print(f"CHANGELOG.md 已 ≤ {target_lines} 行 ({len(lines)} 行), 无需归档")
        return

    # 找 ## Sprint 或 ## [v...] heading 边界
    cut_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^## (Sprint|\[v)", line):
            cut_idx = i
            break

    if cut_idx is None:
        raise ValueError("找不到 ## Sprint / ## [v...] heading")

    archived = "".join(lines[:cut_idx])
    kept = "".join(lines[cut_idx:])

    # append 到 history 顶部 (跟 Sprint 56 模式)
    new_history = archived + history
    Path("CHANGELOG_HISTORY.md").write_text(new_history)
    Path("CHANGELOG.md").write_text(kept)
    print(f"归档: {cut_idx} 行 → CHANGELOG_HISTORY.md, 保留 {len(kept.splitlines())} 行")
```

**Stage 1+2 Codex 跑实施, Stage 3 Claude review**:
- 验证归档后 ≤ 900 行
- 验证 Sprint 53+ 全部保留 (跨 sprint 高频引用)
- 验证 CHANGELOG_HISTORY.md 顶部追加段

**顶部提示行更新**: "本文件保留: Sprint 56 起 (v0.4.14.140+) 至今详细 (Sprint 59 #5 收割季后 ≤ 900 行)".

### #8 audit 措辞 SOP only (0.2d, Codex 跑, 走 ④ review)

**战略收缩** (Codex #3, #5, #18, #23, #24): 删 `scripts/lint_audit_words.py` lint script (关键词 regex 推动作者写出能骗过正则的文本, 失去门禁价值). 只写 30 行 SOP 文档.

**新建 `docs/development/AUDIT-WORDING.md`** (30 行, 5 规则 + 5 对反例正例):

```markdown
# Audit 措辞 SOP

## 5 规则

1. **避免"完成"/"治根"/"闭环"等模糊词**: 必须带 commit SHA (7-40 hex, `git rev-parse --verify` 验证存在) 或具体数据
2. **数据导向**: 用 N=N 验证 + commit hash + 文件:行号 引用代替主观判断
3. **回归可追溯**: `0.5x → 1x 加速` 写 "4.32s → 2.26s, commit SHA X" 而非 "加速 73x"
4. **避免"搞定"/"修好"**: 改用 "WARN→blocking 升级" + commit SHA
5. **结构化证据**: claim + commit + verification + date 字段, 不用关键词 regex

## 反例 → 正例

| ❌ 反例 | ✅ 正例 |
|---------|---------|
| race flake 治本 | race flake 治本 (per-worker tmp DuckDB + ATTACH read_only, commit `81b43cd`) |
| CI 实战 fix 持久化完成 | CI 实战 fix 持久化 (12+4 follow-up → `docs/operating/ci-e2e-history.md` 142 行, commit `09e2a18`) |
| Sprint 58 #1 治根 | Sprint 58 #1 e2e OOM 治本 (DuckDB ATTACH + workers 1 + timeout 60s, commit `4e297a3`) |
| 误报率优化 | 误报率算法优化 (THRESHOLD_RATIO 3.0→10.0, 误报率 17/20 → 0/14, commit `11416b5`) |
| Sprint 58 闭环 | Sprint 58 闭环 (8 commit 0 debt, main HEAD `17b5361`, v0.4.14.142, pytest 754/1) |
```

**走 ④ review** (Codex #12): SOP 内容是 ad-hoc 决策, 必 Stage 3 architecture review 验证反例 → 正例教学材料完整 + commit SHA 真实 (`git rev-parse --verify` 验证).

---

## 文件改动 (6 文件, +260 -60 行, 简化版)

| 文件 | 类型 | 行数 | 备注 |
|------|------|------|------|
| `scripts/status_update.py` | 新建 | +90 | #6 STATUS 自动化 |
| `STATUS.md` | 改 | ~25 (加占位符) | #6 |
| `backend/tests/test_status_update.py` | 新建 | +60 | #6 unit test (Codex #13) |
| `scripts/archive_changelog.py` | 新建 | +40 | #5 归档脚本 |
| `CHANGELOG.md` | 改 | ~30 (顶部提示行 + 行数缩) | #5 |
| `CHANGELOG_HISTORY.md` | 改 | +80 (归档段) | #5 |
| `docs/development/AUDIT-WORDING.md` | 新建 | +30 | #8 SOP only |

**总**: 7 文件 +355 -60 行 (从原 8 文件 +320 -50 行调整为 7 文件 +355 -60 行, 净增 +295 行).

---

## 冲突矩阵 + 串行合并顺序

### 文件冲突矩阵

| 文件 | #6 | #5 | #8 |
|------|----|----|----|
| `scripts/status_update.py` | ✅ 新建 | — | — |
| `STATUS.md` | ✅ 改 | — | — |
| `backend/tests/test_status_update.py` | ✅ 新建 | — | — |
| `scripts/archive_changelog.py` | — | ✅ 新建 | — |
| `CHANGELOG.md` | — | ✅ 改 (顶部 + 行数) | — |
| `CHANGELOG_HISTORY.md` | — | ✅ 改 | — |
| `docs/development/AUDIT-WORDING.md` | — | — | ✅ 新建 |

**冲突分析**:
- 原计划冲突 `#6+#8 都改 STATUS.md` → ✅ 已删 (#6 删 HEAD/分支数, 不再跟 #8 措辞修订冲突)
- 原计划冲突 `#6+#8 都改 .githooks/pre-commit` → ✅ 已删 (#6 删 advisory hook)
- 原计划冲突 `#5+#8 都改 CHANGELOG.md` → ✅ 已删 (#8 删 lint, 不再改 CHANGELOG.md)

**净冲突**: 0 个 (Codex #10 修复).

### 串行合并顺序 (Codex #9 修复)

```
wt-sprint59-01 (#6 STATUS 自动化) → main @ 9X
wt-sprint59-02 (#5 CHANGELOG 归档) → main @ 9Y  (串行: 等 wt-01 完成)
wt-sprint59-03 (#8 SOP only)       → main @ 9Z  (串行: 等 wt-02 完成)
```

**实施**: 实际 2 worktree 并行 (wt-01 + wt-02), wt-03 等 wt-02 merge 后再开 (Codex #11 修复).

### Stage 1-4 流程 (跟 Sprint 58 模式一致)

1. **Stage 1**: Claude 写 ARCHITECTURE (本文件) + 3 份 HANDOFF (已写 + Codex review 吸收)
2. **Stage 2**: wt-01 (#6) Claude 主跑 + wt-02 (#5) Codex 并行, wt-03 (#8) Codex 等 wt-02 后串行
3. **Stage 3**: Claude review 3 worktree (#6 重点 unit test + #5 脚本 + #8 SOP)
4. **Stage 4**: 串行 merge (wt-01 → wt-02 → wt-03), 12 步流程 #6/#8 必走 ④ review + ⑧ qa, #5 跳

---

## 12 步流程应用 (Codex #12 修复)

| 项 | 跳过 ④ review + ⑧ qa | 必走 |
|----|---------------------|------|
| **#6** (新 Python script) | ❌ 必走 | 全部 12 步 |
| **#5** (纯 doc + archive script) | ✅ 跳过 (跟 Sprint 56 模式) | 11 步 - review/qa |
| **#8** (SOP doc-only) | ❌ 必走 (Codex #12 修复, SOP 是 ad-hoc 决策) | 全部 12 步 |

---

## 成功标准 (Codex #19 修复: 统一 754/1)

- pytest **754/1** 持续 (0 回归, Sprint 58 baseline)
- L1 + L3 lint 0 violations
- vite build 750ms 持续
- `scripts/status_update.py --check` exit 0
- `scripts/archive_changelog.py` 跑后 CHANGELOG.md ≤ **900 行**
- `docs/development/AUDIT-WORDING.md` 5 规则 + 5 反例正例 + commit SHA `git rev-parse --verify` 验证全部通过
- backend/tests/test_status_update.py 3 case pass
- Stage 4 VERSION bump 0.4.14.142 → **0.4.14.143** (Codex #20 明确)

---

## Sprint 60+ 留尾 (1 项 + 2 跨 sprint)

- **#3 50m scale Phase 1 调研** (等数据量 30M 触发, 2d, 推 Sprint 60+)
- **17 pytest skipped** (test_w4_t7_integration.py, Sprint 53 race flake fixture 遗留, Sprint 60+ 评估)
- **27 stale remote branches** (Sprint 33-52 历史, Sprint 60+ 统一清理)

---

## 风险与缓解 (基于 Codex review 24 个问题吸收)

| 风险 | 缓解 |
|------|------|
| pytest --collect-only 不可信 (Codex #1) | 只抓 collected + skipped, 删 passed/failed |
| git HEAD 自指 (Codex #2) | 删 HEAD |
| lint 关键词 regex 弱 (Codex #3, #23) | 删 lint script, 只写 SOP |
| CHANGELOG 双阈值漂移 (Codex #22) | 单一规则 ≤ 900 行 |
| 合并冲突 (Codex #10) | 冲突矩阵分析 + 串行合并 |
| 3 worktree 编排过度 (Codex #11) | 2 worktree 并行 + 1 串行 |
| Codex 卡 stdin 50% (Sprint 57 + 58 实战) | wt-01 Claude 主跑, wt-02/wt-03 Codex + Claude 接管 fallback |
| worktree 共享 working tree 副作用 (Sprint 58 wt-06) | 用 `git mv` 跨 worktree, 不 cp/mv |

---

## 关联文件

- `docs/sprints/ARCHITECTURE-Sprint58.md` — Sprint 58 收口架构 (v0.4.14.142)
- `docs/sprints/HANDOFF-TO-CODEX-Sprint59-01.md` — Codex/Claude 实施 #6
- `docs/sprints/HANDOFF-TO-CODEX-Sprint59-02.md` — Codex 实施 #5
- `docs/sprints/HANDOFF-TO-CODEX-Sprint59-03.md` — Codex 实施 #8
- `docs/development/LESSONS_LEARNED.md` — Sprint 50+ 9 pattern 沉淀
- CLAUDE.md L1-L5 永久规则

---

## 验证

```bash
# #6 (Claude 主跑)
PYTHONPATH="$(pwd)" pytest backend/tests/test_status_update.py -v  # 3/3 pass
./scripts/status_update.py --check                                # exit 0
./scripts/status_update.py --apply                                # STATUS.md 更新

# #5 (Codex 跑)
test $(wc -l < CHANGELOG.md) -le 900
python3 scripts/archive_changelog.py                              # 归档, 无需再跑

# #8 (Codex 跑)
test -f docs/development/AUDIT-WORDING.md
# Stage 3 Claude review 验证 commit SHA 真实
for sha in $(grep -oP '[0-9a-f]{7,40}' docs/development/AUDIT-WORDING.md); do
  git rev-parse --verify "$sha" > /dev/null || echo "❌ $sha 不存在"
done

# 收口
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q  # 754/1 持续
cd frontend-vue3 && npx vite build                # 750ms 持续
```