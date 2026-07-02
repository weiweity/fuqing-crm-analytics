# Sprint 197 Codex 交接提示词

> 用户复制下面整段到 Codex app (1 分钟), Codex 进入 Stage 2 实施模式.
> 实施完回报 Claude 走 Stage 3 review.

---

## 提示词 (从下一行开始复制)

```
我给你一个新任务 Sprint 197, 立项信息如下:

【任务一句话】
Sprint 196 R1 立的 fixed-product-list-compare (第 12 个 tool, 走 DuckDB read_only conn) 跟 uvicorn 持写锁冲突. Sprint 197 R1 拍板 D 真治本: 立 ad-hoc-query 第 13 个 tool fixed-product-list-compare-http, 走 backend HTTP API, 0 直连 DuckDB, 跟 L4.38 v3 文档化配套. 跟 Sprint 196 R1 5 case 1:1 配套 (Sprint 196 R1 fixed_product_list_compare.py 保留共存).

【HANDOFF 文档】
请先完整读: /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/sprints/HANDOFF-TO-CODEX-Sprint197.md

【必读文件】
- backend/routers/ad_hoc_query.py (加 1 个新 endpoint /api/v1/ad-hoc/fixed-product-list-compare POST, 跟现有 12 endpoint 模式 1:1)
- backend/services/metrics/audience_summary.py:calculate_audience_summary (Sprint 196 R1 已加 product_ids 参数, 0 业务代码改动, 跟 L4.20 SSOT 配套)
- backend/semantic/filters.py:OrderFilters (L4.5 SSOT 入口, 跟现有 12 endpoint 配套)
- mcp_servers/fuqing_adhoc/_dispatch.py:225-260 (加 1 个新 MCP tool def, 跟 daily-gsv-multi-period 1:1 模式)
- scripts/ad_hoc_queries/registry.py:_load_builtins (加 1 行新 import, L4.37 永久规则)
- scripts/ad_hoc_queries/fixed_product_list_compare.py (Sprint 196 R1 落地, 339 行, 走 DuckDB read_only conn, 跟 uvicorn 持写锁冲突, **保留共存不删**)
- backend/tests/test_fixed_product_list_compare_sprint196.py (Sprint 196 R1 5 case, 加 1 个 TestClass TestSprint197Http 5 case)
- scripts/ad_hoc_queries/_utils.py:read_only_conn (**不要复用**, Sprint 53 race flake 治本不彻底)
- ~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint196_close.md (Sprint 196 R1 收口沉淀)
- /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/CLAUDE.md (L4.5/L4.20/L4.36/L4.37/L4.38/L4.41/L4.46 永久规则必读)

【worktree + 分支】
已建好, 不要再创:
- worktree: /Users/hutou/Desktop/fuqin-date/wt-sprint197-fixed-product-list-http
- 分支: feature/sprint197-fixed-product-list-http
(注意: Sprint 4 P1-2 教训, worktree 分支命名要严格匹配)

【Stage 2 范围】
按 HANDOFF §3 任务 1 跟任务 2 顺序做 (任务 1 优先, 0.5-1 天; 任务 2 0.5 天):

- 任务 1: 立 ad-hoc-query 第 13 个 tool fixed-product-list-compare-http (走 HTTP API 不直连 DuckDB)
  * Step 1.1: 在 backend/routers/ad_hoc_query.py 加 1 个新 endpoint /api/v1/ad-hoc/fixed-product-list-compare POST, 走 calculate_audience_summary SSOT 入口
  * Step 1.2: 新建 scripts/ad_hoc_queries/fixed_product_list_compare_http.py (~80 行, 调 requests.post 走 HTTP API, 0 直连 DuckDB)
  * Step 1.3: 改 mcp_servers/fuqing_adhoc/_dispatch.py 加 1 个新 MCP tool def
  * Step 1.4: 改 scripts/ad_hoc_queries/registry.py:_load_builtins() 加 1 行新 import (L4.37 永久规则)
  * Step 1.5: SKILL.md v2.4 → v2.5 升级 (L4.35 symlink 跨端 1 份, 加 1 个新 tool 描述 + §0.4 段)

- 任务 2: 写 LLM 评估脚本 1 个 TestClass 5 case (跟 Sprint 196 R1 fix_pattern #81 配套)
  * 在 backend/tests/test_fixed_product_list_compare_sprint196.py 加 1 个 TestClass TestSprint197Http 5 case
  * 5 case 全 PASS, 命中率 5/5 = 100%
  * 跟之前 2026-06-30 跑过 2 次 1:1 一致 (回归测试)

【Stage 3 拍板检查点 (Claude review 时查)】
- 任务 1 13 tool 注册 + 5 step 落地
- 任务 2 5 case 全 PASS + 命中率 5/5 = 100%
- pytest baseline 962/73/0 → 967/73/0 (净 +5 case)
- 跟之前 2026-06-30 跑过 2 次 1:1 一致
- ruff check 干净
- 任务 1 跟任务 2 独立 commit (分 2 commit)
- Sprint 196 R1 fixed_product_list_compare.py 保留共存 (不删)

【硬约束 (0 妥协)】
1. ❌ 改 backend/services/audience_summary._extract_metrics SSOT 5 个 YOY/MOM 纯函数 (L4.20 反漂移, 跨 sprint 60+ 沉淀)
2. ❌ 改 backend/routers/ad_hoc_query.py 已存在 12 endpoint 逻辑
3. ❌ 改 mcp_servers/fuqing_adhoc/server.py 协议层
4. ❌ 改 backend/contracts/schemas.py
5. ❌ 复制粘贴 SKILL.md (L4.35 永久规则)
6. ❌ scripts/ad_hoc_queries/fixed_product_list_compare_http.py 调 read_only_conn (L4.38 v3 配套, 跟 uvicorn 持写锁冲突)
7. ❌ 写临取数脚本 scripts/adhoc_*.py (L4.5 禁写, Sprint 193 治本)
8. ❌ 建议用户停 uvicorn (L4.36 永久规则)
9. ❌ 改 daily_gsv_multi_period.py / audience_summary.py 已有 SQL (Sprint 183/60+ 沉淀)
10. ❌ 删除 scripts/ad_hoc_queries/fixed_product_list_compare.py (Sprint 196 R1 落地, 跟 Sprint 197 R1 共存)

【不要碰 git】
不要 git add / commit / push, 留给 Claude 走 12 步流程.

【回报 Claude 格式】
实施完用 prose 报告 (1 段话):
- 改了哪些文件 (路径 + 行数 diff)
- 任务 1 13 tool 注册验证 (跑 list-endpoints 期望 'fixed-product-list-compare-http' 出现)
- 任务 2 5 case pytest PASS 状态 + 命中率统计
- 跟之前 2026-06-30 跑过 2 次 1:1 一致 (回归测试对比)
- ruff check 状态
- 任何 STOP 条件
```

---

## 拍板点

Codex 实施完会主动回报。如果 Codex 长时间没动静, user 复制下面的 follow-up 提示词追问:

```
Sprint 197 进度如何? 任务 1 13 tool 注册好了没? 任务 2 5 case pytest 跑通没? 跟之前 2026-06-30 跑过 2 次 1:1 一致吗?
```

---

## 提示词结束

> **签名**: Claude Code (架构师)
> **日期**: 2026-07-02
> **HANDOFF 路径**: `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/sprints/HANDOFF-TO-CODEX-Sprint197.md`
> **提示词路径**: `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/sprints/SPRINT197-CODEX-HANDOFF-PROMPT.md`
