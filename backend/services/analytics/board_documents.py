"""Durable library canvas. Drafts never change the published head.

One connection per operation, immutable snapshots, monotonic rollback versions,
current grants on every read/replay, and compare-and-swap inside BEGIN IMMEDIATE.
This file never dispatches a model or opens a business DuckDB.
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

from backend.contracts.board_spec import (
    BoardDocument, BoardDraft, BoardLayoutPreview, BoardPatchPreview, BoardRollbackPreview, BoardSnapshot,
    BoardEditSelection, BoardEditProposal, WaterfallFacts, FunnelFacts,
)
from backend.contracts.analytics_query import canonical_json
from backend.contracts.competition_computed import DATA_SCOPE
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, require
from backend.services.analytics.waterfall_pack import waterfall_pack_enabled
from backend.services.analytics.funnel_pack import funnel_pack_enabled
from backend.services.analytics.first_purchase.asset_state import (
    connect, initialize_sqlite, now_ms, opaque, transaction, validate_key,
)

UNAVAILABLE = "看板保存库暂不可用，已保存版本未被本次操作替换。"
DDL = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE heads (
    owner TEXT NOT NULL, board_id TEXT NOT NULL, version INTEGER NOT NULL,
    PRIMARY KEY(owner, board_id)
);
CREATE TABLE revisions (
    owner TEXT NOT NULL, board_id TEXT NOT NULL, version INTEGER NOT NULL,
    operation TEXT NOT NULL, created_ms INTEGER NOT NULL,
    payload TEXT NOT NULL, digest TEXT NOT NULL,
    PRIMARY KEY(owner, board_id, version)
);
CREATE TABLE previews (
    owner TEXT NOT NULL, preview_id TEXT NOT NULL, board_id TEXT NOT NULL,
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

# Additive extension of the v1 snapshot database. No rewrite of existing boards,
# revisions or receipt rows; old readers may ignore this table. Installation and
# proposal/cancellation are transactional. The extension has its own version.
EDIT_DDL = """CREATE TABLE IF NOT EXISTS edit_contexts (
    owner TEXT NOT NULL, edit_context_id TEXT NOT NULL,
    board_id TEXT NOT NULL, base_version INTEGER NOT NULL, block_id TEXT NOT NULL,
    session_id TEXT NOT NULL, expires_ms INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('OPEN','PROPOSED','CANCELLED','APPLIED')),
    preview_id TEXT, PRIMARY KEY(owner, edit_context_id), UNIQUE(owner, preview_id),
    FOREIGN KEY(owner, preview_id) REFERENCES previews(owner, preview_id)
)"""


@dataclass(frozen=True)
class ResolvedBoardFacts:
    facts: dict
    required_scopes: frozenset[str]


def fault(code="VERSION_CONFLICT", status=409):
    messages = {
        "VERSION_CONFLICT": "看板版本已变化，请重新读取后预览；原版本未被覆盖。",
        "NOT_FOUND": "看板或草稿不存在，或当前身份不可见。",
        "PREVIEW_CANCELLED": "草稿已取消，不能保存。",
        "PREVIEW_EXPIRED": "草稿已过期，请重新预览。",
        "IDEMPOTENCY_CONFLICT": "该幂等键已用于另一份草稿。",
        "BINDING_CORRUPT": "看板快照完整性校验失败，请保留状态并检查。",
        "INVALID_BOARD": "看板配置或布局不符合组件合同。",
        "RESULT_UNAVAILABLE": "没有可绑定的当前会话结果，请先完成对应问数。",
        "EDIT_CANCELLED": "组件编辑已取消，请重新点选组件。",
        "EDIT_EXPIRED": "组件编辑上下文已过期，请重新点选组件。",
        "EDIT_PENDING": "当前会话已有待处理的组件编辑，请先确认或取消。",
        "EDIT_PROPOSED": "该组件编辑已生成预览，请先确认或取消，不重复修改。",
    }
    return AnalyticsError(status, code, messages[code])


def validated(model, payload):
    try:
        return model.model_validate(payload)
    except (ValidationError, ValueError, TypeError) as error:
        raise fault("INVALID_BOARD", 422) from error


class BoardDocumentStore:
    def __init__(self, directory: Path, *,
                 resolve_facts: Callable[[AnalyticsPrincipal, str, str], ResolvedBoardFacts] | None = None,
                 clock: Callable[[], int] = now_ms):
        self.path = directory.resolve() / "board_documents.sqlite3"
        self.resolve_facts = resolve_facts
        self.clock = clock
        initialize_sqlite(directory, self.path, application_id=1397572691, schema_version=1,
                          kind="library_board_documents", ddl=DDL, unavailable=UNAVAILABLE)
        with transaction(self.path, unavailable=UNAVAILABLE) as con:
            revision = con.execute("SELECT value FROM metadata WHERE key='edit_context_schema'").fetchone()
            if revision is not None and revision[0] != "1":
                raise fault("BINDING_CORRUPT")
            con.execute(EDIT_DDL)
            con.execute("INSERT OR IGNORE INTO metadata VALUES ('edit_context_schema','1')")

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
            snapshot = BoardSnapshot.model_validate(stored["snapshot"])
            scopes = stored["required_scopes"]
            if (not isinstance(scopes, list) or any(not isinstance(scope, str) or not scope for scope in scopes)
                    or snapshot.spec.board_id != row["board_id"] or snapshot.spec.version != version):
                raise ValueError("snapshot binding differs")
            refs = {block.source_result_id for block in snapshot.spec.blocks if block.source_result_id}
            if refs != set(snapshot.facts_by_result_id):
                raise ValueError("snapshot result bindings differ")
        except (ValueError, TypeError, KeyError, ValidationError) as error:
            raise fault("BINDING_CORRUPT") from error
        self._access(actor, scopes=scopes)
        return snapshot.model_dump(mode="json"), frozenset(scopes)

    @staticmethod
    def _head(con, actor, board_id):
        opaque(board_id, label="board_id")
        row = con.execute("SELECT version FROM heads WHERE owner=? AND board_id=?",
                          (actor.actor_id, board_id)).fetchone()
        if row is None:
            raise fault("NOT_FOUND", 404)
        return row["version"]

    def _revision(self, con, actor, board_id, version):
        row = con.execute("SELECT * FROM revisions WHERE owner=? AND board_id=? AND version=?",
                          (actor.actor_id, board_id, version)).fetchone()
        return self._decode(actor, row, version=version)

    def get(self, actor, board_id, version=None):
        self._access(actor)
        if version is not None and (type(version) is not int or not 1 <= version <= 9007199254740991):
            raise fault("INVALID_BOARD", 422)
        with self._read() as con:
            current = self._head(con, actor, board_id)
            return self._revision(con, actor, board_id, current if version is None else version)[0]

    def list(self, actor, *, limit=100, offset=0):
        self._access(actor)
        self._page(limit, offset)
        with self._read() as con:
            rows = con.execute("SELECT * FROM heads WHERE owner=? ORDER BY board_id LIMIT ? OFFSET ?",
                               (actor.actor_id, limit, offset)).fetchall()
            items = []
            for row in rows:
                try:
                    snapshot, _ = self._revision(con, actor, row["board_id"], row["version"])
                except AnalyticsError as error:
                    if error.status == 403:
                        continue
                    raise
                spec = snapshot["spec"]
                items.append({key: spec[key] for key in ("board_id", "title", "version", "session_id")})
            return items

    def list_session_saved_summaries(self, actor, session_id, *, limit=20, page_size=100, scan_limit=500):
        """Committed heads for one session. Truncation is explicit; a short page is not emptiness."""
        self._access(actor)
        opaque(session_id, label="session_id")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise fault("INVALID_BOARD", 422)
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise fault("INVALID_BOARD", 422)
        if type(scan_limit) is not int or not 1 <= scan_limit <= 500:
            raise fault("INVALID_BOARD", 422)
        items, unknown = [], False
        with self._read() as con:
            heads = con.execute(
                "SELECT board_id, version FROM heads WHERE owner=? ORDER BY board_id LIMIT ?",
                (actor.actor_id, scan_limit + 1)).fetchall()
            over_scan = len(heads) > scan_limit
            for head in heads[:scan_limit]:
                row = con.execute(
                    "SELECT * FROM revisions WHERE owner=? AND board_id=? AND version=?",
                    (actor.actor_id, head["board_id"], head["version"])).fetchone()
                if row is None:
                    unknown = True
                    continue
                try:
                    snapshot, _ = self._decode(actor, row, version=head["version"])
                except AnalyticsError as error:
                    if error.status == 403:
                        continue
                    if error.code in {"BINDING_CORRUPT", "NOT_FOUND"}:
                        unknown = True
                        continue
                    raise
                spec = snapshot["spec"]
                if spec.get("session_id") != session_id:
                    if spec.get("session_id") is None:
                        unknown = True
                    continue
                items.append({key: spec[key] for key in ("board_id", "title", "version")})
                if len(items) > limit:
                    break
        extra = items[limit:]
        shown = items[:limit]
        if unknown:
            status = "unknown"
        elif extra or over_scan:
            status = "truncated"
        else:
            status = "complete"
        return {"items": shown, "status": status}

    @staticmethod
    def _page(limit, offset):
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 1000000:
            raise fault("INVALID_BOARD", 422)

    def history(self, actor, board_id, *, limit=100, offset=0):
        self._access(actor)
        self._page(limit, offset)
        with self._read() as con:
            self._head(con, actor, board_id)
            rows = con.execute("SELECT * FROM revisions WHERE owner=? AND board_id=? ORDER BY version DESC LIMIT ? OFFSET ?",
                               (actor.actor_id, board_id, limit, offset)).fetchall()
            items = []
            for row in rows:
                self._decode(actor, row, version=row["version"])
                items.append({"version": row["version"], "operation": row["operation"], "created_at_ms": row["created_ms"]})
            return items

    def _facts(self, actor, spec, retained=None, scopes=frozenset()):
        retained = retained or {}
        facts = {}
        required_scopes = set(scopes)
        for block in spec.blocks:
            ref = block.source_result_id
            if ref is None or ref in facts:
                continue
            if ref in retained:
                facts[ref] = deepcopy(retained[ref])
                continue
            if self.resolve_facts is None:
                raise fault("RESULT_UNAVAILABLE", 422)
            resolved = self.resolve_facts(actor, spec.session_id, ref)
            self._access(actor, scopes=resolved.required_scopes)
            facts[ref] = deepcopy(resolved.facts)
            required_scopes.update(resolved.required_scopes)
        for block in spec.blocks:
            if block.kind in {"TEXT", "PROCESS", "TIMELINE"}:
                continue
            data = facts[block.source_result_id]
            if block.kind == "FUNNEL":
                if not funnel_pack_enabled():
                    raise AnalyticsError(422, "COMPONENT_UNSUPPORTED", "漏斗包未安装，不能生成或保存 FUNNEL 块。")
                try:
                    FunnelFacts.model_validate(data.get("funnel"))
                except (ValidationError, ValueError, TypeError) as error:
                    raise AnalyticsError(422, "COMPONENT_DATA", "当前结果没有同一人群的嵌套计数，不能生成漏斗；请获取对应结果。") from error
            if block.kind == "WATERFALL":
                if not waterfall_pack_enabled():
                    raise AnalyticsError(422, "COMPONENT_UNSUPPORTED", "瀑布包未安装，不能生成或保存 WATERFALL 块。")
                try:
                    WaterfallFacts.model_validate(data.get("waterfall"))
                except (ValidationError, ValueError, TypeError) as error:
                    raise AnalyticsError(422, "COMPONENT_DATA", "当前结果没有已对账的同单位贡献，不能生成瀑布；请获取对应结果。") from error
            if block.kind == "LINE" and data.get("time_series", data.get("series", {})).get("ordered") is not True:
                raise AnalyticsError(422, "COMPONENT_DATA", "当前结果不是有序时间序列，不能生成趋势；请获取对应结果或明确改用对比图。")
            if block.kind == "TABLE":
                fields = {column["key"] for column in data.get("table", {}).get("columns", [])}
                if (not set(block.props.columns) <= fields
                        or (block.props.sort_field and block.props.sort_field not in fields)):
                    raise AnalyticsError(422, "COMPONENT_DATA", "列或排序字段不在绑定结果中，请重新选择或问数。")
        return facts, required_scopes

    def _preview(self, actor, spec, operation, base_version, *, retained=None, scopes=frozenset(), edit_context=None):
        self._access(actor, write=True)
        facts, scopes = self._facts(actor, spec, retained, scopes)
        snapshot = {"spec": spec.model_dump(mode="json"), "facts_by_result_id": facts}
        payload = canonical_json({"snapshot": snapshot, "required_scopes": sorted(scopes)})
        if len(payload.encode()) > 2_000_000:
            raise fault("INVALID_BOARD", 422)
        preview_id = "preview_" + uuid4().hex
        expires = self.clock() + 30 * 60 * 1000
        with transaction(self.path, unavailable=UNAVAILABLE) as con:
            if base_version and self._head(con, actor, spec.board_id) != base_version:
                raise fault()
            if edit_context is not None:
                context = self._edit_row(con, actor, edit_context, session_id=spec.session_id, active=True)
                if context["status"] != "OPEN":
                    raise fault("EDIT_PROPOSED")
                if context["board_id"] != spec.board_id or context["base_version"] != base_version or operation != "PATCH":
                    raise fault("BINDING_CORRUPT")
                expires = min(expires, context["expires_ms"])
            con.execute("INSERT INTO previews VALUES (?,?,?,?,?,'PENDING',?,?,?)",
                        (actor.actor_id, preview_id, spec.board_id, base_version, operation, expires,
                         payload, hashlib.sha256(payload.encode()).hexdigest()))
            if edit_context is not None:
                con.execute("UPDATE edit_contexts SET status='PROPOSED', preview_id=? WHERE owner=? AND edit_context_id=?",
                            (preview_id, actor.actor_id, edit_context))
        return {"preview_id": preview_id, "status": "PENDING", "operation": operation,
                "base_version": base_version, "expires_at_ms": expires, "snapshot": snapshot}

    def generate(self, actor, request: BoardDraft):
        self._access(actor, write=True)
        spec = validated(BoardDocument, {**request.model_dump(mode="json"),
            "board_id": "board_" + uuid4().hex, "version": 1})
        return self._preview(actor, spec, "GENERATE", 0)

    def _base(self, actor, board_id, base_version):
        self._access(actor, write=True)
        with self._read() as con:
            if self._head(con, actor, board_id) != base_version:
                raise fault()
            return self._revision(con, actor, board_id, base_version)

    def patch(self, actor, board_id, request: BoardPatchPreview, *, edit_context=None):
        snapshot, scopes = self._base(actor, board_id, request.base_version)
        spec = deepcopy(snapshot["spec"])
        block = next((block for block in spec["blocks"] if block["block_id"] == request.block_id), None)
        if block is None:
            raise fault("NOT_FOUND", 404)
        changes = request.changes.model_dump(mode="json", exclude_unset=True)
        if changes.get("kind", block["kind"]) != block["kind"]:
            # Props of one kind must not leak to another. Omitted new props use catalogue defaults.
            block["props"] = {}
        if "props" in changes:
            changes["props"] = {**block["props"], **changes["props"]}
        block.update(changes)
        spec["version"] += 1
        return self._preview(actor, validated(BoardDocument, spec), "PATCH", request.base_version,
                             retained=snapshot["facts_by_result_id"], scopes=scopes, edit_context=edit_context)

    def _edit_row(self, con, actor, edit_context_id, *, session_id=None, active=False):
        opaque(edit_context_id, label="edit_context_id")
        row = con.execute("SELECT * FROM edit_contexts WHERE owner=? AND edit_context_id=?",
                          (actor.actor_id, edit_context_id)).fetchone()
        if row is None or (session_id is not None and row["session_id"] != session_id):
            raise fault("NOT_FOUND", 404)
        snapshot, _ = self._revision(con, actor, row["board_id"], row["base_version"])
        if (snapshot["spec"]["session_id"] != row["session_id"]
                or row["block_id"] not in {block["block_id"] for block in snapshot["spec"]["blocks"]}):
            raise fault("BINDING_CORRUPT")
        if active:
            if row["status"] == "CANCELLED":
                raise fault("EDIT_CANCELLED")
            if row["status"] == "APPLIED":
                raise fault("EDIT_PROPOSED")
            if self.clock() >= row["expires_ms"]:
                raise fault("EDIT_EXPIRED")
            if self._head(con, actor, row["board_id"]) != row["base_version"]:
                raise fault()
        return row

    def select_edit(self, actor, board_id, request: BoardEditSelection):
        self._access(actor, write=True)
        context_id = "edit_" + uuid4().hex
        with transaction(self.path, unavailable=UNAVAILABLE) as con:
            if self._head(con, actor, board_id) != request.base_version:
                raise fault()
            snapshot, _ = self._revision(con, actor, board_id, request.base_version)
            if request.block_id not in {block["block_id"] for block in snapshot["spec"]["blocks"]}:
                raise fault("NOT_FOUND", 404)
            session_id = snapshot["spec"]["session_id"]
            # One unresolved selection per native conversation, including other tabs.
            # Stale/expired selections cannot apply and need not block a fresh one.
            pending = con.execute("""SELECT 1 FROM edit_contexts e JOIN heads h
                ON h.owner=e.owner AND h.board_id=e.board_id AND h.version=e.base_version
                WHERE e.owner=? AND e.session_id=? AND e.status IN ('OPEN','PROPOSED') AND e.expires_ms>?""",
                (actor.actor_id, session_id, self.clock())).fetchone()
            if pending is not None:
                raise fault("EDIT_PENDING")
            con.execute("INSERT INTO edit_contexts VALUES (?,?,?,?,?,?,?,'OPEN',NULL)",
                        (actor.actor_id, context_id, board_id, request.base_version, request.block_id,
                         session_id, self.clock() + 30 * 60 * 1000))
        return self.edit_context(actor, context_id, session_id=session_id)

    def edit_context(self, actor, edit_context_id, *, session_id):
        self._access(actor, write=True)
        with self._read() as con:
            row = self._edit_row(con, actor, edit_context_id, session_id=session_id, active=True)
            snapshot, _ = self._revision(con, actor, row["board_id"], row["base_version"])
            block = next(block for block in snapshot["spec"]["blocks"] if block["block_id"] == row["block_id"])
            ref = block.get("source_result_id")
            return {"schema_version": "board-edit-context/v1", **{key: row[key] for key in (
                "edit_context_id", "board_id", "base_version", "block_id", "session_id", "status", "preview_id")},
                "expires_at_ms": row["expires_ms"], "block": block,
                "facts_by_result_id": {ref: snapshot["facts_by_result_id"][ref]} if ref else {}}

    def current_edit(self, actor, board_id):
        self._access(actor, write=True)
        with self._read() as con:
            version = self._head(con, actor, board_id)
            snapshot, _ = self._revision(con, actor, board_id, version)
            row = con.execute("""SELECT edit_context_id FROM edit_contexts WHERE owner=? AND board_id=?
                AND base_version=? AND status IN ('OPEN','PROPOSED') AND expires_ms>?""",
                (actor.actor_id, board_id, version, self.clock())).fetchone()
        return self.edit_context(actor, row[0], session_id=snapshot["spec"]["session_id"]) if row else None

    def propose_edit(self, actor, edit_context_id, request: BoardEditProposal):
        context = self.edit_context(actor, edit_context_id, session_id=request.session_id)
        if context["status"] != "OPEN":
            raise fault("EDIT_PROPOSED")
        # Only the saved UI selection supplies the target and version.
        return self.patch(actor, context["board_id"], BoardPatchPreview(
            base_version=context["base_version"], block_id=context["block_id"], changes=request.changes),
            edit_context=edit_context_id)

    def cancel_edit(self, actor, edit_context_id):
        self._access(actor, write=True)
        with transaction(self.path, unavailable=UNAVAILABLE) as con:
            row = self._edit_row(con, actor, edit_context_id)
            if row["status"] == "APPLIED":
                raise fault("EDIT_PROPOSED")
            if row["preview_id"]:
                con.execute("UPDATE previews SET status='CANCELLED' WHERE owner=? AND preview_id=? AND status='PENDING'",
                            (actor.actor_id, row["preview_id"]))
            con.execute("UPDATE edit_contexts SET status='CANCELLED' WHERE owner=? AND edit_context_id=?",
                        (actor.actor_id, edit_context_id))
        return {"edit_context_id": edit_context_id, "status": "CANCELLED"}

    def layout(self, actor, board_id, request: BoardLayoutPreview):
        snapshot, scopes = self._base(actor, board_id, request.base_version)
        spec = deepcopy(snapshot["spec"])
        changes = {item.block_id: item.layout.model_dump() for item in request.layouts}
        ids = {block["block_id"] for block in spec["blocks"]}
        if len(changes) != len(request.layouts) or not changes.keys() <= ids:
            raise fault("INVALID_BOARD", 422)
        for block in spec["blocks"]:
            if block["block_id"] in changes:
                block["layout"] = changes[block["block_id"]]
        spec["version"] += 1
        return self._preview(actor, validated(BoardDocument, spec), "LAYOUT", request.base_version,
                             retained=snapshot["facts_by_result_id"], scopes=scopes)

    def rollback(self, actor, board_id, request: BoardRollbackPreview):
        self._base(actor, board_id, request.base_version)
        if request.to_version >= request.base_version:
            raise fault("INVALID_BOARD", 422)
        with self._read() as con:
            snapshot, scopes = self._revision(con, actor, board_id, request.to_version)
        spec = {**snapshot["spec"], "version": request.base_version + 1}
        return self._preview(actor, validated(BoardDocument, spec), "ROLLBACK", request.base_version,
                             retained=snapshot["facts_by_result_id"], scopes=scopes)

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
            con.execute("UPDATE edit_contexts SET status='CANCELLED' WHERE owner=? AND preview_id=?",
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
                # Even a new key for the same confirmed draft cannot create another revision.
                saved, _ = self._revision(con, actor, row["board_id"], version)
                con.execute("INSERT OR IGNORE INTO receipts VALUES (?,?,?)", (actor.actor_id, key, preview_id))
                return saved
            if row["status"] == "CANCELLED":
                raise fault("PREVIEW_CANCELLED")
            if self.clock() >= row["expires_ms"]:
                raise fault("PREVIEW_EXPIRED")
            selection = con.execute("SELECT edit_context_id FROM edit_contexts WHERE owner=? AND preview_id=?",
                                    (actor.actor_id, preview_id)).fetchone()
            if selection is not None:
                self._edit_row(con, actor, selection[0], session_id=snapshot["spec"]["session_id"], active=True)
            if row["base_version"]:
                if self._head(con, actor, row["board_id"]) != row["base_version"]:
                    raise fault()
                con.execute("UPDATE heads SET version=? WHERE owner=? AND board_id=?",
                            (version, actor.actor_id, row["board_id"]))
            else:
                con.execute("INSERT INTO heads VALUES (?,?,?)", (actor.actor_id, row["board_id"], version))
            con.execute("INSERT INTO revisions VALUES (?,?,?,?,?,?,?)", (actor.actor_id, row["board_id"], version,
                        row["operation"], self.clock(), row["payload"], row["digest"]))
            con.execute("UPDATE previews SET status='APPLIED' WHERE owner=? AND preview_id=?", (actor.actor_id, preview_id))
            con.execute("UPDATE edit_contexts SET status='APPLIED' WHERE owner=? AND preview_id=?", (actor.actor_id, preview_id))
            con.execute("INSERT INTO receipts VALUES (?,?,?)", (actor.actor_id, key, preview_id))
            return snapshot
