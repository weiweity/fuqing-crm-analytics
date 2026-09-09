"""C0 error helpers for the diagnosis adapter. No HTTP."""

from __future__ import annotations

from backend.contracts.competition_c0 import CompetitionErrorDetail, CompetitionErrorResponse
from backend.services.analytics.competition_diagnosis.chain import DOC_T06, DOC_T08, DOC_T10, DOC_T13


class DiagnosisFault(Exception):
    """Structured C0 error; not a successful ResultRef."""

    def __init__(self, response: CompetitionErrorResponse):
        super().__init__(response.error.code)
        self.response = response

    @property
    def error(self) -> CompetitionErrorDetail:
        return self.response.error


def c0_error(
    *,
    code: str,
    message: str,
    request_id: str,
    http_status: int,
    param: str | None = None,
    retryable: bool = False,
    retry_after: int | None = None,
    doc_ref: str | None = None,
) -> DiagnosisFault:
    return DiagnosisFault(CompetitionErrorResponse(error=CompetitionErrorDetail(
        code=code,
        message=message,
        param=param,
        retryable=retryable,
        retry_after=retry_after,
        request_id=request_id,
        doc_ref=doc_ref,
        recovery_url=None,
        http_status=http_status,
        maps_to="backend.contracts.analytics.AnalyticsErrorDetail",
    )))


def invalid_request(message: str, request_id: str, param: str) -> DiagnosisFault:
    return c0_error(
        code="INVALID_REQUEST", message=message, param=param, request_id=request_id,
        http_status=422, doc_ref=DOC_T13,
    )


def needs_input(message: str, request_id: str, param: str) -> DiagnosisFault:
    return c0_error(
        code="NEEDS_INPUT", message=message, param=param, request_id=request_id,
        http_status=422, doc_ref=DOC_T13,
    )


def forbidden(message: str, request_id: str, param: str) -> DiagnosisFault:
    return c0_error(
        code="FORBIDDEN", message=message, param=param, request_id=request_id,
        http_status=403, doc_ref=DOC_T06,
    )


def unauthenticated(request_id: str) -> DiagnosisFault:
    return c0_error(
        code="UNAUTHENTICATED", message="需要本次有效身份。", param="Authorization",
        request_id=request_id, http_status=401, doc_ref=DOC_T06,
    )


def unsupported_capability(message: str, request_id: str, param: str) -> DiagnosisFault:
    return c0_error(
        code="UNSUPPORTED_CAPABILITY", message=message, param=param, request_id=request_id,
        http_status=422, doc_ref=DOC_T13,
    )


def not_connected(message: str, request_id: str, param: str) -> DiagnosisFault:
    return c0_error(
        code="NOT_CONNECTED", message=message, param=param, request_id=request_id,
        http_status=503, retryable=True, retry_after=1, doc_ref=DOC_T08,
    )


def budget_exhausted(request_id: str) -> DiagnosisFault:
    return c0_error(
        code="BUDGET_EXHAUSTED", message="单次诊断预算已耗尽，分析未完成。",
        param="max_tool_calls", request_id=request_id, http_status=429,
        retryable=False, doc_ref=DOC_T08,
    )


def cancelled(request_id: str) -> DiagnosisFault:
    return c0_error(
        code="CANCELLED", message="本次诊断已取消，分析未完成。",
        param="run_id", request_id=request_id, http_status=409, doc_ref=DOC_T08,
    )


def busy(request_id: str) -> DiagnosisFault:
    return c0_error(
        code="STATE_UNAVAILABLE", message="状态暂不可用。",
        request_id=request_id, http_status=503, retryable=True, retry_after=1,
        doc_ref=DOC_T08,
    )


def invalid_patch(message: str, request_id: str, param: str) -> DiagnosisFault:
    return c0_error(
        code="MODEL_INVALID_PATCH", message=message, param=param, request_id=request_id,
        http_status=422, doc_ref=DOC_T10,
    )


def roi_unsupported(request_id: str) -> DiagnosisFault:
    return c0_error(
        code="ROI_UNSUPPORTED",
        message="GSV 下降不能断言最佳投放 ROI；缺成本/毛利/增量时只给试验优先级。",
        param="roi", request_id=request_id, http_status=422, doc_ref=DOC_T13,
    )


def injection_refused(request_id: str, param: str) -> DiagnosisFault:
    return c0_error(
        code="PROMPT_INJECTION_REFUSED",
        message="用户指令不能扩大工具权限或暴露未登记路由。",
        param=param, request_id=request_id, http_status=403, doc_ref=DOC_T13,
    )
