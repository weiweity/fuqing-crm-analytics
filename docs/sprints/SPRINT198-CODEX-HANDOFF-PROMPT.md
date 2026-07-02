# Sprint 198 Codex 交接提示词

> 用户复制下面整段到 Codex app (1 分钟), Codex 进入 Stage 2 实施模式.
> 实施完回报 Claude 走 Stage 3 review.

---

## 提示词 (从下一行开始复制)

```
我给你一个新任务 Sprint 198, 立项信息如下:

【任务一句话】
Sprint 197 R1 立的 fixed-product-list-compare-http (第 13 个 tool) 跟 Sprint 196 R1 fixed-product-list-compare (第 12 个 tool) 共存, 但用户的 "AI 命中不到 → 自行跑数" 期望还没治本. Sprint 198 R1 拍板选项 3 真治本: 立 ad-hoc-query 第 14 个 tool ai-sandbox-execute, 接受 SQL 字符串 + 走 backend service SSOT 入口 + 写 audit log (/tmp/fuqing_adhoc_audit.log), 跟 L4.5 + L4.20 + L4.36 + L4.38 + L4.41 + L4.46 + fix_pattern #81 + fix_pattern #82 永久规则 全部配套.

【HANDOFF 文档】
请先完整读: /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/sprints/HANDOFF-TO-CODEX-Sprint198.md

【必读文件】
- backend/services/audience_summary.py:calculate_audience_summary (SSOT 入口, L4.20, Sprint 60+ 沉淀)
- backend/semantic/filters.py:OrderFilters (L4.5 SSOT 入口)
- backend/routers/ad_hoc_query.py (加 1 个新 endpoint /api/v1/ad-hoc/ai-sandbox-execute POST, 跟现有 12 endpoint 模式 1:1)
- mcp_servers/fuqing_adhoc/_dispatch.py:225-260 (加 1 个新 MCP tool def, 跟 daily-gsv-multi-period 1:1 模式)
- scripts/ad_hoc_queries/registry.py:_load_builtins (加 1 行新 import, L4.37 永久规则)
- scripts/ad_hoc_queries/fixed_product_list_compare_http.py (Sprint 197 R1 落地, 1:1 范本, 跟 Sprint 198 R1 模式 stable)
- scripts/ad_hoc_queries/_utils.py:read_only_conn (**不要复用**, L4.38 v3 配套)
- backend/services/sampling_service.py + lifetime_value.py + rfm/* (Sprint 198 R1 sandbox 可选 backend service)
- ~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint197_close.md (Sprint 197 R1 收口沉淀)
- /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/CLAUDE.md (L4.5/L4.20/L4.36/L4.37/L4.38/L4.41/L4.46 永久规则必读)

【worktree + 分支】
已建好, 不要再创:
- worktree: /Users/hutou/Desktop/fuqin-date/wt-sprint198-ai-sandbox-execute
- 分支: feature/sprint198-ai-sandbox-execute
(注意: Sprint 4 P1-2 教训, worktree 分支命名要严格匹配)

【Stage 2 范围】
按 HANDOFF §3 任务 1 跟任务 2 顺序做 (任务 1 优先, 0.5-1 天; 任务 2 0.5 天):

- 任务 1: 立 ad-hoc-query 第 14 个 tool ai-sandbox-execute (走 backend service SSOT + audit log)
  * Step 1.1: 新建 backend/services/ai_sandbox.py:ai_sandbox_execute (~80 行, 走 SSOT 入口, 写 audit log, _validate_sql_security 拦 DROP/DELETE/TRUNCATE/INSERT/UPDATE/EXEC, 跟 L4.5 0 写库配套)
  * Step 1.2: 改 backend/routers/ad_hoc_query.py 加 1 个新 endpoint /api/v1/ad-hoc/ai-sandbox-execute POST (跟现有 12 endpoint 模式 1:1)
  * Step 1.3: 新建 scripts/ad_hoc_queries/ai_sandbox_execute.py (~80 行, 调 requests.post 走 HTTP API, 0 直连 DuckDB)
  * Step 1.4: 改 mcp_servers/fuqing_adhoc/_dispatch.py 加 1 个新 MCP tool def (跟 daily-gsv-multi-period 1:1 模式)
  * Step 1.5: 改 scripts/ad_hoc_queries/registry.py:_load_builtins() 加 1 行新 import (L4.37 永久规则)
  * Step 1.6: SKILL.md v2.5 → v2.6 升级 (L4.35 symlink 跨端 1 份, 加 1 个新 tool 描述 + §0.5 段)

- 任务 2: 写 LLM 评估脚本 5 case 5 TestClass (跟 Sprint 197 R1 fix_pattern #81 配套)
  * 新建 backend/tests/test_ai_sandbox_execute_sprint198.py (5 case, 5 TestClass: SandboxAudienceSummarySSOT + SandboxSQLInjectionPrevention + SandboxAuditLogWritten + SandboxRoutingAccuracy + SandboxSyntheticDuckdb)
  * 5 case 全 PASS, 命中率 5/5 = 100% (跟 fix_pattern #81 配套)
  * 跟 L4.5 0 写库永久规则配套: _validate_sql_security 拦 DROP/DELETE/TRUNCATE/INSERT/UPDATE/EXEC
  * 跟 audit log 配套: /tmp/fuqing_adhoc_audit.log 写正确

【Stage 3 拍板检查点 (Claude review 时查)】
- 任务 1 14 tool 注册 + 6 step 落地
- 任务 2 5 case 全 PASS + 命中率 5/5 = 100%
- pytest baseline 967/73/0 → 972/73/0 (净 +5 case)
- audit log 验证 (L4.5 + fix_pattern #81 配套)
- ruff check 干净
- 任务 1 跟任务 2 独立 commit (分 2 commit)
- Sprint 197 R1 fixed_product_list_compare_http 保留共存 (不删)

【硬约束 (0 妥协)】
1. ❌ 改 backend/services/audience_summary._extract_metrics SSOT 5 个 YOY/MOM 纯函数 (L4.20 反漂移, 跨 sprint 60+ 沉淀)
2. ❌ 改 backend/routers/ad_hoc_query.py 已存在 12 endpoint 逻辑
3. ❌ 改 mcp_servers/fuqing_adhoc/server.py 协议层
4. ❌ 改 backend/contracts/schemas.py
5. ❌ 复制粘贴 SKILL.md (L4.35 永久规则)
6. ❌ scripts/ad_hoc_queries/ai_sandbox_execute.py 调 read_only_conn (L4.38 v3 配套, 跟 uvicorn 持写锁冲突)
7. ❌ 写临取数脚本 scripts/adhoc_*.py (L4.5 禁写, Sprint 193 治本)
8. ❌ 建议用户停 uvicorn (L4.36 永久规则)
9. ❌ 改 daily_gsv_multi_period.py / audience_summary.py 已有 SQL (Sprint 183/60+ 沉淀)
10. ❌ AI 走的 SQL 含 DROP/DELETE/TRUNCATE/INSERT/UPDATE/EXEC (0 写库, 跟 L4.5 配套, _validate_sql_security 拦)
11. ❌ AI 走的 SQL 跨多语句注入漂移 SSOT
12. ❌ 删除 scripts/ad_hoc_queries/fixed_product_list_compare_http.py (Sprint 197 R1 落地, 跟 Sprint 198 R1 共存)

【不要碰 git】
不要 git add / commit / push, 留给 Claude 走 12 步流程.

【回报 Claude 格式】
实施完用 prose 报告 (1 段话):
- 改了哪些文件 (路径 + 行数 diff)
- 任务 1 14 tool 注册验证 (跑 list-endpoints 期望 'ai-sandbox-execute' 出现)
- 任务 2 5 case pytest PASS 状态 + 命中率统计
- audit log 验证 (跑完有 /tmp/fuqing_adhoc_audit.log 记录)
- SQL 注入防御验证 (跑 DROP/DELETE 应被 _validate_sql_security 拦)
- ruff check 状态
- 任何 STOP 条件
```

---

## 拍板点

Codex 实施完会主动回报。如果 Codex 长时间没动静, user 复制下面的 follow-up 提示词追问:

```
Sprint 198 进度如何? 任务 1 14 tool 注册好了没? 任务 2 5 case pytest 跑通没? audit log 写正确吗? SQL 注入防御 OK 吗?
```

---

## 提示词结束

> **签名**: Claude Code (架构师)
> **日期**: 2026-07-02
> **HANDOFF 路径**: `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/sprints/HANDOFF-TO-CODEX-Sprint198.md`
> **提示词路径**: `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/sprints/SPRINT198-CODEX-HANDOFF-PROMPT.md`
