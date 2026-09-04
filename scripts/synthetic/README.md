# 黑客松合成数据生成器

这个目录是公网演示数据的唯一生成入口。生成器只从固定 seed 和代码中的合成经营情景构建数据，不读取私有 CRM、不接收真实 `user_id`、不生成真人映射表。

## 生成

```bash
python3.14 scripts/synthetic/generate_hackathon_dataset.py
```

默认生成：

- `data/synthetic/syn-commerce-1.0.0.duckdb`
- `data/synthetic/syn-commerce-1.0.0.manifest.json`
- 8,000 个合成客户、28,000 笔合成订单、8 个虚拟商品、24 个月的渠道成本假设

`data/` 被 Git 忽略，生成物不直接进仓。已有输出时默认失败；只有明确需要重建才使用 `--force`。

## 硬契约

- 同一个合成客户在货架、直播、淘客和小样关系事件中始终使用同一 `synthetic_user_id`。
- `synthetic_user_id` 只由数据集版本、seed 命名空间和生成顺序产生，不是真实 ID 的哈希或编码；同 seed 保持稳定，不同 seed 不会误关联。
- 关系渠道和首次付费渠道分开；小样可以建立关系，不伪装成付费获客。
- 每张表必须带 `synthetic=true`，所有 ID 必须符合 `SYN-*` 格式。
- 启用列名黑名单、手机号/邮箱模式扫描、外键完整性和跨渠道关联检查。
- 相同 seed 产生相同的 `dataset_content_sha256`；分析观察日固定，不随运行当天漂移。
- 数据中的金额、成本、退款和渠道表现都是合成假设，不能表述为真实业务成果。

## 确定性语义视图

生成器在合成库中同时建立三个只读视图，作为 Mission API 和 AI 问数的唯一首批数值来源：

- `sem_customer_origin`：分开首次可观察关系和首次有效付费。
- `sem_customer_lifecycle_snapshot`：在固定观察日计算二单、跨渠道、30/90/180 天价值、成熟度和生命周期。
- `sem_channel_customer_quality`：按首付费渠道比较队列规模、30 天二单率、二单时间、跨渠道率和 180 天价值。

视图只给出观察证据，不把渠道相关性写成营销因果。

## 验证

```bash
PYTHONPATH=. python3.14 -m pytest \
  backend/tests/test_hackathon_synthetic_generator.py -q
```

单测覆盖可复现性、稳定用户 ID、跨渠道关联、PII 拦截和禁止静默覆盖。

## CEO 演示情景

默认 seed 刻意制造一个需要经营判断的冲突，而不是让所有指标指向同一答案：

- 直播的首付费客户数最大，代表获客规模。
- 货架的 30 天二单率和 180 天人均净价值更高，代表客户资产质量。
- Mission 不因此直接扩大直播投放，而是先针对直播待补货人群做 90/10 二单激活实验。

这是合成业务故事，不是对真实公司经营结果的描述。
