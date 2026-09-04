# AI 调用 Mission API 指南

本文面向后续 AI Agent、MCP 工具包装和自动化编排。机器可读契约以运行时 `/openapi.json` 为准，可视化接口文档位于 `/docs`。

## 安全边界

- Agent 只能调用 `/api/v1/missions` 下的受控业务接口。
- 不向模型开放 DuckDB 文件路径、数据库凭据或任意 SQL 执行器。
- 所有业务响应必须包含 `data_provenance`；`contains_real_data` 必须为 `false`。
- `approve`、`audience-export` 和本地 `demo-reset` 必须携带当前版本与稳定幂等键。
- `demo-reset` 只允许管理员且由独立环境开关启用；公网保持关闭。
- `DRAFT_EXPORT_READY` 只代表草稿可下载，不代表已发送短信或写入 CRM。

## OpenAPI operationId

| operationId | 方法与路径 | 是否写控制状态 |
|---|---|---|
| `mission_get_today` | `GET /api/v1/missions/today` | 否 |
| `mission_get` | `GET /api/v1/missions/{mission_id}` | 否 |
| `mission_diagnose` | `POST /api/v1/missions/diagnose` | 否 |
| `mission_approve` | `POST /api/v1/missions/{mission_id}/approve` | 是 |
| `mission_create_draft_export` | `POST /api/v1/missions/{mission_id}/audience-export` | 是 |
| `mission_download_draft_export` | `GET .../audience-exports/{export_id}/download` | 否 |
| `mission_reset_demo` | `POST /api/v1/missions/{mission_id}/demo-reset` | 是，仅本地 |

## Agent 推荐调用顺序

```text
mission_get_today
  ↓
根据用户问题调用 mission_diagnose（可重复）
  ↓
向人类展示 Mission、证据、假设与限制
  ↓ 明确确认
mission_approve (If-Match + Idempotency-Key)
  ↓
mission_create_draft_export (新版本 + 新幂等键)
  ↓
返回草稿元数据；只有用户明确要求时才下载
```

禁止 Agent 在一次隐藏操作中连点审批和导出。界面可以把两步包装成一个按钮，但审计记录中必须保留两个状态转换。

## 问数意图

| intent | 典型问题 | 受控数据来源 |
|---|---|---|
| `CHANNEL_QUALITY` | 哪个渠道粘性最强？ | `sem_channel_customer_quality` |
| `LIFECYCLE_DISTRIBUTION` | 有多少客户到了补货窗口？ | `sem_customer_lifecycle_snapshot` |
| `PRODUCT_ROLE` | 哪个产品更适合做老客？ | 合成订单的确定性首单/复购排名 |

遇到范围外问题时，Agent 应解释当前只支持这三类意图，并建议改写问题；不得臆造 SQL 或经营结论。

## 幂等与并发

- `If-Match`：使用刚读取到的 Mission 整数 `version`。
- `Idempotency-Key`：同一用户操作重试必须复用；新操作必须新建。
- `409`：先重新读取 Mission，再决定是否需要用户确认；不要自动无限重试。
- `428`：调用方漏传必需请求头。
- `403`：当前账号无管理员权限。
- `404`：Mission 或本地演示能力未启用；不要把它解释成空数据。

推荐键格式：

```text
<operation>-<mission_id>-<client_uuid>
```

## 给 AI Agent 的系统约束模板

```text
你是品牌经营分析 Agent。只能调用 operationId 以 mission_ 开头的工具。
所有数值必须引用工具响应；不得把 synthetic 数据描述为真实公司业绩。
先读 Mission，再回答问题。读取与诊断可以直接执行。
审批、导出、下载和营销属于动作：必须先向用户展示影响并取得明确确认。
遇到 409 时重新读取状态；不得绕过 If-Match、幂等键、权限或 holdout。
不得生成或执行任意 SQL，不得请求真实用户联系方式。
```

## 最小调用示例

```bash
curl -sS http://127.0.0.1:8000/api/v1/missions/today \
  -H "Authorization: Bearer <token>"

curl -sS http://127.0.0.1:8000/api/v1/missions/diagnose \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question":"哪个渠道粘性最强？"}'
```

带状态变更的完整 HTTP 示例见 [MISSION-API.md](./MISSION-API.md)。

## 后续扩展契约

接 CRM/短信前应新增独立操作，而不是扩大 `audience-export` 的副作用：

1. `campaign_plan_create`：生成渠道、商品、频控、模板和预算草稿。
2. `campaign_plan_approve`：由具备权限的人审批。
3. `crm_audience_push`：把私有环境中的客户标识映射并推送到指定 CRM。
4. `campaign_measure`：回收实验组与 holdout 的二单、毛利和退订指标。

每个写操作都必须有 schema、权限、幂等、审计、失败补偿和 dry-run。
