---
name: ad-hoc-query
description: 即席查询 — 让 LLM 通过 MCP tools 调 backend service 口径取数（WorkBuddy 一等公民, **18 个 tool**, 跟 Sprint 203 R5 14→18 累计 1:1 stable). **Sprint 203 R5 + Sprint 198 + Sprint 197 + Sprint 196 治本** (Sprint 203 R5 加 4 件新 tool: channel-monthly / member-monthly / refund-monthly / cross-dimension-monthly + top_n 月/季/年 axis 扩; Sprint 198 加 ai-sandbox-execute 第 14 个 tool, AI 命中不到固定 tool 时走 backend sandbox service + audit log; Sprint 197 加 fixed-product-list-compare-http 第 13 个 tool, 固定清单走 HTTP API 0 DuckDB 子进程锁冲突; Sprint 196 加 fixed-product-list-compare 第 12 个 tool, 固定清单 + 新老客 + 两年对比 + TTL/单品层级; Sprint 195 R1 治本 AI 问数准确率 ≥95%; Sprint 190 决策树 用户提到"按天 + 8 维度 + 多周期" → MUST call `daily-gsv-multi-period`). 触发关键词: "小样/派样/会员/新客/老客/按天/多周期/月报/季报/年报/退款/按渠道" + "GSV/GMV" / "两年对比" / "TOP20" / "整份 Excel" / "排查数据" / "WorkBuddy 帮我跑个数" / "固定清单" / "单品概览" / "AI 自行跑数" / "工具命中不到" / "渠道占比" / "会员占比". 不要误判工具缺位, 不要写临时脚本 (L4.5 永久规则), 锁冲突走 HTTP/sandbox 路径.
disable-model-invocation: false
---

# /ad-hoc-query — 即席查询（WorkBuddy MCP 版, v2.7）

> **WorkBuddy LLM 专用版**: 你不需要 shell、不需要 CLI 参数解析、不需要写 Python。直接调 MCP tools 即可。所有取数走 `backend/services/*` SSOT 口径，零写库、零直连 DuckDB、零前端依赖。
>
> **架构链路**: `LLM (你) → fuqing_adhoc MCP server → scripts/ad_hoc_query.py CLI → scripts/ad_hoc_queries/* → backend/services/* → DuckDB (read_only)`.
>
> **SSOT 同步**: 本文件同时被 `~/.claude/skills/ad-hoc-query/SKILL.md` 和 `~/.workbuddy/skills/ad-hoc-query/SKILL.md` 通过 symlink 消费（**L4.35 永久规则**: 跨端 SKILL 必走软链，不复制粘贴）。

**Sprint 203 R5 14 → 18 tool 累计**: channel-monthly (Sprint 199 R1 留尾任务 A 实证) + member-monthly (is_member 按月) + refund-monthly (is_refund 按月) + cross-dimension-monthly (6 维白名单交叉按月) + top_n 月/季/年 axis 扩 (跟 Sprint 190 daily-gsv-multi-period 1:1 stable DRY 模式). 跟 SKILL.md v2.7 速查表 1:1 stable.

---

## 0. 执行路径强制 (P0 - WorkBuddy 必读)

用户给取数需求 → **直接调 MCP tools** → 14 个 tool 已在 `~/.workbuddy/.mcp.json` 注册 `fuqing_adhoc` stdio server。

**Sprint 190 决策树 (LLM 必读, 防工具缺位误判)**:
- 需求说 "**按天 + 8 维度 (小样/会员/新老客 GMV/GSV/人数) + 多周期**" → **必用 `daily-gsv-multi-period`**
- 需求说 "**按天 + 2 周期对比**" → **必用 `daily-gsv-multi-period`**
- 需求说 "**最近 N 天 GSV 趋势 (全店)**" → 用 `daily_gsv` 单周期
- 需求说 "**两年 30 指标对比**" → 用 `two_year_overview` 汇总
- 需求说 "**30 指标 + order_ids/订单号清单**" → **必用 `two_year_overview`** (新支持 order_ids)
- 需求说 "**小样/会员/新老客 单独维度**" → 必用 `daily-gsv-multi-period` + 指定 metrics

**⚠️ 必读告警**: 需求包含 2 个以上维度(小样/会员/新老客) + 2 个以上周期 + 按天 = 100% 命中 `daily-gsv-multi-period`. **不要**走 `daily_gsv` (全店) 或 `new_old_customer` (汇总) 凑数. **不要**报"工具缺位" + 临时脚本.

**禁止路径** (走任何一条都会失败):
- ❌ 查 openapi.json HTTP API (Sprint 183+ 才考虑; Sprint 182 当前不支持组合查询)
- ❌ 直连 DuckDB (read_only Conn 在 uvicorn 持写锁时仍冲突, Sprint 53 race flake 治本不彻底)
- ❌ 写 scripts/adhoc_*.py 临时脚本 (Sprint 171 v2.0 CLI 已有完整实现, 重复造轮子违反 L4.5)
- ❌ 建议用户停 uvicorn (本地即生产, launchctl unload 是不可逆破坏, L4.36 永久规则)
- ❌ 报"工具缺位"前没查 §1.5 速查表 (Sprint 190 升级, 95% 情况都有现成 tool)

**强制路径**:
1. 读本 SKILL.md 顶部 "0. 决策树" (本节) → 直接锁定 tool
2. 查 §1 14 个 MCP tools 一览 + §1.5 需求-工具映射速查表 + §1.5.1 关键词同义词库
3. 不确定 → 调 `ask(query)` NL 路由
4. 工具够 → 直接调, 不要写临时脚本

## 0.1 运营问数话术模板 (Sprint 193 沉淀)

用户给取数需求时, 先给用户看 [话术模板 5 模板 + 关键词必查表](file:///Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/user-prompt-template-ad-hoc-query.md), 让用户复制模板发问, 跳过 LLM 决策层, 95% 命中现成 tool. 话术模板 Sprint 193 治本, 配套 L4.36 禁停 uvicorn 永久规则.

## 0.2 ask 路由表补全 + LLM 评估脚本 (Sprint 195 R1 收敛方案 1 件事)

Sprint 195 治本 Sprint 183 + Sprint 190 跨 2 sprint 复发的"工具缺位"误判根因之一 (`ask` 路由表 0 关键词命中 `daily-gsv-multi-period`):

- **ask 路由表补 5 关键词**: `scripts/ad_hoc_queries/ask.py:_route_table` 加 `daily-gsv-multi-period` 条目, 关键词 `("小样", "派样", "多周期", "8 维度", "周期对比")` 5 词全命中 (跟 Sprint 190 决策树 1:1 配套). param_builder 抽 periods (start, end + 去年同期), metrics 默认 None (全 8 个)
- **LLM 评估脚本 25 case 5 TestClass**: `backend/tests/test_llm_eval_sprint195.py` 5 TestClass = HighFrequencyScenarios 5 + Sprint183190TriggeredCases 5 + AskRouterRegression 5 + EdgeCases 5 + RoutingAccuracy 5. 实测 25 PASS + TestClass 5 命中率 5/5 = **100.0%** (期望 ≥95%)

## 0.3 fixed-product-list-compare 第 12 个 tool (Sprint 196 plan-eng-review B 治本)

Sprint 195 后续 plan-eng-review 评审发现真缺位: Sprint 193 R1 收口"禁临时脚本"没补 ad-hoc-query 11 tool 覆盖"按固定产品清单", 留下能力缺口. 之前能取 (2026-06-30 + 2026-07-01 用 `scripts/_archive/adhoc_product_new_old.py` 跑过 2 次), Sprint 193 收口后 11 tool 0 覆盖 → 走真缺位 (Sprint 195 R1 §1.5.2 第 1 种). Sprint 196 B 治本 = 把临时脚本能力**固化为第 12 个 tool `fixed-product-list-compare`**, 复用 backend/services SSOT:

- **新建 tool**: `scripts/ad_hoc_queries/fixed_product_list_compare.py` (339 行, 复刻 `_archive/adhoc_product_new_old.py` 60+ product_id + CATEGORY_GROUPS 4 大类; Sprint 196 实证: 实际 35 product_id + 3 TTL 分组, 跟 handoff 范本 60+/4 组 数字错, 跟 L4.42 立项信息实证 + L4.20 SSOT 反漂移 consistent, 归档源是真实 SSOT)
- **backend/service 加 product_ids 参数**: `backend/services/metrics/audience_summary.py:calculate_audience_summary` 加 1 行新参数 + WHERE 段拼凑, 跟 L4.5 SSOT OrderFilters 配套, **0 业务代码改动** (不动 5 个 YOY/MOM 纯函数)
- **ask 路由表配套**: `scripts/ad_hoc_queries/ask.py` 加 fixed-product-list-compare 关键词, 跟 Sprint 195 R1 5 关键词模式 1:1, 跑 ask("按固定清单单品对比 2026 H1") 命中新 tool 1:1
- **LLM 评估脚本 5 case 5 TestClass**: `backend/tests/test_fixed_product_list_compare_sprint196.py` 5 TestClass = FixedProductListCompare + AskRouterRegression + EdgeCases + BackendServiceSSOT + Synthetic. 实测 5 PASS + 命中率 5/5 = 100%, 跟之前 2026-06-30 跑过的 2 次输出 1:1 一致 (回归测试实证)
- **用户拍板 (跟 Sprint 195 R1 "duckdb 不做功能新增" 冲突, 用户重新拍板)**: 真业务触发 (用户当前问 + 之前 2 次跑过) → 立新 tool, 跟 L4.42 立项信息实证 + L4.46 user prompt 强提示配套

详细见 Sprint 196 close memory `~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint196_close.md` (跟 Sprint 192/193/194/195 模式 stable, 累计 27 次 /document-release).
- **fix_pattern #81**: 任何 AI 问数新 tool 上线前, 必先跑 `test_llm_eval_<sprint>.py` 验命中率 ≥95% 才允许 commit. 跟 L4.46 / Sprint 183/190 跨 sprint 复发教训配套
- **配套对话关键词**: 跟 SKILL.md v2.2 决策树 (§0) + 关键词同义词库 (§1.5.1) + 报缺位自检 4 步 (§1.5.2) 3 层防御, 治根 LLM 决策层 false positive (Sprint 183/190 跨 2 sprint 复发的真因)

详细见 Sprint 195 close memory `~/.claude/projects/-Users-hutou/project_fuqing_crm_analytics_sprint195_close.md` (跟 Sprint 192/193/194 模式 stable, 累计 26 次 /document-release).

## 0.4 fixed-product-list-compare-http 第 13 个 tool (Sprint 197 R1 锁冲突治本)

Sprint 196 的 `fixed-product-list-compare` 仍保留共存，但它作为 CLI query 会在子进程里走 DuckDB read_only 路径。若 uvicorn 主进程持有 DuckDB 写锁，子进程 read_only 也会被 OS flock 拦住。Sprint 197 R1 新增 **`fixed-product-list-compare-http`**：同样的固定产品清单能力，但通过 backend HTTP API `/api/v1/ad-hoc/fixed-product-list-compare` 在 uvicorn 进程内执行，0 直连 DuckDB 子进程，0 建议停 uvicorn。

- 需求说"固定清单 / 单品新老客 / 锁冲突 / 现在就跑" → 优先用 `fixed_product_list_compare_http`
- `fixed-product-list-compare` 继续作为旧 CLI/tool 共存，不删除
- HTTP wrapper 默认读 `FQ_CRM_AUTH_TOKEN` 作为 Bearer token

## 0.5 ai-sandbox-execute 第 14 个 tool (Sprint 198 R1 AI 命中不到治本)

当需求确实不在固定 13 个工具覆盖内时，不要写 `scripts/adhoc_*.py` 临时脚本。Sprint 198 R1 新增 **`ai_sandbox_execute`**：接受单条只读 `SELECT/WITH` SQL，经 backend `/api/v1/ad-hoc/ai-sandbox-execute` 进入 service，在 uvicorn 进程内用 shared connection 执行，并写 `/tmp/fuqing_adhoc_audit.log`。

- 只允许单条 `SELECT/WITH`; 拦 `DROP/DELETE/TRUNCATE/INSERT/UPDATE/EXEC` 和多语句
- 查询 `orders` 时必须带 `OrderFilters.valid_order()` 三条件，避免 SSOT 漂移
- 所有执行写 audit log；audit 失败不影响业务查询

## 0.6 月维度业务兜底段 (Sprint 203 R5 新增, 月报核心)

当需求是 **月报 / 季报 / 年报 / 月度数据 / 季度数据 / 月度趋势** 这类**业务月度报告**场景时, WorkBuddy LLM 必须按以下优先级匹配:

1. **"X 月 / X 月份 / X 月度"** → 必用 **按月工具** (Sprint 203 R5 4 件新 tool):
   - `channel_monthly(start="2026-01", end="2026-06")` → 按渠道切片月维度 (货架/达播/直播/淘客/微博 月度占比)
   - `member_monthly(start="2026-01", end="2026-06")` → 会员 vs 非会员 月度 GSV + 占比
   - `refund_monthly(start="2026-01", end="2026-06")` → 退款率月度趋势监控
   - `cross_dimension_monthly(start="2026-01", end="2026-06", dim1="channel", dim2="is_member")` → 会员中各渠道占比 / 衍生交叉场景

2. **"X 季度 / Q1/Q2/Q3/Q4"** → 必用 `top_n(dimension, --axis quarterly, --quarter "2026-Q2")` (Sprint 203 R5 月/季/年 axis 扩, 跟 Sprint 190 daily-gsv-multi-period 1:1 stable DRY 模式)

3. **"X 年度 / 全年"** → 必用 `top_n(dimension, --axis yearly, --year "2026")`

4. **"X 月份 TOP20"** → 必用 `top_n(dimension, --axis monthly, --month "2026-06")` (Sprint 203 R5 月维度 + 多年对比)

**禁止路径**:
- ❌ 走 `daily_gsv(start, end)` + 自行按月汇总 (业务月度报告 1M+ orders 跑 30 次浪费, Sprint 203 R5 月维度工具直接做)
- ❌ 报 "工具缺位, 没按月汇总 tool" (Sprint 203 R5 4 件新 tool 已覆盖)
- ❌ 走 `two_year_overview` 凑数 (它是整年指标对比, 不是月度聚合)
- ❌ 走 `ai_sandbox_execute` 写临时 SQL (Sprint 198 R1 治本, 禁临时脚本)

**强制路径**:
1. 读 §0.6 本节 + §1.5 速查表 (Sprint 203 R5 月度 + 季度 + 年度 + 多维度交叉行)
2. 必用 4 件 Sprint 203 R5 月维度工具
3. 不确定 → 调 `ask(query)` NL 路由

## 0.7 多维度交叉按月业务兜底段 (Sprint 203 R5 新增, 衍生交叉场景)

当需求涉及 **多个维度同时切片** (e.g. "X 月份会员中各渠道占比" / "X 月份各品类在各渠道销售" / "X 月份购金金贡献渠道") 时:

1. **必用 `cross_dimension_monthly(start, end, dim1, dim2)`**:
   - 6 维白名单: `channel` / `is_member` / `is_goujinjin` / `spu_category` / `spu_tier` / `spu_product_class` (跟 L4.5 FilterBuilder 1:1 stable 防护 SQL 注入)
   - 4 件新 tool 任意组合, 业务组合举例:
     - `dim1="channel", dim2="is_member"` → 会员 vs 非会员 各渠道占比
     - `dim1="spu_category", dim2="channel"` → 各品类在各渠道销售 (跨品类分析)
     - `dim1="is_goujinjin", dim2="channel"` → 购金金贡献渠道
     - `dim1="channel", dim2="spu_tier"` → 渠道 × 商品梯队
     - `dim1="is_member", dim2="spu_product_class"` → 会员 × 单品归类
     - `dim1="is_goujinjin", dim2="spu_category"` → 购金金 × 品类

2. **dim1 + dim2 必填, 来自 6 维白名单** (跟 L4.5 FilterBuilder 1:1 stable, 禁任何 inline 字符串)
3. **跨 sprint 留尾**: Sprint 204+ Phase 3 留尾 (traffic_source / influencer_name / province / city 按月) + YTD/QTD/MTD 滚动窗口 (跟 Sprint 203 R5 月/季/年 axis 1:1 stable 续期)

**禁止路径**:
- ❌ 走 2 次单维度 tool 然后在 LLM 端合并 (跨进程 IO 浪费, cross_dimension_monthly 一次查询出结果)
- ❌ 报 "工具缺位, 没交叉维度" (Sprint 203 R5 cross_dimension_monthly 已覆盖)
- ❌ 走 `ai_sandbox_execute` 写 JOIN SQL (Sprint 198 R1 治本, 禁临时脚本)

**强制路径**:
1. 读 §0.7 本节 + §1.5 速查表 cross_dimension_monthly 行
2. 必用 `cross_dimension_monthly(start, end, dim1, dim2)` (6 维白名单)
3. 不确定 → 调 `ask(query)` NL 路由

## 1. 18 个 MCP tools 一览 (Sprint 198 14 tool + Sprint 203 R5 4 件新 tool, 跟 Sprint 60+ 1:1 stable 模式)

| # | Tool 名 | 用途 | 主要参数 |
|---|---|---|---|
| 1 | `daily_gsv` | 日序列 GSV + 客户数 + YOY% | `start`, `end` |
| 2 | `yoy_battle` | 双窗口 YOY 战斗 | `baseline_start`, `baseline_end`, `current_start`, `current_end`, `metric` |
| 3 | `channel_slice` | 按渠道切片（货架/达播/直播/全店） | `date`, `channel`, `compare` |
| 4 | `two_year_overview` | 两年 30 指标对比（最高优先级） | `year`, `period`, `start`, `end`, `exclude_channels`, `order_ids` |
| 5 | `new_old_customer` | 新老客拆分对比 | `start`, `end`, `exclude_channels`, `dimension` |
| 6 | `rfm_repurchase` | R 区间 6 桶复购周期分布（Sprint 170 口径） | `start`, `end`, `channel` |
| 7 | `top_n` | TOP20 品类 / 单品 / SPU, **axis: daily/monthly/quarterly/yearly** (Sprint 203 R5 扩) | `dimension`, `start`, `end`, `axis?`, `month?`, `quarter?`, `year?`, `exclude_channels?`, `limit?` |
| 8 | `export_excel` | 整份 11 sheet Excel 报告 | `start`, `end`, `exclude_channels` |
| 9 | `dq_report` | 数据排查 15 项校验 | `start`, `end`, `full` |
| 10 | `ask` | 自然语言路由（不调 LLM, 关键词正则） | `query` |
| 11 | `daily-gsv-multi-period` | 多周期 × 8 维度按天序列 | `periods`, `metrics` |
| 12 | **`fixed-product-list-compare`** (Sprint 196) | 固定产品清单 + 新老客 + 两年对比 + TTL/单品层级 (旧 CLI 共存) | `start_date`, `end_date`, `product_ids`, `mom_start_date`, `mom_end_date` |
| 13 | **`fixed_product_list_compare_http`** (Sprint 197) | 固定产品清单 HTTP API 版，0 DuckDB 子进程锁冲突 | `start_date`, `end_date`, `product_ids`, `mom_start_date`, `mom_end_date`, `auth_token` |
| 14 | **`ai_sandbox_execute`** (Sprint 198) | AI 命中不到固定 tool 时走 backend sandbox service + audit log | `sql`, `sandbox_type`, `audit_id`, `auth_token` |
| 15 | **`channel_monthly`** (Sprint 203 R5) | **按 channel 切片月维度** (Sprint 199 R1 留尾任务 A 实证, 月报核心) | `start: YYYY-MM`, `end: YYYY-MM`, `channel?` |
| 16 | **`member_monthly`** (Sprint 203 R5) | **按 is_member 切片月维度** + 占比 + YOY (会员留存分析) | `start: YYYY-MM`, `end: YYYY-MM` |
| 17 | **`refund_monthly`** (Sprint 203 R5) | **按 is_refund 切片月维度** + 退款率 + 退款金额 + YOY (退款监控必备) | `start: YYYY-MM`, `end: YYYY-MM` |
| 18 | **`cross_dimension_monthly`** (Sprint 203 R5) | **通用多维度交叉按月** (channel × is_member / spu_category × channel / is_goujinjin × channel, 6 维白名单) | `start: YYYY-MM`, `end: YYYY-MM`, `dim1`, `dim2` |

---

## 1.5 需求-工具映射速查表 (Sprint 183 v2.2 + Sprint 190 升级 + Sprint 195 R1 ask 路由表补全 + Sprint 203 R5 月维度 + 多维度交叉)

| 用户表达 (运营场景) | 推荐 tool | inputSchema | 关键词触发 |
|---|---|---|---|
| 最近 N 天 GSV 趋势 | `daily_gsv(start, end)` | start, end, format?, output? | "GSV 趋势" / "日 GSV" / "日序列" |
| 两年 GSV 对比 | `two_year_overview(year, period?)` | year, period?, start?, end?, exclude_channels? | "两年对比" / "30 指标" / "今年 vs 去年" |
| 30 指标 + order_ids 清单 | `two_year_overview(year, start, end, order_ids=...)` | year, start?, end?, order_ids: list[str] | "订单号清单" / "按这些订单" / "matched order set" |
| 新老客 GSV 拆分 | `new_old_customer(start, end, dimension?)` | start, end, exclude_channels?, dimension? | "新老客" / "新客 GSV" / "老客 GSV" |
| TOP20 品类 / 单品 / SPU | `top_n(dimension, start, end, axis?)` | dimension, start, end, axis: daily/monthly/quarterly/yearly, month?, quarter?, year?, exclude_channels?, limit? | "TOP20" / "品类排行" / "单品" |
| **TOP20 月度 (新增 Sprint 203 R5!)** | `top_n(dimension, --axis monthly, --month YYYY-MM)` | dimension (spu_category / spu_product_class / spu_tier 等 8 维), month: YYYY-MM | "TOP20 月度" / "月报品类" / "单品月度排行" |
| 整份 11 sheet Excel | `export_excel(start, end)` | start, end, exclude_channels? | "导出 Excel" / "11 sheet" / "整份报告" |
| 数据质量排查 | `dq_report(start, end, full?)` | start, end, full? | "数据质量" / "排查" / "校验" |
| 渠道切片 | `channel_slice(date)` | date, channel?, compare? | "渠道切片" / "货架 / 达播 / 直播" |
| **渠道按月 (新增 Sprint 203 R5! 月报核心)** | **`channel_monthly(start, end, channel?)`** | start: YYYY-MM, end: YYYY-MM, channel: all/online/offline/具体渠道名 | **"渠道按月" / "淘客按月" / "渠道月报" / "月维度"** |
| **会员按月 (新增 Sprint 203 R5! 会员留存分析)** | **`member_monthly(start, end)`** | start: YYYY-MM, end: YYYY-MM | **"会员按月" / "会员留存" / "is_member 月度"** |
| **退款率按月 (新增 Sprint 203 R5! 退款监控)** | **`refund_monthly(start, end)`** | start: YYYY-MM, end: YYYY-MM | **"退款率" / "退款按月" / "is_refund 月度"** |
| **多维度交叉按月 (新增 Sprint 203 R5! 衍生机会)** | **`cross_dimension_monthly(start, end, dim1, dim2)`** | start: YYYY-MM, end: YYYY-MM, dim1 + dim2 ∈ 6 维白名单 (channel / is_member / is_goujinjin / spu_category / spu_tier / spu_product_class) | **"会员中各渠道占比" / "各品类在各渠道销售" / "购金金贡献渠道"** |
| YOY 战斗对比 | `yoy_battle(...)` | baseline_start, baseline_end, current_start, current_end, metric? | "YOY 战斗" / "618 大促" / "去年同期" |
| R 区间复购周期 | `rfm_repurchase(start, end)` | start, end, channel? | "R 区间" / "复购周期" / "Sprint 170 RFM" |
| **多周期 × 8 维度按天序列 (高频!**运营最爱!)** | **`daily-gsv-multi-period(periods, metrics)`** | periods: list[(start,end)], metrics: list[str], format?, output? | **"小样 GMV/GSV" / "会员 GMV/GSV" / "新客 / 老客" + "按天" + "多周期对比" / "8 维度" / "一日日数据" / "周期对比"** |
| 固定清单单品新老客对比（无锁冲突） | `fixed_product_list_compare_http(start_date, end_date, product_ids?)` | start_date, end_date, product_ids?, auth_token? | "固定清单" / "单品新老客" / "uvicorn 锁冲突" / "HTTP 版" |
| 固定工具命中不到但必须跑数 | `ai_sandbox_execute(sql, sandbox_type, audit_id)` | sql, sandbox_type?, audit_id? | "AI 自行跑数" / "工具命中不到" / "sandbox" / "临时需求但禁临时脚本" |
| 不确定要哪个 | `ask(query)` | query | "不确定" / "查一下" / 模糊词 |

## 1.5.1 关键词同义词库 (Sprint 190 新增, 防 WorkBuddy 误判 "工具缺位")

运营问数常用词汇 → tool 名映射（LLM 看到这些词要立刻想起对应 tool）：

| 运营词 | 对应 tool | 关键提示 |
|---|---|---|
| 小样 / 派样 / GMV/GSV（小样） | `daily-gsv-multi-period` (metrics 必含 `sample_gmv`/`sample_gsv`) | 渠道 `U先派样` + `百补派样` 是硬编码 |
| 会员 / is_member=TRUE / 高价值用户 | `daily-gsv-multi-period` (metrics 必含 `member_gmv`/`member_gsv`) | `o.is_member = TRUE` |
| 新客 / 首次购买 / 新增用户 | `daily-gsv-multi-period` (metrics 必含 `new_users`/`new_gsv`) | cutoff = 查询起始日 - 1 天 |
| 老客 / 复购用户 | `daily-gsv-multi-period` (metrics 必含 `old_users`/`old_gsv`) | 跟新客互斥 |
| 按天 / 一日日 / 日序列 | `daily_gsv` (全店) **OR** `daily-gsv-multi-period` (细粒度) | 看是否要拆 8 维度 |
| 多周期 / 周期对比 / 两个窗口 | **必须 `daily-gsv-multi-period`** | `daily_gsv` 只支持单周期 |
| 8 个维度 / 8 维度 / sample+member+new+old | **必须 `daily-gsv-multi-period`** | 8 metric enum 已硬编码 |
| YOY / 同比 / 增长率 | `yoy_battle` (双窗口) **OR** `two_year_overview` (整年) | 不要用 `daily_gsv` 自身算 YOY |
| 订单号清单 / matched order set / 8000 个 order_id | `two_year_overview + order_ids` | 5000+ 自动走 DuckDB temp table (Sprint 196 R1 1:1) |
| 全店 / 整店 / 不分渠道 | 默认行为, 任何 tool 都支持 | 不要传 `exclude_channels` |
| 不确定 | **`ask(query)`** 关键词路由 | 永远不会错 |

**关键提示** (Sprint 190 真业务触发): 运营高频需求"按天 × 8 维度 × 多周期对比" → **必须先查 `daily-gsv-multi-period`**, 跟 `daily_gsv` (全店) 是两个不同的工具, 不要因为 `daily_gsv` 在速查表第一行就误以为它是唯一日工具。

## 1.5.2 工具缺位自检 (Sprint 190 新增, 防 LLM 假阳性 "工具缺位" 误判)

**WorkBuddy 必读: 报"工具缺位"前先查 4 件事**:

1. **本 SKILL.md §1 14 个 tool 全表** (含 `daily-gsv-multi-period` / `fixed_product_list_compare_http` / `ai_sandbox_execute`) → 14 个足够覆盖 95% 运营需求
2. **关键词同义词库 §1.5.1** (本节) → 找到运营词的对应 tool
3. **问 `ask(query)`** 让 NL 路由帮你选 (零 LLM 成本)
4. **`metrics` 能不能满足?** `daily-gsv-multi-period` 支持 8 维度 (sample/member × GMV/GSV + new/old × users/GSV), 几乎全覆盖

**只有下面 3 种情况才是真 "工具缺位"**:
- 需求要拆到 > 8 维度 (Sprint 190 后端仍 8 metric 硬编码, 没法扩)
- 需求要的不是 SQL aggregation 而是明细行 (这种 tool 都不支持, 走 ETL 路径)
- 需求要的 metric 不在 8 enum 列表 (例如"客单价 AUS" → 走 `daily_gsv` 全店 metric)

**其他 95% 情况都有现成 tool**. 不要再报 "工具缺位" 让用户确认要不要临时脚本 (Sprint 190 拍板: 临时脚本永远不写, 跟 L4.5 永久规则禁止).



## 1.6 锁冲突 graceful fallback (新增, L4.36 配套)

DuckDB read_only Conn 在 uvicorn 持写锁时 (Sprint 53 race flake) 会冲突. 处理:
1. 重试 3 次 (间隔 1s, 2s, 4s exponential backoff)
2. 仍失败 → 调 backend HTTP API `GET /api/v1/audience/summary` 取近似 5 指标 (无小样)
3. 再失败 → 返友好错误 "DuckDB 锁冲突, 请 1 分钟后再试或联系 admin 重启 uvicorn", **绝不建议停 uvicorn**

---

## 2. 每个 tool 详细说明

### 2.1 `daily_gsv(start, end)`

- **用途**: 取每日 GSV / 订单 / 客户 / AUS 序列, 自动算 YOY%
- **参数**:
  - `start` (str, 必填, 格式 `YYYY-MM-DD`): 起始日期
  - `end` (str, 必填, 格式 `YYYY-MM-DD`): 结束日期
- **输出**: JSON list, 每行 `{date, gsv, orders, customers, aus, gsv_yoy_pct, orders_yoy_pct, ...}`
- **复用 backend service**: `backend.services.metrics.daily_gsv.*`
- **错误处理**: `start > end` → MCP error "Invalid date range"; 窗口 > 366 天 → MCP error "Window too large"
- **典型调用**:
  - "最近 7 天 GSV 趋势" → `daily_gsv("2026-06-24", "2026-06-30")`

### 2.2 `yoy_battle(baseline_start, baseline_end, current_start, current_end, metric)`

- **用途**: 双窗口 YOY 对比, 单 metric 或 `all` (5 指标齐出)
- **参数**:
  - `baseline_start/end` (str, 必填): 去年同期窗口
  - `current_start/end` (str, 必填): 当前窗口
  - `metric` (str, 必填, 枚举 `gsv|orders|customers|aov|all`): 对比维度
- **输出**: JSON `{baseline: {gsv, ...}, current: {gsv, ...}, yoy_pct: {gsv, ...}}`
- **复用 backend service**: `backend.services.metrics.yoy_battle.*`
- **错误处理**: metric 不在枚举 → MCP error "Invalid metric"; 双窗口长度不一致 → MCP warn 但继续
- **典型调用**:
  - "2026-06-01 vs 2025-06-01 GSV 同比" → `yoy_battle("2025-06-01", "2025-06-01", "2026-06-01", "2026-06-01", "gsv")`

### 2.3 `channel_slice(date, channel, compare)`

- **用途**: 单日 / 单渠道切片, 可选 YOY / POP 对比
- **参数**:
  - `date` (str, 必填): 查询日期
  - `channel` (str, 必填, 枚举 `all|shelf|daren|live|storefront|...`): 渠道
  - `compare` (str, 可选, 枚举 `yoy|pop|none`, 默认 `none`): 对比模式
- **输出**: JSON `{channel, date, gsv, orders, customers, aus, yoy: {...} | pop: {...}}`
- **复用 backend service**: `backend.services.metrics.channel_slice.*`
- **错误处理**: channel 不在枚举 → MCP error "Unknown channel"; `compare=yoy` 但无去年同期数据 → yoy 字段返 None
- **典型调用**:
  - "2026-06-21 全店各渠道 GSV" → `channel_slice("2026-06-21", "all", "none")`
  - "2026-06-21 货架渠道 vs 去年" → `channel_slice("2026-06-21", "shelf", "yoy")`

### 2.4 `two_year_overview(year, period, start, end, exclude_channels, order_ids)`

- **用途**: 30 指标两年对比 (GSV/订单/客户/AUS/退款率/新老客/会员/占比/溢价), **最高优先级**
- **参数**:
  - `year` (int, 必填, e.g. `2026`): 当前年份
  - `period` (str, 可选, 枚举 `wtd|mtd|ytd|q1|q2|q3|q4`): 时间窗口语义
  - `start` (str, 可填): 自定义窗口起点
  - `end` (str, 可填): 自定义窗口终点
  - `exclude_channels` (list[str], 可选, e.g. `["U先派样", "赠品&0.01"]`): 排除渠道
  - `order_ids` (list[str], 可选): 订单号清单, 仅统计匹配订单; 适合 "30 指标 + matched order set"
- **order_ids 路径**: 5000 条以内走参数化 `IN (?,...)`; 5000+ 自动写 DuckDB temp table + `UNNEST(?)`, 跟 audience summary 1:1
- **优先级**: 用户同时说 "30 指标 / 两年对比 / 订单号清单 / matched order set" 时, 不要走临时 SQL, 直接调本 tool 并传 `order_ids`
- **输出**: JSON dict, 每个指标三列 `{2026_value, 2025_value, yoy_pct}`
- **复用 backend service**: `backend.services.metrics.audience_summary.calculate_audience_summary`
- **错误处理**: `period` 与 `start/end` 冲突 → MCP error "Conflicting period/dates"; 窗口 > 366 天 → MCP error
- **典型调用**:
  - "2026 H1 30 指标两年对比" → `two_year_overview(2026, "ytd", null, null, [])`
  - "2026-06 月新老客 30 指标, 排除派样" → `two_year_overview(2026, null, "2026-06-01", "2026-06-30", ["U先派样"])`
  - "30 指标 + 8000 个 order_id 清单" → `two_year_overview(2026, null, start, end, null, order_ids=[...])`

### 2.5 `new_old_customer(start, end, exclude_channels, dimension)`

- **用途**: 新老客拆分对比, 可按 channel / category 维度展开
- **参数**:
  - `start` (str, 必填): 起始日期
  - `end` (str, 必填): 结束日期
  - `exclude_channels` (list[str], 可选): 排除渠道
  - `dimension` (str, 可选, 枚举 `channel|category`, 默认 `channel`): 拆分维度
- **输出**: JSON dict, 每个维度独立三列块（新客 GSV / 老客 GSV / 新客人数 / 老客人数 / AUS / 占比, 各自带 YOY%）
- **复用 backend service**: `backend.services.metrics.audience_table.get_audience_table`
- **错误处理**: dimension 不在枚举 → MCP error; 子项加和 ≠ 父项误差 > 0.1% → MCP warn "新+老≠全店"
- **典型调用**:
  - "2026 H1 分新老客各渠道 GSV" → `new_old_customer("2026-01-01", "2026-06-30", [], "channel")`
  - "2026 H1 分新老客各品类 GSV" → `new_old_customer("2026-01-01", "2026-06-30", [], "category")`

### 2.6 `rfm_repurchase(start, end, channel)`

- **用途**: R 区间 6 桶复购周期分布, **Sprint 170 口径** (R_INTERVALS = `[0-30, 31-90, 91-180, 181-365, 366-730, 731+]` SSOT)
- **参数**:
  - `start` (str, 必填): 起始日期
  - `end` (str, 必填): 结束日期
  - `channel` (str, 可选, 默认 `all`): 单渠道切片
- **输出**: JSON `{r_buckets: [{range, users, pct, gsv, aus, repurchase_rate}, ...], total, yoy: {...}}`
- **复用 backend service**: `backend.services.rfm.r_flow.get_rfm_r_flow` + `backend.semantic.segments.R_SEGMENT_ORDER`
- **错误处理**: 6 桶边界不在 R_INTERVALS → MCP error (硬截断, 走 SSOT)
- **典型调用**:
  - "2026 H1 R 区间复购周期分布" → `rfm_repurchase("2026-01-01", "2026-06-30", "all")`

### 2.7 `top_n(dimension, start, end, exclude_channels, limit)`

- **用途**: TOP N 品类 / 单品 / SPU 两年对比
- **参数**:
  - `dimension` (str, 必填, 枚举 `spu_category|spu_product_subclass|spu_product_class`): TOP 维度
  - `start` (str, 必填): 起始日期
  - `end` (str, 必填): 结束日期
  - `exclude_channels` (list[str], 可选): 排除渠道
  - `limit` (int, 可选, 默认 `20`): TOP 数量
- **输出**: JSON list, 每行 `{rank, name, gsv_2026, gsv_2025, gsv_yoy_pct, customers_2026, aus_2026, ...}`
- **复用 backend service**: `backend.services.metrics.audience_summary.*` (按 dimension 切)
- **错误处理**: dimension 不在枚举 → MCP error; limit > 100 → MCP warn 但继续
- **典型调用**:
  - "2026 H1 TOP20 品类" → `top_n("spu_category", "2026-01-01", "2026-06-30", [], 20)`

### 2.8 `export_excel(start, end, exclude_channels)`

- **用途**: 整份 11 sheet Excel 报告 (一键给老板), **最高优先级**
- **参数**:
  - `start` (str, 必填): 起始日期
  - `end` (str, 必填): 结束日期
  - `exclude_channels` (list[str], 可选): 排除渠道
- **输出**: JSON `{file_path: str, sheets: [str], size_bytes: int}`
- **复用 backend service**: 组合 `two_year_overview` + `new_old_customer` + `rfm_repurchase` + `top_n` + `channel_slice` (同一份 service 调用结果, 零独立 SQL)
- **Sheet 命名** (11 sheets, 跟用户偏好一致):
  - `00_说明`
  - `01_数据排查报告`
  - `02_新老客30指标`
  - `03_单品概览TOP20`
  - `04_复购周期RFM`
  - `05_回购周期RFM`
  - `06_连带TOP20`
  - `07_品类流转矩阵`
  - `08_R区间回购周期`
  - `09_渠道概览`
  - `10_同品复购与回购店铺`
- **视觉规范** (用户固定偏好):
  - 表头深蓝 `#1F4E79`, 子标题中蓝 `#2E75B6`
  - YOY 正值红 `#D32F2F`, 负值绿 `#2E7D32`, 格式 `+X.XX%` / `-X.XX%`
  - 占比同比 pp 单位, 红绿正负
  - **0 公式**: Python 算好直接写值, 防 Excel 记忆错乱
- **错误处理**: 输出 > 20MB → MCP 返文件 path (不内嵌文本); 路径冲突 → 自动 timestamp suffix
- **典型调用**:
  - "给我一份 2026 H1 完整报告" → `export_excel("2026-01-01", "2026-06-30", [])`

### 2.9 `dq_report(start, end, full)`

- **用途**: 数据排查 15 项校验, 独立校验
- **参数**:
  - `start` (str, 必填): 起始日期
  - `end` (str, 必填): 结束日期
  - `full` (bool, 可选, 默认 `false`): `true` = 15 项全跑, `false` = 轻量 5 项
- **输出**: JSON `{checks: [{name, level: "WARN|ERROR|PASS", message, evidence}], summary: {warn, error}}`
- **15 项校验清单**:
  1. 完整性检查 (缺失率 > 50% → WARN)
  2. YOY 范围合理性 (`|yoy| > 1e6` → ERROR)
  3. 占比类 yoy 单位检查 (必须是 pp)
  4. 子项之和 = 父项检查 (新+老 GSV = 全店, 误差 > 0.1% → WARN)
  5. 关键口径交叉验证 (req1 全店 GSV vs req2 TTL GSV)
  6. 同接口字段单位一致性 (AUS yoy vs GSV yoy 量级)
  7. 2026 vs 2025 真相等性 (yoy=None 时数据应相等)
  8. 渠道覆盖率 (9 个标准 channel 齐全)
  9. 日期连续性 (窗口内无断层)
  10. 会员口径稳定性 (is_member 不为 NULL)
  11. 退款率范围 (0-100%)
  12. AUS 量级合理性 (10-10000 区间)
  13. 复购率范围 (0-100%)
  14. 维度 drilldown 一致性 (channel → category 汇总误差 < 0.5%)
  15. ETL 状态 (`/tmp/.etl_running.flag` 不存在)
- **WARN/ERROR 分级**:
  - `WARN`: 可继续, 记录到 audit
  - `ERROR`: 必须 `--force` 才继续, 否则 MCP error 退出 1
- **复用 backend service**: 跨 `metrics.audience_summary` + `metrics.audience_table` + `rfm.r_flow` 交叉
- **典型调用**:
  - "排查下 2026 H1 数据" → `dq_report("2026-01-01", "2026-06-30", true)`

### 2.10 `ask(query)`

- **用途**: 自然语言路由, **不调 LLM** (关键词正则, 确定性、零成本、可预测)
- **参数**:
  - `query` (str, 必填): 用户自然语言查询, e.g. "最近 7 天各渠道 GSV"
- **输出**: JSON `{route: <tool_name>, args: {<param>: <value>, ...}, fallback: bool}`
- **路由规则** (关键词优先):

| 用户文本关键词 | 路由到 | 提取参数 |
|---|---|---|
| 两年对比 / 30指标 / 老客 / 新客 / 会员 | `two_year_overview` | `year`, `period` |
| 新老客拆分 / 新客老客 | `new_old_customer` | `start`, `end` |
| 渠道 / 货架 / 达播 / 直播 / 全店 | `channel_slice` | `date`, `compare` |
| 复购周期 / R 区间 / RFM | `rfm_repurchase` | `start`, `end` |
| TOP20 / 品类 / 单品 / SPU | `top_n` | `dimension`, `limit` |
| 导出 / Excel / 报告 / 整份 | `export_excel` | `start`, `end` |
| 排查 / 校验 / 数据质量 | `dq_report` | `start`, `end` |
| 日 GSV / 每日 / 趋势 | `daily_gsv` | `start`, `end` |
| 同比 / YOY / 战斗 | `yoy_battle` | `baseline`, `current` |

- **不命中的回退**: `fallback: true`, MCP 返提示 "请说更具体点, 如『两年新老客对比』或『最近 7 天渠道 GSV』", LLM 应当追问用户
- **典型调用**:
  - "最近 7 天各渠道 GSV" → `ask("最近 7 天各渠道 GSV")` → 路由到 `channel_slice` (近期)
  - "分新老客看两年" → `ask("分新老客看两年")` → 路由到 `new_old_customer`

---

## 3. 接入方式（硬约束, Sprint 182 拍板）

### 方案 C: 通过 MCP tools (WorkBuddy 一等公民, 当前)

- **链路**: LLM → `fuqing_adhoc` MCP server (stdio) → `scripts/ad_hoc_query.py CLI` → `scripts/ad_hoc_queries/*` → `backend.services.*` → DuckDB (read_only)
- **优点**: 无 shell 依赖、无 Python 环境依赖、统一 10 个 tool interface、不直连 DuckDB、不写库
- **缺点**: 依赖 WorkBuddy MCP 配置 (`.mcp.json` 已写入, LLM 无感)
- **L4.32 subprocess cwd lock**: MCP server 内部 `cwd=PROJECT_ROOT`, 防 chdir 漂移
- **L4.34 Path resolve**: `Path(__file__).resolve()`, 跨平台路径锁
- **L4.37 MCP stdio 协议 (Sprint 191 修复)**: server.py 用 **MCP stdio newline-delimited JSON**（每行一个 JSON + `\n`），**不是** LSP Content-Length framing。原 LSP 实现导致 WorkBuddy 120s 超时。诊断任何 "MCP -32001 timeout" 必查协议：详见 `~/.workbuddy/skills/mcp-stdio-protocol-debugging/SKILL.md`（含 diagnose_mcp.py 对比测试脚本）

### 方案 A: 直接 import backend services (历史方案, 仅 CLI 内部使用)

- CLI 入口 `scripts/ad_hoc_query.py` 仍然走方案 A, 但 **LLM 不直接走方案 A**, 必须经 MCP 抽象层
- 优点: 口径 100% 复用 backend service
- 缺点: 必须同 Python 环境、同 PYTHONPATH, LLM 调用层不适用

### 方案 B: HTTP API (留 Sprint 183+ 触发)

- 触发条件: 业务组远程取数 / 多机部署 / 权限隔离
- 当前不做: 避免重复造 service 调用层

### 硬约束

1. **不直连 DuckDB**: 永远走 service, 禁 inline SQL (防口径漂移 / DuckDB 锁冲突)
2. **零写库**: 所有子命令只读, 禁 `INSERT/UPDATE/DELETE`; audit 留 `/tmp/fuqing_adhoc_audit.log`
3. **不依赖前端**: 纯 MCP tools, 输出 stdout / 文件 path, 零 Vue 依赖
4. **不引入 LLM**: ask 路由走关键词正则 (确定性、零成本、可预测)
5. **不复制粘贴 SKILL**: 跨端 SSOT 走 symlink (L4.35 永久规则)

---

## 4. 设计原则硬约束（沿用）

1. **复用 backend/services 口径** — 禁 inline SQL、禁直连 DuckDB
2. **复用 backend/contracts/schemas.py Pydantic 类型** — 不裸返回 dict
3. **零写库** — 所有 tool 只读; audit 留 `/tmp/fuqing_adhoc_audit.log`
4. **强制时间窗口 ≤ 366 天** — 防 OOM (Sprint 58 #S58-1 治本同模式)
5. **service 端 SQL aggregation** — `GROUP BY year/channel` 后 fetch, 不取明细
6. **YOY 范围强截断** — `|v| > 1e6` 视为脏数据 → None (Sprint 27/60+ 同模式)
7. **单位语义检查** — 绝对值类 yoy 用 %, 占比/复购率类用 pp (Sprint 169 ratio convention 配套)
8. **路径 sanitize** — `_sanitize_path_component` 防 `../../../tmp/evil` 路径逃逸
9. **同秒覆盖防 race** — `O_EXCL` 独占创建 + 微秒后缀
10. **ETL 跑批中检测** — `/tmp/.etl_running.flag` 存在 → 警告但继续
11. **0 公式 Excel** — Python 算好直接写值, 用户偏好
12. **整份重跑原则** — 全局口径 (exclude_channels 等) 变化 → 整份 11 sheet 重生成, 不局部 patch
13. **L4.5 FilterBuilder exception note**: ad-hoc-query 非 service 层, 走 CLI 复用 service 函数不强制 FilterBuilder (但 service 函数内部仍走 FilterBuilder, L4.5 SSOT 不破坏)

---

## 5. 风险硬约束（沿用 + 新增）

| 风险 | 治本模式 |
|---|---|
| 直连 DuckDB 锁冲突 | 强制走 service (Sprint 24+ P3 race flake 治本) |
| 口径漂移 | 强走 service 函数, 禁 inline SQL |
| 输出格式分裂 | `--format` 强制枚举: `table / csv / xlsx` |
| 路径遍历攻击 | `_sanitize_path_component` 全部替换为 `_` |
| 同秒覆盖 (TOCTOU) | `O_EXCL` 独占创建 + 微秒后缀 |
| ETL 跑批中查询卡顿 | `/tmp/.etl_running.flag` 检测 → 警告 |
| 误覆盖已存在文件 | `export_excel` 路径冲突自动 timestamp suffix |
| 数据逃逸 TAKE_ROOT | `_check_take_root_containment` 自动路径校验 |
| 数值校验失败 | `dq_report` 15 项校验 + WARN/ERROR 分级 |
| 单位混淆 | ratio vs percentage 字段强类型 (Pydantic `RatioField` / `PercentageField` / `PpField`) |
| 跨 sheet 不一致 | `export_excel` 所有 sheet 走同一份 service 调用结果, 零独立 SQL |
| **MCP server 进程死** | WorkBuddy 自动重启 MCP server (stdio 长连接监控) |
| **subprocess cwd 漂移** | L4.32 永久规则 + `cwd=PROJECT_ROOT` |
| **跨平台路径硬编码** | L4.34 永久规则 + `Path(__file__).resolve()` |
| **WorkBuddy 升级清 symlink** | L4.35 永久规则 + SessionStart hook symlink verify |

---

## 6. 输出双层目录规则（沿用 Sprint 61+）

不传 `--output` 时, CSV/XLSX 自动落到 `~/Desktop/fuqin date/取数/<base_year>年/<生成日期>/<base_year>年-<生成日期>-<业务标签>/`:

```
~/Desktop/fuqin date/取数/
└── 2026年/
    └── 2026年6月30日/
        └── 2026年-2026年6月30日-新老客30指标/
            └── 新老客30指标-2026-01-01至2026-06-30.xlsx
```

测试隔离: `FQ_TAKE_ROOT=/tmp/test_take_root python3 scripts/ad_hoc_query.py ...`

业务标签 (跟 tool 一一对应):
- `daily_gsv` → `日序列GSV`
- `yoy_battle` → `YOY对比`
- `channel_slice` → `渠道切片`
- `two_year_overview` → `新老客30指标`
- `new_old_customer` → `新老客拆分`
- `rfm_repurchase` → `R区间复购`
- `top_n` → `TOP20维度`
- `export_excel` → `整份报告`
- `dq_report` → `数据排查`

---

## 7. LLM 调用最佳实践

### 7.1 路由优先级

当用户提出取数需求时, 按以下优先级选择 tool:

1. **结构化查询** (明确知道要什么): 直接调对应 tool, 不走 `ask`
2. **NL 查询** (用户用自然语言描述): 先调 `ask` 路由, 看返回 `route` + `args`, 再调对应 tool
3. **模糊查询** (`ask` 返回 `fallback: true`): 反问用户具体需求, 给 "两年新老客对比" / "最近 7 天渠道 GSV" 这种 example

### 7.2 错误重试策略

- **MCP error "Invalid date range"**: 检查 `start <= end`, 修正后重试
- **MCP error "Window too large"**: 窗口拆成多段 (e.g. 按月切), 多次调用
- **MCP error "Unknown channel"**: 查 channel 枚举 (shelf / daren / live / storefront / all), 修正后重试
- **MCP error "Conflicting period/dates"**: 要么 `period` 要么 `start/end`, 二选一
- **MCP warn (非 error)**: 正常返回结果 + 警告, 不阻断, LLM 可继续下一步

### 7.3 输出展示

- **JSON list/dict**: 直接展示给用户 (格式化 pretty-print)
- **Excel 文件 path**: 提示用户文件位置, 让用户去 Desktop 目录打开
- **audit log**: 不展示给用户, 留 `/tmp/fuqing_adhoc_audit.log` 给排查用

### 7.4 组合调用模式

- **"对比 + 排查"**: 先 `dq_report` 验数据 OK, 再调对应业务 tool
- **"整份报告 + 单维度深挖"**: 先 `export_excel` 出整份, 再按 sheet 调对应单 tool 深挖
- **"两年对比 + 排除渠道"**: `two_year_overview(year, period, null, null, exclude_channels)`, 跟 `export_excel` 的 exclude_channels 保持一致

---

## 8. 跟其他 skill 联动

- `/ship` (gstack) — 上报表 (`export_excel` → `/ship "v0.4.14.150 报告"`)
- `/qa` (gstack) — 端到端验证 (`two_year_overview` 验 200 + `dq_report` 0 ERROR)
- `/investigate` (gstack) — 排查 500 错误: 复现现场用 `dq_report` 验数据状态
- `/regen-types`（项目内）— 改了 `contracts/schemas.py` 后必跑
- `/plan-eng-review`（gstack）— 架构变更（新 query tool / 数据源切换）走架构评审

---

## 9. Sprint 182 留尾（backlog）

- **Sprint 183+**: HTTP API 数据源 (方案 B 切换), 业务组远程取数
- **Sprint 184+**: 业务组只读账号 + 权限隔离
- **Sprint 185+**: 指标维度 registry 暴露 (`backend/semantic/dimensions.py` 给 ask 路由复用)
- **Sprint 186+**: WorkBuddy 真 GUI 端到端测试 (需要 Selenium-style 工具链)
- **Sprint 187+**: cross-platform (Linux/Windows) MCP server 测试
- **Sprint 188+**: LLM 误用 ask router 时 fallback 行为边界 case (5 cases 已测, 边界留 obs)
- **Sprint 189+**: 自动化 `test_e2e_cli.sh` (pytest 覆盖不到的 subprocess 流程)

---

## 10. 跟 Sprint 60+ 沉淀的对齐

| 沉淀 | ad-hoc-query 怎么落 |
|---|---|
| 端到端必须覆盖所有 user-input 路径 | MCP server 14 tool regression (`test_fuqing_adhoc_mcp_server.py`) |
| 复用 backend/services 口径 (方案 A) | Sprint 182 MCP server 强制走 CLI, CLI 内部走 service |
| 复用 L3 Pydantic 类型 (RatioField/PercentageField/PpField) | 所有 yoy 列强类型 |
| ground-truth-lint | L1 SQL f-string lint 干净, 无 inline SQL |
| pytest baseline 持续 | Sprint 182 +12 cases (925 → 937, +1.3%) |
| audit trail 必留 | `/tmp/fuqing_adhoc_audit.log` |
| DuckDB 锁 race flake 治本 | 走 service 函数, 不直连 DuckDB |
| OOM 治本 | 时间窗口 ≤ 366 天 + service 端 aggregation |
| YOY 范围强截断 | `|v| > 1e6 → None` |
| 占位符数强校验 | service 内部已保证 |
| **单位语义** (Sprint 169+) | ratio vs percentage vs ppt 字段强类型 |
| **0 公式 Excel** (用户偏好) | openpyxl 直填值 |
| **L4.32 subprocess cwd lock** (Sprint 181) | MCP server `cwd=PROJECT_ROOT` |
| **L4.34 Path resolve 跨平台** (Sprint 181.1) | `Path(__file__).resolve()` |
| **L4.35 SKILL SSOT symlink** (Sprint 182) | `~/.workbuddy/skills/ad-hoc-query/SKILL.md` → `~/.claude/skills/ad-hoc-query/SKILL.md` 软链 |
