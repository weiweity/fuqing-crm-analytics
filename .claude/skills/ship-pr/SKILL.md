---
name: ship-pr
description: 在用户要求 PR 或 Git 交付时核对目标、变更和检查，执行已授权的 commit、push、PR 或 merge；普通本地修改不触发发布。
disable-model-invocation: true
---

# ship-pr

以仓库根 [AGENTS.md](../../../AGENTS.md) 为唯一行为规则。此 Skill 只补充 PR 交付的上下文，不能赋予额外 Git、部署或清理权限。

- 核对当前分支、dirty 状态、目标 base 和已有 PR，保留用户改动；不先切 main、自动 pull/stash 或创建重复 PR。
- 明确当前已授权动作，完成不依赖额外批准的 diff、相关验证和 PR 草稿。commit 前 review、merge 前 QA 与现有 hooks/CI 按 AGENTS.md 执行，不将全部业务测试写成所有任务的前置。
- 提交和推送不使用跳过 hooks 的默认参数；失败先定位原因。冲突修复、rebase、强推或历史改写不由报错自动授权。
- 只有 PR 创建已获授权才调用创建接口；有 PR 则继续该 PR。CI 结论绑定实际提交，未运行不称全绿。
- merge 仅在明确授权且对应检查通过后执行，采用用户/项目约定的合并方式。合并不附带删分支、pull、重启服务、部署或发布；这些操作分别确认范围和既有授权。
- 最终报告实际做到哪个阶段、验证证据及余项；本地完成与 Git/运行发布分开。不要为制造完整流程记录而追加无意义提交。
