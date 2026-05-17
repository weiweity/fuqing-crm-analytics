"""
话术库 API 路由
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from typing import List, Optional
import tempfile
import os

from backend.services.script_library_service import (
    get_product_list,
    get_product_scripts,
    search_product_scripts,
    import_product_scripts,
    get_celebrity_list,
    get_celebrity_scripts,
    update_celebrity_scripts
)

router = APIRouter(prefix="/api/v1/scripts", tags=["话术库"])


# ==================== 产品话术 ====================

@router.get("/products")
def list_products():
    """获取产品话术列表"""
    return {
        "code": 0,
        "data": get_product_list()
    }


@router.get("/products/{product_name}")
def get_product(product_name: str):
    """获取指定产品的话术"""
    result = get_product_scripts(product_name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"产品 '{product_name}' 不存在")
    return {
        "code": 0,
        "data": result
    }


@router.get("/products/search")
def search_products(keyword: str = Query(..., description="搜索关键词")):
    """搜索产品话术"""
    results = search_product_scripts(keyword)
    return {
        "code": 0,
        "data": results,
        "total": len(results)
    }


@router.post("/products/import")
async def import_products(file: UploadFile = File(...)):
    """导入产品话术Excel"""
    # 验证文件类型
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 或 .xls 文件")

    # 保存临时文件
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # 执行导入
        result = import_product_scripts(tmp_path)
        return {
            "code": 0,
            "message": f"导入成功：新增 {result['imported']} 条，跳过 {result['skipped']} 条",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败：{str(e)}")
    finally:
        # 清理临时文件
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ==================== 明星专项 ====================

@router.get("/celebrities")
def list_celebrities():
    """获取明星列表"""
    return {
        "code": 0,
        "data": get_celebrity_list()
    }


@router.get("/celebrities/{celebrity_name}")
def get_celebrity(celebrity_name: str):
    """获取指定明星的话术"""
    result = get_celebrity_scripts(celebrity_name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"明星 '{celebrity_name}' 不存在")
    return {
        "code": 0,
        "data": result
    }


@router.put("/celebrities/{celebrity_name}/scripts")
def update_celebrity(celebrity_name: str, scripts: List[dict]):
    """更新明星话术"""
    success = update_celebrity_scripts(celebrity_name, scripts)
    if not success:
        raise HTTPException(status_code=404, detail=f"明星 '{celebrity_name}' 不存在")
    return {
        "code": 0,
        "message": "更新成功"
    }
