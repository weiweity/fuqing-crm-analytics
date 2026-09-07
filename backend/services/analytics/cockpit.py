"""Append-only private cockpit store.

Independent SQLite; not jobs.py, saved_analyses.py, or an HTTP/OpenAPI surface.
Cards freeze SNAPSHOT run_id/digest/facts supplied by the caller. This module
does not compute channel-follow-up metrics. Owner always comes from the server
principal. Preview never writes. Apply requires If-Match; version conflicts
are 409. Undo writes a new version from a prior config and does not delete
historical rows.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import sqlite3
import stat
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from pydantic import ValidationError

from backend.contracts.analytics_query import (
    B0_RUN_SCHEMA,
    ChannelFollowupFacts,
    ChannelFollowupResolvedFilters,
)
from backend.contracts.analytics_query_run import QUERY_DATA_SCOPE
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, require
from backend.services.analytics.resource_profile import canonical_json, content_hash

DASHBOARD_SCHEMA = "analytics-cockpit/v1"
FILTER_SCHEMA = "analytics-cockpit-filters/v1"
DATA_SCOPE = QUERY_DATA_SCOPE
CAPABILITY_READ = "dashboard:read"
CAPABILITY_WRITE = "dashboard:update"
APPLICATION_ID = 1397572401  # SMC1; distinct from SMA1 and SMB0.
STATE_SCHEMA_VERSION = 1
MAX_CARDS = 20
GRID_COLUMNS = 12
MIN_SPAN = 2
MAX_SPAN = 12
OPAQUE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
ANALYSIS_ID = re.compile(r"^analysis_[A-Za-z0-9_.:-]{1,118}$")
DEFAULT_TITLE = "我的驾驶舱"
DEFAULT_GLOBAL_FILTERS = {"schema_version": FILTER_SCHEMA, "channel_ids": []}
PLUGIN_TABLE = {"type": "TABLE", "version": "analytics-visual-table/v1"}
PLUGIN_LINE = {"type": "LINE", "version": "analytics-visual-line/v1"}
PLUGIN_CATALOG = {
    "TABLE": PLUGIN_TABLE,
    "LINE": PLUGIN_LINE,
    "BAR": {"type": "BAR", "version": "analytics-visual-bar/v1"},
    "METRIC": {"type": "METRIC", "version": "analytics-visual-metric/v1"},
    "EVIDENCE": {"type": "EVIDENCE", "version": "analytics-visual-evidence/v1"},
}
AI_INTENTS = {
    "annotate-live": {
        "instruction": "这一块只看直播，其他不动",
        "display_overrides": {"title": "直播渠道快照"},
        "local_filters": {"channel_ids": ["A"]},
    },
    "trend-enlarge": {
        "instruction": "改成趋势图并放大",
        "plugin_ref": dict(PLUGIN_LINE),
        "layout_patch": {"w": 12, "h": 6},
    },
}
CREATE_FIELDS = frozenset({"title", "owner_id", "visibility"})
PATCH_FIELDS = frozenset({
    "op", "card_id", "scope", "analysis_ref", "snapshot", "facts", "limitations",
    "plugin_ref", "layout", "display_overrides", "local_filters", "filter_mapping",
    "intent", "restore_from_version",
})
SNAPSHOT_KEYS = frozenset({"run_id", "evidence_digest", "resolved_filters", "data_snapshot_ref", "as_of"})
B0_SCHEMAS = frozenset({B0_RUN_SCHEMA, "analytics-b0/v1", "analytics-run-b0/v1"})
FACT_FIELDS = frozenset({
    "snapshot", "facts", "analysis_ref", "filter_hash", "effective_spec_hash", "run_id", "evidence_digest",
})

_SCHEMA = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE owners (
    owner TEXT PRIMARY KEY,
    dashboard_id TEXT NOT NULL UNIQUE
);
CREATE TABLE dashboards (
    dashboard_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK(version >= 1),
    owner TEXT NOT NULL,
    title TEXT NOT NULL,
    cards_json TEXT NOT NULL,
    global_filters_json TEXT NOT NULL,
    created_ms INTEGER NOT NULL,
    PRIMARY KEY(dashboard_id, version)
);
CREATE INDEX dashboards_owner ON dashboards(owner, created_ms, dashboard_id);
CREATE TABLE idempotency (
    actor TEXT NOT NULL, operation TEXT NOT NULL, target TEXT NOT NULL, key TEXT NOT NULL,
    request_hash TEXT NOT NULL, response_json TEXT NOT NULL, http_status INTEGER NOT NULL,
    PRIMARY KEY(actor, operation, target, key)
);
"""


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def _timestamp(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _missing() -> AnalyticsError:
    return AnalyticsError(404, "NOT_FOUND", "驾驶舱不存在或当前身份不可见。")


def _conflict() -> AnalyticsError:
    return AnalyticsError(409, "CONFLICT", "请求、状态或版本已变化，请读取当前驾驶舱后核对。")


def _unprocessable(message: str) -> AnalyticsError:
    return AnalyticsError(422, "UNPROCESSABLE", message)


def _invalid(message: str) -> AnalyticsError:
    return AnalyticsError(400, "INVALID_REQUEST", message)


def validate_key(key: str | None) -> str:
    if key is None:
        raise AnalyticsError(428, "IDEMPOTENCY_KEY_REQUIRED", "需要稳定的 Idempotency-Key。")
    if not key or len(key) > 200 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise AnalyticsError(400, "INVALID_IDEMPOTENCY_KEY", "Idempotency-Key 格式无效。")
    return key


def validate_if_match(value: str | None) -> int:
    if value is None:
        raise AnalyticsError(428, "IF_MATCH_REQUIRED", "需要 If-Match 版本。")
    if not isinstance(value, str) or not value.isdigit() or value.startswith("0"):
        raise AnalyticsError(400, "INVALID_VERSION", "If-Match 必须是正整数字符串。")
    version = int(value)
    if version < 1:
        raise AnalyticsError(400, "INVALID_VERSION", "If-Match 必须是正整数字符串。")
    return version


def _opaque(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not OPAQUE_ID.fullmatch(value):
        raise _invalid(f"{label} 不是合法标识。")
    return value


def _sha256(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not SHA256_HEX.fullmatch(value):
        raise _invalid(f"{label} 不是 SHA-256。")
    return value


def _mapping(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or isinstance(value, bool):
        raise _invalid(f"{label} 必须是对象。")
    return value


def _looks_like_b0(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    schema = payload.get("schema_version")
    if schema in B0_SCHEMAS:
        return True
    if "repeat_rate" in payload or "repeat_customers" in payload:
        return True
    if payload.get("customers") == 100 and payload.get("repeat_customers") == 25:
        return True
    for nested in (payload.get("result"), payload.get("facts"), payload.get("filters"), payload.get("snapshot")):
        if _looks_like_b0(nested):
            return True
    return False


def _reject_b0(payload: object) -> None:
    if _looks_like_b0(payload):
        raise _unprocessable("B0 固定 fixture 不能保存为驾驶舱板块。")


def _title(value: object) -> str:
    if not isinstance(value, str):
        raise _invalid("标题必须是文字。")
    title = value.strip()
    if not title or len(title) > 120 or any(ord(ch) < 32 or ord(ch) == 127 for ch in title):
        raise _invalid("标题须为 1–120 个字符，不含控制字符。")
    return title


def _layout(value: object) -> dict[str, int]:
    payload = _mapping(value, label="layout")
    if set(payload) != {"x", "y", "w", "h"}:
        raise _invalid("layout 只允许 x/y/w/h。")
    for key in ("x", "y", "w", "h"):
        if type(payload[key]) is not int:
            raise _invalid("layout 必须是整数栅格。")
    x, y, w, h = payload["x"], payload["y"], payload["w"], payload["h"]
    if x < 0 or y < 0 or w < MIN_SPAN or h < MIN_SPAN or w > MAX_SPAN or h > MAX_SPAN or x + w > GRID_COLUMNS:
        raise _unprocessable("布局超出 12 列栅格或小于最小尺寸。")
    return {"x": x, "y": y, "w": w, "h": h}


def _plugin_ref(value: object | None) -> dict[str, str]:
    if value is None:
        return dict(PLUGIN_TABLE)
    payload = _mapping(value, label="plugin_ref")
    kind = payload.get("type") if isinstance(payload.get("type"), str) else ""
    expected = PLUGIN_CATALOG.get(kind)
    if expected is None or payload != expected:
        raise _unprocessable("板块类型未登记。")
    return dict(expected)


def _analysis_ref(value: object) -> dict[str, Any]:
    payload = _mapping(value, label="analysis_ref")
    if set(payload) != {"analysis_id", "version"}:
        raise _invalid("analysis_ref 只允许 analysis_id/version。")
    analysis_id = payload.get("analysis_id")
    if not isinstance(analysis_id, str) or not ANALYSIS_ID.fullmatch(analysis_id):
        raise _invalid("analysis_id 不是合法标识。")
    version = payload.get("version")
    if type(version) is not int or version < 1:
        raise _invalid("analysis_ref.version 必须是从 1 起的整数。")
    return {"analysis_id": analysis_id, "version": version}


def _display_overrides(value: object | None) -> dict[str, str]:
    if value is None or value == {}:
        return {}
    payload = _mapping(value, label="display_overrides")
    if set(payload) != {"title"}:
        raise _invalid("display_overrides 只允许 title。")
    return {"title": _title(payload.get("title"))}


def _local_filters(value: object | None) -> dict[str, Any]:
    if value is None or value == {}:
        return {}
    payload = _mapping(value, label="local_filters")
    if set(payload) != {"channel_ids"}:
        raise _invalid("本波 local_filters 只允许 channel_ids。")
    channels = payload.get("channel_ids")
    if not isinstance(channels, list) or not channels or any(item not in ("A", "B") for item in channels):
        raise _unprocessable("local_filters.channel_ids 只能是登记渠道 A/B。")
    if len(channels) != len(set(channels)):
        raise _invalid("channel_ids 不能重复。")
    return {"channel_ids": list(channels)}


def _limitations(value: object | None) -> list[str]:
    if value is None:
        return ["finite mock: SNAPSHOT facts are displayed as supplied; not a live compute."]
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
        raise _invalid("limitations 必须是非空文字列表。")
    return list(value)


def _next_layout(cards: list[dict[str, Any]]) -> dict[str, int]:
    if not cards:
        return {"x": 0, "y": 0, "w": 6, "h": 4}
    bottom = max(card["layout"]["y"] + card["layout"]["h"] for card in cards)
    return {"x": 0, "y": bottom, "w": 6, "h": 4}


def _copy_layout(layout: dict[str, int]) -> dict[str, int]:
    return {"x": layout["x"], "y": layout["y"] + layout["h"], "w": layout["w"], "h": layout["h"]}


def _spec_hash(analysis_ref: dict[str, Any], snapshot: dict[str, Any], local_filters: dict[str, Any]) -> str:
    return content_hash({
        "analysis_ref": analysis_ref,
        "data_mode": "SNAPSHOT",
        "run_id": snapshot["run_id"],
        "evidence_digest": snapshot["evidence_digest"],
        "filter_hash": snapshot["resolved_filters"]["filter_hash"],
        "local_filters": local_filters,
    })


def _validate_snapshot(value: object) -> dict[str, Any]:
    payload = _mapping(value, label="snapshot")
    _reject_b0(payload)
    if set(payload) != SNAPSHOT_KEYS:
        raise _invalid("snapshot 字段必须是 run_id/evidence_digest/resolved_filters/data_snapshot_ref/as_of。")
    run_id = _opaque(payload.get("run_id"), label="run_id")
    digest = _sha256(payload.get("evidence_digest"), label="evidence_digest")
    try:
        resolved = ChannelFollowupResolvedFilters.model_validate(payload.get("resolved_filters"))
    except ValidationError:
        raise _unprocessable("SNAPSHOT resolved_filters 不合法。") from None
    dumped = json.loads(canonical_json(resolved.model_dump(mode="json")))
    if payload.get("data_snapshot_ref") != dumped["data_snapshot_ref"]:
        raise _unprocessable("data_snapshot_ref 与已解析条件不一致。")
    return {
        "run_id": run_id,
        "evidence_digest": digest,
        "resolved_filters": dumped,
        "data_snapshot_ref": dumped["data_snapshot_ref"],
        "as_of": dumped["as_of"],
    }


def _validate_facts(value: object, snapshot: dict[str, Any]) -> dict[str, Any]:
    _reject_b0(value)
    try:
        facts = ChannelFollowupFacts.model_validate(value)
    except ValidationError:
        raise _unprocessable("SNAPSHOT facts 不合法，不能写入驾驶舱。") from None
    dumped = json.loads(canonical_json(facts.model_dump(mode="json")))
    if dumped["observation_days"] != snapshot["resolved_filters"]["observation_days"]:
        raise _unprocessable("facts.observation_days 必须与 SNAPSHOT 条件一致。")
    return dumped


def _freeze_card(
    *,
    card_id: str,
    plugin_ref: dict[str, str],
    analysis_ref: dict[str, Any],
    layout: dict[str, int],
    display_overrides: dict[str, str],
    local_filters: dict[str, Any],
    snapshot: dict[str, Any],
    facts: dict[str, Any],
    limitations: list[str],
) -> dict[str, Any]:
    return {
        "card_id": card_id,
        "plugin_ref": dict(plugin_ref),
        "analysis_ref": dict(analysis_ref),
        "data_mode": "SNAPSHOT",
        "layout": dict(layout),
        "display_overrides": dict(display_overrides),
        "filter_mapping": {},
        "local_filters": dict(local_filters),
        "snapshot": json.loads(canonical_json(snapshot)),
        "facts": json.loads(canonical_json(facts)),
        "filter_hash": snapshot["resolved_filters"]["filter_hash"],
        "limitations": list(limitations),
        "effective_spec_hash": _spec_hash(analysis_ref, snapshot, local_filters),
        "freshness": "PINNED",
    }


def _find_card(cards: list[dict[str, Any]], card_id: str) -> dict[str, Any]:
    for card in cards:
        if card["card_id"] == card_id:
            return card
    raise _unprocessable("目标板块不存在。")


def _scope(body: dict[str, Any], *, op: str) -> str:
    default = "board" if op == "undo" else "card"
    scope = body.get("scope", default)
    if scope not in {"card", "board"}:
        raise _invalid("scope 只能是 card 或 board。")
    if op == "undo":
        if scope != "board":
            raise _unprocessable("撤销恢复整份配置，必须显式整板。")
        return "board"
    if scope == "board":
        raise _unprocessable("未指明整板操作时默认只改目标板块。")
    return "card"


@dataclass(frozen=True)
class CockpitRecord:
    schema_version: str
    dashboard_id: str
    version: int
    title: str
    owner_id: str
    visibility: str
    cards: list[dict[str, Any]]
    global_filters: dict[str, Any]
    created_at: str
    preview: bool
    persisted: bool
    affected_card_ids: list[str]
    finite_mock: bool
    http_api: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "dashboard_id": self.dashboard_id,
            "version": self.version,
            "title": self.title,
            "owner_id": self.owner_id,
            "visibility": "PRIVATE",
            "cards": json.loads(canonical_json(self.cards)),
            "global_filters": json.loads(canonical_json(self.global_filters)),
            "created_at": self.created_at,
            "preview": self.preview,
            "persisted": self.persisted,
            "affected_card_ids": list(self.affected_card_ids),
            "finite_mock": True,
            "http_api": "NOT_CONNECTED",
        }


class CockpitStore:
    """Finite-mock private cockpit. HTTP/OpenAPI is NOT_CONNECTED."""

    finite_mock = True
    http_api = "NOT_CONNECTED"

    def __init__(self, state_dir: Path, *, clock: Callable[[], int] = _now_ms):
        original = Path(state_dir)
        if original.is_symlink() or not original.is_dir():
            raise ValueError("an existing private cockpit directory is required")
        self.directory = original.resolve(strict=True)
        mode = self.directory.stat()
        if mode.st_mode & 0o077 or mode.st_uid != os.getuid():
            raise ValueError("cockpit directory must be owned by the caller and mode 0700")
        self.path = self.directory / "cockpit.sqlite3"
        self.clock = clock
        self._initialize()

    def close(self) -> None:
        """Connections are per-call; callers drop the instance before reopen."""

    def _initialize(self) -> None:
        flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW
        fd = os.open(self.directory / ".initialize.lock", flags, 0o600)
        try:
            lock_info = os.fstat(fd)
            if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_nlink != 1 or lock_info.st_uid != os.getuid():
                raise ValueError("refusing unowned or linked cockpit initialization lock")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            existed = self.path.exists() or self.path.is_symlink()
            if existed:
                info = self.path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
                    raise ValueError("refusing unowned or linked cockpit state file")
                with self._connection(readonly=True) as con:
                    if con.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
                        raise ValueError("refusing a foreign or incomplete cockpit database")
                    if con.execute("PRAGMA user_version").fetchone()[0] != STATE_SCHEMA_VERSION:
                        raise ValueError("cockpit schema differs; retain old evidence and use fresh state")
                    kind = con.execute("SELECT value FROM metadata WHERE key = ?", ("kind",)).fetchone()
                    if kind is None or kind[0] != "cockpit":
                        raise ValueError("refusing a foreign or incomplete cockpit database")
                return
            created = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.close(created)
            with self._connection() as con:
                con.execute("PRAGMA journal_mode=WAL")
                con.executescript("BEGIN IMMEDIATE;\n" + _SCHEMA)
                try:
                    con.execute(f"PRAGMA application_id={APPLICATION_ID}")
                    con.execute(f"PRAGMA user_version={STATE_SCHEMA_VERSION}")
                    con.execute("INSERT INTO metadata VALUES (?, ?)", ("kind", "cockpit"))
                    con.execute("INSERT INTO metadata VALUES (?, ?)", ("finite_mock", "true"))
                    con.execute("INSERT INTO metadata VALUES (?, ?)", ("http_api", "NOT_CONNECTED"))
                    con.execute("COMMIT")
                except BaseException:
                    if con.in_transaction:
                        con.execute("ROLLBACK")
                    raise
        finally:
            os.close(fd)

    @contextmanager
    def _connection(self, *, readonly: bool = False):
        if self.path.is_symlink():
            raise ValueError("cockpit state file must not be a symlink")
        uri = self.path.as_uri() + ("?mode=ro" if readonly else "?mode=rw")
        con = sqlite3.connect(uri, uri=True, timeout=0.1, autocommit=True)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA foreign_keys=ON")
            if not readonly:
                con.execute("PRAGMA synchronous=FULL")
            yield con
        finally:
            con.close()

    @contextmanager
    def _transaction(self):
        try:
            with self._connection() as con:
                con.execute("BEGIN IMMEDIATE")
                try:
                    yield con
                    con.execute("COMMIT")
                except BaseException:
                    con.execute("ROLLBACK")
                    raise
        except sqlite3.DatabaseError as error:
            raise AnalyticsError(
                503, "STATE_UNAVAILABLE", "驾驶舱状态暂不可用，请使用原请求标识查询或重试。",
                retryable=True,
            ) from error

    def _require(self, principal: AnalyticsPrincipal, capability: str) -> None:
        require(principal, capability, data_scope=DATA_SCOPE)

    @staticmethod
    def _prior(con, principal, operation, target, key, digest):
        row = con.execute(
            "SELECT * FROM idempotency WHERE actor=? AND operation=? AND target=? AND key=?",
            (principal.actor_id, operation, target, key),
        ).fetchone()
        if row is not None and row["request_hash"] != digest:
            raise _conflict()
        return row

    @staticmethod
    def _remember(con, principal, operation, target, key, digest, response, status):
        con.execute(
            "INSERT INTO idempotency VALUES (?, ?, ?, ?, ?, ?, ?)",
            (principal.actor_id, operation, target, key, digest, canonical_json(response), status),
        )

    def create(self, principal: AnalyticsPrincipal, key: str, payload: dict[str, Any] | None = None) -> CockpitRecord:
        self._require(principal, CAPABILITY_WRITE)
        key = validate_key(key)
        body = _mapping(payload or {}, label="create")
        extra = set(body) - CREATE_FIELDS
        if extra:
            raise _invalid("请求包含未声明字段。")
        title = DEFAULT_TITLE if "title" not in body else _title(body.get("title"))
        digest = content_hash({"title": title})
        with self._transaction() as con:
            prior = self._prior(con, principal, "dashboard:create", "", key, digest)
            if prior is not None:
                return CockpitRecord(**json.loads(prior["response_json"]))
            existing = con.execute(
                "SELECT dashboard_id FROM owners WHERE owner=?", (principal.actor_id,),
            ).fetchone()
            if existing is not None:
                row = self._dashboard_row(con, principal, existing["dashboard_id"], None)
                record = self._record(row, preview=False, persisted=True, affected=[])
                response = record.as_dict()
                self._remember(con, principal, "dashboard:create", "", key, digest, response, 200)
                return CockpitRecord(**response)
            dashboard_id = _id("dashboard")
            created_ms = self.clock()
            con.execute("INSERT INTO owners VALUES (?, ?)", (principal.actor_id, dashboard_id))
            con.execute(
                """INSERT INTO dashboards (
                    dashboard_id, version, owner, title, cards_json, global_filters_json, created_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    dashboard_id, 1, principal.actor_id, title, canonical_json([]),
                    canonical_json(DEFAULT_GLOBAL_FILTERS), created_ms,
                ),
            )
            row = self._dashboard_row(con, principal, dashboard_id, 1)
            record = self._record(row, preview=False, persisted=True, affected=[])
            response = record.as_dict()
            self._remember(con, principal, "dashboard:create", "", key, digest, response, 201)
            return CockpitRecord(**response)

    def get(self, principal: AnalyticsPrincipal, dashboard_id: str | None = None) -> CockpitRecord:
        self._require(principal, CAPABILITY_READ)
        with self._connection(readonly=True) as con:
            if dashboard_id is None:
                owned = con.execute(
                    "SELECT dashboard_id FROM owners WHERE owner=?", (principal.actor_id,),
                ).fetchone()
                if owned is None:
                    raise _missing()
                dashboard_id = owned["dashboard_id"]
            else:
                dashboard_id = _opaque(dashboard_id, label="dashboard_id")
            row = self._dashboard_row(con, principal, dashboard_id, None)
            return self._record(row, preview=False, persisted=True, affected=[])

    def list(self, principal: AnalyticsPrincipal) -> list[dict[str, Any]]:
        self._require(principal, CAPABILITY_READ)
        with self._connection(readonly=True) as con:
            owned = con.execute(
                "SELECT dashboard_id FROM owners WHERE owner=?", (principal.actor_id,),
            ).fetchone()
            if owned is None:
                return []
            row = self._dashboard_row(con, principal, owned["dashboard_id"], None)
            cards = json.loads(row["cards_json"])
            return [{
                "schema_version": DASHBOARD_SCHEMA,
                "dashboard_id": row["dashboard_id"],
                "version": row["version"],
                "title": row["title"],
                "visibility": "PRIVATE",
                "card_count": len(cards),
                "finite_mock": True,
                "http_api": "NOT_CONNECTED",
            }]

    def preview(self, principal: AnalyticsPrincipal, dashboard_id: str, patch: dict[str, Any]) -> CockpitRecord:
        self._require(principal, CAPABILITY_READ)
        dashboard_id = _opaque(dashboard_id, label="dashboard_id")
        body = _mapping(patch, label="patch")
        _reject_b0(body)
        extra = set(body) - PATCH_FIELDS
        if extra:
            raise _invalid("请求包含未声明字段。")
        with self._connection(readonly=True) as con:
            row = self._dashboard_row(con, principal, dashboard_id, None)
            cards, title, filters, affected = self._apply_patch(con, row, body, preview=True)
            return self._record(
                row, preview=True, persisted=False, affected=affected,
                cards=cards, title=title, global_filters=filters,
            )

    def apply(
        self,
        principal: AnalyticsPrincipal,
        key: str,
        dashboard_id: str,
        if_match: str | None,
        patch: dict[str, Any],
    ) -> CockpitRecord:
        self._require(principal, CAPABILITY_WRITE)
        key = validate_key(key)
        dashboard_id = _opaque(dashboard_id, label="dashboard_id")
        version = validate_if_match(if_match)
        body = _mapping(patch, label="patch")
        _reject_b0(body)
        extra = set(body) - PATCH_FIELDS
        if extra:
            raise _invalid("请求包含未声明字段。")
        digest = content_hash({"dashboard_id": dashboard_id, "if_match": version, "patch": body})
        with self._transaction() as con:
            prior = self._prior(con, principal, "dashboard:patch", dashboard_id, key, digest)
            if prior is not None:
                return CockpitRecord(**json.loads(prior["response_json"]))
            row = self._dashboard_row(con, principal, dashboard_id, None)
            if row["version"] != version:
                raise _conflict()
            cards, title, filters, affected = self._apply_patch(con, row, body, preview=False)
            created_ms = self.clock()
            con.execute(
                """INSERT INTO dashboards (
                    dashboard_id, version, owner, title, cards_json, global_filters_json, created_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    dashboard_id, version + 1, principal.actor_id, title, canonical_json(cards),
                    canonical_json(filters), created_ms,
                ),
            )
            stored = self._dashboard_row(con, principal, dashboard_id, version + 1)
            record = self._record(stored, preview=False, persisted=True, affected=affected)
            response = record.as_dict()
            self._remember(con, principal, "dashboard:patch", dashboard_id, key, digest, response, 200)
            return CockpitRecord(**response)

    def _apply_patch(self, con, row, body: dict[str, Any], *, preview: bool):
        op = body.get("op")
        if op not in {"add", "copy", "remove", "layout", "ai_edit", "undo"}:
            raise _invalid("op 必须是 add/copy/remove/layout/ai_edit/undo。")
        _scope(body, op=op)
        cards = json.loads(row["cards_json"])
        title = row["title"]
        filters = json.loads(row["global_filters_json"])
        if op == "undo":
            restore = body.get("restore_from_version")
            if type(restore) is not int or restore < 1:
                raise _invalid("restore_from_version 必须是从 1 起的整数。")
            if restore >= row["version"]:
                raise _unprocessable("只能从当前版本之前的配置恢复。")
            prior = con.execute(
                "SELECT * FROM dashboards WHERE dashboard_id=? AND owner=? AND version=?",
                (row["dashboard_id"], row["owner"], restore),
            ).fetchone()
            if prior is None:
                raise _missing()
            restored = json.loads(prior["cards_json"])
            return restored, prior["title"], json.loads(prior["global_filters_json"]), [
                card["card_id"] for card in restored
            ]
        if op == "add":
            if body.get("card_id") is not None:
                raise _invalid("添加板块时由服务端分配 card_id。")
            if len(cards) >= MAX_CARDS:
                raise _unprocessable("驾驶舱板块数量已达上限。")
            if body.get("filter_mapping") not in (None, {}):
                raise _unprocessable("本波不支持全局筛选映射。")
            snapshot = _validate_snapshot(body.get("snapshot"))
            facts = _validate_facts(body.get("facts"), snapshot)
            new_id = _id("preview") if preview else _id("card")
            card = _freeze_card(
                card_id=new_id,
                plugin_ref=_plugin_ref(body.get("plugin_ref")),
                analysis_ref=_analysis_ref(body.get("analysis_ref")),
                layout=_layout(body["layout"]) if "layout" in body else _next_layout(cards),
                display_overrides=_display_overrides(body.get("display_overrides")),
                local_filters=_local_filters(body.get("local_filters")),
                snapshot=snapshot,
                facts=facts,
                limitations=_limitations(body.get("limitations")),
            )
            cards.append(card)
            return cards, title, filters, [new_id]
        card_id = body.get("card_id")
        if card_id is None:
            raise _unprocessable("未指明目标板块，不能改整板。")
        card_id = _opaque(card_id, label="card_id")
        target = _find_card(cards, card_id)
        if op == "copy":
            if len(cards) >= MAX_CARDS:
                raise _unprocessable("驾驶舱板块数量已达上限。")
            clone = json.loads(canonical_json(target))
            clone["card_id"] = _id("preview") if preview else _id("card")
            clone["layout"] = _copy_layout(target["layout"])
            cards.append(clone)
            return cards, title, filters, [clone["card_id"]]
        if op == "remove":
            remaining = [card for card in cards if card["card_id"] != card_id]
            return remaining, title, filters, [card_id]
        if op == "layout":
            if "layout" not in body:
                raise _invalid("布局操作必须提供 layout。")
            updated = json.loads(canonical_json(target))
            updated["layout"] = _layout(body.get("layout"))
            cards = [updated if card["card_id"] == card_id else card for card in cards]
            return cards, title, filters, [card_id]
        return self._ai_edit(cards, title, filters, target, body)

    def _ai_edit(self, cards, title, filters, target, body):
        intent = body.get("intent")
        if intent not in AI_INTENTS:
            raise _unprocessable("未知的 finite mock 提案。")
        if FACT_FIELDS & set(body):
            raise _unprocessable("AI 提案不能改写 SNAPSHOT 事实字段。")
        spec = AI_INTENTS[intent]
        updated = json.loads(canonical_json(target))
        if "display_overrides" in spec:
            updated["display_overrides"] = _display_overrides(spec["display_overrides"])
        if "local_filters" in spec:
            updated["local_filters"] = _local_filters(spec["local_filters"])
        if "plugin_ref" in spec:
            updated["plugin_ref"] = _plugin_ref(spec["plugin_ref"])
        if "layout_patch" in spec:
            layout = dict(updated["layout"])
            layout.update(spec["layout_patch"])
            updated["layout"] = _layout(layout)
        updated["effective_spec_hash"] = _spec_hash(
            updated["analysis_ref"], updated["snapshot"], updated["local_filters"],
        )
        cards = [updated if card["card_id"] == target["card_id"] else card for card in cards]
        return cards, title, filters, [target["card_id"]]

    @staticmethod
    def _dashboard_row(con, principal: AnalyticsPrincipal, dashboard_id: str, version: int | None):
        if version is None:
            row = con.execute(
                """SELECT * FROM dashboards WHERE dashboard_id=? AND owner=?
                   ORDER BY version DESC LIMIT 1""",
                (dashboard_id, principal.actor_id),
            ).fetchone()
        else:
            row = con.execute(
                "SELECT * FROM dashboards WHERE dashboard_id=? AND owner=? AND version=?",
                (dashboard_id, principal.actor_id, version),
            ).fetchone()
        if row is None:
            raise _missing()
        return row

    @staticmethod
    def _record(row, *, preview: bool, persisted: bool, affected: list[str],
                cards=None, title=None, global_filters=None) -> CockpitRecord:
        return CockpitRecord(
            schema_version=DASHBOARD_SCHEMA,
            dashboard_id=row["dashboard_id"],
            version=row["version"],
            title=row["title"] if title is None else title,
            owner_id=row["owner"],
            visibility="PRIVATE",
            cards=json.loads(row["cards_json"]) if cards is None else cards,
            global_filters=json.loads(row["global_filters_json"]) if global_filters is None else global_filters,
            created_at=_timestamp(row["created_ms"]),
            preview=preview,
            persisted=persisted,
            affected_card_ids=list(affected),
            finite_mock=True,
            http_api="NOT_CONNECTED",
        )
