# 芙清 CRM 客户分析系统 - 文档索引

> **最后更新**: 2026-06-07
> **状态**: v0.4.14.16 sprint 8 收口 (391+ passed / 12 skipped, main a6389c8). Sprint 8: P0 前端 2 bug + P1 删 16 root test ignore. CI 三连绿.

---

## 快速导航

| 我想了解... | 看这里 |
|---|---|
| AI 行为规则（自动加载） | [CLAUDE.md](../CLAUDE.md) ← **每次会话自动注入** |
| 参考手册（口径/教训/目录结构） | [reference.md](./reference.md) ← **按需读取** |
| 系统整体架构 | [feishu-architecture/00-system-overview.md](./feishu-architecture/00-system-overview.md) |
| 每个文件做什么 | [backend/data-source-map.md](./backend/data-source-map.md) |
| 项目是什么、解决什么问题 | [product/prd-v3.0.md](./product/prd-v3.0.md) |
| 当前 Bug 和修复记录 | [feishu-architecture/07-faq.md](./feishu-architecture/07-faq.md) |
| 语义层设计规范 | [backend/semantic/](./backend/semantic/) |
| 前端契约指南 | [frontend/frontend-contract-guide.md](./frontend/frontend-contract-guide.md) |
| 618大促拆解资产 | [618-breakdown/](./618-breakdown/) |
| CRM业务知识 | [business-knowledge/](./business-knowledge/) |
| Windows Server 部署 | [deploy-windows.md](./deploy-windows.md) |
| 历史文档归档 | [archive/](./archive/) |
| **Sprint 8 收口** (2026-06-07) | [archive/sprints/](./archive/sprints/) ← P0 前端 2 bug + P1 删 16 root test ignore |
| **痛点 1 跑批验证** (2026-06-07) | [validation-reports/etl-3-runs-2026-06-07.md](./validation-reports/etl-3-runs-2026-06-07.md) ← 3 次 13.4 min 平均 |
| **达摩盘 POC** | [dmp-poc/dmp-api-evaluation-v1.0.md](./dmp-poc/dmp-api-evaluation-v1.0.md) |

---

## 文档分类

### 📋 核心文档
| 文件 | 状态 | 说明 |
|---|---|---|
| [reference.md](./reference.md) | ✅ **参考手册** | 口径表/历史教训/包拆分清单/目录结构（按需读取） |
| [product/prd-v3.0.md](./product/prd-v3.0.md) | ✅ **当前版本** | v3.0 PRD，包含架构与演进路线 |
| [deploy-windows.md](./deploy-windows.md) | ✅ 当前 | Windows Server 部署指南 |

### 🏗️ 架构设计
| 文件 | 状态 | 说明 |
|---|---|---|
| [feishu-architecture/](./feishu-architecture/) | ✅ **主要架构文档** | 7 份完整架构文档 |
| [design/etl-phase4-architecture.md](./design/etl-phase4-architecture.md) | ✅ 当前 | ETL Phase 4 架构设计 |
| [archive/architecture.md](./archive/architecture.md) | 📦 历史版本 | v1.0 初始技术架构 |

### 🔧 后端设计
| 文件 | 状态 | 说明 |
|---|---|---|
| [backend/semantic/](./backend/semantic/) | ✅ 当前 | 语义层设计（指标/分群/渠道） |
| [backend/features/](./backend/features/) | ✅ 当前 | 功能模块设计（RFM 下钻等） |
| [backend/data-source-map.md](./backend/data-source-map.md) | ✅ 当前 | 数据源映射 |

### 🎨 前端设计
| 文件 | 状态 | 说明 |
|---|---|---|
| [frontend/frontend-contract-guide.md](./frontend/frontend-contract-guide.md) | ✅ 当前 | 前后端契约指南 |

### 🎯 大促资产
| 文件 | 状态 | 说明 |
|---|---|---|
| [618-breakdown/](./618-breakdown/) | ✅ 资产 | 618 大促拆解文档 |

### 📚 业务知识
| 文件 | 状态 | 说明 |
|---|---|---|
| [business-knowledge/](./business-knowledge/) | ✅ 参考 | CRM 赛道知识萃取 |

### 🔍 探索/POC
| 文件 | 状态 | 说明 |
|---|---|---|
| [dmp-poc/dmp-api-evaluation-v1.0.md](./dmp-poc/dmp-api-evaluation-v1.0.md) | ✅ POC | 达摩盘官方 API 评估报告 |

### 🚀 Sprint 收口记录
| 文件 | 状态 | 说明 |
|---|---|---|
| [archive/sprints/sprint-3-plan.md](./archive/sprints/sprint-3-plan.md) | 📦 已完成 | Sprint 3: 4/5 done + 痛点 1 闭环 |
| [archive/sprints/sprint-4-plan.md](./archive/sprints/sprint-4-plan.md) | 📦 已完成 | Sprint 4: 2/2 P0 done (DuckDB 备份 + dedup) |
| Sprint 5 | 📦 已完成 | P0-3 排查 + NOT EXISTS hotfix 3 (d9165bb) |
| Sprint 6 | 📦 已完成 | 5→6 层防护 + W7 pytest 修复 + D-6 版本同步 |
| Sprint 7 | 📦 已完成 | P0 治根 10 root test + P2 DuckDB 测试 |
| Sprint 8 | 📦 已完成 | P0 前端 2 bug (YOYBadge + R 桶) + P1 删 16 root test ignore |

### 📊 验证报告
| 文件 | 状态 | 说明 |
|---|---|---|
| [validation-reports/etl-3-runs-2026-06-07.md](./validation-reports/etl-3-runs-2026-06-07.md) | ✅ 闭环 | P0-1 痛点 1 跑批 3 次验证（W1 GROUPING SETS 平均 13.4 min） |
| [validation-reports/w4-full-t7-2026-06-06.md](./validation-reports/w4-full-t7-2026-06-06.md) | ✅ 闭环 | sprint 2 痛点 3 T-7 真跑 4/4 PASSED |
| [validation-reports/sprint7-p2-duckdb-upgrade-2026-06-07.md](./validation-reports/sprint7-p2-duckdb-upgrade-2026-06-07.md) | ✅ 闭环 | Sprint 7 P2 DuckDB 升级验证 |

### 🛠️ 运维
| 文件 | 状态 | 说明 |
|---|---|---|
| [operations/cleanup.md](./operations/cleanup.md) | ✅ 当前 | 清理操作指南 |

### 📦 归档文档
| 目录 | 说明 |
|---|---|
| [archive/sprints/](./archive/sprints/) | Sprint 3/4 收口记录 |
| [archive/refactor/](./archive/refactor/) | Phase 0-7 重构文档 |
| [archive/](./archive/) | 历史文档、过期设计 |

---

## 文档维护纪律
- **PRD**: 只维护最新版（v3.0），旧版移入 archive
- **架构文档**: 以 `feishu-architecture/` 为准
- **功能设计**: 上线后保留设计文档作为参考，不删除
- **AI 协作规范**: 统一由 CLAUDE.md 维护，不再单独维护 ai/DESIGN.md
- **部署文档**: 启动命令统一由 CLAUDE.md 维护，Docker 配置见 archive/deploy.md
- **文档精简**: 2026-05-30 归档已完成计划（etl-incremental-fix-plan、repair-plan）和冗余文档（design.md、deploy.md、module-index.md）
- **命名规范**: 全英文 kebab-case，中文内容保留在正文，日期用 YYYY-MM-DD
