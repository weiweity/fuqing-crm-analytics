def test_tmp_duckdb_creates_orders_table(tmp_duckdb_with_synthetic_orders) -> None:
    tables = {
        row[0]
        for row in tmp_duckdb_with_synthetic_orders.execute("SHOW TABLES").fetchall()
    }

    assert {"orders", "user_first_purchase"}.issubset(tables)


def test_tmp_duckdb_inserts_synthetic_data(tmp_duckdb_with_synthetic_orders) -> None:
    order_count = tmp_duckdb_with_synthetic_orders.execute(
        "SELECT COUNT(*) FROM orders"
    ).fetchone()[0]
    user_count = tmp_duckdb_with_synthetic_orders.execute(
        "SELECT COUNT(*) FROM user_first_purchase"
    ).fetchone()[0]

    assert order_count >= 5
    assert user_count >= 5


def test_tmp_duckdb_isolated_per_worker(synthetic_duckdb_factory) -> None:
    first = synthetic_duckdb_factory()
    second = synthetic_duckdb_factory()

    first.execute("DELETE FROM orders WHERE order_id = 'o2026_sample'")
    first_count = first.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    second_count = second.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

    assert first.path != second.path
    assert first_count == second_count - 1


def test_tmp_duckdb_teardown_cleans_file(synthetic_duckdb_factory) -> None:
    handle = synthetic_duckdb_factory()
    db_path = handle.path

    assert db_path.exists()
    handle.cleanup()

    assert not db_path.exists()
