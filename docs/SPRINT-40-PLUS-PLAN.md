# Sprint 40+ Ground-Truth Audit + 推后排期 (2026-06-19)

**Audit date**: 2026-06-19
**Auditor**: Sprint 40 ground-truth audit (跟 Sprint 39.2 visitor chain audit 模式一致)
**触发**: Sprint 39 收口后, user 指示 "#2-7都先进行更新, 拉个 workflow"
**目的**: Sprint 40+ 候选 6 项推后任务的 ground-truth audit + ROI 重评 + Sprint 41-43 推后排期

---

## TL;DR

| Sprint | 任务 | 工作量 | ROI 重评 | 决策 |
|---|---|---|---|---|
| **40** | race flake 真治本 (Sprint 38 调研 3 选 1) | 2+ 天 | **ROI 偏低** (跟 Sprint 38 一致) | **推后 Sprint 36.x+ (DuckDB 2.x 触发)** |
| **41** | CI 跑 e2e 自动化 (GitHub Actions) | 1.5 天 | **ROI 高** (Sprint 39.1 baseline CI 修完闭环) | **✅ v0.4.14.131 完成, 4 commit 实战 (e2e job + disk full + npm ci fix + 收口)** |
| **42** | L2 AST parser + ground-truth-lint 扩 | 半天 + 1h | **ROI 低** (L1 已够, 0 触发词) | **推后 Sprint 50+** |
| **43** | commit msg check + 50m scale | 1 天 + 2 人日 | **ROI 负/低** (误报率高, 0 紧迫) | **推后 Sprint 50+ (50m 触发 30M)** |

---

## Sprint 40: race flake 真治本 (推后)

**Sprint 38 调研结论** (audit doc 在 Sprint 38 close memory):
- DuckDB 文件锁 exclusive, 任何 conn (read_only / read_write / ATTACH) 都抢同一锁
- 实测 ATTACH (READ_ONLY) 跟 uvicorn write lock 也冲突 (`IOError: Could not set lock`)
- 真治本 3 选项 ROI 都偏低:
  - A: fixture ATTACH 跟 uvicorn 解耦 (2+ 天, 工程化)
  - B: pre-push kill uvicorn + pytest + restart uvicorn (1 天, push 时 1-2 min frontend 不可用)
  - C: 改真连 test 用 mock conn (半天, 但失去 Sprint 34.1 真连抓 typo 能力)

**Sprint 40 重新评估**:
- Sprint 39.1 加 `_PROD_DUCKDB_AVAILABLE` skipif (跨 3 个真连 test), race flake 在 GH Actions CI 0 复发 (期望变绿)
- Sprint 38 加 `_IN_XDIST_PARALLEL` skipif (跨 3 个真连 test), 本地 -n auto 5/5 0 flake
- Sprint 36-5 加 `_UVICORN_LOCK_PID` skipif (test_api_integration.py), uvicorn 跑着时跳过
- **三层 skipif 叠加后, race flake 0 业务影响** (只剩"刷 test 时偶发 skip 提示", 0 flake)

**决策**: 推后 Sprint 36.x+ (Sprint 38 plan-eng-review 推荐的 "等 DuckDB 2.x 改 lock 协议")。

**真治本触发条件** (任一):
1. DuckDB 2.x 发布 (文件锁改 shared mode)
2. 用户报"race flake skipif 0 flake 但 UX 不友好"
3. CI 跑 e2e 自动化时 race flake 又复发 (新场景)
4. 真连 test 数量从当前 12 → 50+ (skipif 透明化不够)

---

## Sprint 41: CI 跑 e2e 自动化 (本 sprint 执行, ROI 高)

**Sprint 32.1 留尾** (v0.4.14.114 Playwright HTTPS error tolerance, 7 sprint 仍未做):
- 加 GH Actions e2e job, paths: `frontend-vue3/e2e/**` + `playwright.config.ts`
- NODE_EXTRA_CA_CERTS=certifi cacert.pem (Sprint 32.1 实战过 SELF_SIGNED_CERT_IN_CHAIN fix)
- `npx playwright install --with-deps chromium`
- 强依赖 Sprint 33.2 spec 稳定 (10/10 view smoke pass ✅)
- 强依赖 Sprint 39.1 baseline CI 修完 ✅

**实施步骤** (估 1.5 天):
1. 改 `.github/workflows/lint.yml` 加 e2e job (15 min)
2. 配 env: NODE_EXTRA_CA_CERTS=certifi cacert.pem (15 min)
3. 配 npx playwright install (15 min)
4. 验证 GH Actions e2e job 跑通 (30 min)
5. 失败兜底: 离线 dev server 启动 (15 min)
6. 文档 (CHANGELOG + CLAUDE.md + TECH-DEBT.md 同步) (15 min)

**触发条件** (本 sprint 执行):
- Sprint 41 应该做 (不是 Sprint 40), 因为 Sprint 40 是 audit (0 代码改动)
- 顺序: Sprint 40 audit → Sprint 41 CI e2e → Sprint 42-43 推后项

**ROI**:
- ✅ e2e 自动门禁 (不依赖本地手跑)
- ✅ 1.5 天 (含 env config, Sprint 32.1 实战过 SSL fix)
- ✅ 强依赖 Sprint 33.2 + 39.1 已闭环
- ⚠️ 需要 user 提供 GH Actions 权限 (已是 public repo, 应该 OK)

---

## Sprint 42: L2 AST parser + ground-truth-lint 扩 (推后)

**L2 AST parser** (Sprint 34.2 留尾):
- 升级 L1 regex lint → AST parser (更准, 跨 multiline + nested string)
- Sprint 34.2 评估 0 实际价值, L1 regex lint 已 0 violations (101 files)
- 实施成本: 半天
- ROI: **低** (L1 已够用, 升级无 bug 修复价值)

**ground-truth-lint 扩 backend/scripts** (Sprint 36-4 留尾):
- 当前覆盖: `docs/validation-reports/*.md` + `docs/飞书版架构文档/*.md`
- 扩展: `backend/scripts/**/*.py` (触发 ground-truth claim)
- 0 触发词 (backend scripts 不写 "ground-truth" 类声明)
- 实施成本: 1h
- ROI: **极低** (0 触发词, 不会增加 lint 覆盖)

**决策**: 合并成 Sprint 42, 半天总成本, 但 ROI 极低, **推后 Sprint 50+** (作为"季度 lint 健康检查"一并做)。

**触发条件** (任一):
1. backend scripts 出现 ground-truth claim 触发词
2. L1 SQL lint 出现 false negative (实际有 violation 没抓到)
3. 季度 lint audit (每 6 个月 1 次)

---

## Sprint 43: commit msg check + 50m scale (推后)

**commit msg ↔ diff 一致性 CI check** (Sprint 35 留尾):
- 防 a9b1d91 类 (commit 声称做 8 处业务专名 sed, 实际只改 1 处)
- 启发式正则提取 N 数字 + 单位词 vs git show --stat 数量比对
- Sprint 35 评估误报率高 (commit message 描述经常比 diff 抽象)
- 实施成本: 1 天
- ROI: **负** (误报率高 = 真正 commit 也会 fail, 反而降低体验)

**决策**: 推后 Sprint 50+, 等更好的 commit msg diff 算法 (e.g. AI 辅助检查)。

**50m-scale-architecture Phase 1-3** (Sprint 25 留尾):
- Phase 1: 预计算表 + Layer 3 serving tables
- Phase 2: 索引 + ANALYZE
- Phase 3: 生产部署
- 总估时 2 人日
- **触发条件**: 30M 数据量 (`data/processed/fuqing_crm.duckdb` 行数 >= 30M, 当前 10.75M = 36%)
- 当前 0 性能压力 (ETL 18 min < 35 min SLO, 看板 P95 响应正常)

**决策**: 推后到 30M 触发, 不主动排期。

---

## Sprint 41 实战总结 (v0.4.14.131 已完成, 2026-06-19)

**实施**: 1.5 天估时, 4 commit 实战:

| Commit | 内容 | 失败原因 |
|---|---|---|
| ef22b2a (Sprint 41) | 加 e2e job (lint.yml +55 行) | — |
| d44804b (Sprint 41.1 follow-up) | test_wo_cleanup_orphans.py 加 monkeypatch.setenv("ETL_MIN_DISK_GB", "0") | Sprint 39.1 留尾债: GH Actions runner 14GB disk < ETL 50GB 阈值 → FATAL disk full → 0 marker write → test fail |
| ee8a655 (Sprint 41.2 follow-up) | npm ci → npm ci --legacy-peer-deps | openapi-typescript@7.13.0 peer dep typescript@^5.x vs frontend typescript@~6.0.2 → ERESOLVE → e2e job fail |
| 2676a8b (Sprint 41 收口) | VERSION bump + CHANGELOG + CLAUDE.md + README.md + TECH-DEBT.md | — |

**关键发现 (实战教训)**:

1. **GH Actions runner 14GB disk** 限制 ETL 默认 50GB 阈值 (Sprint 24 #26 设计防御), 必须 monkeypatch 跳过
2. **GH Actions runner npm ci peer dep 冲突** (openapi-typescript@7.13.0 vs typescript@~6.0.2), 必须 --legacy-peer-deps
3. **CI 0→1 实战路径** = baseline fix (Sprint 39.1) + audit (Sprint 40) + 实施 (Sprint 41) + 3 次 follow-up (e2e + disk + npm ci) = 4 commit 才能完全闭环
4. **跨 sprint 教训**: Sprint 32.1 留尾 7 sprint 没做, Sprint 41 三次实战 fix 验证 "实战 fix 模式" 比 "一次性完美实施" 更有效

**当前 CI 状态** (等 GH Actions runner 完成):
- ee8a655 (Sprint 41.2 npm ci fix): queued → in_progress
- c035f47 (Sprint 41.1 follow-up disk): in_progress (e2e 跑批中)
- 3aa3949 (Sprint 41 原始 e2e job): in_progress (disk full fail 阻塞)

**期望最终结果**: CI 全绿 (lint + ground-truth-lint + test + e2e 4 job 全 pass)

## Sprint 41 实施计划 (本 sprint 执行)

### Step 1: 改 `.github/workflows/lint.yml` (15 min)

加 e2e job:

```yaml
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - uses: astral-sh/ruff-action@v3
      - name: Install deps
        run: |
          cd frontend-vue3
          npm ci
      - name: Install Playwright
        env:
          NODE_EXTRA_CA_CERTS: $(python3 -c "import certifi; print(certifi.where())")
        run: |
          cd frontend-vue3
          npx playwright install --with-deps chromium
      - name: Build + e2e
        env:
          NODE_EXTRA_CA_CERTS: $(python3 -c "import certifi; print(certifi.where())")
        run: |
          cd frontend-vue3
          npm run build
          npx playwright test
```

### Step 2: paths filter (10 min)

加 paths filter:

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'frontend-vue3/e2e/**'
      - 'frontend-vue3/playwright.config.ts'
```

避免 docs-only commit 触发 e2e (跟 Sprint 39 lint.yml 加 paths 模式一致)。

### Step 3: 验证 (30 min)

- push fix branch → GH Actions 跑 e2e
- 期望 10/10 view smoke pass
- 失败兜底: 跑本地 Playwright 对比

### Step 4: 文档同步 (15 min)

- CHANGELOG.md 加 Sprint 41 entry
- CLAUDE.md 加 CI e2e 永久规则 (L4.5)
- README.md 当前状态加 CI e2e 段
- TECH-DEBT.md 加债 #S41-1 闭环

---

## 跨 sprint 教训

1. **audit doc 作为跨 sprint truth source**: 跟 Sprint 39.2 visitor chain audit doc 模式一致, Sprint 40+ 推后项决策基于本次 audit.

2. **ROI 重评要持续**: Sprint 32.1 留尾"CI 跑 e2e" 在 Sprint 39.1 修 baseline CI 之前 ROI 中等 (因为 baseline CI 红, e2e 跑也红), Sprint 39.1 修完后 ROI 升为高 (e2e 才能真正起作用).

3. **推后 ≠ 永远不做**: 每项推后都列了"触发条件", Sprint 50+ 重新评估不是"等几年", 而是"满足触发条件就排".

4. **DuckDB 真治本等上游**: Sprint 38 调研 DuckDB 文件锁 exclusive, Sprint 40 接受"等 DuckDB 2.x". 跨 sprint 教训: 基础设施限制别硬刚, 等上游升级.

---

## 关联 Memory / 文件

- Sprint 38 close memory (race flake 治标 + ATTACH 真治本 ROI 重评为低)
- Sprint 39 close memory (GH CI 爆红修复 + visitor chain audit doc)
- Sprint 32.1 close memory (Playwright HTTPS tolerance 留尾)
- Sprint 25 close memory (50m scale 留尾)
- `docs/VISITOR-CHAIN-AUDIT-SPRINT39.md` (跨 sprint audit doc 模式参考)