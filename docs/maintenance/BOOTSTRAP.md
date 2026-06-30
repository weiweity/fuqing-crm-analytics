# BOOTSTRAP — 新开发者必读 (Sprint 68 收口)

> **目的**: 新开发者 clone 仓库后, 必读本文档启用 Claude Code 全部 hook + 留尾 SSOT 治理.

## 1. 必跑步骤 (clone 后)

```bash
# 1. 拉 main
git clone git@github.com:weiweity/fuqing-crm-analytics.git
cd fuqing-crm-analytics

# 2. .claude/settings.json 已 commit (Sprint 68 修 .gitignore 例外化, line 94),
#    但 per-dev local hook 可能被 .gitignore 覆盖, 验证一下:
cat .claude/settings.json | python3 -c "import json, sys; d=json.load(sys.stdin); print('UserPromptSubmit hook:', 'UserPromptSubmit' in d.get('hooks', {}))"
# 期望: UserPromptSubmit hook: True

# 3. 跑留尾 SSOT 治理 hook 测试 (3/3 应 PASS)
python3 -m pytest backend/tests/test_check_remaining_tasks.py -v
# 期望: 3 passed in 0.3s
```

## 2. L4.12 留尾 SSOT 治理 (Sprint 67 收口)

- **SSOT**: `docs/TECH-DEBT.md` 留尾章节 = 跨 sprint 唯一权威
- **触发**: UserPromptSubmit hook 自动注入, 触发词 "剩余任务|留尾|backlog|剩余待办|todo"
- **行为**: 任何 sprint 收口必更新 SSOT (dedup vs close memory), AI 问"剩余任务" 时 hook 自动输出当前真留尾

## 3. 已知 gap (非项目债, 平台限制)

- **MEMORY.md 29.6KB 截断**: Claude Code 平台限制 (24.4KB 系统上限), 不是项目债
  - 不在 L4.12 治理范围
  - 用户本地 auto-memory, 不进 git
  - 治理路径: 每次 sprint 收口后手动 dedupe (USER 拍板), 不自动写避免数据丢失

## 4. CI 维修 (Sprint 60-66 累计)

- CI 4/4 jobs (lint + ground-truth-lint + test + e2e) 全绿
- 平台特定检查 (`sys.platform` / `os.name` / `platform.system()`) **必须** 放 `main()`/CLI 入口, 不能在 `_core()` 逻辑函数 (L4.10)
- 任何 GitHub Action major 升级必先 `gh api tags` 验证 stable tag 真存在 (L4.9)
- 跨 workflow env 同步必加 regression test (Sprint 66 P0 教训)

## 5. 留尾 SSOT 维护 SOP (Sprint 68 收口)

- **Sprint 收口时**: 必 dedup 留尾章节 vs close memory, 加 D1-D4 跨 sprint 推后
- **AI 误列已闭环**: hook 输出已闭环 list, AI 必读 + 不重列
- **TECH-DEBT.md 章节**: "留尾" 章节 = 当前真剩余, "已闭环" 章节 = 历史闭环记录 (Sprint 60+ 实战)

## 6. 累计 sprint

- 12 sprint 0 debt: Sprint 56+60+60.1+60.1.1+60.2+61+62+62.5+63+64+65+66 (Sprint 66 收口日 2026-06-22)
- + Sprint 67+68 留尾治理 (1 commit 0 debt, 2026-06-23)
- = **14 sprint 0 debt 累计**

## Sprint 169-171 收口沉淀（2026-06-30）

- **Sprint 169 02 板块回购周期分布率最终收口**: `memories/project_fuqing_crm_analytics_sprint169_close.md`
- **Sprint 170 RFM 8 象限 → R 6 桶业务口径变更**: 跨 11 service 同步 `backend/semantic/segments.py:R_SEGMENT_ORDER` 公共 SSOT
- **Sprint 171 ad-hoc-query v2.0 升级** + **CI 治本**: `memories/project_fuqing_crm_analytics_document_release_v0_4_14_22.md` + `memories/project_fuqing_crm_analytics_cleanup_2026_06_30.md` + `memories/project_fuqing_crm_analytics_sprint169_third_agent_handoff_resolved.md`
- **新 `/ad-hoc-query` skill v2.0**: `~/.claude/skills/ad-hoc-query/SKILL.md`（391 行，9 子命令规格）
- **WorkBuddy skill 同步**: `~/.workbuddy/skills/ad-hoc-query/SKILL.md`（16468 bytes）
- **实战 fix 模式 #46-52 沉淀**: 公共 SSOT 复用 / 字段全链路 rename / Codex 协作 handoff 模式 / 改 README 引用顺序 / Codex UI sidebar dangling commit 教训 / CI 红 ≠ selector 问题
