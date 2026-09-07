"""Adversarial acceptance regressions; only small private synthetic databases."""
from __future__ import annotations

import hashlib

import duckdb
import pytest

from backend.services.analytics.warehouse.contract import WarehouseContractError
from backend.services.analytics.warehouse.generate import write_tabular_sources
from backend.services.analytics.warehouse.pipeline import run_warehouse_pipeline

ORDERS = [
    dict(synthetic_user_id="u", order_id=key, paid_at="2026-06-10T00:00:00+08:00",
         channel="A", status="PAID", gross_paid_minor=amount)
    for key, amount in (("a", 1000), ("b", 2000))
]
LINES = [
    dict(line_id="line-" + key, synthetic_user_id="u", order_id=key, product_id="sku", quantity=1)
    for key in ("a", "b")
]
VERSION = dict(product_id="sku", product_version_id="v1",
               valid_from="2026-01-01T00:00:00+08:00", valid_to="2027-01-01T00:00:00+08:00")
IDENTITY = [dict(identity_domain="domain-a", source_channel="A", source_user_id="source-u",
                 synthetic_user_id="u", permission_scope="brand_a")]


def source(root, name, **changes):
    path = root / name
    path.mkdir(mode=0o700)
    values = dict(orders=ORDERS, lines=LINES, refunds=[], product_versions=[VERSION], identities=IDENTITY)
    values.update(changes)
    return write_tabular_sources(path, **values)


def warehouse(root, **changes):
    s = source(root, "initial", **changes)
    wh = root / "warehouse"
    wh.mkdir(mode=0o700)
    return wh, run_warehouse_pipeline(s.directory, wh)


def read(run, sql):
    with duckdb.connect(run.database, read_only=True) as con:
        return con.execute(sql).fetchall()


def tables(run):
    with duckdb.connect(run.database, read_only=True) as con:
        names = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
        return {name: sorted(con.execute(f'SELECT * FROM "{name}"').fetchall(), key=repr) for name in names}


def test_rejected_increment_rolls_back_every_table_and_published_metadata(tmp_path):
    wh, run = warehouse(tmp_path)
    before = tables(run)
    published = (wh / "published.json").read_bytes()
    delta = source(tmp_path, "delta", orders=[{**ORDERS[0], "gross_paid_minor":1111}], lines=[],
                   product_versions=[{**VERSION, "product_version_id":"v2"}])
    with pytest.raises(WarehouseContractError, match="overlap"):
        run_warehouse_pipeline(delta.directory, wh, incremental=True)
    assert tables(run) == before  # fresh connection, including source/rules/meta/staging
    assert (wh / "published.json").read_bytes() == published


@pytest.mark.parametrize("change", [
    {"valid_to":"2026-05-01T00:00:00+08:00"},
    {"valid_from":"2026-07-01T00:00:00+08:00"},
    {"product_id":"other-sku"},
])
def test_product_version_correction_invalidates_old_matches(tmp_path, change):
    wh, run = warehouse(tmp_path)
    delta = source(tmp_path, "delta", orders=[], lines=[], product_versions=[{**VERSION, **change}])
    run_warehouse_pipeline(delta.directory, wh, incremental=True)
    assert read(run, "SELECT line_id, product_version_id FROM fact_order_line ORDER BY line_id") == [
        ("line-a", None), ("line-b", None),
    ]


@pytest.mark.parametrize("kind", ["refund", "line"])
def test_stable_child_id_moving_order_rebuilds_both_sides(tmp_path, kind):
    refund = dict(refund_id="r", synthetic_user_id="u", order_id="a",
                  refunded_at="2026-07-01T00:00:00+08:00", refund_minor=200)
    wh, run = warehouse(tmp_path, refunds=[refund])
    change = {"refunds":[{**refund, "order_id":"b"}]} if kind == "refund" else {
        "lines":[{**LINES[0], "order_id":"b"}],
    }
    values = dict(orders=[], lines=[], refunds=[], product_versions=[])
    values.update(change)
    delta = source(tmp_path, "delta", **values)
    run_warehouse_pipeline(delta.directory, wh, incremental=True)
    if kind == "refund":
        assert read(run, "SELECT order_id,net_paid_minor FROM fact_order_header ORDER BY order_id") == [
            ("a", 1000), ("b", 1800),
        ]
        assert read(run, "SELECT refund_id,order_id FROM fact_order_refund") == [("r", "b")]
    else:
        assert read(run, "SELECT line_id,order_id FROM fact_order_line ORDER BY line_id") == [
            ("line-a", "b"), ("line-b", "b"),
        ]


def test_old_schema_is_rejected_without_mutating_old_file(tmp_path):
    wh = tmp_path / "warehouse"
    wh.mkdir(mode=0o700)
    db = wh / "warehouse.duckdb"
    with duckdb.connect(str(db)) as con:
        con.execute("CREATE TABLE warehouse_meta (schema_version VARCHAR)")
        con.execute("INSERT INTO warehouse_meta VALUES ('analytics-warehouse-schema/v1')")
        con.execute("CREATE TABLE stg_identity (sentinel INTEGER)")
        con.execute("INSERT INTO stg_identity VALUES (7)")
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    delta = source(tmp_path, "source")
    with pytest.raises(WarehouseContractError, match="preserve old state.*separate empty directory"):
        run_warehouse_pipeline(delta.directory, wh, incremental=True)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


