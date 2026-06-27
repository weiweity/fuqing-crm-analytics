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

Sprint 53 race flake 治本:
- 每个 pytest-xdist worker 使用 temp DuckDB + ATTACH production read_only.
- 真连接回归测试可在 serial / parallel 模式执行，不再因文件锁跳过.
"""
import pytest

from backend.services.category_service.churn import get_category_user_list


# CI / fresh checkout 没 production DuckDB 时仍跳过；本地 xdist 并行真跑。
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE  # noqa: E402

pytestmark = [
    pytest.mark.skipif(
        not _PROD_DUCKDB_AVAILABLE,
        reason="生产 DuckDB 不可用 (CI / fresh checkout / data/processed/ 缺文件)",
    ),
]


@pytest.fixture(autouse=True)
def _use_isolated_db(monkeypatch_connection):
    """所有 churn 回归测试使用当前 worker 的隔离 DuckDB。"""


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
