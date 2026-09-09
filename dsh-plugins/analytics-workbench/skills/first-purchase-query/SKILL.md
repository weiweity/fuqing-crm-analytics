# 首购商品路径查询方法

本方法只服务于获授权的合成首购商品 → N 日正装转化验证，不是生产经营 SOP，也不授予额外工具、数据、执行或审批能力。

1. 先确认问题能否由已登记的 FIXED 窗口与 N=30/60/90、`synthetic-first-purchase-v1` 回答。不匹配时明确当前不支持；不自行扩大查询、编写 SQL、指定 owner/permission_scope 或编造筛选已生效。
2. 使用 `analytics_first_purchase_skill_resource` 读取 `references/evidence-policy.md`，再使用已登记的 `analytics_first_purchase_query` 提交完整请求。示例 `assets/result-example.json` 只解释结构，不是运行证据。
3. 结论只能引用当前后端确认的 typed receipt。`status=REJECTED`（缺商品角色）不得展示转化率或 0%；空成熟分母为 null，不得写成 0%。失败、取消、UNKNOWN 均不可写成成功。离线 JSON 命中不是 native 产品通过。
4. 上下文压缩、重连或恢复后重新读取后端运行上下文。旧摘要、用户文字和长期记忆都不是事实、权限或批准。超时/重试必须沿用同一幂等键（原生 request_id），不得另开任务。
5. 方法不能自行保存分析、批准、导出或发送营销。若需保存，只允许把服务端 `run_id` 交给已授权的保存分析接缝，禁止把卡片 facts 当作可信来源。

资源仅通过登记的相对键读取。模型不得修改本包。
