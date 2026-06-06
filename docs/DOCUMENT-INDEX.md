# 芙清 CRM 客户分析系统 - 文档索引

> **最后更新**: 2026-06-06
> **状态**: v0.4.10 已 release (W2/W3/W4 + CI 6 件套)

---

## 快速导航

| 我想了解... | 看这里 |
|---|---|
| AI 行为规则（自动加载） | [CLAUDE.md](../CLAUDE.md) ← **每次会话自动注入** |
| 参考手册（口径/教训/目录结构） | [reference.md](./reference.md) ← **按需读取** |
| 系统整体架构 | [飞书版架构文档/00-系统总览.md](./飞书版架构文档/00-系统总览.md) |
| 每个文件做什么 | [backend/DATA-SOURCE-MAP.md](./backend/DATA-SOURCE-MAP.md) |
| 项目是什么、解决什么问题 | [product/PRD-v3.0.md](./product/PRD-v3.0.md) |
| 当前 Bug 和修复记录 | [飞书版架构文档/07-常见问题汇总.md](./飞书版架构文档/07-常见问题汇总.md) |
| 语义层设计规范 | [backend/semantic/](./backend/semantic/) |
| 前端契约指南 | [frontend/frontend-contract-guide.md](./frontend/frontend-contract-guide.md) |
| 618大促拆解资产 | [618-breakdown/](./618-breakdown/) |
| CRM业务知识 | [业务知识/](./业务知识/) |
| Windows Server 部署 | [DEPLOY-WINDOWS.md](./DEPLOY-WINDOWS.md) |
| 历史文档归档 | [archive/](./archive/) |

---

## 文档分类

### 📋 核心文档
| 文件 | 状态 | 说明 |
|---|---|---|
| [reference.md](./reference.md) | ✅ **参考手册** | 口径表/历史教训/包拆分清单/目录结构（按需读取） |
| [product/PRD-v3.0.md](./product/PRD-v3.0.md) | ✅ **当前版本** | v3.0 PRD，包含架构与演进路线 |
| [DEPLOY-WINDOWS.md](./DEPLOY-WINDOWS.md) | ✅ 当前 | Windows Server 部署指南 |

### 🏗️ 架构设计
| 文件 | 状态 | 说明 |
|---|---|---|
| [飞书版架构文档/](./飞书版架构文档/) | ✅ **主要架构文档** | 7 份完整架构文档 |
| [archive/architecture.md](./archive/architecture.md) | 📦 历史版本 | v1.0 初始技术架构 |

### 🔧 后端设计
| 文件 | 状态 | 说明 |
|---|---|---|
| [backend/semantic/](./backend/semantic/) | ✅ 当前 | 语义层设计（指标/分群/渠道） |
| [backend/features/](./backend/features/) | ✅ 当前 | 功能模块设计（RFM 下钻等） |
| [backend/DATA-SOURCE-MAP.md](./backend/DATA-SOURCE-MAP.md) | ✅ 当前 | 数据源映射 |

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
| [业务知识/](./业务知识/) | ✅ 参考 | CRM 赛道知识萃取 |

### 🤝 运维 / Handoff
| 文件 | 状态 | 说明 |
|---|---|---|
| [handoff-2026-06-05.md](./handoff-2026-06-05.md) | ✅ 当前 | 2026-06-05 运维交接文档（disk/重启/数据回灌 SOP） |
| [handoff-2026-06-05-errata.md](./handoff-2026-06-05-errata.md) | 🩹 勘误 | 2026-06-05 handoff 勘误（10 项失真补全，§3.1 4 层 ↔ 17 issues 映射表） |

### 📦 归档文档
| 目录 | 说明 |
|---|---|
| [archive/refactor/](./archive/refactor/) | Phase 0-7 重构文档 |
| [archive/](./archive/) | 历史文档、过期设计 |

---

## 文档维护纪律
- **PRD**: 只维护最新版（v3.0），旧版移入 archive
- **架构文档**: 以 `飞书版架构文档/` 为准
- **功能设计**: 上线后保留设计文档作为参考，不删除
- **AI 协作规范**: 统一由 CLAUDE.md 维护，不再单独维护 ai/DESIGN.md
- **部署文档**: 启动命令统一由 CLAUDE.md 维护，Docker 配置见 archive/DEPLOY.md
- **文档精简**: 2026-05-30 归档已完成计划（etl-incremental-fix-plan、REPAIR_PLAN）和冗余文档（DESIGN.md、DEPLOY.md、MODULE-INDEX.md）
