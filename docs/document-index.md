# 芙清 CRM 客户分析系统 - 文档索引

> **最后更新**: 2026-06-11
> **状态**: v0.4.14.43 sprint 17 收口 (3/3 P1 治理完成 #120+#121+#122, main 31db7ef, 26 YOY ratio 字段命名冲突留 Sprint 18)
> **文档策略**: 精简为核心 5 份 + 归档 44 份（详见下方说明）

---

## 当前 Sprint

| Sprint | 状态 | 文档 |
|--------|------|------|
| **Sprint 18** (26 YOY 命名冲突治根 + W5 cache invalidation hook + pre-commit lint + YOYGuard 通用化) | ✅ 收口 2026-06-11 | [SPRINT-18-RETROSPECTIVE.md](./SPRINT-18-RETROSPECTIVE.md) + [SPRINT-18-YOY-FIX.md](./SPRINT-18-YOY-FIX.md) (299 行) + [CACHE-INVALIDATION.md](./CACHE-INVALIDATION.md) (333 行) + [PRE-COMMIT.md](./PRE-COMMIT.md) (335 行) |
| **Sprint 17** (B1+B2 Pydantic Contract 模式: CLAUDE.md + ground-truth-lint + B2 全量 audit) | ✅ 收口 2026-06-11 | [SPRINT-17-RETROSPECTIVE.md](./SPRINT-17-RETROSPECTIVE.md) + [SPRINT-17-B2-AUDIT-FULL.md](./SPRINT-17-B2-AUDIT-FULL.md) (299 行) + [LINTING.md](./LINTING.md) (359 行) |
| **Sprint 16.5** (P1/P2 治理: cache_key MD5 + 3 contract audit + YOYBadge 守卫) | ✅ 收口 2026-06-11 | [SPRINT-16-5-RETROSPECTIVE.md](./SPRINT-16-5-RETROSPECTIVE.md) + [SPRINT-16-5-B2-AUDIT.md](./SPRINT-16-5-B2-AUDIT.md) (252 行 audit 报告) |
| **Sprint 16 P0** (DuckDB 1.5.3 race 治根) | ❌ 中止 (等 1.5.4) | [SPRINT-16-5-README.md](./SPRINT-16-5-README.md) (40 行, 等 1.5.4 release 激活) |
| **Sprint 15** (Wave 1/2/3 治根) | ✅ 收口 2026-06-11 | [SPRINT-15-PLAN-RATIO-AUDIT.md](./SPRINT-15-PLAN-RATIO-AUDIT.md) (326 行 plan) |
| **Sprint 14.5** (RFM TTL ratio 500 治根) | ✅ 收口 2026-06-10 | [SPRINT-14-5-RETROSPECTIVE.md](./SPRINT-14-5-RETROSPECTIVE.md) |
| **Sprint 14** (Stage 2 Pydantic + ETL 治根) | ✅ 收口 2026-06-10 | [SPRINT-14-PLAN-RATIO-STAGE2.md](./SPRINT-14-PLAN-RATIO-STAGE2.md) + [SPRINT-14-RETROSPECTIVE.md](./SPRINT-14-RETROSPECTIVE.md) |
| **Sprint 13** (Ratio 治理 Stage 1) | ✅ 收口 2026-06-10 | [SPRINT-13-RETROSPECTIVE.md](./SPRINT-13-RETROSPECTIVE.md) |
| **Sprint 12** (7/7 质量加固 + 50M benchmark) | ✅ 收口 2026-06-09 (反推补齐 2026-06-11) | [SPRINT-12-RETROSPECTIVE.md](./SPRINT-12-RETROSPECTIVE.md) (44 行) |
| **Sprint 11** (codex audit 4→3 件 + YOY/pp 5 层修法) | ✅ 收口 2026-06-09 (反推补齐 2026-06-11) | [SPRINT-11-RETROSPECTIVE.md](./SPRINT-11-RETROSPECTIVE.md) (61 行) |
| **Sprint 10** (codex 重塑 plan 12→5 件 + B1 preflight) | ✅ 收口 2026-06-08 (反推补齐 2026-06-11) | [SPRINT-10-RETROSPECTIVE.md](./SPRINT-10-RETROSPECTIVE.md) (47 行) |
| **Sprint 9** (维修 4 件根因: watchdog / cache key / W3 valid_sql / W4 memory) | ✅ 收口 2026-06-07 (反推补齐 2026-06-11) | [SPRINT-9-RETROSPECTIVE.md](./SPRINT-9-RETROSPECTIVE.md) (49 行) |
| **Sprint 8** (P0 前端 2 bug 修复 + P1 16 root test 删) | ✅ 收口 2026-06-07 (反推补齐 2026-06-11) | [SPRINT-8-RETROSPECTIVE.md](./SPRINT-8-RETROSPECTIVE.md) (34 行) |
| **Sprint 7** (治根 10 root test fail + P2 6 层防护) | ✅ 收口 2026-06-07 (反推补齐 2026-06-11) | [SPRINT-7-RETROSPECTIVE.md](./SPRINT-7-RETROSPECTIVE.md) (40 行) |
| **Sprint 6** (5→6 层防护 + W7 pytest 修复) | ✅ 收口 2026-06-07 (反推补齐 2026-06-11) | [SPRINT-6-RETROSPECTIVE.md](./SPRINT-6-RETROSPECTIVE.md) (37 行) |
| **Sprint 5** (UNIQUE INDEX race Fix A 拆 2 tx, 跑批真闭环 17 min) | ✅ 收口 2026-06-07 (反推补齐 2026-06-11) | [SPRINT-5-RETROSPECTIVE.md](./SPRINT-5-RETROSPECTIVE.md) (39 行) |
| **Sprint 4** (2/2 P0 done, 痛点 1 端到端 + DuckDB 55GB 备份) | ✅ 收口 2026-06-07 (反推补齐 2026-06-11) | [SPRINT-4-RETROSPECTIVE.md](./SPRINT-4-RETROSPECTIVE.md) (36 行) |
| **Sprint 3** (5/5 P0+P1 done, 痛点 1 闭环 13.4 min) | ✅ 收口 2026-06-07 (反推补齐 2026-06-11) | [SPRINT-3-RETROSPECTIVE.md](./SPRINT-3-RETROSPECTIVE.md) (40 行) |
| **Sprint 2** (W3/W4 pipeline 集成 + RFM banner + 飞书 refresh + W4 T-7) | ✅ 收口 2026-05 下 (反推补齐 2026-06-11) | [SPRINT-2-RETROSPECTIVE.md](./SPRINT-2-RETROSPECTIVE.md) (36 行) |
| **Sprint 1** (项目 init + ETL 4 阶段奠基) | ✅ 收口 2026-05 中 (反推补齐 2026-06-11) | [SPRINT-1-RETROSPECTIVE.md](./SPRINT-1-RETROSPECTIVE.md) (42 行) |

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
| [SPRINT-17-B2-AUDIT-FULL.md](./SPRINT-17-B2-AUDIT-FULL.md) | Sprint 17 B2 全量 audit 10 contract (299 行, 60+ mark 字段治根) |
| [SPRINT-16-5-B2-AUDIT.md](./SPRINT-16-5-B2-AUDIT.md) | Sprint 16.5 B2 试点 3 contract audit (252 行, 9 mark 字段治根) |
| [LINTING.md](./LINTING.md) | Sprint 17 ground-truth-lint 使用文档 (359 行, 4 规则 R1/R2/R3/R4) |
| [SPRINT-18-YOY-FIX.md](./SPRINT-18-YOY-FIX.md) | Sprint 18 #141 26 YOY ratio 字段命名/语义冲突治根 (299 行, 白名单 + 类型补标混合) |
| [CACHE-INVALIDATION.md](./CACHE-INVALIDATION.md) | Sprint 18 #123 W5 DuckDB-KV cache invalidation 启动 hook 使用文档 (333 行, 跨进程 manifest 同步) |
| [PRE-COMMIT.md](./PRE-COMMIT.md) | Sprint 18 #142 pre-commit ground-truth-lint hook 使用文档 (335 行, 跟 .githooks 双轨并存) |
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

*此文件由 AI 维护，最后更新：2026-06-11*
