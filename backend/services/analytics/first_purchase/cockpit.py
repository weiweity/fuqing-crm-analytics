"""Append-only private first-purchase cockpit store.

Independent SQLite. Cards freeze SNAPSHOT run_id/digest/facts from a saved
first-purchase analysis. ChannelFollowup facts are rejected. Preview never
writes. Apply requires If-Match; version conflicts are 409.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from backend.contracts.analytics_first_purchase import FirstPurchaseFacts, FirstPurchaseResolvedFilters
from backend.contracts.analytics_first_purchase_cockpit import GRID_MAX_ROW
from backend.contracts.analytics_first_purchase_run import FIRST_PURCHASE_DATA_SCOPE
from backend.services.analytics.access import AnalyticsPrincipal, require
from backend.services.analytics.first_purchase.asset_state import (
    conflict,
    connect,
    initialize_sqlite,
    invalid,
    mapping,
    missing,
    new_id,
    now_ms,
    opaque,
    prior_row,
    reject_foreign_family,
    remember,
    sha256_hex,
    timestamp,
    title_text,
    transaction,
    unprocessable,
    validate_if_match,
    validate_key,
)
from backend.services.analytics.resource_profile import canonical_json, content_hash

DASHBOARD_SCHEMA = "analytics-first-purchase-cockpit/v1"
FILTER_SCHEMA = "analytics-first-purchase-cockpit-filters/v1"
DATA_SCOPE = FIRST_PURCHASE_DATA_SCOPE
CAPABILITY_READ = "dashboard:read"
CAPABILITY_WRITE = "dashboard:update"
APPLICATION_ID = 1397572602  # SMF2; distinct from SMA1/SMC1/SMB0/SMF1.
STATE_SCHEMA_VERSION = 1
KIND = "first_purchase_cockpit"
UNAVAILABLE = "驾驶舱状态暂不可用，请使用原请求标识查询或重试。"
MAX_CARDS = 20
GRID_COLUMNS = 12
MIN_SPAN = 2
MAX_SPAN = 12
ANALYSIS_ID = re.compile(r"^analysis_[A-Za-z0-9_.:-]{1,118}$")
DEFAULT_TITLE = "我的首购驾驶舱"
DEFAULT_GLOBAL_FILTERS = {"schema_version": FILTER_SCHEMA, "channel_ids": []}
PLUGIN_TABLE = {"type": "TABLE", "version": "analytics-visual-table/v1"}
CREATE_FIELDS = frozenset({"title"})
PATCH_FIELDS = frozenset({
    "op", "card_id", "scope", "analysis_ref", "snapshot", "facts", "limitations",
    "plugin_ref", "layout", "display_overrides", "local_filters", "filter_mapping",
    "restore_from_version",
})
SNAPSHOT_KEYS = frozenset({"run_id", "evidence_digest", "resolved_filters", "data_snapshot_ref", "as_of"})

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


def spec_hash(analysis_ref: dict[str, Any], snapshot: dict[str, Any], local_filters: dict[str, Any]) -> str:
    return content_hash({
        "analysis_ref": analysis_ref,
        "data_mode": "SNAPSHOT",
        "run_id": snapshot["run_id"],
        "evidence_digest": snapshot["evidence_digest"],
        "filter_hash": snapshot["resolved_filters"]["filter_hash"],
        "local_filters": local_filters,
    })


def _layout(value: object) -> dict[str, int]:
    payload = mapping(value, label="layout")
    if set(payload) != {"x", "y", "w", "h"}:
        raise invalid("layout 只允许 x/y/w/h。")
    for key in ("x", "y", "w", "h"):
        if type(payload[key]) is not int:
            raise invalid("layout 必须是整数栅格。")
    x, y, w, h = payload["x"], payload["y"], payload["w"], payload["h"]
    if (x < 0 or y < 0 or y > GRID_MAX_ROW or w < MIN_SPAN or h < MIN_SPAN
            or w > MAX_SPAN or h > MAX_SPAN or x + w > GRID_COLUMNS):
        raise unprocessable("布局超出 12 列栅格、行上限或小于最小尺寸。")
    return {"x": x, "y": y, "w": w, "h": h}


def _plugin_ref(value: object | None) -> dict[str, str]:
    if value is None:
        return dict(PLUGIN_TABLE)
    payload = mapping(value, label="plugin_ref")
    if payload != PLUGIN_TABLE:
        raise unprocessable("本波只允许 TABLE 板块。")
    return dict(PLUGIN_TABLE)


def _analysis_ref(value: object) -> dict[str, Any]:
    payload = mapping(value, label="analysis_ref")
    if set(payload) != {"analysis_id", "version"}:
        raise invalid("analysis_ref 只允许 analysis_id/version。")
    analysis_id = payload.get("analysis_id")
    if not isinstance(analysis_id, str) or not ANALYSIS_ID.fullmatch(analysis_id):
        raise invalid("analysis_id 不是合法标识。")
    version = payload.get("version")
    if type(version) is not int or version < 1:
        raise invalid("analysis_ref.version 必须是从 1 起的整数。")
    return {"analysis_id": analysis_id, "version": version}


def _display_overrides(value: object | None) -> dict[str, str]:
    if value is None or value == {}:
        return {}
    payload = mapping(value, label="display_overrides")
    if set(payload) != {"title"}:
        raise invalid("display_overrides 只允许 title。")
    return {"title": title_text(payload.get("title"))}


def _local_filters(value: object | None) -> dict[str, Any]:
    if value is None or value == {}:
        return {}
    raise invalid("本波 local_filters 必须为空。")


def _limitations(value: object | None) -> list[str]:
    if value is None:
        return ["finite mock: SNAPSHOT facts are displayed as supplied; not a live compute."]
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
        raise invalid("limitations 必须是非空文字列表。")
    return list(value)


def _next_layout(cards: list[dict[str, Any]]) -> dict[str, int]:
    if not cards:
        return {"x": 0, "y": 0, "w": 6, "h": 4}
    bottom = max(card["layout"]["y"] + card["layout"]["h"] for card in cards)
    return {"x": 0, "y": bottom, "w": 6, "h": 4}


def _copy_layout(layout: dict[str, int]) -> dict[str, int]:
    return {"x": layout["x"], "y": layout["y"] + layout["h"], "w": layout["w"], "h": layout["h"]}


def _validate_snapshot(value: object) -> dict[str, Any]:
    payload = mapping(value, label="snapshot")
    reject_foreign_family(payload)
    if set(payload) != SNAPSHOT_KEYS:
        raise invalid("snapshot 字段必须是 run_id/evidence_digest/resolved_filters/data_snapshot_ref/as_of。")
    run_id = opaque(payload.get("run_id"), label="run_id")
    digest = sha256_hex(payload.get("evidence_digest"), label="evidence_digest")
    try:
        resolved = FirstPurchaseResolvedFilters.model_validate(payload.get("resolved_filters"))
    except ValidationError:
        raise unprocessable("SNAPSHOT resolved_filters 不合法。") from None
    dumped = json.loads(canonical_json(resolved.model_dump(mode="json")))
    if payload.get("data_snapshot_ref") != dumped["data_snapshot_ref"]:
        raise unprocessable("data_snapshot_ref 与已解析条件不一致。")
    return {
        "run_id": run_id,
        "evidence_digest": digest,
        "resolved_filters": dumped,
        "data_snapshot_ref": dumped["data_snapshot_ref"],
        "as_of": dumped["as_of"],
    }


def _validate_facts(value: object, snapshot: dict[str, Any]) -> dict[str, Any]:
    reject_foreign_family(value)
    try:
        facts = FirstPurchaseFacts.model_validate(value)
    except ValidationError:
        raise unprocessable("SNAPSHOT facts 不合法，不能写入驾驶舱。") from None
    dumped = json.loads(canonical_json(facts.model_dump(mode="json")))
    if dumped["observation_days"] != snapshot["resolved_filters"]["observation_days"]:
        raise unprocessable("facts.observation_days 必须与 SNAPSHOT 条件一致。")
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
        "effective_spec_hash": spec_hash(analysis_ref, snapshot, local_filters),
        "freshness": "PINNED",
    }


def _find_card(cards: list[dict[str, Any]], card_id: str) -> dict[str, Any]:
    for card in cards:
        if card["card_id"] == card_id:
            return card
    raise unprocessable("目标板块不存在。")


def _scope(body: dict[str, Any], *, op: str) -> str:
    default = "board" if op == "undo" else "card"
    scope = body.get("scope", default)
    if scope not in {"card", "board"}:
        raise invalid("scope 只能是 card 或 board。")
    if op == "undo":
        if scope != "board":
            raise unprocessable("撤销恢复整份配置，必须显式整板。")
        return "board"
    if scope == "board":
        raise unprocessable("未指明整板操作时默认只改目标板块。")
    return "card"


@dataclass(frozen=True)
class FirstPurchaseCockpitRecord:
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


class FirstPurchaseCockpitStore:
    finite_mock = True
    http_api = "NOT_CONNECTED"

    def __init__(self, state_dir: Path, *, clock: Callable[[], int] = now_ms):
        original = Path(state_dir)
        self.directory = original.resolve(strict=True)
        self.path = self.directory / "first_purchase_cockpit.sqlite3"
        self.clock = clock
        initialize_sqlite(
            original, self.path, application_id=APPLICATION_ID, schema_version=STATE_SCHEMA_VERSION,
            kind=KIND, ddl=_SCHEMA, unavailable=UNAVAILABLE,
        )

    def close(self) -> None:
        """Connections are per-call; callers drop the instance before reopen."""

    def _require(self, principal: AnalyticsPrincipal, capability: str) -> None:
        require(principal, capability, data_scope=DATA_SCOPE)

    def acquire(
        self, principal: AnalyticsPrincipal, key: str, payload: dict[str, Any] | None = None,
    ) -> tuple[FirstPurchaseCockpitRecord, int]:
        self._require(principal, CAPABILITY_WRITE)
        key = validate_key(key)
        body = mapping(payload or {}, label="create")
        extra = set(body) - CREATE_FIELDS
        if extra:
            raise invalid("请求包含未声明字段。")
        title = DEFAULT_TITLE if "title" not in body else title_text(body.get("title"))
        digest = content_hash({"title": title})
        with transaction(self.path, unavailable=UNAVAILABLE) as con:
            prior = prior_row(con, principal, "dashboard:create", "", key, digest, kind="cockpit")
            if prior is not None:
                return FirstPurchaseCockpitRecord(**json.loads(prior["response_json"])), int(prior["http_status"])
            existing = con.execute(
                "SELECT dashboard_id FROM owners WHERE owner=?", (principal.actor_id,),
            ).fetchone()
            if existing is not None:
                row = self._dashboard_row(con, principal, existing["dashboard_id"], None)
                record = self._record(row, preview=False, persisted=True, affected=[])
                response = record.as_dict()
                remember(con, principal, "dashboard:create", "", key, digest, response, 200, canonical_json)
                return FirstPurchaseCockpitRecord(**response), 200
            dashboard_id = new_id("dashboard")
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
            remember(con, principal, "dashboard:create", "", key, digest, response, 201, canonical_json)
            return FirstPurchaseCockpitRecord(**response), 201

    def get(self, principal: AnalyticsPrincipal, dashboard_id: str | None = None) -> FirstPurchaseCockpitRecord:
        self._require(principal, CAPABILITY_READ)
        with connect(self.path, readonly=True, unavailable=UNAVAILABLE) as con:
            if dashboard_id is None:
                owned = con.execute(
                    "SELECT dashboard_id FROM owners WHERE owner=?", (principal.actor_id,),
                ).fetchone()
                if owned is None:
                    raise missing("cockpit")
                dashboard_id = owned["dashboard_id"]
            else:
                dashboard_id = opaque(dashboard_id, label="dashboard_id")
            row = self._dashboard_row(con, principal, dashboard_id, None)
            return self._record(row, preview=False, persisted=True, affected=[])

    def get_version(self, principal: AnalyticsPrincipal, dashboard_id: str, version: int) -> FirstPurchaseCockpitRecord:
        self._require(principal, CAPABILITY_READ)
        dashboard_id = opaque(dashboard_id, label="dashboard_id")
        if type(version) is not int or version < 1:
            raise invalid("version 必须是从 1 起的整数。")
        with connect(self.path, readonly=True, unavailable=UNAVAILABLE) as con:
            row = self._dashboard_row(con, principal, dashboard_id, version)
            return self._record(row, preview=False, persisted=True, affected=[])

    def list(self, principal: AnalyticsPrincipal) -> list[dict[str, Any]]:
        self._require(principal, CAPABILITY_READ)
        with connect(self.path, readonly=True, unavailable=UNAVAILABLE) as con:
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

    def preview(
        self, principal: AnalyticsPrincipal, dashboard_id: str, patch: dict[str, Any],
        if_match: str | None = None,
    ) -> FirstPurchaseCockpitRecord:
        self._require(principal, CAPABILITY_READ)
        dashboard_id = opaque(dashboard_id, label="dashboard_id")
        body = mapping(patch, label="patch")
        reject_foreign_family(body)
        extra = set(body) - PATCH_FIELDS
        if extra:
            raise invalid("请求包含未声明字段。")
        version = None if if_match is None else validate_if_match(if_match)
        with connect(self.path, readonly=True, unavailable=UNAVAILABLE) as con:
            row = self._dashboard_row(con, principal, dashboard_id, version)
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
    ) -> FirstPurchaseCockpitRecord:
        self._require(principal, CAPABILITY_WRITE)
        key = validate_key(key)
        dashboard_id = opaque(dashboard_id, label="dashboard_id")
        version = validate_if_match(if_match)
        body = mapping(patch, label="patch")
        reject_foreign_family(body)
        extra = set(body) - PATCH_FIELDS
        if extra:
            raise invalid("请求包含未声明字段。")
        digest = content_hash({"dashboard_id": dashboard_id, "if_match": version, "patch": body})
        with transaction(self.path, unavailable=UNAVAILABLE) as con:
            prior = prior_row(con, principal, "dashboard:patch", dashboard_id, key, digest, kind="cockpit")
            if prior is not None:
                return FirstPurchaseCockpitRecord(**json.loads(prior["response_json"]))
            row = self._dashboard_row(con, principal, dashboard_id, None)
            if row["version"] != version:
                raise conflict("cockpit")
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
            remember(con, principal, "dashboard:patch", dashboard_id, key, digest, response, 200, canonical_json)
            return FirstPurchaseCockpitRecord(**response)

    def _apply_patch(self, con, row, body: dict[str, Any], *, preview: bool):
        op = body.get("op")
        if op not in {"add", "copy", "remove", "layout", "undo"}:
            raise invalid("op 必须是 add/copy/remove/layout/undo。")
        _scope(body, op=op)
        cards = json.loads(row["cards_json"])
        title = row["title"]
        filters = json.loads(row["global_filters_json"])
        if op == "undo":
            restore = body.get("restore_from_version")
            if type(restore) is not int or restore < 1:
                raise invalid("restore_from_version 必须是从 1 起的整数。")
            if restore >= row["version"]:
                raise unprocessable("只能从当前版本之前的配置恢复。")
            prior = con.execute(
                "SELECT * FROM dashboards WHERE dashboard_id=? AND owner=? AND version=?",
                (row["dashboard_id"], row["owner"], restore),
            ).fetchone()
            if prior is None:
                raise missing("cockpit")
            restored = json.loads(prior["cards_json"])
            return restored, prior["title"], json.loads(prior["global_filters_json"]), [
                card["card_id"] for card in restored
            ]
        if op == "add":
            if body.get("card_id") is not None:
                raise invalid("添加板块时由服务端分配 card_id。")
            if len(cards) >= MAX_CARDS:
                raise unprocessable("驾驶舱板块数量已达上限。")
            if body.get("filter_mapping") not in (None, {}):
                raise unprocessable("本波不支持全局筛选映射。")
            snapshot = _validate_snapshot(body.get("snapshot"))
            facts = _validate_facts(body.get("facts"), snapshot)
            new_id_value = new_id("preview") if preview else new_id("card")
            card = _freeze_card(
                card_id=new_id_value,
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
            return cards, title, filters, [new_id_value]
        card_id = body.get("card_id")
        if card_id is None:
            raise unprocessable("未指明目标板块，不能改整板。")
        card_id = opaque(card_id, label="card_id")
        target = _find_card(cards, card_id)
        if op == "copy":
            if len(cards) >= MAX_CARDS:
                raise unprocessable("驾驶舱板块数量已达上限。")
            clone = json.loads(canonical_json(target))
            clone["card_id"] = new_id("preview") if preview else new_id("card")
            clone["layout"] = _copy_layout(target["layout"])
            cards.append(clone)
            return cards, title, filters, [clone["card_id"]]
        if op == "remove":
            remaining = [card for card in cards if card["card_id"] != card_id]
            return remaining, title, filters, [card_id]
        if "layout" not in body:
            raise invalid("布局操作必须提供 layout。")
        updated = json.loads(canonical_json(target))
        updated["layout"] = _layout(body.get("layout"))
        cards = [updated if card["card_id"] == card_id else card for card in cards]
        return cards, title, filters, [card_id]

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
            raise missing("cockpit")
        return row

    @staticmethod
    def _record(row, *, preview: bool, persisted: bool, affected: list[str],
                cards=None, title=None, global_filters=None) -> FirstPurchaseCockpitRecord:
        return FirstPurchaseCockpitRecord(
            schema_version=DASHBOARD_SCHEMA,
            dashboard_id=row["dashboard_id"],
            version=row["version"],
            title=row["title"] if title is None else title,
            owner_id=row["owner"],
            visibility="PRIVATE",
            cards=json.loads(row["cards_json"]) if cards is None else cards,
            global_filters=json.loads(row["global_filters_json"]) if global_filters is None else global_filters,
            created_at=timestamp(row["created_ms"]),
            preview=preview,
            persisted=persisted,
            affected_card_ids=list(affected),
            finite_mock=True,
            http_api="NOT_CONNECTED",
        )
