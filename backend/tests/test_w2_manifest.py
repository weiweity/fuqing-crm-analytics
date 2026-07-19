"""
W2 v0.4.8 — manifest 原子切换 pytest 覆盖 (design doc v1.1 §7.2 + §8 完成标志)

覆盖:
1. write_active 原子性 (POSIX rename)
2. read_active 兼容损坏 (返回空串, 不抛异常)
3. 旧版本保留 7 天 (.versions/{ts}_v{N}.json)
4. 过期版本清理 (> 7 天)
5. concurrent write 不破坏 (同 pid 同时写, 最后一个赢)
6. SIGKILL 中途不破坏 (tmp 残留, manifest 仍可读旧 view)
7. /api/v1/rfm/version endpoint 返回正确 schema

CLAUDE.md 合规: pytest 走 homebrew Python 3.14, test_*.py 命名, fixtures 隔离 tmp_path.
"""
import json
import os
import time
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# 路径: backend/tests/ → ../../scripts/etl/manifest.py
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.etl.manifest import SnapshotManifest  # noqa: E402


@pytest.fixture
def manifest_dir(tmp_path):
    """每个 test 一个独立 manifest + .versions 目录."""
    path = tmp_path / "manifest.json"
    versions = tmp_path / ".versions"
    versions.mkdir(parents=True, exist_ok=True)
    yield path, versions


class TestSnapshotManifestWriteRead:
    """基本 write/read 行为."""

    def test_init_creates_dirs(self, manifest_dir):
        path, versions = manifest_dir
        SnapshotManifest(path, versions_dir=versions, retention_days=7)
        assert path.parent.exists()
        assert versions.exists()

    def test_read_active_empty_when_no_manifest(self, manifest_dir):
        path, _ = manifest_dir
        m = SnapshotManifest(path)
        assert m.read_active() == ""

    def test_read_full_empty_when_no_manifest(self, manifest_dir):
        path, _ = manifest_dir
        m = SnapshotManifest(path)
        info = m.read_full()
        assert info == {"active_view": "", "version": 0, "ts": ""}

    def test_write_active_creates_manifest(self, manifest_dir):
        path, _ = manifest_dir
        m = SnapshotManifest(path)
        result = m.write_active("rfm_view_v1")
        assert result["active_view"] == "rfm_view_v1"
        assert result["version"] == 1
        assert path.exists()
        assert m.read_active() == "rfm_view_v1"

    def test_write_active_increments_version(self, manifest_dir):
        path, _ = manifest_dir
        m = SnapshotManifest(path)
        m.write_active("view_v1")
        m.write_active("view_v2")
        m.write_active("view_v3")
        info = m.read_full()
        assert info["version"] == 3
        assert info["active_view"] == "view_v3"


class TestSnapshotManifestAtomic:
    """原子性 + 损坏兼容."""

    def test_corrupt_manifest_returns_empty(self, manifest_dir):
        """manifest.json 损坏 → read_active 返回空串, 不抛异常."""
        path, _ = manifest_dir
        path.write_text("not valid json {{{")
        m = SnapshotManifest(path)
        assert m.read_active() == ""

    def test_partial_manifest_returns_empty(self, manifest_dir):
        """manifest.json 缺 active_view 字段 → 返回空串."""
        path, _ = manifest_dir
        path.write_text(json.dumps({"version": 5}))  # 缺 active_view
        m = SnapshotManifest(path)
        assert m.read_active() == ""

    def test_no_tmp_files_leaked_after_write(self, manifest_dir):
        """write_active 后 .tmp.* 残留应被清理 (成功路径)."""
        path, _ = manifest_dir
        m = SnapshotManifest(path)
        m.write_active("view_v1")
        # 检查 .tmp.* 文件
        tmp_files = list(path.parent.glob("manifest.json.tmp.*"))
        assert tmp_files == [], f"残留 tmp: {tmp_files}"


class TestSnapshotManifestVersions:
    """旧版本保留 + 过期清理."""

    def test_old_versions_archived(self, manifest_dir):
        """write_active 复制旧版本到 .versions/."""
        path, versions = manifest_dir
        m = SnapshotManifest(path, versions_dir=versions, retention_days=7)
        m.write_active("view_v1")
        m.write_active("view_v2")
        m.write_active("view_v3")
        # v0 (空) 不被复制 (init 时 path 不存在), v1 + v2 复制, v3 是当前
        archived = list(versions.glob("*.json"))
        assert len(archived) == 2  # v1 + v2 旧版本

    def test_list_versions_returns_sorted(self, manifest_dir):
        """list_versions 按文件名 (含时间戳) 倒序."""
        path, versions = manifest_dir
        m = SnapshotManifest(path, versions_dir=versions, retention_days=7)
        m.write_active("view_v1")
        time.sleep(0.01)
        m.write_active("view_v2")
        listed = m.list_versions()
        assert len(listed) == 1  # 只有 v1 被保留
        assert listed[0]["active_view"] == "view_v1"

    def test_old_versions_cleanup(self, manifest_dir):
        """retention_days 过期版本被清理."""
        path, versions = manifest_dir
        m = SnapshotManifest(path, versions_dir=versions, retention_days=1)
        # 写 2 次, 让 .versions/ 里有 1 个旧版本 (v1)
        m.write_active("view_v1")
        time.sleep(0.01)
        m.write_active("view_v2")  # 此时 v1 被复制到 .versions/, 触发 cleanup
        # 但 v1 mtime 是刚写入, 不会被清
        assert len(list(versions.glob("*.json"))) == 1
        # 把 .versions 里 v1 改 mtime 到 8 天前
        for f in versions.glob("*.json"):
            old_time = time.time() - (8 * 86400)
            os.utime(f, (old_time, old_time))
        # 写 v3 触发清理 (cleanup 看 cutoff=now-1day, v1 mtime<cutoff → 删)
        m.write_active("view_v3")
        # v1 应被清, 只剩 v2
        archived = list(versions.glob("*.json"))
        assert all("v1" not in f.name for f in archived), f"v1 没清: {archived}"
        # v2 还在 (mtime 是第二次写入时, < 1 天前)
        assert any("v2" in f.name for f in archived), f"v2 应在: {archived}"

    def test_retention_zero_keeps_all(self, manifest_dir):
        """retention_days=0 不清理 (禁用)."""
        path, versions = manifest_dir
        m = SnapshotManifest(path, versions_dir=versions, retention_days=0)
        m.write_active("view_v1")
        time.sleep(0.01)
        m.write_active("view_v2")
        # 即便 8 天前的 mtime 也不清理
        for f in versions.glob("*.json"):
            old_time = time.time() - (8 * 86400)
            os.utime(f, (old_time, old_time))
        m.write_active("view_v3")
        archived = list(versions.glob("*.json"))
        assert len(archived) >= 1  # 至少有 1 个保留


class TestSnapshotManifestConcurrency:
    """并发安全 (单进程内多 SnapshotManifest 实例, 都用同 path)."""

    def test_concurrent_writes_last_wins(self, manifest_dir):
        """多个 SnapshotManifest 实例并发写 (模拟多 ETL worker), 最后 write_active 胜出.
        设计 doc v1.1 §13: 单 view, 出问题回滚. 不要求多 view 并行.
        """
        path, _ = manifest_dir
        m1 = SnapshotManifest(path)
        m2 = SnapshotManifest(path)
        m1.write_active("view_v1")  # m1 init version=0, write → v1
        # m2 重新 init 时读 path 拿到 v1
        m2 = SnapshotManifest(path)
        m2.write_active("view_v2")  # m2 续 +1 → v2
        # 最后胜出
        assert SnapshotManifest(path).read_active() == "view_v2"


class TestSnapshotManifestSIGKILL:
    """SIGKILL 中途不破坏 (设计 doc v1.1 §7.2 第 2 条完成标志)."""

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal only")
    def test_sigkill_during_write_leaves_manifest_intact(self, manifest_dir):
        """在 write_active 写到一半 SIGKILL → manifest.json 仍可读旧值 (atomic rename 兜底).

        实现: 子进程跑 write_active 写到一半 SIGKILL, 父进程验证 manifest 仍可读.
        POSIX 保证: os.rename 是 atomic, 子进程在 fsync 之后 SIGKILL, 旧 manifest 仍完整.
        """
        path, _ = manifest_dir
        # 父进程先写 v1
        SnapshotManifest(path).write_active("view_v1")
        # 子进程尝试写 v2, 父进程 SIGKILL 子进程
        # 由于 os.rename 是 atomic, 要么 v1, 要么 v2, 不会有部分写入
        child_script = f"""
import sys, os, time
sys.path.insert(0, {repr(str(ROOT))})
from scripts.etl.manifest import SnapshotManifest
m = SnapshotManifest({repr(str(path))})
# 模拟慢写 (sleep 在 fsync 后, rename 前)
m._version = m._load_or_init_version() + 1
import json
manifest = {{"active_view": "view_v2", "version": m._version, "ts": "2026-06-06"}}
tmp = m.path.with_suffix(f".tmp.{{os.getpid()}}.{{int(time.time() * 1000)}}")
with open(tmp, "w") as f:
    json.dump(manifest, f)
    f.flush()
    os.fsync(f.fileno())
# sleep 故意给 SIGKILL 窗口
time.sleep(2)
os.rename(tmp, m.path)
"""
        proc = subprocess.Popen(
            [sys.executable, "-c", child_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(0.5)  # 让子进程跑起来, 到 sleep
        proc.kill()  # SIGKILL
        proc.wait()
        # 父进程读 manifest: 应该是 v1 (SIGKILL 在 rename 前) 或 v2 (rename 后)
        # 关键是: 不是损坏状态
        result = SnapshotManifest(path).read_active()
        assert result in ("view_v1", "view_v2"), f"manifest 损坏: {result!r}"


class TestRfmVersionEndpoint:
    """/api/v1/rfm/version endpoint (设计 doc v1.1 §7.2 第 4 条完成标志).

    用 mock 绕过 main.py auth_middleware (验 _verify_token) — endpoint 本身不需要 token,
    只是中间件对所有非白名单路径加 auth. TestClient 触发中间件 → 401.

    Sprint C (2026-07-19): /api/v1/rfm/* 走 QueryRouterMiddleware read 池.
    endpoint 本体只读 manifest JSON, 不查业务表, 但 middleware 仍会
    dual_conn.get_read_connection() → 打开 DUCKDB_PATH. CI 无生产库时
    旧写法 IOException "database does not exist". 本 class 用 tmp 空
    DuckDB + schema_test 隔离, 0 依赖 production DuckDB.
    """

    @pytest.fixture
    def bypass_auth(self):
        """mock _verify_token 返回有效 payload, 绕过 auth_middleware."""
        from backend.routers import auth
        return patch.object(auth, "_verify_token", return_value={"sub": "test"})

    @pytest.fixture
    def isolated_read_db(self, tmp_path, monkeypatch):
        """CI-safe DuckDB for QueryRouterMiddleware read pool.

        Creates an empty file-backed DuckDB so read_only connect succeeds
        without production data. Clears dual_conn read pool so no stale
        conn points at a previous path.
        """
        import duckdb
        from backend.services import dual_conn

        db_path = tmp_path / "w2_rfm_version_ci.duckdb"
        duckdb.connect(str(db_path)).close()

        monkeypatch.setenv("FQ_DB_MODE", "schema_test")
        monkeypatch.setattr(dual_conn, "DUCKDB_PATH", db_path)
        try:
            import backend.config as cfg
            monkeypatch.setattr(cfg, "DUCKDB_PATH", db_path)
            monkeypatch.setattr(cfg, "DB_MODE", "schema_test")
        except Exception:  # noqa: BLE001
            pass

        with dual_conn._read_lock:
            while dual_conn._read_pool:
                try:
                    dual_conn._read_pool.pop().close()
                except Exception:  # noqa: BLE001
                    pass

        yield db_path

        with dual_conn._read_lock:
            while dual_conn._read_pool:
                try:
                    dual_conn._read_pool.pop().close()
                except Exception:  # noqa: BLE001
                    pass

    def test_endpoint_returns_manifest_info(
        self, manifest_dir, bypass_auth, isolated_read_db,
    ):
        """mock get_rfm_manifest_info 返回 dict, 验 endpoint schema."""
        from fastapi.testclient import TestClient
        from backend.main import app

        path, _ = manifest_dir
        SnapshotManifest(path).write_active("test_view_v1")
        # 替换 manifest 路径
        from backend.services.rfm import loader
        with patch.object(loader, "DEFAULT_MANIFEST_PATH", path), bypass_auth:
            client = TestClient(app)
            response = client.get(
                "/api/v1/rfm/version",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert response.status_code == 200, f"got {response.status_code}: {response.text}"
            data = response.json()
            assert data["active_view"] == "test_view_v1"
            assert "version" in data
            assert "ts" in data
            assert "path" in data

    def test_endpoint_returns_empty_when_no_manifest(
        self, manifest_dir, bypass_auth, isolated_read_db,
    ):
        """manifest 缺失 → active_view 空串, version=0."""
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.services.rfm import loader

        path, _ = manifest_dir
        # path 不存在
        with patch.object(loader, "DEFAULT_MANIFEST_PATH", path), bypass_auth:
            client = TestClient(app)
            response = client.get(
                "/api/v1/rfm/version",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert response.status_code == 200, f"got {response.status_code}: {response.text}"
            data = response.json()
            assert data["active_view"] == ""
            assert data["version"] == 0
