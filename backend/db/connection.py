"""数据库连接管理"""
import os
from backend.config import DUCKDB_PATH


def get_connection():
    """获取 DuckDB 连接（P3: 支持可选密码认证）"""
    import duckdb
    db_password = os.environ.get("DUCKDB_PASSWORD")
    if db_password:
        return duckdb.connect(str(DUCKDB_PATH), config={"password": db_password})
    return duckdb.connect(str(DUCKDB_PATH))
