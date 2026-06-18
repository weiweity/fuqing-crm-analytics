# -*- coding: utf-8 -*-
"""
Sprint 34.1 debt #S34-1: backend/services/category_service/churn.py L418 fix regression test.

Root cause: L418 count_sql missed f-string prefix; DuckDB parsed literal "{valid_sql}"
and threw ParserException syntax error at or near "}".

Fix: L418 plain triple-quote changed to f-string (1 character).

Test strategy:
- Real DuckDB connection (Sprint 7 P2 single-connection lesson: simulate production
  new connection, not mock).
- Assert passes with fix, then temporarily revert to verify test FAILs
  (Sprint 24+ P3 single-connection lesson application).

Sprint 38 race flake 治标:
- DuckDB 文件锁 exclusive, pytest-xdist 多 worker 跑同一文件会跨进程 lock 冲突
  (Sprint 32.3/34.1/36-1/37 4 sprint 复发). 真治本留 Sprint 36.x+ (per-test tmp
  DuckDB ATTACH 模式, 1-2 天; Sprint 38 调研发现 DuckDB 文件锁 ATTACH 也冲突,
  ROI 重评为低).
- 治标: module-level skipif, 跟 test_api_integration.py:41-68 Sprint 36-5 模式一致.
- 真单跑验证: `pytest backend/tests/test_churn_user_list_fstring.py -v` 必 pass,
  串行模式 0 race flake. 失败模式 → 真 typo, 用 Sprint 24+ P3 single-connection
  lesson 故意破坏验证 test FAIL 再恢复验证 PASS.
"""
import os as _os

import pytest

from backend.services.category_service.churn import get_category_user_list


# Sprint 39 CI 爆红修复 + Sprint 38 race flake 治标 (三层防护):
# - Sprint 39 第 1 层: production DuckDB 不可用 → 整 module skip
#   (CI / fresh checkout 没 data/processed/fuqing_crm.duckdb, 真连空 DuckDB
#   → CatalogException fail)
# - Sprint 38 race flake 第 2 层: pytest-xdist 多 worker → 整 module skip
#   (worker 之间竞争同一文件锁)
# - 单跑 (`pytest ... -v -n0`) serial 模式: 0 skip, 真跑回归测试 (Sprint 34.1 价值保留)
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE  # noqa: E402

_UVICORN_LOCK_PID = (
    _os.environ.get("_FICTIONAL_UVICORN_PID_FOR_TEST")  # 留 hook for future test
)
_XDIST_WORKER_COUNT = _os.environ.get("PYTEST_XDIST_WORKER_COUNT")
_IN_XDIST_PARALLEL = _XDIST_WORKER_COUNT is not None and int(_XDIST_WORKER_COUNT) > 1
pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE
    or (_UVICORN_LOCK_PID is not None and _UVICORN_LOCK_PID != _os.getpid())
    or _IN_XDIST_PARALLEL,
    reason=(
        (
            "生产 DuckDB 不可用 (CI / fresh checkout / data/processed/ 缺文件). "
            "本地真跑: 先 ETL 跑批生成 data/processed/fuqing_crm.duckdb. "
        )
        if not _PROD_DUCKDB_AVAILABLE
        else ""
    )
    + (
        (
            f"生产 DuckDB lock 冲突: pytest-xdist 多 worker ({_XDIST_WORKER_COUNT}) 跑 race flake. "
            f"用 `pytest backend/tests/test_churn_user_list_fstring.py -n0` serial mode 跑 = 0 冲突. "
            f"真治本留 Sprint 36.x+ (per-test tmp DuckDB ATTACH 模式, Sprint 38 调研 ROI 低)."
        )
        if _IN_XDIST_PARALLEL
        else ""
    ),
)


class TestChurnUserListFString:
    """Sprint 34.1 regression test: churn.py L418 f-string fix."""

    def test_get_category_user_list_runs_without_parser_exception(self):
        """
        Real-connection run: route /category-detail/:id -> get_category_user_list
        -> L425 conn.execute(count_sql).

        With f-string fix: does NOT throw ParserException, returns total_users int.
        Without fix (plain triple-quote): throws _duckdb.ParserException.
        """
        result = get_category_user_list(
            category_id="B5_mask",
            start_date="2024-01-01",
            end_date="2024-01-31",
            limit=10,
        )

        # Assert: returns dict containing total_users int (fix passes)
        assert isinstance(result, dict)
        assert "total_users" in result
        assert isinstance(result["total_users"], int)
        assert result["total_users"] >= 0
        assert result["category_id"] == "B5_mask"

    def test_get_category_user_list_with_nonexistent_category(self):
        """
        Edge case: nonexistent category_id should return 0, not throw SQL error
        (Sprint 24+ P3 lesson: any parameterized input should gracefully return,
        not throw SQL error).
        """
        result = get_category_user_list(
            category_id="non_existent_category_XYZ",
            start_date="2024-01-01",
            end_date="2024-01-31",
            limit=10,
        )
        assert isinstance(result, dict)
        assert result["total_users"] == 0  # empty range returns 0


# Warning: Temporary break verification (Sprint 24+ P3 single-connection lesson)
#
# To verify the test really catches the typo:
#   1. sed -i.bak 's/count_sql = f"""/count_sql = """/' \
#        backend/services/category_service/churn.py
#   2. PYTHONPATH=. pytest backend/tests/test_churn_user_list_fstring.py -v
#      Expected: test 1 FAILS (ParserException: syntax error at or near "}")
#   3. mv backend/services/category_service/churn.py.bak \
#         backend/services/category_service/churn.py
#   4. PYTHONPATH=. pytest backend/tests/test_churn_user_list_fstring.py -v
#      Expected: test 1 PASSES (f-string restored)
#
# This break-verify-restore cycle is what mock unit tests can never catch (Sprint 7 P2).
