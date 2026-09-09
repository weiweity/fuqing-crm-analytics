"""
人群看板路由

前缀: /api/v1/audience/*
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import date, timedelta
from typing import Any, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ConfigDict

from backend.contracts.audience import AudienceSummaryRequest
from backend.contracts.schemas import AudienceTableResponse
from backend.middleware.query_router import (
    DOC_T03,
    DOC_T06,
    DOC_T07,
    competition_error_response,
    new_request_id,
    overlay_live_capabilities,
)
from backend.services import PeriodBuilder, check_future_date
from backend.services.metrics_service import calculate_audience_summary, get_audience_table

router = APIRouter(prefix="/api/v1/audience", tags=["人群看板"])

_PERIODS = frozenset({"wtd", "mtd", "ytd", "q1", "q2", "q3", "q4"})
_SILENT_FILTERS = frozenset({
    "timezone",
    "data_cutoff",
    "sample_mode",
    "sample_channels",
    "history_scope",
    "as_of",
    "as_of_date",
    "member_status",
    "member_only",
})
_SUMMARY_QUERY_ALLOWED = frozenset({
    "year",
    "metric_type",
    "period",
    "start_date",
    "end_date",
    "channel",
    "exclude_channels",
    "compare_start_date",
    "compare_end_date",
    "order_ids",
    "product_ids",
})
_TABLE_QUERY_ALLOWED = frozenset({
    "dimension",
    "mode",
    "start_date",
    "end_date",
    "channels",
    "metric_type",
    "exclude_channels",
    "member_only",
    "compare_start_date",
    "compare_end_date",
})
_RESULT_LOCK = threading.Lock()
_RESULT_STORE: dict[str, dict[str, Any]] = {}


class AudienceSummaryBindRequest(AudienceSummaryRequest):
    """HTTP bind: expose product_ids without changing the A1 AudienceSummaryRequest schema."""

    model_config = ConfigDict(extra="allow")
    product_ids: Optional[List[str]] = None


def _request_id(request: Request) -> str:
    return new_request_id(request.headers.get("x-request-id"))


def _error(
    request: Request,
    *,
    http_status: int,
    code: str,
    message: str,
    retryable: bool,
    param: str | None = None,
    retry_after: int | None = None,
    doc_ref: str = DOC_T03,
) -> JSONResponse:
    return competition_error_response(
        http_status=http_status,
        code=code,
        message=message,
        request_id=_request_id(request),
        retryable=retryable,
        param=param,
        retry_after=retry_after,
        doc_ref=doc_ref,
    )


def _require_actor(request: Request) -> str | JSONResponse:
    username = getattr(request.state, "username", None)
    if isinstance(username, dict):
        username = username.get("username")
    if username:
        return str(username)
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return _error(
            request,
            http_status=401,
            code="UNAUTHENTICATED",
            message="需要本次有效身份。",
            retryable=False,
            param="Authorization",
            doc_ref=DOC_T06,
        )
    from backend.routers.auth import _verify_token

    verified = _verify_token(auth[7:])
    if isinstance(verified, dict):
        verified = verified.get("username")
    if not verified:
        return _error(
            request,
            http_status=401,
            code="UNAUTHENTICATED",
            message="登录已过期，请重新登录。",
            retryable=False,
            param="Authorization",
            doc_ref=DOC_T06,
        )
    return str(verified)


def _actor_capabilities(username: str) -> set[str]:
    caps = {"analysis:read"}
    try:
        from backend.routers.auth import is_admin_username

        if is_admin_username(username):
            caps.update({"analysis:save", "dashboard:read", "dashboard:update"})
    except Exception:  # noqa: BLE001
        pass
    return caps


def _reject_unknown_query(request: Request, allowed: frozenset[str]) -> JSONResponse | None:
    for key in request.query_params.keys():
        if key not in allowed:
            return _error(
                request,
                http_status=422,
                code="INVALID_REQUEST",
                message=f"未实现或未暴露的筛选 {key} 不得忽略。",
                retryable=False,
                param=key,
            )
        if key in _SILENT_FILTERS and key != "member_only":
            return _error(
                request,
                http_status=422,
                code="INVALID_REQUEST",
                message=f"筛选 {key} 当前无计算后端，拒绝静默丢弃。",
                retryable=False,
                param=key,
            )
    return None


def _require_gsv(request: Request, metric_type: str) -> JSONResponse | None:
    if (metric_type or "").upper() != "GSV":
        return _error(
            request,
            http_status=422,
            code="INVALID_REQUEST",
            message="metric_type 仅接受 GSV；GMV 不得当 GSV 成功。",
            retryable=False,
            param="metric_type",
        )
    return None


def _require_ordered_dates(
    request: Request,
    start_date: Optional[str],
    end_date: Optional[str],
) -> JSONResponse | None:
    if not start_date or not end_date:
        return None
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        return _error(
            request,
            http_status=422,
            code="INVALID_REQUEST",
            message="start_date/end_date 必须是 YYYY-MM-DD。",
            retryable=False,
            param="start_date",
        )
    if end < start:
        return _error(
            request,
            http_status=422,
            code="INVALID_REQUEST",
            message="end_date 不得早于 start_date。",
            retryable=False,
            param="end_date",
        )
    return None


def _normalize_period(request: Request, period: Optional[str]) -> tuple[str | None, JSONResponse | None]:
    if period is None or period == "":
        return None, None
    key = period.lower()
    if key not in _PERIODS:
        return None, _error(
            request,
            http_status=422,
            code="INVALID_REQUEST",
            message="period 仅接受 WTD/MTD/YTD/Q1-Q4。",
            retryable=False,
            param="period",
        )
    return key, None


def _executed_windows(
    period: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    compare_start_date: Optional[str],
    compare_end_date: Optional[str],
) -> dict[str, Any]:
    windows: dict[str, Any] = {
        "period": period.upper() if period else None,
        "start_date": start_date,
        "end_date": end_date,
        "compare_start_date": compare_start_date,
        "compare_end_date": compare_end_date,
        "cutoff": None,
        "comparison_start": compare_start_date,
        "comparison_end": compare_end_date,
        "cutoff_policy": None,
    }
    if period:
        ranges = getattr(PeriodBuilder, period)(today=date.today())
        current = ranges["current"]
        comparison = ranges["comparison"]
        windows.update({
            "start_date": current.start,
            "end_date": current.end,
            "cutoff": current.cutoff,
            "comparison_start": comparison.start,
            "comparison_end": comparison.end,
            "cutoff_policy": "period_builder_start_minus_one",
        })
        return windows
    if start_date and end_date:
        start = date.fromisoformat(start_date)
        # Echo the legacy custom branch the service still runs: month-start minus
        # one day. C0 wants start-1; A2 must change compute. Bind does not lie.
        month_start = date(start.year, start.month, 1)
        windows["cutoff"] = (month_start - timedelta(days=1)).isoformat()
        windows["cutoff_policy"] = "legacy_month_start_minus_one"
        windows["limitations"] = [
            "自定义 start/end 仍走 audience_summary 月初 cutoff；C0 要求 start-1。",
        ]
    return windows


def _digest(payload: Any) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _page_for(total: int, offset: int, limit: int, checksum: str) -> dict[str, Any]:
    limit = max(1, min(500, limit))
    offset = max(0, offset)
    unread = offset + limit < total
    return {
        "offset": offset,
        "limit": limit,
        "total": total,
        "checksum": checksum,
        "complete": not unread,
    }


def _wrap_summary_result(
    *,
    owner: str,
    facts: dict[str, Any],
    windows: dict[str, Any],
    product_ids: Optional[List[str]],
) -> dict[str, Any]:
    from backend.contracts.competition_c0 import CompetitionResultRef, empty_result, success_result

    indicators = facts.get("indicators") or []
    row_count = len(indicators)
    checksum = _digest({"facts": facts, "windows": windows, "product_ids": product_ids or []})
    result_id = f"result_{uuid4().hex}"
    if row_count == 0:
        data = empty_result().model_dump(mode="json")
    else:
        data = success_result().model_dump(mode="json")
        data["completeness"] = "COMPLETE"
        data["empty_reason"] = None
        data["facts_schema_ref"] = "backend.contracts.audience.AudienceSummaryResponse"
        data["existing_result_schema"] = "none"
        data["query_id"] = "audience_summary"
        data["query_version"] = "competition-metrics/v1"
        data["metric_id"] = "gsv_summary"
        data["metric_version"] = "competition-metrics/v1"
    data["result_id"] = result_id
    data["run_id"] = f"run_{uuid4().hex[:16]}"
    data["primary_result_ref"] = result_id
    data["row_count"] = row_count
    data["evidence_digest"] = checksum
    data["contains_real_data"] = False
    data["data_mode"] = "SNAPSHOT"
    data["page"] = None if row_count == 0 else _page_for(row_count, 0, 50, checksum)
    extra_limits = list(data.get("limitations") or [])
    extra_limits.append("HTTP bind echoes executed windows; A2 custom cutoff may still be month-start.")
    data["limitations"] = extra_limits
    ref = CompetitionResultRef.model_validate(data)
    record = {
        "owner": owner,
        "facts": facts,
        "windows": windows,
        "checksum": checksum,
        "result_ref": ref.model_dump(mode="json"),
        "product_ids": list(product_ids or []),
    }
    with _RESULT_LOCK:
        _RESULT_STORE[result_id] = record
    return record


@router.get("/table", response_model=AudienceTableResponse)
def get_audience_table_api(
    request: Request,
    response: Response,
    dimension: str = Query(default="channel", description="维度：channel 或 spu_tier"),
    mode: str = Query(default="mtd", description="模式：mtd 或 free"),
    start_date: Optional[str] = Query(default=None, description="开始日期（free模式必填）"),
    end_date: Optional[str] = Query(default=None, description="结束日期（free模式必填）"),
    channels: Optional[str] = Query(default=None, description="逗号分隔的渠道列表"),
    metric_type: str = Query(default="GSV", description="指标类型：仅 GSV"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
    member_only: bool = Query(default=False, description="仅会员行；service 已支持"),
    compare_start_date: Optional[str] = Query(default=None, description="table 无自选对比，传入则 422"),
    compare_end_date: Optional[str] = Query(default=None, description="table 无自选对比，传入则 422"),
):
    """
    人群看板主表

    默认 MTD 同月对比（当年MTD vs 去年MTD），
    支持自由时间段筛选和渠道筛选。
    返回 24 个指标字段。
    """
    actor = _require_actor(request)
    if isinstance(actor, JSONResponse):
        return actor
    unknown = _reject_unknown_query(request, _TABLE_QUERY_ALLOWED)
    if unknown:
        return unknown
    gsv_error = _require_gsv(request, metric_type)
    if gsv_error:
        return gsv_error
    if compare_start_date is not None or compare_end_date is not None:
        return _error(
            request,
            http_status=422,
            code="INVALID_REQUEST",
            message="audience/table 无自选对比期；传入 compare_* 不得忽略。",
            retryable=False,
            param="compare_start_date",
        )
    if mode == "free" and (not start_date or not end_date):
        return _error(
            request,
            http_status=422,
            code="INVALID_REQUEST",
            message="free 模式需要传入 start_date 和 end_date。",
            retryable=False,
            param="start_date",
        )
    date_error = _require_ordered_dates(request, start_date, end_date)
    if date_error:
        return date_error
    if warning := check_future_date(start_date) or check_future_date(end_date):
        response.headers["X-Data-Warning"] = warning

    channel_list = None
    if channels:
        channel_list = [ch.strip() for ch in channels.split(",") if ch.strip()]

    return get_audience_table(
        dimension=dimension,
        mode=mode,
        start_date=start_date,
        end_date=end_date,
        channels=channel_list,
        metric_type="GSV",
        exclude_channels=exclude_channels,
        member_only=member_only,
    )


@router.get("/summary")
def get_audience_summary_api(
    request: Request,
    response: Response,
    year: int = Query(default=2026, description="对比基准年（仅影响列标签）"),
    metric_type: str = Query(default="GSV", description="仅 GSV"),
    period: Optional[str] = Query(default=None, description="WTD / MTD / YTD / Q1-Q4"),
    start_date: Optional[str] = Query(default=None, description="开始日期 YYYY-MM-DD（period为空时使用）"),
    end_date: Optional[str] = Query(default=None, description="结束日期 YYYY-MM-DD（period为空时使用）"),
    channel: Optional[str] = Query(default=None, description="渠道筛选"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
    order_ids: Optional[List[str]] = Query(default=None, description="订单号列表，仅统计匹配订单"),
    product_ids: Optional[List[str]] = Query(default=None, description="产品 ID 列表，透传 service"),
):
    """
    人群看板汇总接口

    一次返回三块数据：
    - Panel A：30指标对比（__TOTAL__ 全店，3年同比）
    - Panel B：渠道概览-全店（各渠道 GSV，3年同比 + 占比）
    - Panel C：渠道概览-会员（各渠道会员 GSV，3年同比 + 占比）
    """
    return _calculate_summary(
        request,
        response,
        year,
        metric_type,
        period,
        start_date,
        end_date,
        channel,
        exclude_channels,
        compare_start_date,
        compare_end_date,
        order_ids,
        product_ids,
    )


def _calculate_summary(
    request: Request,
    response: Response,
    year: int,
    metric_type: str,
    period: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    channel: Optional[str],
    exclude_channels: Optional[List[str]],
    compare_start_date: Optional[str],
    compare_end_date: Optional[str],
    order_ids: Optional[List[str]],
    product_ids: Optional[List[str]],
    extra_fields: dict[str, Any] | None = None,
):
    actor = _require_actor(request)
    if isinstance(actor, JSONResponse):
        return actor
    unknown = _reject_unknown_query(request, _SUMMARY_QUERY_ALLOWED)
    if unknown:
        return unknown
    if extra_fields:
        for key in extra_fields:
            if key in AudienceSummaryBindRequest.model_fields:
                continue
            return _error(
                request,
                http_status=422,
                code="INVALID_REQUEST",
                message=f"未实现或未暴露的筛选 {key} 不得忽略。",
                retryable=False,
                param=key,
            )
    gsv_error = _require_gsv(request, metric_type)
    if gsv_error:
        return gsv_error
    period_key, period_error = _normalize_period(request, period)
    if period_error:
        return period_error
    date_error = _require_ordered_dates(request, start_date, end_date)
    if date_error:
        return date_error
    compare_error = _require_ordered_dates(request, compare_start_date, compare_end_date)
    if compare_error:
        return compare_error
    if warning := check_future_date(start_date) or check_future_date(end_date):
        response.headers["X-Data-Warning"] = warning

    # Pass period through. Do not fold it into start/end (that forces month-start cutoff).
    facts = calculate_audience_summary(
        year=year,
        metric_type="GSV",
        start_date=start_date,
        end_date=end_date,
        channel=channel,
        period=period_key.upper() if period_key else None,
        exclude_channels=exclude_channels,
        compare_start_date=compare_start_date,
        compare_end_date=compare_end_date,
        order_ids=order_ids,
        product_ids=product_ids,
    )
    windows = _executed_windows(
        period_key, start_date, end_date, compare_start_date, compare_end_date,
    )
    record = _wrap_summary_result(
        owner=actor,
        facts=facts,
        windows=windows,
        product_ids=product_ids,
    )
    ref = record["result_ref"]
    page = ref.get("page")
    indicators = facts.get("indicators") or []
    if page:
        start = page["offset"]
        end = start + page["limit"]
        page_rows = indicators[start:end]
    else:
        page_rows = indicators
    return {
        "year_label": facts.get("year_label"),
        "comp_year_label": facts.get("comp_year_label"),
        "prev2_year_label": facts.get("prev2_year_label"),
        "metric_type": "GSV",
        "indicators": page_rows if page else indicators,
        "channel_all": facts.get("channel_all") or [],
        "channel_member": facts.get("channel_member") or [],
        "current_period": {
            "start": windows.get("start_date"),
            "end": windows.get("end_date"),
            "cutoff": windows.get("cutoff"),
        },
        "comparison_period": {
            "start": windows.get("comparison_start") or windows.get("compare_start_date"),
            "end": windows.get("comparison_end") or windows.get("compare_end_date"),
        },
        "executed_windows": windows,
        "result_ref": ref,
        "page": page,
        "integrity": {
            "row_count": ref.get("row_count"),
            "checksum": record["checksum"],
            "complete": None if page is None else page.get("complete"),
            "result_id": ref.get("result_id"),
        },
    }


@router.post("/summary")
def post_audience_summary_api(
    request: Request,
    response: Response,
    body: AudienceSummaryBindRequest,
):
    """人群看板汇总接口（POST 版，支持大量订单号列表）"""
    extras = dict(getattr(body, "__pydantic_extra__", None) or {})
    return _calculate_summary(
        request,
        response,
        body.year,
        body.metric_type,
        body.period,
        body.start_date,
        body.end_date,
        body.channel,
        body.exclude_channels,
        body.compare_start_date,
        body.compare_end_date,
        body.order_ids,
        body.product_ids,
        extra_fields=extras,
    )


@router.get("/capabilities")
def get_audience_capabilities(request: Request):
    """Live capability catalog for this bind layer. Official /analytics/catalog is unwired."""
    actor = _require_actor(request)
    if isinstance(actor, JSONResponse):
        return actor
    caps = overlay_live_capabilities(_actor_capabilities(actor))
    return {
        "schema_version": "competition-capabilities/v1",
        "actor_filtered": True,
        "backend_recheck": True,
        "http_mapping": "GET /api/v1/audience/capabilities",
        "official_catalog": "GET /api/v1/analytics/catalog (NOT_CONNECTED in main.py)",
        "capabilities": caps,
    }


@router.get("/results/{result_id}")
def get_audience_result(
    request: Request,
    result_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
):
    """Read a stored summary by result_id. Rechecks current owner; never returns others' facts."""
    actor = _require_actor(request)
    if isinstance(actor, JSONResponse):
        return actor
    with _RESULT_LOCK:
        record = _RESULT_STORE.get(result_id)
    if record is None or record["owner"] != actor:
        return _error(
            request,
            http_status=403,
            code="FORBIDDEN",
            message="当前身份无权读取该结果引用。",
            retryable=False,
            param="result_id",
            doc_ref=DOC_T06,
        )
    facts = record["facts"]
    indicators = list(facts.get("indicators") or [])
    total = len(indicators)
    if offset > total:
        return _error(
            request,
            http_status=422,
            code="INVALID_REQUEST",
            message="page offset exceeds total。",
            retryable=False,
            param="offset",
            doc_ref=DOC_T07,
        )
    page = _page_for(total, offset, limit, record["checksum"])
    sliced = indicators[offset:offset + page["limit"]]
    ref = dict(record["result_ref"])
    ref["page"] = page
    ref["row_count"] = total
    if total == 0:
        ref["completeness"] = "EMPTY"
    elif page["complete"]:
        ref["completeness"] = "COMPLETE"
    else:
        ref["completeness"] = "PARTIAL"
    return {
        "result_ref": ref,
        "indicators": sliced,
        "executed_windows": record["windows"],
        "integrity": {
            "row_count": total,
            "checksum": record["checksum"],
            "complete": page["complete"],
            "result_id": result_id,
        },
    }
