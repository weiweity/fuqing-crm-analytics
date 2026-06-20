# HANDOFF-TO-CODEX: Sprint 53 — race flake 真治本

> **Claude Stage 1 产出** — Codex Stage 2 实施
> **目标**: 消除 DuckDB race flake 根因，让 3 个真连 test 在 pytest-xdist `-n auto` 下不再 skip
> **估时**: 2-4 小时 (Codex 实施)
> **难度**: ⭐⭐⭐⭐⭐

---

## 1. 问题根因

```
get_connection() 进程内单例 → 连生产 DuckDB 文件
        ↓
pytest-xdist 多 worker → 每个 worker 独立进程 → 各自创建单例
        ↓
多个进程同时打开同一个 .duckdb 文件 → DuckDB exclusive 文件锁冲突
        ↓
IOError: Could not set lock → test flake
```

**当前治标** (Sprint 38): `_IN_XDIST_PARALLEL` skipif — xdist 多 worker 时 skip 整个文件。
**问题**: 这些 test 在 CI 中永远被 skip，等于没有回归保护。

---

## 2. 治本方案: per-worker tmp DuckDB + ATTACH read_only

**核心思路** (已验证可行):

```
Worker 1: tmp_1.duckdb ──ATTACH──→ production.duckdb (READ_ONLY)
Worker 2: tmp_2.duckdb ──ATTACH──→ production.duckdb (READ_ONLY)
Worker 3: tmp_3.duckdb ──ATTACH──→ production.duckdb (READ_ONLY)

每个 worker 独立 temp DuckDB, 共享只读 production 数据
PRAGMA search_path='main,prod' → 无前缀访问 production 表
写操作自动落到 temp db (main schema)
```

**验证结果** (Claude 已跑通):
- ✅ ATTACH read_only 支持 4 个并发 worker
- ✅ `PRAGMA search_path='main,prod'` 让无前缀查询找到 production 表
- ✅ 写操作自动隔离到 temp db (main schema 优先)
- ✅ 兼容 `connection.py` 的 config (`memory_limit`)
- ✅ 3 个 test 文件全部是只读操作，不写 production

---

## 3. 实施步骤

### Step 1: 在 conftest.py 新增 `isolated_duckdb` fixture

文件: `backend/tests/conftest.py`

新增 fixture (session scope 或 function scope, 推荐 session scope 因为每个 xdist worker 是独立进程):

```python
import tempfile
import duckdb
from pathlib import Path

@pytest.fixture(scope="session")
def isolated_duckdb():
    """per-worker 隔离 DuckDB: temp db + ATTACH production read_only.

    每个 pytest-xdist worker 是独立进程, 各自创建自己的 temp DuckDB,
    ATTACH 生产库为 read_only. 多个 worker 可以并发读 production,
    写操作自动落到 temp db, 不触发文件锁冲突.

    PRAGMA search_path='main,prod' 让 service 代码无前缀访问 production 表.
    """
    if not _PROD_DUCKDB_AVAILABLE:
        pytest.skip("production DuckDB not available")

    prod_path = str(DUCKDB_PATH)
    tmp = tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        cfg = {"memory_limit": DUCKDB_MEMORY_LIMIT}
        conn = duckdb.connect(tmp_path, config=cfg)
        conn.execute(f"ATTACH '{prod_path}' AS prod (READ_ONLY)")
        conn.execute("PRAGMA search_path='main,prod'")

        yield conn

        conn.close()
    finally:
        Path(tmp_path).unlink(missing_ok=True)
```

### Step 2: 新增 `monkeypatch_connection` fixture

让 `backend.db.connection.get_connection()` 返回隔离连接:

```python
@pytest.fixture(scope="session")
def monkeypatch_connection(isolated_duckdb, monkeypatch_session):
    """monkeypatch get_connection() 返回隔离连接."""
    from backend.db import connection

    class FakeThreadSafeConnection:
        """模拟 ThreadSafeConnection, 直接代理到隔离连接."""
        def __init__(self, conn):
            self._conn = conn

        def execute(self, query, parameters=None):
            if parameters:
                return self._conn.execute(query, parameters)
            return self._conn.execute(query)

        def close(self):
            pass  # 不关闭, session 生命周期管理

    def _fake_get_connection():
        return FakeThreadSafeConnection(isolated_duckdb)

    monkeypatch_session.setattr(connection, "get_connection", _fake_get_connection)
    # 也要重置 _conn 为 None, 避免 get_connection 走旧单例
    monkeypatch_session.setattr(connection, "_conn", None)

    return isolated_duckdb
```

**注意**: `monkeypatch_session` 不是 pytest 内置的 (monkeypatch 默认 function scope).
替代方案: 直接用 `unittest.mock.patch` 或在 fixture 中手动 patch + teardown.

推荐实现:

```python
@pytest.fixture(scope="session")
def monkeypatch_connection(isolated_duckdb):
    """monkeypatch get_connection() 返回隔离连接."""
    from backend.db import connection
    from unittest.mock import patch

    class FakeThreadSafeConnection:
        def __init__(self, conn):
            self._conn = conn
        def execute(self, query, parameters=None):
            if parameters:
                return self._conn.execute(query, parameters)
            return self._conn.execute(query)
        def close(self):
            pass

    original_conn = connection._conn
    original_get = connection.get_connection

    def _fake_get_connection():
        return FakeThreadSafeConnection(isolated_duckdb)

    connection._conn = None
    connection.get_connection = _fake_get_connection

    yield isolated_duckdb

    connection._conn = original_conn
    connection.get_connection = original_get
```

### Step 3: 更新 test_api_integration.py

文件: `backend/tests/test_api_integration.py`

改动:
1. 删除 `_IN_XDIST_PARALLEL` skipif (行 55-85 中的相关部分)
2. 保留 `_PROD_DUCKDB_AVAILABLE` skipif (CI 没生产库仍需 skip)
3. 添加 `monkeypatch_connection` fixture 到 test class 或 module
4. 确保 `TestClient(app)` 使用 monkeypatched 连接

关键: `TestClient(app)` import 时 `backend.main` 已加载, `get_connection()` 在第一次请求时才调用.
所以 monkeypatch 在 fixture 中生效即可.

```python
# 删除:
_XDIST_WORKER_COUNT = _os.environ.get("PYTEST_XDIST_WORKER_COUNT")
_IN_XDIST_PARALLEL = _XDIST_WORKER_COUNT is not None and int(_XDIST_WORKER_COUNT) > 1

# 修改 pytestmark:
pytestmark = [
    pytest.mark.skipif(not _PROD_DUCKDB_AVAILABLE, reason="production DuckDB 不可用"),
    pytest.mark.integration,
]

# 添加 fixture 引用:
@pytest.fixture(autouse=True)
def _use_isolated_db(self, monkeypatch_connection):
    """每个 test 自动使用隔离 DuckDB."""
    pass
```

### Step 4: 更新 test_churn_user_list_fstring.py

文件: `backend/tests/test_churn_user_list_fstring.py`

改动:
1. 删除 `_IN_XDIST_PARALLEL` skipif
2. 保留 `_PROD_DUCKDB_AVAILABLE` skipif
3. 添加 `monkeypatch_connection` fixture

```python
# 删除:
_XDIST_WORKER_COUNT = _os.environ.get("PYTEST_XDIST_WORKER_COUNT")
_IN_XDIST_PARALLEL = _XDIST_WORKER_COUNT is not None and int(_XDIST_WORKER_COUNT) > 1

# 修改 pytestmark:
pytestmark = [
    pytest.mark.skipif(not _PROD_DUCKDB_AVAILABLE, reason="production DuckDB 不可用"),
    pytest.mark.integration,
]
```

### Step 5: 更新 test_w4_t7_integration.py

文件: `backend/tests/test_w4_t7_integration.py`

这个最复杂 — 它自己 `duckdb.connect()` 创建连接, 不走 `get_connection()`.

改动:
1. 删除 `_IN_XDIST_PARALLEL` skipif
2. 删除 `_open_production_duckdb()` helper 函数 (行 84-142)
3. 改 `prod_conn` fixture 使用 `isolated_duckdb`
4. 删除 `_PROD_DUCKDB_AVAILABLE` skipif (fixture 自带 skip)

```python
# 删除 _open_production_duckdb() 和相关辅助函数

# 改 prod_conn fixture:
@pytest.fixture(scope="module")
def prod_conn(isolated_duckdb):
    """使用隔离 DuckDB 连接 (ATTACH production read_only)."""
    return isolated_duckdb
```

**注意**: test_w4_t7_integration 的 test 会写入 DuckDB (创建临时表). search_path 机制确保写入到 temp db, 读取走 production. 需要验证 test 的写操作不破坏 production 数据.

### Step 6: 清理 conftest.py

1. 移动 `_IN_XDIST_PARALLEL` 定义到 conftest.py (如果还有其他文件用)
2. 确认 `_PROD_DUCKDB_AVAILABLE` 保持不变
3. 更新 `skip_if_duckdb_locked` fixture — 有了 `isolated_duckdb` 后, 这个 fixture 只用于 subprocess test

---

## 4. 需要特别注意的坑

### 4.1 TestClient 和 app 生命周期

`test_api_integration.py` 的 `TestClient(app)` 在 module 加载时 import `backend.main`, app 的 lifespan startup 会调 `get_connection()`. 如果 `monkeypatch_connection` fixture 是 session scope, 需要在 TestClient 创建之前就 patch 好.

**解法**: 用 module-level fixture 或在 conftest.py 中用 `autouse=True` session fixture.

### 4.2 search_path 与 CREATE TABLE 冲突

如果 service 代码有 `CREATE TABLE IF NOT EXISTS rfm_query_cache (...)`, 在 search_path 下会在 main (temp db) 创建. 如果 production 已有同名表, 两个表共存 — main 优先 (因为 search_path 顺序). 这是**期望行为**: cache 写到 temp, 不污染 production.

但如果有 `DROP TABLE rfm_query_cache`, 只会 drop temp db 中的, production 不受影响 (READ_ONLY 保护).

### 4.3 ATTACH 的 production 文件路径

`DUCKDB_PATH` 从 `backend.config` import, 路径是 `data/processed/fuqing_crm.duckdb`.
如果 CI 没有 production 文件, `_PROD_DUCKDB_AVAILABLE` 会 False, 整个 fixture skip.
这跟当前行为一致, 不需要改.

### 4.4 memory_limit 双重设置

`duckdb.connect(tmp_path, config={"memory_limit": ...})` 设的是 temp db 的内存限制.
ATTACH 的 production db 是 read_only, 不受 memory_limit 影响 (它不缓存, 直接读文件).
不需要额外处理.

### 4.5 session scope vs function scope

- **session scope**: 每个 xdist worker 进程创建一次 temp db, 所有 test 共享. 性能好, 但 test 之间可能有状态残留 (CREATE TABLE, INSERT 等).
- **function scope**: 每个 test 创建独立 temp db. 隔离好, 但 ATTACH 开销重复.
- **推荐**: session scope + 每个 test 开一个 transaction + rollback. 或者接受 test 之间的状态残留 (当前 test 已经是 read-only 模式, 不写 production).

---

## 5. 验证标准

### 5.1 必须通过

```bash
# 1. serial mode (当前行为不变)
pytest backend/tests/test_api_integration.py backend/tests/test_churn_user_list_fstring.py backend/tests/test_w4_t7_integration.py -n0 -v

# 2. parallel mode (核心验证: 不再 skip, 不再 flake)
pytest backend/tests/test_api_integration.py backend/tests/test_churn_user_list_fstring.py backend/tests/test_w4_t7_integration.py -n4 -v

# 3. 全量 test 不回归
pytest backend/tests/ -x -q
```

### 5.2 期望结果

- serial mode: 全 PASS (跟当前行为一致)
- parallel mode: 不再 skip, 全 PASS, 无 flake
- 全量: 无回归

### 5.3 性能基准

- serial mode 耗时不应显著增加 (< 5%)
- parallel mode 耗时应比 serial 快 (多 worker 并发)

---

## 6. 关联文件

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `backend/tests/conftest.py` | 新增 fixture | `isolated_duckdb` + `monkeypatch_connection` |
| `backend/tests/test_api_integration.py` | 修改 | 删 skipif, 加 fixture |
| `backend/tests/test_churn_user_list_fstring.py` | 修改 | 删 skipif, 加 fixture |
| `backend/tests/test_w4_t7_integration.py` | 修改 | 删 `_open_production_duckdb`, 用 fixture |
| `backend/db/connection.py` | 不改 | 只 monkeypatch, 不改源码 |
| `CLAUDE.md` L4.3 | 更新 | 删 "必须有 skipif" 规则 |

---

## 7. 不在 scope 内

- 不改 `backend/db/connection.py` 源码
- 不改 `test_w4_full.py` (它用 subprocess, 不在本次 scope)
- 不改 CI 配置 (advisory → blocking 留后续)
- 不处理 DUCKDB_PASSWORD (当前生产不用密码)

---

## 8. Claude 已验证的技术细节

```python
# ATTACH read_only + search_path 完整 POC:
tmp = tempfile.mktemp(suffix='.duckdb')
conn = duckdb.connect(tmp, config={"memory_limit": "256MB"})
conn.execute(f"ATTACH '{prod_path}' AS prod (READ_ONLY)")
conn.execute("PRAGMA search_path='main,prod'")
# SELECT * FROM orders → 找到 prod.orders (无前缀)
# CREATE TABLE cache (...) → 写到 main (temp db)
# INSERT INTO cache ... → 写到 main (temp db)
# 4 个 worker 并发 → 0 锁冲突
```
