"""Library BoardSpec HTTP contract. Catalogue is shared with the plugin, offline.

This is the new canvas contract, not the frozen C0 board or legacy CRM schema.
No submitted document carries facts, executable code, an owner or a saved version.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Annotated, Literal, Union

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, create_model, model_validator

CATALOG = json.loads((Path(__file__).resolve().parents[2] /
    "dsh-plugins/analytics-workbench/src/board-spec/component-catalog.json").read_text())
DEFINITIONS = {item["kind"]: item for item in CATALOG["components"]}
Opaque = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")]
Title = Annotated[str, Field(min_length=1, max_length=160, pattern=r"\S")]
Version = Annotated[int, Field(ge=1, le=9007199254740991)]


class BoardModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class FunnelStage(BoardModel):
    label: Title
    count: Annotated[int, Field(ge=0, le=9007199254740991)]


class FunnelFacts(BoardModel):
    """Server-owned nested customer cohorts; rates are derived, never AI props."""
    unit: Literal["人"]
    cohort_label: Annotated[str, Field(min_length=1, max_length=240, pattern=r"\S")]
    counting_rule: Annotated[str, Field(min_length=1, max_length=1000, pattern=r"\S")]
    stages: Annotated[list[FunnelStage], Field(min_length=2, max_length=12)]

    @model_validator(mode="after")
    def nested(self):
        labels = [stage.label for stage in self.stages]
        counts = [stage.count for stage in self.stages]
        if len(set(labels)) != len(labels) or counts != sorted(counts, reverse=True):
            raise ValueError("funnel stages must be distinct and nonincreasing nested customer counts")
        return self


class WaterfallValue(BoardModel):
    label: Title
    value: float


class WaterfallFacts(BoardModel):
    """Trusted facts only; intentionally not accepted as a component property."""
    unit: Annotated[str, Field(min_length=1, max_length=24, pattern=r"\S")]
    start: WaterfallValue
    end: WaterfallValue
    contributions: Annotated[list[WaterfallValue], Field(max_length=200)]

    @model_validator(mode="after")
    def conserved(self):
        labels = [item.label for item in self.contributions]
        if len(set(labels)) != len(labels):
            raise ValueError("waterfall contribution labels must be distinct")
        try:
            running = self.start.value
            for item in self.contributions:
                running = math.fsum([running, item.value])
                if not math.isfinite(running):
                    raise ValueError("waterfall cumulative value is outside finite range")
        except OverflowError as error:
            raise ValueError("waterfall cumulative value is outside finite range") from error
        if not math.isclose(running, self.end.value, rel_tol=1e-12, abs_tol=1e-8):
            raise ValueError("waterfall contributions must reconcile the start and end")
        return self


def unique(values):
    if len(set(values)) != len(values):
        raise ValueError("items must be unique")
    return values


def calendar_date(value):
    date.fromisoformat(value)
    return value


def property_type(rule, name="Property"):
    if "enum" in rule:
        return Literal[tuple(rule["enum"])]
    if rule["type"] == "boolean":
        return bool
    if rule["type"] == "integer":
        return Annotated[int, Field(ge=rule["minimum"], le=rule["maximum"])]
    if rule["type"] == "string":
        value = Annotated[str, Field(min_length=rule.get("minLength", 0), max_length=rule["maxLength"],
            pattern=rule.get("pattern"), json_schema_extra={"format": "date"} if rule.get("format") == "date" else {})]
        return Annotated[value, AfterValidator(calendar_date)] if rule.get("format") == "date" else value
    if rule["type"] == "array":
        value = Annotated[list[property_type(rule["items"], name + "Item")], Field(
            min_length=rule.get("minItems", 0), max_length=rule["maxItems"],
            json_schema_extra={"uniqueItems": rule.get("uniqueItems", False)})]
        return Annotated[value, AfterValidator(unique)] if rule.get("uniqueItems") else value
    if rule["type"] == "object":
        return create_model(name, __base__=BoardModel, **{
            key: (property_type(item, name + key.title()), ... if key in rule.get("required", []) else item["default"])
            for key, item in rule["properties"].items()})
    raise ValueError("unregistered catalogue property type")


class BoardLayout(BoardModel):
    x: Annotated[int, Field(ge=0, le=CATALOG["grid"]["columns"])]
    y: Annotated[int, Field(ge=0, le=CATALOG["grid"]["max_rows"])]
    w: Annotated[int, Field(ge=1, le=CATALOG["grid"]["columns"])]
    h: Annotated[int, Field(ge=1, le=CATALOG["grid"]["max_rows"])]


class ComponentBase(BoardModel):
    block_id: Opaque
    title: Title
    library_version: Literal[CATALOG["library_version"]] = CATALOG["library_version"]
    layout: BoardLayout

    @model_validator(mode="after")
    def dimensions(self):
        minimum = DEFINITIONS[self.kind]["min_size"]
        box = self.layout
        if (box.w < minimum["w"] or box.h < minimum["h"]
                or box.x + box.w > CATALOG["grid"]["columns"]
                or box.y + box.h > CATALOG["grid"]["max_rows"]):
            raise ValueError("component layout is outside its registered bounds")
        if DEFINITIONS[self.kind].get("allows_result") is False and self.source_result_id is not None:
            raise ValueError("planning content must not impersonate a verified result")
        if self.kind in {"PROCESS", "TIMELINE"}:
            items = self.props.nodes if self.kind == "PROCESS" else self.props.events
            unique([item.id for item in items])
        if self.kind == "PROCESS":
            ids = {node.id for node in self.props.nodes}
            edges = [edge.model_dump() for edge in self.props.edges]
            if any(edge["from"] not in ids or edge["to"] not in ids for edge in edges):
                raise ValueError("process edge references a missing node")
            unique([(edge["from"], edge["to"], edge["label"]) for edge in edges])
        return self


COMPONENT_MODELS = []
for kind, definition in DEFINITIONS.items():
    rules = {**CATALOG["common_properties"], **definition["properties"]}
    props = create_model(f"Board{kind}Props", __base__=BoardModel,
        **{name: (property_type(rule, f"Board{kind}{name.title()}"), Field(default=rule["default"])) for name, rule in rules.items()})
    COMPONENT_MODELS.append(create_model(f"Board{kind}Block", __base__=ComponentBase,
        kind=(Literal[kind], ...), props=(props, Field(default_factory=props)),
        source_result_id=(Opaque, ...) if definition["requires_result"] else
            (None, None) if definition.get("allows_result") is False else (Opaque | None, None)))
BoardBlock = Annotated[Union[tuple(COMPONENT_MODELS)], Field(discriminator="kind")]


class BoardDraft(BoardModel):
    title: Title
    session_id: Opaque
    blocks: Annotated[list[BoardBlock], Field(min_length=1, max_length=60)]

    @model_validator(mode="after")
    def distinct_nonoverlapping_blocks(self):
        unique([block.block_id for block in self.blocks])
        for index, block in enumerate(self.blocks):
            a = block.layout
            for other in self.blocks[:index]:
                b = other.layout
                if a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h:
                    raise ValueError("component layouts must not overlap")
        return self


class BoardDocument(BoardDraft):
    schema_version: Literal["board-spec/v1"] = "board-spec/v1"
    board_id: Opaque
    version: Version


class BlockChanges(BoardModel):
    title: Title | None = None
    props: dict[str, object] | None = None
    layout: BoardLayout | None = None
    kind: Literal[tuple(DEFINITIONS)] | None = None
    source_result_id: Opaque | None = None

    @model_validator(mode="after")
    def nonempty_nonnull(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("a patch must have explicit non-null changes")
        return self


class BoardPatchPreview(BoardModel):
    base_version: Version
    block_id: Opaque
    changes: BlockChanges


class BoardEditSelection(BoardModel):
    """Created by the UI, never by a model tool. Session comes from the saved board."""
    base_version: Version
    block_id: Opaque


class BoardEditProposal(BoardModel):
    # The host supplies its executing native session, not model arguments.
    session_id: Opaque
    changes: BlockChanges


class BoardEditContext(BoardModel):
    schema_version: Literal["board-edit-context/v1"] = "board-edit-context/v1"
    edit_context_id: Opaque
    board_id: Opaque
    base_version: Version
    block_id: Opaque
    session_id: Opaque
    expires_at_ms: int
    status: Literal["OPEN", "PROPOSED", "CANCELLED", "APPLIED"]
    preview_id: Opaque | None
    block: BoardBlock
    facts_by_result_id: dict[str, dict]


class BoardCurrentEdit(BoardModel):
    context: BoardEditContext | None


class LayoutChange(BoardModel):
    block_id: Opaque
    layout: BoardLayout


class BoardLayoutPreview(BoardModel):
    base_version: Version
    layouts: Annotated[list[LayoutChange], Field(min_length=1, max_length=60)]


class BoardRollbackPreview(BoardModel):
    base_version: Version
    to_version: Version


class BoardSnapshot(BoardModel):
    spec: BoardDocument
    # Only server result resolvers may construct this field. No input route accepts it.
    facts_by_result_id: dict[str, dict]


class BoardPreview(BoardModel):
    preview_id: Opaque
    status: Literal["PENDING", "APPLIED", "CANCELLED"]
    operation: Literal["GENERATE", "PATCH", "LAYOUT", "ROLLBACK"]
    base_version: Annotated[int, Field(ge=0, le=9007199254740991)]
    expires_at_ms: int
    snapshot: BoardSnapshot


class BoardRevision(BoardModel):
    version: Version
    operation: Literal["GENERATE", "PATCH", "LAYOUT", "ROLLBACK"]
    created_at_ms: int


def board_spec_openapi() -> dict:
    """Offline type source; the HTTP tests also check actual route model bindings."""
    schemas = {}
    for model in (BoardDraft, BoardDocument, BoardPatchPreview, BoardLayoutPreview,
                  BoardRollbackPreview, BoardSnapshot, BoardPreview, BoardRevision,
                  BoardEditSelection, BoardEditProposal, BoardEditContext, BoardCurrentEdit):
        schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
        schemas.update(schema.pop("$defs", {}))
        schemas[model.__name__] = schema
    return {"openapi": "3.1.0", "info": {"title": "Library BoardSpec", "version": "1"},
            "paths": {}, "components": {"schemas": schemas}}
