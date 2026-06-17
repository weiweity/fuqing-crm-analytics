"""Sprint 31.1 — TrackerDB 单元测试 (25+ cases)

设计要点:
  - 每个 test 用独立 tmp_path/tracker.db, 不污染全局
  - bootstrap 测试用 monkeypatch FQ_TMP_PREFIXES 风格 (跟 test_wo_cleanup_orphans 同)
  - 损坏自愈测试: 直接写 garbage bytes 到 .db 文件, 验证 .corrupt-<ts> 备份 + 重建
  - env var 禁用测试: monkeypatch.setenv
"""
import os
import sqlite3
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def tracker_db_path(tmp_path):
    """每个 test 一个独立 tracker DB."""
    return str(tmp_path / "test-tracker.db")


@pytest.fixture
def fresh_tracker(tracker_db_path):
    """构造 + 自动 close 句柄 (实际上 TrackerDB 用 per-call connection, 无 close 必要)."""
    from scripts.etl.common.tmp_tracker import TrackerDB
    return TrackerDB(db_path=tracker_db_path)


# ─────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────
class TestTrackerDBSchema:
    def test_create_table_idempotent(self, tracker_db_path):
        """第二次开同一 DB 不报错 (CREATE TABLE IF NOT EXISTS)."""
        from scripts.etl.common.tmp_tracker import TrackerDB
        t1 = TrackerDB(db_path=tracker_db_path)
        t1.register("/tmp/foo.duckdb", 100, pid=1234)
        # 再开一次 (模拟 cleanup 跑两次), 不能 raise
        t2 = TrackerDB(db_path=tracker_db_path)
        assert t2.is_available()
        # row 还在
        assert t2.is_tracked("/tmp/foo.duckdb")

    def test_schema_columns_match_design(self, tracker_db_path):
        """表 schema 必须跟设计一致: path PK + create_at + size + pid + last_seen."""
        from scripts.etl.common.tmp_tracker import TrackerDB
        t = TrackerDB(db_path=tracker_db_path)
        t.register("/tmp/foo.duckdb", 100, pid=1234)

        conn = sqlite3.connect(tracker_db_path)
        try:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(tracker)").fetchall()]
        finally:
            conn.close()
        # 5 列, 顺序跟 _SCHEMA 一致
        assert cols == ["path", "create_at", "size", "pid", "last_seen"]

    def test_wal_mode_enabled(self, tracker_db_path):
        """__init__ 后 journal_mode 必须是 WAL."""
        from scripts.etl.common.tmp_tracker import TrackerDB
        TrackerDB(db_path=tracker_db_path)

        conn = sqlite3.connect(tracker_db_path)
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        finally:
            conn.close()
        assert mode.lower() == "wal", f"期望 WAL 模式, 实际 {mode}"


# ─────────────────────────────────────────────────────────────
# Register
# ─────────────────────────────────────────────────────────────
class TestTrackerDBRegister:
    def test_register_new_path(self, fresh_tracker, tmp_path):
        """新路径 register → is_tracked True."""
        f = tmp_path / "fuqing_new.duckdb"
        f.write_bytes(b"x" * 1024)
        fresh_tracker.register(str(f), size=1024, pid=os.getpid())
        assert fresh_tracker.is_tracked(str(f))

    def test_register_insert_or_replace_idempotent(self, fresh_tracker, tmp_path):
        """register 同一 path 两次 = UPDATE 语义 (INSERT OR REPLACE), 不应 raise 不应 duplicate."""
        f = tmp_path / "fuqing_x.duckdb"
        f.write_bytes(b"x" * 1024)
        fresh_tracker.register(str(f), size=1024, pid=111)
        fresh_tracker.register(str(f), size=2048, pid=222)  # 第二次
        rows = fresh_tracker.list_expired(age_hours=0)  # age 0 = 全 include
        matching = [r for r in rows if r[0].endswith("fuqing_x.duckdb")]
        assert len(matching) == 1, f"应该 1 行, 实际 {len(matching)}"
        assert matching[0][1] == 2048, f"size 应该是 2048 (后写), 实际 {matching[0][1]}"

    def test_register_soft_fails_on_readonly_db(self, tmp_path):
        """chmod 000 DB 目录 → register 软失败不 raise."""
        from scripts.etl.common.tmp_tracker import TrackerDB
        ro_dir = tmp_path / "ro_dir"
        ro_dir.mkdir()
        db_path = str(ro_dir / "tracker.db")
        TrackerDB(db_path=db_path)  # init OK (目录可写)
        # chmod parent dir 000 — 后续操作全部失败
        os.chmod(ro_dir, 0o000)
        try:
            t = TrackerDB(db_path=db_path)
            # register 必须不 raise (软失败)
            t.register("/tmp/whatever.duckdb", 100, pid=1)
            # list 也必须不 raise
            result = t.list_expired(24)
            assert result == []  # 软失败 → 空 list
        finally:
            os.chmod(ro_dir, 0o755)  # 恢复避免污染 tmp_path

    def test_register_soft_fails_on_corrupt_db_self_heals(self, tracker_db_path):
        """DB 文件被写 garbage → TrackerDB 构造时自愈 (rename .corrupt + 重建)."""
        # 1. 先造正常 DB
        from scripts.etl.common.tmp_tracker import TrackerDB
        t1 = TrackerDB(db_path=tracker_db_path)
        t1.register("/tmp/foo.duckdb", 100, pid=1)
        assert os.path.exists(tracker_db_path)

        # 2. 写 garbage bytes 覆盖 DB (模拟磁盘损坏)
        with open(tracker_db_path, "wb") as f:
            f.write(b"GARBAGE_NOT_SQLITE_FORMAT" * 100)

        # 3. 重新构造 — 必须自愈, 不 raise
        t2 = TrackerDB(db_path=tracker_db_path)
        assert t2.is_available(), "损坏 DB 自愈后必须 available"

        # 4. 原 row 已丢失 (新 DB), 但应能 register 新 row
        t2.register("/tmp/bar.duckdb", 200, pid=2)
        assert t2.is_tracked("/tmp/bar.duckdb")

        # 5. 验证 .corrupt-<ts> 备份存在
        corrupt_files = [
            p for p in os.listdir(os.path.dirname(tracker_db_path))
            if p.startswith(os.path.basename(tracker_db_path) + ".corrupt-")
        ]
        assert len(corrupt_files) == 1, f"应该有 1 个 corrupt 备份, 实际 {len(corrupt_files)}"

    def test_register_disabled_env_var_is_noop(self, tracker_db_path, monkeypatch):
        """FQ_TMP_TRACKER_DISABLED=1 → register 不写 DB."""
        from scripts.etl.common.tmp_tracker import TrackerDB
        monkeypatch.setenv("FQ_TMP_TRACKER_DISABLED", "1")
        t = TrackerDB(db_path=tracker_db_path)
        # is_available() 在 disabled 模式下也是 False
        # (但 _init_db 没跑, 严格说 DB 文件根本不应该被创建)
        if os.path.exists(tracker_db_path):
            # 如果 DB 已存在, register 也应该 no-op
            t.register("/tmp/foo.duckdb", 100, pid=1)
            assert not t.is_tracked("/tmp/foo.duckdb")


# ─────────────────────────────────────────────────────────────
# List Expired
# ─────────────────────────────────────────────────────────────
class TestTrackerDBListExpired:
    def test_list_expired_filters_by_age(self, fresh_tracker):
        """create_at 25h 前的才 list_expired(24) 出来; 1h 前的不出."""
        old_path = "/tmp/fuqing_old.duckdb"
        fresh_path = "/tmp/fuqing_fresh.duckdb"
        # register 后手工改 create_at 模拟历史文件
        fresh_tracker.register(old_path, 100, pid=1)
        fresh_tracker.register(fresh_path, 100, pid=1)
        # 把 old_path 的 create_at 改成 25h 前
        conn = sqlite3.connect(fresh_tracker.db_path)
        try:
            conn.execute(
                "UPDATE tracker SET create_at = ? WHERE path = ?",
                (time.time() - 25 * 3600, str(Path(old_path).resolve())),
            )
            conn.commit()
        finally:
            conn.close()

        expired = fresh_tracker.list_expired(age_hours=24)
        paths = [r[0] for r in expired]
        assert any(p.endswith("fuqing_old.duckdb") for p in paths)
        assert not any(p.endswith("fuqing_fresh.duckdb") for p in paths)

    def test_list_expired_excludes_zero_size(self, fresh_tracker):
        """size=0 的 row 排除 (mid-delete transient state)."""
        path = "/tmp/fuqing_zero.duckdb"
        fresh_tracker.register(path, size=0, pid=1)  # size=0
        expired = fresh_tracker.list_expired(age_hours=0)
        assert not any(r[0].endswith("fuqing_zero.duckdb") for r in expired)

    def test_list_expired_orders_by_create_at_asc(self, fresh_tracker):
        """list_expired 按 create_at ASC 排序 (oldest first)."""
        # register 3 个, 手工改 create_at 制造 3 个不同 age
        paths = [
            "/tmp/fuqing_a.duckdb",
            "/tmp/fuqing_b.duckdb",
            "/tmp/fuqing_c.duckdb",
        ]
        now = time.time()
        ages = [25 * 3600, 30 * 3600, 27 * 3600]  # a=25h, b=30h, c=27h 前
        for p, age in zip(paths, ages):
            fresh_tracker.register(p, size=100, pid=1)

        conn = sqlite3.connect(fresh_tracker.db_path)
        try:
            for p, age in zip(paths, ages):
                conn.execute(
                    "UPDATE tracker SET create_at = ? WHERE path = ?",
                    (now - age, str(Path(p).resolve())),
                )
            conn.commit()
        finally:
            conn.close()

        expired = fresh_tracker.list_expired(age_hours=24)
        # 排序: b(30h) < c(27h) < a(25h)  按 create_at ASC
        expired_basenames = [Path(r[0]).name for r in expired]
        assert expired_basenames == ["fuqing_b.duckdb", "fuqing_c.duckdb", "fuqing_a.duckdb"]


# ─────────────────────────────────────────────────────────────
# Remove
# ─────────────────────────────────────────────────────────────
class TestTrackerDBRemove:
    def test_remove_deletes_row(self, fresh_tracker, tmp_path):
        """register → remove → is_tracked False."""
        f = tmp_path / "fuqing_rm.duckdb"
        f.write_bytes(b"x" * 100)
        fresh_tracker.register(str(f), size=100, pid=1)
        assert fresh_tracker.is_tracked(str(f))
        fresh_tracker.remove(str(f))
        assert not fresh_tracker.is_tracked(str(f))

    def test_remove_idempotent_on_missing_path(self, fresh_tracker):
        """remove 未 register 过的 path = no-op, 不 raise."""
        fresh_tracker.remove("/tmp/never_existed.duckdb")  # 不应 raise

    def test_remove_soft_fails(self, fresh_tracker, monkeypatch):
        """remove 在 sqlite3 error 时不 raise."""
        def broken_execute(*args, **kwargs):
            raise sqlite3.OperationalError("simulated DB lock")
        # patch _open_connection 强制 return broken conn
        from scripts.etl.common import tmp_tracker
        with patch.object(tmp_tracker, "_open_connection", side_effect=broken_execute):
            fresh_tracker.remove("/tmp/whatever.duckdb")  # 不应 raise


# ─────────────────────────────────────────────────────────────
# Is Tracked
# ─────────────────────────────────────────────────────────────
class TestTrackerDBIsTracked:
    def test_is_tracked_true_when_present(self, fresh_tracker, tmp_path):
        f = tmp_path / "fuqing_present.duckdb"
        f.write_bytes(b"x" * 100)
        fresh_tracker.register(str(f), size=100, pid=1)
        assert fresh_tracker.is_tracked(str(f)) is True

    def test_is_tracked_false_when_absent(self, fresh_tracker):
        assert fresh_tracker.is_tracked("/tmp/never_existed.duckdb") is False


# ─────────────────────────────────────────────────────────────
# Bootstrap
# ─────────────────────────────────────────────────────────────
class TestTrackerDBBootstrap:
    def test_bootstrap_adopts_unknown_files(self, fresh_tracker, tmp_path):
        """103GB 场景核心: 没 register 的 fuqing_*.duckdb 被 bootstrap 拾起."""
        # 造一个未 register 的 fuqing_*.duckdb, mtime 25h 前
        target = tmp_path / "fuqing_external.duckdb"
        target.write_bytes(b"x" * 1024)
        old = time.time() - 25 * 3600
        os.utime(target, (old, old))

        # bootstrap 用自定义 prefix 指向 tmp_path (隔离)
        adopted = fresh_tracker.bootstrap_from_filesystem(
            prefixes=(str(tmp_path / "fuqing_"),)
        )
        assert adopted == 1
        # 现在 is_tracked True
        assert fresh_tracker.is_tracked(str(target))

    def test_bootstrap_idempotent(self, fresh_tracker, tmp_path):
        """第二次 bootstrap 同一目录 → adopted=0."""
        target = tmp_path / "fuqing_x.duckdb"
        target.write_bytes(b"x" * 100)
        old = time.time() - 25 * 3600
        os.utime(target, (old, old))

        prefixes = (str(tmp_path / "fuqing_"),)
        assert fresh_tracker.bootstrap_from_filesystem(prefixes=prefixes) == 1
        assert fresh_tracker.bootstrap_from_filesystem(prefixes=prefixes) == 0

    def test_bootstrap_skips_already_tracked(self, fresh_tracker, tmp_path):
        """已 register 的不会被 bootstrap 二次采用."""
        target = tmp_path / "fuqing_y.duckdb"
        target.write_bytes(b"x" * 100)
        # 先 register
        fresh_tracker.register(str(target), size=100, pid=1)
        # bootstrap 不应再 adopted
        prefixes = (str(tmp_path / "fuqing_"),)
        adopted = fresh_tracker.bootstrap_from_filesystem(prefixes=prefixes)
        assert adopted == 0

    def test_bootstrap_records_real_mtime_not_now(self, fresh_tracker, tmp_path):
        """设计决策 #1: create_at = 文件真实 mtime, 不是 now()."""
        target = tmp_path / "fuqing_mtime_test.duckdb"
        target.write_bytes(b"x" * 100)
        # 设 mtime 到 1 年前
        very_old = time.time() - 365 * 24 * 3600
        os.utime(target, (very_old, very_old))

        prefixes = (str(tmp_path / "fuqing_"),)
        fresh_tracker.bootstrap_from_filesystem(prefixes=prefixes)

        # list_expired(0) 返全部, 检查 create_at 接近 very_old
        conn = sqlite3.connect(fresh_tracker.db_path)
        try:
            row = conn.execute(
                "SELECT create_at FROM tracker WHERE path = ?",
                (str(Path(target).resolve()),),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        # 应该 ~ very_old, 不该是 now()
        create_at = row[0]
        assert abs(create_at - very_old) < 1.0, (
            f"create_at 应是文件 mtime ({very_old}), 实际 {create_at} "
            f"(差 {create_at - very_old}s, 偏离 mtime 太多说明是 now())"
        )

    def test_bootstrap_skips_symlinks(self, fresh_tracker, tmp_path):
        """symlink 跳过 (跟 cli.py F7 一致) — 不会为 symlink 单独创建 row.

        注: is_tracked 走 Path.resolve() 跟 link 走, 所以 symlink 的 is_tracked
        跟 real file 是同一个 row. 验证点应是 DB 里 row 总数 = 1 (real file only),
        不是 is_tracked(symlink) == False (semantically 同一文件).
        """
        real_file = tmp_path / "fuqing_real.duckdb"
        real_file.write_bytes(b"x" * 100)
        old = time.time() - 25 * 3600
        os.utime(real_file, (old, old))
        # 造 symlink 指向 real file
        symlink_path = tmp_path / "fuqing_link.duckdb"
        os.symlink(str(real_file), str(symlink_path))

        prefixes = (str(tmp_path / "fuqing_"),)
        adopted = fresh_tracker.bootstrap_from_filesystem(prefixes=prefixes)
        # 只 adopt 1 个 (real file), symlink 被 glob 发现但 islink 跳过
        assert adopted == 1

        # 验证 DB 里只有 1 行
        conn = sqlite3.connect(fresh_tracker.db_path)
        try:
            row_count = conn.execute("SELECT COUNT(*) FROM tracker").fetchone()[0]
        finally:
            conn.close()
        assert row_count == 1, f"应该只有 1 行 (real file), 实际 {row_count}"
        # real file 必然 tracked
        assert fresh_tracker.is_tracked(str(real_file))

    def test_bootstrap_handles_no_files_gracefully(self, fresh_tracker, tmp_path):
        """空目录 → adopted=0, 不 raise."""
        prefixes = (str(tmp_path / "fuqing_"),)
        adopted = fresh_tracker.bootstrap_from_filesystem(prefixes=prefixes)
        assert adopted == 0

    def test_bootstrap_103gb_scenario_e2e(self, fresh_tracker, tmp_path):
        """集成: 模拟 103GB 外部副本 → bootstrap → list_expired 立即拾起.

        这是 Sprint 31.1 的核心业务场景验证.
        """
        # 造 1 个 24h+1min 前的外部副本
        target = tmp_path / "fuqing_orphan_103gb.duckdb"
        target.write_bytes(b"x" * 100)  # 真生产是 103GB, 测试用 100B
        old_mtime = time.time() - (24 * 3600 + 60)
        os.utime(target, (old_mtime, old_mtime))

        prefixes = (str(tmp_path / "fuqing_"),)
        # 1. bootstrap 拾起
        assert fresh_tracker.bootstrap_from_filesystem(prefixes=prefixes) == 1

        # 2. list_expired(24) 立即能找到 (mtime > 24h)
        expired = fresh_tracker.list_expired(age_hours=24)
        assert any(r[0].endswith("fuqing_orphan_103gb.duckdb") for r in expired)

        # 3. 模拟 cleanup 删了
        target.unlink()
        fresh_tracker.remove(str(target))
        assert not fresh_tracker.is_tracked(str(target))


# ─────────────────────────────────────────────────────────────
# Concurrency
# ─────────────────────────────────────────────────────────────
class TestTrackerDBConcurrency:
    def test_concurrent_register_from_threads(self, fresh_tracker, tmp_path):
        """10 线程 × 10 个不同 path 并发 register → 全部成功, 无 raise."""
        paths = [str(tmp_path / f"fuqing_thread_{i}_{j}.duckdb") for i in range(10) for j in range(10)]
        for p in paths:
            Path(p).write_bytes(b"x" * 100)

        errors = []

        def worker(p):
            try:
                fresh_tracker.register(p, size=100, pid=os.getpid())
            except Exception as e:
                errors.append((p, e))

        threads = [threading.Thread(target=worker, args=(p,)) for p in paths]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"并发 register 不应 raise, 实际 {len(errors)} 个 error: {errors[:3]}"
        # 全部 is_tracked True
        for p in paths:
            assert fresh_tracker.is_tracked(p), f"missing {p}"


# ─────────────────────────────────────────────────────────────
# 紧急逃生舱口
# ─────────────────────────────────────────────────────────────
class TestTrackerDBDisabled:
    def test_FQ_TMP_TRACKER_DISABLED_makes_register_noop(self, tracker_db_path, monkeypatch):
        """FQ_TMP_TRACKER_DISABLED=1 → TrackerDB 不可用, 所有写 no-op."""
        from scripts.etl.common.tmp_tracker import TrackerDB
        monkeypatch.setenv("FQ_TMP_TRACKER_DISABLED", "1")
        t = TrackerDB(db_path=tracker_db_path)
        # is_available() 应是 False
        assert not t.is_available()
        # register / list_expired / is_tracked 都不报错, 但 list 空 / is_tracked False
        t.register("/tmp/foo.duckdb", 100, pid=1)
        assert t.list_expired(24) == []
        assert not t.is_tracked("/tmp/foo.duckdb")

    def test_FQ_TMP_TRACKER_DISABLED_does_not_create_db(self, tmp_path, monkeypatch):
        """FQ_TMP_TRACKER_DISABLED=1 → DB 文件不该被创建."""
        from scripts.etl.common.tmp_tracker import TrackerDB
        monkeypatch.setenv("FQ_TMP_TRACKER_DISABLED", "1")
        db_path = str(tmp_path / "should_not_exist.db")
        TrackerDB(db_path=db_path)
        # DB 文件不该存在
        assert not os.path.exists(db_path)
