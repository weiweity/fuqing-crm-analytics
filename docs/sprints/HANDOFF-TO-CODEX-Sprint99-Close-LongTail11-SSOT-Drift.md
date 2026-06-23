# HANDOFF — Sprint 99 留尾 #11 SSOT 漂移闭环 + L4.20 反 SSOT 漂移永久规则

> **角色**: Codex Stage 2 实施
> **来源**: Claude Stage 1 架构 (Sprint 98 收口后盘点 + Sprint 99 真因真发现)
> **范围**: 留尾治理 sprint 模式 (跟 Sprint 67+68+91 一致, 1 sprint 多范围, 0 业务代码)
> **分支**: `fix/sprint99-close-longtail-11-ssot-drift` (新创建)
> **目标**: Sprint 91 必修 3 真修持续验证 + 反 SSOT 漂移永久规则 L4.20 + 跨文档一致性 100% PASS

---

## 0. 背景 (Context)

### Sprint 98 收口后盘点真因真发现 (跟 Sprint 96.5 7 sprint 完整链路真因真发现模式 一致)

Sprint 98 close memory 留尾:

> 📋 必修 1 fail 跨 sprint 留尾 #11 (test_ad_hoc_query.py 跨日 fail): Sprint 98 不修

**实测验证 Sprint 91 必修 3 已真修留尾 #11** (5 项 100% PASS):

| 验证项 | 结果 |
|--------|------|
| `test_build_take_path_cross_year_correct` 单独跑 | ✅ 1/1 PASS (0.18s) |
| `test_ad_hoc_query.py` 全量 | ✅ 26/26 PASS (1.02s) |
| `build_take_path("新老客数据", 2025, "2025-12-01至2026-01-31")` 实际路径 | ✅ 含 "2025年" |
| `date.today().strftime("%Y年%-m月%d日")` | ✅ "2026年6月23日" |
| 路径包含 today_str | ✅ True |

Sprint 91 close memory 必修 3 真修:

> 必修 3 1 fail 跨 sprint 留尾 #11 修 (`test_ad_hoc_query.py::TestTakePathRules::test_build_take_path_cross_year_correct` hardcode `2026年6月22日` 漂移, 改 `date.today().strftime("%Y年%-m月%d日")` 用 `%-m` POSIX 避免 0 填充)
> pytest 验证: 1/1 PASS, 跟 Sprint 90 baseline `744/23/1` → Sprint 91 `745/23/0`

### SSOT 漂移复发 (跟 Sprint 67 反思同根因)

| 时间 | 留尾 #11 状态 | 来源 |
|------|--------------|------|
| Sprint 91 close memory | ✅ 必修 3 真修 (1/1 PASS) | 1 fail → 0 fail |
| Sprint 92-97 close memory | 📋 留尾 #11 (复制粘贴未更新) | SSOT 漂移 |
| Sprint 98 close memory | 📋 必修 1 fail 跨 sprint 留尾 #11 (Sprint 98 不修) | **SSOT 漂移复发** |

Sprint 67 close memory 反思 "跨 sprint 误列已闭环 4 次, 重复列 L4.7 + RFM_DEFINITIONS 3 次" + Sprint 91 必修 5 反思治根 (D3+D4 标闭环) — 同样问题再次出现, Sprint 99 治根.

### Sprint 99 模式 (跟 Sprint 67+68+91 留尾治理 sprint 一致)

- **1 sprint**: Sprint 99 (留尾治理 sprint, 0 业务代码)
- **1 范围**: 留尾 #11 SSOT 漂移闭环 + L4.20 反 SSOT 漂移永久规则
- **0 debt**: 1 commit 0 debt 累计 (跟 Sprint 91 模式一致)
- **0 业务代码改动**: Sprint 91 已真修, Sprint 99 只验证 + 闭环 + 加永久规则
- **0 治理 SOP 追加**: 0 永久规则追加 (L4.20 是新增但属于 Sprint 91 必修 5 反思治根的延续, 跟 Sprint 90 L4.7 + Sprint 97 L4.19 配套)

---

## 1. 任务清单 (Must Do)

### T1 — 必修 1: 验证 Sprint 91 真修持续生效 (5min)

跑 pytest 验证 Sprint 91 必修 3 真修仍然生效 (留尾 #11 已闭环):

```bash
python3 -m pytest backend/tests/test_ad_hoc_query.py -v 2>&1 | tail -30
# 预期: 26 passed

python3 -m pytest --tb=no -q 2>&1 | tail -10
# 预期: 815 passed / 23 skipped / 0 failed (Sprint 98 baseline 持续)

python3 -c "
from scripts.ad_hoc_queries._utils import build_take_path
from datetime import date
today_str = date.today().strftime('%Y年%-m月%d日')
path = build_take_path('新老客数据', 2025, '2025-12-01至2026-01-31')
assert '2025年' in str(path), f'2025年 不在 {path}'
assert today_str in str(path), f'{today_str} 不在 {path}'
print('T1 验证 PASS:', path)
"
# 预期: T1 验证 PASS: .../2025年/2026年6月23日/2025年-2026年6月23日-新老客数据/...
```

**T1 验收**: 3 项 PASS, 0 fail. Sprint 91 必修 3 真修持续生效.

---

### T2 — 必修 2: 反 SSOT 漂移永久规则 L4.20 + ground-truth-lint 防回归 (1h)

跟 Sprint 90 L4.7 + Sprint 97 L4.19 模式一致, 加 L4.20 永久规则 + ground-truth-lint 防回归.

#### T2.1 — CLAUDE.md 加 L4.20 永久规则

文件: `CLAUDE.md`

在 L4.19 后面加 L4.20 永久规则 (跟现有 L4.x 表格格式一致):

```markdown
| **L4.20 (流程)** | **留尾 close memory 必引用前 sprint 真修 commit SHA + 标 ✅ 闭环 vs 📋 推后, 禁止复制粘贴未更新状态** (SSOT 漂移复发根治, 跟 Sprint 67 反思 + Sprint 91 必修 5 同根因) | review skill 强制 | **Sprint 99** | 本节 + `docs/sprints/HANDOFF` |
```

#### T2.2 — 写 ground-truth-lint 防回归

文件: `backend/scripts/check_ssot_drift.py` (新建, 跟 Sprint 97 `check_channel_alias.py` 模式一致, 170 行 ±20)

功能: 扫 `docs/sprints/* close memory` 找 "留尾 #" 引用:

1. 如果 close memory 留尾章节 引用某 sprint "未修" 但该 sprint 后续 close memory 显示已真修 → 标 SSOT 漂移 (Sprint 99 真因真发现模式)
2. 如果 close memory 留尾章节 没引用 commit SHA → 标 缺引用
3. 0 业务代码改动, 只读 close memory

**L4.20 ground-truth-lint 防 SSOT 漂移复发的根因**: 留尾 close memory 跨 sprint 复制粘贴, 没引用真修 commit SHA + 没标 ✅ 闭环 vs 📋 推后 状态, 导致留尾列表 SSOT 漂移.

#### T2.3 — 写 regression test

文件: `backend/tests/test_sprint99_l4_ssot_drift_lint.py` (新建, 跟 Sprint 97 `test_sprint97_channel_alias_coverage.py` 模式一致, 4 case)

4 case:

1. `test_sprint99_close_memory_references_real_fix_commit_sha` — Sprint 99 close memory 引用 Sprint 91 真修 commit (留尾 #11 闭环)
2. `test_sprint99_close_memory_marks_longtail_11_closed` — Sprint 99 close memory 留尾 #11 标 ✅ 闭环
3. `test_ssot_drift_lint_detects_unmarked_longtail` — 故意破坏: 制造一个未标 ✅/📋 的留尾 → lint 报错
4. `test_ssot_drift_lint_source_scan_min_lint_lines` — 源码扫描: `backend/scripts/check_ssot_drift.py` 至少 100 行 + 含 "留尾 #" + "✅ 闭环" + "📋 推后" 3 个关键字

**T2 验收**: 4 case PASS, L4.20 永久规则 加 CLAUDE.md, `check_ssot_drift.py` 跑通 0 SSOT 漂移.

---

### T3 — 必修 3: 跨文档同步 (30min, 跟 Sprint 94 /document-release 跨文档一致性 100% PASS 模式 一致)

| 文件 | 改动 |
|------|------|
| `STATUS.md` | 加 Sprint 99 收口 entry: `2026-06-23 (Sprint 99 收口: 留尾 #11 SSOT 漂移闭环 + L4.20 反 SSOT 漂移永久规则)` |
| `CHANGELOG.md` | 加 Sprint 99 entry (顶部): `## [0.4.14.157] - 2026-06-23 (Sprint 99, VERSION 不变 留尾治理 sprint)` |
| `docs/TECH-DEBT.md` | 留尾章节 加 Sprint 99 留尾 #11 标 ✅ 闭环 (引用 Sprint 91 真修 commit SHA + Sprint 99 验证), 跟 Sprint 67 D3+D4 标闭环模式一致 |
| `VERSION` | 不 bump (0.4.14.157 持续, 留尾治理 sprint 模式 跟 Sprint 67+68+91+96+96.5 一致 VERSION 不变) |
| `backend/CLAUDE.md` | L4.20 永久规则 加 (T2.1 已覆盖) |

**T3 验收**: 跨文档一致性 100% PASS (4/4 文件同步, 跟 Sprint 94 验证模式一致).

---

## 2. 验收标准 (Acceptance Criteria)

### 必达项 (跟 Sprint 91 留尾治理 sprint 模式 一致)

1. ✅ **T1 pytest baseline 持续**: 815/23/0 (Sprint 98 baseline 持续, 留尾 #11 已闭环)
2. ✅ **T2 L4.20 永久规则 加 CLAUDE.md** (跟 L4.1-L4.19 表格格式一致)
3. ✅ **T2 `check_ssot_drift.py` ground-truth-lint 跑通** (0 SSOT 漂移, 跟 Sprint 90 L4.7 + Sprint 97 L4.19 模式一致)
4. ✅ **T2 regression test 4 case PASS** (跟 Sprint 97 L4.19 3 case 模式一致 + 1 case 加固)
5. ✅ **T3 跨文档一致性 100% PASS** (STATUS + CHANGELOG + TECH-DEBT + CLAUDE.md 4 文件同步)
6. ✅ **0 业务代码改动** (Sprint 91 已真修, Sprint 99 0 改动)
7. ✅ **0 留尾新增** (留尾 #11 闭环, L4.x 永久规则 19 → 20 stable)
8. ✅ **累计 49 sprint 0 debt 持续** (Sprint 56+60+60.1+60.1.1+60.2+61+62+62.5+63+64+65+66+67+68+69+70+71+72+73+74+75+76+77+78+79+80+81+82+83+84+85+86+87+88+89+90+91+92+92.1+92.2+93+94+95+96+96.1+96.2+96.3+96.4+96.5+97+98+99)

### 不达项 (跟 Sprint 89 暂收口 + Sprint 91 0 治理 SOP 追加 一致)

- ❌ 0 Sprint 99 真业务代码 (留尾治理 sprint 0 业务代码, 跟 Sprint 67+68+91 模式一致)
- ❌ 0 VERSION bump (留尾治理 sprint 不 bump, 跟 Sprint 67+68+91+96+96.5 一致)
- ❌ 0 push 触发 (L4.15 push 必 user 拍板, Stage 4 才决定)

---

## 3. Sprint 99 留尾 (0 项, 全闭环)

按 L4.12 留尾 SSOT 治理 + Sprint 89 暂收口原则 + Sprint 99 L4.20 反 SSOT 漂移永久规则根治:

| # | 留尾项 | 状态 | 闭环 sprint | L4.x 永久规则 |
|---|--------|------|-----------|--------------|
| 1 | FilterBuilder 治本 | ✅ 全闭环 | Sprint 60.1 治标 + 97 治标推广 + **98 真治本** | L4.5 + L4.19 |
| 2 | L4.7 ground-truth-lint | ✅ 闭环 | Sprint 90 (3 _compute_* 加 assert) | L4.7 |
| 3 | L4.8 RFM_DEFINITIONS | ✅ 闭环 | Sprint 60+ | L4.8 |
| 4 | **必修 1 fail 跨 sprint 留尾 #11** | ✅ **闭环** | **Sprint 91 真修 + Sprint 99 验证** (Sprint 99 反 SSOT 漂移根治) | L4.7 + **L4.20** |
| 5 | D1 50m-scale benchmark | 📋 推后 (触发条件 30M) | 待业务触发 | — |

**Sprint 99 留尾闭环后**, 整个 Sprint 60+ 留尾列表 5 项 → 4 项闭环 + 1 项推后 (D1 50m-scale 跨 sprint 推后, 触发条件 30M 数据量).

---

## 4. Stage 4 commit 规范 (跟 Sprint 91 留尾治理 sprint 模式 一致)

### 1 commit 0 debt (跟 Sprint 91 必修 1+2+3+4+5 整合 1 commit 一致)

```bash
git checkout -b fix/sprint99-close-longtail-11-ssot-drift
# 1. 验证 Sprint 91 真修 (T1)
python3 -m pytest backend/tests/test_ad_hoc_query.py -v
# 2. 加 L4.20 永久规则 + ground-truth-lint + regression test (T2)
# 3. 跨文档同步 (T3)
git add CLAUDE.md backend/scripts/check_ssot_drift.py backend/tests/test_sprint99_l4_ssot_drift_lint.py STATUS.md CHANGELOG.md docs/TECH-DEBT.md
git commit -m "chore(lint): Sprint 99 留尾治理 sprint 模式 — L4.20 反 SSOT 漂移永久规则 + 留尾 #11 标闭环 (1 commit 0 debt, 跟 Sprint 67+68+91 模式一致)"
git push origin fix/sprint99-close-longtail-11-ssot-drift
# 4. 等 user 拍板 push (L4.15)
```

### Commit message 规范 (跟 Sprint 91 模式一致)

```
chore(lint): Sprint 99 留尾治理 sprint 模式 — L4.20 反 SSOT 漂移永久规则 + 留尾 #11 标闭环

- T1: pytest baseline 815/23/0 持续 (Sprint 91 真修持续生效)
- T2: L4.20 永久规则 + check_ssot_drift.py ground-truth-lint + 4 case regression test
- T3: STATUS + CHANGELOG + TECH-DEBT + CLAUDE.md 跨文档一致性 100% PASS
- 0 业务代码改动 (留尾治理 sprint 模式, 跟 Sprint 67+68+91 一致)
- 累计 49 sprint 0 debt 持续
```

### Merge --no-ff + 0 VERSION bump

- 1 commit + 1 merge --no-ff (跟 Sprint 91 `fix/sprint91-mandatory-4-close` 模式一致)
- VERSION 不 bump (0.4.14.157 持续, 留尾治理 sprint 不 bump, 跟 Sprint 67+68+91+96+96.5 一致)
- L4.8 删分支: push 后 `git branch -d fix/sprint99-close-longtail-11-ssot-drift` + `git push origin --delete fix/sprint99-close-longtail-11-ssot-drift`

### 12 步流程 (跟 Sprint 50+ 12 步流程一致)

1. ✅ git checkout -b fix/sprint99-close-longtail-11-ssot-drift
2. ✅ 改 code (T1+T2+T3, 0 业务代码改动 + L4.20 + lint + test + doc)
3. ✅ pytest baseline (T1 验证)
4. ✅ review (跳过 /review skill, Stage 3 手动 review, 跟 Sprint 97+98 模式一致)
5. ✅ fix (Codex 实施 + user 拍板)
6. ✅ commit (1 commit chore(lint))
7. ✅ push origin fix branch
8. ✅ qa (skip simple fix, 跟 Sprint 97+98 模式一致)
9. ✅ merge --no-ff to main
10. ✅ push origin main + fix branch
11. ✅ pull --ff-only (verify 0 drift)
12. ✅ restart uvicorn (skip, 0 业务代码改动, 跟 Sprint 67+68+91+96+96.5 留尾治理 sprint 模式一致)

---

## 5. 风险评估 (跟 Sprint 91 留尾治理 sprint 模式 一致)

| 风险 | 等级 | 缓解 |
|------|------|------|
| Sprint 91 真修 regress | **极低** (1 行 import + 1 行 assert + 1 行 docstring, 跨 8 sprint 持续 PASS) | T1 pytest baseline 815/23/0 验证 |
| L4.20 永久规则 误伤其他 close memory | **低** (只读 `docs/sprints/*` 不改业务代码) | T2 ground-truth-lint + 4 case regression test |
| 跨文档不一致 | **极低** (跟 Sprint 94 /document-release 跨文档一致性 100% PASS 模式一致) | T3 4 文件同步 + close memory 引用前 sprint 真修 commit SHA |
| Codex over-fix | **低** (Codex 可能加额外代码超出 T1+T2+T3 范围) | Stage 3 手动 review, 0 业务代码改动原则 |

---

## 6. Sprint 99 模式总结 (跟 Sprint 89 暂收口 + Sprint 91 留尾治理 sprint 一致)

| 维度 | Sprint 89 暂收口 | Sprint 91 留尾治理 | **Sprint 99 留尾治理** |
|------|------------------|--------------------|------------------------|
| 业务代码改动 | 0 | 0 | **0** |
| 永久规则追加 | 0 | 0 | **1 (L4.20)** |
| VERSION bump | 0 | 0 | **0** |
| Sprint 模式 | 暂收口 0 commit 验证 | 留尾治理 1 commit | **留尾治理 1 commit** |
| 跨 sprint 推后链 | 等下次真业务 | 跨 1 sprint 必修 4 | **跨 8 sprint 留尾 #11 SSOT 漂移闭环** |

Sprint 99 跟 Sprint 67+68+91 留尾治理 sprint 模式一致:
- 0 业务代码改动 (留尾 #11 已 Sprint 91 真修, Sprint 99 验证 + 闭环)
- 0 VERSION bump (留尾治理 sprint 不 bump)
- 1 永久规则追加 (L4.20 反 SSOT 漂移, 跟 Sprint 90 L4.7 + Sprint 97 L4.19 配套)

---

## 7. 参考链接 (跟 Sprint 91 留尾治理 sprint 模式 一致)

- **Sprint 91 必修 3 真修**: `backend/tests/test_ad_hoc_query.py:368-373` (1 行 import + 1 行 assert + 1 行 docstring = 3 行改动)
- **Sprint 91 close memory 必修 3**: `/Users/hutou/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint91_close.md`
- **Sprint 90 L4.7 模式**: `_compute_*` 函数体加 `assert sql.count('?') == len(params)` 防回归 + 3 case regression test
- **Sprint 97 L4.19 模式**: `backend/scripts/check_channel_alias.py` 170 行 ground-truth-lint + 3 case regression test
- **Sprint 67 反思**: "跨 sprint 误列已闭环 4 次, 重复列 L4.7 + RFM_DEFINITIONS 3 次" — 同样问题再次出现治根

---

**Sprint 99 HANDOFF 完成. 等 Codex Stage 2 实施 → Stage 3 review → Stage 4 commit + push 收口.**

---

## 8. L4.20 Close Memory 记录

<!-- L4.20-CLOSE-MEMORY -->
- 留尾 #11 | ✅ 闭环 | fix_sprint=Sprint 91 | commit=287efb8 | evidence=26/26 ad-hoc-query PASS + 全量 819/23/0 (815 baseline + 4 regression)
- 留尾 #D1 | 📋 推后 | fix_sprint=- | commit=- | evidence=触发条件为订单数据达到 30M
