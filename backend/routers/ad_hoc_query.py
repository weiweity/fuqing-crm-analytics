"""
backend.routers.ad_hoc_query — 即席查询 HTTP API 入口 (Sprint 188)

本文件职责（三层架构 - Sprint 54+ 永久规则 L4.5 配套）:
- L1 路由层: 9 个 POST endpoint, 把 HTTP request 映射到 scripts/ad_hoc_queries/*.py 的 run_xxx 函数
- 参数校验: Pydantic BaseModel (跟 Sprint 60+ B2 强类型配套, 422 拦截)
- 不重业务口径: 所有 SQL / 业务逻辑全走 scripts/ad_hoc_queries/*.py 已落地的 QuerySpec.run
- export-xlsx endpoint 返 StreamingResponse 二进制流

合规清单:
- L4.5 FilterBuilder: route 层不写 inline SQL, 复用 scripts/ad_hoc_queries/*.run_xxx 已走 semantic 层
- L4.19 channel alias: 透传 channel 参数到下游 service, 复用 service 内部 FilterBuilder o. alias
- L4.36 禁停 uvicorn: route 层不允许任何 duckdb.connect / close (跨进程 read_only, 跨 sprint Sprint 53 race flake 治本)
- L4.38 DuckDB flock: uvicorn 主进程 read_write + CLI/MCP 子进程 read_only 跨进程共存
- L4.41 subprocess PYTHONPATH 绝对路径: 本 router 不开子进程 (CLI 仍存在, 走 HTTP = uvicorn 主进程)
- Sprint 187 沉淀: 任何 subprocess 注入 env[PYTHONPATH] 必须 str(PROJECT_ROOT)

CLI / MCP server 仍存在 (scripts/ad_hoc_query.py + mcp_servers/fuqing_adhoc/server.py).
本 router 是平行入口, 不替换 CLI, 让 HTTP API 可被前端 / WorkBuddy / 任意 HTTP client 调用.

9 endpoint:
- POST /api/v1/ad-hoc/daily-gsv
- POST /api/v1/ad-hoc/yoy-battle
- POST /api/v1/ad-hoc/channel-slice
- POST /api/v1/ad-hoc/two-year-overview
- POST /api/v1/ad-hoc/new-old-customer
- POST /api/v1/ad-hoc/rfm-repurchase
- POST /api/v1/ad-hoc/top-n
- POST /api/v1/ad-hoc/dq-report
- POST /api/v1/ad-hoc/export-excel  (返 application/vnd.openxmlformats-officedocument.spreadsheetml.sheet 二进制)
"""
from __future__ import annotations

import io
import logging
from datetime import date
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ad-hoc", tags=["即席查询 (Sprint 188)"])


# ─────────────────────────────────────────────────────────────
# Pydantic request schemas (B2 强类型, 422 拦截, L4.19 channel alias 配套)
# ─────────────────────────────────────────────────────────────

class _DateWindowMixin(BaseModel):
    """所有需要日期窗口的 endpoint 共用 (start/end)."""
    start_date: str = Field(..., description="起始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")


class DailyGsvRequest(_DateWindowMixin):
    """daily-gsv: 日序列 GSV + customers + YOY%."""
    pass


class YoyBattleRequest(_DateWindowMixin):
    """yoy-battle: baseline vs current 双窗口 YOY 战斗."""
    baseline_start: str = Field(..., description="基期起始日期 YYYY-MM-DD")
    baseline_end: str = Field(..., description="基期结束日期 YYYY-MM-DD")
    current_start: str = Field(..., description="当期起始日期 YYYY-MM-DD")
    current_end: str = Field(..., description="当期结束日期 YYYY-MM-DD")
    metric: str = Field(
        default="all",
        description="输出指标: gsv|orders|customers|aov|all",
    )


class ChannelSliceRequest(BaseModel):
    """channel-slice: 按 channel 切片日维度."""
    date: str = Field(..., description="目标日期 YYYY-MM-DD")
    channel: str = Field(default="all", description="渠道筛选: all|online|offline|单渠道")
    store_id: Optional[str] = Field(default=None, description="店铺 ID 过滤 (可选)")
    compare: str = Field(default="none", description="对比口径: yoy|pop|none")


class TwoYearOverviewRequest(BaseModel):
    """two-year-overview: 两年新老客 30 指标对比 (AudienceSummaryResponse)."""
    year: int = Field(default=2026, description="基准年份")
    period: Optional[str] = Field(default=None, description="WTD/MTD/YTD/Q1-Q4 (period 空时用 start/end)")
    start: Optional[str] = Field(default=None, description="开始日期 YYYY-MM-DD")
    end: Optional[str] = Field(default=None, description="结束日期 YYYY-MM-DD")
    channel: Optional[str] = Field(default=None, description="渠道筛选")
    exclude_channels: Optional[str] = Field(default=None, description="排除渠道, 逗号分隔")


class NewOldCustomerRequest(_DateWindowMixin):
    """new-old-customer: 新老客拆分对比, 字段前缀隔离."""
    exclude_channels: Optional[str] = Field(default=None, description="排除渠道, 逗号分隔")
    dimension: str = Field(default="channel", description="维度: channel|category")


class RfmRepurchaseRequest(_DateWindowMixin):
    """rfm-repurchase: R 区间复购周期分布, 复用 get_rfm_r_flow."""
    channel: Optional[str] = Field(default=None, description="渠道筛选")
    exclude_channels: Optional[str] = Field(default=None, description="排除渠道, 逗号分隔")
    year: int = Field(default=2026, description="基准年份")


class TopNRequest(_DateWindowMixin):
    """top-n: TOP N 品类/产品层级两年对比."""
    dimension: str = Field(
        default="spu_category",
        description="TOP 维度: spu_category|spu_product_subclass|spu_product_class",
    )
    exclude_channels: Optional[str] = Field(default=None, description="排除渠道, 逗号分隔")
    limit: int = Field(default=20, description="返回行数")


class DqReportRequest(_DateWindowMixin):
    """dq-report: 数据质量 5/15 项规则报告."""
    full: bool = Field(default=False, description="输出完整 15 项 (默认仅 5 项)")
    force: bool = Field(default=False, description="预留: ERROR 时继续")
    exclude_channels: Optional[str] = Field(default=None, description="排除渠道, 逗号分隔")


class ExportExcelRequest(_DateWindowMixin):
    """export-excel: 导出 11 sheet Excel 整份报告 (返二进制流)."""
    exclude_channels: Optional[str] = Field(default=None, description="排除渠道, 逗号分隔")
    year: int = Field(default=2026, description="基准年份")


class DailyGsvMultiPeriodRequest(BaseModel):
    """daily-gsv-multi-period: 多周期 × 8 维度 daily rows.

    Sprint 190 加: 运营高频需求"按天 × 8 维度 × 多周期对比" — 必用 daily-gsv-multi-period.

    8 metric enum (跟 scripts.ad_hoc_queries.daily_gsv_multi_period._METRIC_SQL 对齐):
      - sample_gmv / sample_gsv (小样 GMV/GSV, 渠道 U先派样 + 百补派样)
      - member_gmv / member_gsv (会员 GMV/GSV, is_member=TRUE)
      - new_users / new_gsv (新客人数 / 新客 GSV, cutoff = 查询起始日 - 1 天)
      - old_users / old_gsv (老客人数 / 老客 GSV)

    periods 必须是 start/end 成对 [YYYY-MM-DD, YYYY-MM-DD, ...], 偶数长度.

    L4.5 / L4.19: 无 inline SQL, 复用 service. L4.25 防串台字段前缀 (跟 Sprint 171 v2.0 一致).
    """

    periods: List[str] = Field(
        ...,
        min_length=2,
        max_length=20,
        description="多周期列表, start/end 成对. 偶数长度. 例 ['2026-01-01','2026-06-30','2025-01-01','2025-06-30']",
    )
    metrics: List[str] = Field(
        default_factory=lambda: [
            "sample_gmv", "sample_gsv", "member_gmv", "member_gsv",
            "new_users", "new_gsv", "old_users", "old_gsv",
        ],
        description="8 metric (默认全 8). 传空列表用默认.",
    )


# ─────────────────────────────────────────────────────────────
# Response helpers (rows 序列化 + headers from QuerySpec)
# ─────────────────────────────────────────────────────────────

class AdHocQueryResponse(BaseModel):
    """通用 JSON 响应: {headers, rows} 跟 CSV 输出列对齐."""
    command: str = Field(..., description="子命令名")
    headers: List[str] = Field(..., description="列名 (跟 CSV headers 一致)")
    rows: List[List[Any]] = Field(..., description="数据行 (跟 headers 对齐)")
    row_count: int = Field(..., description="行数")
    # 跟 L4.5 / Sprint 60+ '未来日期告警' 中间件对齐
    warning: Optional[str] = Field(default=None, description="数据告警 (如未来日期)")


def _validate_date_range(start: str, end: str) -> None:
    """复用 CLI 校验: parse + range 检查, 校验失败 422."""
    try:
        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"日期格式错: {exc}")
    if s > e:
        raise HTTPException(status_code=422, detail=f"start_date({start}) > end_date({end})")


def _future_date_warn(*dates: str) -> Optional[str]:
    """复用 backend.main:_future_date_warning_for_request 同语义 (中间件版在 query params, 这里是 body 字段).

    返回 warning str 给前端 banner (Sprint 60+ '未来日期全 0' 误导治理)."""
    today = date.today()
    for d in dates:
        if not d:
            continue
        try:
            parsed = date.fromisoformat(d)
        except ValueError:
            continue
        if parsed > today:
            return f"date {d} is in the future, data will be all-zero. Use a date <= today."
    return None


def _serialize(command: str, headers: List[str], rows: List[List[Any]], warning: Optional[str] = None) -> AdHocQueryResponse:
    """把 CLI 的 rows = list[list] 包成 {headers, rows} JSON."""
    return AdHocQueryResponse(
        command=command,
        headers=headers,
        rows=rows,
        row_count=len(rows),
        warning=warning,
    )


# ─────────────────────────────────────────────────────────────
# 9 endpoint
# ─────────────────────────────────────────────────────────────

@router.post("/daily-gsv", response_model=AdHocQueryResponse, summary="日序列 GSV + customers + YOY%")
def post_daily_gsv(req: DailyGsvRequest) -> AdHocQueryResponse:
    """日维度 GSV + 客户数 + 同比百分比 (复用 scripts.ad_hoc_queries.daily_gsv.run_daily_gsv)."""
    _validate_date_range(req.start_date, req.end_date)
    # 延迟 import 避免 router 顶层拉起 scripts (跟 L4.41 spark PROJECT_ROOT 配套)
    from scripts.ad_hoc_queries.daily_gsv import run_daily_gsv  # noqa: WPS433
    headers = ["date", "gsv", "customers", "yoy_pct"]
    warning = _future_date_warn(req.start_date, req.end_date)
    try:
        rows = run_daily_gsv(start=req.start_date, end=req.end_date)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _serialize("daily-gsv", headers, rows, warning)


@router.post(
    "/daily-gsv-multi-period",
    response_model=AdHocQueryResponse,
    summary="多周期 × 8 维度 daily rows (Sprint 190 加, 运营高频需求)",
)
def post_daily_gsv_multi_period(req: DailyGsvMultiPeriodRequest) -> AdHocQueryResponse:
    """多周期 × 8 维度 daily rows. Sprint 190 加 (跟 Sprint 188 B1 endpoint pattern stable).

    周期列表 start/end 成对. 输出列: [period_label, date, sample_gmv, sample_gsv,
    member_gmv, member_gsv, new_users, new_gsv, old_users, old_gsv].
    """
    if len(req.periods) % 2 != 0:
        raise HTTPException(
            status_code=422,
            detail=f"periods 必须是 start/end 成对 (偶数长度), 当前 {len(req.periods)}",
        )
    # 校验每个 period date
    for d in req.periods:
        try:
            date.fromisoformat(d)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"date 格式错: {d}: {exc}")
    periods_tuple = list(zip(req.periods[::2], req.periods[1::2]))
    from scripts.ad_hoc_queries.daily_gsv_multi_period import (  # noqa: WPS433
        run_daily_gsv_multi_period,
    )
    headers = ["period", "date"] + (req.metrics or [
        "sample_gmv", "sample_gsv", "member_gmv", "member_gsv",
        "new_users", "new_gsv", "old_users", "old_gsv",
    ])
    # 周期日期全部 future 警告
    warning = _future_date_warn(*req.periods)
    try:
        rows = run_daily_gsv_multi_period(
            periods=periods_tuple,
            metrics=req.metrics or None,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _serialize("daily-gsv-multi-period", headers, rows, warning)


@router.post("/yoy-battle", response_model=AdHocQueryResponse, summary="baseline vs current 双窗口 YOY 战斗")
def post_yoy_battle(req: YoyBattleRequest) -> AdHocQueryResponse:
    """双窗口 YOY 战斗 (baseline_start/end → current_start/end)."""
    _validate_date_range(req.baseline_start, req.baseline_end)
    _validate_date_range(req.current_start, req.current_end)
    from scripts.ad_hoc_queries.yoy_battle import run_yoy_battle  # noqa: WPS433
    headers = ["metric", "baseline_value", "current_value", "abs_diff", "yoy_pct"]
    warning = _future_date_warn(req.baseline_start, req.baseline_end, req.current_start, req.current_end)
    try:
        rows = run_yoy_battle(
            baseline_start=req.baseline_start,
            baseline_end=req.baseline_end,
            current_start=req.current_start,
            current_end=req.current_end,
            metric=req.metric,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _serialize("yoy-battle", headers, rows, warning)


@router.post("/channel-slice", response_model=AdHocQueryResponse, summary="按 channel 切片日维度")
def post_channel_slice(req: ChannelSliceRequest) -> AdHocQueryResponse:
    """按 channel 切片日维度, 全店排第一 (L4.19 channel alias 配套)."""
    from scripts.ad_hoc_queries.channel_slice import run_channel_slice  # noqa: WPS433
    headers = ["channel", "gsv", "orders", "customers", "aov", "yoy_pct"]
    warning = _future_date_warn(req.date)
    try:
        rows = run_channel_slice(
            date=req.date,
            channel=req.channel,
            store_id=req.store_id,
            compare=req.compare,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _serialize("channel-slice", headers, rows, warning)


@router.post("/two-year-overview", response_model=AdHocQueryResponse, summary="两年新老客 30 指标对比")
def post_two_year_overview(req: TwoYearOverviewRequest) -> AdHocQueryResponse:
    """复用 scripts.ad_hoc_queries.two_year_overview (走 backend.services.metrics.audience_summary)."""
    from scripts.ad_hoc_queries.two_year_overview import (  # noqa: WPS433
        TWO_YEAR_HEADERS,
        run_two_year_overview,
    )
    warning = _future_date_warn(req.start, req.end)
    try:
        rows = run_two_year_overview(
            year=req.year,
            period=req.period,
            start=req.start,
            end=req.end,
            channel=req.channel,
            exclude_channels=req.exclude_channels,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _serialize("two-year-overview", TWO_YEAR_HEADERS, rows, warning)


@router.post("/new-old-customer", response_model=AdHocQueryResponse, summary="新老客拆分对比, 字段前缀隔离")
def post_new_old_customer(req: NewOldCustomerRequest) -> AdHocQueryResponse:
    """字段前缀隔离 (new_*/old_*/member_*/all_* + r_seg_* + channel_*), 跟 Sprint 171 L4.25 防串台字段配套."""
    _validate_date_range(req.start_date, req.end_date)
    from scripts.ad_hoc_queries.new_old_customer import (  # noqa: WPS433
        NEW_OLD_HEADERS,
        run_new_old_customer,
    )
    warning = _future_date_warn(req.start_date, req.end_date)
    try:
        rows = run_new_old_customer(
            start=req.start_date,
            end=req.end_date,
            exclude_channels=req.exclude_channels,
            dimension=req.dimension,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _serialize("new-old-customer", NEW_OLD_HEADERS, rows, warning)


@router.post("/rfm-repurchase", response_model=AdHocQueryResponse, summary="R 区间复购周期分布")
def post_rfm_repurchase(req: RfmRepurchaseRequest) -> AdHocQueryResponse:
    """R 区间复购周期分布, 复用 backend.services.rfm.get_rfm_r_flow."""
    _validate_date_range(req.start_date, req.end_date)
    from scripts.ad_hoc_queries.rfm_repurchase import (  # noqa: WPS433
        RFM_HEADERS,
        run_rfm_repurchase,
    )
    warning = _future_date_warn(req.start_date, req.end_date)
    try:
        rows = run_rfm_repurchase(
            start=req.start_date,
            end=req.end_date,
            channel=req.channel,
            exclude_channels=req.exclude_channels,
            year=req.year,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _serialize("rfm-repurchase", RFM_HEADERS, rows, warning)


@router.post("/top-n", response_model=AdHocQueryResponse, summary="TOP N 品类/产品层级两年对比")
def post_top_n(req: TopNRequest) -> AdHocQueryResponse:
    """TOP N 品类/产品层级两年对比."""
    _validate_date_range(req.start_date, req.end_date)
    from scripts.ad_hoc_queries.top_n import TOP_N_HEADERS, run_top_n  # noqa: WPS433
    warning = _future_date_warn(req.start_date, req.end_date)
    try:
        rows = run_top_n(
            dimension=req.dimension,
            start=req.start_date,
            end=req.end_date,
            exclude_channels=req.exclude_channels,
            limit=req.limit,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _serialize("top-n", TOP_N_HEADERS, rows, warning)


@router.post("/dq-report", response_model=AdHocQueryResponse, summary="数据质量 5/15 项规则报告")
def post_dq_report(req: DqReportRequest) -> AdHocQueryResponse:
    """数据质量 5 (默认) / 15 (full=true) 项规则报告, 跟 backend.services.metrics.dq_report 配套."""
    _validate_date_range(req.start_date, req.end_date)
    from scripts.ad_hoc_queries.dq_report import DQ_HEADERS, run_dq_report  # noqa: WPS433
    warning = _future_date_warn(req.start_date, req.end_date)
    try:
        rows = run_dq_report(
            start=req.start_date,
            end=req.end_date,
            full=req.full,
            force=req.force,
            exclude_channels=req.exclude_channels,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _serialize("dq-report", DQ_HEADERS, rows, warning)


@router.post("/export-excel", summary="导出 11 sheet Excel 整份报告 (返回 application/vnd.openxmlformats-officedocument.spreadsheetml.sheet 二进制流)")
def post_export_excel(req: ExportExcelRequest) -> StreamingResponse:
    """导出 11 sheet Excel 整份报告 (返 StreamingResponse 二进制流, 跟 export-xlsx endpoint 一致)."""
    _validate_date_range(req.start_date, req.end_date)
    from scripts.ad_hoc_queries.export_excel import write_export_excel  # noqa: WPS433
    try:
        # write_export_excel 返 xlsx 落盘 path, 我们 read binary → StreamingResponse
        # 不传 output_path 走 save_workbook 内部默认路径 (双层目录规则)
        xlsx_path = write_export_excel(
            start=req.start_date,
            end=req.end_date,
            exclude_channels=req.exclude_channels,
            year=req.year,
            output_path=None,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    xlsx_file = Path(xlsx_path)
    if not xlsx_file.exists():
        raise HTTPException(status_code=500, detail=f"Excel 文件未生成: {xlsx_path}")
    binary = xlsx_file.read_bytes()
    return StreamingResponse(
        io.BytesIO(binary),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="ad-hoc-export-{req.start_date}_to_{req.end_date}.xlsx"',
            "X-Xlsx-Path": xlsx_path,
            "X-Data-Warning": _future_date_warn(req.start_date, req.end_date) or "",
        },
    )
