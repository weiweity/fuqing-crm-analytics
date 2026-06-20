# CI e2e 实施历程 (Sprint 32.1 → Sprint 41 → Sprint 52)

> 合并自 `docs/SPRINT-40-PLUS-PLAN.md` + `docs/SPRINT-41-CI-LESSONS-LEARNED.md`。
> 记录 e2e CI 从规划到实施的完整历程和实战教训。

---

## TL;DR

Sprint 32.1 留尾 "CI 跑 e2e", Sprint 40 audit 重评 ROI 升高, Sprint 41 实施 12 次 follow-up 仍 fail, 改 advisory 0→1 (跟 ground-truth-lint 一致). **Sprint 52 e2e CI 自动化 (4 job: lint + ground-truth-lint + pytest + e2e advisory)**.

---

## 1. 时间线

| Sprint | 事件 | 版本 |
|---|---|---|
| Sprint 32.1 | 留尾 "CI 跑 e2e", 估 1.5 天 ROI 高 | v0.4.14.114 |
| Sprint 39 | GH CI baseline fix (7+ sprint 一直红 → 绿) | v0.4.14.128 |
| Sprint 40 | audit 重评, 决策实施 Sprint 41 | v0.4.14.129 |
| Sprint 41 | 实施, 12 次 follow-up 仍 fail | v0.4.14.131+ |
| Sprint 41.12 | 改 advisory (跟 ground-truth-lint 一致) | v0.4.14.132 |
| Sprint 42 | spec-lint 预防层 + CI 实战 fix 框架沉淀 | v0.4.14.132 |
| Sprint 52 | e2e CI 自动化 (4 job advisory) | v0.4.14.138 |

---

## 2. Sprint 41 实战 fix 时间线 (12 commits)

| Commit | 内容 | 失败原因 |
|---|---|---|
| ef22b2a | 加 e2e job (lint.yml +55 行) | — |
| d44804b | test_wo_cleanup_orphans.py + monkeypatch ETL_MIN_DISK_GB=0 | GH runner 14GB disk < ETL 50GB 阈值 |
| ee8a655 | npm ci → npm ci --legacy-peer-deps | openapi-typescript peer dep ERESOLVE |
| b374f36 | HealthOverviewTab.vue type cast readonly string[] | vue-tsc strict TS2345 (本地 vite build 不跑 tsc) |
| ae68c6c | e2e job 启 uvicorn backend | GH runner 没 uvicorn, /api/v1/... 401 |
| 7df0c84 | page.request 加 Authorization header (3 spec 401 fix) | page.request 不带 sessionStorage Bearer token |
| 342e2f3 | sampling spec channel_summary typo + fullyParallel 关 | backend 字段名 typo + 3 worker 抢资源 |
| d2a8534 | playwright.config.ts CI timeout 30s | GH runner 渲染慢 + 没 DuckDB fetch 慢 |
| da9cd2b | spec hardcode timeout 10000 → 30000 (34 处) | config timeout 不覆盖 spec hardcode |
| 9770cfa | playwright.config.ts CI timeout 30s → 60s | beforeEach + test body 30-50s |
| e3729a5 | uvicorn 启动 set -e + redirect log + 60s wait | `\|\| true` 吞错, 30s curl 不返 200 |
| **e9020a1** | **e2e job 改 non-blocking** | **11 次 follow-up 仍 fail, ROI 重评为低** |

---

## 3. 实战教训

### 3.1 GH Actions runner 跟本地差异巨大

| 维度 | 本地 (macOS) | GH Actions runner (Linux) |
|---|---|---|
| Disk | ~500GB | 14GB |
| Browser | Chrome 真实渲染 | Headless Chromium |
| DuckDB | 本地有 103GB production | runner 没 (gitignored) |
| Memory | 16GB | 7GB |
| 渲染速度 | <1s | 5-30s |

### 3.2 实战 fix 模式 ROI 重评

| Sprint | Follow-up | ROI | 结果 |
|---|---|---|---|
| Sprint 38 race flake 治标 | 1 (skipif) | 中 | 0 flake |
| Sprint 39 GH CI baseline fix | 1 (skipif) | 高 | 红 → 绿 |
| **Sprint 41 CI e2e** | **11 (治本)** | **低** | **仍 fail → advisory** |

**决策树**: Q1 本地能跑? → Q2 根因是 spec 还是环境? → Q3 治本 1-2 天能闭环? → Q4 治标会反复?

### 3.3 Playwright 3 个 timeout 区别

| Config | 作用 | 覆盖 spec hardcode? |
|---|---|---|
| `timeout` | Global test timeout (beforeEach + test) | ❌ |
| `expect.timeout` | 单 expect 等待 | ✅ |
| `navigationTimeout` | 单 navigation | ❌ |

### 3.4 错误可见性 > 优雅失败

```bash
# ❌ 沉默失败
nohup python3 -m uvicorn ... > /tmp/uvicorn-ci.log 2>&1 &

# ✅ 错误可见
set -e
python3 -m uvicorn ... &
```

---

## 4. 当前状态 (Sprint 52)

- **e2e CI**: advisory mode (4 job: lint + ground-truth-lint + pytest + e2e)
- **本地 e2e**: 12/12 pass (Sprint 52)
- **触发重新评估条件**: GH runner disk >50GB / seed DuckDB step / DuckDB 2.x lock 协议改进

---

## 5. 关联文件

- `.github/workflows/lint.yml` (e2e job config)
- `frontend-vue3/playwright.config.ts` (timeout + serial mode)
- `docs/CI-DEFENSE-PLAYBOOK.md` (防御策略)
- `docs/SPRINT-40-PLUS-PLAN.md` (原始 Sprint 40 计划, 已合并)
- `docs/SPRINT-41-CI-LESSONS-LEARNED.md` (原始 lessons, 已合并)
