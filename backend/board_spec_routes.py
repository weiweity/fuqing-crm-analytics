"""Authenticated library canvas routes; no untyped facts input or model saves."""
from fastapi import APIRouter, Request, Response

from backend.analytics_app import _single_header
from backend.contracts.board_spec import (
    BoardDraft, BoardLayoutPreview, BoardPatchPreview, BoardPreview,
    BoardRollbackPreview, BoardSnapshot, BoardRevision,
    BoardEditSelection, BoardEditProposal, BoardEditContext, BoardCurrentEdit,
)
from backend.services.analytics.access import AnalyticsError
from backend.services.analytics.board_result_adapter import board_generation_context


def board_spec_router(store, principal, computed_store=None):
    router = APIRouter(prefix="/api/v1/analytics/board-spec")

    def service():
        if store is None:
            raise AnalyticsError(503, "STATE_UNAVAILABLE", "看板保存库尚未显式配置。", retryable=True)
        return store

    def actor(request, response):
        response.headers["Cache-Control"] = "no-store"
        return principal(request)

    @router.get("/context")
    def context(session_id: str, request: Request, response: Response, offset: int = 0):
        who = actor(request, response)
        boards = service()  # Do not advertise generation when board persistence is unavailable.
        return board_generation_context(computed_store, who, session_id, offset=offset, board_store=boards)

    @router.post("/previews", response_model=BoardPreview, status_code=201)
    def generate(payload: BoardDraft, request: Request, response: Response):
        who = actor(request, response)
        return service().generate(who, payload)

    @router.post("/boards/{board_id}/edit-context", response_model=BoardEditContext, status_code=201)
    def select_edit(board_id: str, payload: BoardEditSelection, request: Request, response: Response):
        return service().select_edit(actor(request, response), board_id, payload)

    @router.get("/boards/{board_id}/edit-context", response_model=BoardCurrentEdit)
    def current_edit(board_id: str, request: Request, response: Response):
        return {"context": service().current_edit(actor(request, response), board_id)}

    @router.get("/edit-contexts/{context_id}", response_model=BoardEditContext)
    def edit_context(context_id: str, session_id: str, request: Request, response: Response):
        return service().edit_context(actor(request, response), context_id, session_id=session_id)

    @router.post("/edit-contexts/{context_id}/propose", response_model=BoardPreview, status_code=201)
    def propose_edit(context_id: str, payload: BoardEditProposal, request: Request, response: Response):
        return service().propose_edit(actor(request, response), context_id, payload)

    @router.post("/edit-contexts/{context_id}/cancel")
    def cancel_edit(context_id: str, request: Request, response: Response):
        return service().cancel_edit(actor(request, response), context_id)

    @router.get("/previews/{preview_id}", response_model=BoardPreview)
    def preview(preview_id: str, request: Request, response: Response):
        who = actor(request, response)
        return service().preview(who, preview_id)

    @router.post("/previews/{preview_id}/confirm", response_model=BoardSnapshot)
    def confirm(preview_id: str, request: Request, response: Response):
        who = actor(request, response)
        return service().confirm(who, preview_id, _single_header(request, "idempotency-key"))

    @router.post("/previews/{preview_id}/cancel")
    def cancel(preview_id: str, request: Request, response: Response):
        who = actor(request, response)
        return service().cancel(who, preview_id)

    @router.get("/boards")
    def list_boards(request: Request, response: Response, limit: int = 100, offset: int = 0):
        who = actor(request, response)
        return {"items": service().list(who, limit=limit, offset=offset)}

    @router.get("/boards/{board_id}", response_model=BoardSnapshot)
    def get_board(board_id: str, request: Request, response: Response, version: int | None = None):
        who = actor(request, response)
        return service().get(who, board_id, version)

    @router.get("/boards/{board_id}/versions", response_model=list[BoardRevision])
    def history(board_id: str, request: Request, response: Response, limit: int = 100, offset: int = 0):
        who = actor(request, response)
        return service().history(who, board_id, limit=limit, offset=offset)

    @router.post("/boards/{board_id}/patch-preview", response_model=BoardPreview, status_code=201)
    def patch(board_id: str, payload: BoardPatchPreview, request: Request, response: Response):
        who = actor(request, response)
        return service().patch(who, board_id, payload)

    @router.post("/boards/{board_id}/layout-preview", response_model=BoardPreview, status_code=201)
    def layout(board_id: str, payload: BoardLayoutPreview, request: Request, response: Response):
        who = actor(request, response)
        return service().layout(who, board_id, payload)

    @router.post("/boards/{board_id}/rollback-preview", response_model=BoardPreview, status_code=201)
    def rollback(board_id: str, payload: BoardRollbackPreview, request: Request, response: Response):
        who = actor(request, response)
        return service().rollback(who, board_id, payload)

    return router
