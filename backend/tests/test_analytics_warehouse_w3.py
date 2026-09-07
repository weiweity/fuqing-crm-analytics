"""W3 true-incremental warehouse. Production modules do not import this file."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from backend.services.analytics.warehouse.contract import PermissionScopeDenied, utc_naive_instant
from backend.services.analytics.warehouse.facts import read_fact_order_header, read_first_purchases
from backend.services.analytics.warehouse.generate import write_tabular_sources
from backend.services.analytics.warehouse.pipeline import run_warehouse_pipeline

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
EXPECTED_PATH = FIXTURE_DIR / "warehouse_w3_expected.json"


def load_expected() -> dict:
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


def private_dir(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)
    return path


def identity(user_id: str, *, domain: str = "group-1", scope: str = "brand_a") -> list[dict]:
    return [
        {
            "identity_domain": domain,
            "source_channel": "taobao",
            "source_user_id": f"tb-{user_id}",
            "synthetic_user_id": user_id,
            "permission_scope": scope,
        }
    ]


def line_for(order: dict, product_id: str = "sku_a") -> dict:
    return {
        "line_id": f"{order['synthetic_user_id']}-{order['order_id']}-l1",
        "synthetic_user_id": order["synthetic_user_id"],
        "order_id": order["order_id"],
        "product_id": product_id,
        "quantity": 1,
    }


def write_source(directory, *, orders, expected, refunds=None, identities=None, as_of=None, rules=None, rule_version=None):
    if identities is None:
        seen = set()
        identities = []
        for order in orders:
            user_id = order["synthetic_user_id"]
            if user_id not in seen:
                seen.add(user_id)
                identities.extend(identity(user_id))
    kwargs = {
        "orders": orders,
        "lines": [line_for(order) for order in orders],
        "refunds": refunds or [],
        "product_versions": expected["shared_product_versions"],
        "identities": identities,
        "as_of": as_of or expected["as_of"],
        "seed": None,
        "source_kind": "hand_fixture",
        "generator_id": "warehouse-w3-hand-incremental",
    }
    if rules is not None:
        kwargs["rules"] = rules
    if rule_version is not None:
        kwargs["rule_version"] = rule_version
    return write_tabular_sources(directory, **kwargs)


def header_index(rows: list[dict]) -> dict[tuple[str, str], dict]:
    return {(row["synthetic_user_id"], row["order_id"]): row for row in rows}


def read_brand_a(run, tmp_path, name: str = "tmp"):
    connection = run.connect_readonly(private_dir(tmp_path, name))
    try:
        return read_fact_order_header(connection, permission_scope="brand_a")
    finally:
        connection.close()


def load_extra(run) -> dict:
    return run.observation["stages"][3]["extra"]


def transform_extra(run) -> dict:
    return run.observation["stages"][2]["extra"]


def old_global_max_pay_time_keep(paid_at: str, *, max_pay_time: str, now: str, window_days: int) -> tuple[bool, bool]:
    paid = utc_naive_instant(paid_at)
    max_pay = utc_naive_instant(max_pay_time)
    today = utc_naive_instant(now).replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = today - timedelta(days=window_days)
    is_new = paid > max_pay
    is_refresh = paid >= window_start and paid <= max_pay
    return is_new, is_refresh


def fingerprint(rows: list[dict]) -> list[tuple]:
    return [
        (
            row["synthetic_user_id"],
            row["order_id"],
            row["channel"],
            row["status"],
            row["gross_paid_minor"],
            row["refund_minor_as_of"],
            row["net_paid_minor"],
            row["is_valid"],
        )
        for row in rows
    ]


def test_expected_fixture_is_hand_calculated_not_dumped():
    expected = load_expected()
    text = EXPECTED_PATH.read_text(encoding="utf-8")
    assert expected["method"] == "hand_calculated"
    assert expected["computation"] == "NOT_RUN"
    assert expected["not_generated_from_sql"] is True
    assert "dump" not in text.lower()
    assert expected["late_historical"]["expected_header_gross_sum_minor"] == 3500
    assert expected["future_refund"]["next_snapshot"]["net_paid_minor"] == 5000
    assert expected["outside_30d_refund"]["expected"]["net_paid_minor"] == 4500
    assert expected["resend"]["expected_gross_sum_minor"] == 5000
    assert expected["rule_change"]["before"]["net-1"]["net_paid_minor"] == 8000
    assert expected["rule_change"]["after"]["net-1"]["net_paid_minor"] == 7000
    assert expected["notes"]["late_historical"].startswith("recent-1 1000 + late-hist-1 2500 = 3500")
    assert expected["notes"]["rule_net"] == (
        "net-1 10000 minus standard 2000 = 8000 under v1; v2 also counts correction 1000 so 10000-2000-1000=7000."
    )


def test_late_historical_order_uses_hash_pk_not_max_pay_time(tmp_path):
    expected = load_expected()
    spec = expected["late_historical"]
    incoming = spec["incoming_orders"][0]
    is_new, is_refresh = old_global_max_pay_time_keep(
        incoming["paid_at"],
        max_pay_time=expected["existing_max_pay_time"],
        now=expected["as_of"],
        window_days=expected["window_days"],
    )
    assert is_new is spec["old_rule_would_append"]
    assert is_refresh is spec["old_rule_would_refresh"]

    warehouse_dir = private_dir(tmp_path, "wh")
    write_source(private_dir(tmp_path, "src1"), orders=spec["existing_orders"], expected=expected)
    run_warehouse_pipeline(tmp_path / "src1", warehouse_dir)
    write_source(private_dir(tmp_path, "src2"), orders=spec["incoming_orders"], expected=expected)
    run = run_warehouse_pipeline(tmp_path / "src2", warehouse_dir, incremental=True)
    extra = load_extra(run)
    assert extra["used_global_max_pay_time"] is False
    assert extra["used_mtime_as_incremental_cursor"] is False
    assert extra["full_table_rebuild"] is False
    assert extra["content_hash_compared"] is True
    assert extra["affected_order_keys"] == spec["expected_affected_order_keys"]
    headers = read_brand_a(run, tmp_path)
    keys = sorted((row["synthetic_user_id"], row["order_id"]) for row in headers)
    assert keys == [tuple(item) for item in spec["expected_loaded_keys"]]
    assert len(headers) == spec["expected_header_count"]
    assert sum(row["gross_paid_minor"] for row in headers) == spec["expected_header_gross_sum_minor"]


def test_future_refund_held_until_next_as_of_snapshot(tmp_path):
    expected = load_expected()
    spec = expected["future_refund"]
    warehouse_dir = private_dir(tmp_path, "wh")
    write_source(private_dir(tmp_path, "src1"), orders=[spec["order"]], expected=expected)
    run_warehouse_pipeline(tmp_path / "src1", warehouse_dir)

    write_source(
        private_dir(tmp_path, "src2"),
        orders=[],
        refunds=[spec["refund"]],
        identities=identity(spec["order"]["synthetic_user_id"]),
        expected=expected,
    )
    held_run = run_warehouse_pipeline(tmp_path / "src2", warehouse_dir, incremental=True)
    held_extra = load_extra(held_run)
    assert held_extra["as_of_unchanged"] is True
    assert held_extra["full_table_rebuild"] is False
    assert held_extra["future_refunds_held"] == 1
    assert held_extra["affected_order_keys"] == 1
    held = header_index(read_brand_a(held_run, tmp_path, "tmp-held"))[("u-ref", "held-1")]
    assert held["gross_paid_minor"] == spec["held"]["gross_paid_minor"]
    assert held["refund_minor_as_of"] == spec["held"]["refund_minor_as_of"]
    assert held["net_paid_minor"] == spec["held"]["net_paid_minor"]
    assert held["is_valid"] is spec["held"]["is_valid"]
    assert held_run.published_manifest["as_of"] == spec["held"]["as_of"]

    write_source(
        private_dir(tmp_path, "src3"),
        orders=[],
        refunds=[spec["refund"]],
        identities=identity(spec["order"]["synthetic_user_id"]),
        expected=expected,
        as_of=expected["next_as_of"],
    )
    next_run = run_warehouse_pipeline(tmp_path / "src3", warehouse_dir, incremental=True)
    next_extra = load_extra(next_run)
    assert next_extra["as_of_unchanged"] is False
    assert next_extra["full_table_rebuild"] is False
    nxt = header_index(read_brand_a(next_run, tmp_path, "tmp-next"))[("u-ref", "held-1")]
    assert nxt["refund_minor_as_of"] == spec["next_snapshot"]["refund_minor_as_of"]
    assert nxt["net_paid_minor"] == spec["next_snapshot"]["net_paid_minor"]
    assert nxt["is_valid"] is spec["next_snapshot"]["is_valid"]
    assert next_run.published_manifest["as_of"] == spec["next_snapshot"]["as_of"]


def test_refund_outside_30_day_window_still_applies_when_before_as_of(tmp_path):
    expected = load_expected()
    spec = expected["outside_30d_refund"]
    is_new, is_refresh = old_global_max_pay_time_keep(
        spec["order"]["paid_at"],
        max_pay_time=expected["existing_max_pay_time"],
        now=expected["as_of"],
        window_days=expected["window_days"],
    )
    assert is_new is False
    assert is_refresh is False
    warehouse_dir = private_dir(tmp_path, "wh")
    write_source(private_dir(tmp_path, "src1"), orders=[spec["order"]], expected=expected)
    run_warehouse_pipeline(tmp_path / "src1", warehouse_dir)
    write_source(
        private_dir(tmp_path, "src2"),
        orders=[],
        refunds=[spec["refund"]],
        identities=identity(spec["order"]["synthetic_user_id"]),
        expected=expected,
    )
    run = run_warehouse_pipeline(tmp_path / "src2", warehouse_dir, incremental=True)
    assert load_extra(run)["used_global_max_pay_time"] is False
    row = header_index(read_brand_a(run, tmp_path))[("u-old", "old-1")]
    assert row["gross_paid_minor"] == spec["expected"]["gross_paid_minor"]
    assert row["refund_minor_as_of"] == spec["expected"]["refund_minor_as_of"]
    assert row["net_paid_minor"] == spec["expected"]["net_paid_minor"]
    assert row["is_valid"] is spec["expected"]["is_valid"]


def test_late_order_for_same_user_replaces_first_purchase(tmp_path):
    expected = load_expected()
    spec = expected["first_purchase_late"]
    warehouse_dir = private_dir(tmp_path, "wh")
    write_source(private_dir(tmp_path, "src1"), orders=[spec["existing_order"]], expected=expected)
    run_warehouse_pipeline(tmp_path / "src1", warehouse_dir)
    write_source(private_dir(tmp_path, "src2"), orders=[spec["incoming_order"]], expected=expected)
    run = run_warehouse_pipeline(tmp_path / "src2", warehouse_dir, incremental=True)
    connection = run.connect_readonly(private_dir(tmp_path, "tmp"))
    try:
        firsts = {row["synthetic_user_id"]: row for row in read_first_purchases(connection, permission_scope="brand_a")}
    finally:
        connection.close()
    first = firsts["u-fp"]
    assert first["order_id"] == spec["expected_first"]["order_id"]
    assert first["channel"] == spec["expected_first"]["channel"]
    assert first["header_gross_paid_minor"] == spec["expected_first"]["header_gross_paid_minor"]
    assert first["header_net_paid_minor"] == spec["expected_first"]["header_net_paid_minor"]


def test_source_resend_same_content_hash_does_not_double_count(tmp_path):
    expected = load_expected()
    spec = expected["resend"]
    warehouse_dir = private_dir(tmp_path, "wh")
    first_src = write_source(private_dir(tmp_path, "src1"), orders=[spec["order"]], expected=expected)
    run_warehouse_pipeline(first_src.directory, warehouse_dir)
    second_src = write_source(private_dir(tmp_path, "src2"), orders=[spec["order"]], expected=expected)
    assert second_src.content_hash == first_src.content_hash
    run = run_warehouse_pipeline(second_src.directory, warehouse_dir, incremental=True)
    extra = load_extra(run)
    assert extra["affected_order_keys"] == spec["expected_affected_on_resend"]
    assert extra["new_or_changed_records"] == 0
    assert extra["unchanged_records"] > 0
    headers = read_brand_a(run, tmp_path)
    assert len(headers) == spec["expected_header_count"]
    assert sum(row["gross_paid_minor"] for row in headers) == spec["expected_gross_sum_minor"]


def test_rule_change_updates_only_affected_net_and_validity(tmp_path):
    expected = load_expected()
    spec = expected["rule_change"]
    warehouse_dir = private_dir(tmp_path, "wh")
    write_source(
        private_dir(tmp_path, "src1"),
        orders=spec["orders"],
        refunds=spec["refunds"],
        expected=expected,
        rules=expected["rules_v1"],
        rule_version="analytics-warehouse-rules/w3-v1",
    )
    first = run_warehouse_pipeline(tmp_path / "src1", warehouse_dir)
    before = header_index(read_brand_a(first, tmp_path, "tmp-before"))
    for order_id, values in spec["before"].items():
        row = before[("u-rule", order_id)]
        for key, value in values.items():
            assert row[key] == value, (order_id, key, row[key], value)

    write_source(
        private_dir(tmp_path, "src2"),
        orders=spec["orders"],
        refunds=spec["refunds"],
        expected=expected,
        rules=expected["rules_v2"],
        rule_version="analytics-warehouse-rules/w3-v2",
    )
    second = run_warehouse_pipeline(tmp_path / "src2", warehouse_dir, incremental=True)
    extra = load_extra(second)
    assert extra["rules_changed"] is True
    assert extra["full_table_rebuild"] is False
    assert extra["affected_order_keys"] == spec["expected_affected_order_keys"]
    after = header_index(read_brand_a(second, tmp_path, "tmp-after"))
    for order_id, values in spec["after"].items():
        row = after[("u-rule", order_id)]
        for key, value in values.items():
            assert row[key] == value, (order_id, key, row[key], value)


def test_no_change_rerun_is_idempotent(tmp_path):
    expected = load_expected()
    spec = expected["resend"]
    warehouse_dir = private_dir(tmp_path, "wh")
    write_source(private_dir(tmp_path, "src1"), orders=[spec["order"]], expected=expected)
    first = run_warehouse_pipeline(tmp_path / "src1", warehouse_dir)
    first_headers = read_brand_a(first, tmp_path, "tmp1")
    write_source(private_dir(tmp_path, "src2"), orders=[spec["order"]], expected=expected)
    second = run_warehouse_pipeline(tmp_path / "src2", warehouse_dir, incremental=True)
    second_headers = read_brand_a(second, tmp_path, "tmp2")
    assert fingerprint(first_headers) == fingerprint(second_headers)
    assert first.row_counts == second.row_counts
    assert load_extra(second)["affected_order_keys"] == 0
    assert load_extra(second)["headers_rewritten"] == 0


def test_cross_permission_scope_still_refused_after_incremental(tmp_path):
    expected = load_expected()
    spec = expected["permission"]
    warehouse_dir = private_dir(tmp_path, "wh")
    write_source(
        private_dir(tmp_path, "src1"),
        orders=[spec["brand_a_order"], spec["brand_b_order"]],
        identities=identity("u-a") + identity("u-b", domain="group-2", scope="brand_b"),
        expected=expected,
    )
    run_warehouse_pipeline(tmp_path / "src1", warehouse_dir)
    write_source(
        private_dir(tmp_path, "src2"),
        orders=[
            {
                "synthetic_user_id": "u-a",
                "order_id": "scope-a-2",
                "paid_at": "2026-08-12T00:00:00+08:00",
                "channel": "A",
                "status": "PAID",
                "gross_paid_minor": 400,
            }
        ],
        expected=expected,
    )
    run = run_warehouse_pipeline(tmp_path / "src2", warehouse_dir, incremental=True)
    connection = run.connect_readonly(private_dir(tmp_path, "tmp"))
    try:
        with pytest.raises(PermissionScopeDenied):
            read_fact_order_header(
                connection,
                permission_scope=spec["cross_scope_request"]["permission_scope"],
                synthetic_user_ids=spec["cross_scope_request"]["synthetic_user_ids"],
            )
        brand_a = read_fact_order_header(connection, permission_scope="brand_a")
        brand_b = read_fact_order_header(connection, permission_scope="brand_b")
    finally:
        connection.close()
    assert {row["synthetic_user_id"] for row in brand_a} == {"u-a"}
    assert {row["synthetic_user_id"] for row in brand_b} == {"u-b"}
    assert sum(row["gross_paid_minor"] for row in brand_a) == 3400


def test_incremental_observation_still_uses_tracemalloc(tmp_path):
    expected = load_expected()
    warehouse_dir = private_dir(tmp_path, "wh")
    write_source(private_dir(tmp_path, "src1"), orders=expected["late_historical"]["existing_orders"], expected=expected)
    run_warehouse_pipeline(tmp_path / "src1", warehouse_dir)
    write_source(private_dir(tmp_path, "src2"), orders=expected["late_historical"]["incoming_orders"], expected=expected)
    run = run_warehouse_pipeline(tmp_path / "src2", warehouse_dir, incremental=True)
    names = [stage["name"] for stage in run.observation["stages"]]
    assert names == ["ingest", "identity", "transform", "load", "publish"]
    for stage in run.observation["stages"]:
        assert stage["memory_method"] == "tracemalloc_reset_peak"
        assert stage["uses_ru_maxrss"] is False
        assert stage["stage_memory_peak_bytes"] != run.observation["process_ru_maxrss_bytes"]
    assert run.observation["process_ru_maxrss_is_stage_peak"] is False
    assert transform_extra(run)["content_hash_compared"] is True
    assert transform_extra(run)["used_mtime_as_incremental_cursor"] is False
    assert datetime.fromisoformat(expected["as_of"])
