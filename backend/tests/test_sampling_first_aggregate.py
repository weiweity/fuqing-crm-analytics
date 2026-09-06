"""Check the actual service SQL using synthetic orders, never the archived DB."""
from __future__ import annotations

import ast
from pathlib import Path

import duckdb
import pytest

from backend.semantic.channels import GIFT_SAMPLE_DB
from scripts.diagnostics.benchmark_sampling_first import legacy_query


def sample_users_query(field="spu_category"):
    source = Path(__file__).parents[1] / "services" / "sampling_service.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "get_sampling_roi")
    nodes = [
        node.value for node in ast.walk(function)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "sample_users_sql" for t in node.targets)
    ]
    assert len(nodes) == 1
    # Compile only this known SQL literal, not module imports or application startup.
    return eval(compile(ast.Expression(nodes[0]), str(source), "eval"),
                {"__builtins__": {}},
                {"cat_field": field, "GIFT_SAMPLE_DB": GIFT_SAMPLE_DB,
                 "ch_placeholders": "?,?"})


@pytest.fixture
def orders():
    conn = duckdb.connect(":memory:", config={
        "memory_limit": "128MB", "threads": 1, "temp_directory": "",
    })
    conn.execute("""CREATE TABLE orders (
        order_id VARCHAR, sub_order_id VARCHAR, user_id VARCHAR, channel VARCHAR,
        pay_time TIMESTAMP, sample_received_at TIMESTAMP,
        spu_category VARCHAR, spu_tier VARCHAR
    )""")
    conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
        ("late", None, "a" * 128, "U先派样", "2025-06-10", None, "乳液", "次线"),
        ("early", "gift", "a" * 128, "U先派样", "2025-06-01", None, "面膜", "核心"),
        ("gift", None, "a" * 128, GIFT_SAMPLE_DB, "2025-06-01", "2025-06-03", "礼品", "赠品"),
        ("other-channel", None, "a" * 128, "百补派样", "2025-06-02", None, "精华", "新品"),
        ("null-category", None, "b" * 128, "U先派样", "2025-06-01", None, None, None),
        ("later-category", None, "b" * 128, "U先派样", "2025-06-02", None, "精华", "新品"),
        ("empty-string", None, "c" * 128, "U先派样", "2025-06-02", None, "", ""),
        ("no-date", None, "d" * 128, "U先派样", None, None, "面膜", "核心"),
        ("out-of-range", None, "e" * 128, "U先派样", "2025-05-01", None, "面膜", "核心"),
    ])
    try:
        yield conn
    finally:
        conn.close()


def test_service_uses_scalar_first_not_materialized_arrays():
    query = sample_users_query()
    assert "array_agg" not in query.lower()
    assert query.lower().count("first(") == 2


@pytest.mark.parametrize("field", ["spu_category", "spu_tier"])
def test_first_sample_matches_legacy_and_golden(orders, field):
    query = sample_users_query(field)
    legacy = query.replace(
        "FIRST(COALESCE(o.spu_category, '未知') ORDER BY o.pay_time ASC)",
        "(ARRAY_AGG(COALESCE(o.spu_category, '未知') ORDER BY o.pay_time ASC))[1]",
    ).replace(
        f"FIRST(COALESCE(o.{field}, '未知') ORDER BY o.pay_time ASC)",
        f"(ARRAY_AGG(COALESCE(o.{field}, '未知') ORDER BY o.pay_time ASC))[1]",
    )
    params = ["U先派样", "百补派样", "2025-06-01", "2025-06-30"]
    actual = sorted(orders.execute(query, params).fetchall())
    assert actual == sorted(orders.execute(legacy, params).fetchall())
    by_group = {(row[0][0], row[1]): row for row in actual}
    assert len(actual) == 4
    assert by_group[("a", "U先派样")][4:] == ("面膜", "面膜" if field == "spu_category" else "核心")
    assert str(by_group[("a", "U先派样")][3]) == "2025-06-03 00:00:00"
    assert by_group[("a", "百补派样")][4] == "精华"
    assert by_group[("b", "U先派样")][4:] == ("未知", "未知")
    assert by_group[("c", "U先派样")][4:] == ("", "")


def test_empty_window_stays_empty(orders):
    assert orders.execute(sample_users_query(), [
        "U先派样", "百补派样", "2024-01-01", "2024-01-31",
    ]).fetchall() == []


@pytest.mark.parametrize("level", ["spu_category", "spu_tier"])
@pytest.mark.parametrize("compare_range", [None, ("2025-05-01", "2025-05-31")])
def test_complete_roi_response_matches_legacy(orders, monkeypatch, level, compare_range):
    from backend.services import sampling_service

    orders.execute("ALTER TABLE orders ADD COLUMN actual_amount DOUBLE DEFAULT 1")
    orders.execute("ALTER TABLE orders ADD COLUMN spu_type VARCHAR DEFAULT '小样'")
    orders.execute("ALTER TABLE orders ADD COLUMN is_refund BOOLEAN DEFAULT FALSE")
    orders.execute("ALTER TABLE orders ADD COLUMN order_status VARCHAR DEFAULT '交易成功'")
    # Previous-month/year baselines exercise both comparison modes, not just no-data paths.
    orders.execute("""INSERT INTO orders
        SELECT order_id || '-month', NULL, user_id || '-month', channel,
               pay_time - INTERVAL '1 month', sample_received_at - INTERVAL '1 month',
               spu_category, spu_tier, actual_amount, spu_type, is_refund, order_status
        FROM orders""")
    orders.execute("""INSERT INTO orders
        SELECT order_id || '-year', NULL, user_id || '-year', channel,
               pay_time - INTERVAL '1 year', sample_received_at - INTERVAL '1 year',
               spu_category, spu_tier, actual_amount, spu_type, is_refund, order_status
        FROM orders WHERE pay_time >= TIMESTAMP '2025-06-01'""")
    monkeypatch.setattr(sampling_service, "get_connection", lambda: orders)
    kwargs = {"level": level, "compare_date_range": compare_range}
    actual = sampling_service.get_sampling_roi("2025-06-01", "2025-06-30", **kwargs)

    class LegacyConnection:
        def execute(self, sql, params=None):
            return orders.execute(legacy_query(sql), params)

    monkeypatch.setattr(sampling_service, "get_connection", LegacyConnection)
    expected = sampling_service.get_sampling_roi("2025-06-01", "2025-06-30", **kwargs)
    assert actual == expected
    assert len(actual["category_breakdown"]) == 4
    assert actual["summary"]["channels"][0]["sample_users"] == 3


def test_equal_time_ties_do_not_invent_a_new_attribution_rule(orders):
    orders.execute("""INSERT INTO orders VALUES
        ('tie-a', NULL, 'tie-user', 'U先派样', '2025-06-01', NULL, '面膜', '核心'),
        ('tie-b', NULL, 'tie-user', 'U先派样', '2025-06-01', NULL, '精华', '新品')
    """)
    params = ["U先派样", "百补派样", "2025-06-01", "2025-06-30"]
    # Existing SQL has no secondary tie-break. Either earliest item is allowed;
    # deterministic cross-line attribution is a separate business decision.
    for query in (sample_users_query(), legacy_query(sample_users_query())):
        row = next(row for row in orders.execute(query, params).fetchall() if row[0] == "tie-user")
        assert row[4] in {"面膜", "精华"}


@pytest.mark.parametrize("rows", ["0", "-1", "1000001"])
def test_benchmark_refuses_unbounded_scale(monkeypatch, rows):
    from scripts.diagnostics import benchmark_sampling_first as probe

    monkeypatch.setattr(probe.sys, "argv", ["probe", "--rows", rows])
    with pytest.raises(SystemExit) as stopped:
        probe.main()
    assert stopped.value.code == 2
