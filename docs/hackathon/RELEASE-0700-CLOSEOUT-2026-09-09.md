# v0.7.0.0 发布收尾（2026-09-09）

PR [#108](https://github.com/weiweity/fuqing-crm-analytics/pull/108) 已合并，main 为 `d95e504`，版本 `0.7.0.0`。PR CI `34310344976` 必需检查通过。合并后本机 DSH 使用合成数据和本地 stub，浏览器已验证首购查询→保存分析→加入驾驶舱。真实模型、完整业务 UAT 和公网未验。

## 分支与工作树

未删除分支、工作树或远端引用。逐文件 SHA256 比较只证明内容相同与否，不把不同文件自动判作缺失功能；许多差异是旧实现被集成修复取代。所有候选继续保留。

| 候选分支 | 改动及未跟踪文件 | 与 main 相同 | 不同或待核对 |
|---|---:|---:|---:|
| codex/first-purchase-assets-round2 | 60 | 44 | 16 |
| grok/first-purchase-assets-round2 | 40 | 24 | 16 |
| codex/w4-shared-customer-features | 6 | 4 | 2 |
| codex/first-purchase-native-r2 | 60 | 34 | 26 |
| codex/first-purchase-native-round2 | 31 | 11 | 20 |
| codex/first-purchase-runtime | 5 | 1 | 4 |

远端实际保留 main 和 codex/parallel-query-w4-integration。本地三个失效引用待另行授权 prune：origin/docs/hackathon-closeout-225dc68、origin/docs/hackathon-closeout-a71a0cf、origin/docs/hackathon-readme-closeout。

## 演示与本地文档

旧 8000/5173 保留。当前 4318 演示保持运行，仍使用集成 worktree 的构建。独立构建已准备在主工作区 `.context/dsh-b0/releases/0.7.0.0/analytics-workbench`：130 个文件哈希一致，20 个依赖链接均解析到工作树外已有固定依赖；未复制 node_modules 实体、数据库或运行状态。独立构建尚未启动验证，因此当前集成 worktree 仍不可删除。

下一次演示切换：先结束本次 DSH 查看并只停止本次拥有的 DSH 实例，再从 main 运行原 serve 命令，将 `--plugin` 改为上述独立构建绝对路径，仍带 `--native-first-purchase`；随后 bootstrap、prepare-ui、gateway 并复验查询与保存。旧 CRM 不参与。切换前需重新核对 PID 和端口，不能复用历史 PID 执行停止。

主工作区四个未跟踪文件保持原样、不纳入交付：ARCHIVE.md 是本地归档提示；三个 GOAL-PARALLEL 文档是已结束并行轮次的计划、启动词和模板，内含旧基线/旧授权，不作为当前执行入口。原样备份及候选哈希清单位于主工作区 `.context/ship/closeout-0700/`。

## 后续缺口

完整 W4 消费接线、W5 发布恢复、候选人群、连续追问与同条件 BI、多人/容量/真实模型/业务 UAT、公网仍开放。本次仅更新收尾文档，不重开业务开发、不自动追加提交或发布。
