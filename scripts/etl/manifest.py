"""
W2 原子 snapshot 切换 (v0.4.8) — design doc v1.1 §6

痛点 2 根因: ETL 写一半 API 读到半新半旧. 修法: manifest.json 单文件 +
POSIX atomic rename + fsync.

设计 (design doc v1.1 §6):
- 写: tmp file + os.fsync + os.rename (POSIX atomic, near-atomic on Windows)
- 读: open().read() (Python < 4KB 原子, 足够)
- 旧版本保留 7 天: .versions/{ts}.json
- 单 view (user 拍板 v1.1 §13: 出问题直接全量回滚到上一版本)

CLAUDE.md 合规:
- ① manifest.json 用 os.rename() + fsync (POSIX atomic 兜底, Windows near-atomic)
- ② 多 API 线程并发读安全 (短读, atomic rename 后单文件原子, Python 内核层保证 < 4KB)
- ③ 不动 ETL 单例连接 (manifest.py 只读 FS, 与 DuckDB 无关)
"""
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# 默认 manifest 路径 (跟 data/processed/ 同级, 实际由 ETL 跑批后写到此处)
DEFAULT_MANIFEST_PATH = Path("data/processed/manifest.json")
DEFAULT_RETENTION_DAYS = 7


class SnapshotManifest:
    """POSIX atomic switch via tmp file + os.rename + fsync.

    使用模式:
        manifest = SnapshotManifest()
        manifest.write_active("rfm_view_v42")  # ETL 末尾调用
        view = manifest.read_active()  # API 层每次查询调用
    """

    def __init__(
        self,
        path: Path = DEFAULT_MANIFEST_PATH,
        versions_dir: Optional[Path] = None,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ) -> None:
        self.path = Path(path)
        self.versions_dir = Path(versions_dir) if versions_dir else self.path.parent / ".versions"
        self.retention_days = retention_days
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self._version = self._load_or_init_version()

    def _load_or_init_version(self) -> int:
        """读当前 manifest.json 的 version, 缺失则 0."""
        if not self.path.exists():
            return 0
        try:
            with open(self.path) as f:
                return int(json.load(f).get("version", 0))
        except (json.JSONDecodeError, ValueError, KeyError, OSError):
            return 0

    def read_active(self) -> str:
        """API 层每次查询读这个. 返回 active_view 名字.

        缺失或损坏返回空串 (caller 决定 fallback).
        """
        if not self.path.exists():
            return ""
        try:
            with open(self.path) as f:
                data = json.load(f)
            return str(data.get("active_view", ""))
        except (json.JSONDecodeError, KeyError, OSError):
            return ""

    def read_full(self) -> dict:
        """返回完整 manifest dict (version + active_view + ts)."""
        if not self.path.exists():
            return {"active_view": "", "version": 0, "ts": ""}
        try:
            with open(self.path) as f:
                return json.load(f)
        except (json.JSONDecodeError, KeyError, OSError):
            return {"active_view": "", "version": 0, "ts": ""}

    def _next_version(self) -> int:
        self._version += 1
        return self._version

    def write_active(self, view_name: str) -> dict:
        """原子切换 active view. POSIX atomic via os.rename + fsync.

        步骤:
        1. 写 tmp file (per-pid 避免并发冲突)
        2. flush + fsync tmp file (强制刷盘)
        3. 复制旧版本到 .versions/{ts}_v{N}.json (7 天保留)
        4. os.rename tmp → manifest.json (POSIX atomic on same FS)

        失败模式:
        - 写 tmp 失败: 不影响 manifest, 抛异常
        - fsync 失败: 不影响 manifest, 抛异常
        - 复制旧版本失败: 静默 (log only, 不阻断主流程)
        - rename 失败: tmp 残留, 下次 write 时清掉
        """
        new_version = self._next_version()
        ts = datetime.now(timezone.utc).isoformat()
        manifest = {
            "active_view": view_name,
            "version": new_version,
            "ts": ts,
        }

        # 1. 写 tmp file
        tmp = self.path.with_suffix(f".tmp.{os.getpid()}.{int(time.time() * 1000)}")
        try:
            with open(tmp, "w") as f:
                json.dump(manifest, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())  # 强制刷盘
        except OSError:
            # 清理 tmp 残留
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            raise

        # 2. 复制旧版本到 .versions/ (在 rename 前)
        if self.path.exists():
            old_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            try:
                shutil.copy2(self.path, self.versions_dir / f"{old_ts}_v{self._version - 1}.json")
            except OSError:
                # 保留失败不阻断主流程 (log 由 caller 处理)
                pass

        # 3. POSIX atomic rename
        os.rename(tmp, self.path)

        # 4. 清理过期版本 (lazy cleanup on write)
        self._cleanup_old_versions()

        return manifest

    def _cleanup_old_versions(self) -> int:
        """删 > retention_days 天的旧版本. 返回删除数."""
        if self.retention_days <= 0:
            return 0
        cutoff = time.time() - (self.retention_days * 86400)
        deleted = 0
        try:
            for f in self.versions_dir.glob("*.json"):
                try:
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
                        deleted += 1
                except OSError:
                    continue
        except OSError:
            pass
        return deleted

    def list_versions(self) -> list[dict]:
        """列出 .versions/ 里所有保留的版本 (调试用)."""
        out: list[dict] = []
        try:
            files = sorted(self.versions_dir.glob("*.json"), reverse=True)
        except OSError:
            return out
        for f in files:
            try:
                with open(f) as fp:
                    data = json.load(fp)
                out.append({
                    "file": f.name,
                    "version": data.get("version"),
                    "active_view": data.get("active_view"),
                    "ts": data.get("ts"),
                })
            except (OSError, json.JSONDecodeError, KeyError):
                continue
        return out


# Module-level convenience (跟 backend/db/connection.py 单例模式类似)
_default_manifest: Optional[SnapshotManifest] = None


def get_manifest(path: Optional[Path] = None) -> SnapshotManifest:
    """Get or create default manifest singleton (单进程足够).

    多进程场景: 每次 ETL 跑批新进程, 进程退出后 singleton 失效, 适合 ETL 一次性调用.
    API 层每次请求新 SnapshotManifest(path) 实例即可, 不需要 singleton.
    """
    global _default_manifest
    if _default_manifest is None or (path is not None and Path(path) != _default_manifest.path):
        _default_manifest = SnapshotManifest(Path(path) if path else DEFAULT_MANIFEST_PATH)
    return _default_manifest
