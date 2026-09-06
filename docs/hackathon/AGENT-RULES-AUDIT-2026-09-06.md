# Agent 规则统一与项目盘查

日期：2026-09-06。范围：当前 `hackathon-mission-mvp` 工作树，分支 `codex/architecture-warehouse-plan-closeout`。这是规则/工具入口修订与结构性盘查，不是业务功能、全仓死代码、模型 API 或安全全面验收。

## 结果

唯一维护的行为正文为根 [AGENTS.md](../../AGENTS.md)（61 行）；原 408 行 CLAUDE 规则已蒸馏，`CLAUDE.md` 仅保留 `@AGENTS.md`。保留此兼容文件是为 Claude 读取同一正文，不维护第二套规则。该方式符合 [Claude 官方 AGENTS 兼容说明](https://code.claude.com/docs/en/memory#agentsmd)。

AGENTS.md 已取消 Git 忽略；本轮尚未 stage/commit/push，因而是可纳入版本控制的本地修改，尚未成为其他机器能获取的远端版本。

| 旧来源/问题 | 当前处理 |
|---|---|
| CLAUDE 固定旧模型分工、本地即生产、自动 stash/ETL/发布、多轮 review | 正文蒸馏到 AGENTS；保留任务授权、实际证据、分级验证、数据/技术边界，删除默认流程串联 |
| `scripts/sync-agents.sh` 覆盖生成 AGENTS | 改为只读检查；缺文件或兼容入口不符时失败，绝不覆盖用户正文 |
| README、PR 模板和 CI 仍指向旧源 | 当前入口改指 AGENTS；模板移除“12 步全跑/重生 AGENTS”；CI 加入口检查及对应路径触发 |
| Claude 推送后自动清理分支、会话起止与关键词扫描 | 从项目 hooks 移除；保留 PreToolUse 模式保护及 PostToolUse 单文件 lint/契约提醒 |
| Git pre-commit 自动恢复配置，误把相对路径当异常 | 接受正确的相对/绝对路径；异常时说明并停止对应提交，不写 Git 配置 |
| 两个危险根路径命令漏拦截 | 修正原模式边界，实际配置命令的输入测试验证拒绝；不是完整命令沙箱的声明 |
| `regen-types` 自动启动旧 CRM、复制类型及附带发布 | 区分 B0 离线生成器和旧 CRM；只处理受影响契约，禁止用真实配置或默认起服务绕过 |
| `ship-pr` 绕 hooks、附带删分支/重启 | 改为实际授权内的 PR 流程；移除默认绕过和附带动作 |
| 旧 hook 测试复制实现、验证自动清理、修改自己的源码测试 lint | 改为读取真实配置，在隔离目录执行命令，使用无害替身检测隐式动作；不自改源码 |
| L4/operating 多份“优先/永久/默认流程” | 加适用性声明、更新当前入口；保留历史证据和有效技术合同，不批量篡改历史结论 |

当前采用 [GPT-6 Astra 官方提示指南](https://developers.openai.com/api/docs/guides/latest-model#prompting-best-practices)中的授权内持续执行、减少矛盾指令、简洁表达和按影响验证原则。按项目偏好保留按需委派及 Git/数据授权，不照搬官方示例扩大权限。未切换任何业务 provider、模型默认值或 API 协议，也没有付费模型调用。

## 保留的技术与架构依据

- DSH/Hermes/StaffDeck 上游独立、业务扩展隔离、版本锁定、候选环境验证、状态迁移与回退核验。
- 语义/服务/契约分层、参数化 SQL、字段实际证据、B0/旧 CRM 契约区分、ratio 展示责任、连接 owner 与跨连接持久化验证。
- DESIGN 的原品牌/UI 约束、只读真实资产与合成演示边界、按需 CodeGraph 及失败回退、跨平台 subprocess/cwd 规则。
- commit 前 review、merge 前 QA、实际 hooks/CI 门仍在，仅阻塞对应已授权动作；普通本地编辑不强制完成发布。

## 项目盘查及未删除候选

本轮清点 730 个 Git 跟踪路径的结构、当前规则入口、显式引用的 Skill/hook/同步脚本及操作文档；不逐文件做业务死代码分析，也不以“无文本引用”判定动态工具或脚本无用。未读取真实库、凭据或会话内容；构建/运行目录只查看目录名和磁盘占用。

| 对象 | 证据与处理 |
|---|---|
| `.context/dsh-b0/upstream` | 约 1.62 GiB，固定上游源码与依赖，当前构建需要；保留，不因体积大当冗余 |
| `frontend-vue3/node_modules` / 插件 build-tools 依赖 | 约 428 / 44 MiB，可重装依赖但仍用于本地验证；本轮不清理 |
| 13 个 `clean-build-*` | 合计 4,172 KiB；部分有报告引用，列去重候选，先辨别证据关联再单独授权清理 |
| 19 个 `runtime-*` | 合计 21,484 KiB；包含成功和失败验证历史，不因当前已停止就删除 |
| `.claude/skills/ad-hoc-query/SKILL.md` | 指向仓库外已不存在目标的绝对软链；未修复、未删除、未安装全局替代。若后续需要此 Skill，先决定仓库内可移植实现或正式来源 |
| `session_start_check.py` / `session_close_check.py` / `check_remaining_tasks.py` | 已不由项目 hooks 自动调用；保留为待专项整理的旧维护工具，不建议直接运行以恢复旧流程 |
| `branch_cleanup.py` / `post_push_restart_uvicorn_verify.sh` / launchd 模板 | 历史运维用途，不等于无用；当前规则不允许因提交/推送自动执行，不删除或安装 |
| 历史 docs、旧 CRM/Vue、品牌/锁文件、合成样例 | 各有历史、兼容或验证用途；保留，未把新 DSH 工作台方向解释成删除旧系统许可 |

`fuqing-crm-analytics` 原归档 checkout、全局 Claude/Codex 规则、第三方上游规则及其他项目不在本轮修改范围；它们可能仍有旧规则，不宣称全机统一。包级 AGENTS 的归档边界仍生效，当前仓库不再要求加载兄弟 checkout 的旧流程。

## 验证与限制

- 针对实际 hooks 和只读规则入口共 **40 PASS**，使用 `pytest --noconftest`，不导入旧 CRM 全局 fixture、不触碰业务库。覆盖正常/保护路径、两个根路径拒绝、单文件 lint、无隐式维护、入口错误不覆盖，以及 pre-commit 不写 Git 配置。
- 最初实测发现 6 个旧配置问题（2 个拒绝缺口、4 类自动维护）；另有 2 个测试夹具换行错误，已单独修正。最终没有靠跳过失败用例变绿。
- 改动 Python 文件 Ruff 通过；shell 语法、真实仓库只读入口、文档链接与 diff 检查通过。CI 配置只做本地静态核验，远端 CI 未运行。
- Skill Creator 通用校验器不支持 Claude 的 `disable-model-invocation` 字段，两个原格式均报告此项；保留 regen-types 的自动选择和 ship-pr 的显式调用策略，另做 YAML/内容/引用检查。不冒充 Codex 自动发现或 Claude GUI 端到端调用验收。
- 旧说明正文被合并/替换，但没有删除数据库、业务文件或验证目录；原跟踪内容可从 Git 历史/本轮 diff 查回。未提交、推送、部署、启动服务或修改真实 Git 配置。
