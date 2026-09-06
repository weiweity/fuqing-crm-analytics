# 阶段 Git 归档与合并前 QA

日期：2026-09-06。范围：用户要求的第 1 项成果归档、第 2 项合并遗留处理。候选 commit `3c5a77ac0602c655a827fde3497a059716e40083`；[PR #67](https://github.com/weiweity/fuqing-crm-analytics/pull/67)。整体 B0 仍为 PARTIAL。

## 成果与修复

- 原有 22 个阶段提交已随分支保存到远端；工作流治理为 commit `03106a5`，重置时序修复为 commit `b269c6c`，登录声明修复为 commit `dc96a3f`，测试编译目标兼容为 commit `3c5a77a`。均使用正常 hooks。
- 已核对其他工作树独有内容：main 的规则文件与归档说明、blueprint 的 README 和五份设计文档，共 9 个文件保存本地副本和哈希清单。原件保留，私有副本未入 Git；没有清理工作树或分支。
- 重置在首个 await 前递增请求代次；旧成功、旧失败、旧 finally 均不能污染重置后的结果、错误或忙碌状态。新增请求可独立完成；组件卸载也使旧请求失效。
- 共享登录页现在仅声明增长董事会演示使用合成数据；普通 CRM 的账号权限与认证逻辑不变。

## 本次实际验证

| 层级 | 结果与证据 |
|---|---|
| 正常 pre-push | 后端分 8 组：1725 PASS / 77 SKIP / 71 DESELECT；未新增跳过或复用旧结果放行 |
| Vue | 类型检查、构建和 23 文件 / 205 项单元测试通过；保留现有大 chunk 警告 |
| B0 静态与合成检查 | 164 Python、133 源 Node、原目录及干净构建各 14 项编译装配/组件检查通过 |
| LFS / 远端分支 | 11 个对象、1.6 MB 上传成功；远端分支指向上述候选 SHA |
| 实际演示浏览器 | 已有本地合成 Mission 的问数、重置通过；390px 视口无横向溢出，未见控制台错误 |
| 时序浏览器回归 | 受控 HTTP 保留旧请求，分别让旧成功/旧失败跨越重置与新请求，均通过；最终显示新答案，旧 finally 不清除新请求忙碌状态 |
| 登录浏览器 | 仅在测试浏览器拦截演示能力响应以查看共享登录页；1440px 与 390px 文案、布局通过，无 page error |
| 暂存 lint | 6 项新增索引测试及相关旧测试共 28 PASS；全文件暂存快照检测、未暂存修复不能隐藏错误、Git 错误拒绝放行均已验证 |

本地证据保留在 `.context/checks/closeout-push-second.log`、`.context/closeout-20260906/qa-ui-browser.json` 及同目录截图。首次推送因测试使用了编译目标不支持的 Promise API 而被正常阻断，改为普通 deferred fixture 后重新完整推送通过。首次浏览器脚本匹配范围过宽拦截 Vite 模块，收窄到业务 API 后重跑通过；失败记录保留。

浏览器时序负测使用独立上下文和合成 HTTP 响应，不声称真实模型或 CRM 验收。实际演示测试仅重置合成 Mission。已有服务进程保持，未启动真实库、ETL 或部署。

## 远端与后续

首轮远端 CI 的 frontend、dependency-audit、docker-smoke、lint、ground-truth-lint、contract-filterbuilder-lint 已通过。[CI 34042551155](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34042551155) 的后端测试因 lockfile 未安装可选 xdist 而拒绝 `-n0`；[B0 34042551208](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34042551208) 在上游嵌套脚本调用裸 pnpm 时因隔离 PATH 无入口失败。两者均保留失败日志。

后续补丁将串行选择改为 pytest 自带 `-p no:xdist`，新增无第三方插件的实际子进程回归（先失败、后通过，相关 26 项通过）；B0 仅在自身准备目录创建 Corepack shim，嵌套 shell 的固定 pnpm 版本回归通过。未增加 xdist 安装、改固定上游或设置全局 shim。修复后的远端结果以 PR 最新 SHA checks 为准，尚不据此声明合并。

第 3 项将在第 1、2 项检查完成后独立推进：原生故障到卡片全链、多 key 原生卡片共存、监督器退出证据。

第二轮 CI 已越过两处启动失败：B0 上游构建成功；普通后端进入测试后在严格 worker RSS 检查失败，独立 B0 环境的六个 SQL barrier 用例也失败。后者在本地禁用 NumPy 导入后已复现 DuckDB `create_function` 报依赖错误，B0 检查锁补入与当前工程一致的 NumPy 2.4.4；探针通过私有 proof pipe 返回设置失败类型，避免仅等待超时。

Linux 峰值补丁采用当前进程映像的 `/proc/self/status` VmHWM，保留监督器采样与原资源上限。依据 [getrusage 手册](https://www.man7.org/linux/man-pages/man2/getrusage.2.html) 的 exec 保留行为和 [Linux proc 文档](https://www.kernel.org/doc/html/latest/filesystems/proc.html)；新增大父进程 fork/exec 与子进程释放后保留峰值回归，本地 worker/资源 59 项通过。Linux 实测由后续 CI 证明，不以 macOS 单测替代。

第三轮 Linux 已验证旧指标污染：[CI 34043450329](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34043450329) 中相同子进程的旧指标为 567083008 bytes，当前映像峰值约 71475200 bytes，原严格资源测试通过。新增回归的相邻峰值读数相差 20480 bytes，触发了不适用的逐字节单调断言；改为确认释放后仍保留 32 MiB 工作负载的峰值增量。[B0 34043450142](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34043450142) 同样只有此断言失败，原有 164 项通过，包括此前六项 UDF 故障测试。最终全绿结果仍以 PR 后续 checks 为准。

历史 Excel 全仓审计仍有 32 项旧问题，未改变字段倍率。真实模型、业务 UAT、容量、数仓 ETL、公开交付及分支清理不属于本次通过结论。
