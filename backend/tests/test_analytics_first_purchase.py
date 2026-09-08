"""Offline first-purchase JSON compute. Production modules do not import this file."""

from __future__ import annotations

import ast
import json
from copy import deepcopy
from pathlib import Path

from backend.contracts.analytics_first_purchase import snapshot_digest
from backend.services.analytics.first_purchase import execute_first_purchase_path_query

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SNAPSHOT_PATH = FIXTURE_DIR / "analytics_first_purchase_v1.json"
EXPECTED_PATH = FIXTURE_DIR / "analytics_first_purchase_v1_expected.json"
MUTATED_SNAPSHOT_PATH = FIXTURE_DIR / "analytics_first_purchase_v1_mutated.json"
MUTATED_EXPECTED_PATH = FIXTURE_DIR / "analytics_first_purchase_v1_mutated_expected.json"
MISSING_SNAPSHOT_PATH = FIXTURE_DIR / "analytics_first_purchase_v1_missing_role.json"
MISSING_EXPECTED_PATH = FIXTURE_DIR / "analytics_first_purchase_v1_missing_role_expected.json"

FAMILY_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def compute(snapshot: dict, expected: dict, *, days=None, scope=None) -> dict:
    request = deepcopy(expected["request"])
    if days is not None:
        request["observation_days"] = days
    return execute_first_purchase_path_query(
        request=request,
        snapshot=snapshot,
        permission_scope=scope or expected["permission_scope"],
    )


def test_expected_fixture_is_hand_calculated_not_channel_golden():
    expected = load_json(EXPECTED_PATH)
    text = EXPECTED_PATH.read_text(encoding="utf-8")
    assert expected["method"] == "hand_calculated"
    assert expected["hand_calculated"] is True
    assert expected["computation"] == "NOT_RUN"
    assert expected["fixture_id"] != "synthetic-channel-followup-v1"
    assert "110000" not in text
    assert "87000" not in text
    assert "25%" not in text
    assert "0.25" not in text


def test_family_modules_are_json_only():
    names = set()
    for path in (
        FAMILY_ROOT / "contracts/analytics_first_purchase.py",
        FAMILY_ROOT / "services/analytics/first_purchase/compute.py",
        FAMILY_ROOT / "services/analytics/first_purchase/__init__.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".", 1)[0])
                names.add(node.module)
    assert "duckdb" not in names
    assert "backend.services.analytics.catalog" not in names
    assert "backend.services.analytics.queries" not in names
    assert "backend.services.analytics.warehouse" not in names


def test_shipped_compute_equals_hand_expected_snapshot():
    expected = load_json(EXPECTED_PATH)
    result = compute(load_json(SNAPSHOT_PATH), expected)
    assert result == expected["result"]


def test_window_facts_equal_hand_expected():
    expected = load_json(EXPECTED_PATH)
    snapshot = load_json(SNAPSHOT_PATH)
    for days, facts in expected["windows"].items():
        result = compute(snapshot, expected, days=int(days))
        assert result["facts"] == facts
        assert result["status"] == expected["result"]["status"]


def test_mutated_input_changes_answer_and_digest():
    expected = load_json(EXPECTED_PATH)
    mutated_expected = load_json(MUTATED_EXPECTED_PATH)
    baseline = compute(load_json(SNAPSHOT_PATH), expected)
    mutated = compute(load_json(MUTATED_SNAPSHOT_PATH), mutated_expected)
    assert mutated == mutated_expected["result"]
    assert snapshot_digest(load_json(MUTATED_SNAPSHOT_PATH)) != snapshot_digest(load_json(SNAPSHOT_PATH))
    assert mutated["resolved_filters"]["data_digest"] != baseline["resolved_filters"]["data_digest"]
    assert mutated["facts"] != baseline["facts"]
    assert mutated["filter_hash"] != baseline["filter_hash"]


def test_missing_product_role_rejects_without_conversion_ratio():
    expected = load_json(MISSING_EXPECTED_PATH)
    result = compute(load_json(MISSING_SNAPSHOT_PATH), expected)
    assert result == expected["result"]
    assert result["facts"] is None
    dumped = json.dumps(result)
    assert "finished_conversion_ratio" not in dumped
    assert "finished_conversion_count" not in dumped
    assert result["status"] == expected["result"]["status"]
    assert result["reason_code"] == expected["result"]["reason_code"]
    assert result["missing_product_ids"] == expected["result"]["missing_product_ids"]


def test_permission_scope_changes_hash_not_counts():
    expected = load_json(EXPECTED_PATH)
    snapshot = load_json(SNAPSHOT_PATH)
    left = compute(snapshot, expected)
    right = compute(snapshot, expected, scope="other-scope")
    assert left["facts"] == right["facts"]
    assert left["filter_hash"] != right["filter_hash"]
    assert left["resolved_filters"]["permission_scope"] != right["resolved_filters"]["permission_scope"]


def test_input_permutation_keeps_digest_and_answers():
    expected = load_json(EXPECTED_PATH)
    original = load_json(SNAPSHOT_PATH)
    shuffled = deepcopy(original)
    shuffled["orders"] = list(reversed(shuffled["orders"]))
    shuffled["lines"] = list(reversed(shuffled["lines"]))
    shuffled["refunds"] = list(reversed(shuffled["refunds"]))
    shuffled["product_roles"] = list(reversed(shuffled["product_roles"]))
    assert snapshot_digest(original) == snapshot_digest(shuffled)
    left = compute(original, expected)
    right = compute(shuffled, expected)
    assert left == right
