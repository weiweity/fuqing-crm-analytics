# 芙清 CRM 客户分析系统 - 文档索引

> **最后更新**: 2026-05-27
> **状态**: Phase 0-6 重构完成，文档体系已建立

---

## 快速导航

| 我想了解... | 看这里 |
|---|---|
| 系统整体架构 | [ARCHITECTURE.md](./ARCHITECTURE.md) ← **入口** |
| AI 改代码的操作规范 | [DESIGN.md](./DESIGN.md) |
| 每个文件做什么 | [MODULE-INDEX.md](./MODULE-INDEX.md) |
| 数据源在哪、删了影响什么 | [DATA-SOURCE-MAP.md](./DATA-SOURCE-MAP.md) |
| 如何部署 | [DEPLOY.md](./DEPLOY.md) |
| 项目是什么、解决什么问题 | [PRD-v3.0.md](./PRD-v3.0.md) |
| 飞书版详细架构 | [飞书版架构文档/00-系统总览.md](./飞书版架构文档/00-系统总览.md) |
| AI 协作约束 | [ai-constraints.md](./ai-constraints.md) |
| 数据库和技术选型 | [architecture.md](./architecture.md) |
| 当前 Bug 和修复记录 | [飞书版架构文档/07-常见问题汇总.md](./飞书版架构文档/07-常见问题汇总.md) |
| 语义层设计规范 | [semantic/](./semantic/) |
| 老客健康分析仪表盘设计 | [design_customer_health_dashboard.md](./design_customer_health_dashboard.md) |
| RFM 模型口径修复方案 | [RFM_FIX_PLAN.md](./RFM_FIX_PLAN.md) |
| 人群漏斗设计计划 | [../../PLAN-crowd-funnel.md](../../PLAN-crowd-funnel.md) |
| 618大促拆解资产（复用模板） | [618-breakdown/](./618-breakdown/) |
| CRM业务知识和赛道认知 | [业务知识/](./业务知识/) |
| 品类看板v2设计评审 | [category-dashboard-v2-design-review.md](./category-dashboard-v2-design-review.md) |
| 历史周报和旧版文档 | [archive/](./archive/) |

---

## 文档分类

### 📋 产品与需求
| 文件 | 状态 | 说明 |
|---|---|---|
| [PRD-v3.0.md](./PRD-v3.0.md) | ✅ **当前版本** | v3.0 PRD，包含架构与演进路线 |
| [PRD-v2.0.md](./PRD-v2.0.md) | 📦 归档参考 | v2.0 PRD，新增口径统一需求 |
| [PRD.md](./PRD.md) | 📦 历史版本 | v1.0 初始 PRD |
| [implementation-plan.md](./implementation-plan.md) | 📦 历史参考 | Week 1-5 实现计划（已大幅超出） |

### 🏗️ 架构设计
| 文件 | 状态 | 说明 |
|---|---|---|
| [飞书版架构文档/](./飞书版架构文档/) | ✅ **主要架构文档** | 7 份完整架构文档（总览→数据→语义→契约→服务→前端→运维→问题汇总） |
| [architecture.md](./architecture.md) | 📦 历史版本 | v1.0 初始技术架构 |
| [architecture-dashboard.md](./architecture-dashboard.md) | 📦 参考 | 架构看板设计文档 |
| [review_eng_design.md](./review_eng_design.md) | 📦 参考 | 工程设计评审记录 |
| [plan-vue3-frontend-architecture.md](./plan-vue3-frontend-architecture.md) | 📦 参考 | Vue3 前端架构计划 |

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
| [design_customer_health_dashboard.md](./design_customer_health_dashboard.md) | ✅ 已上线 | 老客健康分析仪表盘设计（5 Tab） |
| [RFM_FIX_PLAN.md](./RFM_FIX_PLAN.md) | ✅ 已修复 | RFM 模型口径统一修复方案 |
| [rfm-business-design.md](./rfm-business-design.md) | 📦 历史参考 | RFM 业务设计 |
| [rfm-user-guide.md](./rfm-user-guide.md) | 📦 历史参考 | RFM 用户指南 |

### 🔄 迁移与重构
| 文件 | 状态 | 说明 |
|---|---|---|
| [MIGRATION-CHECKLIST.md](./MIGRATION-CHECKLIST.md) | ⏳ 进行中 | 口径统一重构迁移清单 |
| [frontend-contract-guide.md](./frontend-contract-guide.md) | ✅ 当前 | 前后端契约指南 |
| [QA-v3.0-architecture-2026-04-16.md](./QA-v3.0-architecture-2026-04-16.md) | 📦 参考 | v3.0 架构 QA 报告 |

### 📝 AI 协作规范
| 文件 | 状态 | 说明 |
|---|---|---|
| [ai-constraints.md](./ai-constraints.md) | ✅ 当前 | AI 行为约束文档 |

### 📊 设计评审与 Review
| 文件 | 状态 | 说明 |
|---|---|---|
| [category-dashboard-v2-design-review.md](./category-dashboard-v2-design-review.md) | ✅ 已上线 | 品类看板v2 设计评审 |
| [PLAN-crowd-funnel.md](./PLAN-crowd-funnel.md) | ✅ 已上线 | 人群漏斗设计计划 |

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
| [archive/](./archive/) | 历史周报、旧版 HTML 原型、Week 1-5 过程文档 |
| [archive/week1-4/week1/](./archive/week1-4/week1/) | Week 1 设计文档（API 契约、前端设计、RFM PRD） |
| [archive/week1-4/week3/](./archive/week1-4/week3/) | Week 3 技术计划（SQL 规范、技术草案） |
| [archive/week1-4/week4/](./archive/week1-4/week4/) | Week 4 需求与 API 契约 |
| [archive/week1-4/week5/](./archive/week1-4/week5/) | Week 5 交接文档 |
| [archive/week1-4/飞书版架构文档/](./archive/week1-4/飞书版架构文档/) | 早期飞书架构草稿（已被 docs/飞书版架构文档/ 替代） |
| [临时脚本/](./临时脚本/) | 临时调试脚本（可定期清理） |

---

## 文档整理说明

### 本次整理做了什么
1. **根目录清理**: `_null_check*.py` 临时调试脚本移到 `docs/临时脚本/`
2. **建立索引**: 创建本文档（`DOCUMENT-INDEX.md`），为所有文档分类导航
3. **版本标注**: 区分"当前版本"、"历史参考"、"归档"三级状态
4. **去重标记**: `archive/` 下的飞书版架构文档为早期草稿，已被 `docs/飞书版架构文档/` 替代

### 建议清理
- `docs/临时脚本/` 下的 `_null_check*.py` 如无用处可删除
- `docs/archive/week1-4/飞书版架构文档/` 已被替代，可删除
- `docs/archive/week1-4/` 下空目录（week2）可删除
- `docs/semantic/` 下的 `.DS_Store` 可删除

### 文档维护纪律
- **PRD**: 只维护最新版（v3.0），旧版移入 archive
- **架构文档**: 以 `飞书版架构文档/` 为准
- **功能设计**: 上线后保留设计文档作为参考，不删除
- **迁移清单**: 完成一项勾选一项，完成后归档
