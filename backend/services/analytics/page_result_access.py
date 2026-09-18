"""Read-only authorized result_ref/data_ref access for free HTML pages.

New queries stay on the native Agent. Snapshots are injected fixtures. Cache
hits re-check actor, unit, time, version and revocation.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import re
from threading import RLock
from typing import Any, Callable
from uuid import uuid4

from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, require
from backend.services.analytics.first_purchase.asset_state import now_ms, timestamp

PROTOCOL = "free-page-bridge/v1"
SCHEMA_VERSION = "free-page/v1"
DATA_SCOPE = "free-page-result-fixture"
CAPABILITY = "dashboard:read"
IDENTITY = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
BINDING_STATES = ("UNBOUND_SAMPLE", "BOUND_VERIFIED", "BOUND_STALE")
READ_MODES = ("summary", "page", "range")
PAGE_TO_HOST_OPS = ("data.read", "data.cancel")
FORBIDDEN_OPS = ("sql", "save", "http.fetch", "credential.read")
FORBIDDEN_FIELDS = frozenset({
    "sql", "token", "query", "save", "credential", "authorization", "fetch",
    "url", "headers", "http", "password", "secret",
})
SUMMARY_FIELDS = ("unit", "time_range", "queried_at", "source", "row_count")
READ_FIELDS = frozenset({
    "op", "request_id", "result_ref", "data_ref", "mode", "cursor", "limit",
    "start", "end", "instance_id",
})
CANCEL_FIELDS = frozenset({"op", "request_id", "instance_id"})
MAX_RESPONSE_BYTES = 65536
MAX_CUMULATIVE_ROWS = 2000
MAX_PAGE_LIMIT = 50
SUMMARY_PREVIEW_ROWS = 5

_FAULTS = {
    "FORBIDDEN": (403, "当前身份无权读取该授权结果。"),
    "NOT_FOUND": (404, "授权结果不存在，或当前身份不可见。"),
    "RESULT_UNAVAILABLE": (409, "授权结果当前不可用，页面仍可打开；请改走原生问数。"),
    "RESULT_STALE": (409, "授权结果已过期或单位/时间/版本不符，宿主标记为过期。"),
    "RESULT_REVOKED": (403, "授权结果已被撤销，不能继续读取。"),
    "BRIDGE_UNKNOWN_OP": (400, "页面请求了未授权的桥接操作。"),
    "BRIDGE_NONCE": (409, "桥接 nonce 无效或已使用，请重新握手。"),
    "BRIDGE_EXPIRED_INSTANCE": (409, "页面实例已过期，请重新握手。"),
    "INVALID_PAGE": (422, "页面绑定或读取请求不符合合同。"),
    "PACKAGE_TOO_LARGE": (413, "单次或累计读取超过额度。"),
}


def fault(code: str) -> AnalyticsError:
    status, message = _FAULTS[code]
    return AnalyticsError(status, code, message)


def identity(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not IDENTITY.fullmatch(value):
        raise fault("INVALID_PAGE")
    return value


def _record(value: object) -> bool:
    return isinstance(value, dict) and not isinstance(value, bool)


def _time_range(value: object) -> dict[str, str]:
    if (not _record(value) or set(value) != {"start", "end"}
            or not isinstance(value["start"], str) or not isinstance(value["end"], str)
            or not value["start"] or not value["end"] or len(value["start"]) > 32
            or len(value["end"]) > 32):
        raise fault("INVALID_PAGE")
    return {"start": value["start"], "end": value["end"]}


@dataclass(frozen=True)
class AuthorizedSnapshot:
    result_ref: str
    owner: str
    unit: str
    time_range: dict[str, str]
    queried_at: str
    source: str
    result_version: int
    expires_at_ms: int | None
    rows: tuple[dict[str, Any], ...]
    data_scope: str = DATA_SCOPE
    session_id: str = ""


def default_synthetic_snapshot(*, owner: str = "alice", row_count: int = 120, **overrides) -> dict:
    rows = [{"i": index, "label": f"row-{index}", "value": index * 10} for index in range(row_count)]
    payload = {
        "result_ref": "result_fixture_1",
        "owner": owner,
        "unit": "CNY 元",
        "time_range": {"start": "2026-04-30", "end": "2026-07-28"},
        "queried_at": "2026-07-28T12:00:00.000+00:00",
        "source": "合成结果夹具 · result_fixture_1",
        "result_version": 1,
        "expires_at_ms": None,
        "rows": rows,
        "session_id": "native_session_fixture",
        "data_scope": DATA_SCOPE,
    }
    payload.update(overrides)
    return payload


def _manifest_entries(manifest: object) -> list[dict[str, Any]]:
    if manifest is None:
        return []
    if not _record(manifest):
        raise fault("INVALID_PAGE")
    allowed = {"bindings", "result_refs"}
    if any(key not in allowed for key in manifest):
        raise fault("INVALID_PAGE")
    refs = manifest.get("result_refs", [])
    bindings = manifest.get("bindings", [])
    if not isinstance(refs, list) or not isinstance(bindings, list):
        raise fault("INVALID_PAGE")
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in refs:
        ref = identity(item, label="result_ref")
        if ref not in seen:
            entries.append({"result_ref": ref})
            seen.add(ref)
    for item in bindings:
        if not _record(item):
            raise fault("INVALID_PAGE")
        allowed_binding = {
            "result_ref", "data_ref", "unit", "time_range", "result_version",
        }
        if any(key not in allowed_binding for key in item):
            raise fault("INVALID_PAGE")
        if "result_ref" not in item:
            raise fault("INVALID_PAGE")
        ref = identity(item["result_ref"], label="result_ref")
        entry = {"result_ref": ref}
        if "data_ref" in item:
            entry["data_ref"] = identity(item["data_ref"], label="data_ref")
        if "unit" in item:
            if not isinstance(item["unit"], str) or not item["unit"] or len(item["unit"]) > 64:
                raise fault("INVALID_PAGE")
            entry["unit"] = item["unit"]
        if "time_range" in item:
            entry["time_range"] = _time_range(item["time_range"])
        if "result_version" in item:
            version = item["result_version"]
            if type(version) is not int or version < 1:
                raise fault("INVALID_PAGE")
            entry["result_version"] = version
        if ref in seen:
            merged = next(existing for existing in entries if existing["result_ref"] == ref)
            merged.update(entry)
        else:
            entries.append(entry)
            seen.add(ref)
    return entries


class PageResultAccess:
    """In-memory authorized snapshot reader. Not a page asset store."""

    def __init__(self, *, clock: Callable[[], int] = now_ms):
        self.clock = clock
        self._lock = RLock()
        self._snapshots: dict[str, AuthorizedSnapshot] = {}
        self._revoked: set[str] = set()
        self._data_refs: dict[str, tuple[str, str, int]] = {}
        self._cancelled: set[tuple[str, str]] = set()
        self._consumed_rows: dict[tuple[str, str], int] = {}
        self._cache: dict[tuple[str, str, int], AuthorizedSnapshot] = {}

    def put_snapshot(self, payload: dict) -> AuthorizedSnapshot:
        if not _record(payload):
            raise fault("INVALID_PAGE")
        result_ref = identity(payload.get("result_ref"), label="result_ref")
        owner = identity(payload.get("owner"), label="owner")
        unit = payload.get("unit")
        if not isinstance(unit, str) or not unit or len(unit) > 64:
            raise fault("INVALID_PAGE")
        time_range = _time_range(payload.get("time_range"))
        queried_at = payload.get("queried_at")
        if not isinstance(queried_at, str) or not queried_at or len(queried_at) > 64:
            queried_at = timestamp(self.clock())
        source = payload.get("source")
        if not isinstance(source, str) or not source or len(source) > 200:
            raise fault("INVALID_PAGE")
        version = payload.get("result_version", 1)
        if type(version) is not int or version < 1:
            raise fault("INVALID_PAGE")
        expires = payload.get("expires_at_ms")
        if expires is not None and (type(expires) is not int or expires < 1):
            raise fault("INVALID_PAGE")
        rows = payload.get("rows")
        if not isinstance(rows, list) or len(rows) > MAX_CUMULATIVE_ROWS:
            raise fault("INVALID_PAGE")
        copied = []
        for row in rows:
            if not _record(row):
                raise fault("INVALID_PAGE")
            copied.append(deepcopy(row))
        scope = payload.get("data_scope", DATA_SCOPE)
        if not isinstance(scope, str) or not scope:
            raise fault("INVALID_PAGE")
        session_id = payload.get("session_id", "")
        if session_id != "":
            identity(session_id, label="session_id")
        snapshot = AuthorizedSnapshot(
            result_ref=result_ref, owner=owner, unit=unit, time_range=time_range,
            queried_at=queried_at, source=source, result_version=version,
            expires_at_ms=expires, rows=tuple(copied), data_scope=scope,
            session_id=session_id,
        )
        with self._lock:
            self._snapshots[result_ref] = snapshot
            self._revoked.discard(result_ref)
            self._cache = {
                key: value for key, value in self._cache.items() if key[1] != result_ref
            }
        return snapshot

    def revoke(self, actor: AnalyticsPrincipal, result_ref: str) -> None:
        self._access(actor)
        ref = identity(result_ref, label="result_ref")
        with self._lock:
            snapshot = self._snapshots.get(ref)
            if snapshot is None or snapshot.owner != actor.actor_id:
                raise fault("NOT_FOUND")
            self._revoked.add(ref)

    def cancel(self, actor: AnalyticsPrincipal, request: dict) -> dict[str, str]:
        self._access(actor)
        payload = self._request(request, CANCEL_FIELDS, op="data.cancel")
        request_id = identity(payload.get("request_id"), label="request_id")
        with self._lock:
            self._cancelled.add((actor.actor_id, request_id))
        return {"request_id": request_id, "status": "CANCELLED"}

    def binding_state(self, actor: AnalyticsPrincipal, manifest: object) -> dict[str, Any]:
        self._access(actor)
        entries = _manifest_entries(manifest)
        if not entries:
            return {
                "binding_state": "UNBOUND_SAMPLE",
                "verified": False,
                "refs": [],
                "reasons": [],
                "host_source": {
                    "endorses": "result_provenance",
                    "does_not_endorse": "page_dom",
                },
            }
        refs = []
        reasons: list[str] = []
        verified = 0
        for entry in entries:
            item, reason = self._probe(actor, entry)
            refs.append(item)
            if reason:
                reasons.append(reason)
            else:
                verified += 1
        state = "BOUND_VERIFIED" if verified == len(entries) else "BOUND_STALE"
        return {
            "binding_state": state,
            "verified": state == "BOUND_VERIFIED",
            "refs": refs,
            "reasons": reasons,
            "host_source": {
                "endorses": "result_provenance",
                "does_not_endorse": "page_dom",
            },
        }

    def read(self, actor: AnalyticsPrincipal, request: dict, *, manifest: object) -> dict[str, Any]:
        self._access(actor)
        payload = self._request(request, READ_FIELDS, op="data.read")
        request_id = payload.get("request_id")
        if request_id is not None:
            request_id = identity(request_id, label="request_id")
            self._raise_if_cancelled(actor, request_id)
        instance_id = payload.get("instance_id")
        if instance_id is not None:
            instance_id = identity(instance_id, label="instance_id")
        mode = payload.get("mode", "summary")
        if mode not in READ_MODES:
            raise fault("INVALID_PAGE")
        snapshot, binding = self._resolve(actor, payload, manifest)
        self._raise_if_cancelled(actor, request_id)
        rows, cursor = self._slice(snapshot, payload, mode)
        data_ref = self._issue_data_ref(actor, snapshot)
        summary = {
            "unit": snapshot.unit,
            "time_range": dict(snapshot.time_range),
            "queried_at": snapshot.queried_at,
            "source": snapshot.source,
            "row_count": len(snapshot.rows),
        }
        body = {
            "ok": True,
            "op": "data.read",
            "mode": mode,
            "result_ref": snapshot.result_ref,
            "data_ref": data_ref,
            "result_version": snapshot.result_version,
            "summary": summary,
            "rows": rows,
            "cursor": cursor,
            "binding_state": "BOUND_VERIFIED",
            "host_source": {
                "label": snapshot.source,
                "endorses": "result_provenance",
                "does_not_endorse": "page_dom",
                "session_id": snapshot.session_id or None,
            },
            "expected": {
                key: binding[key]
                for key in ("unit", "time_range", "result_version")
                if key in binding
            },
        }
        encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        if len(encoded.encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise fault("PACKAGE_TOO_LARGE")
        self._consume(actor, instance_id, len(rows))
        self._raise_if_cancelled(actor, request_id)
        return body

    def _access(self, actor: AnalyticsPrincipal) -> None:
        require(actor, CAPABILITY, data_scope=DATA_SCOPE)

    def _request(self, request: object, allowed: frozenset[str], *, op: str) -> dict[str, Any]:
        if not _record(request):
            raise fault("INVALID_PAGE")
        if any(field in request for field in FORBIDDEN_FIELDS):
            raise fault("BRIDGE_UNKNOWN_OP")
        if request.get("op") in FORBIDDEN_OPS:
            raise fault("BRIDGE_UNKNOWN_OP")
        if request.get("op") not in PAGE_TO_HOST_OPS:
            raise fault("BRIDGE_UNKNOWN_OP")
        if request.get("op") != op:
            raise fault("BRIDGE_UNKNOWN_OP")
        if any(key not in allowed for key in request):
            raise fault("INVALID_PAGE")
        return request

    def _raise_if_cancelled(self, actor: AnalyticsPrincipal, request_id: str | None) -> None:
        if request_id is None:
            return
        with self._lock:
            cancelled = (actor.actor_id, request_id) in self._cancelled
        if cancelled:
            raise fault("RESULT_UNAVAILABLE")

    def _resolve(self, actor: AnalyticsPrincipal, payload: dict, manifest: object) -> tuple[AuthorizedSnapshot, dict]:
        has_ref = "result_ref" in payload
        has_data = "data_ref" in payload
        if has_ref == has_data:
            raise fault("INVALID_PAGE")
        entries = _manifest_entries(manifest)
        listed = {entry["result_ref"]: entry for entry in entries}
        with self._lock:
            if has_data:
                handle = identity(payload["data_ref"], label="data_ref")
                issued = self._data_refs.get(handle)
                if issued is None or issued[0] != actor.actor_id:
                    raise fault("NOT_FOUND")
                _, result_ref, pinned_version = issued
                if result_ref not in listed:
                    raise fault("FORBIDDEN")
                snapshot = self._authorized_snapshot(actor, result_ref)
                if snapshot.result_version != pinned_version:
                    raise fault("RESULT_STALE")
                binding = listed[result_ref]
            else:
                result_ref = identity(payload["result_ref"], label="result_ref")
                if result_ref not in listed:
                    raise fault("FORBIDDEN")
                snapshot = self._authorized_snapshot(actor, result_ref)
                binding = listed[result_ref]
            self._match_binding(snapshot, binding)
            cached = self._cache.get((actor.actor_id, snapshot.result_ref, snapshot.result_version))
            if cached is not None:
                snapshot = cached
            else:
                self._cache[(actor.actor_id, snapshot.result_ref, snapshot.result_version)] = snapshot
        return snapshot, binding

    def _authorized_snapshot(self, actor: AnalyticsPrincipal, result_ref: str) -> AuthorizedSnapshot:
        snapshot = self._snapshots.get(result_ref)
        if snapshot is None or snapshot.owner != actor.actor_id:
            raise fault("NOT_FOUND")
        if result_ref in self._revoked:
            raise fault("RESULT_REVOKED")
        if snapshot.data_scope not in actor.data_scopes:
            raise fault("FORBIDDEN")
        if snapshot.expires_at_ms is not None and self.clock() >= snapshot.expires_at_ms:
            raise fault("RESULT_STALE")
        return snapshot

    @staticmethod
    def _match_binding(snapshot: AuthorizedSnapshot, binding: dict) -> None:
        if binding.get("unit") is not None and binding["unit"] != snapshot.unit:
            raise fault("RESULT_STALE")
        if binding.get("time_range") is not None and binding["time_range"] != snapshot.time_range:
            raise fault("RESULT_STALE")
        if binding.get("result_version") is not None and binding["result_version"] != snapshot.result_version:
            raise fault("RESULT_STALE")

    def _probe(self, actor: AnalyticsPrincipal, entry: dict) -> tuple[dict[str, Any], str | None]:
        ref = entry["result_ref"]
        item = {
            "result_ref": ref,
            "status": "UNAVAILABLE",
            "unit": None,
            "time_range": None,
            "queried_at": None,
            "source": None,
            "result_version": None,
        }
        try:
            with self._lock:
                snapshot = self._authorized_snapshot(actor, ref)
                self._match_binding(snapshot, entry)
            item.update({
                "status": "VERIFIED",
                "unit": snapshot.unit,
                "time_range": dict(snapshot.time_range),
                "queried_at": snapshot.queried_at,
                "source": snapshot.source,
                "result_version": snapshot.result_version,
            })
            return item, None
        except AnalyticsError as error:
            item["status"] = error.code
            return item, error.code

    def _slice(self, snapshot: AuthorizedSnapshot, payload: dict, mode: str) -> tuple[list[dict], str | None]:
        total = len(snapshot.rows)
        if mode == "summary":
            rows = [deepcopy(row) for row in snapshot.rows[:SUMMARY_PREVIEW_ROWS]]
            cursor = self._cursor(snapshot, len(rows)) if total > len(rows) else None
            return rows, cursor
        limit = payload.get("limit", MAX_PAGE_LIMIT)
        if type(limit) is not int or not 1 <= limit <= MAX_PAGE_LIMIT:
            raise fault("INVALID_PAGE")
        if mode == "page":
            offset = 0
            if payload.get("cursor") is not None:
                offset = self._parse_cursor(snapshot, payload["cursor"])
            if payload.get("start") is not None or payload.get("end") is not None:
                raise fault("INVALID_PAGE")
            end = min(offset + limit, total)
            rows = [deepcopy(row) for row in snapshot.rows[offset:end]]
            cursor = self._cursor(snapshot, end) if end < total else None
            return rows, cursor
        if payload.get("cursor") is not None:
            raise fault("INVALID_PAGE")
        start = payload.get("start", 0)
        end = payload.get("end", start + limit)
        if type(start) is not int or type(end) is not int or start < 0 or end < start or end > total:
            raise fault("INVALID_PAGE")
        if end - start > MAX_PAGE_LIMIT:
            raise fault("PACKAGE_TOO_LARGE")
        return [deepcopy(row) for row in snapshot.rows[start:end]], None

    @staticmethod
    def _cursor(snapshot: AuthorizedSnapshot, offset: int) -> str:
        return f"v{snapshot.result_version}:{offset}"

    @staticmethod
    def _parse_cursor(snapshot: AuthorizedSnapshot, cursor: object) -> int:
        if not isinstance(cursor, str) or not re.fullmatch(r"v[1-9][0-9]{0,15}:[0-9]{1,16}", cursor):
            raise fault("INVALID_PAGE")
        version_text, offset_text = cursor[1:].split(":", 1)
        version = int(version_text)
        offset = int(offset_text)
        if version != snapshot.result_version:
            raise fault("RESULT_STALE")
        if offset > len(snapshot.rows):
            raise fault("INVALID_PAGE")
        return offset

    def _consume(self, actor: AnalyticsPrincipal, instance_id: str | None, count: int) -> None:
        key = (actor.actor_id, instance_id or "_")
        with self._lock:
            used = self._consumed_rows.get(key, 0) + count
            if used > MAX_CUMULATIVE_ROWS:
                raise fault("PACKAGE_TOO_LARGE")
            self._consumed_rows[key] = used

    def _issue_data_ref(self, actor: AnalyticsPrincipal, snapshot: AuthorizedSnapshot) -> str:
        handle = "data_" + uuid4().hex
        with self._lock:
            self._data_refs[handle] = (actor.actor_id, snapshot.result_ref, snapshot.result_version)
        return handle
