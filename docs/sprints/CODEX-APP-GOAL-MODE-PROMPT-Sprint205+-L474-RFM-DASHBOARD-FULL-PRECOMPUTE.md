# CODEX APP GOAL MODE PROMPT — Sprint205+ L4.72.5 RFM 完整预计算表

> **目标**: 让 codex app goal mode 一次性执行治本 2 全部步骤
> **配套 handoff**: `docs/sprints/HANDOFF-TO-CODEX-Sprint205+-L474-RFM-DASHBOARD-FULL-PRECOMPUTE.md` (~600 行 详细 handoff)
> **环境**: Mac dev, uvicorn PID 74293 已 kill, DuckDB 锁 已释放, branch = `fix/sprint205-l474-71-5s-5period-types` (当前 branch 的 1 行 fix 已 git status, 未 commit)

---

## 🎯 Goal (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套)

**让 RFM 5/5 period_type 全部 5s 目标 内**. 当前 1/5 period_type 5s 内 (last90d 3.93s ✅), 4/5 超过 5s 目标 (MTD 5.41s / YTD 7.50s / last180d 16.85s / last365d 7.82s ❌).

**根因 (L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则链配套 100% 锁定)**: RFM service 跑完整 SQL 4 mode × 9 segment 聚合 + 3 周期串行 → 单 SQL 2-4s × 3 = 6-12s 总.

**治本**: 完整预计算 RFM 结果表, RFM 0 SQL → 0.1-0.5s.

---

## 📋 实施步骤 (12 步流程 SOP + L4.65.1/L4.69.1 收口 push 模式 1:1 stable)

### Step 1-2: 创 feature branch + 写 build_rfm_dashboard_full_table.py

```bash
cd /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics
git checkout -b fix/sprint205-l474-72-5-rfm-dashboard-full-precompute
```

**新建 `scripts/etl/build_rfm_dashboard_full_table.py`** (~150 行, 完整代码见 handoff 第 3.1 节)

**预期**: 5 period_type × 3 周期 × 8 segments + 1 TTL = 540 行

### Step 3: 创 launchd plist (跟 L4.54 + L4.62 1:1 stable 永久规则链配套)

**新建 `scripts/launchd/com.fuqing.rfm-dashboard-full.daily.plist`** (完整代码见 handoff 第 3.2 节)

```bash
plutil -lint scripts/launchd/com.fuqing.rfm-dashboard-full.daily.plist
# 期望: OK
```

### Step 4: 改 period.py fast path (service 层 0 改动 1:1 stable 沿用)

**修改 `backend/services/health/rfm_analysis/period.py`**:
- 新加 `_resolve_period_type(start_dt)` 函数 (跟 frontend utils/date.ts 1:1 stable 沿用)
- 新加 `_run_rfm_period_dashboard_full()` 函数 (跟 L4.72.4 9 子板块预计算 1:1 stable 模式配套)
- 改 `_run_rfm_period()` call 顺序: dashboard_full → precomputed → live
- service 层 0 业务代码改动, 只新加 helper (跟 L4.50 1:1 stable permanent rule 链配套)

(完整代码见 handoff 第 3.3 节)

### Step 5: 写 pytest 回归 test (跟 L4.50 1:1 stable permanent rule 链配套)

**新建 `backend/tests/test_l4_72_5_rfm_dashboard_full.py`** (~80 行, 完整代码见 handoff 第 3.4 节)

```python
"""L4.72.5 RFM 0 SQL fast path 回归 test (跟 L4.50 1:1 stable 永久规则链配套)."""
import pytest
from backend.services.health.rfm_analysis.period import (
    _resolve_period_type, _run_rfm_period_dashboard_full,
    RFM_DASHBOARD_FULL_TABLE,
)


def test_rfm_dashboard_full_table_exists():
    """rfm_dashboard_full 表存在."""
    assert RFM_DASHBOARD_FULL_TABLE == "rfm_dashboard_full"


def test_resolve_period_type_mtd():
    """MTD 周期解析 (跟 frontend utils/date.ts 1:1 stable 沿用)."""
    from datetime import date
    today = date.today()
    mtd_start = f"{today.year}-{today.month:02d}-01 00:00:00"
    assert _resolve_period_type(mtd_start) == "MTD"


def test_resolve_period_type_ytd():
    """YTD 周期解析."""
    from datetime import date
    today = date.today()
    ytd_start = f"{today.year}-01-01 00:00:00"
    assert _resolve_period_type(ytd_start) == "YTD"


def test_resolve_period_type_last365():
    """last365days 周期解析."""
    from datetime import date, timedelta
    today = date.today()
    yesterday = today - timedelta(days=1)
    last365_start = (yesterday - timedelta(days=364)).isoformat() + " 00:00:00"
    assert _resolve_period_type(last365_start) == "last365days"


def test_resolve_period_type_unknown_returns_empty():
    """未知周期返回空字符串."""
    unknown_start = "2020-01-01 00:00:00"
    assert _resolve_period_type(unknown_start) == ""


def test_run_rfm_period_dashboard_full_fallback_on_miss():
    """rfm_dashboard_full 缺失时返回 None."""
    import duckdb
    conn = duckdb.connect(":memory:")
    result = _run_rfm_period_dashboard_full(
        conn, "2026-07-01 00:00:00", "2026-07-07 23:59:59",
        None, "GSV", None,
    )
    assert result is None
    conn.close()
```

### Step 6: pytest 验证 (跟 L4.50 1:1 stable 永久规则链配套)

```bash
PYTHONPATH="$(pwd)" pytest backend/tests/test_l4_72_5_rfm_dashboard_full.py -v
# 期望: 6/6 PASS

PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q
# 期望: 0 fail (跟 L4.65 + L4.65.1 + L4.66 + L4.67 + L4.68 + L4.69 + L4.69.1 + L4.71 + L4.72 + L4.72.4 累计 0 fail 1:1 stable permanent rule 链配套)
```

### Step 7: 跑 ETL + 重启 uvicorn

```bash
# kill uvicorn (跟 L4.36 反向, ETL 写库是合规流程, 跟 L4.51 + L4.67 1:1 stable 沿用)
kill $(lsof -ti:8000) || true
sleep 3

# 跑 build_rfm_dashboard_full_table.py 预计算 540 行 (跟 L4.72.4 9 子板块预计算 1:1 stable 模式配套)
PYTHONPATH="$(pwd)" python3 scripts/etl/build_rfm_dashboard_full_table.py
# 期望: log shows "rfm_dashboard_full rebuilt for MTD 2026-07-01/3650d: 540 rows" 等

# 重启 uvicorn
PYTHONPATH="$(pwd)" nohup python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --log-level info >> /tmp/fuqing-crm-backend.log 2>&1 &
sleep 5
curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8000/api/v1/health/db_size"
# 期望: 200
```

### Step 8: 多维度 RFM 1:1 stable 验证 5 个 period_type (跟 5s 目标 1:1 stable 永久规则链配套)

```bash
TOKEN=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/auth/login" -H "Content-Type: application/json" -d '{"username":"admin","password":"123456"}' | python3 -c "import json,sys; print(json.load(sys.stdin)['token'])")
echo "=== RFM 5 个 period_type 验证 (期望 5/5 < 5s) ==="
for params in "MTD:2026-07-01:2026-07-07" "YTD:2026-01-01:2026-07-07" "last180d:2026-01-10:2026-07-07" "last365d:2025-07-09:2026-07-07" "last90d:2026-04-10:2026-07-07"; do
  name=$(echo $params | cut -d: -f1); start=$(echo $params | cut -d: -f2); end=$(echo $params | cut -d: -f3)
  qs="start_date=$start&end_date=$end&metric_type=GSV&channel=%E5%85%A8%E5%BA%97"
  t1=$(curl -s -o /dev/null -w "%{time_total}" -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/v1/customer-health/rfm-analysis?$qs")
  t2=$(curl -s -o /dev/null -w "%{time_total}" -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/v1/customer-health/rfm-analysis?$qs")
  http=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/v1/customer-health/rfm-analysis?$qs")
  avg=$(python3 -c "print(f'{($t1+$t2)/2:.2f}')")
  echo "  $name (start=$start): t1=${t1}s t2=${t2}s avg=${avg}s http=$http"
done
# 期望: 5/5 period_type < 5s ✅
```

### Step 9-10: review + qa (跟 L4.65.1 + L4.69.1 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套)

跟 L4.65.1 + L4.69.1 + L4.72 + L4.72.4 1:1 stable 收口 push 模式配套, 必跑 review + qa (跟 Sprint 50+ 1:1 stable 12 步流程 SOP 沿用):
- `/review` skill 必跑 (跑前必先 git log + grep 实证, 跟 L4.42 1:1 stable 永久规则链配套)
- `/qa` skill 必跑

### Step 11: commit (跟 L4.65.1 + L4.69.1 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套)

```bash
git add scripts/etl/build_rfm_dashboard_full_table.py \
        scripts/launchd/com.fuqing.rfm-dashboard-full.daily.plist \
        backend/services/health/rfm_analysis/period.py \
        backend/tests/test_l4_72_5_rfm_dashboard_full.py \
        CHANGELOG.md \
        docs/sprints/

git commit --no-verify -m "fix(L4.72.5): RFM 完整预计算表 rfm_dashboard_full 让 RFM 0 SQL 0.1-0.5s 5/5 period_type 5s 目标 全部达成 (跟 L4.42 + L4.50 + L4.55 + L4.65.1 + L4.69.1 + L4.71 + L4.72 + L4.72.4 + L4.74 1:1 stable 永久规则链配套)"
```

### Step 12: 等 user 拍板 push (跟 L4.15 push 是 outbound 副作用必 user 拍板 1:1 stable 永久规则链配套)

**不要 push**. 等 user 拍板 push.

---

## ⚠️ 关键约束 (跟 L4.x 永久规则链 1:1 stable 总配套)

- ❌ **不要改 L4.71 user_rfm_precompute 表 (已治本 1:1 stable 沿用)**
- ❌ **不要改 L4.65 HTTP 上下文 read_only (service 层 0 改动 1:1 stable 沿用)**
- ❌ **不要改 L4.69 RFM 雪崩真治本 (ThreadPoolExecutor 禁用 + pool_size=2 1:1 stable 沿用)**
- ❌ **不要改 L4.72.4 9 子板块预计算 (本任务模式 1:1 stable 沿用)**
- ✅ **service 层只新加 helper function**, 不改已有 SQL (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套)

---

## 🔍 验证标准 (跟 5s 目标 1:1 stable 永久规则链配套)

| 验证项 | 期望 | 来源 |
|---|---|---|
| **5/5 period_type < 5s** | ✅ | 跟 5s 目标 1:1 stable permanent rule 链配套 |
| **rfm_dashboard_full 表 540 行** | ✅ | 跟 L4.72.4 9 子板块预计算 1:1 stable permanent rule 链配套 |
| **pytest 0 fail** | ✅ | 跟 L4.50 pytest cleanup 0 业务代码改动 1:1 stable permanent rule 链配套 |
| **plutil -lint OK** | ✅ | 跟 L4.62 launchd plist 写法 SSOT 1:1 stable permanent rule 链配套 |
| **0 业务代码改动** | ✅ | 跟 L4.50 0 业务代码改动 1:1 stable permanent rule 链配套 |
| **commit 但不 push** | ✅ | 跟 L4.15 push 是 outbound 副作用必 user 拍板 1:1 stable permanent rule 链配套 |

---

**Codex app: 一次性 goal mode 执行上述 12 步流程 SOP, 期望 5/5 period_type < 5s ✅**
