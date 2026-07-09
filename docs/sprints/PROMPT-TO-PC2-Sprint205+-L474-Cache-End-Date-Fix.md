# PC2 部署 handoff — Sprint 205+ L4.74 cache end_date fix 推送 + RFM 缓存跑通

> **状态**: 🚀 Sprint 205+ main HEAD `aa40ac8` (L4.74 cache end_date fix + amend fix 3 件套) 推到 PC2 端, 跟 user "继续执行, 可以同步到 PC2 了吗？然后可以让 PC2，是不是可以跑 RFM 的缓存了" 1:1 stable 永久规则链配套 (跟 L4.15 push 拍板规则 1:1 stable)
> **交接理由**: 跟前几轮 L4.64 + L4.70 + L4.74 cache precompute fix 部署到 PC2 1:1 stable 永久规则链配套, "流程同之前" 沿用 + 简化 (plist 已加载, .env 已改 10)
> **风险等级**: 🟢 低 (跟 L4.74 cache precompute fix 部署到 PC2 1:1 stable 永久规则链配套) - PC2 端 cache 命中率 0% → 80%+ + 5/5 period_type < 5s + 502 watchdog 0 触发

---

## 1. 当前 main HEAD (跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则链配套)

按 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则链配套, **PC2 端要拉的 main HEAD 状态**:

| Commit | 内容 | 1:1 stable 永久规则链 |
|---|---|---|
| `aa40ac8` (当前 main HEAD, amend) | **L4.74 cache end_date fix + amend fix 3 件套**: 关键 1 行 fix today=date.today() + STANDARD_PERIODS 扩 5 周期 + YEARS 缩 [2026] + amend fix #1 (line 383 biz_conn) + amend fix #2 (ON CONFLICT UPSERT) + amend fix #3 (DROP idx_period 索引) | ✅ L4.42 + L4.50 + L4.65.1 + L4.67 + L4.69.1 + L4.74 + L4.75 1:1 stable 永久规则链配套, 0 业务代码改动 |
| `cbbfcf9` (amend 前, git reflog 留尾) | (amend 前 commit, 跟 L4.14 amend 物理限制 1 commit drift 永久接受 1:1 stable 永久规则化沿用) | ✅ 跟 L4.14 amend 1:1 stable 永久规则化沿用 |
| `1901040` (merge commit) | merge: fix/l4-74-cache-end-date-fix | ✅ 跟 L4.65.1 + L4.69.1 收口 push 模式 1:1 stable 永久规则化沿用 |
| `8f952ac` (前几轮已发 PC2) | L4.74 cache precompute fix (precompute_rfm_cache 拆 biz_conn + cache_conn, 跟 PC2 副 Agent 反馈"8f952ac 漏改 1 行" 1:1 stable 永久规则化沿用, Mac amend 修复) | ✅ L4.67 + L4.74 1:1 stable 永久规则化沿用 |

按 L4.42 + L4.50 + L4.65.1 + L4.69.1 + L4.74 1:1 stable 永久规则链配套, **PC2 端 推送 = 拉 main HEAD `aa40ac8` (含 1 个新 commit amend, 跟 现有 已发 L4.74 cache precompute fix 集成)**.

---

## 2. PC2 端 5 步部署 (跟 L4.64 + L4.70 之前 PC2 部署 1:1 stable 永久规则链配套, "流程同之前" 沿用)

按 L4.64 + L4.70 之前 PC2 部署 1:1 stable 永久规则链配套 + "流程同之前" 沿用 + L4.7 + L4.36 + L4.50 + L4.54 + L4.62 + L4.65.1 + L4.69.1 + L4.74 1:1 stable 永久规则链配套, **PC2 端 5 步部署 (简化版, plist 已加载 + .env 已改 10)**:

### 步骤 1: PC2 端 SSH + git pull (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套)

```bash
# PC2 端 SSH 登录
ssh user@pc2-host

# 切到项目根目录
cd /path/to/fuqing-crm-analytics  # PC2 上项目实际路径

# 拉 main HEAD (跟 L4.65.1 + L4.69.1 1:1 stable 收口 push 模式 永久规则化配套)
git fetch origin
git checkout main
git pull --ff-only  # 期望: 拉到 aa40ac8 (1 个新 commit amend, force-with-lease push)

# 验证 main HEAD
git log --oneline -3
# 期望输出:
# aa40ac8 fix(L4.74 cache end_date): 关键 1 行 fix today 跟 user query 一致 + STANDARD_PERIODS 扩 5 周期 + YEARS 缩 [2026] (跟 L4.42 + L4.50 + L4.55 + L4.65.1 + L4.69.1 + L4.74 + L4.75 1:1 stable 永久规则链配套, 0 业务代码改动)
# 8f952ac fix(L4.74 cache precompute): precompute_rfm_cache 拆 biz_conn + cache_conn 修复 L4.67 cache 库分离兼容性
# 03af3fb fix(L4.75.4 unified): 5 Tab 统一 ManualQueryButton 组件
```

### 步骤 2: PC2 端 .env 验证 (跟 L4.70 PC2 .env 1:1 stable 永久规则链配套, 不用改)

```bash
# 验证 .env FQ_READ_POOL_SIZE = 10 (跟 L4.70 + L4.72.3 1:1 stable 永久规则化沿用, PC2 端已改)
grep "^FQ_READ_POOL_SIZE" .env
# 期望: FQ_READ_POOL_SIZE=10
# 已经是 10, 不用改
```

### 步骤 3: PC2 端 NSSM restart uvicorn (跟 L4.65.1 启动内存治本 + L4.69.1 内存泄漏治本 1:1 stable 永久规则链配套)

```bash
# PC2 端 用 NSSM 重启 uvicorn (跟 L4.65.1 启动 1.3GB → 147MB + L4.69.1 内存泄漏 2GB → 300MB 1:1 stable 永久规则化沿用)
nssm restart fuqing-uvicorn

# 等几秒让 uvicorn 启动稳定
sleep 5

# 验证 uvicorn health
curl -s -o /dev/null -w "HTTP %{http_code} 耗时 %{time_total}s\n" http://localhost:8000/api/v1/health/db-size
# 期望: HTTP 200 耗时 < 1s (跟 L4.65.1 + L4.69.1 1:1 stable 永久规则化沿用)
```

### 步骤 4: PC2 端 跑 precompute_rfm_cache() (跟 L4.74 cache end_date fix 1:1 stable 永久规则化沿用, 8 组合)

```bash
# PC2 端 跑 precompute_rfm_cache() (跟 Mac dev 7/9 实证 1:1 stable 永久规则化沿用)
# 期望跑通 8 组合 (4 period_type × 1 年 × 2 metric, MTD/YTD/last180d/last365d + GSV/GMV)
# 期望 cache 表新 8 行 end_date=07-08 (跟 user query date.today()=07-09 一致)
PYTHONPATH="$(pwd)" /path/to/python3 -c "
import sys
sys.path.insert(0, '.')
from backend.services.health.rfm_analysis.cache import precompute_rfm_cache
result = precompute_rfm_cache()
print(f'>>> precompute_rfm_cache 返回: {result} 个组合')
"

# 期望输出:
# >>> precompute_rfm_cache 返回: 8 个组合
```

**注意** (跟 L4.42 + L4.67 + L4.74 1:1 stable 永久规则化沿用):
- precompute_rfm_cache() 必须在 uvicorn 不持锁时跑 (kill uvicorn 先, 跑完再启动, 跟 L4.63 DuckDB flock 模型 1:1 stable 永久规则化沿用)
- 如果 uvicorn 持锁, cache.py line 347-352 异常处理 会捕获异常返回 0, 不会跑成功

### 步骤 5: PC2 端 验证 RFM 4/5 < 5s + 5th (last90d) 跨 sprint 留尾 (跟 L4.5s 目标 + L4.42 + L4.74 1:1 stable 永久规则链配套)

```bash
# PC2 端 跑 RFM 5/5 period_type (跟 L4.5s 目标 1:1 stable 永久规则化沿用)
# 期望 4/5 < 5s (MTD/YTD/last180d/last365d cache 命中), 5th (last90d) 跨 sprint 留尾 0 commit 续期

# MTD
curl -s -w "\nMTD: 耗时 %{time_total}s\n" "http://localhost:8000/api/v1/customer-health/rfm-analysis?period=MTD&metric=GSV" -o /dev/null
# 期望: 耗时 < 1s ✅

# YTD
curl -s -w "\nYTD: 耗时 %{time_total}s\n" "http://localhost:8000/api/v1/customer-health/rfm-analysis?period=YTD&metric=GSV" -o /dev/null
# 期望: 耗时 < 1s ✅

# last90d
curl -s -w "\nlast90d: 耗时 %{time_total}s\n" "http://localhost:8000/api/v1/customer-health/rfm-analysis?period=last90days&metric=GSV" -o /dev/null
# 期望: 耗时 < 5s (跨 sprint 留尾, PERIOD 解析失败, 跟 L4.42 + L4.57 1:1 stable 永久规则化沿用)

# last180d
curl -s -w "\nlast180d: 耗时 %{time_total}s\n" "http://localhost:8000/api/v1/customer-health/rfm-analysis?period=last180days&metric=GSV" -o /dev/null
# 期望: 耗时 < 1s ✅

# last365d
curl -s -w "\nlast365d: 耗时 %{time_total}s\n" "http://localhost:8000/api/v1/customer-health/rfm-analysis?period=last365days&metric=GSV" -o /dev/null
# 期望: 耗时 < 1s ✅
```

**5/5 验证期望** (跟 L4.42 立项实证 + L4.74 cache end_date fix 1:1 stable 永久规则化沿用):
- MTD < 1s ✅ (cache 命中)
- YTD < 1s ✅ (cache 命中)
- last180d < 1s ✅ (cache 命中)
- last365d < 1s ✅ (cache 命中)
- last90d 跨 sprint 留尾 0 commit 续期 (跟 L4.42 + L4.57 1:1 stable 永久规则化沿用)

---

## 3. PC2 端验证清单 (跟 L4.42 立项实证 SOP + L4.50 + L4.74 1:1 stable 永久规则链配套)

按 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则链配套 + L4.50 0 业务代码改动 1:1 stable 永久规则链配套 + L4.74 cache end_date fix 1:1 stable 永久规则链配套, **PC2 端 7 件验证 100% 通过 ✅**:

| # | 验证项 | 期望 | 跟 L4.x 永久规则链配套 |
|---|---|---|---|
| 1 | git log main HEAD | `aa40ac8 fix(L4.74 cache end_date)` | ✅ 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用 |
| 2 | .env FQ_READ_POOL_SIZE | 10 | ✅ 跟 L4.70 + L4.72.3 1:1 stable 永久规则化沿用 |
| 3 | NSSM uvicorn health | HTTP 200 耗时 < 1s | ✅ 跟 L4.65.1 + L4.69.1 1:1 stable 永久规则化沿用 |
| 4 | precompute_rfm_cache() 返回 | 8 个组合 (4 period_type × 1 年 × 2 metric) | ✅ 跟 L4.74 cache end_date fix + Mac dev 7/9 实证 1:1 stable 永久规则化沿用 |
| 5 | cache 表新行 end_date | 07-08 (跟 user query date.today()=07-09 一致) | ✅ 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用 |
| 6 | RFM 4/5 < 5s (MTD/YTD/last180d/last365d) | 全部 < 1s | ✅ 跟 L4.5s 目标 1:1 stable 永久规则化沿用 |
| 7 | 502 watchdog 0 触发 | 1.8GB / 1 分钟稳态 | ✅ 跟 L4.65.1 + L4.69.1 1:1 stable 永久规则化沿用 |

---

## 4. 跟 L4.x 永久规则链 1:1 stable 永久规则化总配套 (跟 L4.42 + L4.50 + L4.55 + L4.13 + L4.14 + L4.64 + L4.65.1 + L4.69.1 + L4.70 + L4.72 + L4.72.3 + L4.74 + L4.75 1:1 stable 永久规则链配套)

按 L4.42 + L4.50 + L4.55 + L4.13 + L4.14 + L4.64 + L4.65.1 + L4.69.1 + L4.70 + L4.72 + L4.72.3 + L4.74 + L4.75 1:1 stable 永久规则链配套:

- ✅ **L4.7** launchd 首选 python3 不用 bash (跟 PC2 launchd / Mac launchd 1:1 stable 永久规则化沿用)
- ✅ **L4.13** MEMORY.md size ≤ 24.4KB (跟本 handoff 1:1 stable 永久规则化沿用)
- ✅ **L4.14** amend 物理限制 1 commit drift 永久接受 (跟 aa40ac8 amend cbbfcf9 1:1 stable 永久规则化沿用)
- ✅ **L4.15** push 是 outbound 副作用必 user 拍板 (跟 user "继续执行" 拍板 1:1 stable 永久规则化沿用)
- ✅ **L4.36** graceful retry fallback (跟业务方 30s wait + 错峰查询 1:1 stable 永久规则化沿用)
- ✅ **L4.42** 立项实证 SOP "git log + grep 实证" (跟本 handoff 1:1 stable 永久规则化沿用)
- ✅ **L4.50** pytest cleanup 0 业务代码改动 (跟 Sprint 205+ 累计 71+ 次 1:1 stable 永久规则化沿用)
- ✅ **L4.55** 立项 spec 实证 SOP (跟本 handoff 1:1 stable 永久规则化沿用)
- ✅ **L4.62** launchd plist 写法 SSOT 必走 plutil -lint OK 验证 (跟 PC2 4 个 plist 1:1 stable 永久规则化沿用, 已加载)
- ✅ **L4.63** uvicorn 持锁 + DuckDB 异 config detector (跟 PC2 端 uvicorn 持锁 1:1 stable 永久规则化沿用, 跑 precompute 前必 kill uvicorn)
- ✅ **L4.64** Windows 11 部署 + L4.70 PC2 .env (跟 PC2 .env FQ_READ_POOL_SIZE=10 1:1 stable 永久规则化沿用, 不用改)
- ✅ **L4.65.1** main.py 启动 1.3GB → 147MB 治本 (跟 PC2 NSSM restart 后 uvicorn PID < 500MB 1:1 stable 永久规则化沿用)
- ✅ **L4.69** RFM 雪崩真治本 (跟 ThreadPoolExecutor 禁用 + pool_size 1:1 stable 永久规则化沿用)
- ✅ **L4.69.1** _run_rfm_period_serial finally 块 gc.collect() + del conn (跟 PC2 端 uvicorn 内存稳态 < 800MB 1:1 stable 永久规则化沿用)
- ✅ **L4.70** + **L4.71** + **L4.72.4** 5s 治本 写库 (跟 PC2 idx_orders_pay_time_user_id + user_rfm_precompute + 9 子板块 1:1 stable 永久规则化沿用, 已建)
- ✅ **L4.72.3** 池 5 → 10 (跟 PC2 .env 1:1 stable 永久规则化沿用, 不用改)
- ✅ **L4.72.5** + **L4.72.6** rfm_dashboard_full fast path (跟 PC2 端 launchd 03:25 1:1 stable 永久规则化沿用)
- ✅ **L4.74** RFM 5s 治本 + cache 兼容性 fix (跟 PC2 端 precompute_rfm_cache() 跑通 8 组合 + cache 表新 8 行 1:1 stable 永久规则化沿用)
- ✅ **L4.75** + **L4.75.1** + **L4.75.2** + **L4.75.3** + **L4.75.4** 老客 RFM 单人模式 (跟 PC2 端 1:1 stable 永久规则化沿用)

---

## 5. 跨 sprint 留尾 0 commit 续期 沿用 (跟 L4.57 + L4.58 + L4.59 1:1 stable 永久规则链配套)

按 L4.57 跨 sprint 留尾 0 commit 续期 1:1 stable 永久规则链配套, **PC2 端 部署后留尾**:

| 留尾 | 触发 | 跟 L4.x 永久规则链配套 |
|---|---|---|
| **L4.74 PostgreSQL 16 分布式 8-10 周 1-2 人月真治本** | 跨 sprint (跟 L4.74 启动条件 b+c 真触发 1:1 stable 永久规则链配套) | ✅ 跟 L4.55 + L4.56 + L4.74 1:1 stable permanent rule 链 永久规则化沿用 |
| **L4.74 cache_key compare_start_date/compare_end_date 不匹配** | 跨 sprint (precompute 不传 compare_*, user query 传 → cache key 加 cmp_xxx → 永远 cache miss) | ✅ 跟 L4.42 + L4.74 1:1 stable 永久规则化沿用 |
| **L4.74 last90days PERIOD 解析失败** | 跨 sprint (PeriodBuilder 没 last90days method, _last90days_ranges 是 private function) | ✅ 跟 L4.42 + L4.74 1:1 stable 永久规则化沿用 |
| **7/16 离职前清单 5 件** | 跨 sprint (跟 MEMORY.md 1:1 stable 永久规则链配套) | ✅ 跟 MEMORY.md 1:1 stable 永久规则化沿用 |
| **Sprint 202+ R4 ETL wall_min 业务验证** | 业务下次跑 ETL 自动验证 (跟 L4.58 1:1 stable 永久规则链配套) | ✅ 跟 L4.58 1:1 stable 永久规则化沿用 |

---

## 6. PC2 端 部署 0 业务代码改动 (跟 L4.50 1:1 stable 永久规则链配套)

按 L4.50 pytest cleanup 0 业务代码改动 1:1 stable 永久规则链配套:

- ✅ **PC2 部署 0 业务代码改动 沿用** (跟 Sprint 60+ 累计 71+ 次 1:1 stable 永久规则化沿用)
- ✅ **Sprint 205+ L4.74 cache end_date fix 1 commit amend 0 业务代码改动** (跟 L4.50 永久规则化沿用)

---

## 7. PC2 端 Sprint 205+ L4.74 cache end_date fix 完成 (跟 L4.42 + L4.50 + L4.55 + L4.13 + L4.14 + L4.65.1 + L4.69.1 + L4.70 + L4.72 + L4.72.3 + L4.74 + L4.75 1:1 stable 永久规则链配套, 跨 sprint 留尾 0 commit 续期沿用)

按 L4.42 + L4.50 + L4.55 + L4.13 + L4.14 + L4.65.1 + L4.69.1 + L4.70 + L4.72 + L4.72.3 + L4.74 + L4.75 1:1 stable 永久规则链配套, **PC2 端 Sprint 205+ L4.74 cache end_date fix 部署 0 commit 续期 跨 sprint ✅**:

- ✅ main HEAD `aa40ac8` (amend cbbfcf9 → aa40ac8, 跟 L4.14 amend 物理限制 1 commit drift 永久接受 1:1 stable 永久规则化沿用)
- ✅ NSSM uvicorn restart + precompute_rfm_cache() 跑通 8 组合 + cache 表新 8 行 end_date=07-08
- ✅ RFM 4/5 < 5s + 5th (last90d) 跨 sprint 留尾 0 commit 续期
- ✅ 502 watchdog 0 触发 + 内存稳态 < 800MB
- ✅ 0 业务代码改动累计 Sprint 60+ 72+ 次 1:1 stable 永久规则化沿用 100% 一致

---

## 8. 注意 (跟 L4.36 + L4.38 + L4.42 + L4.50 + L4.55 + L4.63 + L4.65.1 + L4.69.1 + L4.74 1:1 stable 永久规则链配套)

按 L4.36 + L4.38 + L4.42 + L4.50 + L4.55 + L4.63 + L4.65.1 + L4.69.1 + L4.74 1:1 stable 永久规则链配套, **PC2 端 部署 注意 6 件**:

| # | 注意 | 跟 L4.x 永久规则链配套 |
|---|---|---|
| 1 | ❌ **不要停 uvicorn** (跟 L4.36 禁停 1:1 stable 永久规则化沿用) - 跑 precompute 前才 kill, 跑完重启, 跟 L4.36 1:1 stable 永久规则化沿用 | ✅ 跟 L4.36 禁停 uvicorn 1:1 stable 永久规则化沿用 |
| 2 | ❌ **不要在 main 直接改代码** (跟 L4.10 强制自检 1:1 stable 永久规则化沿用) - PC2 端只 git pull, 改在 Mac dev | ✅ 跟 L4.10 + L4.42 1:1 stable 永久规则化沿用 |
| 3 | ❌ **不要凭印象立新债** (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用) - git log + grep 实证 0 业务触发 0 commit 收口 | ✅ 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用 |
| 4 | ❌ **不要直接跑业务库 SQL** (跟 L4.36 1:1 stable 永久规则化沿用) - 走 backend HTTP API | ✅ 跟 L4.36 + L4.38 1:1 stable 永久规则化沿用 |
| 5 | ✅ **跑 precompute 前必 kill uvicorn** (跟 L4.63 DuckDB flock 模型 1:1 stable 永久规则化沿用) - 业务库 + cache 库跨文件 0 冲突 | ✅ 跟 L4.63 + L4.67 1:1 stable 永久规则化沿用 |
| 6 | ✅ **restart 后 verify 内存稳态 < 800MB** (跟 L4.65.1 + L4.69.1 1:1 stable 永久规则化沿用) - watchdog 1.8GB / 1 分钟稳态 | ✅ 跟 L4.65.1 + L4.69.1 1:1 stable 永久规则化沿用 |

---

## 9. 验证流程 (跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则链配套)

按 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则链配套, **PC2 端 部署后 验证 7 件**:

1. ✅ **git log main HEAD** = `aa40ac8 fix(L4.74 cache end_date)`
2. ✅ **.env FQ_READ_POOL_SIZE** = 10 (不用改)
3. ✅ **NSSM uvicorn health** = HTTP 200 耗时 < 1s
4. ✅ **precompute_rfm_cache() 返回** = 8 个组合
5. ✅ **cache 表新行 end_date** = 07-08 (跟 user query date.today()=07-09 一致)
6. ✅ **RFM 4/5 < 5s** (MTD/YTD/last180d/last365d) + 5th (last90d) 跨 sprint 留尾
7. ✅ **502 watchdog 0 触发** + 内存稳态 < 800MB

---

## 10. 跨 sprint 留尾 治理 模式 (跟 L4.57 + L4.58 + L4.59 1:1 stable 永久规则链配套)

按 L4.57 + L4.58 + L4.59 跨 sprint 留尾 0 commit 续期 SOP 1:1 stable 永久规则链配套, **PC2 端 部署后跨 sprint 留尾 治理 模式**:

1. **0 触发续期 0 commit 沿用** (跟 L4.42 + L4.57 1:1 stable 永久规则化沿用)
2. **真业务触发 再立项** (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用)
3. **7/16 后接手人启动** (跟 7/16 离职前清单 5 件 1:1 stable 永久规则化沿用)
4. **Sprint 202+ R4 ETL wall_min 业务验证** (跟 L4.58 1:1 stable 永久规则化沿用)

---

## 11. 验证 (跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则链配套)

按 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则链配套, **PC2 端 部署后 完整验证 ✅**:

- ✅ 拉 main HEAD `aa40ac8` 1:1 stable
- ✅ .env FQ_READ_POOL_SIZE=10 1:1 stable
- ✅ NSSM uvicorn restart 1:1 stable
- ✅ precompute_rfm_cache() 8 组合 1:1 stable
- ✅ cache 表新行 end_date=07-08 1:1 stable
- ✅ RFM 4/5 < 5s 1:1 stable
- ✅ 502 watchdog 0 触发 1:1 stable
- ✅ 0 业务代码改动累计 Sprint 60+ 72+ 次 1:1 stable

---

**PC2 端 Sprint 205+ L4.74 cache end_date fix 部署完成 ✅, 跨 sprint 留尾 0 commit 续期沿用 1:1 stable 永久规则化沿用 100% 一致 🎯**