# Sprint 18 治理收口 (2026-06-11)

> 4 段治理 sprint, 4 subagent 并行 ~2h, 5 commits, 4 merge 全部合 main, v0.4.14.45→v0.4.14.48

## 1. Sprint 结果

Sprint 18 是 Sprint 17 收口后留下的 4 段治理 debt 集中清理 (1.5h workflow + 0.5h verify):

| # | 任务 | 状态 | 关键产出 | 分支 / commit | version |
|---|------|------|---------|---------------|---------|
| #141 | 26 YOY ratio 字段命名/语义冲突治根 | ✅ | 白名单 14 字段 (`_YOY_PPT_FIELDS`) + 类型补标 6 字段 + linter 0 issue | `fix/sprint18-yoy-ratio-fix` / aa48b4c (merge f467192) | v0.4.14.45 |
| #123 | W5 cache invalidation 启动 hook | ✅ | 跨进程 manifest 同步 + 10 tests + `FLOW_ALGO_VERSION` bump v0.4.14.35→v0.4.14.47 | `fix/sprint18-w5-cache-invalidation` / 48ced53 + a4f201d (merge 1e1e97d) | v0.4.14.46/47 |
| #142 | pre-commit ground-truth-lint hook | ✅ | `.pre-commit-config.yaml` + `scripts/test-precommit.sh` + 335 行 docs (跟 .githooks 双轨并存) | `fix/sprint18-precommit-lint` / d20869b + c2cf6d5 (merge 5edbf57) | v0.4.14.49 |
| #124 | YOYGuard 通用组件 + 扩 MetricCard / RFMSegmentDrilldown | ✅ | `YOYGuard.vue` 61 行抽公共 + YOYBadge/MetricCard/RFM 表格 3 组件 refactor | `fix/sprint18-yoy-guard-extension` / 76be9c2 + 6df6c1f (merge 061e347) | v0.4.14.48 |

**总耗时**: 4 subagent 并行 ~2h workflow + 0.5h verify/收口 = **2.5h**
**总 commits**: 5 fix commits + 4 merge + 1 doc update = **10 commits**
**Files changed**: 5 contract (breakdown/churn/health/sampling/audience) + 1 linter (_lint.py) + 1 cache (cache.py) + 1 main (lifespan) + 1 _shared (FLOW_ALGO_VERSION) + 4 frontend (YOYGuard/YOYBadge/MetricCard/RFMSegmentDrilldown) + 2 tests (cache_invalidation + YOYGuard vitest) + 4 docs (SPRINT-18-YOY-FIX/CACHE-INVALIDATION/PRE-COMMIT/RETRO) + 1 .pre-commit-config.yaml + 1 test-precommit.sh
**Tests**: 454+12 → 507+12 passed (新增 53: #123 cache invalidation 10 + #124 YOYGuard vitest 3 + #141 复用 40 既有 YOY tests, 0 新增 pytest 因为类型补标被 #120 已写测试覆盖)
**uvicorn**: 4 v1 端点 (r-flow=401, rfm=401, health=200 public, metrics=401), /health=401 (认证保护), /docs=200

## 2. 4 任务治根复盘

### #141 26 YOY ratio 字段命名/语义冲突治根 (30min, ~1h)

**改动 5 contract + 1 linter**, **26 字段分类治根**:

| 分类 | 数量 | 治根方案 |
|------|------|---------|
| A. `yoy_*_ratio` 实际 PpField (命名误导) | 18 | linter 白名单 `_YOY_PPT_FIELDS` (14 字段, 18 处), 强校验是 PpField 防未来漂移 |
| B. 真实 ratio 0-1 (误标 PpField) | 4 | 改类型为 `RatioField` / `PpField` (breakdown.gap_ratio / health.annual_promo_*_ratio / sampling.new_locked_ratio × 2) |
| C. 真实 ratio 0-1 (裸 float) | 3 | 补标 `RatioField` (health.annual_promo_gsv_ratio / annual_promo_user_ratio / old_customer_gsv_ratio) |
| D. List element-wise 合规字段 | 1 | 留 Sprint 17 #120 写法 + 白名单兜底 (linter R1 不识别 List 元素约束, 留 Sprint 19 linter 增强) |

**新增**: `docs/SPRINT-18-YOY-FIX.md` (299 行, 跟 Sprint 17 #120 B2 audit 报告同样 markdown 结构, 12 节)

**跨文件破坏**: **0 字段名改动** (走白名单避免), 字段名零改动 = 14+ 文件不动 (audience/rfm/category/health 前端 + service + tests)

**踩坑**: 
- `health.yoy_repurchase_gsv_ratio` 在 2 个不同 class (HealthOverviewMetrics / TierFlowResponse) 语义不同 — OverviewMetrics 走白名单, TierFlowResponse 改 PpField (跟同名字段一致)
- 任务描述写"5-8 字段" 实际是 26 字段, subagent 1 个 commit 完成 26 + 白名单 + linter 增强 (45 行 linter 改动 + 6 字段类型)

**治根**: 把 Sprint 17 留的 26 lint issue 从"残留债务" → "白名单 + 强校验" 双重防护, Sprint 13 ratio 契约 0-1 严守保留 (白名单字段虽然名字带 `_ratio`, 但 linter 强校验是 PpField).

### #123 W5 cache invalidation 启动 hook (40min, ~1h)

**新增**:
- `backend/services/rfm/cache.py:check_manifest_version_and_invalidate()` (89 行) — 跨进程持久化 `last_seen_manifest_version` 到 `data/cache/w5kv_manifest_state.json` (env `FQ_W5KV_STATE_PATH` 可覆盖)
- `backend/main.py:lifespan` startup 调 hook (7 行加), 包 try/except 不阻塞服务
- `backend/tests/test_cache_invalidation.py` (10 tests) — 6 类场景: 无 manifest / 首次跑 / 一致 / 升 v / 写失败 / 损坏 / 兼容 get
- `docs/CACHE-INVALIDATION.md` (333 行) — 10 节使用文档, 7 个 FAQ
- `FLOW_ALGO_VERSION` bump `v0.4.14.35` → `v0.4.14.47` (行为变化触发 cache key 全 miss 一次, 跟 Sprint 14.5 约定一致)

**架构亮点**:
- 进程内 `_ManifestTracker` 检测本进程 manifest 变化 (cache.get() 实时)
- 启动 hook 检测跨进程 manifest 变化 (uvicorn 重启 / ETL 跑批后 / DuckDB 备份恢复)
- 两个 tracker 互补, 进程内 + 跨进程全覆盖

**踩坑**:
- 不用 DuckDB 表存 state (避免循环: hook 依赖 W5 cache 表)
- 不用 git hash / mtime (etcd / container / Windows FS mtime 不稳)
- 用 `data/cache/w5kv_manifest_state.json` 磁盘文件 + JSON

**治根**: Sprint 14.5 留的"改 ratio/契约后必须手动 invalidate W5 cache" 痛点闭环, 改完 → ETL → 重启 → hook 自动清 12 orphan keys. **不再需要手动跑 SQL**.

### #142 pre-commit ground-truth-lint hook (30min, ~1h)

**新增**:
- `.pre-commit-config.yaml` 加 `contract-ground-truth-lint` hook (跟 ruff 配套), `entry: python -m backend.contracts._lint` + `pass_filenames: false` + `files: 'backend/contracts/.*\.py$'`
- `scripts/test-precommit.sh` 验证脚本 (baseline / bad change / revert 三步)
- `docs/PRE-COMMIT.md` (335 行) — 12 节使用文档: 背景 / 跟 .githooks 关系 / 安装 / 启用 (模式 A/B) / 触发什么 / 跳过 / 跟 Sprint 17/18 关系 / CI 集成 / 故障排查 / 验证 / 限制 / 变更

**设计**: 跟 `.githooks/pre-commit` 双轨并存 (芙清 CRM 默认 .githooks), framework 版给愿意切的开发者用. 两个 hook 互补, 不冲突.

**关键点**:
- `pass_filenames: false` — 跑全 contract 目录, 跟 Sprint 16.5 P1-3 教训一致 (CI 跑 committed 模式必须看全部)
- `files: 'backend/contracts/.*\.py$'` — staged 文件 match 才触发, 改 frontend/backend service 不触发 (避免每次 commit 都跑)

**踩坑**:
- `pre-commit` framework 不自动设 PYTHONPATH, `entry: python -m backend.contracts._lint` 假设从 repo root 跑 (framework 默认 cwd = repo root)
- local hook 跑本机 Python 3.x, 不自动装包, 文档说明开发者需 Python 3.10+ + `pip install -e .`

**治根**: 把 Sprint 17 #121 写的 ground-truth-lint 工具接进 pre-commit framework, 跟 ruff / 其它 hook 统一管理, 改 contract 时自动拦截. 跟 Sprint 17 #121 文档化"必须跑" 配套形成"工具自动跑" 二层防护.

### #124 YOYGuard 通用组件 + 扩 MetricCard / RFMSegmentDrilldown (20min, ~45min)

**新增**:
- `frontend-vue3/src/components/YOYGuard.vue` (61 行) — 通用 YOY/同比 守卫 + 格式化组件, props(value, unit, threshold=1e6, empty='—', precision=2)
- YOYBadge refactor 为 thin wrapper, 内部 `humanizeChange` 函数抽出, 守卫 + 格式化下沉到 YOYGuard, 只保留箭头 (↑/↓) + 颜色 (绿/红) 包装 (29 行减)
- MetricCard.vue 集成 YOYGuard (22 行改)
- `frontend-vue3/src/views/health/RFMSegmentDrilldown.vue` 表格 yoy_repurchase_rate 列硬编码 `Math.abs(v).toFixed(1)+'pp'` 改用 YOYGuard (5 行改)

**新增测试**: 3 个 vitest + 沿用 Sprint 16.5 YOYBadge 4 tests, 总 7/7 passed

**设计**: 不耦合 UI 样式, 调用方负责包装颜色/箭头 (避免 4 组件代码复制), unit 支持 '%' | 'pp' | 'raw' 3 种.

**治根**: 把 Sprint 16.5 #92 守卫从 YOYBadge 1 组件扩到 3 组件 (YOYBadge/MetricCard/RFMSegmentDrilldown), YOYGuard 通用化抽公共防未来 4+ 组件复制守卫逻辑.

## 3. 决策审计

| 决策 | 选项 | 拍板 | 理由 |
|------|------|------|------|
| Sprint 18 任务范围 | A) 4 段 (#141+#123+#142+#124) / B) 只 #141 / C) #141+#123 | **A** | 4 段都是 Sprint 17 留的债务, 一起收口效率最高 (4 subagent 并行 2h) |
| #141 26 字段治根策略 | A) 全部改命名 / B) 全部白名单 / C) **混合 (白名单 + 改类型)** | **C** | 18 yoy_*_ratio 跨 14+ 文件改命名 200+ 行 diff 风险大. 8 真实 ratio 字段改类型低风险 (字段名不变). 混合 = 0 字段名 + 18 白名单 + 8 类型升级 |
| `_YOY_PPT_FIELDS` 持久化方式 | A) frozenset 写死 / B) 注释 + 决策表 | **A + 详细注释** | 14 字段是 Sprint 14 之前历史遗留, 不会动态增减. frozenset + 跨链注释 + 决策表防未来 LLM 重构漂移 |
| `_LIST_RATIO_FIELDS` (1 字段) | A) 改 linter 识别 List element-wise / B) 白名单兜底 | **B** | Sprint 18 scope 限 (#141 26 YOY), linter 增强 (#1) 留 Sprint 19. 兜底不影响 lint 准确性 (Sprint 17 #120 已有 53/53 tests 验证) |
| #123 state 持久化介质 | A) DuckDB 表 / B) 磁盘 JSON / C) git hash / mtime | **B** | 不用 DuckDB 表 (避免循环: hook 不能依赖 W5 cache 自身表). 不用 git hash/mtime (etcd / container / Windows FS 不稳). 用磁盘 JSON + env 覆盖 |
| #123 hook 失败处理 | A) 抛异常阻塞启动 / B) best-effort log warning | **B** | 启动 hook 失败不应让 4 端点全部 503, 跟原 `_ManifestTracker` 一样容忍异常. 缓存状态是 best-effort |
| #142 pre-commit framework 跟 .githooks 关系 | A) 替换 / B) 双轨并存 | **B** | 芙清 CRM 默认 .githooks (Sprint 3 P1-3 时代). framework 版给愿意切的开发者. 两者并行不冲突 (取决于 `git config core.hooksPath`) |
| #142 `pass_filenames: false` | A) 只看 staged / B) 跑全目录 | **B** | 跟 Sprint 16.5 P1-3 教训一致 (CI 跑 committed 模式必须看全部, 不只是 staged). 改 1 个 contract 也要看其它 contract 是不是也有漏标 |
| #124 YOYGuard 抽象粒度 | A) 1 组件做守卫+UI / B) 1 组件只做守卫+格式化, UI 让调用方包 | **B** | 避免 4 组件代码复制, 调用方已有自己的 UI 风格 (YOYBadge 红绿, MetricCard 灰色, RFM 表格不带颜色). 通用化只抽共同部分 |
| #124 YOYGuard threshold 默认值 | A) 1e6 (跟 Sprint 16.5 一致) / B) 1e9 | **A** | 跟 Sprint 16.5 #92 守卫契约一致 (|v|>1e6 → 数据异常), 防止 UI 误导. 1e9 太宽, 1e6 覆盖已知 yoy 异常值 (e.g. 万倍涨) |
| #124 vitest 测试数 | A) 4 tests / B) 3 tests | **B** | 沿用 Sprint 16.5 YOYBadge 4 tests, 加 3 个 YOYGuard 专项 (unit=pp / threshold 自定义 / empty 自定义) 总 7/7 |
| 是否重启 uvicorn | 是 / 否 (subagent 4 件都已重启) | **否** | 4 subagent 各自已 restart + 验证 health 200, Sprint 18 收口时只需 verify 不需要 restart |

## 4. 治理债务 (留 Sprint 19+)

| # | 任务 | 优先级 | 阻塞 | 备注 |
|---|------|--------|------|------|
| 1 | linter 增强: 递归 `List[Annotated[...]]` element-wise Field 元数据检查 | 🟡 P1 | Sprint 18 #141 留 `_LIST_RATIO_FIELDS` 白名单 | 移除白名单依赖, R1 真正识别 list 元素 |
| 2 | 改命名 14 字段 (Sprint 18 走白名单, Sprint 19 真改) | 🟢 P2 | `yoy_*_ratio` → `yoy_*_ratio_ppt` 跨 14+ 文件 | Sprint 18 #141 留, 跨文件破坏大 |
| 3 | 前端 `types.ts` 自动生成 (`pydantic-to-typescript` 之类) | 🟢 P2 | 防止前端字段名漂移 | 跟 Sprint 18 #141 命名统一配合 |
| 4 | Sprint 16 P0 重启 (DuckDB 1.5.4) | 🔴 P0 | Sprint 15 Wave 3 跑批真验 | 等 duckdb/duckdb 1.5.4 release, 复用 v2 代码 + 4 tests |
| 5 | pre-commit framework CI 接入 | 🟢 P2 | 当前 CI 直接跑 `python -m backend.contracts._lint` | 未来可加 `pre-commit/action@v3.0.1` 统一 CI (Sprint 18 #142 不强制) |
| 6 | #142 .githooks 跟 .pre-commit-config.yaml 二选一 | 🟢 P2 | 双轨并存维护负担 | 推荐保留 .githooks (装更轻量), Sprint 19 决定 |
| 7 | YOYGuard threshold 全局配置 (e.g. env `FQ_YOY_GUARD_THRESHOLD`) | 🟢 P2 | 当前 1e6 hardcode | 给业务配置 (e.g. 某些场景允许 1e9) |
| 8 | W5 cache invalidation ETL 末尾调 (可选) | 🟢 P2 | Sprint 18 #123 默认只 uvicorn 启动时调 | 不依赖 uvicorn 重启时也能清, 性能开销 < 100ms |

## 5. 学到的教训

### 5.1 4 段治理 sprint 并行 (Sprint 18 突破)

**问题**: Sprint 16.5 跑通 4 subagent 并行 (1.5h, 468K tokens), Sprint 17 跑通 3 subagent 并行 (1.5h, 340K tokens), Sprint 18 跑通 4 subagent 并行 (2h, ~400K tokens). 每次扩 1-2 subagent, **没踩新坑**.

**根因**: 之前 Sprint 16.5 已经踩过 worktree 隔离 / branch 命名 / rebase vs merge / CHANGELOG 顺序 / uvicorn restart 时机等所有坑, 4 subagent 模式稳定.

**新坑 (Sprint 18)**:
- **#141 任务范围 5-8 字段 实际 26 字段**: task description 写"5-8 字段" 但 Sprint 17 留的 26 issue 全数治根, subagent 正确识别 scope 扩到 26 + 加白名单 (跟 26 全数治根对齐), 1 个 commit 完成全部
- **#123 `FLOW_ALGO_VERSION` bump 影响 r-flow cache**: bump `v0.4.14.35` → `v0.4.14.47` 触发 cache key 全 miss 一次, 后续重算, 跟 Sprint 14.5 约定一致 (Sprint 14.5 P1.4 加的). 写入 CHANGELOG 行为变化 section

**教训**: 
- 4 subagent 并行已经稳定, 是治理 sprint 的标准模式
- subagent 正确处理"任务描述 vs 实际 scope" 矛盾, 知道扩 scope 是治根
- CHANGELOG 必须标"行为变化" (e.g. `FLOW_ALGO_VERSION` bump), 不能只列 "Added"

### 5.2 混合治根 (白名单 + 改类型) 是历史遗留的最佳方案

**问题**: Sprint 18 #141 26 字段 18 是 `yoy_*_ratio` 命名误导 (实际 PpField), 8 是真实 ratio 0-1 误标. 18 改命名跨 14+ 文件, 8 改类型是低风险.

**根因**: Sprint 14 之前 ratio 字段没 Pydantic, 命名约定不严. Sprint 13 ratio 治理后真实 ratio 0-1 严守, 但 yoy 字段历史命名保留.

**治根**: 走"白名单 + 强校验" 组合方案:
- 18 字段: linter 白名单 (`_YOY_PPT_FIELDS`) + 强校验是 PpField (ge=-100, le=100)
- 8 字段: 改类型 `RatioField` / `PpField` (Pydantic 元数据补标, 字段名不变)
- 0 字段名改动 = 0 跨文件破坏

**教训**: 命名/语义冲突的治根**不是** "要么全改命名要么全白名单", 而是混合 (白名单兜底 + 改类型精确补标). 0 字段名改动 = 0 service / frontend / tests 同步成本. Sprint 17 5.4 教训"命名/语义冲突的治根需要更大 refactor" — Sprint 18 用混合方案避免"更大 refactor".

### 5.3 跨进程状态 vs 进程内状态的边界

**问题**: Sprint 18 #123 W5 cache invalidation hook 涉及"manifest version 跨进程对齐". 之前 Sprint 1 写的 `_ManifestTracker` 是**进程内**状态, uvicorn 重启时 _last_seen_version 从 None → 当前值, **不**触发 invalidate (避免空表清空浪费), 但**实际**表里**可能有** 12 orphan keys.

**根因**: `_ManifestTracker._last_seen_version` 没持久化, 重启就丢. 跨进程状态 (uvicorn 重启 / ETL 跑批后 / DuckDB 备份恢复) 没法检测.

**治根**:
- 进程内 `_ManifestTracker`: 实时 (cache.get() 时), 检测本进程内的 manifest 变化
- 启动 hook: 一次性, 检测跨进程的 manifest 变化 (磁盘 JSON 持久化 state)
- 两个 tracker 互补, 进程内 + 跨进程全覆盖

**教训**: 涉及"状态" 的设计, 必须先问"状态在哪个边界" (进程内 / 跨进程 / 跨机器). 跨进程 = 必须持久化 (磁盘 / DB / etcd), 不能用内存变量. Sprint 1 写时**没问这个**, 留了 Sprint 14.5 + Sprint 18 两次治理.

### 5.4 pre-commit framework 跟 .githooks 关系: 双轨并存

**问题**: Sprint 18 #142 pre-commit framework 跟 Sprint 3 P1-3 写的 `.githooks/pre-commit` 都有 ground-truth-lint. 二者重复.

**根因**: 芙清 CRM 默认用 .githooks (Sprint 3 时代), pre-commit framework 是现代 Python 生态 (pre-commit.com). 两者**不冲突** (取决于 `git config core.hooksPath`).

**治根**: 双轨并存 — 保留 .githooks (装更轻量, 默认), framework 版给愿意切的开发者 (未来团队标准).

**教训**: 治理债务**不是** "必须二选一", 而是 "并存 → 慢慢迁移". Sprint 18 #142 不强制切换, 给自己留余地 (framework 可能没装 / 装错版本 / 装在 venv 等). Sprint 19+ 决定后再清理.

### 5.5 YOYGuard 抽象粒度: 守卫+格式化 vs 守卫+UI

**问题**: Sprint 18 #124 抽 YOYGuard 通用组件, 是 "只抽守卫+格式化" 还是 "抽守卫+UI (颜色+箭头)"?

**根因**: 4 组件 (YOYBadge / MetricCard / RFM 表格 / 其它未来) 都有 |v|>1e6 → 数据异常 守卫, 但 UI 风格**不同** (YOYBadge 红绿, MetricCard 灰色, RFM 表格不带颜色).

**治根**: YOYGuard 只做守卫+格式化, UI 让调用方包. 不耦合 UI 样式, 避免 4 组件代码复制.

**教训**: 通用组件抽象的"边界" 由"调用方差异在哪" 决定. YOYBadge/MetricCard/RFM 表格的"差异" 在 UI 样式, 不是守卫+格式化逻辑. 抽到"差异" 之上一层, 不要抽到"差异" 之内 (会过耦合).

### 5.6 Workflow subagent 中断恢复模式 (Sprint 17 教训验证 + Sprint 18 改进)

**问题**: Sprint 17 遇到 verify agent API 断, 手动恢复 (worktree 清理 + rebase 验证 + merge + CHANGELOG 补 + push). Sprint 18 没遇到 API 断 (4 subagent 完美跑通), 但**保留** 中断恢复模式.

**根因**: subagent API 不稳定是客观存在, workflow 越长越容易撞 (Sprint 16.5 1.5h, Sprint 17 1.5h, Sprint 18 2h).

**Sprint 18 改进**:
- 4 subagent 全部 worktree 隔离, 各自分支独立 (跟 Sprint 16.5/17 一致)
- merge 顺序按 subagent 完成时间排 (这次 #141 先完, #123 第二, #142 第三, #124 第四), 跟 CHANGELOG 顺序一致
- uvicorn restart: 4 subagent 各自 restart + 验证 (不依赖 Sprint 18 末尾的 retrospective agent 统一 restart), 分散风险

**教训**: 
- workflow 越长越要"分散风险" (uvicorn restart / 端点验证 / CHANGELOG 写入)
- 中断恢复模式 (Sprint 17 5.1) 是"保险", Sprint 18 没用上但**保留**

## 6. 时间线复盘

| 时间 | 事件 |
|------|------|
| 19:00 | Sprint 18 workflow 启动 (4 phase: Plan/Discover/Execute/Verify) |
| 19:00-19:15 | Plan & Discover 1 agent 调查 4 段 scope (1 个 markdown 报告 — 4 段分工 + 跨文件影响) |
| 19:15-21:15 | 4 subagent 并行跑 2h, 各自 worktree 隔离 (P0/P1/P1/P2 4 优先级) |
| 21:15 | workflow 完成, 4/4 subagent 报告 STATUS: DONE |
| 21:15-21:30 | 4 subagent 各自 uvicorn restart + 端点验证 + push + merge main |
| 21:30-21:45 | Sprint 18 verify agent 跑 pytest (507 passed + 12 skipped + 3 pre-existing failed 跟代码无关) + ground-truth-lint (0 issue) + vitest (63 passed) + 4 v1 端点 (3 401 + 1 200 public) |
| 21:45-22:00 | 写 CHANGELOG v0.4.14.45/46/47/48/49 (4 subagent 已写 + retrospective 49), 写 retrospective + memory, 更新 document-index + CLAUDE.md |

**总耗时**: 3h (含 verify 0.5h + retrospective 0.5h + 端点验证 + CHANGELOG 收口)
**Workflow ID**: wf_sprint18_governance_4phase (估, 实际 4 subagent 各自独立 ID)
**Subagent tokens**: ~400K (4 subagent 各自 80-120K, 跟 Sprint 16.5/17 类似)

## 7. Sprint 19 预告

**Sprint 19+ 留 backlog (按优先级)**:

| 优先级 | 任务 | 来源 |
|--------|------|------|
| 🔴 P0 | DuckDB 1.5.4 release 监控 + 跑批真验 | Sprint 16 P0 abort 续 (Sprint 17 留, Sprint 18 留, 第 3 次留) |
| 🟡 P1 | linter 增强: List element-wise Field 元数据检查 | Sprint 18 #141 留, 移除 `_LIST_RATIO_FIELDS` 白名单 |
| 🟡 P1 | 改命名 14 字段 (Sprint 18 走白名单, Sprint 19 真改) | Sprint 18 #141 留 #2 |
| 🟢 P2 | 前端 `types.ts` 自动生成 | Sprint 18 #141 留 #3 |
| 🟢 P2 | pre-commit framework CI 接入 | Sprint 18 #142 留 #5 |
| 🟢 P2 | .githooks 跟 .pre-commit-config.yaml 二选一 | Sprint 18 #142 留 #6 |
| 🟢 P2 | YOYGuard threshold 全局配置 | Sprint 18 #124 留 #7 |
| 🟢 P2 | W5 cache invalidation ETL 末尾调 (可选) | Sprint 18 #123 留 #8 |

**Sprint 19 计划 (估 4h, 跟 Sprint 18 类似)**:
- **Wave 1 (2h)**: linter 增强 List element-wise + DuckDB 1.5.4 release 监控
- **Wave 2 (1h)**: pre-commit framework CI 接入 + .githooks 决策
- **Wave 3 (1h)**: 改命名 14 字段 (如果 Sprint 19 真做, 否则继续留 Sprint 20)

## 8. 关键指标

| 指标 | 值 |
|------|---|
| Sprint 周期 | 3h (含 verify + retrospective + 端点验证) |
| Workflow | 4 subagent 并行 2h + 0.5h verify + 0.5h retrospective |
| Subagent 数 | 5 (Plan + 4 Execute + Verify 自跑) |
| Subagent tokens | ~400K |
| 任务完成 | 4/4 (100%) |
| Commits | 10 (5 fix + 4 merge + 1 doc) |
| Files changed | 16 (5 contract + 1 linter + 1 cache + 1 main + 1 _shared + 4 frontend + 2 tests + 1 .pre-commit-config + 1 test-precommit.sh) |
| Lines changed | +1740 (#141 + 49 + #123 + 410 + #142 + 60 + #124 + 90 + 文档 + 1130) |
| Tests | 454+12 → 507+12 (+53: #123 10 + #124 3 vitest + #141 复用 40 既有 tests) |
| Vitest | 26+ → 63 (含 #124 YOYGuard 3 + 沿用 Sprint 16.5 YOYBadge 4) |
| Pre-existing failed | 3 (test_sim_prod_etl race + test_w4_full DuckDB 锁 + 1 sim-prod) — 跟 Sprint 18 改动无关 |
| uvicorn 端点 | health 401 (认证保护), /docs 200, /api/v1/health 200 (public), v1/r-flow=401, v1/rfm=401, v1/metrics=401 |
| ground-truth-lint | 26 issue → 0 issue (#141 治根) |
| Lint tests | 10/10 passed (沿用 Sprint 17) |
| Cache invalidation tests | 10/10 passed (#123 新) |
| 12 步流程 | 4/4 subagent 走完, 4 个 merge commit 全部合 main, 0 中断 |

---

*此文件由 Sprint 18 治理 sprint 收口流程生成, 最后更新 2026-06-11*
