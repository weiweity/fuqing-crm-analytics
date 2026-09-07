"""W1 synthetic warehouse baseline. Production modules do not import this file."""

from __future__ import annotations

import ast
import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from backend.services.analytics.warehouse.contract import (
    GENERATOR_VERSION,
    PIPELINE_VERSION,
    RULE_VERSION,
    SCHEMA_VERSION,
    utc_naive_instant,
)
from backend.services.analytics.warehouse.facts import read_fact_order_header
from backend.services.analytics.warehouse.generate import generate_synthetic_sources, write_tabular_sources
from backend.services.analytics.warehouse.pipeline import run_warehouse_pipeline

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
WAREHOUSE_ROOT = Path(__file__).resolve().parents[1] / "services" / "analytics" / "warehouse"


def load_json(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


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


def version(product_id: str) -> dict:
    return {
        "product_id": product_id,
        "product_version_id": f"{product_id}-v1",
        "valid_from": "2026-01-01T00:00:00+08:00",
        "valid_to": "2027-01-01T00:00:00+08:00",
    }


def line_for(order: dict, product_id: str = "sku_a") -> dict:
    return {
        "line_id": f"{order['synthetic_user_id']}-{order['order_id']}-l1",
        "synthetic_user_id": order["synthetic_user_id"],
        "order_id": order["order_id"],
        "product_id": product_id,
        "quantity": 1,
    }


def old_global_max_pay_time_keep(paid_at: str, *, max_pay_time: str, now: str, window_days: int) -> tuple[bool, bool]:
    """Diagnosis replica of load.filter_rolling_window. Not the warehouse loader."""
    paid = utc_naive_instant(paid_at)
    max_pay = utc_naive_instant(max_pay_time)
    today = utc_naive_instant(now).replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = today - timedelta(days=window_days)
    is_new = paid > max_pay
    is_refresh = paid >= window_start and paid <= max_pay
    return is_new, is_refresh


def test_warehouse_package_does_not_import_legacy_etl():
    for path in WAREHOUSE_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("scripts.etl"), path
                    assert alias.name != "scripts.run_etl"
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("scripts.etl"), path
                assert not node.module.startswith("scripts.run_etl")
                assert "test_w1_" not in node.module
                assert "test_w2_manifest" not in node.module


def test_generator_manifest_has_identity_hash_and_versions(tmp_path):
    spec = load_json("warehouse_w1_manifest_contract.json")
    source = generate_synthetic_sources(private_dir(tmp_path, "src"))
    manifest = source.to_dict()
    for key in spec["required_manifest_keys"]:
        assert key in manifest
    for key in spec["required_source_identity_keys"]:
        assert key in manifest["source_identity"]
    assert manifest["schema_version"] == SCHEMA_VERSION == spec["schema_version"]
    assert manifest["rule_version"] == RULE_VERSION == spec["rule_version"]
    assert manifest["generator_version"] == GENERATOR_VERSION == spec["generator_version"]
    assert manifest["pipeline_version"] == PIPELINE_VERSION == spec["pipeline_version"]
    assert manifest["contains_real_data"] is False
    assert manifest["data_source"] == spec["data_source"]
    assert manifest["seed"] == spec["seed"]
    assert manifest["as_of"] == spec["as_of"]
    assert manifest["amount_unit"] == "minor"
    assert manifest["amount_precision"] == "integer_fen"
    assert set(manifest["file_hashes"]) == set(spec["required_file_hash_names"])
    assert len(manifest["content_hash"]) == 64
    assert all(len(value) == 64 for value in manifest["file_hashes"].values())


def test_same_seed_same_content_hash(tmp_path):
    first = generate_synthetic_sources(private_dir(tmp_path, "a"), seed=20260907)
    second = generate_synthetic_sources(private_dir(tmp_path, "b"), seed=20260907)
    third = generate_synthetic_sources(private_dir(tmp_path, "c"), seed=20260908)
    assert first.content_hash == second.content_hash
    assert first.content_hash != third.content_hash
    assert first.to_dict()["file_hashes"] == second.to_dict()["file_hashes"]


def test_stage_observation_and_timer_cover_publish(tmp_path):
    spec = load_json("warehouse_w1_manifest_contract.json")
    source = generate_synthetic_sources(private_dir(tmp_path, "src"))
    run = run_warehouse_pipeline(source.directory, private_dir(tmp_path, "wh"))
    observation = run.observation
    names = [stage["name"] for stage in observation["stages"]]
    assert names == ["ingest", "identity", "transform", "load", "publish"]
    for stage in observation["stages"]:
        assert stage["memory_method"] == "tracemalloc_reset_peak"
        assert stage["uses_ru_maxrss"] is False
        assert type(stage["stage_memory_peak_bytes"]) is int
        assert stage["stage_memory_peak_bytes"] >= 0
        assert type(stage["duration_ns"]) is int
        assert stage["duration_ns"] >= 0
        assert type(stage["bytes_read"]) is int
        assert type(stage["rows_out"]) is int
        assert stage["stage_memory_peak_bytes"] != observation["process_ru_maxrss_bytes"]
    ingest = observation["stages"][0]
    assert ingest["bytes_read"] > 0
    assert ingest["extra"]["planned_equals_read"] is True
    publish = observation["stages"][-1]
    assert publish["extra"]["checkpoint"] is True
    assert publish["extra"]["connection_closed"] is True
    assert observation["timer_start_mark"] == "before_generate"
    assert observation["timer_end_mark"] == "after_publish_close"
    assert observation["checkpoint"] is True
    assert observation["connection_closed"] is True
    assert observation["manifest_written"] is True
    assert observation["published"] is True
    assert observation["process_ru_maxrss_is_stage_peak"] is False
    assert observation["process_ru_maxrss_note"] == "process_watermark_not_stage_peak"
    marks = observation["marks_ns"]
    assert marks["start"] == 0
    assert marks["after_publish"] >= marks["after_close"] >= marks["after_checkpoint"] >= marks["before_publish"]
    assert observation["total_duration_ns"] >= observation["sum_stage_duration_ns"]
    assert observation["total_duration_ns"] >= publish["duration_ns"]
    assert observation["resource_limits"]["duckdb_memory_mib"] == spec["resource_limits"]["duckdb_memory_mib"]
    assert observation["resource_limits"]["duckdb_threads"] == spec["resource_limits"]["duckdb_threads"]
    assert run.published_manifest["contains_real_data"] is False
    assert run.row_counts["fact_order_header"] == source.to_dict()["row_counts"]["orders"]


def test_file_age_filter_matches_actual_read_set(tmp_path):
    spec = load_json("warehouse_w1_file_age.json")
    recent_orders = [
        {
            "synthetic_user_id": "u-recent",
            "order_id": "r1",
            "paid_at": "2026-08-20T00:00:00+08:00",
            "channel": "A",
            "status": "PAID",
            "gross_paid_minor": 1000,
        },
        {
            "synthetic_user_id": "u-recent",
            "order_id": "r2",
            "paid_at": "2026-08-21T00:00:00+08:00",
            "channel": "A",
            "status": "PAID",
            "gross_paid_minor": 1100,
        },
    ]
    old_order = {
        "synthetic_user_id": "u-old",
        "order_id": "old-1",
        "paid_at": "2026-06-01T00:00:00+08:00",
        "channel": "B",
        "status": "PAID",
        "gross_paid_minor": 9999,
    }
    source_dir = private_dir(tmp_path, "src")
    write_tabular_sources(
        source_dir,
        orders=recent_orders,
        lines=[line_for(order) for order in recent_orders],
        refunds=[],
        product_versions=[version("sku_a")],
        identities=identity("u-recent") + identity("u-old"),
        as_of=spec["now"],
        seed=None,
        source_kind="hand_fixture",
        generator_id="warehouse-w1-file-age",
    )
    orders_path = source_dir / "orders.jsonl"
    recent_path = source_dir / "orders_recent.jsonl"
    old_path = source_dir / "orders_old.jsonl"
    recent_path.write_bytes(orders_path.read_bytes())
    orders_path.unlink()
    old_path.write_text(
        json.dumps(old_order, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    from backend.services.analytics.warehouse.generate import content_hash_from_file_hashes
    manifest_path = source_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["file_hashes"].pop("orders.jsonl")
    for path in (recent_path, old_path):
        manifest["file_hashes"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest["content_hash"] = content_hash_from_file_hashes(manifest["file_hashes"])
    manifest_path.write_text(json.dumps(manifest))
    now = datetime.fromisoformat(spec["now"])
    now_ts = now.timestamp()
    os.utime(recent_path, (now_ts - spec["files"][0]["mtime_days_ago"] * 86400,) * 2)
    os.utime(old_path, (now_ts - spec["files"][1]["mtime_days_ago"] * 86400,) * 2)
    run = run_warehouse_pipeline(
        source_dir,
        private_dir(tmp_path, "wh"),
        now=now,
        max_age_days=spec["max_age_days"],
        order_file_names=(),
        extra_order_patterns=("orders_*.jsonl",),
    )
    ingest = run.observation["stages"][0]
    assert ingest["extra"]["orders_read"] == spec["expected_read_names_after_filter"]
    assert ingest["extra"]["orders_skipped"] == spec["expected_skipped_names"]
    assert ingest["extra"]["planned_equals_read"] is True
    connection = run.connect_readonly(private_dir(tmp_path, "tmp"))
    try:
        headers = read_fact_order_header(connection, permission_scope="brand_a")
    finally:
        connection.close()
    keys = {(row["synthetic_user_id"], row["order_id"]) for row in headers}
    assert keys == {("u-recent", "r1"), ("u-recent", "r2")}
    assert len(headers) == spec["expected_rows_read"]
    assert ("u-old", "old-1") not in keys


def test_late_historical_order_not_dropped_by_max_pay_time(tmp_path):
    spec = load_json("warehouse_w1_late_order.json")
    existing = spec["existing_orders"][0]
    incoming = spec["incoming_orders"][0]
    is_new, is_refresh = old_global_max_pay_time_keep(
        incoming["paid_at"],
        max_pay_time=spec["existing_max_pay_time"],
        now=spec["now"],
        window_days=spec["window_days"],
    )
    assert is_new is spec["old_rule_would_append"]
    assert is_refresh is spec["old_rule_would_refresh"]

    first_src = private_dir(tmp_path, "src1")
    write_tabular_sources(
        first_src,
        orders=[existing],
        lines=[line_for(existing)],
        refunds=[],
        product_versions=[version("sku_a")],
        identities=identity(existing["synthetic_user_id"]),
        as_of=spec["as_of"],
        seed=None,
        source_kind="hand_fixture",
        generator_id="warehouse-w1-late-existing",
    )
    warehouse_dir = private_dir(tmp_path, "wh")
    run_warehouse_pipeline(first_src, warehouse_dir)

    second_src = private_dir(tmp_path, "src2")
    write_tabular_sources(
        second_src,
        orders=[incoming],
        lines=[line_for(incoming)],
        refunds=[],
        product_versions=[version("sku_a")],
        identities=identity(incoming["synthetic_user_id"]),
        as_of=spec["as_of"],
        seed=None,
        source_kind="hand_fixture",
        generator_id="warehouse-w1-late-incoming",
    )
    run = run_warehouse_pipeline(second_src, warehouse_dir, incremental=True)
    assert run.observation["stages"][3]["extra"]["used_global_max_pay_time"] is False
    connection = run.connect_readonly(private_dir(tmp_path, "tmp"))
    try:
        headers = read_fact_order_header(connection, permission_scope="brand_a")
    finally:
        connection.close()
    keys = sorted((row["synthetic_user_id"], row["order_id"]) for row in headers)
    assert keys == [tuple(item) for item in spec["expected_loaded_keys"]]
    assert len(headers) == spec["expected_header_count"]
    assert sum(row["gross_paid_minor"] for row in headers) == spec["expected_header_gross_sum_minor"]


def test_product_version_join_does_not_repeat_header_amount(tmp_path):
    spec = load_json("warehouse_w1_product_join.json")
    assert spec["hand_naive_cartesian_rows"] == spec["n_orders"] * spec["n_versions"]
    assert spec["expected_header_gross_sum_minor"] == spec["n_orders"] * spec["unit_gross_minor"]
    assert spec["wrong_join_gross_if_repeated"] == spec["hand_naive_cartesian_rows"] * spec["unit_gross_minor"]
    paid_at = spec["paid_at"]
    orders = []
    lines = []
    for index in range(spec["n_orders"]):
        order = {
            "synthetic_user_id": "u-join",
            "order_id": f"j-{index:03d}",
            "paid_at": paid_at,
            "channel": "A",
            "status": "PAID",
            "gross_paid_minor": spec["unit_gross_minor"],
        }
        orders.append(order)
        lines.append(line_for(order, spec["product_id"]))
    versions = []
    day0 = datetime.fromisoformat(spec["version_day0"])
    for index in range(spec["n_versions"]):
        start = day0 + timedelta(days=index)
        end = start + timedelta(days=1)
        versions.append({
            "product_id": spec["product_id"],
            "product_version_id": f"{spec['product_id']}-d{index:02d}",
            "valid_from": start.isoformat(),
            "valid_to": end.isoformat(),
        })
    source = write_tabular_sources(
        private_dir(tmp_path, "src"),
        orders=orders,
        lines=lines,
        refunds=[],
        product_versions=versions,
        identities=identity("u-join"),
        as_of="2026-09-01T00:00:00+08:00",
        seed=None,
        source_kind="hand_fixture",
        generator_id="warehouse-w1-product-join",
    )
    run = run_warehouse_pipeline(source.directory, private_dir(tmp_path, "wh"))
    transform = run.observation["stages"][2]
    assert transform["extra"]["unconstrained_product_join_rows"] == spec["hand_naive_cartesian_rows"]
    assert transform["extra"]["range_join_rows"] == spec["expected_join_matches"]
    assert transform["extra"]["header_amounts_aggregated_from_join"] is False
    assert run.row_counts["fact_order_header"] == spec["expected_header_count"]
    assert run.row_counts["fact_order_line"] == spec["expected_line_count"]
    connection = run.connect_readonly(private_dir(tmp_path, "tmp"))
    try:
        headers = read_fact_order_header(connection, permission_scope="brand_a")
        header_sum = connection.execute(
            "SELECT SUM(gross_paid_minor) FROM fact_order_header"
        ).fetchone()[0]
        joined_if_repeated = connection.execute(
            """
            SELECT SUM(h.gross_paid_minor)
            FROM fact_order_header h
            JOIN fact_order_line l
              ON encode(l.synthetic_user_id) = encode(h.synthetic_user_id)
             AND encode(l.order_id) = encode(h.order_id)
            """
        ).fetchone()[0]
    finally:
        connection.close()
    assert len(headers) == spec["expected_header_count"]
    assert int(header_sum) == spec["expected_header_gross_sum_minor"]
    assert int(joined_if_repeated) == spec["expected_header_gross_sum_minor"]
    assert int(header_sum) != spec["wrong_join_gross_if_repeated"]


def test_invalid_source_is_rejected_before_warehouse_creation(tmp_path):
    from backend.services.analytics.warehouse.generate import write_tabular_sources
    from backend.services.analytics.warehouse.pipeline import run_warehouse_pipeline
    from backend.services.analytics.warehouse.contract import WarehouseContractError
    src = tmp_path / "source"
    src.mkdir()
    write_tabular_sources(
        src,
        orders=[dict(synthetic_user_id="u", order_id="a", paid_at="2026-06-10T00:00:00+08:00",
                     channel="A", status="PAID", gross_paid_minor=1000)],
        lines=[dict(line_id="l", synthetic_user_id="u", order_id="a", product_id="sku", quantity=1)],
        refunds=[],
        product_versions=[dict(product_id="sku", product_version_id="v1",
                               valid_from="2026-01-01T00:00:00+08:00", valid_to="2027-01-01T00:00:00+08:00")],
        identities=[dict(identity_domain="d", source_channel="A", source_user_id="s",
                         synthetic_user_id="u", permission_scope="brand_a")],
    )
    with (src / "orders.jsonl").open("ab") as file:
        file.write(b"\n")
    wh = tmp_path / "warehouse"
    wh.mkdir()
    with pytest.raises(WarehouseContractError):
        run_warehouse_pipeline(src, wh)
    assert not list(wh.iterdir())
