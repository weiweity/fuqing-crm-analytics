"""C0 audience/draft errors. Not an HTTP surface."""

from __future__ import annotations

from uuid import uuid4

from backend.contracts.competition_c0 import CompetitionErrorDetail, CompetitionErrorResponse

DOC_T05 = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T05"
DOC_T06 = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T06"
DOC_T12 = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T12"
DOC_T14 = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T14"


class CompetitionAudienceError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        param: str | None = None,
        retryable: bool = False,
        retry_after: int | None = None,
        request_id: str | None = None,
        doc_ref: str | None = None,
        recovery_url: str | None = None,
    ):
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message
        self.param = param
        self.retryable = retryable
        self.retry_after = retry_after
        self.request_id = request_id or f"req_a8_{uuid4().hex}"
        self.doc_ref = doc_ref
        self.recovery_url = recovery_url

    def to_detail(self) -> CompetitionErrorDetail:
        return CompetitionErrorDetail(
            code=self.code,
            message=self.message,
            param=self.param,
            retryable=self.retryable,
            retry_after=self.retry_after,
            request_id=self.request_id,
            doc_ref=self.doc_ref,
            recovery_url=self.recovery_url,
            http_status=self.status,
            maps_to="backend.contracts.analytics.AnalyticsErrorDetail",
        )

    def to_response(self) -> CompetitionErrorResponse:
        return CompetitionErrorResponse(error=self.to_detail())


def unauthenticated(message: str = "需要本次有效身份。") -> CompetitionAudienceError:
    return CompetitionAudienceError(
        401, "UNAUTHENTICATED", message, param="Authorization",
        doc_ref=DOC_T06, request_id=f"req_a8_{uuid4().hex}",
    )


def forbidden(*, param: str = "customer_key", message: str = "当前身份无权预览该候选明细。") -> CompetitionAudienceError:
    return CompetitionAudienceError(
        403, "FORBIDDEN", message, param=param, doc_ref=DOC_T06,
        request_id=f"req_a8_{uuid4().hex}",
    )


def invalid(message: str, *, param: str | None = None, doc_ref: str = DOC_T05) -> CompetitionAudienceError:
    return CompetitionAudienceError(
        422, "INVALID_REQUEST", message, param=param, doc_ref=doc_ref,
        request_id=f"req_a8_{uuid4().hex}",
    )


def unsupported(message: str, *, param: str, doc_ref: str = DOC_T05) -> CompetitionAudienceError:
    return CompetitionAudienceError(
        422, "UNSUPPORTED_FILTER", message, param=param, doc_ref=doc_ref,
        request_id=f"req_a8_{uuid4().hex}",
    )


def conflict(message: str = "草稿 base_version 冲突，未覆盖。", *, param: str = "version") -> CompetitionAudienceError:
    return CompetitionAudienceError(
        409, "VERSION_CONFLICT", message, param=param, doc_ref=DOC_T12,
        request_id=f"req_a8_{uuid4().hex}",
    )


def unavailable(message: str = "人群草稿状态暂不可用。") -> CompetitionAudienceError:
    return CompetitionAudienceError(
        503, "STATE_UNAVAILABLE", message, retryable=True, retry_after=1,
        doc_ref="docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T08",
        request_id=f"req_a8_{uuid4().hex}",
    )
