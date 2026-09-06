# 架构图留存

2026-09-05：增长分析工作台目标架构，**不是部署现状或验收通过证明**。业务边界与技术状态以[工程基线](../docs/hackathon/ENGINEERING-BASELINE-2026-09-05.md)为准，运行证据见[B0 报告](../docs/hackathon/B0-DSH-VALIDATION-2026-09-05.md)。图中实线表示目标调用关系，不表示已实现；虚线表示设计参考或待适配跳转。孤立的真实数据库明确排除于演示之外。

收口说明：当前图表示本地 B0 profile。新增 ETL 分层、版本发布与多人状态/权限方案的补图任务已列入[总待办 A3](../docs/hackathon/PLAN-CLOSEOUT-2026-09-05.md)；本轮没有修改图源或产物，不把现图当作多人/数仓改型的完整拓扑。

- [Mermaid 源文件](./analytics-target-architecture.mmd)：架构维护的单一主源。
- [Excalidraw 可编辑稿](./analytics-target-architecture.excalidraw)：在 excalidraw.com 选择 File → Open 打开；含可编辑节点和连线。
- [SVG 矢量图](./analytics-target-architecture.svg) / [PNG 预览](./analytics-target-architecture.png)：用于文档与评审。

通过 gstack diagram 离线渲染，不依赖 CDN。修改 Mermaid 后同步重新生成其他三个文件。若手改 Excalidraw，先把结构变化同步回 Mermaid，再重新生成，避免两份架构事实来源。需提交时四个文件作为同一个审阅单元；本轮未 commit/push。
