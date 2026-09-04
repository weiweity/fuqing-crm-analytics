# AI 增长董事会

本目录记录黑客松公网演示主链，它不替代原有 CRM 分析文档。

## 演示主链

```text
Mission GET /today
  → CEO 增长董事会首屏
  → 受控自由问数
  → CEO 审批
  → DRAFT_EXPORT_READY
  → WAITING_MEASUREMENT
```

首屏只给出一个需要拍板的经营 Mission：直播带来最多首付费用户，但货架用户的二单率和 180 天价值更高。因此先对“直播首购·待补货”人群发起带对照组的二单激活，而不是盲目加投。

## 评委演示

1. 使用部署环境提供的公网演示账号登录，进入 `/growth-board`。
2. 先讲“直播规模第一、货架质量第一”的经营冲突，再点三个建议问题之一验证证据链。
3. 点击“审批并生成 DRAFT_EXPORT”，明确系统只生成 90/10 合成人群草稿，不自动发送短信。
4. 下载 CSV，展示同一 `synthetic_user_id` 可跨渠道关联；刷新页面后下载入口仍会保留。

演示前需按 [`scripts/synthetic/README.md`](../../scripts/synthetic/README.md) 生成数据，并在部署环境显式配置 `.env.example` 中的四个 `FQ_MISSION_*` 变量。

## 边界

- 公网演示仅使用 `data_profile=synthetic` 且 `contains_real_data=false` 的数据集。
- `FQ_MISSION_DEMO_ENABLED` 默认关闭；Mission 不会回退到真实 `DUCKDB_PATH`。
- 问数只调用已测试的语义视图，不执行模型生成的任意 SQL。
- 未审批不生成名单；草稿名单只包含合成用户 ID、Mission ID 和实验分组。
- `DRAFT_EXPORT_READY` 不等于短信已发送，也不等于已对接 CRM。

接口、幂等与状态转换见 [MISSION-API.md](./MISSION-API.md)，合成数据生成见 [`scripts/synthetic/README.md`](../../scripts/synthetic/README.md)。
