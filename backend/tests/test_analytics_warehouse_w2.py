"""W2 warehouse facts and hand-calculated goldens. Production modules do not import this file."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from backend.services.analytics.warehouse.contract import (
    EMPTY_DENOMINATOR,
    PermissionScopeDenied,
    ratio_from_counts,
    utc_naive_instant,
)
from backend.services.analytics.warehouse.facts import (
    customer_key_for_source,
    read_fact_order_header,
    read_fact_order_line,
    read_first_purchases,
)
from backend.services.analytics.warehouse.generate import write_tabular_sources
from backend.services.analytics.warehouse.pipeline import run_warehouse_pipeline

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SNAPSHOT_PATH = FIXTURE_DIR / "warehouse_w2_snapshot.json"
EXPECTED_PATH = FIXTURE_DIR / "warehouse_w2_expected.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def private_dir(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)
    return path


def materialize_w2(tmp_path: Path):
    snapshot = load_json(SNAPSHOT_PATH)
    source = write_tabular_sources(
        private_dir(tmp_path, "src"),
        orders=snapshot["orders"],
        lines=snapshot["lines"],
        refunds=snapshot["refunds"],
        product_versions=snapshot["product_versions"],
        identities=snapshot["identities"],
        as_of=snapshot["as_of"],
        seed=None,
        source_kind="hand_fixture",
        generator_id="warehouse-w2-hand-snapshot",
    )
    run = run_warehouse_pipeline(source.directory, private_dir(tmp_path, "wh"))
    return run, load_json(EXPECTED_PATH)


def header_index(rows: list[dict]) -> dict[tuple[str, str], dict]:
    return {(row["synthetic_user_id"], row["order_id"]): row for row in rows}


def test_expected_fixture_is_hand_calculated_not_dumped():
    expected = load_json(EXPECTED_PATH)
    snapshot = load_json(SNAPSHOT_PATH)
    text = EXPECTED_PATH.read_text(encoding="utf-8")
    assert expected["method"] == "hand_calculated"
    assert expected["computation"] == "NOT_RUN"
    assert expected["not_generated_from_sql"] is True
    assert "dump" not in text.lower()
    assert expected["fixture_id"] == snapshot["fixture_id"]
    assert expected["fixture_id"] != "synthetic-channel-followup-v1"
    assert expected["aggregates_brand_a"]["valid_header_net_sum_minor"] == 54000
    assert expected["aggregates_brand_a"]["valid_header_gross_sum_minor"] == 58000
    assert expected["notes"]["valid_brand_a_net"] == "15000+7000+4000+8000+8000+2000+4000+6000=54000"


def test_empty_denominator_is_null_not_zero():
    ratio, reason = ratio_from_counts(0, 0)
    assert ratio is None
    assert reason == EMPTY_DENOMINATOR
    ratio, reason = ratio_from_counts(4, 0)
    assert ratio is None
    assert reason == EMPTY_DENOMINATOR
    ratio, reason = ratio_from_counts(1, 2)
    assert ratio == 0.5
    assert reason is None


def test_w2_hand_goldens_headers_and_valid_orders(tmp_path):
    run, expected = materialize_w2(tmp_path)
    connection = run.connect_readonly(private_dir(tmp_path, "tmp"))
    try:
        headers = read_fact_order_header(connection, permission_scope="brand_a")
        lines = read_fact_order_line(connection, permission_scope="brand_a")
        firsts = read_first_purchases(connection, permission_scope="brand_a")
        brand_b = read_fact_order_header(connection, permission_scope="brand_b")
        customers = connection.execute(
            """
            SELECT synthetic_user_id, identity_domain, permission_scope, customer_key
            FROM dim_customer
            ORDER BY customer_key
            """
        ).fetchall()
    finally:
        connection.close()

    assert [(row[0], row[1], row[2], int(row[3])) for row in customers] == [
        (item["synthetic_user_id"], item["identity_domain"], item["permission_scope"], item["customer_key"])
        for item in expected["customer_keys"]
    ]
    actual = header_index(headers)
    assert len(headers) == expected["aggregates_brand_a"]["header_count"]
    for item in expected["headers"]:
        row = actual[(item["synthetic_user_id"], item["order_id"])]
        assert type(row["synthetic_user_id"]) is str
        assert type(row["order_id"]) is str
        assert type(row["gross_paid_minor"]) is int
        assert type(row["net_paid_minor"]) is int
        assert type(row["customer_key"]) is int
        for key in (
            "customer_key",
            "channel",
            "status",
            "gross_paid_minor",
            "refund_minor_as_of",
            "net_paid_minor",
            "is_valid",
        ):
            assert row[key] == item[key], (item["order_id"], key, row[key], item[key])
        assert row["paid_at"] == utc_naive_instant(
            next(
                order["paid_at"]
                for order in load_json(SNAPSHOT_PATH)["orders"]
                if order["order_id"] == item["order_id"] and order["synthetic_user_id"] == item["synthetic_user_id"]
            )
        )
    assert len(brand_b) == 1
    other = brand_b[0]
    expected_b = expected["brand_b_headers"][0]
    assert other["synthetic_user_id"] == expected_b["synthetic_user_id"]
    assert other["net_paid_minor"] == expected_b["net_paid_minor"]
    assert other["customer_key"] == expected_b["customer_key"]

    valid = [row for row in headers if row["is_valid"]]
    assert len(valid) == expected["aggregates_brand_a"]["valid_header_count"]
    assert sum(row["gross_paid_minor"] for row in valid) == expected["aggregates_brand_a"]["valid_header_gross_sum_minor"]
    assert sum(row["net_paid_minor"] for row in valid) == expected["aggregates_brand_a"]["valid_header_net_sum_minor"]
    assert len(lines) == expected["aggregates_brand_a"]["line_count"]

    first_index = {row["synthetic_user_id"]: row for row in firsts}
    assert len(firsts) == len(expected["first_purchases_brand_a"])
    for item in expected["first_purchases_brand_a"]:
        row = first_index[item["synthetic_user_id"]]
        assert row["order_id"] == item["order_id"]
        assert row["channel"] == item["channel"]
        assert row["customer_key"] == item["customer_key"]
        assert row["header_gross_paid_minor"] == item["header_gross_paid_minor"]
        assert row["header_net_paid_minor"] == item["header_net_paid_minor"]
        assert row["product_ids"] == item["product_ids"]


def test_first_purchase_multiproduct_does_not_repeat_header_amount(tmp_path):
    run, expected = materialize_w2(tmp_path)
    connection = run.connect_readonly(private_dir(tmp_path, "tmp"))
    try:
        headers = header_index(read_fact_order_header(connection, permission_scope="brand_a"))
        lines = read_fact_order_line(connection, permission_scope="brand_a")
        firsts = {row["synthetic_user_id"]: row for row in read_first_purchases(connection, permission_scope="brand_a")}
    finally:
        connection.close()
    basket = headers[("0009007199254740993", "basket-1")]
    basket_lines = [row for row in lines if row["order_id"] == "basket-1"]
    assert len(basket_lines) == expected["aggregates_brand_a"]["basket_line_count"]
    assert basket["gross_paid_minor"] == expected["aggregates_brand_a"]["basket_header_gross_paid_minor"]
    assert basket["gross_paid_minor"] != basket["gross_paid_minor"] * len(basket_lines)
    first = firsts["0009007199254740993"]
    assert first["order_id"] == "basket-1"
    assert first["product_ids"] == ["sku_full", "sku_sample"]
    assert first["header_gross_paid_minor"] == 15000


def test_same_instant_orders_stay_separate_and_sort_by_order_id(tmp_path):
    run, expected = materialize_w2(tmp_path)
    connection = run.connect_readonly(private_dir(tmp_path, "tmp"))
    try:
        headers = header_index(read_fact_order_header(connection, permission_scope="brand_a"))
        firsts = {row["synthetic_user_id"]: row for row in read_first_purchases(connection, permission_scope="brand_a")}
    finally:
        connection.close()
    same_a = headers[("user_same_ts", "same-a")]
    same_b = headers[("user_same_ts", "same-b")]
    assert same_a["paid_at"] == same_b["paid_at"]
    assert same_a["gross_paid_minor"] == 8000
    assert same_b["gross_paid_minor"] == 2000
    assert firsts["user_same_ts"]["order_id"] == "same-a"
    assert firsts["user_same_ts"]["channel"] == "A"
    assert firsts["user_same_ts"]["header_net_paid_minor"] == 8000


def test_partial_refund_net_and_as_of_cutoff(tmp_path):
    run, _expected = materialize_w2(tmp_path)
    connection = run.connect_readonly(private_dir(tmp_path, "tmp"))
    try:
        headers = header_index(read_fact_order_header(connection, permission_scope="brand_a"))
    finally:
        connection.close()
    assert headers[("0009007199254740993", "partial-1")]["net_paid_minor"] == 7000
    assert headers[("0009007199254740993", "partial-1")]["is_valid"] is True
    assert headers[("0009007199254740993", "asof-refund-1")]["refund_minor_as_of"] == 1000
    assert headers[("0009007199254740993", "asof-refund-1")]["net_paid_minor"] == 4000
    assert headers[("0009007199254740993", "future-refund-1")]["refund_minor_as_of"] == 0
    assert headers[("0009007199254740993", "future-refund-1")]["net_paid_minor"] == 8000
    assert headers[("0009007199254740993", "future-refund-1")]["is_valid"] is True
    assert headers[("user_same_ts", "full-refund-1")]["net_paid_minor"] == 0
    assert headers[("user_same_ts", "full-refund-1")]["is_valid"] is False
    assert headers[("user_same_ts", "cancelled-1")]["is_valid"] is False


def test_two_users_may_share_order_id_string(tmp_path):
    run, expected = materialize_w2(tmp_path)
    connection = run.connect_readonly(private_dir(tmp_path, "tmp"))
    try:
        headers = read_fact_order_header(connection, permission_scope="brand_a")
    finally:
        connection.close()
    shared = [row for row in headers if row["order_id"] == "shared-oid"]
    assert len(shared) == expected["aggregates_brand_a"]["shared_order_id_header_count"]
    by_user = {row["synthetic_user_id"]: row for row in shared}
    assert by_user["user_dup_a"]["net_paid_minor"] == 4000
    assert by_user["user_dup_b"]["net_paid_minor"] == 6000
    assert by_user["user_dup_a"]["customer_key"] != by_user["user_dup_b"]["customer_key"]


def test_long_user_id_stays_str_and_customer_key_is_stable_int(tmp_path):
    run, expected = materialize_w2(tmp_path)
    long_id = expected["aggregates_brand_a"]["long_user_id"]
    connection = run.connect_readonly(private_dir(tmp_path, "tmp"))
    try:
        headers = read_fact_order_header(
            connection,
            permission_scope="brand_a",
            synthetic_user_ids=[long_id],
        )
        key = customer_key_for_source(
            connection,
            identity_domain="group-1",
            source_channel="taobao",
            source_user_id="tb-0009007199254740993",
            permission_scope="brand_a",
        )
        other = customer_key_for_source(
            connection,
            identity_domain="group-1",
            source_channel="jd",
            source_user_id="jd-0009007199254740993",
            permission_scope="brand_a",
        )
    finally:
        connection.close()
    assert type(long_id) is str
    assert long_id == "0009007199254740993"
    assert all(type(row["synthetic_user_id"]) is str for row in headers)
    assert all(row["synthetic_user_id"] == long_id for row in headers)
    assert type(key) is int
    assert key == 1
    assert other == key


def test_cross_permission_scope_is_rejected(tmp_path):
    run, expected = materialize_w2(tmp_path)
    connection = run.connect_readonly(private_dir(tmp_path, "tmp"))
    try:
        with pytest.raises(PermissionScopeDenied):
            read_fact_order_header(
                connection,
                permission_scope=expected["permission"]["cross_scope_request"]["permission_scope"],
                synthetic_user_ids=expected["permission"]["cross_scope_request"]["synthetic_user_ids"],
            )
        with pytest.raises(PermissionScopeDenied):
            customer_key_for_source(
                connection,
                identity_domain="group-2",
                source_channel="taobao",
                source_user_id="tb-user_scope_b",
                permission_scope="brand_a",
            )
        brand_a = read_fact_order_header(connection, permission_scope="brand_a")
    finally:
        connection.close()
    assert {row["synthetic_user_id"] for row in brand_a} == set(expected["permission"]["brand_a_user_ids"])
    assert "user_scope_b" not in {row["synthetic_user_id"] for row in brand_a}
