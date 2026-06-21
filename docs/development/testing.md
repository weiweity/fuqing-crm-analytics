# Testing 开发指南

> **本文档是 quick card (≤60 行), 完整 fixture 实现 + L4.3/L4.4/L4.5/L4.6 详见 `docs/architecture/TEST_INFRASTRUCTURE.md`**。

## 1. Fixture 模式 (Sprint 53 治本)

| Fixture | Scope | 用途 |
|---------|-------|------|
| `isolated_duckdb` | session | per-worker tmp DuckDB + ATTACH production READ_ONLY + `PRAGMA search_path='main,prod'` |
| `monkeypatch_connection` | function | 函数级 connection 隔离, 跑完自动 unpatch |
| `_PROD_DUCKDB_AVAILABLE` | module | 跨 3 个真连 test 共享的 skipif 判定常量, 见 conftest.py:_detect_prod_duckdb_available() |

**新增 fixture 见** `docs/architecture/TEST_INFRASTRUCTURE.md` §1。

**真连 fixture 范本**: `backend/tests/test_dmp_asset_cache.py` (Sprint 55.5 rename 后验证 `asset_focus_service/_helpers.py` cache invalidation, 4622 字节真实 test).

## 2. 真连 test skipif (L4.4)

```python
import pytest
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE

pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用 (CI runner / fresh checkout)"
)
```

## 3. L3 FilterBuilder 防御 (L4.5)

新加 service 函数必须用 `FilterBuilder.build()` + DuckDB `?` 参数化。详见:
- `docs/architecture/AI_SAFETY_NET.md` §3
- `docs/architecture/TEST_INFRASTRUCTURE.md` §4

## 4. E2E spec 写法 (L5.2)

- 不 `waitForTimeout(N)` 死等, 用 `expect.toBeVisible({ timeout: N })`
- 不 hardcode 业务数据长度 (`toBe(5)` 禁, 用 `length > 0` 替)
- 视口外元素先 `scrollIntoViewIfNeeded()`
- `page.request` 加 Authorization header (从 sessionStorage 拿 `fq_crm_auth_token`)
- 配合 `frontend-vue3/e2e/lint/spec-lint-l2.sh` pre-commit hook (L2 默认, L1 fallback)

详见 `docs/operating/ci-e2e-history.md` + `docs/architecture/TEST_INFRASTRUCTURE.md`。

## 5. 跑测试

```bash
# 全量
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q

# 跑特定 test
PYTHONPATH="$(pwd)" pytest backend/tests/test_X.py -v

# e2e
cd frontend-vue3 && npx playwright test
```

## 关联文档

- `docs/architecture/TEST_INFRASTRUCTURE.md` — fixture 模式详细
- `docs/architecture/AI_SAFETY_NET.md` — L1/L2/L3 防御
- `docs/operating/ci-e2e-history.md` — Sprint 41 实战 follow-up 12 修
- `CLAUDE.md` L4.3/L4.4/L4.5/L4.6 永久规则