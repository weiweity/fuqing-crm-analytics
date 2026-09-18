# 并行开工夹具

主协调冻结，供 Lane C/D/E/F 在 A/B 落地前写确定性测试。不是已实现 API，也不是第二套产品合同。

| 文件 | 给谁 | 用途 |
|---|---|---|
| `frozen-contract-v0.json` | A 为实现目标；B–F 为消费形状 | 页面包、桥消息、错误码、绑定状态 |
| `d48-scope.fixture.json` | D | 静态/动态/失效/整页/共享 CSS 五个分支 |
| `leave-epoch.fixture.json` | F | 脏稿谓词与迟到响应 |

Lane A 生成正式 OpenAPI/类型后，调用方改引用生成物，并在 LANE 报告写明替换了哪份夹具。破坏性改字段必须 BLOCKED，不要默默改这份 JSON 的语义。
