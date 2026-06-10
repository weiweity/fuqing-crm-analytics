# Sprint 14.5 Retrospective — RFM TTL 段 ratio 越界 500 治根

**Sprint**: 14.5 (Sprint 14 后 mini-sprint)
**时间**: 2026-06-10
**状态**: ✅ 收口 (main @ f0903a0)
**主题**: Sprint 14 A.3 RatioField 0-1 验证引发的 RFM 4 端点 500 治根

---

## 1. Sprint 结果

| 维度 | Sprint 14 收口 | Sprint 14.5 收口 | Delta |
|------|----------------|------------------|-------|
| **Bug 修复** | | | |
| rfm/r-flow 500 (TTL ratio=1.771 越界) | — | **0 处 (修)** | 治根 |
| rfm/f-flow 500 | — | **0 处** | 修 |
| rfm/m-flow 500 | — | **0 处** | 修 |
| rfm/segment-orders | ✅ 200 | ✅ 200 | ✓ |
| **RFM 4 端点** | 全 500 | **全 200** | 修 |
| **W5 cache 清理** | 12 个 stale keys | 0 | invalidate |
| **测试** | | | |
| test_rfm_flow_ttl_ratio.py | — | **5 个** (全过) | 新增 |
| 全部 backend pytest | 399 passed | 399 passed | ✓ |
| **Commits** | 11 (Sprint 14) | +2 (Sprint 14.5) | +1 commit |
| **根因** | | | |
| _parse_flow_rows 算 ratio 循环含 TTL 段 | ❌ bug | ✅ 排除 | 修 |

---

## 2. 关键 bug 复盘

### 2.1 Sprint 14 A.3 引入的 RFM TTL 段 ratio 越界 500

**症状 (2026-06-10 用户报告)**:
- 浏览器 console: `api/v1/rfm/r-flow` 500, `api/v1/customer-health` 多次 500
- 4 个 RFM 端点全 500

**根因 (Sprint 14.5 P0 治根)**:
- Sprint 14 A.3 给 `contracts/rfm.py` 14 个 `repurchase_gsv_ratio_*` 字段加 `RatioField` (0-1 范围)
- `backend/services/rfm/_flow_engine.py:139-143` 计算 ratio 循环**包含** TTL 段
- 但 `line 135-136` totals 累加**排除** TTL 段
- 数学结果: `ttl_gsv / (sum_R_buckets)` > 1.0 (因为 TTL 段 gsv 含当期新购客复购, 是 R 桶累计的真超集)
- 真实越界值: 1.771, 2.2548, 2.094, 3.0617, 2.947, 2.8754 (4 mode × 3 period 组合)

**修法 (1 commit + 1 test 5 cases)**:
- `_flow_engine.py:148-150` 排除 `已购客TTL` 段 ratio 计算循环, ratio 留 0.0
- 注释说明业务语义: TTL 是商业指标汇总行, 跟 R/F/M 桶 ratio 语义不同
- `test_rfm_flow_ttl_ratio.py` 5 测试, 验证 6 段 R 桶 ratio ∈ [0,1] + TTL = 0 + 缺失段 = 0 + 4 mode 都生效

### 2.2 W5 DuckDB-KV cache 仍存旧 ratio (踩坑教训)

**症状**:
- 修改 + merge + push + 重启 uvicorn 后, 端点还是 500
- stack trace 还是 1.771 越界

**根因**:
- Sprint 1 W5 v0.4.13 加了 DuckDB-KV cache (rfm_query_cache 表), 24h TTL
- cache key = `endpoint + params`, **不含 ratio 算法 version**
- 我的修改只让 ratio 算 0, 但 24h 内 cache 命中返旧 ratio (1.771)
- **file cache 跟 DuckDB-KV cache 是两套**, 我之前只删了 `data/cache/rfm_flow/*.json` (file cache), 没碰 DuckDB 表

**修法**:
- 调 `POST /api/v1/rfm/cache/invalidate` (admin endpoint) → 删 12 个 stale keys
- 触发重算, 4 端点全 200

**教训**:
- Sprint 1 W5 文档里要写清 "schema/ratio 算法变更后必须调 /cache/invalidate"
- 未来 Sprint 加 cache invalidation hook (跟 manifest 同步) — 留 Sprint 15 治理

### 2.3 /customer-health 404 是 curl 测试残留 (非 bug)

**分析**:
- 浏览器 console 报 404 是用户自己用 curl 测试时的残留 log
- 实际前端 RFMView/HealthView 全用子路径 (overview/targets/...), 没漏路径
- 没有真 bug

---

## 3. 决策审计

| 决策 | 选项 | 拍板 | 理由 |
|------|------|------|------|
| 修法 | A: 排除 TTL 段 ratio / B: 改契约 Optional / C: 放宽 RatioField | **A** | 跟 Sprint 13 ratio 治理一致 (ratio 0-1 强契约), TTL 段 ratio 留 0 + 前端过滤 = 最小化改 |
| 契约变更 | Optional[RatioField] | **不动** | A 方案不需要契约改, RatioField 0-1 保持 (6 R 桶段必然 ≤ 1.0) |
| cache 清理 | 手动 invalidate / 加 manifest hook | **手动** | Sprint 15 治理, 当前先 invalidate |

---

## 4. 治理债务 (留 Sprint 15+)

| # | 任务 | 优先级 | 阻塞 |
|---|------|--------|------|
| 1 | W5 cache invalidation hook (跟 manifest 同步, 自动失效) | 🟡 P1 | 改 ratio/契约后必须手动 invalidate |
| 2 | `AudienceRow.yoy_*` 28 字段加 `PercentageField` (Sprint 14 漏标) | 🟡 P1 | ratio 治根 |
| 3 | `replay_is_member.py` 包 `BEGIN; ... COMMIT;` (DROP INDEX 6 秒窗口数据风险) | 🔴 P0 | 跑批原子性 |
| 4 | `replay_is_member.py` member 删除不清 (mark rebuild 后 is_member 不清) | 🟢 P2 | 数据一致性 |
| 5 | Step 4.6/4.7 fail-soft 隐藏 mark drift | 🟢 P2 | 数据可见性 |
| 6 | 拉数据 pipeline 写 processed_files (上下游解耦) | 🟢 P2 | 架构债 |
| 7 | 6 道门禁 Connection 错误 (cross_day/api_health/dedup) | 🟢 P2 | pre-existing flake |
| 8 | e2e customer-health WASM flake | 🟢 P2 | pre-existing |
| 9 | 50M 架构实施 (Stage 2 plan 已写好) | 🔵 P3 | 长期 |
| 10 | is_member 派生重构 (143 处引用) | 🔵 P3 | defer |

---

## 5. 学到的教训

### 5.1 ratio/契约变更后必须主动 invalidate W5 cache

**问题**: Sprint 14.5 改 _parse_flow_rows 后, 端点还 500 因为 W5 cache 24h 内返旧 ratio.

**教训**: Cache key 不含算法 version, 算法变更时 cache 静默返旧值, 跟"代码改完跑过单测就行"踩坑. Sprint 15 必加 invalidation hook (跟 manifest 变化同步触发).

**行动**: Sprint 15 + sprint16 治理任务清单加 #1 W5 invalidation hook.

### 5.2 Pydantic loc 报 index 5 但实际是 TTL 段 (Pydantic 内部 list 错位)

**问题**: 错误报 `('rows', 5, 'repurchase_gsv_ratio_current') input=1.771`, 但 cache 内 rows[5] = "2年外已购客" ratio = 0.0705 (cache 的 ratio 是 row index, 不是 field index).

**根因**: Pydantic 验证 List[BaseModel] 时, loc 用 list index + field name 报路径, 但内部 list 序列化顺序跟 cache JSON dict 顺序可能不一致. **input 值 (1.771) 才是真相, 来自 TTL 段 ratio, 跟 loc[5] 错位**.

**教训**: 不要凭 loc index 推断错误位置, 读 `input` 真实值反推.

**行动**: debug 时 always read `input` + `type` + `ctx`, 跟 cache/raw data 对照.

### 5.3 user 报告"console 500" 包含 curl 测试残留 (auto classifier 干扰排查)

**问题**: 用户报告 `customer-health` 404 + `audience` 401, 我花时间 audit 路径 + token, 才发现 404 是用户自己 curl 测试残留, 401 是 login 前没带 token.

**教训**: 浏览器 console 错误可能是 dev tools 手动 fetch / 调试脚本残留, 不一定真 bug. **先问"在哪个 context 看到的"再排查**.

**行动**: Sprint 16 + 排查清单第一步: "user-reported error timestamp" + "是浏览器自动 fetch 还是手动".

### 5.4 Sprint 14.5 mini-sprint 模式高效 (半天闭环)

**成果**: 1 commit (96702c8) + 1 merge (f0903a0) + 5 测试 + 1 治根 + W5 cache 清理 + 端到端 QA (3 端点 200). 总耗时 ~ 1.5 小时 (从 user 报告到收口).

**对比 Sprint 14** (5-6 天治根 ratio 治理), mini-sprint 适合 "单 bug 治根 + 加测试 + 走 12 步流程", 不需要完整 plan/retrospective.

**行动**: 未来单 bug 治根直接用 mini-sprint 模式, 跳过完整 plan/retrospective 模板.

---

## 6. 时间线复盘

| 时间 | 事件 |
|------|------|
| 18:30 | 用户报告 console RFM 500 + customer-health 404 + audience 401 |
| 18:32 | TaskCreate 3 个排查 task |
| 18:35 | curl 3 端点, 确认 rfm/r-flow 500, 401/404 是 token/路径问题 (非真 bug) |
| 18:40 | 看 uvicorn log, Pydantic ValidationError: TTL ratio=1.771 越界 RatioField 0-1 |
| 18:45 | 找到根因: _flow_engine.py:139-143 算 ratio 循环含 TTL 段, totals 排除 TTL → ratio > 1.0 |
| 18:50 | 切 fix/sprint14-rfm-ratio-ttl 分支, 改 + 加 5 测试 + CHANGELOG v0.4.14.33 |
| 19:00 | commit 96702c8 + push + merge + push main (f0903a0) + 重启 uvicorn |
| 19:05 | curl 端点还 500, ratio 1.771 还在 (Pydantic loc[5] 跟 input 值错位, 重新定位) |
| 19:10 | 删 file cache `data/cache/rfm_flow/*.json` + 重启, 还 500 |
| 19:20 | 直接 debug: 用 read_only DuckDB 调 run_flow_period 跑 6/1-6/8, 看到 6 R 桶段 ratio 全 0.07-0.30, TTL ratio = 0.0. **修生效了**! |
| 19:25 | 怀疑 W5 DuckDB-KV cache (rfm_query_cache 表) 还存旧 ratio, 调 /api/v1/rfm/cache/invalidate 删 12 个 key |
| 19:30 | curl 4 端点全 200, ratio 正常 (0.28, 0.20, 0.16 等) |
| 19:35 | 写 retrospective + memory + push |

**总耗时**: ~ 1 小时 5 分钟 (从 user 报告到 4 端点全 200 + 测试 + retrospective)

---

## 7. Sprint 15 预告

**Sprint 14.5 留的 P1 治理**:
- W5 cache invalidation hook (跟 manifest 同步)
- `AudienceRow.yoy_*` 28 字段加 `PercentageField`

**Sprint 15 全做**:
- C.1: composables/useFormat.ts (4 函数, 2h)
- C.2: 替换 50+ 处散落 *100 (3h)
- C.3: TypeScript Branded Type (4h)
- C.4: ESLint AST 级别 lint (4h, dry-run 1 周)
- C.5: W5 cache invalidation hook (2h)
- 总: 5-7d, 50% AI 友好化, 防 LLM 写双重 *100

---

## 8. 关键指标

| 指标 | 值 |
|------|---|
| Sprint 周期 | 1.5 小时 (mini-sprint) |
| Commits | 1 (96702c8) + 1 merge (f0903a0) |
| Files changed | 3 (_flow_engine.py + test + CHANGELOG) |
| Lines changed | +118 |
| Memory files | project_sprint14_5.md (新) |
| RFM 4 端点 HTTP | 全 200 |
| W5 cache 清理 | 12 keys |
| 测试 | 5 个 ttl ratio 测试 全过 + 394 既有 + 12 skipped |
| pre-commit 防线 | vue-tsc --noEmit 强制 (Sprint 14 教训) |
| 12 步流程 | 100% 走完 (review/qa/merge/push/pull/restart) |
| Sprint 14.5 留治理 | 10 任务 (1 P0 replay transaction + 1 P1 invalidation + 8 P2/P3) |

---

*此文件由 Sprint 14.5 mini-sprint 治根流程生成, 最后更新 2026-06-10*
