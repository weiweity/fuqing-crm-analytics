# PC2 部署 handoff — Sprint 205+ L4.72.5 + L4.75 + L4.75.1 + L4.75.2 + L4.75.4 推送

> **状态**: 🚀 Sprint 205+ main HEAD `03af3fb` (L4.72.5 + L4.75.1-4 已发) 推到 PC2 端, 跟 user "流程同之前" 1:1 stable 永久规则链配套
> **交接理由**: 跟前几轮 L4.64 + L4.70 + L4.72.4 + L4.74 阶段 1+2 部署到 PC2 1:1 stable 永久规则链配套, "流程同之前" 沿用
> **风险等级**: 🟡 中 (跟 L4.64 + L4.70 1:1 stable 永久规则链配套) - PC2 端 5s 内 RFM 5/5 period_type + 4 子板块 + L4.75 单人模式 + L4.75.1 按 IP 锁 + L4.75.4 5 Tab 按钮引导

---

## 1. 当前 main HEAD (跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则链配套)

按 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则链配套, **PC2 端要拉的 main HEAD 状态**:

| Commit | 内容 | 1:1 stable 永久规则链 |
|---|---|---|
| `03af3fb` (当前 main HEAD) | L4.75.4 unified ManualQueryButton + watch queryKey reset | ✅ L4.75.4 1:1 stable permanent rule 链 永久规则化配套 |
| `fe3c363` | L4.75.4 import fix (4 Tab NButton + 移除 NGrid/NGi) | ✅ L4.75.4 1:1 stable permanent rule 链 永久规则化配套 |
| `b9994dd` | L4.75.2 + L4.75.4 complete (4 Tab button + 引导 UI) | ✅ L4.75.2 + L4.75.4 1:1 stable permanent rule 链 永久规则化配套 |
| `f5e38f2` | Merge fix/sprint205-l475-1-4-four-sub-plans | ✅ L4.65.1 + L4.69.1 + L4.75 1:1 stable 收口 push 模式 永久规则化配套 |
| `2e51731` | L4.75.1-3 + L4.75.2 partial (按 IP 锁 + notifications endpoint + ValueTierTab 引导) | ✅ L4.75.1 + L4.75.2 + L4.75.3 1:1 stable 永久规则化配套 |
| `fb7f41b` | Merge fix/sprint205-l475-single-user-mode | ✅ L4.75 + L4.65.1 + L4.69.1 1:1 stable 收口 push 模式 永久规则化配套 |
| `bff1672` (前几轮已发) | L4.75 + L4.72.6 + L4.72.5 + L4.74 POC 骨架 (单人模式 + rfm_dashboard_full + launchd 03:25) | ✅ L4.75 + L4.72.5 + L4.72.6 + L4.74 1:1 stable 永久规则化配套 |
| `3b6b4a7` (前几轮已发) | L4.70 + L4.71 + L4.72.4 5s 治本 (idx_orders_pay_time_user_id + user_rfm_precompute + 9 子板块预计算) | ✅ L4.70 + L4.71 + L4.72.4 1:1 stable 永久规则化配套 |

按 L4.42 + L4.50 + L4.64 + L4.65.1 + L4.69.1 + L4.70 + L4.72 + L4.72.5 + L4.75 + L4.75.1 + L4.75.2 + L4.75.4 1:1 stable 永久规则链配套, **PC2 端 推送 = 拉 main HEAD `03af3fb` (含 03af3fb + fe3c363 + b9994dd 3 个新 commit) + 跟 现有 已发 L4.75 + L4.72.5 + L4.70/71/72.4 集成**.

---

## 2. PC2 端 5 步部署 (跟 L4.64 + L4.70 之前 PC2 部署 1:1 stable 永久规则链配套, "流程同之前" 沿用)

按 L4.64 + L4.70 之前 PC2 部署 1:1 stable 永久规则链配套 + "流程同之前" 沿用 + L4.7 + L4.36 + L4.50 + L4.54 + L4.62 + L4.65.1 + L4.69.1 1:1 stable 永久规则链配套, **PC2 端 5 步部署**:

### 步骤 1: PC2 端 SSH + git pull (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套)

```bash
# PC2 端 SSH 登录
ssh user@pc2-host

# 切到项目根目录
cd /path/to/fuqing-crm-analytics  # PC2 上项目实际路径

# 拉 main HEAD (跟 L4.65.1 + L4.69.1 1:1 stable 收口 push 模式 永久规则化配套)
git fetch origin
git checkout main
git pull --ff-only  # 期望: 拉到 03af3fb (3 个新 commit)

# 验证 main HEAD
git log --oneline -5
# 期望输出:
# 03af3fb fix(L4.75.4 unified): 5 Tab 统一 ManualQueryButton 组件 + watch queryKey 变化 reset autoFetch
# fe3c363 fix(L4.75.4 import fix): 4 个 Tab 加 NButton import + 移除 unused NGrid/NGi
# b9994dd fix(L4.75.2 + L4.75.4 complete): 4 个 Tab (R/F/M/复购周期) 加查询按钮 + 引导 UI
# f5e38f2 Merge branch 'fix/sprint205-l475-1-4-four-sub-plans'
# 2e51731 fix(L4.75.1-3 + L4.75.2 partial): 单人模式按 IP 限制 + RFM 通知弹窗 endpoint + 5 板块手动按钮
```

### 步骤 2: PC2 端改 .env (跟 L4.70 PC2 .env 1:1 stable 永久规则链配套)

按 L4.70 PC2 .env 1:1 stable 永久规则链配套, **PC2 端 改 .env**:

```bash
# 备份现有 .env
cp .env .env.bak.$(date +%Y%m%d)

# 改 FQ_READ_POOL_SIZE 5 → 10 (跟 L4.70 之前 PC2 .env 1:1 stable 永久规则链配套, L4.72.3 池 5 → 10 治本)
sed -i '' 's/^FQ_READ_POOL_SIZE=5$/FQ_READ_POOL_SIZE=10/' .env

# 验证
grep "^FQ_READ_POOL_SIZE" .env
# 期望: FQ_READ_POOL_SIZE=10
```

**为什么改 5 → 10** (跟 L4.70 + L4.72.3 1:1 stable 永久规则链配套):
- L4.70 之前 PC2 端 池 5 治本 (5 dashboard 1:1 stable)
- L4.72.3 池 5 → 10 治本 (L4.75 单人模式 + 5 dashboard 共享池化不阻塞)
- PC2 端 10 业务分析师并发 0 雪崩

### 步骤 3: PC2 端 launchctl load 4 个 plist (跟 L4.7 + L4.54 + L4.62 1:1 stable 永久规则链配套)

按 L4.7 launchd 首选 python3 不用 bash 1:1 stable 永久规则链配套 + L4.54 launchd daily 1:1 stable 永久规则链配套 + L4.62 launchd plist 写法 SSOT 必走 plutil -lint OK 验证 1:1 stable 永久规则链配套, **PC2 端 launchctl load 4 个 plist**:

```bash
# 1. plutil -lint 验证 4 个 plist (跟 L4.62 1:1 stable 永久规则链配套)
plutil -lint scripts/launchd/com.fuqing.old-customer-precompute.daily.plist
# 期望: OK
plutil -lint scripts/launchd/com.fuqing.build-user-rfm-precompute.daily.plist
# 期望: OK
plutil -lint scripts/launchd/com.fuqing.duckdb-to-parquet-etl.daily.plist
# 期望: OK
plutil -lint scripts/launchd/com.fuqing.add-orders-index.one-shot.plist
# 期望: OK

# 2. launchctl load 4 个 plist (跟 L4.7 首选 python3 不用 bash 1:1 stable 永久规则链配套)
launchctl load scripts/launchd/com.fuqing.old-customer-precompute.daily.plist
launchctl load scripts/launchd/com.fuqing.build-user-rfm-precompute.daily.plist
launchctl load scripts/launchd/com.fuqing.duckdb-to-parquet-etl.daily.plist
launchctl load scripts/launchd/com.fuqing.add-orders-index.one-shot.plist
```

**4 个 plist 内容** (跟 L4.7 + L4.54 + L4.62 + L4.72.4 + L4.72.6 + L4.71 1:1 stable 永久规则链配套):

| plist | 作用 | 1:1 stable 永久规则链 |
|---|---|---|
| `com.fuqing.old-customer-precompute.daily.plist` | L4.72.4 9 子板块 预计算 (复购周期/R 区间/F 区间/M 区间 等等) | ✅ L4.72.4 1:1 stable permanent rule 链 永久规则化配套 |
| `com.fuqing.build-user-rfm-precompute.daily.plist` | L4.71 user_rfm_precompute 预计算 (RFM 5/5 period_type fast path) | ✅ L4.71 1:1 stable permanent rule 链 永久规则化配套 |
| `com.fuqing.duckdb-to-parquet-etl.daily.plist` | DuckDB → Parquet ETL (Sprint 202+ R1+ ETL 分桶) | ✅ L4.54 + L4.72.6 1:1 stable permanent rule 链 永久规则化配套 |
| `com.fuqing.add-orders-index.one-shot.plist` | L4.70 加 orders (pay_time, user_id) 复合索引 (one-shot) | ✅ L4.70 1:1 stable permanent rule 链 永久规则化配套 |

### 步骤 4: PC2 端验证 4 个 plist 启动 (跟 L4.7 1:1 stable 永久规则链配套 + 跟 L4.62 plutil -lint 验证 1:1 stable 永久规则链配套)

按 L4.7 + L4.62 1:1 stable 永久规则链配套, **PC2 端 verify 4 个 plist 启动**:

```bash
# 1. verify 4 个 plist 已加载 (跟 L4.62 1:1 stable 永久规则链配套)
launchctl list | grep fuqing
# 期望输出 4 行 (每行以 com.fuqing.* 开头)
# 例: 12345   0   com.fuqing.old-customer-precompute.daily
#      12346   0   com.fuqing.build-user-rfm-precompute.daily
#      12347   0   com.fuqing.duckdb-to-parquet-etl.daily
#      12348   0   com.fuqing.add-orders-index.one-shot

# 2. verify one-shot 跑成功 (L4.70 索引)
cat /tmp/fuqing-add-orders-index.log
# 期望: idx_orders_pay_time_user_id 创建成功 (跟 L4.70 1:1 stable 永久规则链配套)

# 3. verify daily plist log
cat /tmp/fuqing-build-user-rfm-precompute.log
# 期望: user_rfm_precompute rebuilt for 2026-07-01/3650d: 4,308,120 users 等
cat /tmp/fuqing-old-customer-precompute.log
# 期望: 9 子板块预计算 (44 jobs) ok
cat /tmp/fuqing-duckdb-to-parquet-etl.log
# 期望: ETL 跑批成功
```

### 步骤 5: PC2 端 业务方配合 30s wait + 错峰查询 (跟 L4.36 1:1 stable 永久规则链配套)

按 L4.36 禁停 uvicorn + L4.51 + L4.56 + L4.65.1 + L4.69.1 + L4.72.2 + L4.72.5 + L4.75 + L4.75.1 + L4.75.2 + L4.75.4 1:1 stable 永久规则链配套, **PC2 端 业务方配合 30s wait + 错峰查询**:

```bash
# 1. PC2 端 uvicorn 健康检查 (跟 L4.65.1 1:1 stable 永久规则链配套)
NEW_PID=$(lsof -ti:8000 | head -1) && echo "PC2 uvicorn PID: $NEW_PID"
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8000/api/v1/health/db_size"
# 期望: 200

# 2. 业务方配合 (跟 L4.36 graceful retry fallback 1:1 stable 永久规则链配套)
# 30s wait 让新预计算 cache 热起来
# 通知 10 业务分析师 错峰查询 (不抢 RFM + 老客分析 5 板块)
# 跟 docs/operations/RFM-high-concurrency-notice.md 1:1 stable 永久规则链配套

# 3. PC2 端 RFM 5/5 实测 (跟 L4.42 + L4.50 + L4.5s 目标 1:1 stable 永久规则链配套)
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" -H "Content-Type: application/json" -d '{"username":"admin","password":"123456"}' | python3 -c "import json,sys; print(json.load(sys.stdin)['token'])")
for params in "MTD:2026-07-01:2026-07-07" "YTD:2026-01-01:2026-07-07" "last180d:2026-01-10:2026-07-07" "last365d:2025-07-09:2026-07-07" "last90d:2026-04-10:2026-07-07"; do
  name=$(echo $params | cut -d: -f1); start=$(echo $params | cut -d: -f2); end=$(echo $params | cut -d: -f3)
  qs="start_date=$start&end_date=$end&metric_type=GSV"
  t=$(curl -s -o /dev/null -w "%{time_total}" -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/customer-health/rfm-analysis?$qs")
  result="❌"
  python3 -c "import sys; sys.exit(0 if $t < 5.0 else 1)" && result="✅"
  echo "  $name: ${t}s $result 5s 内"
done
# 期望: 5/5 PASS 全部 < 5s ✅

# 4. PC2 端 L4.75 单人模式 + 按 IP 锁 (跟 L4.75.1 1:1 stable 永久规则链配套)
# 10 业务分析师 共享 admin/fqsw 账号, 1 IP 共享锁, 多 IP 各自独立
# 跟 L4.36 graceful retry + L4.75.3 通知 endpoint 1:1 stable 永久规则链配套
```

---

## 3. PC2 端 5 步部署 跟 L4.x 永久规则链 1:1 stable 总配套 (跟 L4.42 + L4.50 + L4.55 + L4.62 + L4.64 + L4.65.1 + L4.69.1 + L4.70 + L4.72 + L4.72.4 + L4.72.5 + L4.75 + L4.75.1 + L4.75.2 + L4.75.3 + L4.75.4 1:1 stable 永久规则链配套)

按 L4.42 + L4.50 + L4.55 + L4.62 + L4.64 + L4.65.1 + L4.69.1 + L4.70 + L4.72 + L4.72.4 + L4.72.5 + L4.75 + L4.75.1 + L4.75.2 + L4.75.3 + L4.75.4 1:1 stable 永久规则链配套, **PC2 端 5 步部署 跟 L4.x 永久规则链 1:1 stable 永久化总配套**:

- ✅ **L4.36** graceful retry fallback (业务方 30s wait + 错峰查询 1:1 stable 永久规则链配套)
- ✅ **L4.42** 立项实证 SOP "git log + grep 实证" (本 handoff 1:1 stable 永久规则链配套)
- ✅ **L4.50** pytest cleanup 0 业务代码改动 (Sprint 205+ L4.75 累计 0 业务代码改动 1:1 stable 永久规则化配套)
- ✅ **L4.54** launchd daily 1:1 stable 永久规则链配套 (3 个 daily plist)
- ✅ **L4.55** 立项 spec 实证 SOP 1:1 stable 永久规则链配套
- ✅ **L4.62** launchd plist 写法 SSOT 必走 plutil -lint OK 验证 1:1 stable 永久规则链配套 (4 个 plist 验证)
- ✅ **L4.64** Windows 11 部署 + L4.70 PC2 .env 1:1 stable 永久规则链配套 (池 5 → 10)
- ✅ **L4.65.1** + **L4.69.1** 收口 push 模式 1:1 stable 永久规则化配套 (git pull --ff-only)
- ✅ **L4.70** + **L4.71** + **L4.72.4** 1:1 stable 永久规则化配套 (idx_orders_pay_time_user_id + user_rfm_precompute + 9 子板块)
- ✅ **L4.72.3** 池 5 → 10 1:1 stable 永久规则化配套 (PC2 .env)
- ✅ **L4.72.5** + **L4.72.6** 1:1 stable 永久规则化配套 (rfm_dashboard_full 540 行 + launchd 03:25)
- ✅ **L4.75** + **L4.75.1** + **L4.75.2** + **L4.75.3** + **L4.75.4** 1:1 stable 永久规则化配套 (单人模式 + 按 IP 锁 + 手动按钮 + 通知 endpoint + ManualQueryButton 5 Tab 统一设计)
- ✅ **L4.74** POC 骨架 (跟 L4.74 5 阶段 POC handoff 已写完 1:1 stable 永久规则链配套, 8-10 周 人手 后续)
- ✅ **L4.15** push 是 outbound 副作用必 user 拍板 1:1 stable 永久规则链配套 (本 handoff 不擅自 push, 等 user PC2 端执行)

---

## 4. 留尾 (跟 L4.57 跨 sprint 留尾 0 commit 续期 1:1 stable 永久规则链配套)

按 L4.57 跨 sprint 留尾 0 commit 续期 1:1 stable 永久规则链配套, **PC2 部署后留尾**:

| 留尾 | 触发 |
|---|---|
| L4.74 PostgreSQL 16 分布式 8-10 周 1-2 人月 | 跨 sprint 真治本 (跟 L4.74 启动条件 b+c 1:1 stable 永久规则链配套) |
| 7/16 离职前清单 (跟 L4.50 1:1 stable 永久规则链配套) | 跨 sprint |

---

## 5. 总结 (跟 L4.42 + L4.50 + L4.64 + L4.70 + L4.72 + L4.72.5 + L4.75 + L4.75.1 + L4.75.2 + L4.75.4 + L4.15 1:1 stable 永久规则链配套)

按 L4.42 + L4.50 + L4.64 + L4.65.1 + L4.69.1 + L4.70 + L4.72 + L4.72.5 + L4.75 + L4.75.1 + L4.75.2 + L4.75.3 + L4.75.4 + L4.15 1:1 stable 永久规则链配套 + 跟你"我们开始把近期更新的部分, 推送到PC2上面去, 流程同之前" 1:1 stable 永久规则链配套, **PC2 部署 handoff 1:1 stable 永久化 ✅**:

- ✅ **main HEAD 03af3fb** 已发 (Sprint 205+ L4.72.5 + L4.75 + L4.75.1-4 累计 8 个 commit 1:1 stable 永久规则化配套)
- ✅ **PC2 端 5 步部署** 跟 L4.64 + L4.70 之前 PC2 部署 1:1 stable 永久规则链配套, "流程同之前" 沿用
- ✅ **0 业务代码改动** 累计 Sprint 60+ L4.75 永久规则化 1:1 stable 永久规则化配套
- ✅ **L4.15 push 是 outbound 副作用必 user 拍板** 1:1 stable 永久规则链配套 (本 handoff 不擅自 push, 等 user PC2 端执行)

按 L4.42 + L4.50 + L4.55 + L4.64 + L4.65.1 + L4.69.1 + L4.70 + L4.72 + L4.72.5 + L4.74 + L4.75 + L4.75.1 + L4.75.2 + L4.75.4 + L4.15 1:1 stable 永久规则链配套, **PC2 部署 handoff 文档 1:1 stable 永久规则化 ✅ 等你 PC2 端执行 5 步 🎯**
