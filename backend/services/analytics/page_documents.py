"""Durable free-page assets. Drafts never change the published head.

One connection per operation, immutable snapshots, monotonic rollback versions,
current grants on every read/replay, and compare-and-swap inside BEGIN IMMEDIATE.
Source package and binding manifest share one atomic version. This file never
dispatches a model or opens a business DuckDB. BoardSpec codec is not used.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Callable
from uuid import uuid4

from pydantic import ValidationError

from backend.contracts.analytics_query import canonical_json
from backend.contracts.competition_computed import DATA_SCOPE
from backend.contracts.page_documents import (
    PACKAGE_MAX_BYTES, PageDocument, PageDraft, PagePatchPreview, PageRollbackPreview,
    PageSavePreview, is_package_too_large,
)
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, require
from backend.services.analytics.first_purchase.asset_state import (
    connect, initialize_sqlite, now_ms, opaque, transaction, validate_key,
)

UNAVAILABLE = "页面保存库暂不可用，已保存版本未被本次操作替换。"
DDL = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE heads (
    owner TEXT NOT NULL, page_id TEXT NOT NULL, version INTEGER NOT NULL,
    PRIMARY KEY(owner, page_id)
);
CREATE TABLE revisions (
    owner TEXT NOT NULL, page_id TEXT NOT NULL, version INTEGER NOT NULL,
    operation TEXT NOT NULL, created_ms INTEGER NOT NULL,
    payload TEXT NOT NULL, digest TEXT NOT NULL,
    PRIMARY KEY(owner, page_id, version)
);
CREATE TABLE previews (
    owner TEXT NOT NULL, preview_id TEXT NOT NULL, page_id TEXT NOT NULL,
    base_version INTEGER NOT NULL, operation TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PENDING','CANCELLED','APPLIED')),
    expires_ms INTEGER NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL,
    PRIMARY KEY(owner, preview_id)
);
CREATE TABLE receipts (
    owner TEXT NOT NULL, key TEXT NOT NULL, preview_id TEXT NOT NULL,
    PRIMARY KEY(owner, key),
    FOREIGN KEY(owner, preview_id) REFERENCES previews(owner, preview_id)
);
"""


@dataclass(frozen=True)
class ResolvedPageBinding:
    status: str
    required_scopes: frozenset[str]


def fault(code="VERSION_CONFLICT", status=409):
    messages = {
        "VERSION_CONFLICT": "页面版本已变化，请重新读取后预览；原版本未被覆盖。",
        "NOT_FOUND": "页面或草稿不存在，或当前身份不可见。",
        "PREVIEW_CANCELLED": "草稿已取消，不能保存。",
        "PREVIEW_EXPIRED": "草稿已过期，请重新预览。",
        "IDEMPOTENCY_CONFLICT": "该幂等键已用于另一份草稿。",
        "BINDING_CORRUPT": "页面快照完整性校验失败，请保留状态并检查。",
        "INVALID_PAGE": "页面源码包、绑定或字段不符合合同。",
        "PACKAGE_TOO_LARGE": "页面源码包超过大小上限。",
        "RESULT_UNAVAILABLE": "没有可绑定的当前会话结果，请先完成对应问数。",
        "RESULT_STALE": "绑定结果已过期，页面仍可打开，请重新绑定。",
        "RESULT_REVOKED": "绑定结果授权已撤销。",
        "FORBIDDEN": "当前身份无权操作此页面。",
    }
    return AnalyticsError(status, code, messages[code])


def validated(model, payload):
    try:
        return model.model_validate(payload)
    except ValidationError as error:
        if is_package_too_large(error):
            raise fault("PACKAGE_TOO_LARGE", 413) from error
        raise fault("INVALID_PAGE", 422) from error
    except (ValueError, TypeError) as error:
        raise fault("INVALID_PAGE", 422) from error


def stamp_binding_state(payload):
    spec = dict(payload)
    refs = (spec.get("binding_manifest") or {}).get("result_refs") or []
    if not refs:
        spec["binding_state"] = "UNBOUND_SAMPLE"
    elif spec.get("binding_state") not in {"BOUND_VERIFIED", "BOUND_STALE"}:
        spec["binding_state"] = "BOUND_VERIFIED"
    return spec


class PageDocumentStore:
    def __init__(self, directory: Path, *,
                 resolve_binding: Callable[[AnalyticsPrincipal, str, str], ResolvedPageBinding] | None = None,
                 clock: Callable[[], int] = now_ms):
        self.path = directory.resolve() / "page_documents.sqlite3"
        self.resolve_binding = resolve_binding
        self.clock = clock
        initialize_sqlite(directory, self.path, application_id=1804289383, schema_version=1,
                          kind="library_page_documents", ddl=DDL, unavailable=UNAVAILABLE)

    @contextmanager
    def _read(self):
        try:
            with connect(self.path, readonly=True, unavailable=UNAVAILABLE) as con:
                yield con
        except sqlite3.DatabaseError as error:
            raise AnalyticsError(503, "STATE_UNAVAILABLE", UNAVAILABLE, retryable=True) from error

    @staticmethod
    def _access(actor, *, write=False, scopes=()):
        require(actor, "dashboard:read", data_scope=DATA_SCOPE)
        if write:
            require(actor, "dashboard:update", data_scope=DATA_SCOPE)
        for scope in scopes:
            require(actor, "dashboard:read", data_scope=scope)

    def _decode(self, actor, row, *, version):
        if row is None or row["owner"] != actor.actor_id:
            raise fault("NOT_FOUND", 404)
        try:
            if hashlib.sha256(row["payload"].encode()).hexdigest() != row["digest"]:
                raise ValueError("snapshot digest differs")
            stored = json.loads(row["payload"])
            snapshot = validated(PageDocument, stored["snapshot"]["spec"])
            scopes = stored["required_scopes"]
            if (not isinstance(scopes, list) or any(not isinstance(scope, str) or not scope for scope in scopes)
                    or snapshot.page_id != row["page_id"] or snapshot.version != version
                    or snapshot.schema_version != "free-page/v1"):
                raise ValueError("snapshot binding differs")
        except (ValueError, TypeError, KeyError, AnalyticsError) as error:
            if isinstance(error, AnalyticsError) and error.code == "INVALID_PAGE":
                raise fault("BINDING_CORRUPT") from error
            raise fault("BINDING_CORRUPT") from error
        self._access(actor, scopes=scopes)
        return {"spec": snapshot.model_dump(mode="json")}, frozenset(scopes)

    @staticmethod
    def _head(con, actor, page_id):
        opaque(page_id, label="page_id")
        row = con.execute("SELECT version FROM heads WHERE owner=? AND page_id=?",
                          (actor.actor_id, page_id)).fetchone()
        if row is None:
            raise fault("NOT_FOUND", 404)
        return row["version"]

    def _revision(self, con, actor, page_id, version):
        row = con.execute("SELECT * FROM revisions WHERE owner=? AND page_id=? AND version=?",
                          (actor.actor_id, page_id, version)).fetchone()
        return self._decode(actor, row, version=version)

    def get(self, actor, page_id, version=None):
        self._access(actor)
        if version is not None and (type(version) is not int or not 1 <= version <= 9007199254740991):
            raise fault("INVALID_PAGE", 422)
        with self._read() as con:
            current = self._head(con, actor, page_id)
            return self._revision(con, actor, page_id, current if version is None else version)[0]

    def list(self, actor, *, limit=100, offset=0):
        self._access(actor)
        self._page(limit, offset)
        with self._read() as con:
            rows = con.execute("SELECT * FROM heads WHERE owner=? ORDER BY page_id LIMIT ? OFFSET ?",
                               (actor.actor_id, limit, offset)).fetchall()
            items = []
            for row in rows:
                try:
                    snapshot, _ = self._revision(con, actor, row["page_id"], row["version"])
                except AnalyticsError as error:
                    if error.status == 403:
                        continue
                    raise
                spec = snapshot["spec"]
                items.append({key: spec[key] for key in
                              ("page_id", "title", "version", "session_id", "binding_state")})
            return items

    @staticmethod
    def _page(limit, offset):
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 1000000:
            raise fault("INVALID_PAGE", 422)

    def history(self, actor, page_id, *, limit=100, offset=0):
        self._access(actor)
        self._page(limit, offset)
        with self._read() as con:
            self._head(con, actor, page_id)
            rows = con.execute(
                "SELECT * FROM revisions WHERE owner=? AND page_id=? ORDER BY version DESC LIMIT ? OFFSET ?",
                (actor.actor_id, page_id, limit, offset)).fetchall()
            items = []
            for row in rows:
                self._decode(actor, row, version=row["version"])
                items.append({"version": row["version"], "operation": row["operation"],
                              "created_at_ms": row["created_ms"]})
            return items

    def _bind(self, actor, spec, *, retained_scopes=None):
        refs = list(spec.binding_manifest.result_refs)
        if not refs:
            return spec.model_copy(update={"binding_state": "UNBOUND_SAMPLE"}), frozenset()
        if retained_scopes is not None:
            self._access(actor, scopes=retained_scopes)
            return spec, frozenset(retained_scopes)
        if self.resolve_binding is None:
            raise fault("RESULT_UNAVAILABLE", 409)
        scopes = set()
        stale = False
        for ref in refs:
            resolved = self.resolve_binding(actor, spec.session_id, ref)
            if resolved.status == "REVOKED":
                raise fault("RESULT_REVOKED", 403)
            if resolved.status == "UNAVAILABLE":
                raise fault("RESULT_UNAVAILABLE", 409)
            if resolved.status not in {"VERIFIED", "STALE"}:
                raise fault("INVALID_PAGE", 422)
            self._access(actor, scopes=resolved.required_scopes)
            scopes.update(resolved.required_scopes)
            stale = stale or resolved.status == "STALE"
        state = "BOUND_STALE" if stale else "BOUND_VERIFIED"
        return spec.model_copy(update={"binding_state": state}), frozenset(scopes)

    def _preview(self, actor, spec, operation, base_version, *, retained_scopes=None):
        self._access(actor, write=True)
        spec, scopes = self._bind(actor, spec, retained_scopes=retained_scopes)
        snapshot = {"spec": spec.model_dump(mode="json")}
        payload = canonical_json({"snapshot": snapshot, "required_scopes": sorted(scopes)})
        if len(payload.encode()) > PACKAGE_MAX_BYTES:
            raise fault("PACKAGE_TOO_LARGE", 413)
        preview_id = "preview_" + uuid4().hex
        expires = self.clock() + 30 * 60 * 1000
        with transaction(self.path, unavailable=UNAVAILABLE) as con:
            if base_version and self._head(con, actor, spec.page_id) != base_version:
                raise fault()
            con.execute("INSERT INTO previews VALUES (?,?,?,?,?,'PENDING',?,?,?)",
                        (actor.actor_id, preview_id, spec.page_id, base_version, operation, expires,
                         payload, hashlib.sha256(payload.encode()).hexdigest()))
        return {"preview_id": preview_id, "status": "PENDING", "operation": operation,
                "base_version": base_version, "expires_at_ms": expires, "snapshot": snapshot}

    def generate(self, actor, request: PageDraft):
        self._access(actor, write=True)
        spec = validated(PageDocument, stamp_binding_state({**request.model_dump(mode="json"),
            "page_id": "page_" + uuid4().hex, "version": 1}))
        return self._preview(actor, spec, "GENERATE", 0)

    def _base(self, actor, page_id, base_version):
        self._access(actor, write=True)
        with self._read() as con:
            if self._head(con, actor, page_id) != base_version:
                raise fault()
            return self._revision(con, actor, page_id, base_version)

    def patch(self, actor, page_id, request: PagePatchPreview):
        snapshot, scopes = self._base(actor, page_id, request.base_version)
        spec = deepcopy(snapshot["spec"])
        changes = request.model_dump(mode="json", exclude_unset=True)
        changes.pop("base_version")
        spec.update(changes)
        spec["version"] += 1
        retain = None if "binding_manifest" in request.model_fields_set else scopes
        return self._preview(actor, validated(PageDocument, stamp_binding_state(spec)), "PATCH",
                             request.base_version, retained_scopes=retain)

    def save(self, actor, page_id, request: PageSavePreview):
        snapshot, _scopes = self._base(actor, page_id, request.base_version)
        spec = deepcopy(snapshot["spec"])
        spec.update(request.model_dump(mode="json", exclude={"base_version"}))
        spec["version"] += 1
        return self._preview(actor, validated(PageDocument, stamp_binding_state(spec)), "SAVE",
                             request.base_version)

    def rollback(self, actor, page_id, request: PageRollbackPreview):
        self._base(actor, page_id, request.base_version)
        with self._read() as con:
            snapshot, _scopes = self._revision(con, actor, page_id, request.to_version)
        spec = {**snapshot["spec"], "version": request.base_version + 1}
        return self._preview(actor, validated(PageDocument, stamp_binding_state(spec)), "ROLLBACK",
                             request.base_version)

    def _draft_row(self, con, actor, preview_id):
        opaque(preview_id, label="preview_id")
        row = con.execute("SELECT * FROM previews WHERE owner=? AND preview_id=?",
                          (actor.actor_id, preview_id)).fetchone()
        if row is None:
            raise fault("NOT_FOUND", 404)
        return row

    def preview(self, actor, preview_id):
        self._access(actor)
        with self._read() as con:
            row = self._draft_row(con, actor, preview_id)
            snapshot, _ = self._decode(actor, row, version=row["base_version"] + 1)
        return {"preview_id": preview_id, "status": row["status"], "operation": row["operation"],
                "base_version": row["base_version"], "expires_at_ms": row["expires_ms"], "snapshot": snapshot}

    def cancel(self, actor, preview_id):
        self._access(actor, write=True)
        with transaction(self.path, unavailable=UNAVAILABLE) as con:
            row = self._draft_row(con, actor, preview_id)
            self._decode(actor, row, version=row["base_version"] + 1)
            if row["status"] == "APPLIED":
                raise fault()
            con.execute("UPDATE previews SET status='CANCELLED' WHERE owner=? AND preview_id=?",
                        (actor.actor_id, preview_id))
        return {"preview_id": preview_id, "status": "CANCELLED"}

    def confirm(self, actor, preview_id, key):
        self._access(actor, write=True)
        key = validate_key(key)
        with transaction(self.path, unavailable=UNAVAILABLE) as con:
            row = self._draft_row(con, actor, preview_id)
            version = row["base_version"] + 1
            snapshot, _ = self._decode(actor, row, version=version)
            receipt = con.execute("SELECT preview_id FROM receipts WHERE owner=? AND key=?",
                                  (actor.actor_id, key)).fetchone()
            if receipt is not None and receipt["preview_id"] != preview_id:
                raise fault("IDEMPOTENCY_CONFLICT")
            if row["status"] == "APPLIED":
                saved, _ = self._revision(con, actor, row["page_id"], version)
                con.execute("INSERT OR IGNORE INTO receipts VALUES (?,?,?)", (actor.actor_id, key, preview_id))
                return saved
            if row["status"] == "CANCELLED":
                raise fault("PREVIEW_CANCELLED")
            if self.clock() >= row["expires_ms"]:
                raise fault("PREVIEW_EXPIRED")
            if row["base_version"]:
                if self._head(con, actor, row["page_id"]) != row["base_version"]:
                    raise fault()
                con.execute("UPDATE heads SET version=? WHERE owner=? AND page_id=?",
                            (version, actor.actor_id, row["page_id"]))
            else:
                con.execute("INSERT INTO heads VALUES (?,?,?)", (actor.actor_id, row["page_id"], version))
            con.execute("INSERT INTO revisions VALUES (?,?,?,?,?,?,?)", (actor.actor_id, row["page_id"], version,
                        row["operation"], self.clock(), row["payload"], row["digest"]))
            con.execute("UPDATE previews SET status='APPLIED' WHERE owner=? AND preview_id=?",
                        (actor.actor_id, preview_id))
            con.execute("INSERT INTO receipts VALUES (?,?,?)", (actor.actor_id, key, preview_id))
            return snapshot
