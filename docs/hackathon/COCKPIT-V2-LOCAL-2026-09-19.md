# 驾驶舱 V2 本地交付（2026-09-19）

**C01–C03 与五处修复已完成实现、隔离验收及代码推送，PR 待创建。** 从 codex/cockpit-v2-kernel / c0f47a24 接管的 Grok 四包与 Codex 成果已提交至候选 `1da06ba1`，版本为 0.10.0.0；本次文档同步随后追加。产品整体仍 PARTIAL；真实模型、现役和真实业务未验收。

## 使用路径

1. 在原生对话中生成文件，再打开驾驶舱；点「刷新」读取该来源会话的交付。
2. 选择工作区 HTML 查看，点「保存为可编辑副本」，检查候选后「确认保存副本」。原工作区文件保持原样。
3. 已存页面点「编辑」，选择有可靠源码映射的文字，填「替换文本」并预览；确认生成新版本，取消保留保存版本。历史回退也先预览。
4. 看板点「编辑」后选中组件，在右栏改标题/可支持的属性/数据来源，预览后确认。点选不会发消息；「用 AI 改」才进入原生对话。
5. 看板布局、版本历史和回退在侧栏。窄屏编辑时收起产物列表，手机在「画布预览/编辑设置」切换。
6. 切换资产或返回对话时，未保存修改走原有三选离开保护。回执未知先留在当前页核对或重试同一次确认，不切选区、不再建 PATCH；看板可尝试取消未应用草稿，只有服务端匹配取消回执后才解除保护。

## 本次验证

| 层级 | 结果 |
|---|---|
| 路径计划 | backend full + B0 + FilterBuilder；未选中旧Vue构建 |
| 合成后端日常 profile | 261文件、11组；2633 passed、77 skipped；skip/deselect不算通过 |
| B0完整聚合 | PASS：固定版本、离线契约、Python/Node、类型、插件构建、真实Cordis夹具、干净重建 |
| 真实原生RPC+HTTP | PASS：生成/确认/布局/回退/选定编辑/重开（synthetic，无模型） |
| Chromium浏览器 | 本轮21项PASS，0未处理异常；新增原始HTML重入、脚本顺序、新看板预览切换、属性入库和看板确认409恢复；实际HTML副本/替换/取消/保存/回退，看板字段/布局，冲突/未知回执/来源变化/EOF负测 |
| 持久化 | 真实SQLite新读取、浏览器重载恢复保存版本、丢回执后同键恢复不重复写 |
| lint/导入 | backend Ruff、导入完整性PASS；FilterBuilder/渠道别名相关合成测试由backend profile覆盖，本轮未另跑独立lint |
| 完整宿主/现役/真实模型/真实业务/用户本人UAT/远端CI（创建PR前） | NOT_RUN |

Node24.19.0、Python3.14.4、Chromium151.0.7922.34；1440/1280/1024/390 ×1000、100%缩放、DPR1。浏览器使用生产组件/客户端、synthetic宿主文件与真实FastAPI/SQLite；不是完整DSH壳。

本次修复证据：`.context/checks/cockpit-v2-ship/`，`full-checks.log` 为完整路径矩阵成功日志；`targeted-final.log` 为107项针对性测试；`browser-pass/results.json` 为21项浏览器通过和17张截图。`backend-summary.json` 为本轮后端统计，完整矩阵汇总为 `.context/checks/20260919T143819911190Z/summary.json`。

上一轮本地交付证据目录：`.context/checks/cockpit-v2-codex/`。
完整B0日志 `pipeline-final-3.log`，产物指纹 `.context/dsh-b0/build-evidence.json`；浏览器 `browser-release-candidate.log`、`browser/results.json`、同目录16张截图；后端覆盖 `backend-coverage.json`。
本轮失败保留：`browser/` 为定位器失配、`browser-final.log` 为启动路径错误、`browser-final/` 为CAS取消后旧选择阻止刷新；修复后以 `browser-pass/` 为准。
上一轮原失败日志保留：STATUS行数、夹具订阅/运行时、B0 effect类型/无window、EOF半文件；修复与最终复验分开记录。

## 适用范围

- 工作区列表手动/重入刷新；相对文本资源可有界内联，经典脚本保留内联/外部标签顺序及重复执行；模块、async/defer/nomodule 等无法保真的脚本执行方式明确拒绝转换。禁止外联，Host文本接口不能读取的二进制资源明确报错。
- 普通 HTML 无 data-shine-node / node_map 时可入库但保持只读；不猜测映射。动态节点、含子标签节点、绑定数据节点不做普通改字。
- 原生侧栏切换无法 veto；store草稿在插件存活期间保留。浏览器刷新/关闭由 beforeunload 提醒，不声称断电或浏览器重启后恢复未确认草稿。
- P13原首场失败、后两场NOT_RUN保留。文件入柜不代表Agent Team工具注入修复，字面替换不代表复杂AI编辑通过。
- 本轮用户授权 commit/push/PR，明确跳过追加代码审查；提交和推送已完成，PR 由主任务在文档同步后创建。merge/reload 未执行；6677/18091与归档真实业务库未切换或修改。原HANDOVER与交接稿保留，不自动纳入Git。

## Git 与证据收尾

三笔代码/版本提交为 `336ede2d`（HTML 来源合同与持久化）、`8b2dc43a`（驾驶舱 V2 与修复）、`1da06ba1`（0.10.0.0 候选与证据）。正常 push 已成功，远端分支为 `origin/codex/cockpit-v2-kernel`；PR 创建和远端 CI 在此记录时仍待主任务完成。

第一次 push 在完整后端/B0 检查通过后以 141 退出，随后核验远端分支尚不存在；错误日志 `push.log` 保留。使用 SSH 保活重试并再次通过原 hooks 后成功，见 `push-retry.log`；没有跳过 hooks，未将第一次发布失败写成成功。该轮测试自动生成的 T0 JSON 与三张截图随本次文档同步提交，时间为 `2026-09-19T15:03:22.805Z`；前一次生成副本保留于 `.context/checks/cockpit-v2-ship/push-attempt-1-t0/`。T0 只记录本次 Chrome 沙箱观察，不替代完整 DSH/P13/真实业务验收。

## 复现浏览器证据

在本任务树的 `dsh-plugins/analytics-workbench` 执行，复用机器已有工具；探针会创建并关闭其拥有的临时服务和浏览器，不使用现役端口：

```sh
PATH="$HOME/homebrew/opt/node@24/bin:$PATH" \
B0_BUILD_UPSTREAM="/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics/.context/dsh-b0/upstream" \
FQ_B0_PYTHON=/Users/hutou/homebrew/bin/python3.14 \
COCKPIT_PLAYWRIGHT=/Users/hutou/Desktop/beian/node_modules/playwright-core \
COCKPIT_CHROMIUM="/Users/hutou/Library/Caches/ms-playwright/chromium-1234/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing" \
node test/cockpit-v2-browser-probe.mjs
```

报告位于原仓本地交接目录 `.context/handoffs/cockpit-grok-codex-20260919/reports/V2-C01.md`、`V2-C02.md`、`V2-C03.md`。C01含状态表和截图，C02含接口与跨层修复，C03含最终矩阵、失败证据与未运行项。
本次修复后按用户授权执行 `/ship` 至 PR；新增代码审查按用户要求跳过。现役切换、真实模型与真实业务验收独立安排。
