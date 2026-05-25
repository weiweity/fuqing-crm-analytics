"""
导出路由

前缀: /api/v1/export/*
"""

from fastapi import APIRouter

from backend.contracts.schemas import ExportPPTRequest, ExportPPTResponse, TemplatesResponse
from backend.services.export_service import generate_ppt_report, get_available_templates

router = APIRouter(prefix="/api/v1/export", tags=["导出"])


@router.post("/ppt", response_model=ExportPPTResponse)
def export_ppt_api(request: ExportPPTRequest):
    """
    生成 PPT 报告

    支持模块: cover, metrics, segments, geo, category, actions
    """
    result = generate_ppt_report(
        report_type=request.report_type,
        start_date=request.start_date,
        end_date=request.end_date,
        modules=request.modules,
        template=request.template,
    )
    return ExportPPTResponse(**result)


@router.get("/templates", response_model=TemplatesResponse)
def get_templates_api():
    """
    获取可用模板列表

    返回模板ID、名称、描述和支持的模块
    """
    return get_available_templates()
