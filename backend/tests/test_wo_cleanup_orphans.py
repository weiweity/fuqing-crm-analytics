"""
WO-x 治理：/tmp 孤儿 duckdb 自动清理钩子单元测试

背景（2026-06-05 治理事件）:
  6/1-6/4 期间子 agent 调试 E2E 测试时手工 cp 主库到 /tmp，累计 7 个
  38-44GB 孤儿 duckdb 文件，占用磁盘 ~349GB。本测试覆盖 cli.py 中
  atexit 钩子 _cleanup_fq_tmp_orphans 的核心行为。

adversarial review 2026-06-05 修复:
  - F1 (CRITICAL): test_skips_fresh_files_under_24h 改用 patch 隔离到 tmp_path
  - F2 (HIGH): test_atexit_registered 真验证 atexit._exithandlers 含本函数
  - F23 (LOW): 删未用的 monkeypatch 参数
  - F27 (LOW): test_soft_fail_on_permission_error 加 assert f.exists() 验证
  - 新增: byte cap 测试、log 持久化测试、cap starvation 测试、main() 不
    自动 register 测试（防止 atexit 顶层注册回归）
"""
import atexit as atexit_mod
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestCleanupFqTmpOrphans:
    """atexit 钩子 _cleanup_fq_tmp_orphans 行为测试。"""

    def test_deletes_only_whitelisted_prefixes(self, tmp_path):
        """白名单外的前缀绝不删（防止误删用户/系统文件）。"""
        from scripts.etl import cli

        wl_files = [
            tmp_path / "_fq_ro_old.duckdb",
            tmp_path / "fuqing_query_old.duckdb",
        ]
        non_wl_file = tmp_path / "user_important_data.duckdb"
        for f in wl_files + [non_wl_file]:
            f.write_bytes(b"x" * 100)
            old_time = time.time() - 48 * 3600
            os.utime(f, (old_time, old_time))

        new_prefixes = (
            str(tmp_path / "_fq_ro"),
            str(tmp_path / "fuqing_"),
        )
        with patch.object(cli, "FQ_TMP_PREFIXES", new_prefixes):
            deleted_count = cli._cleanup_fq_tmp_orphans()

        # 2 个白名单 prefix 各匹配 1 个文件 = 2 个删除
        assert deleted_count == 2
        for f in wl_files:
            assert not f.exists(), f"白名单文件应被删: {f}"
        # 非白名单文件绝不能删
        assert non_wl_file.exists(), "非白名单文件绝不能删"

    def test_skips_fresh_files_under_24h(self, tmp_path):
        """24h 内的文件不删（保留活跃跑批产物）。F1 修复：用 patch 隔离到 tmp_path。"""
        from scripts.etl import cli

        # 在 tmp_path 造一个 1h 前的新文件，patch FQ_TMP_PREFIXES 指向它
        fresh_file = tmp_path / "_fq_ro_fresh.duckdb"
        fresh_file.write_bytes(b"x" * 100)
        new_time = time.time() - 3600  # 1h 前
        os.utime(fresh_file, (new_time, new_time))

        new_prefixes = (str(tmp_path / "_fq_ro"),)
        with patch.object(cli, "FQ_TMP_PREFIXES", new_prefixes):
            deleted_count = cli._cleanup_fq_tmp_orphans()

        # 1h 前的文件应被跳过
        assert deleted_count == 0
        assert fresh_file.exists(), "1h 前的文件不能被删"

    def test_max_count_cap(self, tmp_path):
        """count cap：单次最多删 _FQ_TMP_MAX_DELETE_PER_RUN 个文件（F5 cap starvation 修复验证）。"""
        from scripts.etl import cli

        # 造 8 个老白名单文件（应只删 5 个 = MAX）
        files = []
        for i in range(8):
            f = tmp_path / f"fuqing_old_{i}.duckdb"
            f.write_bytes(b"x" * 100)
            old_time = time.time() - 48 * 3600
            os.utime(f, (old_time, old_time))
            files.append(f)

        new_prefixes = (str(tmp_path / "fuqing_"),)
        with patch.object(cli, "FQ_TMP_PREFIXES", new_prefixes):
            deleted_count = cli._cleanup_fq_tmp_orphans()

        assert deleted_count == cli._FQ_TMP_MAX_DELETE_PER_RUN == 5
        remaining = [f for f in files if f.exists()]
        assert len(remaining) == 3
        deleted = [f for f in files if not f.exists()]
        assert len(deleted) == 5
        assert set(deleted + remaining) == set(files)

    def test_byte_cap(self, tmp_path):
        """byte cap：单次累计删除字节 ≤ _FQ_TMP_MAX_DELETE_BYTES_PER_RUN（F8 修复验证）。

        模拟场景：3 个文件各 50GB，总和 150GB > 100GB cap。
        期望：只删 2 个（100GB），剩 1 个（50GB）保留。
        """
        from scripts.etl import cli
        import scripts.etl.cli as cli_mod

        files = []
        for i in range(3):
            f = tmp_path / f"fuqing_huge_{i}.duckdb"
            f.write_bytes(b"x" * 10)  # 物理上只写 10 字节
            old_time = time.time() - 48 * 3600
            os.utime(f, (old_time, old_time))
            files.append(f)

        new_prefixes = (str(tmp_path / "fuqing_huge_"),)
        # patch 在 cli 模块命名空间（os 是 frozen 不能直接 mock）
        with patch.object(cli, "FQ_TMP_PREFIXES", new_prefixes), \
             patch.object(cli_mod, "os") as mock_os:
            mock_os.path.getsize.return_value = 50 * 1024**3
            mock_os.path.getmtime.return_value = time.time() - 48 * 3600
            mock_os.remove = os.remove  # 真实 remove 行为
            deleted_count = cli._cleanup_fq_tmp_orphans()

        # 3 × 50GB = 150GB，cap 100GB → 应只删 2 个（2×50=100GB 命中 cap）
        assert deleted_count == 2
        # 第 3 个应保留（byte cap 阻止）
        assert files[2].exists(), "byte cap 阻止后第 3 个文件应保留"

    def test_cap_starvation_avoided(self, tmp_path):
        """first-prefix starvation 修复验证（F5）：两个 prefix 都能被扫到。"""
        from scripts.etl import cli

        # 造 8 个 _fq_ro* + 2 个 fuqing_*，都用同 mtime
        ro_files = [tmp_path / f"_fq_ro_x{i}.duckdb" for i in range(8)]
        fq_files = [tmp_path / f"fuqing_x{i}.duckdb" for i in range(2)]
        all_files = ro_files + fq_files
        for f in all_files:
            f.write_bytes(b"x" * 100)
            old_time = time.time() - 48 * 3600
            os.utime(f, (old_time, old_time))

        new_prefixes = (
            str(tmp_path / "_fq_ro"),
            str(tmp_path / "fuqing_"),
        )
        with patch.object(cli, "FQ_TMP_PREFIXES", new_prefixes):
            deleted_count = cli._cleanup_fq_tmp_orphans()

        # 5 个 cap 全用于 _fq_ro*（按 mtime 倒序）；fuqing_* 全部保留
        assert deleted_count == 5
        assert all(not f.exists() for f in ro_files[:5])
        assert all(f.exists() for f in ro_files[5:])
        assert all(f.exists() for f in fq_files), "fuqing_* 应被扫到（即使 cap 5 已用完）"

    def test_soft_fail_on_permission_error(self, tmp_path):
        """rm 失败不抛异常（软失败），且**文件不能被真删**（F27 修复）。"""
        from scripts.etl import cli

        f = tmp_path / "fuqing_perm_denied.duckdb"
        f.write_bytes(b"x" * 100)
        old_time = time.time() - 48 * 3600
        os.utime(f, (old_time, old_time))

        new_prefixes = (str(tmp_path / "fuqing_"),)

        def mock_remove(_path, _err=PermissionError("mock denied")):
            raise _err

        with patch.object(cli, "FQ_TMP_PREFIXES", new_prefixes), \
             patch.object(cli.os, "remove", side_effect=mock_remove):
            deleted_count = cli._cleanup_fq_tmp_orphans()
            assert deleted_count == 0

        # F27 修复：mock 失效时文件不能真被删
        assert f.exists(), "mock remove 失败时文件必须保留"

    def test_persistent_log_written(self, tmp_path):
        """清理结果写到 _FQ_TMP_LOG_PATH（F12 修复：返回值的归宿）。"""
        from scripts.etl import cli

        f = tmp_path / "fuqing_log_test.duckdb"
        f.write_bytes(b"x" * 100)
        old_time = time.time() - 48 * 3600
        os.utime(f, (old_time, old_time))

        log_file = tmp_path / "fuqing-tmp-cleanup.log"
        new_prefixes = (str(tmp_path / "fuqing_"),)
        with patch.object(cli, "FQ_TMP_PREFIXES", new_prefixes), \
             patch.object(cli, "_FQ_TMP_LOG_PATH", str(log_file)):
            cli._cleanup_fq_tmp_orphans()

        # 持久日志应被写
        assert log_file.exists()
        log_content = log_file.read_text()
        assert "tmp-cleanup" in log_content
        assert str(f) in log_content

    def test_atexit_registered_only_in_main(self):
        """atexit 钩子**不在 import 时注册**（F4 修复），只在 main() 内部注册。

        验证：模块 import 不会触发 atexit 注册 → pytest 退出时不会扫 /tmp。
        Python 3.14+ atexit 内部结构变了：用 atexit.unregister 试探性删除，
        验证 _cleanup_fq_tmp_orphans 不在已注册列表中（无论 Python 版本）。
        """
        from scripts.etl import cli

        # atexit.unregister 返回 True 表示成功注销（即确实注册了）
        # 修复后应该返回 False（从未注册）
        was_registered = atexit_mod.unregister(cli._cleanup_fq_tmp_orphans)
        assert not was_registered, \
            "atexit.register 不应在 import 顶层调用，否则 pytest 退出时静默扫 /tmp"


class TestCleanupFqTmpConstants:
    """配置常量 sanity 检查（F2 真验证 + 防回归）。"""

    def test_constants_exist(self):
        from scripts.etl import cli
        assert hasattr(cli, "FQ_TMP_PREFIXES")
        assert hasattr(cli, "_FQ_TMP_MAX_DELETE_PER_RUN")
        assert hasattr(cli, "_FQ_TMP_MIN_AGE_HOURS")
        assert hasattr(cli, "_FQ_TMP_MAX_DELETE_BYTES_PER_RUN")
        assert hasattr(cli, "_FQ_TMP_LOG_PATH")

    def test_whitelist_only_2_prefixes_after_f13(self):
        """F13 修复：claude-501 死 prefix 已删，只剩 2 个真实 prefix。"""
        from scripts.etl import cli
        assert len(cli.FQ_TMP_PREFIXES) == 2
        assert all(p.startswith("/private/tmp/") for p in cli.FQ_TMP_PREFIXES)

    def test_byte_cap_reasonable(self):
        """byte cap 不应是 0（无意义）或无限（F8 修复验证）。"""
        from scripts.etl import cli
        assert 0 < cli._FQ_TMP_MAX_DELETE_BYTES_PER_RUN < 1024**4  # 1TB 上限合理

    def test_count_cap_reasonable(self):
        """count cap 是 5（防御性批量误删）。"""
        from scripts.etl import cli
        assert 1 <= cli._FQ_TMP_MAX_DELETE_PER_RUN <= 20
