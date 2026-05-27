"""指标服务 - 共享工具"""
from typing import Optional, List
from backend.db.connection import get_connection
from backend.semantic.channels import UI_TO_DB

def _get_conn():
    """连接上下文管理器（确保连接始终关闭）"""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()





def _expand_channel(ch: Optional[str]) -> List[str]:
    """将UI渠道名展开为实际DB渠道名列表（支持组合渠道如'纯派样'）"""
    if not ch or ch == "全店":
        return []
    if ch == "纯派样":
        return ["U先派样", "百补派样"]
    return [UI_TO_DB.get(ch, ch)]
