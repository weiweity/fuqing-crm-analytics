"""Offline candidate handoff-audience compute. Production modules do not import this file."""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path

import pytest

from backend.semantic.analytics_handoff_audience import (
    EXPORT_STATUS,
    FAMILY_STATUS,
    QUERY_ID,
    RULE_VERSION,
    audience_digest,
    snapshot_digest,
)
from backend.services.analytics.catalog import (
    QUERY_FAMILIES,
    QueryFamilyStatus,
    UnsupportedQueryError,
    require_supported_query,
)
from backend.services.analytics.family_handoff_audience import execute_handoff_audience

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SNAPSHOT_PATH = FIXTURE_DIR / "handoff_audience_v1.json"
EXPECTED_PATH = FIXTURE_DIR / "handoff_audience_v1_expected.json"
PERMISSION = "synthetic-demo"

VALID_REQUEST = {
    "schema_version": "analytics-handoff-audience/v1",
    "query_id": "candidate_handoff_audience",
    "query_version": "handoff-audience-query/v1",
    "cohort_window": {"kind": "FIXED", "start_date": "2026-06-01", "end_date": "2026-09-01"},
    "observation_days": 30,
    "data_snapshot_ref": "synthetic-handoff-audience-v1",
    "timezone": "Asia/Shanghai",
    "first_channel": "A",
    "sample_product_id": "sample-sku-1",
    "mapping_version": "sample-full-map/v1",
    "rule_version": "handoff-audience-rule/v1",
    "source_result_ref": "synthetic-step:first_purchase_product_path:v1:succeeded",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def private_dir(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)
    return path


def request_for(sample_product_id="sample-sku-1") -> dict:
    payload = deepcopy(VALID_REQUEST)
    payload["sample_product_id"] = sample_product_id
    return payload


def compute(tmp_path: Path, snapshot, sample_product_id="sample-sku-1", scope=PERMISSION, name="run"):
    return execute_handoff_audience(
        request=request_for(sample_product_id),
        snapshot=snapshot,
        permission_scope=scope,
        fixture_directory=private_dir(tmp_path, f"{name}-db"),
        temp_directory=private_dir(tmp_path, f"{name}-tmp"),
    )


def test_expected_fixture_is_hand_calculated_not_dumped():
    expected = load_json(EXPECTED_PATH)
    text = EXPECTED_PATH.read_text(encoding="utf-8")
    assert expected["method"] == "hand_calculated"
    assert expected["computation"] == "NOT_RUN"
    assert expected["not_generated_from_sql"] is True
    assert "dump" not in text.lower()
    assert expected["fixture_id"] != "synthetic-channel-followup-v1"
    assert expected["cohort_count"] == 2
    assert expected["notes"]["not_draft_export"] is True
    assert hashlib.sha256(expected["digest_canonical"].encode("utf-8")).hexdigest() == expected["cohort_digest"]
    empty = expected["empty_sample_sku_2"]
    assert hashlib.sha256(empty["digest_canonical"].encode("utf-8")).hexdigest() == empty["cohort_digest"]
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


def test_catalog_stays_deferred_and_family_source_skips_supported_path():
    family_path = Path(__file__).resolve().parents[1] / "services/analytics/family_handoff_audience.py"
    semantic_path = Path(__file__).resolve().parents[1] / "semantic/analytics_handoff_audience.py"
    imported = _imported_names(family_path) | _imported_names(semantic_path)
    assert "require_supported_query" not in imported
    assert "ChannelFollowupResult" not in imported
    assert "backend.services.analytics.catalog" not in imported
    assert EXPORT_STATUS == "NOT_DRAFT_EXPORT"
    assert QUERY_FAMILIES[QUERY_ID].status is QueryFamilyStatus.DEFERRED
    assert FAMILY_STATUS == "DEFERRED"
    with pytest.raises(UnsupportedQueryError, match="DEFERRED"):
        require_supported_query(QUERY_ID)


def test_golden_members_match_hand_digest_without_leaking_ids(tmp_path):
    expected = load_json(EXPECTED_PATH)
    result = compute(tmp_path, load_json(SNAPSHOT_PATH), name="gold")
    facts = result["facts"]
    assert result["query_id"] == QUERY_ID
    assert facts["cohort_count"] == expected["cohort_count"]
    assert facts["cohort_digest"] == expected["cohort_digest"]
    assert facts["audience_kind"] == "READ_ONLY_DEFINITION"
    assert facts["export_status"] == "NOT_DRAFT_EXPORT"
    assert facts["marketing_sent"] is False
    assert facts["source_result_ref"] == VALID_REQUEST["source_result_ref"]
    dumped = json.dumps(result)
    assert "members" not in facts
    assert "synthetic_user_ids" not in facts
    for user_id in expected["members_for_digest_only"]:
        assert user_id not in dumped
        assert type(user_id) is str
    assert any("不发送营销" in item for item in result["limitations"])
    assert any("DRAFT_EXPORT" in item for item in result["limitations"])


def test_empty_audience_count_is_zero_and_digest_is_stable(tmp_path):
    expected = load_json(EXPECTED_PATH)["empty_sample_sku_2"]
    result = compute(
        tmp_path, load_json(SNAPSHOT_PATH), sample_product_id="sample-sku-2", name="empty"
    )
    facts = result["facts"]
    assert facts["cohort_count"] == 0
    assert facts["cohort_digest"] == expected["cohort_digest"]
    assert facts["cohort_digest"] == audience_digest([], RULE_VERSION)
    again = compute(
        tmp_path, load_json(SNAPSHOT_PATH), sample_product_id="sample-sku-2", name="empty2"
    )
    assert again["facts"]["cohort_digest"] == facts["cohort_digest"]


def test_rule_version_is_part_of_hand_digest():
    expected = load_json(EXPECTED_PATH)
    members = expected["members_for_digest_only"]
    assert audience_digest(members, RULE_VERSION) == expected["cohort_digest"]
    assert audience_digest(list(reversed(members)), RULE_VERSION) == expected["cohort_digest"]
    assert audience_digest(members, "handoff-audience-rule/v2") != expected["cohort_digest"]


def test_input_permutation_keeps_digest(tmp_path):
    original = load_json(SNAPSHOT_PATH)
    shuffled = deepcopy(original)
    shuffled["orders"] = list(reversed(shuffled["orders"]))
    shuffled["lines"] = list(reversed(shuffled["lines"]))
    shuffled["refunds"] = list(reversed(shuffled["refunds"]))
    assert snapshot_digest(original) == snapshot_digest(shuffled)
    left = compute(tmp_path, original, name="perm-a")
    right = compute(tmp_path, shuffled, name="perm-b")
    assert left["facts"]["cohort_count"] == right["facts"]["cohort_count"]
    assert left["facts"]["cohort_digest"] == right["facts"]["cohort_digest"]


def test_permission_scope_changes_hash_not_digest(tmp_path):
    snapshot = load_json(SNAPSHOT_PATH)
    left = compute(tmp_path, snapshot, scope="scope-a", name="scope-a")
    right = compute(tmp_path, snapshot, scope="scope-b", name="scope-b")
    assert left["facts"]["cohort_digest"] == right["facts"]["cohort_digest"]
    assert left["filter_hash"] != right["filter_hash"]


def test_long_id_in_canonical_is_string():
    expected = load_json(EXPECTED_PATH)
    assert expected["members_for_digest_only"][0] == "ha-0009007199254741000"
    assert type(expected["members_for_digest_only"][0]) is str
    assert expected["digest_canonical"].startswith('{"members":["ha-0009007199254741000","ha-1"]')


def test_sql_and_unknown_fields_are_rejected():
    request = deepcopy(VALID_REQUEST)
    request["sql"] = "SELECT 1"
    with pytest.raises(ValueError, match="unsupported request fields"):
        execute_handoff_audience(
            request=request,
            snapshot=load_json(SNAPSHOT_PATH),
            permission_scope=PERMISSION,
            fixture_directory="unused",
            temp_directory="unused",
        )
