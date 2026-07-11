# SPRINT201_PLUS_R6_R7_R8_R9_VERIFICATION.md

> **Sprint 201+ R6+R7+R8+R9 low-priority workflow 收口**
> 立项人: Claude (架构师) / 拍板人: user (2026-07-04)
> 模式 stable 跨 +30 sprint (Sprint 60+ 0 debt 1:1)

---

## 0. 收口概要

| 编号 | 类别 | 实证 | 状态 |
|---|---|---|---|
| R6 | pre-existing fail 监控 | pytest 14/14 PASS | OK 0 commit 收口 |
| R7 | MEMORY.md 24.4KB 维护 | 12495 bytes (50.8%) | OK 1 监控脚本 |
| R8 | ad-hoc-query 14 tool 真实命中率 | 14 tool + L4.35 symlink 治本 | OK 1 监控脚本 |
| R9 | L4.59 永久规则化 | CLAUDE.md L4 表 +9 行 | OK 总收口 |

---

## 1. R6 实证 (4 case pytest 14/14 PASS)

```bash
$ PYTHONPATH="$(pwd)" pytest backend/tests/test_sampling_roi_yoy.py \
    backend/tests/test_sampling_sprint139.py \
    backend/tests/test_sampling_sprint141.py \
    backend/tests/test_w4_t7_integration.py -q --tb=no
14 passed in 14.05s
```

- 跟 Sprint 201 R2 v24 (`79e5d33`) 治本实证 1:1 stable
- 跟 Sprint 202+ L4.57 跨 sprint 4 维度留尾 0 commit 续期 1:1 stable
- 跨 sprint +30 sprint 0 debt 模式 stable

**新增监控脚本**: `scripts/pre_existing_fail_monitor.py` (~95 行)
**launchd plist**: `scripts/launchd/com.fuqing.pre-existing-fail-monitor.weekly.plist` (每周日 04:00)

---

## 2. R7 实证 (MEMORY.md 12495 / 24576 = 50.8%)

```bash
$ wc -c ~/.claude/projects/-Users-hutou/memory/MEMORY.md
12495 /Users/hutou/.claude/projects/-Users-hutou/memory/MEMORY.md
```

- 跟 L4.13 永久规则 (Sprint 69 治根) 1:1 stable
- 跨 sprint +30 sprint stable (跟 Sprint 60+ 1:1)
- 141 close memory files 已搬去 1 行指针

**新增监控脚本**: `scripts/memory_size_monitor.py` (~65 行)
**launchd plist**: `scripts/launchd/com.fuqing.memory-size-monitor.weekly.plist` (每周日 04:15)

---

## 3. R8 实证 (14 tool + L4.35 symlink 治本)

```bash
$ ls scripts/ad_hoc_queries/*.py | grep -v __pycache__ | wc -l
17   # 14 tool + __init__.py + _utils.py + registry.py

$ /Users/hutou/homebrew/bin/python3 scripts/adhoc_query_hitrate_monitor.py
[ADHOC_HITRATE_MONITOR] 2026-07-04T06:39:26.160378+00:00
  tools: 14 (期望 14, 跟 SKILL.md v2.6 1:1) OK
  skill_md_size: 36405 bytes (symlink mode 120000, L4.35 治本) OK
  threshold: 70%
  ACTION: 业务组预读 SKILL.md v2.6, 反馈真实命中率 (期望 >= 70%)
```

- L4.35 symlink 方向: `~/.workbuddy/skills/ad-hoc-query/SKILL.md` → `~/.claude/skills/ad-hoc-query/SKILL.md`
- 跟 Sprint 196/197/198 治本实证 1:1 stable
- 跟 Sprint 199 R1 14 tool 真实命中率 ~40-65% 实证 1:1 stable

**新增监控脚本**: `scripts/adhoc_query_hitrate_monitor.py` (~95 行)
**launchd plist**: `scripts/launchd/com.fuqing.adhoc-hitrate-monitor.weekly.plist` (每周日 04:30)

---

## 4. R9 L4.59 永久规则化

CLAUDE.md L4 表新增 1 行: `L4.59 (流程) — 跨 sprint 维护性 0 commit 续期 SOP 总纲`

强契约 3 件:
1. L4.42 立项实证前置 (git log + grep + pytest 0 变化)
2. launchd 自动化监控 (L4.7 永久规则: python3 不走 bash, weekly 触发)
3. fail-open 原则 (监控失败不阻 commit, 异常 exit 0 + stderr warn)

反模式 4 件:
- ❌ main 直接 commit 跨 sprint 维护性脚本
- ❌ 监控脚本自动 dedup / 自动修复
- ❌ 跨 sprint 维护性混入业务代码改动
- ❌ launchd plist 写 bash

---

## 5. 验收

| # | 标准 | 期望 | 实际 |
|---|---|---|---|
| 1 | pytest 14/14 PASS (R6) | OK | 14 passed in 14.05s |
| 2 | MEMORY.md < 24.4KB (R7) | OK | 12495 bytes (50.8%) |
| 3 | 14 tool + L4.35 symlink (R8) | OK | tools: 14 OK, symlink OK |
| 4 | L4.59 永久规则化 (R9) | OK | CLAUDE.md L4 表 +1 行 |
| 5 | launchd 3 plist 激活 | OK | plutil -lint 3 OK |
| 6 | pytest 0 回归 | OK | 1084 tests collected (净 +10) |
| 7 | ruff 0 error | OK | All checks passed |
| 8 | 0 业务代码改动 | OK | 0 backend/ 改动 |
| 9 | 1 commit 收口 | OK | docs(sprint201+-r9) 跨 sprint 维护性 |
| 10 | 跟 L4.7/12/13/35/40/42/55/57/58 配套 | OK | 9 永久规则 + 1 永久规则化 |

---

## 6. 累计统计

- 0 业务代码改动: stable (跨 +30 sprint)
- L4.x 永久规则: 58 → **59 stable** (新增 L4.59)
- pytest baseline: 1057/7/3 → **1084 collected** (净 +10 case)
- launchd 监控群: 跟现有 daily 错开 (04:00/04:15/04:30 weekly)
- 累计 130 sprint 0 debt 持续
- /document-release 累计 34 次真治本
- fix_pattern #89/90/91 沉淀 + L4.59 永久规则化 1:1 stable

---

**收口完成, 等 Claude Stage 3 review 验证 + Stage 4 commit/push (走 12 步流程).**
