"""W4 customer features over published W1–W3 facts. Production modules do not import this file."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from backend.services.analytics.customer_features import (
    FEATURE_LAYER_VERSION,
    compute_customer_features,
    write_customer_features,
)
from backend.services.analytics.warehouse.contract import PermissionScopeDenied, WarehouseContractError
from backend.services.analytics.warehouse.facts import read_fact_order_header, read_fact_order_line
from backend.services.analytics.warehouse.generate import write_tabular_sources
from backend.services.analytics.warehouse.pipeline import run_warehouse_pipeline

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SNAPSHOT_PATH = FIXTURE_DIR / "warehouse_w4_customer_features_snapshot.json"
EXPECTED_PATH = FIXTURE_DIR / "warehouse_w4_customer_features_expected.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def private_dir(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)
    return path


def write_source(directory, snapshot: dict, *, orders, lines, refunds=None, identities=None, as_of=None):
    return write_tabular_sources(
        directory,
        orders=orders,
        lines=lines,
        refunds=refunds if refunds is not None else snapshot["refunds"],
        product_versions=snapshot["product_versions"],
        identities=identities if identities is not None else snapshot["identities"],
        as_of=as_of or snapshot["as_of"],
        seed=None,
        source_kind="hand_fixture",
        generator_id="warehouse-w4-customer-features",
    )


def materialize_w4(tmp_path: Path):
    snapshot = load_json(SNAPSHOT_PATH)
    source = write_source(
        private_dir(tmp_path, "src"),
        snapshot,
        orders=snapshot["orders"],
        lines=snapshot["lines"],
    )
    run = run_warehouse_pipeline(source.directory, private_dir(tmp_path, "wh"))
    return run, snapshot, load_json(EXPECTED_PATH)


def features_for(run, tmp_path, *, scope: str, name: str = "tmp", feature_as_of=None, users=None):
    connection = run.connect_readonly(private_dir(tmp_path, name))
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM duckdb_tables() WHERE schema_name = 'main' AND NOT internal"
            ).fetchall()
        }
        result = compute_customer_features(
            connection,
            permission_scope=scope,
            published_manifest=run.published_manifest,
            feature_as_of=feature_as_of,
            synthetic_user_ids=users,
            database_path=run.database,
        )
        tables_after = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM duckdb_tables() WHERE schema_name = 'main' AND NOT internal"
            ).fetchall()
        }
    finally:
        connection.close()
    return result, tables, tables_after


def by_user(rows) -> dict:
    return {row["synthetic_user_id"]: row for row in rows}


def test_expected_fixture_is_hand_calculated_not_dumped():
    expected = load_json(EXPECTED_PATH)
    snapshot = load_json(SNAPSHOT_PATH)
    text = EXPECTED_PATH.read_text(encoding="utf-8")
    assert expected["method"] == "hand_calculated"
    assert expected["hand_calculated"] is True
    assert expected["computation"] == "NOT_RUN"
    assert expected["not_generated_from_sql"] is True
    assert expected["not_rfm_buckets"] is True
    assert "dump" not in text.lower()
    assert expected["fixture_id"] == snapshot["fixture_id"]
    assert expected["fixture_id"] != "warehouse-w2-hand-snapshot/v1"
    assert expected["brand_a_as_of"][0]["valid_net_paid_minor"] == 15000
    assert expected["notes"]["u_refund_net"] == "7000+4000+8000=19000 at warehouse as_of 2026-09-01."
    assert expected["notes"]["days_u_basket"].endswith("91.")
    assert expected["clock_advance_brand_a"][0]["days_since_last_paid"] == 106
    assert expected["warehouse_rebuild_next_as_of"]["u-refund"]["valid_net_paid_minor"] == 17000


def test_brand_a_features_match_hand_gold(tmp_path):
    run, _snapshot, expected = materialize_w4(tmp_path)
    result, tables, tables_after = features_for(run, tmp_path, scope="brand_a")
    assert tables == tables_after
    assert "fact_customer_feature" not in tables_after
    assert result.feature_layer_version == FEATURE_LAYER_VERSION
    assert result.schema_version == expected["schema_version"]
    assert result.rule_version == run.published_manifest["rule_version"]
    assert result.pipeline_version == run.published_manifest["pipeline_version"]
    assert result.content_hash == run.published_manifest["content_hash"]
    assert result.database_sha256 == run.published_manifest["database_sha256"]
    assert result.warehouse_as_of == expected["as_of"]
    assert result.feature_as_of == expected["as_of"]
    assert result.permission_scope == "brand_a"
    assert result.timezone == expected["timezone"]
    assert result.amount_unit == "minor"
    assert result.amount_precision == "integer_fen"
    assert [row for row in result.rows] == expected["brand_a_as_of"]
    assert {row["synthetic_user_id"] for row in result.rows} == set(expected["permission"]["brand_a_feature_user_ids"])
    for user_id in expected["absent_at_warehouse_as_of"]:
        assert user_id not in by_user(result.rows)


def test_multiline_order_counts_once_not_by_lines(tmp_path):
    run, _snapshot, expected = materialize_w4(tmp_path)
    connection = run.connect_readonly(private_dir(tmp_path, "tmp-lines"))
    try:
        headers = {
            (row["synthetic_user_id"], row["order_id"]): row
            for row in read_fact_order_header(connection, permission_scope="brand_a")
        }
        lines = [row for row in read_fact_order_line(connection, permission_scope="brand_a") if row["order_id"] == "basket-1"]
        result = compute_customer_features(
            connection,
            permission_scope="brand_a",
            published_manifest=run.published_manifest,
            database_path=run.database,
        )
    finally:
        connection.close()
    basket = headers[("u-basket", "basket-1")]
    feature = by_user(result.rows)["u-basket"]
    assert len(lines) == expected["basket_line_count"]
    assert basket["net_paid_minor"] == expected["basket_header_net_minor"]
    assert feature["valid_order_count"] == 1
    assert feature["valid_net_paid_minor"] == expected["basket_header_net_minor"]
    assert feature["valid_net_paid_minor"] != expected["basket_header_net_minor"] * len(lines)


def test_refunds_as_of_cutoff_and_invalid_orders_excluded(tmp_path):
    run, _snapshot, expected = materialize_w4(tmp_path)
    result, _, _ = features_for(run, tmp_path, scope="brand_a", name="tmp-refund")
    rows = by_user(result.rows)
    refund = rows["u-refund"]
    assert refund["valid_order_count"] == 3
    assert refund["valid_net_paid_minor"] == 19000
    assert refund["first_order_id"] == "paid-1"
    assert refund["last_order_id"] == "held-1"
    assert "u-invalid" not in rows
    assert "u-future" not in rows


def test_same_instant_first_and_last_follow_order_id_bytes(tmp_path):
    run, _snapshot, expected = materialize_w4(tmp_path)
    result, _, _ = features_for(run, tmp_path, scope="brand_a", name="tmp-same")
    same = by_user(result.rows)["u-same"]
    gold = expected["brand_a_as_of"][4]
    assert same["first_order_id"] == "same-a"
    assert same["last_order_id"] == "same-b"
    assert same["first_paid_at"] == same["last_paid_at"] == gold["first_paid_at"]
    assert same["valid_net_paid_minor"] == 10000


def test_clock_advance_changes_recency_without_future_leakage(tmp_path):
    run, _snapshot, expected = materialize_w4(tmp_path)
    advanced, _, _ = features_for(
        run,
        tmp_path,
        scope="brand_a",
        name="tmp-clock",
        feature_as_of=expected["next_as_of"],
    )
    assert advanced.warehouse_as_of == expected["as_of"]
    assert advanced.feature_as_of == expected["next_as_of"]
    actual = by_user(advanced.rows)
    assert "u-future" not in actual
    assert "u-late" not in actual
    for item in expected["clock_advance_brand_a"]:
        row = actual[item["synthetic_user_id"]]
        assert row["last_paid_at"] == item["last_paid_at"]
        assert row["valid_order_count"] == item["valid_order_count"]
        assert row["valid_net_paid_minor"] == item["valid_net_paid_minor"]
        assert row["days_since_last_paid"] == item["days_since_last_paid"]
    baseline = by_user(expected["brand_a_as_of"])
    assert actual["u-refund"]["days_since_last_paid"] - baseline["u-refund"]["days_since_last_paid"] == 15
    assert actual["u-refund"]["valid_net_paid_minor"] == baseline["u-refund"]["valid_net_paid_minor"]


def test_feature_as_of_before_warehouse_snapshot_is_rejected(tmp_path):
    run, _snapshot, _expected = materialize_w4(tmp_path)
    connection = run.connect_readonly(private_dir(tmp_path, "tmp-early"))
    try:
        with pytest.raises(WarehouseContractError, match="cannot precede warehouse snapshot as_of"):
            compute_customer_features(
                connection,
                permission_scope="brand_a",
                published_manifest=run.published_manifest,
                feature_as_of="2026-08-01T00:00:00+08:00",
            )
    finally:
        connection.close()


def test_late_historical_order_appears_after_incremental(tmp_path):
    run, snapshot, expected = materialize_w4(tmp_path)
    before, _, _ = features_for(run, tmp_path, scope="brand_a", name="tmp-before-late")
    assert "u-late" not in by_user(before.rows)
    write_source(
        private_dir(tmp_path, "src-late"),
        snapshot,
        orders=[snapshot["late_order"]],
        lines=[snapshot["late_line"]],
        refunds=[],
        identities=[item for item in snapshot["identities"] if item["synthetic_user_id"] == "u-late"],
    )
    late_run = run_warehouse_pipeline(tmp_path / "src-late", Path(run.directory), incremental=True)
    after, _, _ = features_for(late_run, tmp_path, scope="brand_a", name="tmp-after-late")
    late = by_user(after.rows)["u-late"]
    gold = expected["late_incremental"]
    for key, value in gold.items():
        assert late[key] == value
    assert by_user(after.rows)["u-basket"]["valid_net_paid_minor"] == 15000


def test_warehouse_as_of_rebuild_applies_held_refund_and_future_paid(tmp_path):
    run, snapshot, expected = materialize_w4(tmp_path)
    write_source(
        private_dir(tmp_path, "src-next"),
        snapshot,
        orders=[],
        lines=[],
        as_of=expected["next_as_of"],
    )
    next_run = run_warehouse_pipeline(tmp_path / "src-next", Path(run.directory), incremental=True)
    result, _, _ = features_for(next_run, tmp_path, scope="brand_a", name="tmp-rebuild")
    assert next_run.published_manifest["as_of"] == expected["next_as_of"]
    assert result.warehouse_as_of == expected["next_as_of"]
    rows = by_user(result.rows)
    refund = rows["u-refund"]
    future = rows["u-future"]
    refund_gold = expected["warehouse_rebuild_next_as_of"]["u-refund"]
    future_gold = expected["warehouse_rebuild_next_as_of"]["u-future"]
    for key, value in refund_gold.items():
        assert refund[key] == value
    for key, value in future_gold.items():
        assert future[key] == value


def test_identity_domain_and_permission_scope_are_isolated(tmp_path):
    run, _snapshot, expected = materialize_w4(tmp_path)
    brand_a, _, _ = features_for(run, tmp_path, scope="brand_a", name="tmp-scope-a")
    brand_b, _, _ = features_for(run, tmp_path, scope="brand_b", name="tmp-scope-b")
    assert {row["synthetic_user_id"] for row in brand_a.rows} == set(expected["permission"]["brand_a_feature_user_ids"])
    assert {row["synthetic_user_id"] for row in brand_b.rows} == set(expected["permission"]["brand_b_feature_user_ids"])
    assert brand_b.rows[0] == expected["brand_b_as_of"][0]
    assert all(row["identity_domain"] == "group-1" for row in brand_a.rows)
    assert all(row["identity_domain"] == "group-2" for row in brand_b.rows)
    connection = run.connect_readonly(private_dir(tmp_path, "tmp-cross"))
    try:
        with pytest.raises(PermissionScopeDenied):
            compute_customer_features(
                connection,
                permission_scope=expected["permission"]["cross_scope_request"]["permission_scope"],
                published_manifest=run.published_manifest,
                synthetic_user_ids=expected["permission"]["cross_scope_request"]["synthetic_user_ids"],
            )
        with pytest.raises(PermissionScopeDenied):
            compute_customer_features(
                connection,
                permission_scope="missing-scope",
                published_manifest=run.published_manifest,
            )
    finally:
        connection.close()


def test_written_output_carries_snapshot_rule_as_of_and_scope(tmp_path):
    run, _snapshot, expected = materialize_w4(tmp_path)
    result, _, _ = features_for(run, tmp_path, scope="brand_a", name="tmp-write")
    output = private_dir(tmp_path, "features-out")
    published = write_customer_features(result, output)
    written_rows = [
        json.loads(line)
        for line in (output / "customer_features.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    on_disk = json.loads((output / "published.json").read_text(encoding="utf-8"))
    assert written_rows == expected["brand_a_as_of"]
    assert published == on_disk
    assert on_disk["feature_layer_version"] == FEATURE_LAYER_VERSION
    assert on_disk["schema_version"] == expected["schema_version"]
    assert on_disk["rule_version"] == run.published_manifest["rule_version"]
    assert on_disk["pipeline_version"] == run.published_manifest["pipeline_version"]
    assert on_disk["content_hash"] == run.published_manifest["content_hash"]
    assert on_disk["database_sha256"] == run.published_manifest["database_sha256"]
    assert on_disk["warehouse_as_of"] == expected["as_of"]
    assert on_disk["feature_as_of"] == expected["as_of"]
    assert on_disk["permission_scope"] == "brand_a"
    assert on_disk["valid_order_rule"] == expected["valid_order_rule"]
    assert on_disk["order_grain"] == expected["order_grain"]
    assert on_disk["recency_unit"] == expected["recency_unit"]
    assert on_disk["contains_real_data"] is False
    assert on_disk["row_count"] == len(expected["brand_a_as_of"])
    assert on_disk["features_sha256"] == result.features_sha256


def test_output_digest_matches_file_and_mutation_is_rejected(tmp_path):
    import hashlib
    from dataclasses import replace

    run, _, _ = materialize_w4(tmp_path)
    result, _, _ = features_for(run, tmp_path, scope="brand_a")
    output = private_dir(tmp_path, "digest-output")
    published = write_customer_features(result, output)
    payload = (output / "customer_features.jsonl").read_bytes()
    assert hashlib.sha256(payload).hexdigest() == published["features_sha256"]
    assert hashlib.sha256(payload + b" ").hexdigest() != published["features_sha256"]
    bad = private_dir(tmp_path, "bad-digest")
    with pytest.raises(WarehouseContractError, match="changed"):
        write_customer_features(replace(result, features_sha256="0" * 64), bad)
    assert list(bad.iterdir()) == []
    result.rows[0]["valid_net_paid_minor"] = 1
    changed = private_dir(tmp_path, "changed")
    with pytest.raises(WarehouseContractError, match="changed"):
        write_customer_features(result, changed)
    assert list(changed.iterdir()) == []


def test_empty_output_digest_matches_zero_bytes(tmp_path):
    import hashlib

    run, _, _ = materialize_w4(tmp_path)
    result, _, _ = features_for(run, tmp_path, scope="brand_a", users=[])
    output = private_dir(tmp_path, "empty-output")
    manifest = write_customer_features(result, output)
    assert (output / "customer_features.jsonl").read_bytes() == b""
    assert manifest["features_sha256"] == hashlib.sha256(b"").hexdigest()
