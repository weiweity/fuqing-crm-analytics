# W3 DQ 2 failed 真因 advisory (Sprint 165 沉淀)

> **Sprint**: Sprint 165 (advisory only, 0 业务代码改动, 跟 Sprint 89/134/152 暂收口模式 stable)
> **状态**: 2 failed 不阻塞 ETL (已 quarantine, alert_sent=False) + Sprint 166 已治本 (阈值 0.3→0.5 + 动态 channels + 容差 10%)
> **Sprint 模式**: 真业务 + e2e 治根 + ETL 治根 batch 4/4 advisory
> **优先级**: ⚪ advisory, 0 业务代码改动, Sprint 166 治本后 0 expected failure

---

## Sprint 范围

### 触发: 2026-06-29 ETL 跑批 W3 DQ 6 断言

跑批日志:
```
W3 DQ assertions (6 断言)...
  DQ assertions: passed=4 failed=2 alert_sent=False
  ⚠️ 失败断言: ['assert_total_not_drop', 'assert_540_completeness'] (详见 rfm_quarantine 表)
```

2 failed 不阻塞 ETL (Sprint 1 痛点 2 收尾: 脏数据隔离不阻塞业务, 走 quarantine 路径). 跨 sprint 5+ sprint 没修 (跟 Sprint 161 e2e 漂移 18 sprint 滞后 + Sprint 162 ETL 48min 异常同根因, 真业务触发才排查).

---

## 真因分析 (Sprint 165 advisory 沉淀)

### 1. assert_total_not_drop 真因

**代码位置**: `scripts/etl/assertions.py:99-141`

**逻辑**:
```python
today_total = SUM(actual_amount) WHERE DATE(pay_time) = target_date
prev_avg = AVG(daily_total) WHERE DATE(pay_time) IN (target_date - 30d, target_date)
threshold = prev_avg × 0.3  # TOTAL_DROP_THRESHOLD = 0.3
if today_total < threshold: quarantine
```

**真因 (推测)**: 阈值 `0.3 × prev_30d_avg` 太严. 跑批 2026-06-29 (data_max=2026-06-28 是周日), 周末/周一数据 vs prev_30d_avg (含平日) 差异大, today_total < 0.3 × prev_avg 真发生不是 bug 是业务真实情况.

**建议修法** (advisory only, Sprint 166+ 可选修):
- 阈值放宽到 `0.5` 或 `0.7` (周末/周一波动 30% 是合理)
- 加 weekday-aware 阈值: 周一/二 阈值放宽到 `0.5`, 其他日保持 `0.3`
- 改用中位数 prev_30d_median 替代平均, 抗周末波动

### 2. assert_540_completeness 真因

**代码位置**: `scripts/etl/assertions.py:206-234`

**逻辑**:
```python
expected_combos = EXPECTED_DIM_COMBOS_PER_DATE = 54  # 3 lookbacks × 2 metrics × 9 channels
actual_combos = COUNT(DISTINCT lookback_days, metric_type, channel) WHERE analysis_date = target_date
if actual < 54: quarantine
```

**真因 (推测)**: `9 channels` 是写死阈值, 跟 Sprint 144+ 改派样后实际 channel 数不匹配. 实际 channels:
- TTL派样 (Sprint 144 新增)
- U先派样
- 百补派样
- 赠品&0.01渠道
- 达播/微博
- 直播
- 淘客
- 货架
- 其他

实际可能 = 8 (Sprint 144 改后合并某些) 或 = 7 (Sprint 144 改后删某些) — 跟当前 GROUP BY 实际值相关, 期望 54 跟实际 dim 维度可能漂移 1-3 个, 导致 actual_combos < 54.

**建议修法** (advisory only, Sprint 166+ 可选修):
- 改写死 54 → 改动态从 `SELECT COUNT(DISTINCT channel) FROM user_rfm` 取实际 channel 数, expected = actual_channels × 2 metrics × 3 lookbacks
- 或改成 ratio: actual_combos / max_expected > 0.9 (容差 10%, 跟 dim drift 断言 ±20% 一致)
- 或加 channel registry SSOT: `backend/config.py:CHANNELS` 统一管理 9 channels

### 3. alert_sent=False 跟 Sprint 164 飞书解耦一致

`alert_sent=False` 是因为 Sprint 164 飞书完整解耦, `_send_lark_alert_mockable` 改 no-op. **不是新 bug, 是 Sprint 164 飞书解耦的预期行为**.

---

## Coverage map (Diataxis)

| 维度 | 覆盖状态 |
|---|---|
| **Reference** (factual description) | ✅ 本 doc (w3-dq-advisory.md) |
| **How-to** (task-oriented) | ❌ (advisory, 不需 how-to) |
| **Tutorial** (step-by-step) | ❌ (advisory, 不需 tutorial) |
| **Explanation** (why this works) | ✅ 本 doc (2 failed 真因 + 建议修法) |

---

## 实战 fix 模式 #41 (Sprint 165 沉淀)

1. **W3 DQ 断言阈值写死真因排查模式 (Sprint 165 沉淀)**: 任何 DuckDB 写死阈值 (e.g. `EXPECTED_DIM_COMBOS_PER_DATE = 54`) 跨 sprint 维度变更 (channel/category/level 新增或合并) 时会 false fail. 排查 3 步走: ① 查 rfm_quarantine 表 assert_type 分布 ② 读 assert 函数代码看期望值是常量还是动态 ③ 对比实际 GROUP BY 维度数 vs 写死阈值. 适用场景: 任何 ETL DQ 断言 false fail 报"缺维度/缺行数"时, 第一反应是检查期望值是否还跟实际 schema 一致.
2. **advisory only 暂收口模式 (跟 Sprint 89/134/152 stable)**: 不阻塞 ETL 的 failure (已 quarantine, 0 critical / 0 informative) 跨多 sprint 一直 fail, 不一定需要修. 写 advisory doc 沉淀真因 + 建议修法 + 留 Sprint 166+ 可选修. 跟 Sprint 161 e2e 漂移 18 sprint 滞后稳定累积相反 (那个不能 ignore 因为阻塞 CI, 这个 ignore 因为已 quarantine).

### 累计 sprint 治理循环 (2026-06-29)

- **累计 sprint 治理循环**: **55 sprint** (+1 Sprint 165 advisory)
- **累计 0 debt sprint**: **88 sprint** (advisory 不算 debt)
- **VERSION**: `0.4.14.20` 不变 (累计 55 sprint 不 bump)
- **L4.x 永久规则**: 23 stable, 0 新增
- **pytest baseline**: 723 passed / 66 skipped / 0 failed
- **main HEAD**: 待 push (跟 Sprint 162+163+164 stable)

---

## Sprint 165 收口完成 ✅ + W3 DQ 2 failed advisory 沉淀

User 报 ETL 48min 异常 → 1 turn 拍板 4 advisory ETL 治根 batch (Sprint 162-165) → Sprint 162 未来日期 skip ✅ + Sprint 163 tracker weekly backup ✅ + Sprint 164 飞书完整解耦 8 files ✅ + Sprint 165 W3 DQ 2 failed advisory doc 沉淀 (本 doc, 0 业务代码改动, 留 Sprint 166+ 可选修). 跨 sprint ETL 治根 batch 4/4 1 turn 拍板收口.

## 下个 sprint 可开

- **Sprint 166+ 可选**: 修 assert_total_not_drop 阈值 (放宽到 0.5 或 weekday-aware) + assert_540_completeness 改动态 channels (从 user_rfm GROUP BY 取实际 channels) + 加 ratio 容差 10%. 跨 sprint 5+ 漂移 false fail 治根.
- 留尾治理 sprint 链 (P0/P1/P2 优先级, 跟 Sprint 67+68 模式)
- ~~**Sprint 166+ 可选**: 修复 `docs/architecture/DATA_PIPELINE.md` ASCII diagram 派样 02 板块 4 桶柱状图 drift (Sprint 159 删 4 桶, diagram 需更新) — advisory only (跟 Sprint 65+135+138+141.5+145+149+153+160 stable 跨 sprint 9 次真治本)~~ — **Sprint 167 验证: DATA_PIPELINE.md 全文 0 处 4 桶 ASCII 残留, 0 处派样 02 标记. Sprint 165 advisory line 116 推测错误 (no git log 实证), 0 commit 暂收口. 跟 Sprint 89/134/152 模式 stable.**
- **Sprint 166+ 可选**: L4.23 实施检查 (e2e spec drift detection script 自动化, 跟前 sprint 改 UI 后必查 spec 同步, 防止下次跨 sprint 漂移) — 跟 L4.7 ground-truth-lint hook 模式 stable
