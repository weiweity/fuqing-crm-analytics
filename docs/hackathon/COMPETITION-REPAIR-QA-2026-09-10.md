# Competition 修复 Git 收口与独立 QA（2026-09-10）

本次修复范围的合成浏览器回归通过，生产代码为 `1550f43cbb8192c8b6df59eaee20ae039e87dda6`。[PR #114](https://github.com/weiweity/fuqing-crm-analytics/pull/114) 已合并为 `788b5b108fed22526805248a86f310ef7602cc6e`；最终 PR 提交 `3862e77` 与合并提交的文件树一致。完整产品仍为 PARTIAL，后续工作统一记入[七阶段验收账本](PRODUCT-READINESS-2026-09-10.md)。

## 版本和环境

| 项目 | 值 |
|---|---|
| 工作树 / 分支 | `competition-repair-ship` / `codex/competition-review-fixes` |
| Git 基线 | `38242b4`（已合并 PR #112） |
| 固定 DSH | `d347e703908d0406b7a7ef80e3a0e594d86b2215` |
| 浏览器 | 独立 GStack Chromium，1440 × 1000；实际点击编译后的 React UI |
| 本轨端口 | DSH `127.0.0.1:4325`，合成 FastAPI `127.0.0.1:18083` |
| 数据 | 私有新建状态目录、两份有限合成结果；无真实数据库、API key 或付费模型 |
| 证据 | [文件及 SHA-256 清单](evidence/competition-repair-2026-09-10/manifest.json)；4 张截图均实际读取核验 |

旧修复树保留。新树从主线基线建立，仅迁入 21 个已验证文件并逐一比对哈希；没有再次纳入已 squash 合并的旧集成提交。解释器、锁文件、SDK 和构建工具复用已准备的固定版本，不重新下载或升级。

## 实际检查

| 检查 | 结果与证据 |
|---|---|
| commit 前审查 | 7 项修复、并发/权限/持久化边界及编译调用方审查完成；未发现本修复新增的阻断项。OCR 未恢复。 |
| 正常 pre-push | PASS；后端定向 9 项、工具 187 项、共享 B0（460 项 Python、Node 各分组、合同、类型、真实 Cordis loader、干净重建）和 FilterBuilder；LFS 正常。 |
| 远端 CI | 最终 PR 提交 `3862e77` 的 [CI run 34385964860](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34385964860) 和合并后 main `788b5b1` 的 [CI run 34386758906](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34386758906) 均为 SUCCESS。未选中的 job 是 SKIPPED，不算执行通过。 |
| 连续成板 | 第一份结果建板成功；换选第二份结果，新 batch/operation/idempotency ID 建成另一块板，无 409。 |
| 丢响应重试 | 浏览器 fetch 包装在第二次 POST `/batches` 的服务端 200 后主动抛出网络错误；dialog 仍开。点击同一成板按钮重试，请求体逐字相同，仍共 2 块板。见 [请求与数量断言](evidence/competition-repair-2026-09-10/boards-verification.json)。这项有意故障不是后端失败。 |
| 同页重开、保存布局 | 返回聊天 → footer 再开 → 认可成板 → 编辑看板，显示已存板、COMPLETE 和行数 1；选中板块右移、保存版本，再关闭重开仍为 `x1/y0/w6/h4`。GET 恢复的是该板绑定的第二份结果。 |
| 草稿首次创建和更新 | 人群行动 → 预览 6 个合成候选 → 填对照/停止条件 → 保存草稿，得到 v1；关闭重开后更新文案到 v2，再次重开保留相同 draft ID 和第二版文案。`auto_send=false`，没有提交复核或发送。 |
| 诊断会话隔离 | 从浏览器对本轨合成 HTTP 使用明确测试 session ID：第一会话 step 200，其后 11 次 capabilities 200，第 13 次总调用 429；另一会话 INHERIT 422，新会话 capabilities 200。见 [会话断言](evidence/competition-repair-2026-09-10/diagnosis-session-qa.json)。这是 live HTTP 层；原生工具 session 传递另有 11 项编译工具测试，不冒充真实模型对话。 |

浏览器 [HTTP 记录](evidence/competition-repair-2026-09-10/browser-trace.json) 仅收集本轨 competition 路径、方法、状态及公开合成请求体，不含认证头。布局检查的 DOM/HTTP 记录见 [layout trace](evidence/competition-repair-2026-09-10/browser-trace-layout.json)。这些 UI 行为全部由真实点击、填写与保存驱动，未修改 DOM 伪造成功状态。

![丢响应后的可重试状态](evidence/competition-repair-2026-09-10/screenshots/board-response-lost.png)

![保存布局后同页重开](evidence/competition-repair-2026-09-10/screenshots/board-layout-persisted.png)

![同一行动草稿 v2 重开](evidence/competition-repair-2026-09-10/screenshots/draft-v2-reopened.png)

## 开放项与未验收范围

1. **固定上游首次启动提示的状态反馈异常。** 新配置下两次点击 Internal Testing Notice 的 Continue，界面提示确认无法保存；本轨 `harness/settings.yaml` 实际已持久化 `ui-onboarding.welcomeNoticeVersion: 2026-08-13.1`。刷新后提示消失，随后正常选择 Configure later 继续。没有删 DOM 或写入跳过标志；未修改固定上游源码，尚未定位状态反馈的完整根因。
2. **原生工作区/新会话完整路径未验收。** Add workspace / Choose workspace 调用的是 macOS 原生目录选择器；无头浏览器不能操作该窗口。本次只回收经父 PID 核验、本轨 DSH 创建的两个 picker 进程，并关闭相应浏览器提示。未由此宣称 T17 通过。
3. **现有产品缺口保留。** B0 同域 `/b0/assets` 仍 404，比赛独立 HTTP 正常；界面已说明两平面差异。登记图表下拉切换只是当前组件显示，单独切换不会启用保存，重开恢复已存 TABLE；本次验证通过的是布局保存，不是图表类型持久化。界面混用上游浅色外框和比赛深色内容，未作完整设计/响应式验收。

![首次启动提示仍报保存失败](evidence/competition-repair-2026-09-10/screenshots/onboarding-save-failed.png)

本份七项修复 QA 完成时，T13 真实模型、T15 三角色业务 UAT、T16 容量未运行，T17 PARTIAL；后续真实模型与性能证据见七阶段验收账本。没有真实业务数据、营销发送、部署或恢复 OCR。上述开放项不属于本次 7 项修复的新回归，不能用本次范围通过替代整产品验收。

## 复现及收尾

后端、编译组件和 B0 验证入口见 [首轮修复记录](COMPETITION-REPAIR-2026-09-10.md) 和 [当前验证入口](../operating/verification.md)。浏览器需要两个有限结果：默认启动夹具，加一份不同 run/result ID 的同结构合成保存分析；第二份 ID 为 `run_repair_second_synthetic` / `result_repair_second_synthetic`。本次在私有状态目录完成，不改仓库夹具或真实数据。

启动使用 `COMPETITION_SYNTH_PORT=18083`、`COMPETITION_SYNTH_WEB_ORIGIN=http://127.0.0.1:4325`、私有 `COMPETITION_SYNTH_STATE`，以及 `scripts/dsh-dev/cli.mjs start --plugin on --web-port 4325 --fresh --detach --upstream <固定上游>`。浏览器 transport 指向本轨合成 API；认证只使用启动器的公开合成夹具 token，日志不保留认证头或 DSH launch token。

本次临时实例已用修复工作树的 `scripts/dsh-dev/cli.mjs stop` 和核验归属后的 18083 进程停止，独立浏览器也已回收；原修复树及其工具链保留。4327 / 8000 / 5173 和既有 14327 不属于本轨，保持原状。Git 已完成合并及 main CI 核验。
