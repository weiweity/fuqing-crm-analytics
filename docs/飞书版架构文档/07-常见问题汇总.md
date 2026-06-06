# 芙清 CRM — 常见问题汇总

**版本**: v3.1（2026-06-06 补 9 个 commit SHA 索引 + CI 5/6 done）
**包含**: Bug修复记录 / 决策记录 / 经验教训

---

## 1. 重大 Bug 修复记录

### 1.1 P0: 语义层 `order_status LIKE '%成功%'` 误杀有效订单

**发现日期**: 2026-04-17
**影响**: 4月 GSV 从 ¥534万 → 仅显示 ¥143万（损失 73%）

**根因**: `order_status LIKE '%成功%'` 会过滤掉所有不含"成功"二字的订单，包括"卖家已发货"等有效订单（4月有 49,064 条）。

**修复方案（双保险）**:
```python
# 修复前（错误）
"order_status LIKE '%成功%'"

# 修复后（正确 — 双保险）
"is_refund = FALSE AND order_status != '交易关闭'"
```

**修复范围**:
- `OrderFilters.valid_order()` → `is_goujinjin = FALSE AND order_status != '交易关闭' AND is_refund = FALSE`
- `OrderFilters.gmv_base()` → `is_goujinjin = FALSE AND order_status != '交易关闭'`
- `AmountExprBuilder.gsv()` → 同步更新 CASE WHEN
- `FilterBuilder.build()` → 按 metric_type 选 gmv_base() 或 valid_order()
- 人群看板 API → 全部改为 GSV 口径

**数据验证**:
```
4月1-17日：
  修复前 GSV: ¥143万
  修复后 GSV: ¥534万  ✅ 合理（与订单量匹配）
```

---

### 1.2 P1: WTD prev2 日期倒置

**发现日期**: 2026-04-17
**影响**: 同比数据使用错误的时间区间

**修复**: `prev2_wtd()` 计算逻辑修正。

---

### 1.3 P1: 新老客 cutoff Bug

**发现日期**: 2026-04-17
**影响**: Q1 2025 老客占比从 75% → 38.9%

**根因**: cutoff 计算错误，应为 `start_date - 1天`。

**修复**: `cutoff = T1-1天` 逻辑已统一。

---

### 1.4 P2: RFM 覆盖率缺口（1.7k 用户落入"其他"）

**发现日期**: 2026-04-16
**影响**: 97.5% → 100%（覆盖率）

**修复**: 新增象限 10「偶遇沉睡」和象限 11「边缘组合」。
> ⚠️ 此修复于 v4.0（2026-04-20）被 8 象限重构替代，v4.0 已移除象限 10/11。

---

### 1.5 P1: RFM 象限分类循环论证（cutoff = end_date）

**发现日期**: 2026-05-29
**影响**: "价值/发展"象限回购率虚高 27-35%，"保持/挽留"仅 0.02-0.17%，数据完全失真

**根因**: `_shared.py` 中 `_resolve_date_ranges()` 的自定义日期路径使用 `cutoff = end_date`，导致当期购买者被自动归类为高 R 分 → 进入"价值/发展"象限 → 回购率必然虚高（循环论证）。

**修复**: `cutoff = start_date - 1 day`，覆盖四处：
- 当前周期 cutoff
- 自定义对比期 cutoff
- 去年同期 cutoff（`ly_cutoff_str`）
- 去年对比期 cutoff（`y2_cutoff_str`）

**修复文件**: `backend/services/rfm/_shared.py`
**分支**: `fix/cutoff-start-minus-one` → 已合并 main

---

### 1.6 P1: R/F/M flow hist_customers_all 使用 user_recency 全局累计值

**发现日期**: 2026-05-29
**影响**: R/F/M 区间流转图（近1月/近2-3月/近4-6月...）数据全部错误

**根因**: `r_flow.py`、`f_flow.py`、`m_flow.py` 中的 `hist_customers_all` CTEs 从 `user_recency` 表读取数据（`last_pay_time`/`total_orders`/`total_amount`），但 `user_recency` 在 ETL 后更新到最新日期，无法反映历史周期的真实状态。

**修复**: 所有 `hist_customers_all` 改从 `orders` 表实时聚合：
- R: `MAX(pay_time)` + `DATEDIFF('day', MAX(pay_time)::DATE, cutoff::DATE)`
- F: `COUNT(*)` 截至 cutoff
- M: `SUM(actual_amount)` 截至 cutoff

**修复文件**: `backend/services/rfm/r_flow.py`、`f_flow.py`、`m_flow.py`
**分支**: `fix/rfm-flow-hist-customers-all` → 已合并 main

**验证**: 修复后 R 区间回购率呈单调递减（8.09% → 0.25% ✅），F/M 区间呈单调递增（✅）

---

## 2. 架构决策记录

### 2.1 双保险过滤原则

**决策**: 所有有效订单判定必须同时满足两个独立条件。
**原因**: 单一 `is_refund` 字段或 `order_status` 判断均有漏洞，两个独立字段交叉验证更可靠。
**结论**: `is_refund = FALSE AND order_status != '交易关闭'`。

### 2.2 GSV vs GMV 口径统一

**决策**: 人群看板所有指标统一使用 GSV 口径。
**原因**: GSV 反映真实销售，更适合人群分析和运营决策。
**结论**: KPI/日趋势/30指标/渠道概览全部改为 GSV。

### 2.3 渠道漏斗 v2.0（P4/P5 拆分）

**决策**: 将原来的"达播/微博"合并层拆分为 P4=达播、P5=微博。
**原因**: 达播和微博是不同运营团队、不同ROI，需要独立分析。
**结论**: 购物金不参与渠道分析（已由 `is_goujinjin` 标记剔除）。

### 2.4 前端类型手写禁止

**决策**: 前端 TypeScript 类型必须从 OpenAPI 自动生成，禁止手写。
**原因**: 手工类型与后端 Pydantic 模型容易产生不一致，且维护成本高。
**结论**: `npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts`。

### 2.5 公式统一原则（2026-04-20）

**决策**: 所有 MoM/YoY 计算统一使用 `calculations.py`，禁止在 Service 中内联。
**原因**: `get_overview_metrics` 中内联计算与语义层 `calculations.py` 两套逻辑不一致。
**结论**: `mom_absolute/mom_ratio/yoy_absolute/yoy_ratio` 为唯一数据源。

### 2.6 渠道名大小写统一（2026-04-20）

**决策**: 数据库统一存储 `U先派样`（大写U），ETL `match_channel()` P1 写入大写。
**原因**: DB存 `u先派样`（小写）、前端用 `U先派样`（大写），导致单渠道筛选返回0。
**结论**: `DB_TO_UI` 变为恒等映射，消除大小写差异。

### 2.7 ETL 增量检测升级（2026-04-20）

**决策**: 增量检测升级为"文件名 + mtime 双重判断"。
**原因**: 原逻辑只判断文件名，覆盖旧文件后 ETL 不会重新处理。
**结论**: 文件级淘客缓存（`taoke_file_cache.json`）实现49文件0秒加载。

### 2.8 健康分析配置扩展（2026-04-19）

**决策**: 健康分析配置系统扩展 P1-P4。
**原因**: 配置变更无法预览影响、无历史记录、无审计追踪。
**结论**: P1预览评分变化 → P2历史回滚 → P3审计日志 → P4多环境默认。

---

## 3. 经验教训

### 3.1 "失去记忆"问题

**事件**: 前端迁移 Vue3 后，启动命令文档一直指向废弃的 Streamlit 版本，导致每次都要重新查找正确命令。

**教训**: 文档必须与代码同步更新。迁移时同步更新：
- README.md
- MEMORY.md
- 所有相关文档中的路径/命令

**行动**: 建立文档与代码的同步检查机制。

---

### 3.2 ETL is_refund Bug 存活 4 周

**事件**: `is_refund` 标记错误导致 139 万退款未正确剔除，Bug 存活 4 周才被发现。

**根因**: 无数据验收机制，没有定期对比 ETL 结果和人工计算结果。

**教训**: 每个 ETL run 必须有 sanity check：
```python
# 每次 ETL 后必须执行
assert refund_rate < 0.25, "退款率异常"
assert gmv >= gsv, "GMV必须>=GSV"
```

---

### 3.3 三路方案收敛 ≠ 方案优秀

**事件**: 同一个问题写了 3 种实现路径，以为是"多方案备选"，实为问题理解不清晰。

**教训**: 停下来搞清楚"为什么需要 3 条路"，收敛是信号，不是结果。

---

### 3.4 优先 API 拦截而非 DOM 解析

**事件**: SPA 页面的 DOM 元素频繁变化，Canvas 图表数据无法从 DOM 读取。

**教训**: 浏览器 network 拦截是更稳定的维度，优先使用 API 拦截获取数据。

---

## 4. RFM 象限语义变更说明

### 4.1 v4.0（2026-04-20）：11象限 → 8象限

**状态**: 已接受 `segments.py` 为新标准

> ⚠️ v4.0 重大变更：从 11 象限重构为**经典 8 象限**（重要价值/重要保持/重要发展/重要挽留 + 一般×4）。

| 象限ID | 名称 | R维度 | F维度 | M维度 |
|------|------|--------|--------|--------|
| 1 | 重要价值 | R≥4（14天内） | F≥4（4次+） | M≥4（500元+） |
| 2 | 重要保持 | R≥4 | F≥4 | M<4 |
| 3 | 重要发展 | R≥4 | F<4 | M≥4 |
| 4 | 重要挽留 | R≥4 | F<4 | M<4 |
| 5 | 一般价值 | R<4 | F≥4 | M≥4 |
| 6 | 一般保持 | R<4 | F≥4 | M<4 |
| 7 | 一般发展 | R<4 | F<4 | M≥4 |
| 8 | 一般挽留 | R<4 | F<4 | M<4 |

### 4.2 v2.0（2026-04-16）：11象限规则（已废弃）

| 象限 | 旧规则 | segments.py（语义层） | 影响 |
|------|--------|---------------------|------|
| 钻石会员 R | (5,5) = 仅 R=5 | (4,5) = R=4,5 | R=4 客户（14-30天）**新增进入** |
| 潜力新贵 R | (5,5) | (4,5) | 同上 |
| 频次买家 M | (2,3) | (1,3) | M=1 客户（<100元）**新增进入** |

---

## 5. 数据规模参考

| 月份 | 订单数 | GSV | 说明 |
|------|--------|-----|------|
| 2026-01 | ~88万 | ¥1,169万 | Q1 高点 |
| 2026-02 | ~55万 | ¥740万 | 春节低谷 |
| 2026-03 | ~75万 | ¥1,005万 | Q1 回升 |
| 2026-04（WTD） | ~17万 | ¥534万 | 截至04-17 |

> 数据均为 GSV 口径（剔除购物金+退款）

## 6. 关键架构原则速查

| 原则 | 说明 |
|------|------|
| 语义层唯一数据源 | 口径只定义一次，`filters.py/metrics.py/segments.py` 为唯一真数据源 |
| 双保险过滤 | `is_refund=FALSE AND order_status!='交易关闭'` |
| GSV vs GMV | GSV剔除退款，GMV含退款 |
| 8象限RFM | v4.0经典RFM，阈值统一在 `RFM_THRESHOLDS` |
| 9层渠道漏斗 | P1=U先派样 → P9=其他，P4-P7受 `channel=='其他'` 保护 |
| 公式统一 | MoM/YoY/占比计算统一用 `calculations.py` |
| 前端类型安全 | TypeScript类型从 OpenAPI 自动生成，禁止手写 |
| 连接零泄漏 | `conn = get_connection()` 后立即进入 `try:`，`conn.close()` 在 `finally:` |

---

## 7. v0.4.10 之前 9 个 commit SHA 索引（2026-04-17 → 2026-06-06）

> 9 个核心 commit，按时间倒序排列。每个 commit 对应一个 P0/P1/P2 修复或新功能。

| # | 主题 | commit SHA | merge SHA | 标签 | 文档位置 |
|---|------|-----------|-----------|------|---------|
| 1 | **VERSION drift 修复 v0.4.10.1** | `6c0021f` | `f344d11` | v0.4.10.1 | `fix/version-drift-recurrent` |
| 2 | **W3 MVP DQ assertions** | `937b034` | `1917e08` | v0.4.10 | `feat/wo3-dq-assertions-mvp` |
| 3 | **W4 MVP fact_rfm_long** | `56f4a43` | `52a74bd` | v0.4.9 | `feat/wo4-fact-rfm-mvp` |
| 4 | **W2 原子 manifest 切换** | `c031503` | `e254426` | v0.4.8 | `feat/wo2-manifest-snapshot` |
| 5 | B6 P3 每周 CI 健康报告 | `45f72bf` | `c2c9e4d` | v0.4.7.9 | `feat/b6-weekly-report` |
| 6 | B5 P2 test 顺序无关性 lint | `496f1d8` | `5290df3` | v0.4.7.8 | `feat/b5-test-order-lint` |
| 7 | B4 P1 requirements-lock.txt | `eb40690` | `835f650` | v0.4.7.7 | `feat/b4-lock-requirements` |
| 8 | B3 P1 nightly 健康检查 | `32252e7` | `9f6156f` | v0.4.7.6 | `feat/b3-nightly-ci` |
| 9 | B2 P0 pre-commit import 完整性 | `8ca17d9` | `ed6d637` | v0.4.7.5 | `feat/b2-precommit-import-check` |

### 7.1 9 个 commit 的设计决策

#### Commit 9（#9, 8ca17d9）— B2 pre-commit import 完整性

- **目标**: 防 `ModuleNotFoundError` 复发（30/30 red CI 根因）
- **方案**: pre-commit 钩子扫所有 import，对比 requirements.txt
- **测试**: 钩子必须能跑通，故意漏 import 时阻塞

#### Commit 8（#8, 32252e7）— B3 nightly 健康检查

- **目标**: 每日 02:00 自动跑 pytest + 抽检 ETL 健康
- **方案**: GitHub Actions cron workflow，失败时 lark 告警

#### Commit 7（#7, eb40690）— B4 requirements-lock.txt

- **目标**: 锁 Python 依赖版本，防 CI 本地漂移
- **方案**: `pip freeze` 生成 `requirements-lock.txt`，CI 用此文件

#### Commit 6（#6, 496f1d8）— B5 test 顺序无关性

- **目标**: 防 shared module 顺序依赖（如 `conftest.py` 状态污染）
- **方案**: `pytest-randomly` 跑 CI 100 次，发现问题修

#### Commit 5（#5, 45f72bf）— B6 每周 CI 健康报告

- **目标**: 每周日 09:00 汇总 CI 跑批结果，识别回归
- **方案**: GitHub Actions weekly report workflow，发 lark 卡片

#### Commit 4（#4, c031503）— W2 原子 manifest 切换

- **目标**: 痛点 2 根因修复（ETL 写入与读取不原子）
- **方案**: `manifest.json` + POSIX atomic rename (tmp + fsync + os.rename, **不**用 symlink)
- **关键文件**: `scripts/etl/manifest.py`（新, ~200 行, `SnapshotManifest` class）

#### Commit 3（#3, 56f4a43）— W4 fact_rfm_long

- **目标**: 痛点 3 部分缓解（RFM 维度查询 60s+ → ms）
- **方案**: 540 组合预计算（W4 MVP 仅 1 组合 `channel=全店` 验证机制, 走 T-1 增量 + ON CONFLICT DO NOTHING）
- **关键文件**: `scripts/etl/precompute_fact_rfm.py`（新, ~245 行, `incremental_load()` / `_next_version()` / `setup_async_memory()` / `cleanup_async_memory()` / `run_mvp_async()`）
- **W4 full 留**: `enumerate_items()` / `enumerate_combos()` / `merge_replace()` / `incremental_load_with_merge(t_minus_days=7)` 占位（本期未实施）

#### Commit 2（#2, 937b034）— W3 DQ assertions

- **目标**: 痛点 2 质量保证（脏数据隔离不阻塞业务）
- **方案**: 3 断言 + quarantine 表 + lark 告警
- **关键文件**: `scripts/etl/assertions.py`（新, ~220 行）

#### Commit 1（#1, 6c0021f）— VERSION drift v0.4.10.1

- **目标**: 修 VERSION/CLAUDE.md/README.md 同步问题
- **方案**: VERSION 0.4.7.4 → 0.4.10（实际 main 状态）
- **教训**: 12 步流程加 "merge 前比对 pytest 输出 vs docs"

---

## 8. CI 6 件套完成度（5/6 done, B1 待）

> **当前状态**：B2/B3/B4/B5/B6 已完成，B1（pytest random order hard assert）待办。

### 8.1 已完成（5/6）

| ID | 名称 | commit | 拦什么 | 教训 |
|----|------|--------|-------|------|
| B2 | pre-commit import 完整性 | `8ca17d9` | 漏 import → CI red | 30/30 red CI 根因 |
| B3 | nightly 健康检查 | `32252e7` | ETL 跑批异常 | 凌晨 2 点发现 |
| B4 | requirements-lock | `eb40690` | 依赖版本漂移 | CI 本地不一致 |
| B5 | test 顺序无关性 | `496f1d8` | conftest 状态污染 | 偶发失败难复现 |
| B6 | 每周 CI 健康报告 | `45f72bf` | 回归识别 | 周日 9 点汇总 |

### 8.2 待办（1/6）

| ID | 名称 | 计划 | 优先级 |
|----|------|------|--------|
| B1 | pytest random order hard assert | `pytest-randomly` 跑 CI 100 次（每次 5min）| P1 |

### 8.3 6 件套的层级关系

```
B6 (weekly report)     ← 长期趋势监控
   ↓
B3 (nightly health)    ← 24h 内异常
   ↓
B5 (test-order lint)   ← 偶发失败
B4 (requirements-lock) ← CI/本地一致
B2 (pre-commit import) ← 防漏
   ↓
B1 (random order assert, 待) ← 兜底强校验
```

### 8.4 关联决策记录

- 见 §2.9 决策记录
- 见 `docs/FOLLOWUPS.md` (D-2 已同步 5/6 done)
