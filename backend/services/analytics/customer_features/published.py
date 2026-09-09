"""Versioned synthetic W4 artifacts. SQLite commits payload and visibility together.

This is a service seam, not an HTTP endpoint: callers resolve current identity
on every read and supply its granted scopes. No warehouse copy or model call.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from backend.services.analytics.customer_features.compute import (
    CustomerFeatureRun,
    _days_since,
    _feature_bytes,
    compute_customer_features,
)
from backend.services.analytics.customer_features.contract import (
    FEATURE_LAYER_VERSION,
    FEATURE_PIPELINE_VERSION,
)
from backend.services.analytics.warehouse.contract import (
    AMOUNT_PRECISION,
    AMOUNT_UNIT,
    CURRENCY,
    SCHEMA_VERSION,
    TIMEZONE,
    PermissionScopeDenied,
    WarehouseContractError,
    require_minor,
    require_str_id,
    utc_naive_instant,
)


class PublicationConflict(WarehouseContractError):
    """Stale expected version or reused key with a different payload."""


def _json(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _require_grant(scope, granted_scopes):
    # A string would perform substring membership (brand_a in brand_ab).
    # This seam accepts only resolved sets, matching AnalyticsPrincipal.data_scopes.
    if not isinstance(granted_scopes, (set, frozenset)) or any(
        type(s) is not str for s in granted_scopes
    ):
        raise PermissionScopeDenied("current grants must be an explicit set of scopes")
    if scope not in granted_scopes:
        raise PermissionScopeDenied("current permission does not grant this snapshot")


def _validated(manifest, rows):
    if (
        manifest.get("contains_real_data") is not False
        or manifest.get("feature_layer_version") != FEATURE_LAYER_VERSION
    ):
        raise WarehouseContractError("only synthetic W4 v1 artifacts are accepted")
    expected = {
        "schema_version": SCHEMA_VERSION,
        "feature_pipeline_version": FEATURE_PIPELINE_VERSION,
        "currency": CURRENCY,
        "amount_unit": AMOUNT_UNIT,
        "amount_precision": AMOUNT_PRECISION,
        "timezone": TIMEZONE,
    }
    if any(manifest.get(k) != v for k, v in expected.items()):
        raise WarehouseContractError("unsupported feature schema or units")
    for name in ("content_hash", "database_sha256", "features_sha256"):
        value = manifest.get(name)
        if (
            type(value) is not str
            or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)
        ):
            raise WarehouseContractError("feature provenance requires SHA256 digests")
    scope = require_str_id(manifest["permission_scope"], name="permission_scope")
    as_of = utc_naive_instant(manifest["feature_as_of"])
    if as_of < utc_naive_instant(manifest["warehouse_as_of"]):
        raise WarehouseContractError("feature clock precedes warehouse snapshot")
    if (
        len(rows) != manifest["row_count"]
        or hashlib.sha256(_feature_bytes(rows)).hexdigest()
        != manifest["features_sha256"]
    ):
        raise WarehouseContractError("feature payload integrity mismatch")
    keys, users = set(), set()
    for row in rows:
        key = require_minor(row["customer_key"], name="customer_key")
        user = require_str_id(row["synthetic_user_id"], name="synthetic_user_id")
        if key == 0 or key in keys or user in users or row["permission_scope"] != scope:
            raise WarehouseContractError("feature grain or scope mismatch")
        keys.add(key)
        users.add(user)
        require_str_id(row["identity_domain"], name="identity_domain")
        if require_minor(row["valid_order_count"], name="frequency") == 0:
            raise WarehouseContractError("valid features require orders")
        if require_minor(row["valid_net_paid_minor"], name="monetary") == 0:
            raise WarehouseContractError("valid features require positive net amount")
        first, last = (
            utc_naive_instant(row["first_paid_at"]),
            utc_naive_instant(row["last_paid_at"]),
        )
        if first > last or last > utc_naive_instant(manifest["warehouse_as_of"]):
            raise WarehouseContractError("invalid feature time range")
        if type(row["days_since_last_paid"]) is not int or row[
            "days_since_last_paid"
        ] != _days_since(last, as_of):
            raise WarehouseContractError("recency does not match feature clock")
    return scope


@dataclass(frozen=True)
class FeatureSnapshot:
    version: int
    previous_version: int | None
    manifest_json: str
    rows_json: str
    digest: str

    @property
    def manifest(self):
        return json.loads(self.manifest_json)

    def read(
        self,
        *,
        granted_scopes,
        synthetic_user_ids=None,
        feature_as_of=None,
        recency_range=None,
        frequency_range=None,
        monetary_range=None,
    ):
        """R/F/M inclusive ranges over snapshot history, never invented buckets.

        Advancing the clock only changes R; F/M remain at warehouse_as_of.
        Unknown or foreign named users are rejected, not silently omitted.
        """
        meta = self.manifest
        _require_grant(meta["permission_scope"], granted_scopes)
        rows = json.loads(self.rows_json)
        clock = utc_naive_instant(
            meta["feature_as_of"] if feature_as_of is None else feature_as_of
        )
        if clock < utc_naive_instant(meta["feature_as_of"]):
            raise WarehouseContractError("feature clock cannot move backwards")
        if synthetic_user_ids is not None:
            users = {
                require_str_id(u, name="synthetic_user_id") for u in synthetic_user_ids
            }
            if users - {r["synthetic_user_id"] for r in rows}:
                raise PermissionScopeDenied(
                    "named users are not present in this scoped snapshot"
                )
            rows = [r for r in rows if r["synthetic_user_id"] in users]
        ranges = [
            ("days_since_last_paid", recency_range),
            ("valid_order_count", frequency_range),
            ("valid_net_paid_minor", monetary_range),
        ]
        for _, bounds in ranges:
            if bounds is not None:
                if not isinstance(bounds, (tuple, list)) or len(bounds) != 2:
                    raise WarehouseContractError(
                        "ranges require inclusive lower and upper bounds"
                    )
                lo, hi = (require_minor(v, name="range bound") for v in bounds)
                if lo > hi:
                    raise WarehouseContractError("range bounds are reversed")
        for row in rows:
            row["days_since_last_paid"] = _days_since(row["last_paid_at"], clock)
        return {
            "version": self.version,
            "artifact_digest": self.digest,
            "permission_scope": meta["permission_scope"],
            "warehouse_as_of": meta["warehouse_as_of"],
            "feature_as_of": clock.isoformat() + "+00:00",
            "contains_real_data": False,
            "rows": [
                r
                for r in rows
                if all(b is None or b[0] <= r[k] <= b[1] for k, b in ranges)
            ],
        }


class FeaturePublicationStore:
    """One SQLite writer, immutable versions, durable retry keys and pinned readers.

    Requires a private, dedicated directory. Retains all versions; no pruning.
    """

    def __init__(self, directory):
        root = Path(directory)
        if (
            root.is_symlink()
            or not root.is_dir()
            or root.stat().st_mode & 0o077
            or root.stat().st_uid != os.getuid()
        ):
            raise WarehouseContractError(
                "an owned mode-0700 publication directory is required"
            )
        self.path = root.resolve() / "features.sqlite3"
        fd = os.open(
            root / ".publication-initialize.lock",
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
            0o600,
        )
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid != os.getuid()
            ):
                raise WarehouseContractError("invalid publication initialization lock")
            fcntl.flock(fd, fcntl.LOCK_EX)
            if self.path.exists() or self.path.is_symlink():
                with self._connect(readonly=True) as con:
                    application = con.execute("PRAGMA application_id").fetchone()[0]
                    schema = con.execute("PRAGMA user_version").fetchone()[0]
                    if application != 0x57504631 or schema != 1:
                        raise WarehouseContractError(
                            "foreign or incomplete publication database"
                        )
                return
            # Build privately, close and fsync before exposing the final name.
            # A crash leaves only an unreferenced initializer; retry uses a fresh
            # name, never treating a foreign/incomplete final database as ours.
            staged = self.path.with_name(f".features-initialize-{uuid4().hex}.sqlite3")
            with self._connect(create=True, path=staged) as con:
                con.executescript("""
                    BEGIN IMMEDIATE;
                    CREATE TABLE feature_versions (
                        scope TEXT NOT NULL, version INTEGER NOT NULL,
                        previous INTEGER, request_key TEXT NOT NULL, digest TEXT NOT NULL,
                        manifest TEXT NOT NULL, rows TEXT NOT NULL,
                        PRIMARY KEY(scope,version), UNIQUE(scope,request_key));
                    CREATE TABLE feature_heads (
                        scope TEXT PRIMARY KEY, version INTEGER NOT NULL);
                    PRAGMA application_id=1464878641;
                    PRAGMA user_version=1;
                    COMMIT;
                """)
            with staged.open("rb") as completed:
                os.fsync(completed.fileno())
            # All store initializers hold this directory lock. Rename exposes
            # one complete file, with no intermediate hardlink state.
            if self.path.exists() or self.path.is_symlink():
                raise WarehouseContractError(
                    "publication destination appeared during initialization"
                )
            os.rename(staged, self.path)
            directory_fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)

        finally:
            os.close(fd)

    @contextmanager
    def _connect(self, *, create=False, readonly=False, path=None):
        path = self.path if path is None else path
        if path.is_symlink():
            raise WarehouseContractError("publication database must not be a symlink")
        if create and not path.exists():
            try:
                fd = os.open(
                    path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                    0o600,
                )
                os.close(fd)
            except FileExistsError:
                pass
        if not path.is_file() or path.stat().st_nlink != 1:
            raise WarehouseContractError(
                "publication database must be a regular unlinked file"
            )
        con = sqlite3.connect(
            path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"),
            uri=True,
            timeout=5,
        )
        try:
            con.execute("PRAGMA synchronous=FULL")
            yield con
        finally:
            con.close()

    def publish_warehouse(
        self,
        warehouse,
        *,
        permission_scope,
        feature_as_of=None,
        request_key,
        expected_version,
        temp_directory,
    ):
        """Trusted batch entry: read the verified synthetic warehouse once.

        Only full-scope customer features are published. Subsequent consumers
        filter the pinned artifact without reopening or reaggregating DuckDB.
        """
        con = warehouse.connect_readonly(temp_directory)
        try:
            run = compute_customer_features(
                con,
                permission_scope=permission_scope,
                published_manifest=warehouse.published_manifest,
                feature_as_of=feature_as_of,
                database_path=warehouse.database,
            )
        finally:
            con.close()
        return self.publish(
            run, request_key=request_key, expected_version=expected_version
        )

    def publish(
        self, run: CustomerFeatureRun, *, request_key: str, expected_version: int
    ):
        require_str_id(request_key, name="request_key")
        if type(expected_version) is not int or expected_version < 0:
            raise WarehouseContractError(
                "expected_version must be a nonnegative integer"
            )
        # Detach mutable dicts once before validation; store exactly these bytes.
        manifest = _json(run.published_manifest())
        rows = _json(run.rows)
        scope = _validated(json.loads(manifest), json.loads(rows))
        digest = hashlib.sha256((manifest + "\n" + rows).encode()).hexdigest()
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            prior = con.execute(
                "SELECT version,digest FROM feature_versions WHERE scope=? AND request_key=?",
                (scope, request_key),
            ).fetchone()
            if prior:
                if prior[1] != digest:
                    raise PublicationConflict(
                        "retry key is already bound to another artifact"
                    )
                return prior[0]
            head = con.execute(
                "SELECT version FROM feature_heads WHERE scope=?", (scope,)
            ).fetchone()
            current = head[0] if head else 0
            if expected_version != current:
                raise PublicationConflict("publication head changed")
            version = current + 1
            con.execute(
                "INSERT INTO feature_versions VALUES (?,?,?,?,?,?,?)",
                (scope, version, current or None, request_key, digest, manifest, rows),
            )
            con.execute(
                "INSERT INTO feature_heads VALUES (?,?) ON CONFLICT(scope) DO UPDATE SET version=excluded.version",
                (scope, version),
            )
            con.commit()
        return version

    def pin(self, *, permission_scope, granted_scopes, version=None):
        _require_grant(permission_scope, granted_scopes)
        if version is not None and (type(version) is not int or version < 1):
            raise WarehouseContractError("version must be positive")
        # One SQL statement resolves the head and payload from the same snapshot.
        with self._connect(readonly=True) as con:
            row = con.execute(
                """SELECT v.version,v.previous,v.manifest,v.rows,v.digest
                FROM feature_versions v WHERE v.scope=? AND v.version=COALESCE(?,
                (SELECT version FROM feature_heads WHERE scope=?))""",
                (permission_scope, version, permission_scope),
            ).fetchone()
        if row is None:
            raise WarehouseContractError("published feature version is unavailable")
        snapshot = FeatureSnapshot(*row)
        if (
            hashlib.sha256(
                (snapshot.manifest_json + "\n" + snapshot.rows_json).encode()
            ).hexdigest()
            != snapshot.digest
        ):
            raise WarehouseContractError("published artifact digest mismatch")
        if (
            _validated(snapshot.manifest, json.loads(snapshot.rows_json))
            != permission_scope
        ):
            raise WarehouseContractError("stored artifact scope mismatch")
        return snapshot
