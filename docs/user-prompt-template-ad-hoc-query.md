# 芙清 CRM 运营问数话术模板 (WorkBuddy 专用)

## 1. 必用 daily-gsv-multi-period tool 强提示

> Sprint 193 拍板: 提到「小样 / 派样 / 会员 / 新客 / 老客 + 按天 + 多周期 / 2 周期」时, 必用 daily-gsv-multi-period tool. WorkBuddy 不要走 `daily_gsv` (全店) 或 `new_old_customer` (汇总) 凑数, 不要报"工具缺位", 不要写临时脚本.

## 2. 高频 5 个 prompt 模板 (复制即用)

### 模板 1: 多年同时间段对比 (派样 / 会员 / 新老客按天)

> 帮我跑: 2026-05-06 至 2026-06-21 跟 2025-05-06 至 2025-06-21 两个周期, 按天输出小样 GMV/GSV、会员 GMV/GSV、新客人数/GSV、老客人数/GSV 8 个指标. 必用 daily-gsv-multi-period tool.

### 模板 2: 单周期小样 8 维度按天

> 帮我跑: 2026-06-01 至 2026-06-30, 按天输出 8 个维度 (小样 / 会员 / 新老客 x GMV/GSV/人数). 必用 daily-gsv-multi-period tool.

### 模板 3: 单维度多周期 (只 GMV)

> 帮我跑: 2026-05-06 至 2026-06-21 跟 2025-05-06 至 2025-06-21 两个周期, 按天输出小样 GMV 跟会员 GMV 两个指标. 必用 daily-gsv-multi-period tool.

### 模板 4: 大促 YOY 战斗

> 帮我跑: 2026-06-01 至 2026-06-18 跟 2025-06-01 至 2025-06-18 两个周期, 按天输出全店 GSV 同比. 这个只要全店单维度, 可用 `daily_gsv` 或 `yoy_battle`.

### 模板 5: 不确定要哪个 tool

> 帮我用 `ask` 路由查一下: "小样 + 会员 + 按天 + 多周期对比", 看返回什么 tool + args; 如果返回 daily-gsv-multi-period 就直接跑.

## 3. 关键词必查表

| 运营词 | 必用 tool |
|---|---|
| 小样 / 派样 + 按天 + 多周期 | `daily-gsv-multi-period` |
| 会员 + 按天 + 多周期 | `daily-gsv-multi-period` |
| 新老客 + 按天 + 多周期 | `daily-gsv-multi-period` |
| 8 维度 / 8 指标 | `daily-gsv-multi-period` |
| 周期对比 / 2 周期 / 两个窗口 | `daily-gsv-multi-period` |
| 全店 GSV 趋势 (单周期) | `daily_gsv` |
| 两年 30 指标对比 | `two_year_overview` |
| 不确定 | `ask` |

## 4. 报"工具缺位"自检 4 步

1. 查本模板第 3 节关键词必查表.
2. 查 `~/.claude/skills/ad-hoc-query/SKILL.md` 第 1.5.1 节关键词同义词库.
3. 调 `ask(query)` 关键词路由.
4. 只有 3 种情况才是真工具缺位: 超过 8 维度、需要明细行、指标不在 8 个 enum 内. 其他大多数运营问数都已有现成 tool.
