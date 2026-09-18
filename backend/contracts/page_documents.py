"""Independent free-page asset and bridge contract. Not BoardSpec.

schema_version is free-page/v1. HTML/CSS/JavaScript are the source package;
there is no component catalogue and no INVALID_BOARD.
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "free-page/v1"
BRIDGE_PROTOCOL = "free-page-bridge/v1"
IDENTITY = r"^[A-Za-z0-9_.:-]{1,128}$"
Opaque = Annotated[str, Field(min_length=1, max_length=128, pattern=IDENTITY)]
Title = Annotated[str, Field(min_length=1, max_length=160, pattern=r"\S")]
Version = Annotated[int, Field(ge=1, le=9007199254740991)]
BindingState = Literal["UNBOUND_SAMPLE", "BOUND_VERIFIED", "BOUND_STALE"]
PageOperation = Literal["GENERATE", "PATCH", "SAVE", "ROLLBACK"]
PreviewStatus = Literal["PENDING", "APPLIED", "CANCELLED"]
NodeKind = Literal["static_element", "dynamic_region", "whole_page"]
ReadMode = Literal["summary", "page", "range"]
BRIDGE_MAX_RESPONSE_BYTES = 65536
BRIDGE_MAX_CUMULATIVE_ROWS = 2000
PACKAGE_MAX_BYTES = 2_000_000
HTML_MAX_CHARS = 1_048_576
STYLE_MAX_CHARS = 524_288

PAGE_ERRORS = {
    "VERSION_CONFLICT": 409,
    "NOT_FOUND": 404,
    "FORBIDDEN": 403,
    "PREVIEW_EXPIRED": 409,
    "PREVIEW_CANCELLED": 409,
    "IDEMPOTENCY_CONFLICT": 409,
    "INVALID_PAGE": 422,
    "RESULT_UNAVAILABLE": 409,
    "RESULT_STALE": 409,
    "RESULT_REVOKED": 403,
    "MAPPING_STALE": 409,
    "SCOPE_REQUIRES_CONFIRMATION": 409,
    "RESOURCE_HASH_MISMATCH": 409,
    "PACKAGE_TOO_LARGE": 413,
    "BRIDGE_UNKNOWN_OP": 400,
    "BRIDGE_NONCE": 409,
    "BRIDGE_EXPIRED_INSTANCE": 409,
    "BINDING_CORRUPT": 409,
}


class PageModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


PACKAGE_TOO_LARGE_TYPE = "package_too_large"


def unique(values):
    if len(set(values)) != len(values):
        raise ValueError("items must be unique")
    return values


def is_package_too_large(error: BaseException) -> bool:
    details = getattr(error, "errors", None)
    if callable(details):
        for item in details():
            if item.get("type") == PACKAGE_TOO_LARGE_TYPE:
                return True
            if "超过大小上限" in str(item.get("msg", "")):
                return True
        return False
    return "超过大小上限" in str(error)


class PageResource(PageModel):
    resource_id: Opaque
    content_type: Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._+-]+/[A-Za-z0-9._+-]+$")]
    sha256: Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]
    byte_length: Annotated[int, Field(ge=0, le=PACKAGE_MAX_BYTES)]


class PageNodeMapEntry(PageModel):
    node_id: Opaque
    kind: NodeKind
    selector: Annotated[str, Field(min_length=1, max_length=512, pattern=r"\S")]


class PagePackage(PageModel):
    html: Annotated[str, Field(min_length=1, max_length=HTML_MAX_CHARS)]
    css: Annotated[str, Field(max_length=STYLE_MAX_CHARS)] = ""
    js: Annotated[str, Field(max_length=STYLE_MAX_CHARS)] = ""
    resources: Annotated[list[PageResource], Field(max_length=32)] = Field(default_factory=list)
    node_map: Annotated[list[PageNodeMapEntry], Field(max_length=2000)] = Field(default_factory=list)

    @model_validator(mode="after")
    def distinct_and_sized(self):
        if not self.html.strip():
            raise ValueError("html must contain visible source")
        unique([item.resource_id for item in self.resources])
        unique([item.node_id for item in self.node_map])
        encoded = len(self.html.encode()) + len(self.css.encode()) + len(self.js.encode())
        encoded += sum(item.byte_length for item in self.resources)
        if encoded > PACKAGE_MAX_BYTES:
            raise ValueError("页面源码包超过大小上限。")
        return self


class PageBinding(PageModel):
    binding_id: Opaque
    result_ref: Opaque
    node_id: Opaque | None = None
    data_ref: Opaque | None = None
    mode: ReadMode = "summary"


class PageBindingManifest(PageModel):
    bindings: Annotated[list[PageBinding], Field(max_length=64)] = Field(default_factory=list)
    result_refs: Annotated[list[Opaque], Field(max_length=64)] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_refs(self):
        unique([item.binding_id for item in self.bindings])
        unique(self.result_refs)
        declared = set(self.result_refs)
        for item in self.bindings:
            if item.result_ref not in declared:
                raise ValueError("binding result_ref must be listed in result_refs")
        return self


class PageDraft(PageModel):
    title: Title
    session_id: Opaque
    package: PagePackage
    binding_manifest: PageBindingManifest = Field(default_factory=PageBindingManifest)


class PageDocument(PageDraft):
    schema_version: Literal["free-page/v1"] = SCHEMA_VERSION
    page_id: Opaque
    version: Version
    binding_state: BindingState

    @model_validator(mode="after")
    def binding_matches_refs(self):
        unbound = len(self.binding_manifest.result_refs) == 0
        if unbound and self.binding_state != "UNBOUND_SAMPLE":
            raise ValueError("无 result_refs 时只能是 UNBOUND_SAMPLE")
        if not unbound and self.binding_state == "UNBOUND_SAMPLE":
            raise ValueError("未绑定页不能声明 result_refs")
        return self


class PagePatchPreview(PageModel):
    """D6: patch preview of source and/or manifest. Confirm is a separate call."""
    base_version: Version
    title: Title | None = None
    package: PagePackage | None = None
    binding_manifest: PageBindingManifest | None = None

    @model_validator(mode="after")
    def nonempty_nonnull(self):
        fields = self.model_fields_set - {"base_version"}
        if not fields or any(getattr(self, key) is None for key in fields):
            raise ValueError("a patch must have explicit non-null changes")
        return self


class PageSavePreview(PageModel):
    """D9: explicit save of the host in-memory draft. Exit-edit is not save."""
    base_version: Version
    title: Title
    package: PagePackage
    binding_manifest: PageBindingManifest


class PageRollbackPreview(PageModel):
    base_version: Version
    to_version: Version

    @model_validator(mode="after")
    def earlier_target(self):
        if self.to_version >= self.base_version:
            raise ValueError("rollback target must be older than the current base_version")
        return self


class PageSnapshot(PageModel):
    spec: PageDocument


class PagePreview(PageModel):
    preview_id: Opaque
    status: PreviewStatus
    operation: PageOperation
    base_version: Annotated[int, Field(ge=0, le=9007199254740991)]
    expires_at_ms: int
    snapshot: PageSnapshot


class PageRevision(PageModel):
    version: Version
    operation: PageOperation
    created_at_ms: int


class PageListItem(PageModel):
    page_id: Opaque
    title: Title
    version: Version
    session_id: Opaque
    binding_state: BindingState


class PageList(PageModel):
    items: list[PageListItem]


class PageCancelResult(PageModel):
    preview_id: Opaque
    status: Literal["CANCELLED"]


class PageBridgeHandshake(PageModel):
    protocol: Literal["free-page-bridge/v1"] = BRIDGE_PROTOCOL
    instance_id: Opaque
    page_id: Opaque
    version: Version
    nonce: Opaque


class PageBridgeEnvelope(PageModel):
    protocol: Literal["free-page-bridge/v1"] = BRIDGE_PROTOCOL
    instance_id: Opaque
    request_id: Opaque
    nonce: Opaque
    seq: Annotated[int, Field(ge=0, le=9007199254740991)]


class PageDataReadRequest(PageBridgeEnvelope):
    op: Literal["data.read"]
    result_ref: Opaque
    mode: ReadMode = "summary"
    cursor: Annotated[str, Field(min_length=1, max_length=256)] | None = None
    limit: Annotated[int, Field(ge=1, le=50)] = 50


class PageDataCancelRequest(PageBridgeEnvelope):
    op: Literal["data.cancel"]


class PageDataChunkEvent(PageBridgeEnvelope):
    op: Literal["data.chunk"]
    unit: Annotated[str, Field(min_length=1, max_length=24)] | None = None
    time_range: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    queried_at: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    source: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    row_count: Annotated[int, Field(ge=0, le=BRIDGE_MAX_CUMULATIVE_ROWS)] | None = None
    byte_length: Annotated[int, Field(ge=0, le=BRIDGE_MAX_RESPONSE_BYTES)] | None = None


class PageDataEndEvent(PageBridgeEnvelope):
    op: Literal["data.end"]


class PageDataErrorEvent(PageBridgeEnvelope):
    op: Literal["data.error"]
    code: Literal[
        "RESULT_UNAVAILABLE", "RESULT_STALE", "RESULT_REVOKED", "FORBIDDEN",
        "BRIDGE_NONCE", "BRIDGE_EXPIRED_INSTANCE", "BRIDGE_UNKNOWN_OP", "PACKAGE_TOO_LARGE",
    ]
    message: Annotated[str, Field(min_length=1, max_length=500)]


class PageBindingStateEvent(PageBridgeEnvelope):
    op: Literal["binding.state"]
    binding_state: BindingState


PageBridgeRequest = Annotated[Union[PageDataReadRequest, PageDataCancelRequest], Field(discriminator="op")]
PageBridgeEvent = Annotated[
    Union[PageDataChunkEvent, PageDataEndEvent, PageDataErrorEvent, PageBindingStateEvent],
    Field(discriminator="op"),
]

FORBIDDEN_BRIDGE_OPS = ("sql", "save", "http.fetch", "credential.read")


def _optional_omit_null(schema: dict, *fields: str) -> None:
    """D6 omit-fields: optional properties are absent, not explicit null."""
    props = schema.get("properties") or {}
    for name in fields:
        item = props.get(name)
        if not isinstance(item, dict):
            continue
        item.pop("default", None)
        options = item.get("anyOf")
        if not options:
            continue
        non_null = [option for option in options if option.get("type") != "null"]
        if len(non_null) != 1:
            continue
        replacement = dict(non_null[0])
        for key in ("title", "description"):
            if key in item and key not in replacement:
                replacement[key] = item[key]
        props[name] = replacement


def page_documents_openapi() -> dict:
    """Offline type source. HTTP tests also check actual route model bindings."""
    schemas = {}
    for model in (
        PageResource, PageNodeMapEntry, PagePackage, PageBinding, PageBindingManifest,
        PageDraft, PageDocument, PagePatchPreview, PageSavePreview, PageRollbackPreview,
        PageSnapshot, PagePreview, PageRevision, PageListItem, PageList, PageCancelResult,
        PageBridgeHandshake, PageDataReadRequest, PageDataCancelRequest,
        PageDataChunkEvent, PageDataEndEvent, PageDataErrorEvent, PageBindingStateEvent,
    ):
        schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
        schemas.update(schema.pop("$defs", {}))
        schemas[model.__name__] = schema
    _optional_omit_null(schemas["PagePatchPreview"], "title", "package", "binding_manifest")
    def json_ref(name):
        return {"$ref": f"#/components/schemas/{name}"}
    preview_ok = {"description": "Page preview", "content": {"application/json": {"schema": json_ref("PagePreview")}}}
    snapshot_ok = {"description": "Committed snapshot", "content": {"application/json": {"schema": json_ref("PageSnapshot")}}}
    def body(name):
        return {"required": True, "content": {"application/json": {"schema": json_ref(name)}}}
    page_param = {"name": "page_id", "in": "path", "required": True, "schema": {"type": "string", "pattern": IDENTITY}}
    preview_param = {"name": "preview_id", "in": "path", "required": True, "schema": {"type": "string", "pattern": IDENTITY}}
    idempotency = {"name": "Idempotency-Key", "in": "header", "required": True,
                   "schema": {"type": "string", "minLength": 1, "maxLength": 200}}
    return {
        "openapi": "3.1.0",
        "info": {"title": "Free Page Documents", "version": "free-page/v1",
                 "description": "Independent HTML page assets. Not BoardSpec. D6=PATCH confirm, D9=SAVE."},
        "x-page-http": True,
        "x-free-page-schema": SCHEMA_VERSION,
        "x-b0-board-spec-untouched": "board-spec/v1",
        "x-page-operations": ["GENERATE", "PATCH", "SAVE", "ROLLBACK"],
        "x-binding-states": ["UNBOUND_SAMPLE", "BOUND_VERIFIED", "BOUND_STALE"],
        "x-bridge-protocol": BRIDGE_PROTOCOL,
        "x-bridge-forbidden-ops": list(FORBIDDEN_BRIDGE_OPS),
        "x-page-errors": PAGE_ERRORS,
        "x-bridge-budget": {
            "max_response_bytes": BRIDGE_MAX_RESPONSE_BYTES,
            "max_cumulative_rows": BRIDGE_MAX_CUMULATIVE_ROWS,
        },
        "paths": {
            "/api/v1/analytics/page-documents/previews": {
                "post": {"operationId": "page_generate", "requestBody": body("PageDraft"),
                         "responses": {"201": preview_ok}},
            },
            "/api/v1/analytics/page-documents/previews/{preview_id}": {
                "get": {"operationId": "page_preview", "parameters": [preview_param],
                        "responses": {"200": preview_ok}},
            },
            "/api/v1/analytics/page-documents/previews/{preview_id}/confirm": {
                "post": {"operationId": "page_confirm", "parameters": [preview_param, idempotency],
                         "responses": {"200": snapshot_ok}},
            },
            "/api/v1/analytics/page-documents/previews/{preview_id}/cancel": {
                "post": {"operationId": "page_cancel", "parameters": [preview_param],
                         "responses": {"200": {"description": "Cancelled",
                                               "content": {"application/json": {"schema": json_ref("PageCancelResult")}}}}},
            },
            "/api/v1/analytics/page-documents/pages": {
                "get": {"operationId": "page_list",
                        "responses": {"200": {"description": "Metadata list",
                                              "content": {"application/json": {"schema": json_ref("PageList")}}}}},
            },
            "/api/v1/analytics/page-documents/pages/{page_id}": {
                "get": {"operationId": "page_get", "parameters": [page_param],
                        "responses": {"200": snapshot_ok}},
            },
            "/api/v1/analytics/page-documents/pages/{page_id}/versions": {
                "get": {"operationId": "page_history", "parameters": [page_param],
                        "responses": {"200": {"description": "History",
                                              "content": {"application/json": {
                                                  "schema": {"type": "array", "items": json_ref("PageRevision")}}}}}},
            },
            "/api/v1/analytics/page-documents/pages/{page_id}/patch-preview": {
                "post": {"operationId": "page_patch", "parameters": [page_param],
                         "requestBody": body("PagePatchPreview"), "responses": {"201": preview_ok}},
            },
            "/api/v1/analytics/page-documents/pages/{page_id}/save-preview": {
                "post": {"operationId": "page_save", "parameters": [page_param],
                         "requestBody": body("PageSavePreview"), "responses": {"201": preview_ok}},
            },
            "/api/v1/analytics/page-documents/pages/{page_id}/rollback-preview": {
                "post": {"operationId": "page_rollback", "parameters": [page_param],
                         "requestBody": body("PageRollbackPreview"), "responses": {"201": preview_ok}},
            },
        },
        "components": {"schemas": schemas},
    }
