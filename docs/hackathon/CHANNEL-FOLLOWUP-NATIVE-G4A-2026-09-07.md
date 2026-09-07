# 渠道后续购买 native 接通（G4a）

日期：2026-09-07。任务分支 `codex/channel-followup-native-runtime`。基线 G3b2 `305f0ede2b6df7e1dc426a49ab86da881c3bae5e`。状态：**ASGI/ADAPTER/LOADER**。浏览器 / Gateway / 卡片 **NOT RUN**。G4 未完成。

本文件记录 G4a：在现有 DSH Agent Loop 上接通 `channel_followup` 查询族。证明 FastAPI ASGI、真实 worker 与真实 Cordis loader 的 Host 工具输出和方法上下文正确。不启动 UI/长期服务，不调用产品模型或真实 DB。

## 1. 范围

| 层 | 本单元 |
|---|---|
| query-run 合同 | 新增 `AnalyticsQueryNativeReceipt`（run/attempt/step + 完整 G2 结果）；paths 仍为空；旧 B0/G2 bundle 未改 |
| HTTP | `backend/analytics_query_app.py`：`GET /api/v1/analytics-query/conversations/{id}`、`GET .../runs/{id}`、`POST .../cancel`；auth/no-store/有界错误；无任意 SQL/会话 CRUD |
| runtime | `family=channel_followup` 时恰好 2 个登记 session → 2 conversation，共享 1 RunStore / WorkerManager / dispatcher / 4315 |
| native helper | 固定 `POST /internal/native/channel-followup`：lookup → reserve → worker 或复用 → typed receipt |
| 幂等 | 有 native 时 digest 含冻结 NativePrompt；无 native 的原 query-store hash 不变 |
| Host | `analytics_channel_followup_query`；`B0_RUNTIME_FAMILY=channel_followup` 时登记；decoder 拒未知 schema/缺字段/非法数值/错误 null 形状 |
| 方法包 | `channel-followup-query` + `query-skill-package.lock.json`；默认 B0 包 digest 不变 |

未做：gateway 双 session 出站过滤、query 卡片/run-view、controlled runner 四问、浏览器验收。

## 2. 验证（本机，未跑完整 pre-push）

| 项 | 结果 |
|---|---|
| query-run codegen | PASS `sha256=390430dfc4b244df0c8b929719f8a1cc30e0c1a99c36793d63725f7f71e13f5a`；paths 空 |
| B0/G2 合同 | PASS，保护清单 17 文件 hash 未变 |
| Python query 新测 + jobs/run 合同 | 42 passed |
| 受影响旧 runtime/worker/jobs/context/access | 161 passed |
| 真实 worker N30/N60 | PASS，不同 run/step，typed receipt 与金标准一致 |
| Cordis loader B0+query | 16 built tests PASS |
| clean 四产物 | index/tool/skills/client 逐字节一致 |
| 浏览器 / Gateway / 卡片 | **NOT RUN** |

## 3. 新增具名模块

`backend/analytics_query_app.py`；`src/query-tool.ts`、`query-model.mjs`、`runtime-family.mjs`；`skills/channel-followup-query/`；`query-skill-package.lock.json`。

环境：query-mode 使用 `B0_RUNTIME_FAMILY=channel_followup` 与恰好两个 `B0_SESSION_IDS`。默认仍为 B0 单会话。
