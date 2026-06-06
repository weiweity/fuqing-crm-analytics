"""
W2 API 层 manifest loader (v0.4.8) — design doc v1.1 §6

API 层集成: 每次查询读 manifest 拿 active view name, 然后 SELECT FROM {{ view }}.
替代硬编码 view 名 (修痛点 2: ETL 写到一半 API 读到半新半旧).

CLAUDE.md 合规:
- ① 走语义层 (manifest 是 view 名引用, 不影响 semantic 口径)
- ② 后端单例连接 (每次新 SnapshotManifest 实例, 不动 connection.py)
- ③ 接口只读 (不 conn.close(), 不动 DuckDB)
"""
from pathlib import Path
from typing import Optional

from scripts.etl.manifest import SnapshotManifest, DEFAULT_MANIFEST_PATH


# API 层每次查询创建新实例 (避免 stale 缓存, 多进程/多线程安全)
# 性能: open+read+close < 1ms, 4KB JSON 远小于 POSIX 单次 read
def get_rfm_view_name(manifest_path: Optional[Path] = None) -> str:
    """API 层入口. 返回 active view 名. 缺失/损坏返回空串.

    用法:
        view = get_rfm_view_name()
        if not view:
            return {"error": "manifest not initialized, ETL not run yet"}
        result = conn.execute(f"SELECT * FROM {view} WHERE ...")
    """
    path = Path(manifest_path) if manifest_path else DEFAULT_MANIFEST_PATH
    return SnapshotManifest(path).read_active()


def get_rfm_manifest_info(manifest_path: Optional[Path] = None) -> dict:
    """API 层入口 (调试 + /api/v1/rfm/version endpoint). 返回完整 manifest dict.

    返回: {"active_view": str, "version": int, "ts": str, "path": str}
    """
    path = Path(manifest_path) if manifest_path else DEFAULT_MANIFEST_PATH
    info = SnapshotManifest(path).read_full()
    info["path"] = str(path)
    return info
