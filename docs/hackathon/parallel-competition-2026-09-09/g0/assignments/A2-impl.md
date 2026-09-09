# A2 第二批：计算实现

C0 已冻结。contract_hash=`97ee36833200b3a1626a4fa88e6b3bc9591bfb5f6bebc5e666aeabdcce13815a`。
cwd 仍是 `/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/.worktrees/competition-a2`。

现在可以改：`backend/services/metrics/`（含 audience_summary 及相关人群计算）、`backend/services/rfm/`、`backend/semantic/`（若属口径）、`backend/services/analytics/customer_features/`（仅必要适配）、`backend/tests/test_competition_metrics*.py`。

禁止改 contracts/生成类型（CR 交 A1）、路由/MCP（交 A3）、真实 ETL/DuckDB、UI。

按 C0 实现：cutoff=current.start-1、闰日 clamp、空月 EMPTY、显式 GSV、新老按 start 前历史、F 订单粒度、R/as_of 不偷看未来、销售/历史 scope 分离、sample_mode 三路径、会员 UNKNOWN。派样渠道不得猜全集。HTTP 忽略筛选的问题记给 A3，计算层拒绝「收了却忽略」。

对接本工作树已覆盖的 C0 文件与第一批金标准。相关单测用既有 bounded runner；禁止全套 backend/B0。不要 commit。
