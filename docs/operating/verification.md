# 当前验证入口与工作流

适用于成果工作树的本地补丁；是否已集成，以该工作树 Git 状态和远端证据为准。授权见 [AGENTS](../../AGENTS.md)，产品阶段见 [黑客松入口](../hackathon/README.md)，本轮结果见 [治理实施记录](../hackathon/WORKFLOW-GOVERNANCE-2026-09-06.md)。

## 单一检查定义

`scripts/ci/pre_push_path_class.py:verification_plan` 定义互相独立的 backend/B0/frontend/tooling/dependencies/deployment 维度，另有 ground_truth 与 filterbuilder 触发轴；`scripts/ci/run_checks.py` 生成并执行命令。本地 pre-push、PR 的 Python/Vue/B0 检查共用它；PR CI 只通过 `lint.yml` 调用一次 `check-plan.yml`。`dsh-b0.yml` 仅 `workflow_dispatch` 做空机器 `--prepare`。B0 的本地与 CI 构建始终调用既有 `scripts/dsh-b0/pipeline.mjs`。`merge-gate` 在路径计划失败或已选 job 失败/取消时阻断；skip 不算失败。branch protection 的增补（`b0-contract-build`、`merge-gate`）不在 git 里，需管理员另改。

| 改动 | 选择与边界 |
|---|---|
| 普通文档 | 不跑业务全套；差异/引用由本次编辑验证 |
| AGENTS、自动化配置、运维/验证文档 | 入口和 hook 行为回归；CI 的 ground-truth 仍使用 committed 模式 |
| B0 插件/内核/合同 | 既有 B0 pipeline：离线合同、Python/Node、编译/装配与干净构建；无需旧 CRM 全套 |
| Vue | `npm run build`（含 vue-tsc）和 `test:unit`；品牌、App、FilterSync 共用接缝同时选择 B0 |
| 旧 CRM 实现、未知代码、ETL | 合成 backend 全套；不运行真实 ETL |
| 普通 backend 测试文件 | 选中文件；删除/改名后缺失目标扩大到全套 |
| 公共 conftest、测试支撑文件 | 合成 backend 全套；conftest 不再仅当普通单文件执行 |
| hooks/检查脚本 | Shell 语法、改动 Python 的 Ruff、实际入口/失败/选择回归；不再只检查无关 backend Ruff |
| Python 共用锁/配置 | backend + B0 与 CI 依赖审计 |
| Docker/部署配置 | backend + CI 容器 smoke；本地入口不启动容器 |
| CI workflow | 扩大 CI 相关检查；B0 workflow 走 B0 + tooling |

混合改动取检查集合并集。新分支比较 merge-base 至待推送 SHA，不能只看最后一个提交。`--no-renames` 保留改名前后的两个路径，避免代码移入文档目录后漏检。取差异失败保守扩大，不能按空文档变化放行。未知空范围走 backend 全套。

## 本地命令

在目标仓库根目录执行。命令不安装依赖、不提交、不推送：

```bash
# 查看计划：changed-files.txt 每行一个仓库相对路径
python3 scripts/ci/run_checks.py --files-from changed-files.txt --plan-only
# 实施该检查集合
python3 scripts/ci/run_checks.py --files-from changed-files.txt
# 直接执行完整的日常合成后端 profile
python3 scripts/run_backend_tests_bounded.py
# 仅验证指定后端文件；同样使用隔离环境和共享排除列表
python3 scripts/run_backend_tests_bounded.py backend/tests/test_local_demo_access.py
```

包含 B0/Vue 的检查会先核对 Node 24，再运行耗时步骤；手工入口可用 `--node /absolute/node` 选择已有解释器。Git hook 继承调用 shell 的 PATH，需要在该次操作中选用已有 Node 24，不自动安装或修改全局版本。ruff 锁 `0.16.6`，`pyproject.toml` 的 `lint.select` 为 `E4/E7/E9/F`（0.15 默认集）；不要用无 select 的 `ruff check .` 去套 0.16 的 413 条默认规则。

B0 独立入口：`node scripts/dsh-b0/pipeline.mjs --check --python /absolute/python3.14`。`--prepare` 会下载固定上游和安装构建依赖，属于另一个明确动作。插件 `package.json` 的 `test` 是部分源测试便捷入口，`test:built` 也只有一个子集，均不能作为完整 B0 通过声明。原生查询资产需显式 `node scripts/dsh-b0/serve.mjs --python /absolute/python3.14 --native-query-assets`，不替代默认 `--native-query`。离线分析/驾驶舱合同用 `scripts/dsh-b0/analysis-contract.mjs` 与 `cockpit-contract.mjs`，不启动旧 CRM。旧 Vue 的依赖由 `frontend-vue3/package-lock.json` 管理，B0 的固定版本由 toolchain/自身锁管理，旧后端由 requirements-lock 管理；此轮未升级依赖。

已有固定版本工具链可通过环境变量 `B0_BUILD_UPSTREAM=/absolute/prepared/upstream` 供 `--check` 只读复用。仍强制验证上游 SHA、锁文件、SDK 与类型版本；不下载、不升级。该覆盖不允许用于 `--prepare`。

保存分析/驾驶舱的 finite mock 组件仍须独立通过类型检查、编译后 DOM 测试与干净重建。HTTP CONNECTED overlay 另有 `query-card-save`、`asset-overlay`、`native-query-assets-smoke` 与独立 analysis/cockpit HTTP 测试。`asset-overlay` 编译后 DOM（mock transport）覆盖 discard、过期预览、拖拽提交，以及撤销整板、从已保存分析加入、无板时创建、预览/保存 409 后重读；不是浏览器 E2E。默认查询入口不带资产能力。

## 提交内容与历史审计

Excel SSOT 的提交入口使用 `--staged`：从 Git index 读取变更 view 文件全文，工作树中未暂存的修复不能掩盖错误；新增/重命名文件同样校验四条规则。无参数命令仍全量扫描 views。`--only-new` 为 `--staged` 的兼容别名，原先该参数仅打印文案但没有筛选。

2026-09-06 全仓审计仍报 32 条历史违规，结果留在 `.context/checks/closeout-excel-lint.log`。这些未触及页面的字段语义须另做专项核验；本次不改倍率、不把全仓审计记成通过。暂存区正反例覆盖四条规则、未暂存修复、历史文件、重命名与 Git 读取失败。

## 测试环境与排除的归属

- 日常 runner 使用私有临时 HOME/TMP、白名单环境、禁用 dotenv；清除父 hook 的 Git 定位变量和调用方密码/API key/pytest 参数。不连接调用方配置的 DuckDB。
- conftest 在收集前把业务库和缓存库指向本会话临时路径，不自动探测归档；真实库路径只能由明确授权的 `FQ_TEST_ARCHIVE_DB` 验收配置选择。日常 runner 不透传它。
- 认证 fixture 缓存每个 Python 进程的合成 cost-12 哈希，仅恢复可变状态；密码加载、强度和安全行为的专用测试保留真实 bcrypt。纯逻辑测试不会为 autouse fixture 导入应用或 ETL。
- 清理测试显式引用 tracker fixture，构造函数默认值、日志、marker 全部隔离。会话退出只回收自己创建的临时目录，不遍历或删除其他 pytest 会话。
- 默认串行，每 25 个测试文件开新进程；单组 RSS 上限 6 GB、时间上限 900 秒，超过上限以 90/91 退出并只停止自己创建的进程树。可以通过明确 CLI 参数调整，不自动并行。
- `not slow` 与七条 C 类排除仍由既有 `scripts/ci/pytest_c_class_deselects.txt` 统一。PR/nightly/weekly 均使用此日常 profile；慢测、归档数据、宿主安装状态、原生服务与真实设备验收不在其中，不能声称已由 CI 全部覆盖。
- 仅有分进程通过不足以证明跨模块状态隔离；公共 fixture/环境变动另做同进程的混合与反序回归。

## 自动入口与副作用清单

| 入口 | 触发/调用 | 写入或网络 | 当前阻断规则 |
|---|---|---|---|
| Git pre-commit | 暂存路径 → 对应检查器 | 只读差异/源码；历史大临时文件只告警 | 失败阻断，CHANGELOG 默认提示 |
| Git commit-msg | message → commit_msg_check | 只读提交描述/差异 | 非零阻断 |
| Git pre-push | refs → run_checks → LFS | 检查写本次产物；授权 push 时 LFS 使用 remote | 任一非零阻断，无自动复用 |
| Git post-merge | main/master → audit/hint | 追加本工作树审计日志 | 记录 merge，不串联清理或发布 |
| Claude PreToolUse | 本仓配置的文件/命令规则 | 无业务数据写入 | 模式防护，不替代授权判断 |
| Claude PostToolUse | 编辑 Python → 文件 Ruff | 本地静态检查 | 提示型，不替代 commit/push 门禁 |
| PR CI | 共用路径计划 → 各 job | CI 临时依赖、产物；按依赖/部署维度访问注册表或启动微型容器 | 启用 job 保持硬门禁，不 continue-on-error |
| Nightly/Weekly | 既有定时/手动 → bounded runner | CI 临时环境与报告上传 | 失败非零；nightly ground-truth 仍为历史 warning 模式 |
| framework pre-commit | 仅手动选择 | 工具缓存/安装 | 不默认安装或叠加 |
| branch_cleanup | 默认只读预览；apply + exact local | 仅明确 apply 才删指定本地分支；无远端写入 | dirty/protected/current/unmerged/occupied 拒绝；无强删回退 |
| ETL/backup/launchd/start-stack | 独立运维入口 | 可涉及业务库、进程和守护 | 不由治理或普通验证触发，保留归档授权边界 |

全局 Claude 配置、主仓旧版 hooks、历史运维文件没有随成果工作树补丁自动更新。本表列出当前生效关系，不以历史文件存在推断其已安装运行。

## 证据与交付

每次 backend runner 创建新的 `.context/checks/<time>/`，记录解释器、HEAD、Python 检查源码摘要、完整目标与命令、每组退出码/耗时/峰值 RSS、JUnit 与最终结果；失败也保留。摘要是可审查证据，不是绕过检查的授权或自动缓存键。`summarize_checks.py` 汇总 JUnit 子 suite，避免过去从空根属性得到 None。

当前规则只在 AGENTS；当前产品任务状态在 B0 执行清单；日期报告是不可回写的历史证据。本次治理记录单列本地补丁、旧成绩和未运行项目。Git/远端 CI/真实业务验收分别交付，不能因为本地检查通过标记产品完成。
