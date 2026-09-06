from pathlib import Path

import duckdb

from backend.tests.conftest import _detect_prod_duckdb_available


def test_empty_duckdb_is_not_treated_as_production(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "empty.duckdb"
    duckdb.connect(str(db_path)).close()

    assert _detect_prod_duckdb_available(db_path) is False


def test_duckdb_with_orders_table_is_available(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "ready.duckdb"
    with duckdb.connect(str(db_path)) as connection:
        connection.execute("CREATE TABLE orders (order_id VARCHAR)")

    assert _detect_prod_duckdb_available(db_path) is True
