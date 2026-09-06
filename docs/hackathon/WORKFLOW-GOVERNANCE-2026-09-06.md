# 工作流治理实施记录（本地补丁）

日期：2026-09-06。范围：按优先级治理 hooks、测试隔离与固定成本、检查矩阵、CI 和证据入口。当前规则/命令见 [验证入口](../operating/verification.md)。产品仍为 **B0 PARTIAL**。

## 工作位置与交付状态

- 成果工作树：`fuqin-date/.worktrees/hackathon-mission-mvp`，分支 `codex/architecture-warehouse-plan-closeout`。
- 基础 HEAD：`d1b1e0cabc11bf6f5d1ea3fe441ca5001170f4ff`。本报告描述其上的**未提交本地补丁**，不是该 SHA 已包含全部治理。
- 主仓仍为 main / `e2b3bbda7f02dc5468a1fd90d8aa40bcea0428e6`；用户的 Skill 类型变更与未跟踪 `ARCHIVE.md` 保留。两处共用 Git 目录，各工作树解析自己的相对 `.githooks` 文件。
- 本轮没有 commit、push、PR、merge、发布、全局配置修改、业务库操作或真实分支清理。已有演示 PID 36717/36727 保留，未为验证启动或重启归档服务。
- 接手时远端只读核验未发现成果同名分支/PR/该分支 CI。此后未执行远端写入，不把本地成功当作远端检查通过。

## 已实施及证据链

| 优先项 | 根因修复 | 回归入口 |
|---|---|---|
| hook 正确性 | pre-commit `pipefail` 保留检查器失败；pre-push 先验证、再传递原始 refs/remote 参数给 LFS；diff 失败保守扩大；改名保留两个路径 | `test_git_hook_boundaries.py` 无害替身运行真实 hook，覆盖失败传播、LFS、删除-only、新分支累计差异 |
| 隐式清理 | 移除 Git post-merge 自动清理；audit 标 MERGED；维护脚本默认预览、准确本地目标、无远端写入/强删回退 | `test_branch_cleanup.py` 在自建微型 Git 仓库检验默认无改动、保护/未合并/占用拒绝和精确删除 |
| 测试固定成本 | 合成认证 cost-12 哈希每进程缓存；用例只恢复状态；去掉普通 API fixture 的重复 loader，专用密码安全测试不降强度 | `test_test_environment.py` 禁止普通 fixture 再调用 hash/loader，并校验真实成本和密码 |
| 测试环境 | 禁用 dotenv，独立临时 HOME/TMP、业务库/缓存库路径；归档库显式选择；移除跨会话清理和测试模块收集时的环境写入；tracker 改显式 fixture | 普通 pytest 不导入 app/ETL、不探库、不清理前次会话；认证/限流/Mission 混合回归与完整同进程回归 |
| 暴露出的数据依赖 | Mission 控制路径由自身数据源处理，不再申请旧 CRM 读连接 | 已验证：原代码在归档库缺失时稳定复现失败；补丁后 Mission/QueryRouter 33 项通过，fixture 一旦借用旧库就失败 |
| 检查选择 | B0、Vue、旧 backend、工具独立选择，混合取并集，公共 conftest 和缺失测试目标扩大回归；版本预检先于耗时检查 | 已验证：`test_check_runner.py` + 路径回归；真实共用入口执行 B0/Vue/tooling |
| CI 和依赖 | 本地/PR 共用命令生成器，两个 PR workflow 共用路径计划；nightly/weekly 共用 bounded runner；保留既有固定依赖和 CI 硬门禁 | YAML 解析、供应链/资源/LFS/门禁回归；远端 CI 本轮未运行 |
| 证据与文档 | 新验证入口列触发、调用、写入、网络、阻断规则；更正 hooks README/setup 文案；旧 operating 文档加历史声明；报告保存 JUnit/耗时/RSS/来源 | 本文与 verification 为本轮入口，T01–T08/历史失败不改写 |

## 本次实际验证

环境：macOS，Python **3.14.4**；B0/Vue 最终使用本机已有 Node **24.19.0**，固定 DSH `d347e703908d0406b7a7ef80e3a0e594d86b2215`。没有升级依赖。

| 验证层 | 实际结果 | 本地证据 |
|---|---|---|
| 完整合成后端、同一进程 | **1717 PASS / 77 SKIP / 71 DESELECT，140.80 秒**；runner 总计 142.097 秒，峰值 **0.701 GB**，196 个测试文件 | `.context/checks/governance-backend-single-process-20260906/summary.json`、`group-001.xml` 和同名 `.log` |
| 最后补充的 hook/选择器/CI 回归 | **134 PASS，10.64 秒**；经 `run_checks.py` 真实 tooling 路径运行，包含全套开始后补充的改名两路径回归 | `.context/checks/governance-tooling-final-20260906.log` |
| B0 共用入口 → 既有 pipeline | **164 Python / 133 源 Node / 原目录与干净目录各 14 编译装配 PASS**，类型与干净构建通过 | `.context/checks/governance-b0-node24-20260906.log` |
| Vue 共用入口 | vue-tsc/Vite 构建通过；**23 文件、201 单测 PASS** | `.context/checks/governance-vue-node24-20260906.log` |
| 静态检查 | backend 与本轮 CI/runner/清理脚本 Ruff、B2 imports、FilterBuilder、channel alias、规则入口一致性通过；差异与新增引用核对 | 本轮执行输出与仓库差异 |

完整后端运行使用 `--chunk-size 10000`，刻意让所有模块共处同一进程，覆盖跨模块状态串扰；日常默认仍是每 25 文件一个受限进程。此前分组调试的失败与后续补证日志保留在 `.context/checks/governance-*`，不以删记录掩盖失败。完整回归后新增的改名回归单独覆盖，没有把未重新采集的用例计入 1717。

完整回归记录的 Python 检查源码摘要：`1be64ba755f54a46ec7ee64774cb6d78fe58008aa4cc742530a2a7e6657fe487`。摘要描述该次运行的检查源，不是自动复用许可；后续补充回归和本地差异须一起审查，不能仅按 HEAD 跳过 hook。

### 耗时口径

用户交接提供的旧成绩为 **1676 PASS / 76 SKIP / 71 DESELECT，1719.45 秒**。本次完整同进程结果为 **140.80 秒**，观察值约从 28.7 分钟降到 2.35 分钟。

两次代码、测试数量与隔离方式不同，旧成绩是交接记录而非本轮重跑，因此这不是严格相同环境 A/B。此前对旧认证 loader 的独立合成测量约 0.51 秒/三账户，按旧 1676 用例估计仅重复 setup 即约 14.3 分钟；本次行为回归直接证明普通 fixture 不再重复哈希。未靠降低 bcrypt 强度、增加 C 类排除或设置 skip-hook 来提速。77 条 skip 包括既有环境/归档验收条件，逐条理由在 JUnit 和日志。

### 调试时暴露并处理的失败

1. 无归档库的 Mission `/access` GET 暴露旧 CRM 连接依赖；按数据所有权修复中间件分流，并保留负测。
2. CI 旧测试读取旧 `pull_request.paths` 或写死 job 清单；改为检查共用选择器、实际资源接缝、核心检查和禁止阻断型浏览器 E2E，不以加 skip 放行。
3. 默认 shell Node **25.8.2** 被 B0 固定工具链拒绝；切换该次检查的 PATH 至已有 Node 24，新增前置版本检查。失败日志保留，不改全局 Node。

## 尚未完成的层级

- 本地补丁未提交/推送；LFS 在真实 remote 的接线效果、远端 CI、required checks 及 merge QA 仍需对应 Git 授权后的证据。
- CI 的 Docker/依赖审计仅验证配置与选择行为，没有在本轮启动 Docker、安装依赖或执行远端审计。Vue 构建保留现有 chunk 大小提示。
- 慢测、归档数据/宿主安装验收、原生故障至工具卡全链、卡片共存、历史监督器退出根因、真实模型、容量与业务 UAT 不因本轮静态/合成通过关闭。
- 演示重置后的在途问数响应竞争、共用登录页 synthetic 声明范围仍是原有业务开放项。只修复此次隔离验证暴露的数据连接依赖，未进入 B1。
- 主仓旧文件版本和全局 Claude 配置没有自动覆盖；历史运维脚本保留冷存，未恢复 launchd/ETL，也未清理真实资产。
