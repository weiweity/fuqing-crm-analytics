# 芙清 CRM 客户分析系统 - 文档索引

> **最后更新**: 2026-05-29
> **状态**: 代码审计完成，大文件拆分完成，文档重组完成

---

## 快速导航

| 我想了解... | 看这里 |
|---|---|
| 系统整体架构 | [飞书版架构文档/00-系统总览.md](./飞书版架构文档/00-系统总览.md) ← **入口** |
| AI 改代码的操作规范 | [ai/DESIGN.md](./ai/DESIGN.md) |
| 每个文件做什么 | [MODULE-INDEX.md](./MODULE-INDEX.md) |
| 数据源在哪、删了影响什么 | [backend/DATA-SOURCE-MAP.md](./backend/DATA-SOURCE-MAP.md) |
| 如何部署 | [deploy/DEPLOY.md](./deploy/DEPLOY.md) |
| 项目是什么、解决什么问题 | [product/PRD-v3.0.md](./product/PRD-v3.0.md) |
| 当前 Bug 和修复记录 | [飞书版架构文档/07-常见问题汇总.md](./飞书版架构文档/07-常见问题汇总.md) |
| 语义层设计规范 | [backend/semantic/](./backend/semantic/) |
| 前端契约指南 | [frontend/frontend-contract-guide.md](./frontend/frontend-contract-guide.md) |
| 618大促拆解资产 | [campaigns/618-breakdown/](./campaigns/618-breakdown/) |
| CRM业务知识 | [business/业务知识/](./business/业务知识/) |
| 历史文档归档 | [archive/](./archive/) |

---

## 文档分类

### 📋 产品与需求
| 文件 | 状态 | 说明 |
|---|---|---|
| [product/PRD-v3.0.md](./product/PRD-v3.0.md) | ✅ **当前版本** | v3.0 PRD，包含架构与演进路线 |

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

### 🚀 部署运维
| 文件 | 状态 | 说明 |
|---|---|---|
| [deploy/DEPLOY.md](./deploy/DEPLOY.md) | ✅ 当前 | 部署文档 |

### 🤖 AI 协作
| 文件 | 状态 | 说明 |
|---|---|---|
| [ai/DESIGN.md](./ai/DESIGN.md) | ✅ 当前 | AI 改代码操作规范 |

### 🎯 大促资产
| 文件 | 状态 | 说明 |
|---|---|---|
| [campaigns/618-breakdown/](./campaigns/618-breakdown/) | ✅ 资产 | 618 大促拆解文档 |

### 📚 业务知识
| 文件 | 状态 | 说明 |
|---|---|---|
| [business/业务知识/](./business/业务知识/) | ✅ 参考 | CRM 赛道知识萃取 |

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
- **文档重组**: 2026-05-28 按 backend/frontend/deploy/ai/product 归类
