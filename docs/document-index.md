# 芙清 CRM 客户分析系统 - 文档索引

> **最后更新**: 2026-06-07
> **状态**: v0.4.14.16 sprint 8 收口 (391+ passed / 12 skipped, main a6389c8)
> **文档策略**: 精简为核心 5 份 + 归档 44 份（详见下方说明）

---

## 核心文档（必读）

| 文档 | 说明 | 加载方式 |
|---|---|---|
| [CLAUDE.md](../CLAUDE.md) | **AI 行为规则**（自动加载） | 每次会话自动注入 |
| [README.md](../README.md) | **项目入口**（新人第一眼） | 首次阅读 |
| [CHANGELOG.md](../CHANGELOG.md) | **版本历史**（回溯问题时救命） | 按需查阅 |
| [reference.md](./reference.md) | **参考手册**（口径/教训/目录结构） | 按需查阅 |
| [feishu-architecture/00-system-overview.md](./feishu-architecture/00-system-overview.md) | **系统架构**（整体全貌） | 按需查阅 |

---

## 运维文档（部署/排障时查阅）

| 文档 | 说明 |
|---|---|
| [deploy-windows.md](./deploy-windows.md) | Windows Server 部署指南 |
| [feishu-architecture/07-faq.md](./feishu-architecture/07-faq.md) | Bug 修复记录和经验教训 |

---

## 验证报告（证明系统验证）

| 文档 | 说明 |
|---|---|
| [validation-reports/etl-3-runs-2026-06-07.md](./validation-reports/etl-3-runs-2026-06-07.md) | P0-1 痛点 1 跑批 3 次验证（13.4 min 平均） |
| [validation-reports/w4-full-t7-2026-06-06.md](./validation-reports/w4-full-t7-2026-06-06.md) | W4 T-7 真跑验证（4/4 PASSED） |
| [validation-reports/sprint7-p2-duckdb-upgrade-2026-06-07.md](./validation-reports/sprint7-p2-duckdb-upgrade-2026-06-07.md) | Sprint 7 P2 DuckDB 升级验证 |

---

## 归档文档（历史参考）

> 完成任务后移入 `archive/`，不删除但不再维护。

| 目录 | 说明 | 文档数 |
|---|---|---|
| [archive/backend/](./archive/backend/) | 后端设计文档 | 6 |
| [archive/frontend/](./archive/frontend/) | 前端设计文档 | 1 |
| [archive/product/](./archive/product/) | 产品需求文档 | 1 |
| [archive/operations/](./archive/operations/) | 运维文档 | 1 |
| [archive/business-knowledge/](./archive/business-knowledge/) | 业务知识 | 4 |
| [archive/design/](./archive/design/) | 架构设计文档 | 1 |
| [archive/dmp-poc/](./archive/dmp-poc/) | 达摩盘 POC | 1 |
| [archive/618-breakdown/](./archive/618-breakdown/) | 618 大促资产 | 3 |
| [archive/feishu-architecture/](./archive/feishu-architecture/) | 详细架构文档 | 6 |
| [archive/sprints/](./archive/sprints/) | Sprint 收口记录 | 2 |
| [archive/refactor/](./archive/refactor/) | 重构文档 | 8 |
| [archive/plans/](./archive/plans/) | 历史计划 | 2 |
| [archive/reports/](./archive/reports/) | 历史报告 | 1 |
| [archive/validation-reports/](./archive/validation-reports/) | 历史验证报告 | 0 |

---

## 文档策略说明

### 为什么精简？

**问题**：49 个文档难以维护，容易过时，价值递减。

**方案**：保留 5 个核心文档 + 归档 44 个历史文档。

**效果**：
- 维护成本：从 49 个降到 5 个（-90%）
- 知识保留：archive/ 保留所有历史
- 聚焦价值：核心文档始终最新

### 维护规则

| 文档 | 更新频率 | 触发条件 |
|---|---|---|
| `CLAUDE.md` | 每次 sprint | 版本号/测试数字变更 |
| `CHANGELOG.md` | 每次 commit | 代码变更 |
| `reference.md` | 按需 | 发现新教训/口径变更 |
| `README.md` | 按需 | 重大架构变更 |
| `feishu-architecture/` | 按需 | 架构变更 |
| `archive/` | 不更新 | 完成任务后移入 |

### 何时归档？

**移入 archive/ 的条件**：
- ✅ 任务已完成（如 Sprint 收口）
- ✅ 功能已上线（如 PRD v3.0）
- ✅ 设计已落地（如架构文档）
- ✅ 知识已沉淀（如业务知识）

**不归档的条件**：
- ❌ 仍在使用（如 CLAUDE.md）
- ❌ 经常查阅（如 reference.md）
- ❌ 证明验证（如 validation-reports/）

---

## 快速导航

| 我想了解... | 看这里 |
|---|---|
| AI 行为规则 | [CLAUDE.md](../CLAUDE.md) ← **自动加载** |
| 项目是什么 | [README.md](../README.md) |
| 口径/教训 | [reference.md](./reference.md) |
| 系统架构 | [feishu-architecture/00-system-overview.md](./feishu-architecture/00-system-overview.md) |
| Bug 修复记录 | [feishu-architecture/07-faq.md](./feishu-architecture/07-faq.md) |
| 部署指南 | [deploy-windows.md](./deploy-windows.md) |
| 版本历史 | [CHANGELOG.md](../CHANGELOG.md) |
| 验证报告 | [validation-reports/](./validation-reports/) |
| 历史文档 | [archive/](./archive/) |

---

*此文件由 AI 维护，最后更新：2026-06-07*
