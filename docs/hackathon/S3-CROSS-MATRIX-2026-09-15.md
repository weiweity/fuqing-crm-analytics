# S3 正式壳分支与视口交叉补验（2026-09-15）

> 后续用户授权的本地代码修复与定点复验见 [S3 界面修复](S3-UI-REPAIR-2026-09-15.md)：窄屏与提示已修，B0 检查通过，本次取消复验未跳转且未新增保存版本；85 历史未定因不回写为成功。以下保留原批次失败与设置失败证据。

结论：**PARTIAL**。B3 核心恢复分支已补齐桌面与 390px 的交叉证据；核对／取消两种处理中状态的三个恢复按钮，在两种视口下共 **12 次实际鼠标点击**，均没有额外业务请求。全局刷新按钮与看板选择器的四组补测中，三组通过，**桌面取消处理中一组意外返回原生对话，未通过，原因尚未定位**。后续最小复测的写入前阻断未生效，实际新增同正文 **v15**，记为测试设置失败，未复验到取消忙态。已清理临时设置并只读刷新确认 v15 正文完整、原板仍为 **v9**。步骤 60–87 的 v14 结论保留为该批历史时点，最新接续见文末。

本轮在已有真实 Chrome 标签页 `199365531`、正式 DSH 壳 `http://127.0.0.1:6677/` 上操作。起点为说明板 v9；没有无头浏览器、脚本合成点击、代码修改、服务重启、模型调用或真实 DuckDB 访问。`HANDOVER-CODEX.md` 仍保留、不提交。

旧证据与历史失败见 [首次验收记录](S3-ACCEPTANCE-2026-09-15.md)。新证据位于本机 `.context/checks/s3-b3-shell-20260915/cross-matrix/`，编号 60–87；旧证据仍在其父目录，未移动或覆盖。正式壳没有 Figma node-id，以下按可见业务状态和保存版本记录；Figma 节点只用于合同对照。

## 核心分支交叉矩阵

“前／后”是业务状态。不同试次使用不同版本，`vN` 表示该试次的当前版本；单独标明实际版本的证据以截图为准。两个故障场景的“确认前取消”在正式壳共用同一待确认预览组件及取消处理，引用共同组件的取消证据，不伪造两个不同页面。

| 步骤 | 点击文案 | 点击前状态 | 点击后状态 | 桌面截图路径 | 390px 截图路径 | 合同结果 |
|---|---|---|---|---|---|---|
| 1 | 确认保存这份看板；写入前中断 | 待确认草稿 | 结果未知 | `../18-before-write-unknown.png` | `../39-390-before-write-unknown.png` | 通过 |
| 2 | 取消，保留已保存版本 | 写入前确认预览 | 原文／原版本 | `../03-desktop-cancel-v2.png` | `../15-390-cancel-v4.png` | 通过，共同预览组件 |
| 3 | 核对保存结果 | 写入前结果未知 | PENDING，仍未知 | `../19-readonly-pending.png` | `../40-390-v7-pending.png` | 通过 |
| 4 | 重试这次保存 | 写入前未知，未经核对 | 保存成功；随后独立注入读取失败 | `61-desktop-direct-retry-refresh-failed.png` | `../55-390-direct-retry-saved-refresh-failed.png` | 保存分支通过 |
| 5 | 尝试取消未应用草稿 | 写入前未知，未经核对 | 取得取消回执，原文不变 | `../53-direct-canceled-v8.png` | `79-390-direct-canceled-v14.png` | 通过 |
| 6 | 再次核对保存结果 | 已读到 PENDING | 处理中 → PENDING 仍未知 | `81-desktop-inspect-global-disabled-result.png` | `66-390-inspect-all-disabled-result.png` | 通过 |
| 7 | 重试这次保存 | PENDING 仍未知 | 已保存新版本 | `67-desktop-pending-retry-v11.png` | `../43-390-v7-read-completed.png` | 通过 |
| 8 | 尝试取消未应用草稿 | PENDING 仍未知 | 取消回执后恢复原文 | `../46-desktop-canceled-v7.png` | `83-390-cancel-global-disabled-result.png` | 通过 |
| 9 | 确认保存这份看板；丢弃成功回执 | 落盘后断连场景确认前 | 服务端确认 200，前端未知 | `68-desktop-after-unknown.png` | `70-390-after-unknown-cancel.png` | 通过 |
| 10 | 取消，保留已保存版本 | 落盘后断连场景确认前 | 原文／原版本 | `../03-desktop-cancel-v2.png` | `../15-390-cancel-v4.png` | 通过，共同预览组件 |
| 11 | 核对保存结果 | 落盘后未知，未经取消 | 直接读到已存版本 | `69-desktop-after-direct-inspect-v12.png` | `../49-390-direct-inspect-v8.png` | 通过 |
| 12 | 重试这次保存 | 落盘后未知，未经核对 | 同幂等键确认，未再升版本 | `../35-confirmed-v6-refresh-failed.png` | `76-390-after-retry-refresh-failed.png` | 通过；确认后的读取失败另记 |
| 13 | 尝试取消未应用草稿 | 落盘后未知 | 取消被拒，内容保留 | `../29-applied-cancel-rejected.png` | `71-390-after-cancel-rejected.png` | 行为通过，提示有歧义 |
| 14 | 核对保存结果 | 取消被拒 | 已核对已存版本 | `74-desktop-rejected-inspect-v13.png` | `../33-390-verified-saved-v5.png` | 通过 |
| 15 | 再取消 | 取消被拒 | 处理中 → 仍被拒 | `73-desktop-cancel-all-disabled-result.png` | `72-390-cancel-all-disabled-result.png` | 通过，未撤销保存 |
| 16 | 刷新已保存看板 | 已确认保存，但刷新失败 | 只读恢复已存版本 | `77-desktop-failure-refresh-v14.png` | `../37-390-refreshed-v6.png` | 通过 |
| 17 | 查看历史版本 → 预览回退 | 已确认保存，但刷新失败 | 待确认回退草稿，尚未保存 | `62-desktop-failure-rollback-preview.png` | `../56-390-refresh-failed-rollback-preview.png` | 通过；随后取消，正文保留 |

表中截图路径相对于新证据目录；`../` 指向首次验收证据。核心分支矩阵的通过不覆盖下述全局控件异常，也不等于 G5、M1 或用户本人 UAT 通过。

## 本轮请求与版本证据

计数来自真实标签页的 `Network.requestWillBeSent`，仅筛选 `/api/shine-mage-board` 并保存操作名与数量。它是浏览器请求／尝试次数，**不是数据库事务次数**。写入前被阻断的确认仍可能有一次浏览器请求事件，不能据此声称服务端收到了写入。落盘后注错只在实际 `confirm` HTTP 200 的 Response 阶段丢弃响应；随后只读核对／同键重试及新版本回读证明结果。

| 新步骤／证据编号 | 实际点击或处理 | 前 → 后 | 浏览器请求计数 | 结果 |
|---|---|---|---|---|
| 60–63 | 桌面写入前中断后直接重试；刷新失败后回退预览并取消 | v9 → v10；回退草稿 v11 取消 | 重试 confirm 1、get 1；历史 history 1、rollback_preview 1；取消 cancel 1 | 通过，v10 正文保留 |
| 64–67 | 桌面未知后核对；两视口核对忙态按钮；桌面 PENDING 重试 | v10 → v11 | 每次核对 preview 1；重试 confirm 1、get 1、list 1 | 通过 |
| 68–69 | 桌面确认成功丢回执后直接核对 | v11 → v12 | 核对 preview 1、get 1、list 1 | 通过 |
| 70–74 | 窄屏落盘后取消被拒；两视口再次取消；桌面核对 | v12 → v13，取消均未撤掉 v13 | 每次取消 cancel 1；核对 preview 1、get 1、list 1 | 通过 |
| 75–77 | 窄屏成功回执丢失后重试；确认后读失败；桌面刷新 | v13 → v14；重试仍 v14 | 重试 confirm 1、get 1；恢复 list 1、get 1 | 通过，同幂等键 |
| 78–79 | 窄屏写入前未知直接取消 | v14／草稿 v15 → v14 | 取消 cancel 1 | 通过，未保存 v15 |
| 80–83 | PENDING 再核对，全局刷新／选择器禁用；窄屏取消 | v14／草稿 v15 → v14 | 每次核对 preview 1；取消 cancel 1 | 通过 |
| 84–85 | 桌面取消处理中实点全局刷新／选择器 | v14／草稿 v15 → 意外返回原生对话 | cancel 1，没有额外业务请求 | **未通过，停止后续注错** |
| 86–87 | 清理覆盖后只读重开说明板，恢复侧栏 | 重新读到 v14，追加句完整；原板列表 v9 | list 1、get 1 | 清理与最终回读通过 |

每行有同编号 `.audit.json`；Response 注错另有 `.fault.json`。76 的审计首次混入较早事件，已按最后一组同草稿确认请求配对及后续 get 校正，`sameKeyAsFirst=true`。重读事件时 `truncated=true` 表示早期缓冲已淘汰；最后一组两次确认与后续 get 均仍在缓冲。本行只据保留的该组事件判断，不把它当全会话无缺失审计。任何幂等键原文、请求头或凭据均未写入证据文件。

## 处理中按钮实点

使用实际浏览器鼠标点击。为准确观察短暂忙态，施加 4000ms 网络延迟；只读获取已显示控件的边界和 disabled 属性，在响应返回前逐一点击，点击后读取 UI，再等待结果。没有 dispatchEvent、DOM click 或 UI 状态改写。

| 状态／视口 | 被实点的三个恢复按钮 | 观察完成耗时 | 请求数 | 结果与截图 |
|---|---|---|---|---|
| 核对／桌面 | 核对保存结果、尝试取消未应用草稿、处理中… | 4701ms | preview 1 | 通过；`65-desktop-inspect-all-disabled-busy.png` → `65-desktop-inspect-all-disabled-result.png` |
| 核对／390 | 同上 | 4910ms | preview 1 | 通过；`66-390-inspect-all-disabled-busy.png` → `66-390-inspect-all-disabled-result.png` |
| 再取消被拒／390 | 同上 | 4635ms | cancel 1 | 通过；`72-390-cancel-all-disabled-busy.png` → `72-390-cancel-all-disabled-result.png` |
| 再取消被拒／桌面 | 同上 | 4802ms | cancel 1 | 通过；`73-desktop-cancel-all-disabled-busy.png` → `73-desktop-cancel-all-disabled-result.png` |

四组共 12 次实际点击；没有额外确认、取消或核对请求。耗时是包含 4 秒人工网络延迟与观察开销的本次上界，不是正式壳性能基准，也不能替代 Figma 的约 0.8 秒原型计时合同。

| 全局控件补测 | 被实点控件 | 观察耗时 | 请求数 | 结果 |
|---|---|---|---|---|
| 核对／桌面 | 刷新已保存看板、打开已保存看板 | 4354ms | preview 1 | 通过，81 |
| 核对／390 | 同上 | 4851ms | preview 1 | 通过，82 |
| 取消／390 | 同上 | 4852ms | cancel 1 | 通过，83 |
| 取消／桌面 | 同上 | 4565ms | cancel 1 | **异常待定位，85** |

85 的忙态截图显示正确禁用，点击前 disabled 也为 true；但最终截图显示原生对话，不是合同预期的看板取消结果。工具未报告同时操作中断，现有证据不能区分产品交互、焦点／坐标变化或外部操作。`busyEnded=true` 仅表示忙态控件不再存在，不能当作成功；该文件已追加 `verdict=INCONCLUSIVE` 与预期结果不可见的说明。没有把此项归因为已确认的代码缺陷，也没有继续注错尝试绕过停止条件。

## 收尾与开放项

步骤 60–87 有意新增说明板 v10–v14，保存的正文均包含与 v9 相同的 V-A4 追加句。该批各试次中取消的草稿未变成保存版本；86–87 只读重开当时仍为 v14。原板未参与该批保存，列表仍 v9。

该批结束时已清空 Fetch 模式和 URL 阻断、恢复网络延迟为 0、reset 视口覆盖、恢复侧栏展开；证据为 `86-readonly-reopened-v14.png`、`87-restored-ui-v14.png` 和 `87-cleanup.audit.json`。当前只读终态以文末 88–90 为准：阻断未生效后实际保存同正文 v15。

接续优先定位 85 的意外返回对话，再复验该组全局控件。先前发现的 390px 侧栏展开挤压正文、取消拒绝提示含糊、英文网络错误仍未修复。S4 综合 QA、S5 用户本人 UAT、R-1 及 G1–G6 继续开放；不勾 G5、M1 或 UAT。

## 85 导航定位与设置失败记录（步骤 88–90）

只读追踪当前业务源码得到以下范围判断，不能据此认定浏览器运行时没有缺陷：

- `library-board-client.mjs:159` 的取消路径取得 CANCELLED 回执后，只清除草稿并保留已保存快照，没有调用关闭驾驶舱或返回对话。
- `library-workspace.tsx:51` 起的焦点处理调用 focus；返回对话按钮在 `:83` 单独调用 goConversation。外层 `cockpit-composition.tsx:133` 的“仅看对话”调用 close；面板／会话变更也能关闭组合视图（该文件 `:55` 与 `cockpit-composition.mjs:35`）。
- 85 的按钮记录仅保存 disabled 与点击耗时，没有点击坐标，也没有两个全局控件每次点击后的截图。因此无法追溯究竟在哪一步离开画布，不能把焦点恢复、误触或外部操作任一项当成已确认原因。
- 本次只读测量刷新按钮边界为 x=854、y=64、width=138、height=42；视口 1020×649、DPR 2，与当前截图位置一致。该测量只能证明当前坐标一致，不能补成 85 的历史坐标证据。

从 v14 预览回退到同正文 v13，拟通过写入前阻断创建未知态，再只取消草稿以复验 85。实际没有进入未知态，立即停止此复测：

| 步骤 | 点击文案／操作 | 点击前状态 | 点击后状态 | 是否符合预期 | 截图路径 |
|---|---|---|---|---|---|
| 88 | 确认保存这份看板；此前设置 URL 阻断 | 已存 v14，待确认 v15 草稿 | 已保存并读取 v15，同正文 | **SETUP_FAILED**：阻断未生效；未执行取消忙态复验 | `navigation-check/88-unexpected-saved-v15.png` |
| 89 | 清理覆盖、启用 Network 观察后，刷新已保存看板 | 已存 v15 | 只读回读 v15；原板列表 v9 | 回读通过，list 1、get 1 | `navigation-check/89-readonly-refresh-v15.png` |
| 90 | 恢复侧栏展开 | 已存 v15 | v15 正文完整，无待确认草稿 | 清理完成 | `navigation-check/90-restored-ui-v15.png` |

88 的 CDP 设置命令返回成功，但该观察窗口没有任何 Network 事件，不能把空计数写成“没有请求”。本轮复测前沿用了既有 CDP 句柄，**没有重新执行 Network.enable 并验证观察有效性**；89 执行 Network.enable 后，只读刷新记录到 list/get 各一次。这确认了本轮观察初始化的缺口，尚不足以单独证明 URL 阻断失效的全部原因。88 实际保存由页面成功提示与 89 的独立回读共同证明；不伪造 confirm 的网络回执。

88 新增的同正文 v15 保留，不通过回退或删除掩盖测试副作用。Fetch 模式、URL 阻断、网络延迟与视口覆盖均已清除，侧栏恢复展开。证据另有同目录 `.ax.txt`、`88-setup-failed.audit.json`、`89-readonly-refresh.audit.json` 与 `90-cleanup.audit.json`；不含请求头、凭据或幂等键。

下一次复验前，先重新启用 Network 观察，并用只读刷新验证事件捕获及阻断／恢复确实生效；不能只凭设置命令返回值继续点击确认。复验 85 时须保存每个控件点击前的坐标、disabled、命中元素及点击后的画布状态，并以“仍在说明板、取消成功提示、已存版本不变、草稿消失”共同判定结果。85 继续为 **INCONCLUSIVE**，88 为 **SETUP_FAILED**；本次没有新增产品通过项，没有修改业务代码、提交或重启服务。
