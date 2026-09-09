"""Versioned HTTP chart preference; frozen C0 and B0 schemas stay unchanged."""
from typing import Literal

from backend.contracts.analytics import OpaqueId
from backend.contracts.competition_c0 import CompetitionModel, IdempotencyKey, PatchIntent, PositiveVersion


class CompetitionChartPatchRequest(CompetitionModel):
    schema_version: Literal["competition-board-chart-patch/v1"] = "competition-board-chart-patch/v1"
    board_id: OpaqueId
    block_id: OpaqueId
    base_version: PositiveVersion
    attempt_id: OpaqueId
    idempotency_key: IdempotencyKey
    intent: Literal[PatchIntent.STYLE_ONLY] = PatchIntent.STYLE_ONLY
    chart_type: Literal["TABLE", "BAR", "LINE", "METRIC", "EVIDENCE"]


def chart_openapi() -> dict:
    schema = CompetitionChartPatchRequest.model_json_schema(ref_template="#/components/schemas/{model}")
    definitions = schema.pop("$defs", {})
    return {"openapi": "3.1.0", "info": {"title": "Competition chart preference", "version": "1"},
            "paths": {}, "x-runtime-extension": "competition-board-chart-patch/v1",
            "components": {"schemas": {**definitions, "CompetitionChartPatchRequest": schema}}}
