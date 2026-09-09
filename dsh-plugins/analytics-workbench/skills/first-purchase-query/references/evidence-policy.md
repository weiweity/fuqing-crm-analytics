# 证据政策

- 可信条件与结果只来自后端冻结绑定。模型或浏览器不能指定 owner、permission_scope 或提交 facts。
- `MISSING_PRODUCT_ROLE` 是合同拒绝：facts 必须为 null，禁止渲染转化率。
- `EMPTY_MATURE_COHORT` 的比例为 null，显示为破折号，禁止显示 0%。
- 重试与超时使用同一原生 request_id 作为幂等键。
- 保存分析只传递 `created_from_run_id`。
