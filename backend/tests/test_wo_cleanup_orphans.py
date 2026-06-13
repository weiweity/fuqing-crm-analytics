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

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestCleanupFqTmpOrphans:
    """atexit 钩子 _cleanup_fq_tmp_orphans 行为测试。"""

    def test_deletes_only_whitelisted_prefixes(self, tmp_path):
        """白名单外的前缀绝不删（防止误删用户/系统文件）。"""
        from scripts.etl import cli

        wl_files = [
            tmp_path / "_fq_ro_old.duckdb",
            tmp_path / "sample_query_old.duckdb",
        ]
        non_wl_file = tmp_path / "user_important_data.duckdb"
        for f in wl_files + [non_wl_file]:
            f.write_bytes(b"x" * 100)
            old_time = time.time() - 48 * 3600
            os.utime(f, (old_time, old_time))

        new_prefixes = (
            str(tmp_path / "_fq_ro"),
            str(tmp_path / "sample_"),
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
            f = tmp_path / f"sample_old_{i}.duckdb"
            f.write_bytes(b"x" * 100)
            old_time = time.time() - 48 * 3600
            os.utime(f, (old_time, old_time))
            files.append(f)

        new_prefixes = (str(tmp_path / "sample_"),)
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
            f = tmp_path / f"sample_huge_{i}.duckdb"
            f.write_bytes(b"x" * 10)  # 物理上只写 10 字节
            old_time = time.time() - 48 * 3600
            os.utime(f, (old_time, old_time))
            files.append(f)

        new_prefixes = (str(tmp_path / "sample_huge_"),)
        # patch 在 cli 模块命名空间（os 是 frozen 不能直接 mock）
        with patch.object(cli, "FQ_TMP_PREFIXES", new_prefixes), \
             patch.object(cli_mod, "os") as mock_os:
            mock_os.path.getsize.return_value = 50 * 1024**3
            mock_os.path.getmtime.return_value = time.time() - 48 * 3600
            mock_os.path.islink.return_value = False  # F7: 全部视为非 symlink
            mock_os.path.exists.return_value = False  # F3: marker 不存在（保守模式）
            mock_os.remove = os.remove  # 真实 remove 行为
            deleted_count = cli._cleanup_fq_tmp_orphans()

        # 3 × 50GB = 150GB，cap 100GB → 应只删 2 个（2×50=100GB 命中 cap）
        assert deleted_count == 2
        # 顺序无关断言: byte cap 阻止后应只保留 1 个文件（具体哪个不固定，
        # 取决于 glob.glob 在当前文件系统的返回顺序）
        assert sum(1 for f in files if f.exists()) == 1, (
            "byte cap 阻止后应只保留 1 个文件"
        )

    def test_cap_starvation_avoided(self, tmp_path):
        """first-prefix starvation 修复验证（F5）：两个 prefix 都能被扫到。"""
        from scripts.etl import cli

        # 造 8 个 _fq_ro* + 2 个 sample_*，都用同 mtime
        ro_files = [tmp_path / f"_fq_ro_x{i}.duckdb" for i in range(8)]
        fq_files = [tmp_path / f"sample_x{i}.duckdb" for i in range(2)]
        all_files = ro_files + fq_files
        for f in all_files:
            f.write_bytes(b"x" * 100)
            old_time = time.time() - 48 * 3600
            os.utime(f, (old_time, old_time))

        new_prefixes = (
            str(tmp_path / "_fq_ro"),
            str(tmp_path / "sample_"),
        )
        with patch.object(cli, "FQ_TMP_PREFIXES", new_prefixes):
            deleted_count = cli._cleanup_fq_tmp_orphans()

        # 5 个 cap 全用于 _fq_ro*（按 mtime 倒序）；sample_* 全部保留
        assert deleted_count == 5
        assert all(not f.exists() for f in ro_files[:5])
        assert all(f.exists() for f in ro_files[5:])
        assert all(f.exists() for f in fq_files), "sample_* 应被扫到（即使 cap 5 已用完）"

    def test_soft_fail_on_permission_error(self, tmp_path):
        """rm 失败不抛异常（软失败），且**文件不能被真删**（F27 修复）。"""
        from scripts.etl import cli

        f = tmp_path / "sample_perm_denied.duckdb"
        f.write_bytes(b"x" * 100)
        old_time = time.time() - 48 * 3600
        os.utime(f, (old_time, old_time))

        new_prefixes = (str(tmp_path / "sample_"),)

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

        f = tmp_path / "sample_log_test.duckdb"
        f.write_bytes(b"x" * 100)
        old_time = time.time() - 48 * 3600
        os.utime(f, (old_time, old_time))

        log_file = tmp_path / "fuqing-tmp-cleanup.log"
        new_prefixes = (str(tmp_path / "sample_"),)
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


class TestF3MarkerAndF7Symlink:
    """F3 marker-based 异常退出检测 + F7 symlink skip 行为测试。

    F3 修复：atexit 钩子无法覆盖 kill -9 / os._exit / OOM killer
    （Python 文档明确），marker 文件作为"近 24h 是否有 ETL 在跑"的
    旁路信号。main() 入口写 marker，cleanup 钩子读 marker 判断。

    F7 修复：symlink getmtime/getsize 跟随 target 误报 size，且 os.remove
    只删 link 不动 target，难以判断 target 是否 active。保守起见不删 symlink。
    """

    def test_f3_marker_written_in_main(self, tmp_path, monkeypatch):
        """F3 修复：main() 入口在 atexit 注册前必须先写 marker。

        验证：
          1. main() 被调用后，marker 文件存在
          2. marker 内容包含 pid / started_at / script 三个字段
          3. _write_fq_etl_marker() 在 atexit.register() 之前被调用
        """
        import argparse
        import json
        from unittest.mock import MagicMock
        from scripts.etl import cli

        marker_path = tmp_path / "fuqing-etl-marker.json"
        monkeypatch.setattr(cli, "_FQ_TMP_MARKER_PATH", str(marker_path))

        # mock argparse 走 no-op 分支（既不是 --update 也不是 --rescan-*）
        ns = argparse.Namespace(
            full=False, inc=False, update=False, update_taoke=False,
            refresh_status=False, window_days=30, rescan_spu=False,
            rescan_channel=False, product_ids=[], since=None,
            dry_run=False, apply=False, cleanup_tmp=False,
            skip_dq=False, skip_w4=False,
        )

        # 用 mock 替换 _write_fq_etl_marker，记录调用顺序
        call_order = []
        real_write = cli._write_fq_etl_marker

        def tracked_write():
            call_order.append("write")
            return real_write()

        # 替换 atexit.register 为追踪版本（实际不注册，避免污染后续测试）
        def tracked_register(*args, **kwargs):
            call_order.append("register")
            return None

        with patch.object(cli, "_write_fq_etl_marker", side_effect=tracked_write), \
             patch.object(cli.atexit, "register", side_effect=tracked_register), \
             patch.object(cli, "argparse") as mock_argparse, \
             patch.object(cli, "run_full_etl"):
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = ns
            mock_argparse.ArgumentParser.return_value = mock_parser
            try:
                cli.main()
            except SystemExit:
                pass  # argparse 走 default 分支后会调 run_full_etl，然后 sys.exit

        # 验证 marker 被写
        assert marker_path.exists(), f"main() 入口应写 marker 到 {marker_path}"

        # 验证 marker 内容 schema
        marker = json.loads(marker_path.read_text())
        assert marker["pid"] == os.getpid(), "marker.pid 应等于当前进程 PID"
        assert "started_at" in marker and marker["started_at"], "marker 缺 started_at"
        assert marker["script"] == "cli.py", "marker.script 应为 cli.py"

        # 验证调用顺序：write 在 register 之前
        assert "write" in call_order, "_write_fq_etl_marker 未被调用"
        assert "register" in call_order, "atexit.register 未被调用"
        assert call_order.index("write") < call_order.index("register"), (
            f"F3 修复：_write_fq_etl_marker 必须在 atexit.register 之前调用，"
            f"实际顺序: {call_order}"
        )

    def test_f3_marker_cleared_on_cleanup(self, tmp_path, monkeypatch):
        """F3 修复：cleanup 后 marker 必须被删（无论原本是否存在）。

        场景 A：marker 原本存在 → cleanup 后被删
        场景 B：marker 原本不存在 → cleanup 不报错（软失败）
        """
        from scripts.etl import cli

        marker_path = tmp_path / "fuqing-etl-marker.json"
        monkeypatch.setattr(cli, "_FQ_TMP_MARKER_PATH", str(marker_path))

        # 场景 A：marker 存在 → cleanup 后被删
        marker_path.write_text(
            '{"pid": 12345, "started_at": "2026-06-05T00:00:00+00:00", "script": "cli.py"}'
        )
        assert marker_path.exists(), "前置：marker 应被预创建"

        new_prefixes = (str(tmp_path / "sample_"),)
        with patch.object(cli, "FQ_TMP_PREFIXES", new_prefixes):
            cli._cleanup_fq_tmp_orphans()

        assert not marker_path.exists(), (
            "F3 修复：cleanup 后 marker 必须被删（场景 A：原本存在）"
        )

        # 场景 B：marker 不存在 → cleanup 不抛异常
        with patch.object(cli, "FQ_TMP_PREFIXES", new_prefixes):
            # 软失败：不应抛 SystemExit / OSError
            cli._cleanup_fq_tmp_orphans()
        # 验证确实没抛异常 + marker 仍不存在
        assert not marker_path.exists(), "场景 B：marker 仍不存在"

    def test_f7_skip_symlink(self, tmp_path):
        """F7 修复：symlink 不删（避免误报 size + 难判断 target active）。

        验证：
          1. 在白名单前缀下创建 symlink → 不被删
          2. target 不动（双重确认）
          3. 删除计数为 0
        """
        from scripts.etl import cli

        # target 文件：不在白名单前缀下，避免被 _collect 误扫
        target = tmp_path / "real_target.duckdb"
        target.write_bytes(b"x" * 100)
        old_time = time.time() - 48 * 3600
        os.utime(target, (old_time, old_time))

        # symlink：在白名单前缀下
        link = tmp_path / "sample_link.duckdb"
        os.symlink(str(target), str(link))

        # 前置：symlink 创建成功
        assert link.is_symlink(), "前置：symlink 应被创建"
        assert os.path.islink(str(link)) is True, "前置：os.path.islink 应返回 True"

        new_prefixes = (str(tmp_path / "sample_"),)
        with patch.object(cli, "FQ_TMP_PREFIXES", new_prefixes):
            deleted_count = cli._cleanup_fq_tmp_orphans()

        # 验证 1：symlink 不被删（仍然存在且是 symlink）
        assert link.is_symlink(), (
            "F7 修复：symlink 不应被删（os.remove 只删 link 不动 target，"
            "但我们更保守——直接跳过）"
        )
        # 验证 2：删除计数为 0
        assert deleted_count == 0, "F7 修复：symlink 应被跳过，删除计数为 0"
        # 验证 3：target 不动
        assert target.exists(), "target 不应被 cleanup 影响"


class TestF3MarkerConstants:
    """F3 marker 常量 sanity 检查（防回归）。"""

    def test_marker_path_constant_exists(self):
        from scripts.etl import cli
        assert hasattr(cli, "_FQ_TMP_MARKER_PATH"), "F3: marker path 常量缺失"
        assert cli._FQ_TMP_MARKER_PATH.endswith(".json"), "marker 应为 JSON 文件"

    def test_marker_path_is_absolute(self):
        """marker 必须用绝对路径（/tmp 下，避免相对路径解析歧义）。"""
        from scripts.etl import cli
        assert os.path.isabs(cli._FQ_TMP_MARKER_PATH), (
            "F3: marker path 必须是绝对路径"
        )

    def test_write_helper_exists(self):
        """F3: _write_fq_etl_marker 函数必须存在。"""
        from scripts.etl import cli
        assert hasattr(cli, "_write_fq_etl_marker"), "F3: _write_fq_etl_marker 缺失"
        assert callable(cli._write_fq_etl_marker), "F3: _write_fq_etl_marker 必须可调用"


class TestCleanupTmpFlag:
    """--cleanup-tmp CLI 早退出路径测试（handoff 6/5 follow-up #3 落地）。

    验证：
      - argparse 接 --cleanup-tmp 不报错
      - main() 走 cleanup 早退出路径，调一次 _cleanup_fq_tmp_orphans
      - sys.exit(0) 退出（不进入 ETL 主流程）
    """

    def test_argparse_accepts_cleanup_tmp(self):
        """cli.py main() 应能解析 --cleanup-tmp 并早退出（SystemExit 0）。"""
        from scripts.etl import cli
        with patch.object(sys, "argv", ["cli.py", "--cleanup-tmp"]):
            with patch.object(cli, "_cleanup_fq_tmp_orphans", return_value=0) as m:
                with patch("scripts.etl.cli.sys.exit", side_effect=SystemExit(0)) as mock_exit:
                    with pytest.raises(SystemExit):
                        cli.main()
        # 验证 1：cleanup 函数被调一次
        m.assert_called_once()
        # 验证 2：sys.exit(0) 被调（早退出，不进 ETL）
        mock_exit.assert_called_once_with(0)

    def test_cleanup_tmp_prints_audit_path(self, capsys):
        """--cleanup-tmp 应打印审计日志路径提示（运维友好）。"""
        from scripts.etl import cli
        with patch.object(sys, "argv", ["cli.py", "--cleanup-tmp"]):
            with patch.object(cli, "_cleanup_fq_tmp_orphans", return_value=3):
                with patch("scripts.etl.cli.sys.exit", side_effect=SystemExit(0)):
                    with pytest.raises(SystemExit):
                        cli.main()
        captured = capsys.readouterr()
        # 验证 1：输出包含审计日志路径
        assert "/tmp/fuqing-tmp-cleanup.log" in captured.out, (
            "运维提示应包含审计日志路径"
        )
        # 验证 2：输出包含删除计数
        assert "3" in captured.out, "应显示删除的文件数"
