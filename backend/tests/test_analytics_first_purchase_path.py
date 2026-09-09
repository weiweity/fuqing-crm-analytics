"""Offline first-purchase product-path compute. Production modules do not import this file."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from backend.semantic.analytics_first_purchase_path import (
    EMPTY_MATURE_COHORT,
    FAMILY_STATUS,
    QUERY_ID,
    snapshot_digest,
)
from backend.services.analytics.catalog import (
    QUERY_FAMILIES,
    QueryFamilyStatus,
    require_supported_query,
)
from backend.services.analytics.family_first_purchase import execute_first_purchase_path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SNAPSHOT_PATH = FIXTURE_DIR / "first_purchase_path_v1.json"
EXPECTED_PATH = FIXTURE_DIR / "first_purchase_path_v1_expected.json"
PERMISSION = "synthetic-demo"
AS_OF = "2026-09-01T00:00:00+08:00"

VALID_REQUEST = {
    "schema_version": "analytics-first-purchase-path/v1",
    "query_id": "first_purchase_product_path",
    "query_version": "first-purchase-path-query/v1",
    "metric_id": "first_purchase_product_n_day_path",
    "metric_version": "first-purchase-path-metric/v1",
    "cohort_window": {"kind": "FIXED", "start_date": "2026-06-01", "end_date": "2026-09-01"},
    "observation_days": 30,
    "data_snapshot_ref": "synthetic-first-purchase-path-v1",
    "timezone": "Asia/Shanghai",
    "channel_ids": [],
    "product_ids": [],
    "mapping_version": "sample-full-map/v1",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def private_dir(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)
    return path


def request_for(days=30, channel_ids=None, product_ids=None) -> dict:
    payload = deepcopy(VALID_REQUEST)
    payload["observation_days"] = days
    if channel_ids is not None:
        payload["channel_ids"] = channel_ids
    if product_ids is not None:
        payload["product_ids"] = product_ids
    return payload


def compute(tmp_path: Path, snapshot, days=30, channel_ids=None, product_ids=None, scope=PERMISSION, name="run"):
    return execute_first_purchase_path(
        request=request_for(days, channel_ids, product_ids),
        snapshot=snapshot,
        permission_scope=scope,
        fixture_directory=private_dir(tmp_path, f"{name}-db"),
        temp_directory=private_dir(tmp_path, f"{name}-tmp"),
    )


def expected_ratio(count: int, mature: int):
    if mature == 0:
        return None, EMPTY_MATURE_COHORT
    return count / mature, None


def assert_product_row(actual: dict, expected: dict):
    assert actual["product_id"] == expected["product_id"]
    for key in ("mature_count", "immature_count", "subsequent_any_count", "sample_to_full_count"):
        assert actual[key] == expected[key], (expected["product_id"], key, actual[key], expected[key])
    subsequent_ratio, empty = expected_ratio(expected["subsequent_any_count"], expected["mature_count"])
    converted_ratio, converted_empty = expected_ratio(expected["sample_to_full_count"], expected["mature_count"])
    assert empty == converted_empty
    assert actual["subsequent_any_ratio"] == subsequent_ratio
    assert actual["sample_to_full_ratio"] == converted_ratio
    assert actual["empty_reason"] == empty


def test_expected_fixture_is_hand_calculated_not_dumped():
    expected = load_json(EXPECTED_PATH)
    text = EXPECTED_PATH.read_text(encoding="utf-8")
    assert expected["method"] == "hand_calculated"
    assert expected["computation"] == "NOT_RUN"
    assert expected["not_generated_from_sql"] is True
    assert "dump" not in text.lower()
    assert expected["fixture_id"] != "synthetic-channel-followup-v1"
    assert expected["windows"]["30"]["cohort_enrolled_count"] == 10
    assert expected["windows"]["30"]["products"][3]["subsequent_any_count"] == 3
    assert "0.25" not in text
    assert "110000" not in text
    assert "25%" not in text


def _imported_names(path: Path) -> set[str]:
    import ast

    names = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.add(module)
            names.update(f"{module}.{alias.name}" for alias in node.names)
            names.update(alias.name for alias in node.names)
    return names


def test_catalog_supported_and_family_source_skips_channel_payload():
    family_path = Path(__file__).resolve().parents[1] / "services/analytics/family_first_purchase.py"
    semantic_path = Path(__file__).resolve().parents[1] / "semantic/analytics_first_purchase_path.py"
    imported = _imported_names(family_path) | _imported_names(semantic_path)
    assert "require_supported_query" not in imported
    assert "ChannelFollowupResult" not in imported
    assert "backend.services.analytics.catalog" not in imported
    assert QUERY_FAMILIES[QUERY_ID].status is QueryFamilyStatus.SUPPORTED_CONTRACT
    assert FAMILY_STATUS == "SUPPORTED_CONTRACT"
    require_supported_query(QUERY_ID)


@pytest.mark.parametrize("days", [30, 60, 90])
def test_golden_windows_match_hand_expected_field_by_field(tmp_path, days):
    snapshot = load_json(SNAPSHOT_PATH)
    result = compute(tmp_path, snapshot, days=days, name=f"g{days}")
    expected = load_json(EXPECTED_PATH)["windows"][str(days)]
    facts = result["facts"]
    assert result["query_id"] == QUERY_ID
    assert result["contains_real_data"] is False
    assert facts["observation_days"] == days
    assert facts["cohort_enrolled_count"] == expected["cohort_enrolled_count"]
    assert facts["cohort_mature_count"] == expected["cohort_mature_count"]
    assert facts["cohort_immature_count"] == expected["cohort_immature_count"]
    assert [row["product_id"] for row in facts["products"]] == [row["product_id"] for row in expected["products"]]
    for actual, row in zip(facts["products"], expected["products"], strict=True):
        assert_product_row(actual, row)
    dumped = json.dumps(facts)
    for banned in ("user_ids", "order_ids", "synthetic_user_ids", "members"):
        assert banned not in dumped
    assert 0.25 not in [row["subsequent_any_ratio"] for row in facts["products"]]
    assert 0.25 not in [row["sample_to_full_ratio"] for row in facts["products"]]


def test_channel_a_drops_b_firsts_and_keeps_unique_enrollment(tmp_path):
    result = compute(tmp_path, load_json(SNAPSHOT_PATH), days=30, channel_ids=["A"], name="only-a")
    expected = load_json(EXPECTED_PATH)["channel_a_n30"]
    facts = result["facts"]
    assert facts["cohort_enrolled_count"] == expected["cohort_enrolled_count"]
    assert facts["cohort_mature_count"] == expected["cohort_mature_count"]
    assert facts["cohort_immature_count"] == expected["cohort_immature_count"]
    assert [row["product_id"] for row in facts["products"]] == expected["product_ids"]
    sample = next(row for row in facts["products"] if row["product_id"] == "sample-sku-1")
    assert sample["mature_count"] == 6


def test_late_sku_empty_mature_is_null_not_zero(tmp_path):
    result = compute(tmp_path, load_json(SNAPSHOT_PATH), days=30, name="late")
    late = next(row for row in result["facts"]["products"] if row["product_id"] == "late-sku")
    assert late["mature_count"] == 0
    assert late["immature_count"] == 1
    assert late["subsequent_any_ratio"] is None
    assert late["sample_to_full_ratio"] is None
    assert late["empty_reason"] == EMPTY_MATURE_COHORT


def test_pre_cohort_first_is_excluded(tmp_path):
    snapshot = {
        "schema_version": "analytics-first-purchase-path/v1",
        "snapshot_id": "synthetic-first-purchase-path-v1",
        "data_version": "synthetic-first-purchase-path-data/v1",
        "as_of": AS_OF,
        "timezone": "Asia/Shanghai",
        "currency": "CNY",
        "amount_unit": "minor",
        "amount_precision": "integer_fen",
        "scope": "synthetic",
        "contains_real_data": False,
        "sku_mappings": load_json(SNAPSHOT_PATH)["sku_mappings"],
        "orders": [
            {"order_id": "early", "synthetic_user_id": "u", "paid_at": "2026-05-31T00:00:00+08:00",
             "channel": "A", "gross_paid_minor": 6100, "status": "PAID"},
            {"order_id": "in", "synthetic_user_id": "u", "paid_at": "2026-06-10T00:00:00+08:00",
             "channel": "A", "gross_paid_minor": 8800, "status": "PAID"},
        ],
        "lines": [
            {"line_id": "l1", "order_id": "early", "synthetic_user_id": "u", "product_id": "sample-sku-1", "quantity": 1},
            {"line_id": "l2", "order_id": "in", "synthetic_user_id": "u", "product_id": "full-sku-1", "quantity": 1},
        ],
        "refunds": [],
    }
    result = compute(tmp_path, snapshot, days=30, name="pre")
    assert result["facts"]["cohort_enrolled_count"] == 0
    assert result["facts"]["products"] == []


def test_same_time_orders_use_encode_order_id(tmp_path):
    snapshot = load_json(SNAPSHOT_PATH)
    result = compute(tmp_path, snapshot, days=30, name="same")
    sample = next(row for row in result["facts"]["products"] if row["product_id"] == "sample-sku-1")
    assert sample["subsequent_any_count"] == 3


def test_shared_order_id_does_not_merge_users(tmp_path):
    result = compute(tmp_path, load_json(SNAPSHOT_PATH), days=30, name="shared")
    sample = next(row for row in result["facts"]["products"] if row["product_id"] == "sample-sku-1")
    sample2 = next(row for row in result["facts"]["products"] if row["product_id"] == "sample-sku-2")
    assert sample["mature_count"] == 6
    assert sample2["mature_count"] == 2


def test_long_id_remains_str_and_counts_as_one_user(tmp_path):
    snapshot = load_json(SNAPSHOT_PATH)
    long_orders = [order for order in snapshot["orders"] if order["synthetic_user_id"] == "9007199254740993-fp"]
    assert long_orders and type(long_orders[0]["synthetic_user_id"]) is str
    result = compute(tmp_path, snapshot, days=30, name="long")
    assert result["facts"]["cohort_enrolled_count"] == 10


def test_window_includes_exact_n_and_excludes_plus_one_microsecond(tmp_path):
    first = datetime.fromisoformat("2026-06-30T00:00:00+08:00")
    exact = first + timedelta(days=30)
    later = exact + timedelta(microseconds=1)
    mappings = load_json(SNAPSHOT_PATH)["sku_mappings"]

    def one(second, name):
        snapshot = {
            "schema_version": "analytics-first-purchase-path/v1",
            "snapshot_id": "synthetic-first-purchase-path-v1",
            "data_version": "synthetic-first-purchase-path-data/v1",
            "as_of": AS_OF,
            "timezone": "Asia/Shanghai",
            "currency": "CNY",
            "amount_unit": "minor",
            "amount_precision": "integer_fen",
            "scope": "synthetic",
            "contains_real_data": False,
            "sku_mappings": mappings,
            "orders": [
                {"order_id": "f1", "synthetic_user_id": "u", "paid_at": first,
                 "channel": "A", "gross_paid_minor": 9100, "status": "PAID"},
                {"order_id": "f2", "synthetic_user_id": "u", "paid_at": second,
                 "channel": "A", "gross_paid_minor": 4300, "status": "PAID"},
            ],
            "lines": [
                {"line_id": "l1", "order_id": "f1", "synthetic_user_id": "u", "product_id": "sample-sku-1", "quantity": 1},
                {"line_id": "l2", "order_id": "f2", "synthetic_user_id": "u", "product_id": "full-sku-1", "quantity": 1},
            ],
            "refunds": [],
        }
        return compute(tmp_path, snapshot, days=30, name=name)

    included = one(exact, "n-exact")
    excluded = one(later, "n-plus")
    sample_in = next(row for row in included["facts"]["products"] if row["product_id"] == "sample-sku-1")
    sample_out = next(row for row in excluded["facts"]["products"] if row["product_id"] == "sample-sku-1")
    assert sample_in["subsequent_any_count"] == 1
    assert sample_in["sample_to_full_count"] == 1
    assert sample_out["subsequent_any_count"] == 0
    assert sample_out["sample_to_full_count"] == 0


def test_permission_scope_changes_hash_not_counts(tmp_path):
    snapshot = load_json(SNAPSHOT_PATH)
    left = compute(tmp_path, snapshot, days=30, scope="scope-a", name="scope-a")
    right = compute(tmp_path, snapshot, days=30, scope="scope-b", name="scope-b")
    assert left["facts"]["products"] == right["facts"]["products"]
    assert left["filter_hash"] != right["filter_hash"]


def test_input_permutation_keeps_digest_and_answers(tmp_path):
    original = load_json(SNAPSHOT_PATH)
    shuffled = deepcopy(original)
    shuffled["orders"] = list(reversed(shuffled["orders"]))
    shuffled["lines"] = list(reversed(shuffled["lines"]))
    shuffled["refunds"] = list(reversed(shuffled["refunds"]))
    assert snapshot_digest(original) == snapshot_digest(shuffled)
    left = compute(tmp_path, original, days=30, name="perm-a")
    right = compute(tmp_path, shuffled, days=30, name="perm-b")
    assert left["facts"] == right["facts"]
    assert left["resolved_filters"]["data_digest"] == right["resolved_filters"]["data_digest"]


def test_requested_missing_product_is_empty_mature_not_zero_ratio(tmp_path):
    result = compute(
        tmp_path, load_json(SNAPSHOT_PATH), days=30, product_ids=["ghost-sku"], name="ghost"
    )
    assert len(result["facts"]["products"]) == 1
    row = result["facts"]["products"][0]
    assert row["product_id"] == "ghost-sku"
    assert row["mature_count"] == 0
    assert row["subsequent_any_ratio"] is None
    assert row["empty_reason"] == EMPTY_MATURE_COHORT


def test_sql_and_unknown_fields_are_rejected():
    with pytest.raises(ValueError, match="unsupported request fields"):
        request = deepcopy(VALID_REQUEST)
        request["sql"] = "SELECT 1"
        execute_first_purchase_path(
            request=request,
            snapshot=load_json(SNAPSHOT_PATH),
            permission_scope=PERMISSION,
            fixture_directory="unused",
            temp_directory="unused",
        )
