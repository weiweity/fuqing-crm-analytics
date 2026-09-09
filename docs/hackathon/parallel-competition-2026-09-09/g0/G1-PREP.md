# G1 合同集成准备（总控，待第一批交付）

本文件只记录总控后续接线点，不授权子轨改这些文件。

## 总控独占入口

| 路径 | 用途 |
|---|---|
| `backend/main.py` | 旧 CRM FastAPI 总入口、健康检查、路由挂载 |
| `backend/analytics_app.py` | B0 分析 run |
| `backend/analytics_analysis_app.py` | 保存分析 |
| `backend/analytics_cockpit_app.py` | 驾驶舱 overlay |
| `backend/analytics_query_app.py` | native query |
| `backend/analytics_first_purchase_*.py` | 首购分析/驾驶舱 |
| `dsh-plugins/analytics-workbench/src/index.ts` | 插件注册 |
| `dsh-plugins/analytics-workbench/src/client/index.tsx` | 客户端挂载；A4 壳由此接入 |
| `dsh-plugins/analytics-workbench/src/client/styles.ts` | A4 可改；index 仍由总控装配 |
| `scripts/dsh-dev/` | A4 可改诊断/启动；不要动用户 4327 实例 |

## G1 验收清单（A1 回来后）

- [ ] C0-MANIFEST.json 存在且含文件清单/hash/版本/支持矩阵
- [ ] contract_hash 可复算
- [ ] Condition/ResultRef/BoardSpec/Audience/Error 有真实代码名映射
- [ ] 每族成功/空/参数错误/权限失败 fixture；编辑 409/部分成功
- [ ] 生成类型 Python/TS 同源；离线生成器可重复
- [ ] UNKNOWN 口径未伪装成规则
- [ ] 默认值待确认标记存在
- [ ] A2 口径缺口 CR 与 A1 字段对齐或记入变更队列
- [ ] 未改 main.py / index.tsx / 依赖锁

## 第二批门槛

仅当 G1 通过（或总控接受 PARTIAL 且字段已足够 A2/A3/A5/A8 编码）才建 A3/A5/A8 工作树并派发；同时把 A2 从只读核验切到实现。A6/A7 等槽位（≤4 并发）。
