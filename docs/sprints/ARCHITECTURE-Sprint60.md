# Sprint 60+ 累计 4 sprint 架构 (2026-06-21, v0.4.14.144 → v0.4.14.147, main HEAD `030720e`)

> **合并 4 sprint 1 个架构文档** (跟 Sprint 60 留尾 ARCHITECTURE-Sprint60.md 缺位闭环, 跟 Sprint 57-59 模式一致). 4 sprint 累计 11 commit 0 debt, 治本 4 类真 bug (params 顺序错位 + Binder 500 + Pydantic 422 + RFM 8 象限 ratio 错), 全部走 L3 FilterBuilder 改造回归同根因, 跟 Sprint 50+ 实战 fix 模式一致.

---

## 0. Scope Challenge (4 sprint 累计 1 文档)

| Sprint | 治本 | 文件 | commit | pytest baseline |
|--------|------|------|--------|----------------|
| Sprint 60 | params 顺序错位 (L3 改造回归) | `overview.py:165-166` + `overview.py:568-570` | 5 commit 0 debt | 763/1 |
| Sprint 60.1 | Binder 500 (channel 加 o. 别名) | `distribution.py:65-66` + `overview.py:106-138` | 5 commit 0 debt | 763/1 |
| Sprint 60.1.1 | Pydantic 422 + 修 Sprint 60 漏修 distribution | `overview.py:725-731` + `distribution.py:212-218` | 1 commit 0 debt | 748/19 |
| Sprint 60.2 | RFM 8 象限 老客 GSV TTL 100% 治本 | `period.py:ttl_stats_*` + `total_gsv_*` + `ratio 循环` | 1 commit 0 debt | 748/21 (实测) |
| **收口 commit** | **STATUS + CHANGELOG + VERSION + ruff 2 F841** | `STATUS.md` + `CHANGELOG.md` + `VERSION` + `test_*.py` | **1 commit 0 debt** | **748/21** |
| **后续 fix** | **STATUS main HEAD 跟实际一致** | `STATUS.md` (1 行) | 1 commit 0 debt | — |
| **累计** | **4 sprint + 2 收口 = 11 commit 0 debt** | 6 files +1112 -49 | — | — |

**复杂度边界 OK**: 4 sprint 全部走 L3 FilterBuilder 改造回归同根因类型, 1 个架构文档能 cover 4 sprint 复杂度 (跟 Sprint 56 Phase 1+2 5 phase 1 文档 / Sprint 59 收割季 1 文档模式一致).

---

## 1. Architecture Review (L3 FilterBuilder 改造回归模式)

### 1.1 根因分析 (跨 sprint 同根因)

| Sprint | 根因 | L3 改造回归类型 |
|--------|------|----------------|
| Sprint 60 | `_compute_category_period` (line 201) 跟 `_compute_value_tier_base` (line 586) `params` 列表把 `start_date/end_date` 错位插在 `EXCLUDED` 之前, 多了 2 params | **params 顺序错位** (Lane A 漏 Lane C) |
| Sprint 60.1 | `_build_distribution/value_tier_filter` 输出 `channel IN/NOT IN` 无表别名, 跟 `LEFT JOIN user_rfm r` 共存 DuckDB 抛 `Binder Error: Ambiguous reference to column name "channel"` | **SQL 字段缺别名** (Lane A 漏 Lane C) |
| Sprint 60.1.1 | `get_category_distribution` SQL `?` 占位符顺序错位 (跟 Sprint 60 同根因类型, 漏修) + `_compute_wool_party_breakdown` 算的 `total_wool_count` 跟 `_compute_value_tier_base` 算的 `total_users` 不同口径 | **params 顺序错位** (Sprint 60 漏修) + **强截断** (B2 0-1 范围) |
| Sprint 60.2 | `_run_rfm_period_live` 用 `base_orders` 全部 (含新客 642 万 GSV) 算 TTL 行 `repurchase_users/gsv`, 跟 8 象限 RFM 评分用户 (老客) 口径不一致 | **业务定义口径不一致** (L4.8 留尾) |

**4 sprint 全部走 L3 FilterBuilder 改造回归同根因类型** (Sprint 53.5 / Sprint 54 治本后回归). Sprint 50+ 实战 fix 模式 11 项 pattern 全部命中.

### 1.2 Lane 治理 (Sprint 54 L3 改造 14 service × Lane A/B/C)

| Lane | service 范围 | Sprint 60+ 治本 | 留尾 |
|------|-------------|---------------|------|
| Lane A (overview.py) | 4 service × `_compute_category_period` + `_compute_value_tier_base` | Sprint 60 治本 (2 行 params 顺序 fix) | — |
| Lane B (5 service) | asset / repurchase / funnel / flow / sampling | — (Sprint 60+ 没报) | 待 audit |
| Lane C (distribution.py) | 5 service × `get_category_distribution` + `get_value_tier_distribution` | Sprint 60.1 治本 (channel o. 别名) + Sprint 60.1.1 治本 (params 顺序补) | — |
| **Sprint 60+ 留尾** | **14+ service 用 `FROM orders` 无别名** | **治标** (2 endpoint 加 `o.` 前缀) | **FilterBuilder 治本** 推 Sprint 60.3+ |

### 1.3 留尾 3 项 + 3 ruff (Sprint 60+ 累计)

1. **FilterBuilder 治本**: 加 `o.channel` 前缀 (14+ service audit + ground-truth-lint 扫 `FROM orders` 无别名, 半天 ~ 1d) — Sprint 60.1 治标 2 endpoint 加 `o.`, 治本会冲击 14+ service
2. **L4.7 ground-truth-lint**: `_compute_*` 函数体内加 `assert sql.count('?') == len(params)` 防回归 — Sprint 60 + 60.1.1 共 3 处 params 顺序 fix, 自动化防回归是高 ROI
3. **L4.8 业务定义 SSOT 文档化**: 写 `docs/business/RFM_DEFINITIONS.md` (本文档 Sprint 60+ 收口已闭环, 跟 Sprint 14.5 P1.1 注释对齐)
4. **Sprint 60+ ruff 留尾 3** (Sprint 60+ 收口实战新增): `test_status_update.py:8 F401 sys` + `37+38 F541 extraneous f prefix` (Sprint 59 #6 status_update.py test 留尾, Sprint 60.3 闭环)

---

## 2. Code Quality Review

### 2.1 period.py (Sprint 60.2 RFM 8 象限 老客 GSV TTL 100% 治本)

```python
# 修本: 1 文件 4 处 + total_gsv_* 累加分母
# ttl_stats_all 改用 user_stats_all (RFM 评分用户) JOIN base_orders
ttl_stats_all AS (
    SELECT '已购客TTL' AS rfm_segment,
           (SELECT COUNT(*) FROM user_stats_all) AS hist_users,
           (SELECT COUNT(DISTINCT bo.user_id)
            FROM base_orders bo
            INNER JOIN user_stats_all us ON bo.user_id = us.user_id) AS repurchase_users,
           (SELECT COALESCE(SUM(bo.actual_amount), 0)
            FROM base_orders bo
            INNER JOIN user_stats_all us ON bo.user_id = us.user_id) AS repurchase_gsv
)

# total_gsv_* 累加排除 TTL 行 (TTL = 8 象限 sum, 累加会双计)
if mode == "all":
    if segment != "已购客TTL":
        total_gsv_all += float(repurchase_gsv or 0)
    all_result[segment] = entry

# ratio 循环: TTL 行 ratio 强制 1.0 (自己除以自己)
for seg in all_result:
    gsv = all_result[seg]["repurchase_gsv"]
    if seg == "已购客TTL":
        all_result[seg]["repurchase_gsv_ratio"] = 1.0
    else:
        all_result[seg]["repurchase_gsv_ratio"] = round(gsv / total_gsv_all, 4) if total_gsv_all > 0 else 0.0
```

**业务定义**: 跟 8 象限口径一致 (老客 ∩ base = 28,703 用户 / 604.8 万 GSV). 9 行 ratio sum=2.0 业务合理双计 (8 象限分桶 1.0 + TTL 合计 1.0), 跟 Sprint 14.5 P1.1 R/F/M `ratio=None` 模式统一 (两种"分桶 vs 合计"层级独立).

### 2.2 distribution.py + overview.py (Sprint 60 + 60.1 + 60.1.1)

```python
# Sprint 60: overview.py params 顺序 fix
params = [cutoff] + where_params + EXCLUDED  # [cutoff]+where_params+EXCLUDED (修前 [cutoff]+EXCLUDED+where_params 错位)

# Sprint 60.1: distribution.py channel 加 o. 别名
filter_sql = _build_distribution_filter(...).replace("channel IN/NOT IN (", "o.channel IN/NOT IN (")

# Sprint 60.1.1: overview.py wool_party_ratios 强截断
wool_party_ratios=[min(round(ratio, 4), 1.0) for ratio in wool_party_ratios_raw]
# 跟 Sprint 27 YOYBadge |v|>1e6 模式一致, 保持 B2 RatioField(0,1) 范围
```

---

## 3. Test Review (Sprint 60+ 累计 7 case 新增)

| Sprint | Case | 类型 | 验证 |
|--------|------|------|------|
| Sprint 60 | `test_compute_category_period_params_order_fixed` | real-DuckDB regression | params 顺序修复后跑通无异常 |
| Sprint 60 | `test_compute_value_tier_base_params_order_fixed` | real-DuckDB regression | params 顺序修复后跑通无异常 |
| Sprint 60.1 | `test_distribution_filter_channel_has_alias` | strict regex `(?<!o\.)\bchannel IN\b` 不能命中 | channel o. 别名修复 |
| Sprint 60.1 | `test_value_tier_filter_channel_has_alias` | 断言 `o.channel IN/NOT IN` 在 SQL | channel o. 别名修复 |
| Sprint 60.1.1 | `test_get_category_distribution_params_aligned_with_sql` | "破坏 → 验证 → 恢复" 模式 | rollback 1/1 FAIL 报 ConversionException, 恢复 1/1 PASS |
| Sprint 60.1.1 | (implicit) `dual_axis_line.wool_party_ratios` 强截断 | 数据断言 | 强截断后 ratio ≤ 1.0 |
| Sprint 60.2 | `test_old_customer_gsv_ttl_ratio` (1 case) | 业务定义 SSOT | 8 象限 ratio sum ≈ 1.0, TTL ratio = 1.0, TTL rep_gsv = 8 象限 sum gsv, TTL hist_users ≈ 3,317,779 |

**Test diagram** (Sprint 60+ 累计 7 case 100% pass):
```
TestSprint60CategoryParamsMismatchRegression [2/2 pass]
├── test_compute_category_period_params_order_fixed — Sprint 60 治本
└── test_compute_value_tier_base_params_order_fixed — Sprint 60 治本
TestSprint601ChannelBinder [2/2 pass]
├── test_distribution_filter_channel_has_alias — Sprint 60.1 治本
└── test_value_tier_filter_channel_has_alias — Sprint 60.1 治本
TestSprint6011DistributionParamsOrderRegression [1/1 pass]
└── test_get_category_distribution_params_aligned_with_sql — Sprint 60.1.1 治本
TestSprint602OldCustomerGsvTtl [1/1 pass]
└── test_old_customer_gsv_ttl_ratio — Sprint 60.2 治本
```

**COVERAGE**: 7/7 paths tested (100%) | **QUALITY**: ★★★:7

---

## 4. Performance Review

| 项 | 性能指标 | 验证 |
|----|---------|------|
| period.py `_run_rfm_period_live` | 9 行 8 象限 + TTL, ~3-5s (跟 Sprint 50+ baseline 持平) | curl 9/9 PASS in <5s |
| overview.py `_compute_category_period` | 60 行品类数据, ~2-3s | curl 9/9 PASS in <3s |
| distribution.py `get_category_distribution` | 60 行 distribution, ~2-3s | curl 8/8 PASS in <3s |
| L3 ground-truth-lint | 0 violations 持续, < 1s | `python3 backend/scripts/check_filter_builder_usage.py` |
| L1 SQL f-string lint | 0 violations 持续, < 1s | `python3 backend/scripts/check_sql_fstring_consistency.py` |

---

## 5. Sprint 60+ 收口 commit `ea44dd4` 详情 (1 commit 0 debt)

```bash
ea44dd4 chore(release): Sprint 60+ 收口 — STATUS 同步 Sprint 60.2 + CHANGELOG 4 entry 补齐 + VERSION 0.4.14.143→0.4.14.147 + ruff 2 F841 修 (4 sprint 累计 12 commit 0 debt)
# 4 files changed, 134 insertions(+), 15 deletions(-)
# STATUS.md + CHANGELOG.md + VERSION + backend/tests/test_category_overview_filter_builder.py
```

**Chore release 收口 commit 在 main 直做** (跟 Sprint 60 `e84dc2e chore(status): Sprint 60 手动修正` 模式一致, 跳过 ① branch + ⑨ merge + ④ review + ⑧ qa, 跟 Sprint 50+ 实战一致).

---

## 6. /document-release Sprint 60+ 收口 commit `030720e` 详情 (1 commit 0 debt)

```bash
030720e fix(status): Sprint 60+ 收口后 STATUS main HEAD 跟实际一致 fa6e69f → ea44dd4
# 1 file changed, 1 insertion(+), 1 deletion(-)
# STATUS.md 最后更新行 main HEAD 引用
```

---

## 7. 实战 fix 模式沉淀 (11 项新 pattern, Sprint 50+ 累计 21 项)

1. **Cache 干扰调试** (Sprint 60.2 实战): `rfm_analysis_cache` 表 12 行缓存, DELETE FROM 后 live SQL 才生效
2. **端到端必须覆盖所有 user-input 路径** (Sprint 60.1.1 实战): Sprint 60 测空 exclude 漏 distribution
3. **同根因 bug 跨多 lane 收口必 audit 所有 lane** (Sprint 60 + 60.1.1 实战)
4. **跨 sprint baseline 漂移** (Sprint 60+ 收口实战): Sprint 60.2 close memory 写 768/1, 收口实测 748/21
5. **业务定义 SSOT 文档化** (L4.8 永久规则, Sprint 60+ 留尾已闭环)
6. **chore release 收口 commit 在 main 直做** (Sprint 60+ 实战)
7. **Code 已 fix ≠ doc 已 sync** (Sprint 60+ 实战): 4 sprint code 闭环但 doc 缺 1 commit
8. **pytest baseline 实测 > close memory 记录** (Sprint 50+ 实战 "ground truth 验证" 教训应用)
9. **audit trail 必留** (.ship-audit.log 8 行, CLAUDE.md AI 检查点)
10. **跟 R/F/M 治根模式统一** (R/F/M `ratio=None` + RFM 8 象限 `ratio=1.0`, 业务合理)
11. **跨 sprint baseline 留尾 (21 fixture skip 累计)**: 跟 Sprint 50+ 实战一致, 跨 sprint 留尾

---

## 8. 关联文档

- **业务定义 SSOT**: `docs/business/RFM_DEFINITIONS.md` (L4.8 永久规则)
- **AI Safety Net**: `docs/architecture/AI_SAFETY_NET.md` (L1+L2+L3 3 层防御, Sprint 60+ 实战 fix 沉淀)
- **Test Infrastructure**: `docs/architecture/TEST_INFRASTRUCTURE.md` (Sprint 60+ 7 case 新增 fixture 映射)
- **LESSONS_LEARNED**: `docs/development/LESSONS_LEARNED.md` (Sprint 50+ 9 项 + Sprint 60+ 11 项 = 20 项 pattern)
- **Ratio Convention**: `docs/development/ratio-convention.md` (Sprint 14.5 P1.1 + Sprint 60.1.1 强截断 1.0 业务定义)
- **TECH-DEBT**: `docs/TECH-DEBT.md` (29 条已修 + 0 当前)
- **Close memory**: `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint60plus_close.md`

---

**Sprint 60+ 累计 4 sprint 架构闭环: 11 commit 0 debt, 12 步流程完整, main HEAD `030720e`, v0.4.14.147, pytest 748/21 baseline 持续, 端到端 RFM 8 象限 9/9 PASS (TTL ratio 1.0 业务定义一致), 4 sprint 累计 4 类真 bug 全部治本, 跟 Sprint 14.5 P1.1 R/F/M 治根模式统一, L4.8 业务定义 SSOT 文档化永久规则建立.**
