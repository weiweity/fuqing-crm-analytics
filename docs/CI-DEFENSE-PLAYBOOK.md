# CI 0→1 实战 fix 框架(3 层防御 + 决策树)

> **Sprint 42 #S42-1 沉淀**(2026-06-19)
> 跨 sprint 复用,防 Sprint 50+ 重新激活 e2e CI blocking 时复发同类问题

## TL;DR

CI 红了先分类(**Q1** 本地能跑吗?)→ **Q2** 根因是 spec 还是环境?→ **Q3** 治本 1-2 天能闭环吗?→ 治不了就治标(skipif/advisory/timeout)+ 写 lessons learned。

**一句话决策树**:
- 本地能跑 + CI fail → **C 类**(环境差异,治标优先)
- 本地也 fail → **A/B 类**(修代码/spec)
- 治本 < 1 天 + 治本后 0 复发 → 治本
- 治本 > 2 天 OR 治本不现实(基础设施) → 治标
- 治标反复出现 → 写 lessons learned + trigger 评估

---

## 🛡️ 第 1 层:预防(spec 写得"环境无关")

**核心原则**:spec 写得"环境无关"——本地跟 CI 跑出的结果应该一致。

### 4 条原则(配合 spec-lint 自动检查)

| # | 原则 | 错例 | 对例 | 教训源头 |
|---|---|---|---|---|
| 1 | 不 hardcode 业务数据长度 | `expect(arr.length).toBe(5)` | `expect(arr.length).toBeGreaterThan(0)` | Sprint 41.6 sampling spec |
| 2 | 不 `waitForTimeout(N)` 死等 | `await page.waitForTimeout(2000)` | `await expect(chart).toBeVisible({ timeout: 15000 })` | Sprint 32.2 + 41.8/41.9 |
| 3 | `page.request` 加 Authorization | `await page.request.get('/api/v1/x')` | 加 `{ headers: { Authorization: ... } }` | Sprint 41.5 (401 → 200) |
| 4 | 不依赖外部数据假设 | 期望"必须有数据" | 期望"数据存在/不存在都是合规" | Sprint 41.6 backend 字段名 typo |

### spec-lint 自动检查

`frontend-vue3/e2e/lint/spec-lint-l2.sh` (L2 默认, L1 fallback) 3 条规则:

- **Rule 1**(FAIL):不 hardcode 业务数据长度
- **Rule 2**(FAIL):不 `waitForTimeout` 死等
- **Rule 3**(WARN):`page.request` 缺 Authorization

pre-commit 的 spec-lint hook 已默认跑 L2 AST parser; 若本地 Python 环境缺 `tree-sitter` + `tree-sitter-typescript`, wrapper 自动 fallback 到 L1 (`spec-lint.sh`) 并提示安装。L2 5 case + L1 3 case regression tests 同时保留。

---

## 🔍 第 2 层:检测(CI 跑批前自动 check)

**核心原则**:错误可见性 > 优雅失败。

### 4 项 pre-flight check(在 CI job 头部跑)

```bash
set -e  # ❌ 别用 || true 吞错
# 1. 磁盘空间
df -h / | awk 'NR==2 {print $4}' | grep -E '[0-9]+G' || \
  { echo "❌ Disk space check failed"; exit 1; }
# 2. 必填工具
command -v python3 node npm || { echo "❌ Tool missing"; exit 1; }
# 3. 必填 env var
[ -n "$FQ_CRM_PASSWORDS" ] || { echo "❌ env missing"; exit 1; }
# 4. 必填数据
[ -f "$DUCKDB_PATH" ] || { echo "⚠️ DuckDB not found, skip data tests"; }
```

### 跟 ground-truth-lint 一样 non-blocking 起步

观察 1-2 sprint false positive 率后,改 blocking。

### 错误可见性 > 优雅失败(Sprint 41.11 教训)

- ❌ `uvicorn 启动 || true` 吞错 → Sprint 41.11 才看见真错
- ✅ `set -e` + redirect log → uvicorn 启动失败立刻可见

---

## 🚨 第 3 层:响应(5 步流程)

### Step 1:看 log 找根因

```bash
gh run view <id> --log-failed | grep -E "Error|FAIL|panic" | head -20
```

### Step 2:区分类型(A/B/C/D/E)

| 类型 | 表现 | 治法 |
|---|---|---|
| **A. 代码 bug** | 本地 + CI 都 fail | 修代码 |
| **B. Spec 写法错** | 本地过 CI fail | 修 spec |
| **C. 环境差异** ⭐ | **本地过 CI fail** | **本文重点** |
| D. 数据依赖 | CI 缺数据 | seed data / mock |
| E. 第三方服务 | CI 缺工具/服务 | 装依赖 / 跳服务 |

### Step 3:评估治本 ROI(2 天阈值)

| Q | 答 → 决策 |
|---|---|
| Q3 治本 1-2 天能闭环吗? | 能 + 治本后 0 复发 → **治本** |
| | 不能(基础设施限制) → **治标** |
| Q4 治标会反复出现吗? | 会 → 写 lessons learned + trigger 评估 |
| | 不会 → 治标闭环 |

### Step 4:治标 3 板斧(跟 Sprint 38 + 41 一致)

| 板斧 | 用法 | 实战案例 |
|---|---|---|
| **加 skipif** | race flake / 缺数据 / 缺 backend | Sprint 39.1 `_PROD_DUCKDB_AVAILABLE` |
| **改 advisory** | CI 跑不通但代码对的场景 | Sprint 41.12 e2e `continue-on-error: true` |
| **加 timeout + retry** | 渲染慢 / 网络抖 | Sprint 41.10 playwright 60s |

### Step 5:写 lessons learned doc

`docs/SPRINT-XX-LESSONS-LEARNED.md`(跨 sprint 复用)。

---

## 实战决策树(快速版)

```
Q1: 本地能跑通吗?
  能 → C 类(环境差异)
  不能 → A/B 类(修代码/spec)

Q2: 根因是 spec/代码 还是环境?
  spec/代码 → 修
  环境 → Q3 评估

Q3: 治本 1-2 天能闭环吗?
  能 + 治本后 0 复发 → 治本
  不能(基础设施限制)→ 治标

Q4: 治标会反复出现吗?
  会 → 写 lessons learned + trigger 评估
  不会 → 治标闭环
```

---

## Sprint 38 + 41 实战对照

| 维度 | Sprint 38 race flake | Sprint 41 e2e CI |
|---|---|---|
| **现象** | pre-push pytest -n auto fail | GH Actions e2e fail |
| **根因** | DuckDB 文件锁 exclusive | GH runner 14GB disk + headless |
| **治本 ROI** | 低(2.x 等 1+ 年) | 低(CI runner 改不了) |
| **治标 ROI** | 高(skipif 半天) | 高(advisory 半天) |
| **决策** | 治标 + lessons learned | 治标 + lessons learned |
| **N follow-up** | 0(治标 1 次闭环) | 12(治标前 12 次实战 fail) |
| **触发评估** | Sprint 38 调研报告 | Sprint 50+ 重新评估 |

**共同模式**:**实战 fix 闭环 ROI 重评是核心**。N > 5 还没闭环,改治标(advisory 0→1) 是务实选择。

---

## Sprint 50+ 重新评估条件

3 个触发条件之一满足,重新评估 e2e CI blocking:

1. **GH Actions runner 升级**:14GB → 32GB disk / 加速 2x
2. **加 seed DuckDB**:mock 1-2 GB production DuckDB 跟 CI runner
3. **换 CI provider**:GitHub Actions → Self-hosted runner(本地 DuckDB + 大磁盘)

如果都不可行,继续 advisory。配合 spec-lint 预防层减少后续 follow-up 数。

---

## 跨 sprint 教训汇总

| 教训 | 来源 | 落地 |
|---|---|---|
| DuckDB 文件锁 exclusive | Sprint 32.3/34.1/36-1/37/38 | CLAUDE.md L4.3 `_IN_XDIST_PARALLEL` skipif |
| production DuckDB 缺 | Sprint 32-38 7+ sprint | CLAUDE.md L4.4 `_PROD_DUCKDB_AVAILABLE` skipif |
| GH runner 14GB disk < ETL 50GB | Sprint 41.1 | `monkeypatch.setenv("ETL_MIN_DISK_GB", "0")` |
| GH runner 没 uvicorn | Sprint 41.4 | e2e job 启 backend |
| Playwright 3 个 timeout 区别 | Sprint 41.7/41.8/41.9/41.10 | playwright.config.ts CI 60s + serial |
| `\|\| true` 吞错 | Sprint 41.11 | set -e + redirect log |
| 12 follow-up 仍 fail 改 advisory | Sprint 41.12 | e2e `continue-on-error: true` |

---

## 关联文件

- [docs/CI-E2E-HISTORY.md](./CI-E2E-HISTORY.md) — CI e2e 实施历程 (Sprint 32.1→41→52, 实战教训)
- `CLAUDE.md` L4.3(race flake)+ L4.4(production DuckDB skipif 永久规则)
- `CLAUDE.md` L5.1(CI 留尾 ROI 重评)+ L5.2(spec 写法原则) — Sprint 42 新增
- `frontend-vue3/e2e/lint/spec-lint-l2.sh` — 预防层自动检查 (L2 默认, L1 fallback)
- `.github/workflows/lint.yml` — e2e job(Sprint 41.12 advisory)

---

## 流程纪律(自检 checklist)

下次 CI 红了,先走这 5 步:

- [ ] **Step 1**:跑 `gh run view <id> --log-failed` 看根因
- [ ] **Step 2**:分类 A/B/C/D/E(本地能跑吗?根因是 spec 还是环境?)
- [ ] **Step 3**:评估治本 ROI(2 天阈值)
- [ ] **Step 4**:治不了就治标(skipif / advisory / timeout+retry)
- [ ] **Step 5**:写 lessons learned doc(关联 memory)
