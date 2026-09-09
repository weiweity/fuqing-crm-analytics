# GSV 数值诊断与看板接线交付

**GSV 的“真实模型调用 → 合成数据计算 → 保存结果 → 认可成板 → 刷新重开”已实测通过。整产品仍 PARTIAL。**

基础 HEAD 为 `8c2e676cf9a9c4baa62aef67aa08f44b12cb0e66`，工作树 `competition-diagnosis-integration`、分支 `codex/competition-diagnosis-integration`；本增量尚未 commit/push。源码哈希与完整检查绑定于[验证记录](evidence/diagnosis-integration-2026-09-10/computed-verification.json)，不能用基础 HEAD 代表未提交代码。

## 实际结果

| 范围 | 本期 GSV | 对比期 GSV | 差额 | 同比 |
|---|---:|---:|---:|---:|
| ALL | 410 | 305 | 105 | 34.43% |
| CH_RETAIL，仅更改销售范围 | 400 | 300 | 100 | 33.33% |

两期均为 8 月全月：本期 2026 年，对比 2025 年，Asia/Shanghai，小样 INCLUDE，历史范围 ALL。数据为服务器显式创建的六条合成订单和一条带日期的退款，未打开或复制归档真实数据。

DSH 原生 DeepSeek-V4-Flash，Standard mode / Read Only，实际执行两条用户问题、五次可见工具调用，其中两次 GSV 计算。模型答案的完整 analysis_id 和 evidence_digest 均与保存快照一致；第二条只改变 sales_scope。原生界面显示输入约 111K、输出约 4.8K token，LLM 33.6 秒；费用未返回，不推算金额。

第二条结果保存为 `analysis_diag_a9148fb8b5fe679d1df7ebbf1e0fee8fb66dcd9cc7b32a9a`；浏览器认可后生成 `board_cec58430029a57ed942835bba3ef84de`，BAR v2。整页刷新、重开后仍为 400/300/100/33.33%，弹层保持打开。旧板 `board_4dcb6d75329580a96315a8882a1819a7` 与行动草稿 `draft_46510707572a435c92b27ed1eef98fe1` v2 仍可读。

原始证据：[模型与来源绑定](evidence/diagnosis-integration-2026-09-10/t13-computed-eval.json)、[可见模型回答](evidence/diagnosis-integration-2026-09-10/t13-computed-browser-text.json)、[刷新后的截图](evidence/diagnosis-integration-2026-09-10/screenshots/t13-computed-board-reopened.png)。临时 4328 的独立 HTTP/浏览器证据在[单独记录](evidence/diagnosis-integration-2026-09-10/computed-browser.json)。

## 实现与验证

- 删除计算模块通过已加载测试模块寻找 JSON 并补写 refunds 的路径；A9 seeder 显式准备带日期的退款，不把未来全额退款变成过去已关闭订单。
- 新增独立 computed result/facts 合同及离线生成物，C0 hash 保持不变。数字由 A2 计算，模型不提供可信 facts；零分母、未覆盖期间、UNKNOWN 各有明确表达。
- 不可变 SQLite 快照按 actor/session/request 绑定；同键重试、不同条件冲突、撤权、损坏和写锁均有回归。认可、添加、复制、撤销、重开核对同一 result/run/analysis/digest，不依赖源库继续存在。
- UI 按结果版本分派，展示实际数字；BAR/LINE/METRIC 使用已保存值。GSV 0.25 仍显示 0.25，raw ratio 0.25 在展示边界为 25.00%。旧元数据结果继续显示缺少数值序列。

完整日常合成后端 **2315 passed / 77 skipped**；B0 全流程 PASS，包含离线合同、固定类型检查、编译组件和干净目录重建。失败尝试保留：新树 Logo 的 LFS 指针、把完整后端测试错误加入最小 B0 环境，以及两条过时的前端测试，均在最终通过前修正；未安装或升级依赖。

单用户读取 90/90 成功，P95：results 12.48 ms、boards 8.36 ms、单板 13.83 ms；采样峰值 RSS 约 83.6 MiB。见[当前合成基线](evidence/diagnosis-integration-2026-09-10/computed-http-baseline.json)。不代表模型延迟、131 GB 归档规模或正式 T16 通过。

## 当前实例与回退

- 4325 DSH：PID 35587，supervisor 35508，仍由 `competition-product-readiness/scripts/dsh-dev/cli.mjs` 管理；runtime 仍是该树 `.context/dsh-dev/runtime-Cn0Ifc`。新插件通过显式 plugin-path 指向诊断工作树；用户 Models 配置未读取或复制。
- 18083 合成 API：PID 35431，执行诊断树的 `scripts/competition-synth-http.py`；状态仍为 readiness 树 `.context/competition-synth`，新增独立 diagnosis 库。停 API 前必须再次核验端口和进程归属。
- 临时 4328/18084 已停止。4327/8000/5173/14327 的原 PID 分别保持 81058/36717/36727/90347。

切换前四个小型 SQLite 已用 backup API 保存，并在独立恢复目录由新应用读取旧板/草稿：[备份与兼容验证](evidence/diagnosis-integration-2026-09-10/candidate-backup-compatibility.json)。新 diagnosis 库有[单独备份恢复验证](evidence/diagnosis-integration-2026-09-10/computed-backup-restore.json)。

回退不能只换旧代码继续写新资产。先保留切换后的状态，再从上述备份恢复到新的私有目录，使用 readiness 的旧插件/旧 API 指向该恢复目录；保留原 Models runtime。备份早于本轮新增的两个结果和新板，故不能覆盖当前状态或声称回退保留这些新增资产。实际整套回退切换尚未执行。

## 仍需完成

- D5 更新：实际 Node transport 取消/超时 → HTTP → SQLite 不发布已修复并验证，见[取消交付](DIAGNOSIS-CANCELLATION-2026-09-10.md)。新增完整后端 2320 passed / 77 skipped、B0 PASS；浏览器停止入口、Git 版本绑定及正式发布检查仍分开记录。
- 完整诊断链、旧 MCP/截断、业务默认值和 UNKNOWN 边界仍沿总账本保留。模型使用了方法资源中的 UNSUPPORTED 旧措辞，而当前计算源目录对未接能力回显 NOT_CONNECTED；未宣称其可执行，但精确状态措辞仍需统一。
- T15 由用户本人按[更新清单](PRODUCT-UAT-2026-09-10.md)验收。正式 T16 的数据范围/阈值待确认。
- 外层浅色与业务区深色的主题不一致、Ant Design 完整落地及其余 T17 视觉/权限路径仍开放。两条 GSV 真模型通过不等于全部 T13 或产品通过。

七阶段继续以[产品验收账本](PRODUCT-READINESS-2026-09-10.md)为准。
