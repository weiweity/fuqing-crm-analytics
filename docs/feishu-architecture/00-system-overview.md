# 芙清 CRM 客户分析系统 — 系统总览

**版本**: v0.4.14.16（2026-06-07 更新 — Sprint 8 收口）
**状态**: 语义层 ✅ | 契约层 ✅ | 服务层 ✅ | 前端 Vue3 ✅ | 老客健康分析 ✅ | 配置扩展 P1-P4 ✅ | 重构 Phase 0-7 ✅ | Docker 化 ✅ | RFM 缓存修复 ✅ | 代码审计 ✅ | 大文件拆分 ✅ | **W2 manifest 原子切换 ✅ (v0.4.8)** | **W3 DQ 断言 MVP ✅ (v0.4.10)** | **W4 fact_rfm_long ✅ (v0.4.9)** | **CI 6 件套 5/6 ✅ (B2-B6 done, B1 待)** | **Sprint 8 收口 ✅ (P0 前端 2 bug + P1 删 16 root test ignore)**

---

## 1. 系统定位

芙清 CRM 客户分析系统是芙清电商运营团队的**内部数据中台**，服务于日常运营决策和月度复盘。

| 维度 | 说明 |
|------|------|
| 产品定位 | 内部运营中台工具 |
| 目标用户 | 运营专员、运营经理、老板 |
| 核心价值 | 每日 9 点自动推送、数据驱动决策、口径唯一可信 |
| 数据规模 | 原始 1030 万订单 / 410 万用户（2020-2026） |

---

## 2. 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        用户界面层（Vue3 + ECharts 5 + Naive UI）                        │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
│  │GeoView  │  │CatView  │  │RFMView  │  │ChurnView│  │ProdTier │  │Audience │  │Health  │  │
│  │地域分析  │  │品类分析  │  │RFM象限  │  │流失分析  │  │产品梯队  │  │人群看板  │  │老客健康  │  │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  │
│       └────────────┴────────────┴────────────┴────────────┴────────────┴─────────────┘
│                                          │ HTTP JSON
│  ┌─────────────────────────────────────┼────────────────────────────────────────────┐
│  │                          API 层（FastAPI + Pydantic）                             │
│  │  ┌──────────────┐  ┌────────────┴────────────┐  ┌──────────────┐           │
│  │  │ /metrics/*  │  │ /audience/*, /geo/*     │  │ /customer-health/*│           │
│  │  │  指标概览    │  │  人群/地域/品类/流失     │  │  老客健康分析  │           │
│  │  └──────┬───────┘  └────────────┬────────────┘  └──────┬───────┘           │
│  │         └───────────────────────┼───────────────────────┘                       │
│  │                                  │                                              │
│  │  ┌──────────────────────────────┼──────────────────────────────────────────┐  │
│  │  │                    服务层（Services）                                       │  │
│  │  │  MetricsService  ChurnService  GeoService  CategoryService  RFMTierFlow  │  │
│  │  │  HealthOverview  HealthRepurchase  HealthTiers  HealthRFM  HealthConversion... │  │
│  │  │  ────────────────────────────────────────────────────────────────        │  │
│  │  │  ⚠️ 所有 Service 禁止硬编码 SQL，必须引用语义层（filters/metrics/segments） │  │
│  │  └──────────────────────────────┼──────────────────────────────────────────┘  │
│  │                                 │                                              │
│  │  ┌──────────────────────────────┼──────────────────────────────────────────┐  │
│  │  │                   语义层（Semantic Layer）✅                            │  │
│  │  │  filters.py   metrics.py   dimensions.py   segments.py   channels.py    │  │
│  │  │  calculations.py   time.py                                           │  │
│  │  │  ────────────────────────────────────────────────────────────        │  │
│  │  │  ✅ 口径只定义一次，改一处全局生效                                     │  │
│  │  └──────────────────────────────┼──────────────────────────────────────────┘  │
│  │                                 │                                              │
│  │  ┌──────────────────────────────┼──────────────────────────────────────────┐  │
│  │  │                   契约层（Contracts）✅                                │  │
│  │  │              backend/contracts/schemas.py（Pydantic）                    │  │
│  │  │  ✅ OpenAPI 文档 → openapi-typescript → TypeScript 类型（禁止手写）     │  │
│  │  └──────────────────────────────┼──────────────────────────────────────────┘  │
│  │                                 │                                              │
│  │  ┌──────────────────────────────┼──────────────────────────────────────────┐  │
│  │  │                    数据层（DuckDB）                                     │  │
│  │  │       parquet/        orders表(34列)      user_rfm表(17字段)          │  │
│  │  │  └── shop/ └── member/  ├── is_goujinjin    └── (user_id, analysis_date │  │
│  │  │                        ├── is_refund          metric_type, lookback_days) │
│  │  │                        └── pay_time                                   │  │
│  │  └─────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心设计原则

### 3.1 语义层唯一真实数据源

> **所有业务口径只定义一次，全局生效。禁止在 Service 中硬编码 SQL。**

| 以前（错误） | 现在（正确） |
|-------------|-------------|
| 每个 service 自己写 `order_status LIKE '%成功%'` | 统一引用 `OrderFilters.valid_order()` |
| 8 象限 CASE WHEN 散落在多个 service | 统一引用 `SegmentRegistry.build_segment_case_when_sql()` |
| GSV 公式在多个文件里各写一份 | 统一引用 `metrics.py` 中的注册表达式 |
| MoM/YoY 计算在 service 内联 | 统一引用 `calculations.py` 中的 `mom_absolute/yoy_absolute` 等 |

### 3.2 双保险过滤原则

> 所有有效订单判定必须同时满足两个条件，缺一不可：

```
有效订单 = is_refund = FALSE  AND  order_status != '交易关闭'
GSV口径  = is_goujinjin = FALSE AND is_refund = FALSE AND order_status != '交易关闭'
GMV口径  = is_goujinjin = FALSE AND order_status != '交易关闭'（含退款）
```

### 3.3 契约优先

- 前后端接口定义必须先在 `backend/contracts/schemas.py` 确认
- 前端类型必须从 `/openapi.json` 自动生成，禁止手写 TypeScript 类型

---

## 4. 技术栈

| 层级 | 技术选型 | 版本/说明 |
|------|---------|----------|
| 数据处理 | Python + Pandas + DuckDB | parquet dtype=str 防精度丢失 |
| 后端 | FastAPI + Pydantic v2 | 端口 8000 |
| 前端 | Vue3 + Vite + Tailwind + Pinia + TanStack Query + Naive UI | 端口 5173，Stripe Design System 配色 |
| 图表 | ECharts 5 + Naive UI | 品牌紫 `#533afd` |
| 类型安全 | openapi-typescript | 从 `/openapi.json` 自动生成 |
| 导出 | xlsx (SheetJS) | Excel 导出 |

---

## 5. 核心业务参数（v4.0）

| 参数 | 值 | 说明 |
|------|-----|------|
| 新老客基准 | cutoff = T1-1天 | cutoff = 分析窗口起始日期 - 1 天 |
| RFM 阈值 | R=[14/30/60/90] F=[1/2/3/5] M=[100/300/500/1000] | 2026-04-20 修正 |
| RFM 象限 | **8 象限**（经典 RFM，2026-04-20 从11象限重构） | 重要价值/重要保持/重要发展/重要挽留 + 一般×4 |
| 渠道漏斗 | **9 层**（v4.0，2026-04-15 调整） | P1=U先派样 → P2=百补派样 → P3=赠品&0.01 → P4=达播 → P5=微博 → P6=直播 → P7=淘客 → P8=货架 → P9=其他 |
| 默认周期 | **WTD**（当周至今） | 前端默认调取 |
| ETL 增量检测 | 文件名 + mtime 双重判断 | 覆盖旧文件后自动重新处理 |

---

## 6. 启动命令

```bash
# 数据路径
DATA="/Users/hutou/Desktop/fuqin-date/芙清CRM数据库"
PROJECT="/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics"

# 后端（端口 8000）
cd "$PROJECT"
PYTHONPATH="$PROJECT" nohup ~/.workbuddy/binaries/python/envs/default/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir backend >> /tmp/fuqin-crm-backend.log 2>&1 &

# 前端（端口 5173）
cd "$PROJECT/frontend-vue3"
npm run dev

# ETL（增量更新）
cd "$PROJECT"
PYTHONPATH="$PROJECT" ~/.workbuddy/binaries/python/envs/default/bin/python scripts/run_etl.py --update

# ETL（全量重建）
PYTHONPATH="$PROJECT" ~/.workbuddy/binaries/python/envs/default/bin/python scripts/run_etl.py --full
```

---

## 7. 项目进度总览

| 阶段 | 内容 | 状态 |
|------|------|------|
| Week 1 | 核心指标看板 | ✅ 完成 |
| Week 2 | RFM 分析 | ✅ 完成 |
| Week 3 | 人群流转 | ✅ 完成 |
| Week 4 | 人群画像（Geo/Category/Audience） | ✅ 完成 |
| Week 5 | 老客健康分析仪表盘 | ✅ 完成（2026-04-20） |
| Week 6 | 缺口追踪 | ⏳ 待启动 |
| Week 7 | 健康分析配置扩展（P1-P4）+ 架构加固 | ✅ 完成（2026-04-20） |
| **架构升级** | 语义层 + 契约层 + Vue3 前端 + 老客健康分析 | ✅ 完成（2026-04-20） |
| **重构 Phase 0-7** | 清理归档 / 路由拆分 / 服务模块化 / ETL包化 / Schema拆分 / 指标服务拆分 / 文档体系 / Docker化 | ✅ 完成（2026-05-27） |
| **RFM 缓存修复** | 口径校准（user_rfm vs 全量历史12倍差异）+ 缓存键修复（76倍加速） | ✅ 完成（2026-05-28） |
| **渠道规则** | 渠道规则 +8 条 / SPU重匹配 / `--rescan-channel` 子命令 | ✅ 完成（2026-05-16） |
| **W2 manifest 原子切换** | manifest.json + POSIX atomic rename (tmp + fsync，痛点 2 根因修复) | ✅ 完成（2026-06-05，v0.4.8） |
| **W3 DQ 断言 MVP** | 3 断言（total_not_drop / repurchase_nonzero / idempotency）+ quarantine 表 | ✅ 完成（2026-06-06，v0.4.10） |
| **W4 fact_rfm_long MVP** | 9 channel × 60 item × 1 segment = 540 组合预计算 + (date, dimension_key, version) UNIQUE INDEX | ✅ 完成（2026-06-05，v0.4.9） |
| **CI 6 件套** | B2 pre-commit import / B3 nightly / B4 requirements-lock / B5 test-order / B6 weekly report / B1 (待) | 🟡 5/6 done（2026-06-05，B6 完结，B1 待） |

---

## 8. 文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| 系统总览 | `飞书版架构文档/00-系统总览.md` | 本文 |
| 数据层 | `飞书版架构文档/01-数据层.md` | DuckDB/ETL/表结构 |
| 语义层 | `飞书版架构文档/02-语义层.md` | filters/metrics/segments/channels/time/calculations |
| 契约层 | `飞书版架构文档/03-契约层.md` | Pydantic 模型/OpenAPI |
| 服务层 | `飞书版架构文档/04-服务层.md` | 21 个 service + health 10模块 |
| 前端架构 | `飞书版架构文档/05-前端架构.md` | Vue3/8 个 View + health 1页 |
| 部署运维 | `飞书版架构文档/06-部署与运维.md` | 启动/ETL/监控 |
| 常见问题 | `飞书版架构文档/07-常见问题汇总.md` | Bug修复/决策记录 |

---

## 9. v0.4.10 Release Notes（2026-06-06）

> 本节记录 v0.4.10 release 的 W2/W3/W4 + CI 6 件套刷写。

### 9.1 W2 — 原子 manifest.json 切换（v0.4.8, 2026-06-05）

- **目标**: 痛点 2 根因修复（ETL 写入与读取不原子，导致 RFM 缓存可能读到半成品）
- **方案**: `manifest.json` + POSIX atomic rename (tmp + fsync + os.rename)
  - 写：写 `manifest.json.tmp.{pid}.{ms}` → flush + `os.fsync()` → 备份旧版到 `.versions/{ts}_v{N}.json` → `os.rename(tmp, manifest.json)` (POSIX atomic, near-atomic on Windows)
  - 读：API 层 `SnapshotManifest.read_active()` / `read_full()` 每次新实例（短读 < 4KB 原子）
  - 旧版本保留 7 天: `.versions/{ts}_v{N}.json`
- **代码**:
  - `scripts/etl/manifest.py` (新, ~200 行): `class SnapshotManifest` + `get_manifest()` 单例 helper
  - `backend/services/rfm/loader.py` 暴露 `get_rfm_view_name()` / `get_rfm_manifest_info()` (commit `c031503`)
- **测试**: `backend/tests/test_w2_manifest.py` (8 tests) — 验证原子性、并发读、POSIX rename 切换无脏读
- **commit SHA**: `c031503` (merge: `e254426`)

### 9.2 W3 — DQ 断言 MVP（v0.4.10, 2026-06-06）

- **目标**: 痛点 2 质量保证（SaaS 标准：脏数据隔离不阻塞业务）
- **方案**: 3 核心断言 + quarantine 表 + lark 告警
  - `assert_total_not_drop` (total < prev_30d_avg × 0.3 → quarantine)
  - `assert_repurchase_nonzero` (防 P0-102 100%/0% 回归，W4 配套查 `fact_rfm_long`)
  - `assert_idempotency` ((date, dim, version) 唯一，防重复跑批)
- **代码**:
  - `scripts/etl/assertions.py` (新, ~220 行): 总入口 `run_assertions(conn, target_date, send_alert=True)`
  - `rfm_quarantine` 表 (id, date, failed_assertion, reason, raw_data JSON, created_at)
  - 跨子项目 import: 复用 `scraper/core/sanity_check.py:_send_lark_alert`（6 道门禁 lark-cli 通道）
- **测试**: `backend/tests/test_w3_dq_assertions.py` (11 tests) — 全 pass / 部分 fail / lark mock
- **CLI 入口**: `python3 scripts/etl/assertions.py --date=2026-06-05 [--no-alert]`
- **commit SHA**: `937b034` (merge: `1917e08`)

### 9.3 W4 — fact_rfm_long 预计算 MVP（v0.4.9, 2026-06-05）

- **目标**: 痛点 3 部分缓解（RFM 维度查询 60s+ 加速到 ms 级）
- **方案**: 540 组合预计算 + 纯增量 append T-1 (W4 full 留 T-7 dbt-style merge 兜底)
  - 组合数: `9 channel × 60 item × 1 segment = 540` (W4 MVP 仅 `channel=全店` 1 组合验证机制, W4 full 扩 540)
  - 表结构: `(date, dimension_key, dimension_json, user_count, gmv, repurchase_count, version, created_at)` + PRIMARY KEY `(date, dimension_key, version)`
  - 写入: `INSERT ... ON CONFLICT (date, dimension_key, version) DO NOTHING RETURNING date` (DuckDB 1.5+)
- **代码**:
  - `scripts/etl/precompute_fact_rfm.py` (新, ~245 行): `setup_async_memory()` / `cleanup_async_memory()` / `create_fact_rfm_table()` / `incremental_load()` / `_next_version()` / `run_mvp_async()`
  - `backend/services/rfm/loader.py` 暴露 `get_rfm_view_name()` / `get_rfm_manifest_info()` 走 W2 原子读
- **测试**: `backend/tests/test_w4_fact_rfm.py` (7 tests) — 增量 T-1、UNIQUE 约束、version 续号、ON CONFLICT 幂等
- **commit SHA**: `56f4a43` (merge: `52a74bd`)

### 9.4 CI 6 件套（5/6 done, B1 待）

| ID | 名称 | 状态 | commit | 拦什么 |
|----|------|------|--------|-------|
| B2 | pre-commit import 完整性 | ✅ done (v0.4.7.5) | `8ca17d9` | 防 import 漏写 + ruff lint |
| B3 | nightly 健康检查 workflow | ✅ done (v0.4.7.6) | `32252e7` | 每日 02:00 cron + 漏检 ETL 跑批异常 |
| B4 | requirements-lock.txt 锁版本 | ✅ done (v0.4.7.7) | `eb40690` | 防 CI 30/30 red CI 复发 |
| B5 | test 顺序无关性 lint | ✅ done (v0.4.7.8) | `496f1d8` | 防 shared module 顺序依赖 |
| B6 | 每周 CI 健康报告 | ✅ done (v0.4.7.9) | `45f72bf` | 每周日 09:00 汇总 |
| B1 | pytest 顺序无关 hard assert | ⏳ 待 | (TBD) | 强制 random order 全绿 |

### 9.5 与各份文档的对应关系

| 文档 | 关注章节 |
|------|---------|
| 01-数据层.md | §6 fact_rfm_long 表结构 + W5 cache 段 |
| 02-语义层.md | §8 manifest 引用（RFM 5 指标走 semantic） |
| 03-契约层.md | §6 /api/v1/rfm/version endpoint |
| 04-服务层.md | §6 W3 DQ assertions + W5 cache |
| 06-部署与运维.md | §7 W2 manifest + W4 fact_rfm_long + W5 cache 部署段 |
| 07-常见问题汇总.md | §7 v0.4.10 commit SHA 索引 + §8 CI 5/6 done |
