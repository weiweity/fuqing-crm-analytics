"""Offline channel-follow-up compute. Production modules do not import this file."""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest
from pydantic import ValidationError

from backend.analytics_fixture import MAX_DATABASE_BYTES, bounded_bytes
from backend.analytics_query_fixture import (
    DATABASE_NAME,
    MANIFEST_NAME,
    MAX_ORDERS,
    QUERY_DUCKDB_MEMORY_MIB,
    QUERY_DUCKDB_THREADS,
    QUERY_TEMP_MIB,
    ChannelFollowupFixture,
    connect_channel_followup_readonly,
    create_channel_followup_fixture,
)
from backend.contracts.analytics_query import (
    QUERY_SCHEMA,
    ChannelFollowupQueryRequest,
    ChannelFollowupSnapshot,
    snapshot_digest,
)
from backend.semantic.analytics_channel_followup import LIMITATIONS, channel_followup_query
from backend.services.analytics.catalog import bind_resolved_filters
from backend.services.analytics.queries import execute_channel_followup_query

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SNAPSHOT_PATH = FIXTURE_DIR / "analytics_channel_followup_v1.json"
EXPECTED_PATH = FIXTURE_DIR / "analytics_channel_followup_v1_expected.json"
PERMISSION = "synthetic-demo"
AS_OF = "2026-09-01T00:00:00+08:00"

VALID_REQUEST = {
    "schema_version": QUERY_SCHEMA,
    "query_id": "channel_first_observed_followup",
    "query_version": "channel-followup-query/v1",
    "metric_id": "channel_first_observed_n_day_repeat",
    "metric_version": "channel-followup-metric/v1",
    "cohort_window": {"kind": "FIXED", "start_date": "2026-06-01", "end_date": "2026-09-01"},
    "observation_days": 30,
    "data_snapshot_ref": "synthetic-channel-followup-v1",
    "timezone": "Asia/Shanghai",
    "channel_ids": [],
    "cohort_ref": None,
    "product_ids": [],
    "exclude_low_price": False,
    "comparison": None,
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def golden_snapshot() -> ChannelFollowupSnapshot:
    return ChannelFollowupSnapshot.model_validate(load_json(SNAPSHOT_PATH))


def request_for(days: int, channel_ids=None) -> ChannelFollowupQueryRequest:
    payload = deepcopy(VALID_REQUEST)
    payload["observation_days"] = days
    if channel_ids is not None:
        payload["channel_ids"] = channel_ids
    return ChannelFollowupQueryRequest.model_validate(payload)


def private_dir(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)
    return path


def compute(tmp_path: Path, snapshot, days=30, channel_ids=None, scope=PERMISSION, name="run"):
    fixture = create_channel_followup_fixture(private_dir(tmp_path, f"{name}-db"), snapshot)
    temp = private_dir(tmp_path, f"{name}-tmp")
    connection = connect_channel_followup_readonly(fixture, temp)
    try:
        result = execute_channel_followup_query(
            request=request_for(days, channel_ids),
            permission_scope=scope,
            fixture=fixture,
            connection=connection,
        )
        return result, fixture
    finally:
        connection.close()


def tiny_snapshot(*, orders, lines, refunds=None, as_of=AS_OF):
    return ChannelFollowupSnapshot.model_validate({
        "schema_version": QUERY_SCHEMA,
        "snapshot_id": "synthetic-channel-followup-v1",
        "data_version": "synthetic-channel-followup-data/v1",
        "as_of": as_of,
        "timezone": "Asia/Shanghai",
        "currency": "CNY",
        "amount_unit": "minor",
        "amount_precision": "integer_fen",
        "scope": "synthetic",
        "contains_real_data": False,
        "orders": orders,
        "lines": lines,
        "refunds": refunds or [],
    })


def counts(row) -> tuple:
    return (
        row.channel_mature_cohort_count,
        row.channel_immature_count,
        row.channel_repeat_count,
        row.channel_cross_channel_count,
        row.channel_window_net_paid_minor,
        row.channel_empty_reason,
    )


@pytest.mark.parametrize("days", [30, 60, 90])
def test_golden_windows_match_hand_expected_field_by_field(tmp_path, days):
    result, fixture = compute(tmp_path, golden_snapshot(), days=days, name=f"g{days}")
    expected = load_json(EXPECTED_PATH)["windows"][str(days)]
    assert result.facts.observation_days == days
    assert result.contains_real_data is False
    assert result.data_source == "SYNTHETIC_SNAPSHOT"
    assert result.filter_hash == result.resolved_filters.filter_hash
    assert result.resolved_filters.permission_scope == PERMISSION
    assert result.resolved_filters.data_digest == snapshot_digest(golden_snapshot())
    assert result.resolved_filters.data_digest == fixture.manifest()["data_digest"]
    assert fixture.physical_sha256() == fixture.manifest()["database_sha256"]
    assert result.resolved_filters.data_digest != fixture.physical_sha256()
    for index, channel in enumerate(expected["channels"]):
        actual = result.facts.channels[index].model_dump()
        for key, value in channel.items():
            assert actual[key] == value, (days, channel["channel_id"], key, actual[key], value)
    totals = result.facts.totals.model_dump()
    for key, value in expected["totals"].items():
        assert totals[key] == value, (days, key, totals[key], value)
    dumped = result.facts.model_dump()
    for banned in ("user_ids", "order_ids", "synthetic_user_ids", "members"):
        assert banned not in dumped


def test_moving_b02_into_n30_matches_original_n60_hand_values(tmp_path):
    payload = golden_snapshot().model_dump(mode="python")
    for order in payload["orders"]:
        if order["order_id"] == "b02" and order["synthetic_user_id"] == "b":
            order["paid_at"] = datetime.fromisoformat("2026-06-30T00:00:00+08:00")
    result, _fixture = compute(tmp_path, ChannelFollowupSnapshot.model_validate(payload), days=30, name="b02")
    assert counts(result.facts.channels[0]) == (7, 1, 5, 4, 92000, None)
    assert counts(result.facts.channels[1]) == (2, 0, 1, 0, 23000, None)
    assert counts(result.facts.totals) == (9, 1, 6, 4, 115000, None)


def test_delaying_f02_one_microsecond_drops_n30_repeat(tmp_path):
    payload = golden_snapshot().model_dump(mode="python")
    for order in payload["orders"]:
        if order["order_id"] == "f02" and order["synthetic_user_id"] == "f":
            order["paid_at"] = order["paid_at"] + timedelta(microseconds=1)
    result, _fixture = compute(tmp_path, ChannelFollowupSnapshot.model_validate(payload), days=30, name="f02")
    assert counts(result.facts.channels[0])[:4] == (7, 1, 3, 3)
    assert result.facts.channels[0].channel_window_net_paid_minor == 82000
    assert counts(result.facts.totals)[:4] == (9, 1, 4, 3)
    assert result.facts.totals.channel_window_net_paid_minor == 105000


def test_channel_a_filter_still_counts_later_b_as_cross(tmp_path):
    result, _fixture = compute(tmp_path, golden_snapshot(), days=30, channel_ids=["A"], name="only-a")
    assert [row.channel_id for row in result.facts.channels] == ["A"]
    assert result.facts.channels[0].channel_cross_channel_count == 3
    assert counts(result.facts.totals) == counts(result.facts.channels[0])


def test_full_partial_and_future_refunds(tmp_path):
    first = "2026-06-01T00:00:00+08:00"
    second = "2026-06-10T00:00:00+08:00"
    snapshot = tiny_snapshot(
        orders=[
            {"order_id": "full", "synthetic_user_id": "u1", "paid_at": first, "channel": "A",
             "gross_paid_minor": 10000, "status": "PAID"},
            {"order_id": "full-2", "synthetic_user_id": "u1", "paid_at": second, "channel": "B",
             "gross_paid_minor": 8000, "status": "PAID"},
            {"order_id": "part", "synthetic_user_id": "u2", "paid_at": first, "channel": "A",
             "gross_paid_minor": 10000, "status": "PAID"},
            {"order_id": "future", "synthetic_user_id": "u3", "paid_at": first, "channel": "B",
             "gross_paid_minor": 10000, "status": "PAID"},
        ],
        lines=[
            {"line_id": "l1", "order_id": "full", "synthetic_user_id": "u1", "product_id": "p", "quantity": 1},
            {"line_id": "l2", "order_id": "full-2", "synthetic_user_id": "u1", "product_id": "p", "quantity": 1},
            {"line_id": "l3", "order_id": "part", "synthetic_user_id": "u2", "product_id": "p", "quantity": 1},
            {"line_id": "l4", "order_id": "future", "synthetic_user_id": "u3", "product_id": "p", "quantity": 1},
        ],
        refunds=[
            {"refund_id": "r-full", "order_id": "full", "synthetic_user_id": "u1",
             "refunded_at": "2026-06-02T00:00:00+08:00", "refund_minor": 10000},
            {"refund_id": "r-part", "order_id": "part", "synthetic_user_id": "u2",
             "refunded_at": "2026-06-02T00:00:00+08:00", "refund_minor": 3000},
            {"refund_id": "r-future", "order_id": "future", "synthetic_user_id": "u3",
             "refunded_at": "2026-09-02T00:00:00+08:00", "refund_minor": 10000},
        ],
    )
    result, _fixture = compute(tmp_path, snapshot, days=30, name="refunds")
    # u1 first becomes full-2 on B (full refund of A first). u2 first A net 7000. u3 first B still 10000.
    assert counts(result.facts.channels[0]) == (1, 0, 0, 0, 7000, None)
    assert counts(result.facts.channels[1]) == (2, 0, 0, 0, 18000, None)


def test_multiline_first_order_does_not_duplicate_payment(tmp_path):
    snapshot = tiny_snapshot(
        orders=[{"order_id": "o1", "synthetic_user_id": "u", "paid_at": "2026-06-01T00:00:00+08:00",
                 "channel": "A", "gross_paid_minor": 10000, "status": "PAID"}],
        lines=[
            {"line_id": "l1", "order_id": "o1", "synthetic_user_id": "u", "product_id": "a", "quantity": 1},
            {"line_id": "l2", "order_id": "o1", "synthetic_user_id": "u", "product_id": "b", "quantity": 2},
        ],
    )
    result, _fixture = compute(tmp_path, snapshot, days=30, name="lines")
    assert result.facts.channels[0].channel_window_net_paid_minor == 10000
    assert result.facts.channels[0].channel_mature_cohort_count == 1


def test_first_purchase_before_cohort_is_excluded(tmp_path):
    snapshot = tiny_snapshot(
        orders=[
            {"order_id": "early", "synthetic_user_id": "u", "paid_at": "2026-05-31T00:00:00+08:00",
             "channel": "A", "gross_paid_minor": 10000, "status": "PAID"},
            {"order_id": "in", "synthetic_user_id": "u", "paid_at": "2026-06-10T00:00:00+08:00",
             "channel": "B", "gross_paid_minor": 8000, "status": "PAID"},
        ],
        lines=[
            {"line_id": "l1", "order_id": "early", "synthetic_user_id": "u", "product_id": "p", "quantity": 1},
            {"line_id": "l2", "order_id": "in", "synthetic_user_id": "u", "product_id": "p", "quantity": 1},
        ],
    )
    result, _fixture = compute(tmp_path, snapshot, days=30, name="pre")
    assert counts(result.facts.totals) == (0, 0, 0, 0, None, "EMPTY_MATURE_COHORT")


def test_same_time_orders_use_order_id_as_second(tmp_path):
    paid = "2026-06-04T00:00:00+08:00"
    snapshot = tiny_snapshot(
        orders=[
            {"order_id": "e02", "synthetic_user_id": "u", "paid_at": paid, "channel": "B",
             "gross_paid_minor": 2000, "status": "PAID"},
            {"order_id": "e01", "synthetic_user_id": "u", "paid_at": paid, "channel": "A",
             "gross_paid_minor": 10000, "status": "PAID"},
        ],
        lines=[
            {"line_id": "l1", "order_id": "e01", "synthetic_user_id": "u", "product_id": "p", "quantity": 1},
            {"line_id": "l2", "order_id": "e02", "synthetic_user_id": "u", "product_id": "p", "quantity": 1},
        ],
    )
    result, _fixture = compute(tmp_path, snapshot, days=30, name="same")
    assert counts(result.facts.channels[0]) == (1, 0, 1, 1, 12000, None)
    assert counts(result.facts.channels[1]) == (0, 0, 0, 0, None, "EMPTY_MATURE_COHORT")


def test_window_includes_exact_n_and_excludes_n_plus_one_microsecond(tmp_path):
    first = datetime.fromisoformat("2026-06-30T00:00:00+08:00")
    exact = first + timedelta(days=30)
    later = exact + timedelta(microseconds=1)
    base_orders = [
        {"order_id": "f1", "synthetic_user_id": "u", "paid_at": first, "channel": "A",
         "gross_paid_minor": 10000, "status": "PAID"},
        {"order_id": "f2", "synthetic_user_id": "u", "paid_at": exact, "channel": "A",
         "gross_paid_minor": 5000, "status": "PAID"},
    ]
    lines = [
        {"line_id": "l1", "order_id": "f1", "synthetic_user_id": "u", "product_id": "p", "quantity": 1},
        {"line_id": "l2", "order_id": "f2", "synthetic_user_id": "u", "product_id": "p", "quantity": 1},
    ]
    included, _ = compute(tmp_path, tiny_snapshot(orders=base_orders, lines=lines), days=30, name="n-exact")
    assert included.facts.channels[0].channel_repeat_count == 1
    assert included.facts.channels[0].channel_window_net_paid_minor == 15000
    over = deepcopy(base_orders)
    over[1]["paid_at"] = later
    excluded, _ = compute(tmp_path, tiny_snapshot(orders=over, lines=lines), days=30, name="n-plus")
    assert excluded.facts.channels[0].channel_repeat_count == 0
    assert excluded.facts.channels[0].channel_window_net_paid_minor == 10000


def test_maturity_includes_exact_cutoff_and_excludes_one_microsecond_late(tmp_path):
    as_of = datetime.fromisoformat(AS_OF)
    exact = as_of - timedelta(days=30)
    late = exact + timedelta(microseconds=1)
    def one(first, name):
        snapshot = tiny_snapshot(orders=[{
            "order_id": "o1", "synthetic_user_id": "u", "paid_at": first, "channel": "A",
            "gross_paid_minor": 10000, "status": "PAID",
        }], lines=[{"line_id": "l1", "order_id": "o1", "synthetic_user_id": "u", "product_id": "p", "quantity": 1}])
        return compute(tmp_path, snapshot, days=30, name=name)[0]
    mature = one(exact, "mat-exact")
    immature = one(late, "mat-late")
    assert mature.facts.channels[0].channel_mature_cohort_count == 1
    assert immature.facts.channels[0].channel_immature_count == 1
    assert immature.facts.channels[0].channel_mature_cohort_count == 0
    assert immature.facts.channels[0].channel_empty_reason == "EMPTY_MATURE_COHORT"
    assert immature.facts.channels[0].channel_repeat_ratio is None


def test_immature_repeat_is_excluded_from_denominator(tmp_path):
    snapshot = tiny_snapshot(
        orders=[
            {"order_id": "g1", "synthetic_user_id": "u", "paid_at": "2026-08-20T00:00:00+08:00",
             "channel": "A", "gross_paid_minor": 10000, "status": "PAID"},
            {"order_id": "g2", "synthetic_user_id": "u", "paid_at": "2026-08-21T00:00:00+08:00",
             "channel": "B", "gross_paid_minor": 5000, "status": "PAID"},
        ],
        lines=[
            {"line_id": "l1", "order_id": "g1", "synthetic_user_id": "u", "product_id": "p", "quantity": 1},
            {"line_id": "l2", "order_id": "g2", "synthetic_user_id": "u", "product_id": "p", "quantity": 1},
        ],
    )
    result, _ = compute(tmp_path, snapshot, days=30, name="immature")
    assert counts(result.facts.channels[0]) == (0, 1, 0, 0, None, "EMPTY_MATURE_COHORT")


def test_two_users_sharing_order_id_are_not_merged(tmp_path):
    snapshot = tiny_snapshot(
        orders=[
            {"order_id": "shared-1", "synthetic_user_id": "u-1", "paid_at": "2026-06-01T00:00:00+08:00",
             "channel": "A", "gross_paid_minor": 10000, "status": "PAID"},
            {"order_id": "shared-1", "synthetic_user_id": "u-2", "paid_at": "2026-06-02T00:00:00+08:00",
             "channel": "B", "gross_paid_minor": 8000, "status": "PAID"},
        ],
        lines=[
            {"line_id": "l1", "order_id": "shared-1", "synthetic_user_id": "u-1", "product_id": "p", "quantity": 1},
            {"line_id": "l2", "order_id": "shared-1", "synthetic_user_id": "u-2", "product_id": "p", "quantity": 1},
        ],
    )
    result, _ = compute(tmp_path, snapshot, days=30, name="shared")
    assert result.facts.channels[0].channel_window_net_paid_minor == 10000
    assert result.facts.channels[1].channel_window_net_paid_minor == 8000
    assert result.facts.totals.channel_mature_cohort_count == 2


def test_long_id_user_from_golden_is_channel_b(tmp_path):
    result, _ = compute(tmp_path, golden_snapshot(), days=30, name="long")
    assert result.facts.channels[1].channel_repeat_count == 1
    assert result.facts.channels[1].channel_window_net_paid_minor == 23000


def test_input_permutation_keeps_digest_and_answers(tmp_path):
    original = golden_snapshot()
    shuffled_payload = original.model_dump(mode="json")
    shuffled_payload["orders"] = list(reversed(shuffled_payload["orders"]))
    shuffled_payload["lines"] = list(reversed(shuffled_payload["lines"]))
    shuffled_payload["refunds"] = list(reversed(shuffled_payload["refunds"]))
    shuffled = ChannelFollowupSnapshot.model_validate(shuffled_payload)
    assert snapshot_digest(original) == snapshot_digest(shuffled)
    left, left_fix = compute(tmp_path, original, days=30, name="perm-a")
    right, right_fix = compute(tmp_path, shuffled, days=30, name="perm-b")
    assert left.facts == right.facts
    assert left.resolved_filters.data_digest == right.resolved_filters.data_digest
    assert left_fix.physical_sha256() != "" and right_fix.physical_sha256() != ""


def test_permission_scope_changes_hash_not_counts(tmp_path):
    snap = golden_snapshot()
    left, _ = compute(tmp_path, snap, days=30, scope="scope-a", name="scope-a")
    right, _ = compute(tmp_path, snap, days=30, scope="scope-b", name="scope-b")
    assert left.facts.totals == right.facts.totals
    assert left.filter_hash != right.filter_hash
    assert left.resolved_filters.permission_scope == "scope-a"


def test_sql_and_path_inputs_are_rejected():
    with pytest.raises(ValidationError):
        ChannelFollowupQueryRequest.model_validate({**VALID_REQUEST, "sql": "SELECT 1"})
    with pytest.raises(ValidationError):
        ChannelFollowupQueryRequest.model_validate({**VALID_REQUEST, "database": "/tmp/db"})
    sql, params = channel_followup_query()
    assert "?" in sql and "SELECT" in sql.upper()
    assert params[-1] == "channel_ids"


def test_over_cap_and_non_empty_directory_fail_closed(tmp_path):
    occupied = private_dir(tmp_path, "occupied")
    (occupied / "marker").write_text("x")
    with pytest.raises(ValueError, match="empty directory"):
        create_channel_followup_fixture(occupied, golden_snapshot())
    payload = tiny_snapshot(
        orders=[{"order_id": "o1", "synthetic_user_id": "u", "paid_at": "2026-06-01T00:00:00+08:00",
                 "channel": "A", "gross_paid_minor": 1, "status": "PAID"}],
        lines=[{"line_id": "l1", "order_id": "o1", "synthetic_user_id": "u", "product_id": "p", "quantity": 1}],
    ).model_dump(mode="python")
    payload["orders"] = [
        {**payload["orders"][0], "order_id": f"o{i}", "synthetic_user_id": f"u{i}"}
        for i in range(MAX_ORDERS + 1)
    ]
    payload["lines"] = [
        {"line_id": f"l{i}", "order_id": f"o{i}", "synthetic_user_id": f"u{i}", "product_id": "p", "quantity": 1}
        for i in range(MAX_ORDERS + 1)
    ]
    with pytest.raises((ValidationError, ValueError)):
        create_channel_followup_fixture(private_dir(tmp_path, "cap"), ChannelFollowupSnapshot.model_validate(payload))


def _reseal(directory: Path) -> ChannelFollowupFixture:
    database = directory / DATABASE_NAME
    os.chmod(database, 0o600)
    manifest_path = directory / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text())
    manifest["database_sha256"] = hashlib.sha256(bounded_bytes(database, MAX_DATABASE_BYTES)).hexdigest()
    raw = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    manifest_path.write_bytes(raw)
    os.chmod(manifest_path, 0o600)
    os.chmod(database, 0o600)
    return ChannelFollowupFixture(str(directory), hashlib.sha256(raw).hexdigest())


def test_tamper_unknown_table_column_and_digest_fail_closed(tmp_path):
    fixture = create_channel_followup_fixture(private_dir(tmp_path, "seal"), golden_snapshot())
    directory = Path(fixture.directory)
    temp = private_dir(tmp_path, "seal-tmp")

    with (directory / MANIFEST_NAME).open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError):
        ChannelFollowupFixture(str(directory), fixture.manifest_sha256).validate()

    fixture = create_channel_followup_fixture(private_dir(tmp_path, "seal2"), golden_snapshot())
    directory = Path(fixture.directory)
    writer = duckdb.connect(str(directory / DATABASE_NAME), config={"enable_external_access": False})
    try:
        writer.execute("CREATE TABLE evil (x INTEGER)")
        writer.execute("CHECKPOINT")
    finally:
        writer.close()
    tampered = _reseal(directory)
    tampered.validate()
    connection = connect_channel_followup_readonly(tampered, temp)
    try:
        with pytest.raises(ValueError, match="tables"):
            execute_channel_followup_query(
                request=request_for(30), permission_scope=PERMISSION, fixture=tampered, connection=connection,
            )
    finally:
        connection.close()

    fixture = create_channel_followup_fixture(private_dir(tmp_path, "seal3"), golden_snapshot())
    directory = Path(fixture.directory)
    writer = duckdb.connect(str(directory / DATABASE_NAME), config={"enable_external_access": False})
    try:
        writer.execute("ALTER TABLE channel_followup_orders ADD COLUMN extra INTEGER")
        writer.execute("CHECKPOINT")
    finally:
        writer.close()
    tampered = _reseal(directory)
    connection = connect_channel_followup_readonly(tampered, private_dir(tmp_path, "seal3-tmp"))
    try:
        with pytest.raises(ValueError, match="columns"):
            execute_channel_followup_query(
                request=request_for(30), permission_scope=PERMISSION, fixture=tampered, connection=connection,
            )
    finally:
        connection.close()

    fixture = create_channel_followup_fixture(private_dir(tmp_path, "seal4"), golden_snapshot())
    directory = Path(fixture.directory)
    writer = duckdb.connect(str(directory / DATABASE_NAME), config={"enable_external_access": False})
    try:
        writer.execute("UPDATE channel_followup_orders SET gross_paid_minor = gross_paid_minor + 1 WHERE order_id = 'a01'")
        writer.execute("CHECKPOINT")
    finally:
        writer.close()
    tampered = _reseal(directory)
    connection = connect_channel_followup_readonly(tampered, private_dir(tmp_path, "seal4-tmp"))
    try:
        with pytest.raises(ValueError, match="digest"):
            execute_channel_followup_query(
                request=request_for(30), permission_scope=PERMISSION, fixture=tampered, connection=connection,
            )
    finally:
        connection.close()


def test_readonly_settings_persistence_and_close(tmp_path):
    snapshot = golden_snapshot()
    fixture = create_channel_followup_fixture(private_dir(tmp_path, "persist"), snapshot)
    before = fixture.physical_sha256()
    temp = private_dir(tmp_path, "persist-tmp")
    connection = connect_channel_followup_readonly(fixture, temp)
    try:
        settings = dict(connection.execute(
            "SELECT name, value FROM duckdb_settings() WHERE name IN (?, ?, ?, ?)",
            ["access_mode", "enable_external_access", "lock_configuration", "default_collation"],
        ).fetchall())
        assert settings["access_mode"].lower() == "read_only"
        assert settings["enable_external_access"] == "false"
        assert settings["lock_configuration"] == "true"
        assert str(settings["default_collation"]).lower() in ("", "c")
        first = execute_channel_followup_query(
            request=request_for(30), permission_scope=PERMISSION, fixture=fixture, connection=connection,
        )
    finally:
        connection.close()
    with pytest.raises(Exception):
        connection.execute("SELECT 1")
    assert fixture.physical_sha256() == before
    reopened = connect_channel_followup_readonly(fixture, private_dir(tmp_path, "persist-tmp2"))
    try:
        second = execute_channel_followup_query(
            request=request_for(30), permission_scope=PERMISSION, fixture=fixture, connection=reopened,
        )
        assert second.facts == first.facts
        assert fixture.physical_sha256() == before
    finally:
        reopened.close()


def test_same_time_ascii_order_prefers_z_over_lowercase_a(tmp_path):
    paid = "2026-06-01T00:00:00+08:00"
    snapshot = tiny_snapshot(
        orders=[
            {"order_id": "Z", "synthetic_user_id": "u", "paid_at": paid, "channel": "A",
             "gross_paid_minor": 10000, "status": "PAID"},
            {"order_id": "a", "synthetic_user_id": "u", "paid_at": paid, "channel": "B",
             "gross_paid_minor": 2000, "status": "PAID"},
        ],
        lines=[
            {"line_id": "l1", "order_id": "Z", "synthetic_user_id": "u", "product_id": "p", "quantity": 1},
            {"line_id": "l2", "order_id": "a", "synthetic_user_id": "u", "product_id": "p", "quantity": 1},
        ],
    )
    result, _ = compute(tmp_path, snapshot, days=30, name="ascii-z")
    assert counts(result.facts.channels[0]) == (1, 0, 1, 1, 12000, None)
    assert counts(result.facts.channels[1]) == (0, 0, 0, 0, None, "EMPTY_MATURE_COHORT")


def test_distinct_case_users_are_not_merged(tmp_path):
    snapshot = tiny_snapshot(
        orders=[
            {"order_id": "o1", "synthetic_user_id": "u", "paid_at": "2026-06-01T00:00:00+08:00",
             "channel": "A", "gross_paid_minor": 10000, "status": "PAID"},
            {"order_id": "o1", "synthetic_user_id": "U", "paid_at": "2026-06-02T00:00:00+08:00",
             "channel": "B", "gross_paid_minor": 8000, "status": "PAID"},
        ],
        lines=[
            {"line_id": "l1", "order_id": "o1", "synthetic_user_id": "u", "product_id": "p", "quantity": 1},
            {"line_id": "l2", "order_id": "o1", "synthetic_user_id": "U", "product_id": "p", "quantity": 1},
        ],
    )
    result, _ = compute(tmp_path, snapshot, days=30, name="case-users")
    assert counts(result.facts.channels[0]) == (1, 0, 0, 0, 10000, None)
    assert counts(result.facts.channels[1]) == (1, 0, 0, 0, 8000, None)
    assert result.facts.totals.channel_mature_cohort_count == 2


def test_nocase_locked_connection_is_rejected(tmp_path):
    snapshot = tiny_snapshot(
        orders=[
            {"order_id": "Z", "synthetic_user_id": "u", "paid_at": "2026-06-01T00:00:00+08:00",
             "channel": "A", "gross_paid_minor": 10000, "status": "PAID"},
            {"order_id": "a", "synthetic_user_id": "u", "paid_at": "2026-06-01T00:00:00+08:00",
             "channel": "B", "gross_paid_minor": 2000, "status": "PAID"},
        ],
        lines=[
            {"line_id": "l1", "order_id": "Z", "synthetic_user_id": "u", "product_id": "p", "quantity": 1},
            {"line_id": "l2", "order_id": "a", "synthetic_user_id": "u", "product_id": "p", "quantity": 1},
        ],
    )
    fixture = create_channel_followup_fixture(private_dir(tmp_path, "nocase-db"), snapshot)
    temp = private_dir(tmp_path, "nocase-tmp")
    connection = duckdb.connect(str(fixture.validate()), read_only=True, config={
        "memory_limit": f"{QUERY_DUCKDB_MEMORY_MIB}MiB",
        "threads": QUERY_DUCKDB_THREADS,
        "temp_directory": str(temp),
        "max_temp_directory_size": f"{QUERY_TEMP_MIB}MiB",
        "autoload_known_extensions": False,
        "autoinstall_known_extensions": False,
        "allow_community_extensions": False,
        "allow_persistent_secrets": False,
    })
    try:
        connection.execute("SET max_temp_directory_size = ?", [f"{QUERY_TEMP_MIB}MiB"])
        connection.execute("SET default_collation='nocase'")
        connection.execute("SET enable_external_access=false")
        connection.execute("SET lock_configuration=true")
        with pytest.raises(ValueError, match="collation"):
            execute_channel_followup_query(
                request=request_for(30), permission_scope=PERMISSION, fixture=fixture, connection=connection,
            )
    finally:
        connection.close()


def test_column_nocase_cannot_bypass_ascii_order(tmp_path):
    paid = "2026-06-01T00:00:00+08:00"
    snapshot = tiny_snapshot(
        orders=[
            {"order_id": "Z", "synthetic_user_id": "u", "paid_at": paid, "channel": "A",
             "gross_paid_minor": 10000, "status": "PAID"},
            {"order_id": "a", "synthetic_user_id": "u", "paid_at": paid, "channel": "B",
             "gross_paid_minor": 2000, "status": "PAID"},
        ],
        lines=[
            {"line_id": "l1", "order_id": "Z", "synthetic_user_id": "u", "product_id": "p", "quantity": 1},
            {"line_id": "l2", "order_id": "a", "synthetic_user_id": "u", "product_id": "p", "quantity": 1},
        ],
    )
    fixture = create_channel_followup_fixture(private_dir(tmp_path, "col-nocase"), snapshot)
    directory = Path(fixture.directory)
    writer = duckdb.connect(str(directory / DATABASE_NAME), config={"enable_external_access": False})
    try:
        writer.execute("ALTER TABLE channel_followup_lines DROP CONSTRAINT channel_followup_lines_channel_followup_orders_fkey")
    except Exception:
        pass
    try:
        rows = writer.execute("SELECT * FROM channel_followup_orders").fetchall()
        writer.execute("DROP TABLE channel_followup_refunds")
        writer.execute("DROP TABLE channel_followup_lines")
        writer.execute("DROP TABLE channel_followup_orders")
        writer.execute(
            "CREATE TABLE channel_followup_orders ("
            "synthetic_user_id VARCHAR COLLATE NOCASE NOT NULL, "
            "order_id VARCHAR COLLATE NOCASE NOT NULL, "
            "paid_at TIMESTAMP NOT NULL, channel VARCHAR COLLATE NOCASE NOT NULL, "
            "gross_paid_minor BIGINT NOT NULL, status VARCHAR COLLATE NOCASE NOT NULL, "
            "PRIMARY KEY (synthetic_user_id, order_id))"
        )
        writer.executemany("INSERT INTO channel_followup_orders VALUES (?, ?, ?, ?, ?, ?)", rows)
        writer.execute(
            "CREATE TABLE channel_followup_lines ("
            "line_id VARCHAR COLLATE NOCASE NOT NULL PRIMARY KEY, "
            "synthetic_user_id VARCHAR COLLATE NOCASE NOT NULL, "
            "order_id VARCHAR COLLATE NOCASE NOT NULL, "
            "product_id VARCHAR COLLATE NOCASE NOT NULL, quantity BIGINT NOT NULL)"
        )
        writer.execute(
            "INSERT INTO channel_followup_lines VALUES ('l1','u','Z','p',1), ('l2','u','a','p',1)"
        )
        writer.execute(
            "CREATE TABLE channel_followup_refunds ("
            "refund_id VARCHAR COLLATE NOCASE NOT NULL PRIMARY KEY, "
            "synthetic_user_id VARCHAR COLLATE NOCASE NOT NULL, "
            "order_id VARCHAR COLLATE NOCASE NOT NULL, "
            "refunded_at TIMESTAMP NOT NULL, refund_minor BIGINT NOT NULL)"
        )
        writer.execute("CHECKPOINT")
    finally:
        writer.close()
    tampered = _reseal(directory)
    connection = connect_channel_followup_readonly(tampered, private_dir(tmp_path, "col-nocase-tmp"))
    try:
        with pytest.raises(ValueError, match="collation|foreign keys"):
            execute_channel_followup_query(
                request=request_for(30), permission_scope=PERMISSION, fixture=tampered, connection=connection,
            )
    finally:
        connection.close()


def test_manifest_as_of_and_counts_must_match_snapshot(tmp_path):
    snapshot = tiny_snapshot(
        orders=[{"order_id": "o1", "synthetic_user_id": "u", "paid_at": "2026-06-01T00:00:00+08:00",
                 "channel": "A", "gross_paid_minor": 10000, "status": "PAID"}],
        lines=[{"line_id": "l1", "order_id": "o1", "synthetic_user_id": "u", "product_id": "p", "quantity": 1}],
    )
    fixture = create_channel_followup_fixture(private_dir(tmp_path, "meta-lie"), snapshot)
    directory = Path(fixture.directory)
    manifest_path = directory / MANIFEST_NAME
    bad = json.loads(manifest_path.read_text())
    bad["orders"] = 0
    bad["lines"] = 0
    bad["refunds"] = 0
    bad["as_of"] = "not-a-time"
    raw = (json.dumps(bad, sort_keys=True, separators=(",", ":")) + "\n").encode()
    manifest_path.write_bytes(raw)
    os.chmod(manifest_path, 0o600)
    lying = ChannelFollowupFixture(str(directory), hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError, match="as_of"):
        lying.validate()

    fixture = create_channel_followup_fixture(private_dir(tmp_path, "count-lie"), snapshot)
    directory = Path(fixture.directory)
    manifest_path = directory / MANIFEST_NAME
    bad = json.loads(manifest_path.read_text())
    bad["orders"] = 0
    bad["lines"] = 0
    raw = (json.dumps(bad, sort_keys=True, separators=(",", ":")) + "\n").encode()
    manifest_path.write_bytes(raw)
    os.chmod(manifest_path, 0o600)
    lying = ChannelFollowupFixture(str(directory), hashlib.sha256(raw).hexdigest())
    lying.validate()
    connection = connect_channel_followup_readonly(lying, private_dir(tmp_path, "count-lie-tmp"))
    try:
        with pytest.raises(ValueError, match="metadata"):
            execute_channel_followup_query(
                request=request_for(30), permission_scope=PERMISSION, fixture=lying, connection=connection,
            )
    finally:
        connection.close()


def test_extra_schema_is_rejected_after_close_and_reopen(tmp_path):
    fixture = create_channel_followup_fixture(private_dir(tmp_path, "extra-schema"), golden_snapshot())
    directory = Path(fixture.directory)
    writer = duckdb.connect(str(directory / DATABASE_NAME), config={"enable_external_access": False})
    try:
        writer.execute("CREATE SCHEMA extra")
        writer.execute("CREATE TABLE extra.unregistered(x INTEGER)")
        writer.execute("INSERT INTO extra.unregistered VALUES (1)")
        writer.execute("CHECKPOINT")
    finally:
        writer.close()
    tampered = _reseal(directory)
    tampered.validate()
    first = connect_channel_followup_readonly(tampered, private_dir(tmp_path, "extra-tmp1"))
    try:
        with pytest.raises(ValueError, match="schemas|tables"):
            execute_channel_followup_query(
                request=request_for(30), permission_scope=PERMISSION, fixture=tampered, connection=first,
            )
    finally:
        first.close()
    second = connect_channel_followup_readonly(tampered, private_dir(tmp_path, "extra-tmp2"))
    try:
        with pytest.raises(ValueError, match="schemas|tables"):
            execute_channel_followup_query(
                request=request_for(30), permission_scope=PERMISSION, fixture=tampered, connection=second,
            )
    finally:
        second.close()


class _Fetched:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return None if not self._rows else self._rows[0]


class _ExecuteRecorder:
    def __init__(self, inner):
        self._inner = inner
        self.fetches = []

    def execute(self, sql, params=None):
        result = self._inner.execute(sql, params) if params is not None else self._inner.execute(sql)
        if str(sql).strip().upper().startswith("SELECT") or " LIMIT " in str(sql).upper():
            rows = result.fetchall()
            self.fetches.append({"sql": sql, "returned_rows": len(rows)})
            return _Fetched(rows)
        return result

    def __getattr__(self, name):
        return getattr(self._inner, name)


def test_over_cap_file_fetch_is_bounded_then_rejected(tmp_path):
    seed = tiny_snapshot(
        orders=[{"order_id": "o0", "synthetic_user_id": "seed", "paid_at": "2026-06-01T00:00:00+08:00",
                 "channel": "A", "gross_paid_minor": 1, "status": "PAID"}],
        lines=[{"line_id": "l0", "order_id": "o0", "synthetic_user_id": "seed", "product_id": "p", "quantity": 1}],
    )
    fixture = create_channel_followup_fixture(private_dir(tmp_path, "cap-file"), seed)
    directory = Path(fixture.directory)
    writer = duckdb.connect(str(directory / DATABASE_NAME), config={"enable_external_access": False})
    try:
        extra = MAX_ORDERS + 1
        writer.executemany(
            "INSERT INTO channel_followup_orders VALUES (?, ?, TIMESTAMP '2026-06-10 00:00:00', 'A', 1, 'PAID')",
            [(f"u{i}", f"x{i}") for i in range(extra)],
        )
        writer.executemany(
            "INSERT INTO channel_followup_lines VALUES (?, ?, ?, 'p', 1)",
            [(f"xl{i}", f"u{i}", f"x{i}") for i in range(extra)],
        )
        writer.execute("CHECKPOINT")
    finally:
        writer.close()
    tampered = _reseal(directory)
    assert (directory / DATABASE_NAME).stat().st_size <= 4 * 1024 * 1024
    inner = connect_channel_followup_readonly(tampered, private_dir(tmp_path, "cap-file-tmp"))
    recorder = _ExecuteRecorder(inner)
    try:
        with pytest.raises(ValueError, match="row caps"):
            execute_channel_followup_query(
                request=request_for(30), permission_scope=PERMISSION, fixture=tampered, connection=recorder,
            )
        order_fetches = [item for item in recorder.fetches if "channel_followup_orders" in item["sql"]]
        assert order_fetches
        for item in order_fetches:
            assert "LIMIT" in item["sql"].upper()
            assert item["returned_rows"] <= MAX_ORDERS + 1
    finally:
        inner.close()


def test_production_modules_do_not_import_tests_or_expected_answers():
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "analytics_query_fixture.py",
        "semantic/analytics_channel_followup.py",
        "services/analytics/queries.py",
        "services/analytics/catalog.py",
    ):
        text = (root / relative).read_text(encoding="utf-8")
        assert "backend.tests" not in text
        assert "analytics_channel_followup_v1_expected" not in text
        assert "expected.json" not in text
    assert "SQL、worker、调度与 HTTP API 尚未实现" not in LIMITATIONS
    bound = bind_resolved_filters(request_for(30), golden_snapshot(), PERMISSION)
    assert bound.observation_days == 30
