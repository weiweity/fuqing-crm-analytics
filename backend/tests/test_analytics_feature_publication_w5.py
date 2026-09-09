"""Small synthetic W4 consumption / W5 publication correctness, not capacity."""

import json
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from backend.services.analytics.customer_features import (
    FeaturePublicationStore,
    PublicationConflict,
)
from backend.services.analytics.warehouse.contract import (
    PermissionScopeDenied,
    WarehouseContractError,
)
from backend.tests.test_analytics_customer_features_w4 import (
    materialize_w4,
    features_for,
    private_dir,
)


@pytest.fixture
def feature(tmp_path):
    warehouse, _, _ = materialize_w4(tmp_path)
    run, _, _ = features_for(warehouse, tmp_path, scope="brand_a")
    return run


@pytest.fixture
def store(tmp_path):
    return FeaturePublicationStore(private_dir(tmp_path, "publications"))


def pin(store, version=None):
    return store.pin(
        permission_scope="brand_a", granted_scopes={"brand_a"}, version=version
    )


def test_closed_connection_and_reopen(feature, store):
    assert store.publish(feature, request_key="first", expected_version=0) == 1
    reopened = FeaturePublicationStore(store.path.parent)
    saved = pin(reopened)
    assert saved.previous_version is None
    assert saved.read(granted_scopes={"brand_a"})["rows"] == list(feature.rows)
    assert saved.manifest["rule_version"] == feature.rule_version
    assert saved.manifest["database_sha256"] == feature.database_sha256


def test_pinned_reader_retains_old_version_and_retry_does_not_rewind_head(
    feature, store
):
    store.publish(feature, request_key="first", expected_version=0)
    old = pin(store)
    # Metadata changes are versioned even if numeric rows stay the same.
    next_run = replace(feature, rule_version="analytics-warehouse-rules/v2")
    assert store.publish(next_run, request_key="next", expected_version=1) == 2
    assert store.publish(feature, request_key="first", expected_version=0) == 1
    assert pin(store).version == 2
    assert pin(store).previous_version == 1
    assert pin(store, 1) == old
    assert old.read(granted_scopes={"brand_a"})["version"] == 1


def test_retry_conflict_and_stale_writer(feature, store):
    store.publish(feature, request_key="first", expected_version=0)
    with pytest.raises(PublicationConflict):
        store.publish(
            replace(feature, rule_version="changed"),
            request_key="first",
            expected_version=1,
        )
    with pytest.raises(PublicationConflict):
        store.publish(feature, request_key="other", expected_version=0)
    assert pin(store).version == 1


def test_shared_ranges_clock_and_defensive_copies(feature, store):
    store.publish(feature, request_key="first", expected_version=0)
    snap = pin(store)
    result = snap.read(
        granted_scopes={"brand_a"},
        feature_as_of="2026-09-16T00:00:00+08:00",
        recency_range=(32, 32),
        frequency_range=(3, 3),
        monetary_range=(19000, 19000),
    )
    assert [r["synthetic_user_id"] for r in result["rows"]] == ["u-refund"]
    result["rows"][0]["valid_net_paid_minor"] = 0
    assert (
        snap.read(granted_scopes={"brand_a"}, synthetic_user_ids=["u-refund"])["rows"][
            0
        ]["valid_net_paid_minor"]
        == 19000
    )
    with pytest.raises(WarehouseContractError):
        snap.read(granted_scopes={"brand_a"}, frequency_range=(True, 3))
    with pytest.raises(WarehouseContractError):
        snap.read(granted_scopes={"brand_a"}, feature_as_of="2026-08-31T00:00:00+08:00")


def test_scope_and_revocation_on_pinned_reader(feature, store):
    store.publish(feature, request_key="first", expected_version=0)
    snap = pin(store)
    with pytest.raises(PermissionScopeDenied):
        store.pin(permission_scope="brand_a", granted_scopes={"brand_b"})
    with pytest.raises(PermissionScopeDenied):
        snap.read(granted_scopes=set())
    with pytest.raises(PermissionScopeDenied):
        snap.read(granted_scopes={"brand_a"}, synthetic_user_ids=["u-scope-b"])
    assert snap.read(granted_scopes={"brand_a"}, synthetic_user_ids=[])["rows"] == []


def test_mutated_feature_refused_without_head_change(feature, store):
    store.publish(feature, request_key="first", expected_version=0)
    feature.rows[0]["valid_net_paid_minor"] += 1
    with pytest.raises(WarehouseContractError):
        store.publish(feature, request_key="bad", expected_version=1)
    assert pin(store).version == 1


def test_corrupted_persisted_payload_refused(feature, store):
    store.publish(feature, request_key="first", expected_version=0)
    with sqlite3.connect(store.path) as c:
        c.execute("UPDATE feature_versions SET rows='[]'")
    with pytest.raises(WarehouseContractError):
        pin(store)


def test_two_writers_serialize_and_cas(feature, store):
    def publish(key):
        try:
            return store.publish(feature, request_key=key, expected_version=0)
        except PublicationConflict:
            return "conflict"

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(publish, ["one", "two"]))
    assert sorted(map(str, results)) == ["1", "conflict"]
    assert pin(store).version == 1


@pytest.mark.parametrize("after_commit", [False, True])
def test_process_exit_during_actual_publish(feature, store, tmp_path, after_commit):
    store.publish(feature, request_key="first", expected_version=0)
    payload = tmp_path / "feature.json"
    payload.write_text(json.dumps(asdict(feature)))
    code = """
import json,os,sys
from contextlib import contextmanager
from pathlib import Path
from backend.services.analytics.customer_features.compute import CustomerFeatureRun
from backend.services.analytics.customer_features.published import FeaturePublicationStore
run=CustomerFeatureRun(**json.loads(Path(sys.argv[2]).read_text()))
store=FeaturePublicationStore(sys.argv[1])
original=store._connect
class CrashConnection:
    def __init__(self, con): self.con=con
    def execute(self,*args): return self.con.execute(*args)
    def commit(self):
        if sys.argv[3]=='True': self.con.commit()
        os._exit(77)
@contextmanager
def crash(**kwargs):
    with original(**kwargs) as con: yield CrashConnection(con)
store._connect=crash
store.publish(run,request_key='crash',expected_version=1)
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])}
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(store.path.parent),
            str(payload),
            str(after_commit),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        timeout=20,
    )
    assert proc.returncode == 77, proc.stderr.decode()
    reopened = FeaturePublicationStore(store.path.parent)
    assert pin(reopened).version == (2 if after_commit else 1)
    assert reopened.publish(feature, request_key="crash", expected_version=1) == 2
    assert pin(reopened).read(granted_scopes={"brand_a"})["rows"] == list(feature.rows)


def test_foreign_database_and_symlink_refused(tmp_path):
    d = private_dir(tmp_path, "foreign")
    with sqlite3.connect(d / "features.sqlite3") as c:
        c.execute("CREATE TABLE unrelated(value)")
    with pytest.raises(WarehouseContractError):
        FeaturePublicationStore(d)
    linked = tmp_path / "linked"
    linked.symlink_to(d, target_is_directory=True)
    with pytest.raises(WarehouseContractError):
        FeaturePublicationStore(linked)


def test_warehouse_publish_consumers_do_not_reopen_duckdb(store, tmp_path, monkeypatch):
    warehouse, _, _ = materialize_w4(tmp_path)
    assert (
        store.publish_warehouse(
            warehouse,
            permission_scope="brand_a",
            request_key="batch",
            expected_version=0,
            temp_directory=private_dir(tmp_path, "publish-tmp"),
        )
        == 1
    )
    import duckdb

    def forbidden(*args, **kwargs):
        raise AssertionError("consumer must not reopen warehouse")

    monkeypatch.setattr(duckdb, "connect", forbidden)
    snap = pin(store)
    assert len(snap.read(granted_scopes={"brand_a"})["rows"]) == 5
    assert (
        snap.read(granted_scopes={"brand_a"}, frequency_range=(3, 3))["rows"][0][
            "synthetic_user_id"
        ]
        == "u-refund"
    )


def test_other_scope_publishes_independently(store, tmp_path):
    warehouse, _, _ = materialize_w4(tmp_path)
    for scope in ["brand_a", "brand_b"]:
        assert (
            store.publish_warehouse(
                warehouse,
                permission_scope=scope,
                request_key="same-key",
                expected_version=0,
                temp_directory=private_dir(tmp_path, scope),
            )
            == 1
        )
    b = store.pin(permission_scope="brand_b", granted_scopes={"brand_b"})
    assert [
        r["synthetic_user_id"] for r in b.read(granted_scopes={"brand_b"})["rows"]
    ] == ["u-scope-b"]


@pytest.mark.parametrize(
    "change",
    [
        {"database_sha256": None},
        {"amount_unit": "yuan"},
        {"feature_layer_version": "unknown"},
    ],
)
def test_invalid_provenance_or_units_not_published(feature, store, change):
    with pytest.raises(WarehouseContractError):
        store.publish(
            replace(feature, **change), request_key="invalid", expected_version=0
        )
    with pytest.raises(WarehouseContractError):
        pin(store)


@pytest.mark.parametrize("phase", ["before_connect", "before_rename", "after_rename"])
def test_initialization_crash_leaves_retryable_store(tmp_path, phase):
    directory = private_dir(tmp_path, "initializing")
    code = """
import os,sqlite3,sys
from backend.services.analytics.customer_features.published import FeaturePublicationStore
if sys.argv[2]=='before_connect':
    sqlite3.connect=lambda *a,**kw: os._exit(77)
else:
    original=os.rename
    def crash(*args,**kwargs):
        if sys.argv[2]=='after_rename': original(*args,**kwargs)
        os._exit(77)
    os.rename=crash
FeaturePublicationStore(sys.argv[1])
"""
    proc = subprocess.run(
        [sys.executable, "-c", code, str(directory), phase],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
        capture_output=True,
        timeout=20,
    )
    assert proc.returncode == 77, proc.stderr.decode()
    FeaturePublicationStore(directory)
    with sqlite3.connect(directory / "features.sqlite3") as con:
        assert con.execute("PRAGMA application_id").fetchone()[0] == 0x57504631
        assert con.execute("SELECT COUNT(*) FROM feature_heads").fetchone()[0] == 0


def test_grants_are_not_substring_membership_and_false_clock_is_rejected(
    feature, store
):
    store.publish(feature, request_key="first", expected_version=0)
    with pytest.raises(PermissionScopeDenied):
        store.pin(permission_scope="brand_a", granted_scopes="brand_ab")
    snap = pin(store)
    with pytest.raises(PermissionScopeDenied):
        snap.read(granted_scopes="brand_ab")
    for clock in (False, "", 0):
        with pytest.raises(WarehouseContractError):
            snap.read(granted_scopes={"brand_a"}, feature_as_of=clock)
