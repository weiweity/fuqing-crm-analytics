# AI 增长董事会：CEO 价值与行业验证底稿

> 受众：伸美集团老板、黑客松评委、产品与工程团队
> 研究日期：2026-09-05
> 范围：品牌自有电商订单、稳定 `user_id`、首付费渠道、生命周期、自由问数、营销审批与增量实验。本文不把公网合成数据当作真实经营业绩。

## 直接结论

这个产品不应该被定义成“又一个 BI 看板”或“聊天查数据库”。这两种能力已经普及，无法单独构成竞争优势。

更准确的定义是：

> **面向品牌 CEO 的人群经营操作系统：把多渠道订单统一成客户资产，自动发现最值得处理的经营命题，用可追溯问数解释原因，在人工审批后生成可执行人群，并通过实验组/对照组验证增量价值。**

当前成品已经完成从证据到行动草稿的最小闭环，属于“有人审批的无人电商雏形”，而不是全自动无人电商。这个边界反而更可信：高风险动作必须由人确认，系统先承担发现、诊断、计算、分群和留痕。

## 为什么稳定 user_id 是真正的底座

订单平台通常能告诉经营者“哪个渠道卖得多”，但 CEO 真正需要知道的是“哪个渠道带来什么质量的客户”。当跨渠道 `user_id` 始终一致时，可以确定性地连接客户的首购、复购、跨渠道迁移和生命周期：

1. 按首笔有效付费订单计算首付费渠道，而不是把每笔订单都归给最后一次流量来源。
2. 对同一客户追踪 30 天二单率、180 天净价值、补货窗口和跨渠道率。
3. 比较“直播是规模入口、货架是质量标杆”这类经营冲突。
4. 将诊断落到具体人群、产品主张和实验动作，而不是停在报表描述。

Twilio 对身份解析的说明区分了确定性与概率性方法，并把 `user_id`、设备 ID、离线交易等视为可连接的一方数据标识；这支持本项目优先使用稳定一方 `user_id`，不做猜测式身份拼接。[Twilio Identity Resolution](https://www.twilio.com/en-us/blog/insights/identity-resolution)

## “自由问数”行业最佳实践

### 已经人尽皆知的部分

- 自然语言转 SQL。
- 用聊天框替代筛选器。
- 自动生成图表和摘要。
- RFM/生命周期分群。

这些功能可以参赛，但不能作为产品唯一创新点。Google、Snowflake、dbt 与开源项目都已经证明了这条路线。

### 应该采用的最佳实践

1. **语义层先于任意 SQL。** Google 的 text-to-SQL 实践明确列出业务语义层、业务示例、数据链接、检索与自一致校验；dbt MetricFlow 也把指标定义集中成可复用逻辑。[Google Cloud text-to-SQL](https://cloud.google.com/blog/products/databases/techniques-for-improving-text-to-sql) · [MetricFlow](https://github.com/dbt-labs/metricflow)
2. **高频问题必须有已验证答案。** Snowflake Verified Query Repository 将问题与已验证 SQL 配对，并用这些样本做回归评估；这与本项目当前三个确定性意图的做法一致。[Snowflake VQR](https://docs.snowflake.com/en/user-guide/views-semantic/verified-query-repository) · [Snowflake Evaluations](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations)
3. **业务定义要版本化、可审查。** WrenAI 的开源实现强调受治理的上下文层和可版本化语义定义，说明“模型会写 SQL”不等于“模型理解企业口径”。[WrenAI GitHub](https://github.com/Canner/WrenAI)
4. **写动作与读动作分离。** 问数可以自动执行受控只读工具；导出、营销、预算与支付应进入审批、幂等、审计和权限门禁。
5. **结论必须带证据、口径和限制。** 每个回答返回意图、证据、指标版本、合成数据来源和能力限制，不能只给自然语言结论。

因此，本项目下一阶段不应直接开放“LLM 任意写 SQL”，而应扩展受控语义工具：渠道质量、生命周期、产品角色、人群机会、实验结果和预算约束。

## 阿里“无人电商”逻辑与本项目的位置

阿里的公开路线已经从“AI 给建议”走向“AI 执行运营任务”：

- 天猫 2026 路线把生意参谋升级为 24/7 AI Agent 团队，连接本地文件与 CRM，覆盖店铺分析、广告、客服与售后等运营链路。[Alibaba Group：Tmall Agentic Capabilities](https://www.alibabagroup.com/en-US/document-1975267612359131136)
- 阿里 FY2025 年报披露，全站推包含自动出价、优化定向和效果看板；阿里妈妈同时覆盖搜索、信息流、展示、直播与第三方联盟等多种流量形态。[Alibaba FY2025 Annual Report](https://www.hkexnews.hk/listedco/listconews/sehk/2025/0626/2025062601064.pdf)
- Accio Work 对外提供 Agent、自动任务、浏览器、连接器和技能，体现“自然语言入口 + 专业 Agent + 外部系统执行”的组合。[Accio Work](https://seller.alibaba.com/pages/accio_work)

这些证据说明“智能分析 + 自动执行”已经是平台级方向。本项目不能声称先发明了无人电商，但可以明确差异：

| 平台型能力 | 品牌自有经营系统的机会 |
|---|---|
| 平台在自身生态内优化流量和投放 | 用品牌自有 `user_id` 统一货架、直播、淘客、小样等渠道 |
| 重点优化单次投放效率 | 重点优化客户生命周期、复购和 180 天净价值 |
| 平台掌握规则与执行入口 | 品牌保留口径、审批、客户关系与 CRM 选择权 |
| 自动化可能放大错误 | 先生成 DRAFT_EXPORT，保留人工审批与 10% holdout |

OpenAI 的 Agentic Commerce Protocol 同样强调用户逐步确认、商家保留客户关系和最小化数据分享，交叉验证了“AI 可执行，但不可绕过责任主体”的设计原则。[OpenAI Agentic Commerce Protocol](https://openai.com/index/buy-it-in-chatgpt/)

## 为什么 90/10 holdout 不是装饰

只看营销后的成交，无法知道客户本来是否就会购买。Google Conversion Lift 的官方定义就是将人群分为处理组和控制组，以两组转化差异衡量因广告造成的增量。[Google Ads Conversion Lift](https://support.google.com/google-ads/answer/12003020?hl=en)

因此当前系统保留对照组是商业价值的一部分：它让 CEO 从“营销做了多少”转向“营销真正多创造了多少”。但 90/10 只是演示参数，真实运行前仍需根据样本量、自然转化率、预期提升和观察周期做统计功效计算。

## 国外黑客松项目给出的启示

Devpost 对常见评审维度的归纳是创意质量、实现质量和潜在影响；具体赛事还会单列 UI/UX、演示和文档。[Devpost Judging Guide](https://help.devpost.com/article/64-judging-public-voting) · [Impact Forge 2026 Criteria](https://impactforge26.devpost.com/)

与本项目最接近的 Devpost 案例“Autonomous Commerce Agents”展示了：受信数据 grounding、可观察 Mission Control、趋势发现到营销动作的端到端瞬间，比堆叠许多页面更容易形成记忆点。[Autonomous Commerce Agents](https://devpost.com/software/athos)

据此，比赛演示应只讲一条链：

```text
CEO 看见唯一经营冲突
  → 追问证据
  → 审批一项动作
  → 生成实验/对照人群
  → 说明未来如何回收真实增量
```

不要在主演示里漫游所有旧看板。旧模块用于证明系统不是 PPT，主链用于证明 AI 改变了经营方式。

## 产品成熟度与边界

| 等级 | 能力 | 当前状态 |
|---|---|---|
| L0 | 静态报表 | 已有旧 CRM 看板 |
| L1 | 自由问数 | 已有 3 类受控问题 |
| L2 | 自动诊断 | 已生成唯一 CEO Mission |
| L3 | 生成行动草稿，人工审批 | **当前已闭环** |
| L4 | 接 CRM/短信并自动执行，保留规则门禁 | 待做 |
| L5 | 根据增量实验自动调预算与策略 | 远期愿景 |

对老板的准确表达是：“我们已经到了 L3，是无人电商经营闭环的雏形；不是宣布系统已经可以无人值守花钱和触达客户。”

## 建议的源头架构

```text
多渠道成交明细 + 稳定 user_id
            ↓
客户身份与首付费渠道层
            ↓
生命周期 / 渠道质量 / 产品角色语义层
            ↓
已验证问题与诊断工具
            ↓
CEO Mission 生成器
            ↓
审批与策略约束
            ↓
DRAFT_EXPORT / CRM 适配器 / 短信适配器
            ↓
实验组 vs holdout 效果回收
            └──────────→ 下一轮 Mission
```

这不是在旧看板上补一个聊天框，而是把“客户资产语义层 → 决策 → 执行 → 增量测量”设为新的产品主干。

## 关键限制

- 当前 196 人、¥701、+5.7 等数值全部来自合成数据，只能证明链路，不代表真实收益。
- 当前自由问数是确定性工具路由，不是开放域问数；这是有意的安全边界。
- 首付费渠道需要在生产数据中固定退款、取消、同秒订单和历史回补规则。
- 导出目前只有 `synthetic_user_id`、Mission ID 和实验分组；真实 CRM 联系字段只能在私有环境内映射。
- 真正自动营销前必须补充权限、频控、退订、审计、失败补偿和预算上限。

## 停止研究的原因

主要结论已由阿里官方披露、OpenAI 官方协议、Google/Snowflake 官方技术文档、开源 GitHub 项目和 Devpost 项目交叉支持；继续收集更多同类案例不会改变“语义治理 + 人工门禁 + 增量实验 + 单链演示”的决策。
