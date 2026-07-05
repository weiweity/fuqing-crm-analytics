"""Sprint N+2 Trino single-node POC regression tests."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_trino_compose_has_single_node_poc_services_and_safe_ports() -> None:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.trino.yml").read_text())
    services = compose["services"]

    assert {"minio", "hive-metastore", "trino-coordinator", "trino-worker"} <= set(services)
    assert "${FQ_TRINO_COORDINATOR_PORT:-18080}:8080" in services["trino-coordinator"]["ports"]
    assert "${FQ_TRINO_MINIO_PORT:-19000}:9000" in services["minio"]["ports"]
    assert "8000:8000" not in str(compose)


def test_trino_order_schema_matches_backend_database_contract() -> None:
    schema = _load_module("trino_poc_schema", REPO_ROOT / "scripts/trino_poc/schema.py")
    columns = schema.orders_column_names()

    expected = [
        "order_id",
        "sub_order_id",
        "user_id",
        "user_nickname",
        "order_time",
        "pay_time",
        "ship_time",
        "order_type",
        "order_status",
        "product_id",
        "merchant_code",
        "product_title",
        "sku_id",
        "sku_code",
        "sku_name",
        "quantity",
        "amount",
        "refund_status",
        "refund_amount",
        "actual_amount",
        "province",
        "city",
        "influencer_name",
        "influencer_id",
        "live_room_id",
        "video_id",
        "traffic_source",
        "traffic_type",
        "seller_note",
        "year",
        "month",
        "is_member",
        "spu_category",
        "spu_type",
        "spu_tier",
        "spu_product_class",
        "spu_product_subclass",
        "spu_cosmetic",
        "spu_spec",
        "spu_hash",
        "channel",
        "is_goujinjin",
        "is_refund",
    ]
    assert columns == expected
    assert "sample_received_at" not in columns


def test_benchmark_has_ten_required_scenarios_and_channel_aliases() -> None:
    benchmark = _load_module("trino_poc_benchmark", REPO_ROOT / "scripts/trino_poc/benchmark.py")
    scenarios = benchmark.SCENARIOS

    assert len(scenarios) == 10
    assert [scenario.scenario_id for scenario in scenarios] == [
        "s01_monthly_gmv",
        "s02_rfm_lifecycle_value_potential",
        "s03_channel_distribution_yoy",
        "s04_category_transition",
        "s05_refund_rate",
        "s06_member_repurchase",
        "s07_member_lifecycle_distribution",
        "s08_channel_share",
        "s09_r_bucket_repurchase",
        "s10_top20_category_growth",
    ]

    channel_filter_pattern = re.compile(r"(?<!\.)\bchannel\b\s*(?:=|IN|NOT\s+IN)\b", re.I)
    for scenario in scenarios:
        assert not channel_filter_pattern.search(scenario.sql), scenario.scenario_id


def test_r_bucket_boundaries_follow_ssot() -> None:
    schema = _load_module("trino_poc_schema", REPO_ROOT / "scripts/trino_poc/schema.py")
    assert schema.R_BUCKETS == (
        ("近1个月已购客", 0, 30),
        ("近2-3个月已购客", 31, 90),
        ("近4-6月已购客", 91, 180),
        ("近7-12个月已购客", 181, 365),
        ("近13个月-近24个月已购客", 366, 730),
        ("2年外已购客", 731, 99999),
    )


def test_percentile_interpolation() -> None:
    benchmark = _load_module("trino_poc_benchmark", REPO_ROOT / "scripts/trino_poc/benchmark.py")
    values = [0.1, 0.2, 0.3, 0.4]
    assert benchmark.percentile(values, 0.50) == 0.25
    assert round(benchmark.percentile(values, 0.95), 3) == 0.385


def test_opsview_has_trino_stage2_stub_card() -> None:
    ops_view = (REPO_ROOT / "frontend-vue3/src/views/OpsView.vue").read_text()
    assert "Trino POC 状态" in ops_view
    assert "trinoBenchmarkRows" in ops_view
    assert "SQL 兼容" in ops_view
