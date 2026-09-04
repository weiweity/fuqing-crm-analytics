# Mission API

Base URL: `/api/v1/missions`

所有接口继承现有 Bearer 认证。每个业务响应都带 `data_provenance`，用于标识合成数据版本、固定观察日、内容哈希和指标版本。OpenAPI 在启动后可通过 `/docs` 查看。

## 1. 今日 Mission

```http
GET /api/v1/missions/today
Authorization: Bearer <token>
```

返回 CEO 首屏的唯一 Mission，包含渠道规模与质量冲突、目标人群、激活商品、假设收益、证据及状态版本。初始状态为 `AWAITING_APPROVAL`，版本为 `1`。

## 2. 受控自由问数

```http
POST /api/v1/missions/diagnose
Authorization: Bearer <token>
Content-Type: application/json

{"question":"哪个渠道粘性最强？"}
```

当前只支持三类受控意图：

| intent | 来源 |
|---|---|
| `CHANNEL_QUALITY` | `sem_channel_customer_quality` |
| `LIFECYCLE_DISTRIBUTION` | `sem_customer_lifecycle_snapshot` |
| `PRODUCT_ROLE` | 合成订单的确定性排名 |

响应中 `answer_mode` 固定为 `DETERMINISTIC_TOOL`。当前不存在任意 SQL 入口。

## 3. 审批

```http
POST /api/v1/missions/{mission_id}/approve
Authorization: Bearer <token>
If-Match: 1
Idempotency-Key: approve-<client-stable-key>
Content-Type: application/json

{"decision":"APPROVE","note":"同意生成合成数据草稿名单"}
```

- `If-Match` 必须等于当前 Mission 版本，否则 `409`。
- `Idempotency-Key` 相同且 body 相同时返回首次结果；同 key 换 body 时 `409`。
- 审批人从已认证会话获取，客户端不能在 body 伪造。
- 成功后状态为 `APPROVED`，版本加一。

## 4. 生成草稿人群

```http
POST /api/v1/missions/{mission_id}/audience-export
Authorization: Bearer <token>
If-Match: 2
Idempotency-Key: export-<client-stable-key>
```

仅 `APPROVED` Mission 可执行。人群使用 `synthetic_user_id` 的 SHA-256 稳定分桶，约 90% 进入 `EXPERIMENT`，约 10% 进入 `HOLDOUT`。成功后：

- Mission 状态进入 `WAITING_MEASUREMENT`。
- 导出物状态为 `DRAFT_EXPORT_READY`。
- CSV 仅有 `synthetic_user_id,mission_id,experiment_arm`三列，权限 `0600`。
- 返回行数、实验/对照数、文件 SHA-256 和受保护的下载路径。
- 刷新页面后，`GET /today` 的 `latest_export` 会恢复最近一次草稿的下载入口。

## 5. 下载

```http
GET /api/v1/missions/{mission_id}/audience-exports/{export_id}/download
Authorization: Bearer <token>
```

只能下载已在独立 SQLite 控制库登记的文件。浏览器端通过带 Bearer 的 API 请求获取 Blob，不把 token 放进 URL。

## 6. 本地演示重置

```http
POST /api/v1/missions/{mission_id}/demo-reset
Authorization: Bearer <admin-token>
If-Match: 3
Idempotency-Key: reset-<client-stable-key>
```

- 默认关闭；只有 `FQ_MISSION_DEMO_RESET_ENABLED=1` 且当前账号属于 `FQ_CRM_ADMINS` 时可用。
- 重置后回到 `AWAITING_APPROVAL`，清除审批与最近导出状态，版本加一。
- 旧合成 CSV 移入导出目录内的私有 `.reset-archive/`，不做不可恢复删除。
- 不修改合成分析 DuckDB，更不会读取或写入真实 CRM DuckDB。
- 公网部署保持该开关为 `0`。

## 状态流

```text
DISCOVERED → EVIDENCE_READY → AWAITING_APPROVAL
                                      ↓ approve
                                  APPROVED
                                      ↓ audience-export
                             WAITING_MEASUREMENT
```

`DRAFT_EXPORT_READY` 是导出物状态，不是 Mission 状态。

## 本地验证（不启动服务）

```bash
PYTHONPATH=. python3.14 -m pytest \
  backend/tests/test_missions_api.py \
  backend/tests/test_hackathon_synthetic_generator.py -q

cd frontend-vue3
npm run test:unit -- src/views/GrowthBoardView.test.ts src/router/index.test.ts
npm run build
```
