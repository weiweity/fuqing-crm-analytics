# 测试基础设施 (Test Infrastructure)

> pytest fixture 模式 + race flake 治本 (Sprint 53) + 真连 test skipif 模式 + ground-truth-lint 钩子 + L4.3/L4.4/L4.6 永久规则汇总。

**最后更新**: 2026-06-21
**总测试数**: 749 passed / 1 skipped (Sprint 54 收口, e2e 12/12, L2 spec-lint 5/5, L1 SQL f-string 0 violations)

---

## 1. pytest fixture 模式 (Sprint 53 治本后)

### 1.1 核心 fixture: `isolated_duckdb` (session scope)

> **Sprint 53 治本**: per-worker tmp DuckDB + ATTACH production READ_ONLY + PRAGMA search_path. 闭环 5 sprint 复发 race flake (S32.3 / S34.1 / S36-1 / S37 / S38 透明化)。

**位置**: `backend/tests/conftest.py:109-140`

```python
@pytest.fixture(scope="session")
def isolated_duckdb():
    """为每个 pytest-xdist worker 提供隔离 DuckDB。

    worker 只写自己的临时数据库，并以只读方式 ATTACH 生产库。search_path
    让业务代码继续用无 schema 前缀的表名读取生产数据。
    """
    if not _PROD_DUCKDB_AVAILABLE:
        pytest.skip("production DuckDB 不可用")

    from backend.config import DUCKDB_MEMORY_LIMIT, DUCKDB_PATH

    tmp = tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    # DuckDB 1.5+ 会拒绝已存在但为空的文件；保留安全生成的路径即可。
    tmp_path.unlink()
    conn = None

    try:
        conn = duckdb.connect(
            str(tmp_path),
            config={"memory_limit": DUCKDB_MEMORY_LIMIT},
        )
        prod_path = str(DUCKDB_PATH).replace("'", "''")
        conn.execute(f"ATTACH '{prod_path}' AS prod (READ_ONLY)")
        conn.execute("PRAGMA search_path='main,prod'")
        yield conn
    finally:
        if conn is not None:
            conn.close()
        tmp_path.unlink(missing_ok=True)
```

**关键设计**:
- **session scope**: 一个 pytest-xdist worker 整个 session 复用 1 个连接, 避免反复开连接
- **per-worker tmp DuckDB**: `tempfile.NamedTemporaryFile` 自动 unlink 后新建, 4 worker 并发 0 锁冲突
- **ATTACH READ_ONLY**: 不抢生产库 write lock, 不影响 uvicorn 服务
- **PRAGMA search_path='main,prod'**: 业务代码继续用无 schema 前缀表名 (`orders` 而不是 `prod.orders`), 零侵入

**性能**: Sprint 53 4 worker 并发 0 锁冲突 (vs Sprint 38 串行 2.31s 退化 → Sprint 53 并行 0 退化)

---

### 1.2 配套 fixture: `monkeypatch_connection` (function scope)

> **L4.3 强制规则**: 新增真连 test 必须用 `monkeypatch_connection` fixture, 禁止直接 `duckdb.connect(production_path)`.

**位置**: `backend/tests/conftest.py:143-194`

```python
@pytest.fixture
def monkeypatch_connection(isolated_duckdb):
    """让当前 test 的服务层连接使用当前 worker 的隔离 DuckDB。"""
    from backend.db import connection

    class FakeThreadSafeConnection:
        """测试用最小连接包装器；查询结果直接使用 DuckDB 原生 cursor。"""

        def __init__(self, conn):
            self._conn = conn

        def execute(self, query, parameters=None):
            if parameters is not None:
                return self._conn.execute(query, parameters)
            return self._conn.execute(query)

        def close(self):
            pass

        def __getattr__(self, name):
            return getattr(self._conn, name)

    original_conn = connection._conn
    original_get_connection = connection.get_connection

    def _fake_get_connection():
        return FakeThreadSafeConnection(isolated_duckdb)

    # pytest 先收集全部 test module，再创建 fixture。收集期间已经用
    # ``from ... import get_connection`` 绑定的 service 也必须一起替换。
    for module in tuple(sys.modules.values()):
        if (
            module is not None
            and getattr(module, "get_connection", None) is original_get_connection
        ):
            module.get_connection = _fake_get_connection

    connection._conn = None
    connection.get_connection = _fake_get_connection

    try:
        yield isolated_duckdb
    finally:
        # test 执行期间延迟 import 的 service 也可能绑定 fake；一并恢复
        for module in tuple(sys.modules.values()):
            if module is None:
                continue
            if getattr(module, "get_connection", None) is _fake_get_connection:
                module.get_connection = original_get_connection
        connection.get_connection = original_get_connection
        connection._conn = original_conn
```

**关键设计**:
- **function scope**: 每个 test 独立 monkeypatch + 独立恢复, 避免 test 间污染
- **FakeThreadSafeConnection**: 最小包装器, `__getattr__` 透传 DuckDB 原生 cursor
- **遍历 sys.modules**: 收集期间已经 `from backend.db import get_connection` 绑定的 service 也必须一起替换, 防 Sprint 53 Stage 3 抓的 `.env` 覆盖 test credentials 坑

**新真连 test 模板**:
```python
def test_my_real_query(monkeypatch_connection):
    """真连 test — 必须用 monkeypatch_connection fixture。"""
    from backend.services.my_service import get_my_data
    result = get_my_data(channel="直播", start_date="2026-01-01")
    assert len(result) > 0
```

---

## 2. race flake 治本 (Sprint 53)

### 2.1 历史问题 (5 sprint 复发)

| Sprint | 症状 | 治标方案 | 治本 ROI |
|---|---|---|---|
| S32.3 | TestMetricsAPI parallel fail | pytest-xdist `-n 0` serial | 低 (DuckDB 文件锁 exclusive) |
| S34.1 | parallel 偶发 fail | 3 真连 test 加 `_IN_XDIST_PARALLEL` skipif | 中 |
| S36-1 | 复发 | skipif + pre-push uvicorn 状态检测 | 中 |
| S37 | CI 仍 fail | 加 fixture 模式 | 中 |
| S38 | Sprint 38 plan-eng-review 推荐治本 | per-test tmp DuckDB ATTACH, 发现 exclusive ATTACH 也冲突, 改治标 | 评估 ROI 重评错误 |

**根因**: DuckDB 文件锁 exclusive, 任何 2 个进程开同一文件 connection 必冲突。pytest-xdist 多 worker 必中招。

### 2.2 Sprint 53 治本

> **Sprint 53 验证 ATTACH 可行, Sprint 38 ROI 重评错误**。

**方案**: per-worker tmp DuckDB + ATTACH production READ_ONLY

| 阶段 | 步骤 | 说明 |
|---|---|---|
| Stage 1 (架构) | Claude 设计 fixture 协议 | 写 HANDOFF + AGENTS.md 同步 |
| Stage 2 (Codex 实施) | 改 conftest.py 加 `isolated_duckdb` + `monkeypatch_connection` | Codex 不动 git, 本地编辑 |
| Stage 3 (Claude review) | 抓 1 真 bug: `.env` load_dotenv 覆盖 test credentials | Claude 主 agent 修 |
| Stage 4 (commit/push) | 独立 commit + push + merge | 12 步流程完整 |

**验证**: 677 passed / 1 skipped (Sprint 53 收口) → 749 passed / 1 skipped (Sprint 54 收口, 加 70+ 新 test)

### 2.3 实战教训

1. **ATTACH READ_ONLY 不会抢 write lock**: ATTACH 跟直接 connect 行为不同, ATTACH 用只读句柄访问生产库
2. **PRAGMA search_path 是关键**: 业务代码 0 改动, schema prefix 由 search_path 解析
3. **DuckDB 1.5+ 拒绝空文件**: `tempfile.NamedTemporaryFile` + `unlink()` 后 DuckDB.connect() 才能正常
4. **fixture protocol 必须 function scope restore**: `monkeypatch_connection` 遍历 sys.modules 找延迟 import service, 一并恢复

---

## 3. 真连 test skipif 模式 (L4.4)

### 3.1 `_PROD_DUCKDB_AVAILABLE` 检测

> **Sprint 39 CI 爆红修复 (7+ sprint 一直红闭环)**: 加 module-level 常量, 跨 test 共享 skipif 条件。

**位置**: `backend/tests/conftest.py:73-106`

```python
def _detect_prod_duckdb_available() -> bool:
    """动态检测 production DuckDB 是否可访问: 文件存在 + duckdb.connect() 不抛异常.

    Sprint 39: 替代 hardcoded _PROD_DUCKDB_PATH. 跨工作树/clone/CI
    友好. 只 check 文件存在 + 可连接 (read_only=True 不抢 write lock), 不 check 表存在
    (避免 sprint 期间 schema 变动引发 false negative).

    Returns:
        True if production DuckDB 可访问 (本地开发 / 用户 clone + 自己跑 ETL 跑批后)
        False if 不可访问 (fresh checkout / CI runner / data/processed/ 不存在)
    """
    try:
        from backend.config import DUCKDB_PATH
        path = Path(str(DUCKDB_PATH))
    except Exception:
        # backend.config 不可 import (CI 早期失败) → 不可访问
        return False

    if not path.exists():
        return False

    # 文件存在, 进一步 check 可连接 (read_only 不抢 write lock, 不会跟 uvicorn 冲突)
    try:
        import duckdb
        conn = duckdb.connect(str(path), read_only=True)
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return True
    except Exception:
        return False


# Module-level 常量: 跨多个 test 共享 skipif 条件
_PROD_DUCKDB_AVAILABLE = _detect_prod_duckdb_available()
```

**关键设计**:
- **动态检测**: 不 hardcode 路径, 跨 worktree/clone/CI 友好
- **read_only=True**: 检测时不开 write lock, 跟 uvicorn 0 冲突
- **不 check 表存在**: 避免 sprint 期间 schema 变动 false negative
- **module-level 常量**: 跨 test 共享, 避免重复检测

### 3.2 跨 3 个真连 test 应用

| Test | 路径 | skipif 位置 |
|---|---|---|
| `test_api_integration.py` | `backend/tests/` | module-level `pytestmark` |
| `test_churn_user_list_fstring.py` | `backend/tests/` | module-level `pytestmark` |
| `test_w4_t7_integration.py` | `backend/tests/` | module-level `pytestmark` |

**L4.4 模板**:
```python
import pytest
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE

pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用",
)


def test_my_real_query(monkeypatch_connection):
    ...
```

**CI 行为**:
- CI runner (无 `data/processed/fuqing_crm.duckdb`) → `_PROD_DUCKDB_AVAILABLE=False` → test skip (rc=0)
- 本地开发 (有 db) → `_PROD_DUCKDB_AVAILABLE=True` → test 跑 (Sprint 53 治本后无 race flake)

---

## 4. ground-truth-lint 钩子 (L3 FilterBuilder, Sprint 54)

### 4.1 L3 钩子: `check_filter_builder_usage.py`

> **Sprint 53.5 → 54 闭环**: backend/services/** 14 文件 100% 覆盖. 规则: SQL 变量赋值禁止 f-string 内嵌用户输入.

**位置**: `backend/scripts/check_filter_builder_usage.py`

**检测范围**:
- 业务字段: `channel` / `category_id` / `level` / `granularity` / `user_id` / `segment_id` / `min_support` / `min_confidence`
- 检测: 是否走 `?` 占位符 + `FilterBuilder.build()`

**反例 vs 正例**:
```python
# ❌ 反例: f-string 内嵌用户输入 → SQL 注入
sql = f"""
SELECT * FROM orders
WHERE channel = '{channel}'
"""

# ✅ 正例: FilterBuilder.build() + DuckDB ? DB-API
fb = FilterBuilder()
fb.with_channels([channel])
where_sql, params = fb.build()
conn.execute(f"SELECT * FROM orders WHERE {where_sql}", params)
```

**pre-commit hook 集成**:
- L1 范围: `backend/services/**` + `backend/scripts/**` + `scripts/etl/**` (Sprint 36-4 对称补盲)
- L3 范围: `backend/services/**` 14 文件
- 触发: pre-commit (跟 L1 SQL f-string lint 共存)
- 当前: 0 violations (Sprint 54 收口)

### 4.2 70 files scan 输出

```bash
$ python -m backend.scripts.check_filter_builder_usage --committed
Scanning 70 files in backend/services/...
[OK] 70/70 files use FilterBuilder.build() pattern
0 violations found.
```

**Sprint 54 Lane 分布** (Codex 3-lane 并行):
- Lane A: 4 service (4 file)
- Lane B: 5 service (5 file)
- Lane C: 5 service (5 file)
- 1 例 Stage 3 review 抓: `distribution.py` `channel_filter` NameError, 改 `_build_distribution_channel_filter` 返回三元组

### 4.3 L1 钩子: `check_sql_fstring_consistency.py`

> **Sprint 34.1 + Sprint 36-4**: SQL f-string 一致性 lint. 三引号 SQL body 含 `{var}` 必须 f 前缀.

**位置**: `backend/scripts/check_sql_fstring_consistency.py`

**触发**: pre-commit

**fixture test**: `backend/tests/test_check_sql_fstring_consistency.py` 4 case 跨范围验证 (Sprint 36-4 实战 "破坏 → 验证 → 恢复")

---

## 5. L4 永久规则汇总

> 全部进 `CLAUDE.md` L4.x, review skill 强制。

| 规则 | 内容 | Sprint | 验证 |
|---|---|---|---|
| **L4 (流程)** | SQL 三引号赋值若 body 含 `{var}` 必须 f 前缀 | Sprint 34.1 | L1 lint |
| **L4.2 (流程)** | 范围扩大 `backend/scripts/**` + `scripts/etl/**` | Sprint 36-4 | L1 lint |
| **L4.3 (流程)** | 真连 test 必须用 `monkeypatch_connection` fixture, 禁止直接 `duckdb.connect(production_path)` | Sprint 38→53 | Sprint 53 治本 |
| **L4.4 (流程)** | 真连 test 必须有 `pytestmark = pytest.mark.skipif(not _PROD_DUCKDB_AVAILABLE, ...)` | Sprint 39 | CI 7+ sprint 一直红闭环 |
| **L4.5 (流程)** | backend/services 函数必须用 `FilterBuilder` + `?` 参数化, 禁止 f-string 内嵌用户输入 | Sprint 54 | L3 ground-truth-lint |
| **L4.6 (流程)** | worktree 跑 pytest 必须设 `DUCKDB_PATH` 指向主仓 production db | Sprint 54 | Lane A Stage 3 review 抓 1 例 |

### 5.1 L4.3 — 真连 test fixture 强制

**反例** (Sprint 38 旧):
```python
def test_my_real_query():
    import duckdb
    conn = duckdb.connect("/path/to/production.duckdb")  # ❌ 抢 write lock
    # ... 跟 uvicorn 冲突, race flake
```

**正例** (Sprint 53 治本):
```python
def test_my_real_query(monkeypatch_connection):
    """真连 test — 必须用 monkeypatch_connection fixture."""
    from backend.services.my_service import get_my_data
    result = get_my_data(channel="直播")
    assert len(result) > 0
```

### 5.2 L4.4 — CI skipif 强制

**反例** (Sprint 32-38 CI 一直红):
```python
def test_my_real_query():
    # ❌ CI runner 没 production DuckDB → CatalogException → fail
    conn = duckdb.connect("/path/to/production.duckdb")
    ...
```

**正例** (Sprint 39 CI 闭环):
```python
import pytest
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE

pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用",
)


def test_my_real_query(monkeypatch_connection):
    # CI runner → skip, 本地开发 → 跑
    ...
```

### 5.3 L4.5 — FilterBuilder 强制

**反例** (Sprint 53.5 旧):
```python
def get_category_distribution(channel: str, category_id: str):
    valid_sql, _ = OrderFilters.valid_order()
    sql = f"""
    SELECT * FROM orders
    WHERE channel = '{channel}'              # ❌ f-string 内嵌用户输入
      AND category_id = '{category_id}'      # ❌ f-string 内嵌用户输入
      AND {valid_sql}
    """
    conn.execute(sql)
```

**正例** (Sprint 54 治本):
```python
def get_category_distribution(channel: str, category_id: str):
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    if channel and channel != "全店":
        fb.with_channels([channel])
    if category_id:
        fb.add_extra("category_id = ?", [category_id])
    where_sql, params = fb.build()
    conn.execute(f"SELECT * FROM orders WHERE {where_sql}", params)
```

### 5.4 L4.6 — worktree DUCKDB_PATH 强制

**症状** (Sprint 54 Lane A 抓):
```bash
$ git worktree add ../wt-sprint54-lane-a -b feature/sprint54-lane-a
$ cd ../wt-sprint54-lane-a
$ pytest
# ❌ Catalog Error: Table with name orders does not exist!
# (worktree 不带 data/processed/fuqing_crm.duckdb, .gitignore 排除)
```

**正例**:
```bash
$ export DUCKDB_PATH=/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb
$ pytest
# ✅ 749 passed / 1 skipped
```

**不推荐**: `git worktree add --checkout` 带数据 (数据大, 115GB 复制慢)

---

## 6. 测试金字塔

```
                    ┌──────────────────────┐
                    │  e2e (Playwright)    │  12 specs, ~24s fullyParallel
                    │  frontend-vue3/e2e/  │  Sprint 33.2 router smoke
                    └──────────┬───────────┘
                               │
                    ┌──────────┴───────────┐
                    │  pytest backend      │  749 passed / 1 skipped
                    │  真连 + 单测         │  Sprint 53 治本后 0 race flake
                    └──────────┬───────────┘
                               │
                    ┌──────────┴───────────┐
                    │  ground-truth-lint   │  L1 0 + L2 0 + L3 0 violations
                    │  pre-commit hook     │  9 件 lint
                    └──────────────────────┘
```

| 层 | 工具 | Sprint | 状态 |
|---|---|---|---|
| pre-commit hook | `.githooks/pre-commit` 9 件 | 持续 | 9/9 pass |
| L1 SQL f-string lint | `backend/scripts/check_sql_fstring_consistency.py` | Sprint 34.1 + 36-4 | 0 violations (101 files) |
| L1 frontend .vue sanity | grep `<template>/<script>` | Sprint 33 | OK |
| L2 AST spec-lint | `frontend-vue3/e2e/lint/spec-lint-l2.py` | Sprint 50+ | 5/5 pass |
| L3 FilterBuilder lint | `backend/scripts/check_filter_builder_usage.py` | Sprint 54 | 0 violations (70 files) |
| pytest | 749 + 1 skipped | Sprint 54 | green |
| e2e Playwright | 12 specs | Sprint 33.2 | 12/12 pass |
| GH Actions CI | 4 jobs | Sprint 41+ | 3/4 pass (e2e 治标) |

---

## 7. 故障排查

### 7.1 真连 test 偶发 fail

```bash
# 1. 检查 _PROD_DUCKDB_AVAILABLE
PYTHONPATH=. python3 -c "from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE; print(_PROD_DUCKDB_AVAILABLE)"

# 2. 检查 uvicorn 是否在跑
lsof -t /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb

# 3. 串行模式重跑
pytest -n 0
```

### 7.2 worktree 跑 pytest 报 Catalog Error

```bash
# 1. 验证 L4.6 DUCKDB_PATH
echo $DUCKDB_PATH

# 2. 设置
export DUCKDB_PATH=/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb

# 3. 重跑
pytest
```

### 7.3 L3 FilterBuilder lint 报 violation

```bash
# 1. 看具体 violation
python -m backend.scripts.check_filter_builder_usage --committed

# 2. 改 service 函数用 FilterBuilder.build()
# (反例 → 正例见 §5.3)

# 3. 跑相关 test 验证
pytest backend/tests/test_my_service.py -v
```

---

## 关联文档

- [STATUS.md](../../STATUS.md) — 项目总状态 (749 pass / 0 debt)
- [docs/architecture/AI_SAFETY_NET.md](AI_SAFETY_NET.md) — L1 lint + L2 AST + L3 FilterBuilder 3 层防线
- [docs/architecture/DATA_PIPELINE.md](DATA_PIPELINE.md) — ETL 4 阶段
- [docs/data-layout.md](../data-layout.md) — data/ 目录布局 (含 worktree DUCKDB_PATH 提示)
- [docs/TECH-DEBT.md](../TECH-DEBT.md) — 技术债台账 (29 条已修含 Sprint 53 race flake 治本)
- [docs/development/testing.md](../development/testing.md) — test 写法 (mock data, race flake 模式)
- [CLAUDE.md](../../CLAUDE.md) — L4.3/L4.4/L4.5/L4.6 永久规则完整版
- [backend/tests/conftest.py](../../backend/tests/conftest.py) — `isolated_duckdb` + `monkeypatch_connection` fixture 实现
- [backend/scripts/check_filter_builder_usage.py](../../backend/scripts/check_filter_builder_usage.py) — L3 ground-truth-lint
- [backend/scripts/check_sql_fstring_consistency.py](../../backend/scripts/check_sql_fstring_consistency.py) — L1 SQL f-string lint
