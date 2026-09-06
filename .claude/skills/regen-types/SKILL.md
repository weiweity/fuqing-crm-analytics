---
name: regen-types
description: 核对或生成当前仓库受影响的 OpenAPI 与 TypeScript 契约；先区分 B0 和旧 CRM，优先离线生成，不自动启动服务或提交。
disable-model-invocation: false
---

# regen-types

读取仓库根 [AGENTS.md](../../../AGENTS.md) 的授权与契约边界。只处理本次变化及其调用方，不把所有后端 schema 都复制成旧 Vue 类型。

## B0 analytics-run

当前入口是 `scripts/dsh-b0/run-kernel-contract.mjs`，使用已安装的 Node 24、Python 3.14+ 和锁定生成依赖。

- 仅检查时使用 `node scripts/dsh-b0/run-kernel-contract.mjs --check --python /已核验的绝对路径/python3.14`。
- 契约变更已授权时，检查生成目标后用同一入口 `--write`，随后 `--check`，核对 OpenAPI、生成声明和受影响调用方。
- 该入口离线运行，不连接业务库；缺依赖时先报告具体缺项，不自动安装最新版或换到旧 CRM 服务。

## 旧 CRM

先核对 Pydantic Schema、现有前端消费类型及项目生成器，保留字段语义和必要兼容类型；不要直接覆盖 `types.ts`。

优先使用已有离线 schema。若生成确实只能依赖运行服务，先说明具体原因和最小范围；已有明确启动授权才可使用隔离合成配置、loopback 和无冲突端口。不能读取真实配置、填入示例密码、绑定所有网卡或加载真实库来绕过阻碍。

按改动影响执行相关类型/契约检查；展示生成差异和未完成项。此流程结束于本地结果交付，Git、部署、服务启动及清理权限统一遵循 AGENTS.md。
