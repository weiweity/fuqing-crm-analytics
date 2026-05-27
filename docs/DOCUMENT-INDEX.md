# 芙清 CRM 客户分析系统 - 文档索引

> **最后更新**: 2026-05-27
> **状态**: Phase 0-7 重构完成，文档体系已建立，项目已清理

---

## 快速导航

| 我想了解... | 看这里 |
|---|---|
| 系统整体架构 | [飞书版架构文档/00-系统总览.md](./飞书版架构文档/00-系统总览.md) ← **入口** |
| AI 改代码的操作规范 | [DESIGN.md](./DESIGN.md) |
| 每个文件做什么 | [MODULE-INDEX.md](./MODULE-INDEX.md) |
| 数据源在哪、删了影响什么 | [DATA-SOURCE-MAP.md](./DATA-SOURCE-MAP.md) |
| 如何部署 | [DEPLOY.md](./DEPLOY.md) |
| 项目是什么、解决什么问题 | [PRD-v3.0.md](./PRD-v3.0.md) |
| AI 协作约束 | [ai-constraints.md](./ai-constraints.md) |
| 当前 Bug 和修复记录 | [飞书版架构文档/07-常见问题汇总.md](./飞书版架构文档/07-常见问题汇总.md) |
| 语义层设计规范 | [semantic/](./semantic/) |
| 618大促拆解资产（复用模板） | [618-breakdown/](./618-breakdown/) |
| CRM业务知识和赛道认知 | [业务知识/](./业务知识/) |
| 历史周报和旧版文档 | [archive/](./archive/) |
| 过期设计文档（归档） | [archive/refactor/](./archive/refactor/) |

---

## 文档分类

### 📋 产品与需求
| 文件 | 状态 | 说明 |
|---|---|---|
| [PRD-v3.0.md](./PRD-v3.0.md) | ✅ **当前版本** | v3.0 PRD，包含架构与演进路线 |

### 🏗️ 架构设计
| 文件 | 状态 | 说明 |
|---|---|---|
| [飞书版架构文档/](./飞书版架构文档/) | ✅ **主要架构文档** | 7 份完整架构文档（总览→数据→语义→契约→服务→前端→运维→问题汇总） |
| [archive/architecture.md](./archive/architecture.md) | 📦 历史版本 | v1.0 初始技术架构 |
| [archive/refactor/architecture-dashboard.md](./archive/refactor/architecture-dashboard.md) | 📦 参考 | 架构看板设计文档 |

### 🔧 语义层（核心设计）
| 文件 | 状态 | 说明 |
|---|---|---|
| [semantic/ARCHITECTURE-metrics-management.md](./semantic/ARCHITECTURE-metrics-management.md) | ✅ 当前 | 指标管理架构 |
| [semantic/METRICS-REGISTRY.md](./semantic/METRICS-REGISTRY.md) | ✅ 当前 | 指标注册表 |
| [semantic/PLAN-metrics-unification.md](./semantic/PLAN-metrics-unification.md) | ✅ 当前 | 指标统一计划 |
| [semantic/week2-segmentation-design.md](./semantic/week2-segmentation-design.md) | ✅ 当前 | 用户分群设计 |

### 🎯 功能模块设计
| 文件 | 状态 | 说明 |
|---|---|---|
| [features/rfm-segment-drilldown.md](./features/rfm-segment-drilldown.md) | ✅ 当前 | RFM 人群下钻功能设计 |
| [archive/refactor/](./archive/refactor/) | 📦 归档 | 已完成的功能设计文档 |

### 🔄 迁移与重构
| 文件 | 状态 | 说明 |
|---|---|---|
| [frontend-contract-guide.md](./frontend-contract-guide.md) | ✅ 当前 | 前后端契约指南 |
| [archive/refactor/](./archive/refactor/) | 📦 归档 | Phase 0-7 重构文档（已完成） |

### 📝 AI 协作规范
| 文件 | 状态 | 说明 |
|---|---|---|
| [ai-constraints.md](./ai-constraints.md) | ✅ 当前 | AI 行为约束文档 |

### 📊 设计评审与 Review
| 文件 | 状态 | 说明 |
|---|---|---|
| [archive/refactor/](./archive/refactor/) | 📦 归档 | 已完成的设计评审文档 |

### 🎯 大促拆解资产
| 文件 | 状态 | 说明 |
|---|---|---|
| [618-breakdown/](./618-breakdown/) | ✅ 资产 | 26年618大促拆解文档（HTML原型/风格截图/数据生成器/飞书参考/复刻指南） |

### 📚 业务知识
| 文件 | 状态 | 说明 |
|---|---|---|
| [业务知识/](./业务知识/) | ✅ 参考 | CRM赛道知识萃取、PPT、OCR识别文档 |
| [业务知识/CRM赛道知识萃取_AI版_深化.md](./业务知识/CRM赛道知识萃取_AI版_深化.md) | ✅ 主要参考 | AI深化版知识萃取（77 chunks） |

### 📦 归档文档
| 目录 | 说明 |
|---|---|
| [archive/refactor/](./archive/refactor/) | Phase 0-7 重构相关文档（REFACTOR-PLAN、MIGRATION-CHECKLIST 等） |
| [archive/](./archive/) | 历史周报、旧版 HTML 原型、Week 1-5 过程文档 |
| [archive/week1-4/week1/](./archive/week1-4/week1/) | Week 1 设计文档（API 契约、前端设计、RFM PRD） |
| [archive/week1-4/week3/](./archive/week1-4/week3/) | Week 3 技术计划（SQL 规范、技术草案） |
| [archive/week1-4/week4/](./archive/week1-4/week4/) | Week 4 需求与 API 契约 |
| [archive/week1-4/week5/](./archive/week1-4/week5/) | Week 5 交接文档 |

---

## 文档整理说明

### 本次整理做了什么（2026-05-27）
1. **删除废弃文件**: `gen_大促拆解模板.py`（不应在 docs 内）、`cross-review-auth-2026-05-07.md`（gstack 内部文档）
2. **归档旧架构文档**: `architecture.md` 移入 `archive/`
3. **删除重复草稿**: `archive/week1-4/飞书版架构文档/`（已被 `docs/飞书版架构文档/` 替代）
4. **修复死链**: 清理 DOCUMENT-INDEX.md 中引用不存在的文件（PRD-v2.0.md、PRD.md、implementation-plan.md、rfm-business-design.md、rfm-user-guide.md、review_eng_design.md 等）
5. **统一入口**: 快速导航中架构入口改为 `飞书版架构文档/00-系统总览.md`
6. **部署文档**: 拆分为 Mac 开发（DEPLOY.md）和 Windows 生产（windows-deploy-sop.md）两个入口

### 文档维护纪律
- **PRD**: 只维护最新版（v3.0），旧版不再记录
- **架构文档**: 以 `飞书版架构文档/` 为准
- **功能设计**: 上线后保留设计文档作为参考，不删除
- **迁移清单**: 完成一项勾选一项，完成后归档

### 文档维护纪律
- **PRD**: 只维护最新版（v3.0），旧版移入 archive
- **架构文档**: 以 `飞书版架构文档/` 为准
- **功能设计**: 上线后保留设计文档作为参考，不删除
- **迁移清单**: 完成一项勾选一项，完成后归档
