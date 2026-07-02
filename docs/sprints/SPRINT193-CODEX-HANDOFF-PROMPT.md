# Sprint 193 Codex 交接提示词

> 用户复制下面整段到 Codex app (1 分钟), Codex 进入 Stage 2 实施模式.
> 实施完回报 Claude 走 Stage 3 review.

---

## 提示词 (从下一行开始复制)

```
我给你一个新任务 Sprint 193, 立项信息如下:

【任务一句话】
把 Sprint 192 close memory 留尾 R1 (REMAIN-4) + R2 (REMAIN-5) 治本:
- R1 (30 min): WorkBuddy 用户 prompt 话术模板沉淀 (docs/user-prompt-template-ad-hoc-query.md, 必含"必用 daily-gsv-multi-period tool"强提示, 跳过 LLM 决策层误判工具缺位)
- R2 (1-2 sprint): Sprint 53 fixture 模式补 test_ad_hoc_query_api 真连 DuckDB (tmp_duckdb_with_synthetic_orders fixture 不依赖 production 100GB 文件, 让 15 case CI 0 SKIPPED)

【HANDOFF 文档】
请先完整读: /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/sprints/HANDOFF-TO-CODEX-Sprint193.md

【必读文件】
- ~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint192_close.md (R1/R2 留尾详情)
- ~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint183_close.md (daily-gsv-multi-period 真业务触发记录)
- ~/.claude/skills/ad-hoc-query/SKILL.md (v2.2 决策树 + 11 tool 速查表)
- scripts/ad_hoc_queries/daily_gsv_multi_period.py (Sprint 183 实施代码, 不要改)
- mcp_servers/fuqing_adhoc/_dispatch.py:225-260 (MCP server tool def, 不要改)
- backend/tests/test_ad_hoc_query_api.py (Sprint 188 B1 12 case + Sprint 190 加 3 case 全 SKIPPED)
- backend/tests/conftest.py:73-140 (Sprint 53 fixture 模式, 参考实现)
- /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/CLAUDE.md (L4.5 / L4.32 / L4.34 / L4.36 / L4.39 永久规则必读)

【worktree + 分支】
已建好,不要再创: 
- worktree: /Users/hutou/Desktop/fuqin-date/wt-sprint193-remain45
- 分支: feature/sprint193-remain4-5
(注意: Sprint 4 P1-2 教训, worktree 分支命名要严格匹配, 推送到 feature/sprint193-remain4-5 跟 commit 时 branch 名一致)

【Stage 2 范围】
按 HANDOFF §3 任务 A 跟 B 顺序做 (任务 A 优先, 30 min 完成; 任务 B 1-2 sprint 范围):
- 任务 A: 3 个交付物 (docs/user-prompt-template-ad-hoc-query.md + 可选 SKILL.md §0.1 + backend/tests/test_user_prompt_template_sprint193.py 2 case)
- 任务 B: 4 个交付物 (conftest.py 加 tmp_duckdb_with_synthetic_orders fixture + test_ad_hoc_query_api.py 顶部改 + test_tmp_duckdb_fixture_sprint193.py 4 case + test_ad_hoc_query_sprint193_synthetic.py 5 case Option B1)

任务 B 走 Option B1 fallback (Sprint 193 完成 5 新 case + Sprint 194 立项剩余 10 case), 不要擅自走 Option B2 全量 15 case 改 (架构师需重评估).

【Stage 3 拍板检查点 (Claude review 时查)】
- pytest 11 case 全 PASS (2 + 4 + 5)
- pytest baseline 净增 5 case, 减 3 SKIPPED (Sprint 192 844/88/0 → Sprint 193 期望 849/85/0)
- ruff check 干净
- 0 直连 DuckDB 业务代码 (grep `duckdb.connect` 在 scripts/ad_hoc_queries/ 下 0 命中)
- 0 复制粘贴 SKILL.md (L4.35 symlink verify)
- 0 macOS-only test 缺 skipif (L4.39)
- 0 绝对路径 hardcode (L4.34)
- 0 subprocess cwd 漂移 (L4.32)
- 任务 A 跟 B 独立 commit (分 2 commit, 不要 1 个巨型 commit)

【硬约束 (0 妥协)】
1. ❌ 改 backend/services/** 已存在函数
2. ❌ 改 backend/routers/** 已存在 endpoint
3. ❌ 改 scripts/ad_hoc_queries/daily_gsv_multi_period.py (Sprint 183 已落地, 0 业务代码改动)
4. ❌ 改 mcp_servers/fuqing_adhoc/server.py 跟 _dispatch.py 协议层
5. ❌ 改 backend/contracts/schemas.py
6. ❌ 复制粘贴 SKILL.md (跨端走 symlink, L4.35 永久规则)
7. ❌ 直连 DuckDB 业务代码 (只允许在 fixture / test 内部)
8. ❌ 写临取数脚本 scripts/adhoc_*.py (Sprint 183 拍板禁写)
9. ❌ 建议用户停 uvicorn (L4.36 永久规则)

【不要碰 git】
不要 git add / commit / push, 留给 Claude 走 12 步流程 (review → qa → merge → push → pull → restart).
Sprint 12 步流程: ① checkout -b (已建) ② 写代码 ③ pytest ④ review ⑤ 修 ⑥ commit ⑦ push ⑧ qa ⑨ merge ⑩ push ⑪ pull ⑫ kill + restart uvicorn + 更新 CHANGELOG.

【回报 Claude 格式】
实施完用 prose 报告 (1 段话):
- 改了哪些文件 (路径 + 行数 diff)
- 新增多少行 (净增 / 净删)
- pytest 数量 (新增 + 全量 baseline)
- ruff check 状态
- 1-3 个 fix_pattern 沉淀 (Sprint 193 fix_pattern #77 #78 候选)
- 任何 STOP 条件 (service 层 SQL 跟 production 强耦合 / 话术模板运营看不懂 / pytest 退化超 3 case)
```

---

## 拍板点

Codex 实施完会主动回报。如果 Codex 长时间没动静, user 复制下面的 follow-up 提示词追问:

```
Sprint 193 HANDOFF 进度如何? 是否在 1.5 任务 B 走 Option B1 fallback 阶段? 有没有触发 STOP 条件?
```

---

## 提示词结束

> **签名**: Claude Code (架构师)
> **日期**: 2026-07-02
> **HANDOFF 路径**: `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/sprints/HANDOFF-TO-CODEX-Sprint193.md`
> **提示词路径**: `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/sprints/SPRINT193-CODEX-HANDOFF-PROMPT.md`
