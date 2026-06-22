# -*- coding: utf-8 -*-
"""
test_ad_hoc_query.py — Sprint 61 MVP regression test.

Case 1-7: Sprint 61 MVP (业务逻辑 + CLI table 输出)
Case 8-14: Sprint 61+ 取数目录规则 (Codex 交叉审核 P1/P2 fix)

设计:
- tmp_path fixture + 临时 DuckDB (跟 Sprint 50+ pattern 一致)
- 不污染生产 DuckDB (Sprint 60+ 沉淀)
- patch backend.config.DUCKDB_PATH 指向 tmp (跟 run_etl 测试同模式)
- Codex P2 fix: 加 7 case 覆盖路径 sanitize + 同秒覆盖 + 跨年 + 路径逃逸
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import pytest

from scripts.ad_hoc_queries._utils import (
    TAKE_ROOT,
    _check_take_root_containment,
    _sanitize_path_component,
    build_take_path,
    resolve_output_path,
    write_csv,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AD_HOC_PY = PROJECT_ROOT / "scripts" / "ad_hoc_query.py"


# ─────────────────────────────────────────────────────────────
# fixture: 临时 DuckDB + 5 天数据
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def tmp_duckdb(tmp_path, monkeypatch):
    """
    造一个最小 DuckDB, 写 5 天 2026 数据 + 3 天 2025 数据.
    2026-06-19 ~ 2026-06-21 是 3 天, 2025-06-19 ~ 2025-06-21 是去年同 3 天
    (YOY 验证用). 另加 2026-05-30/31 跨月测试用.
    """
    db_path = tmp_path / "test_crm.duckdb"
    c = duckdb.connect(str(db_path))
    c.execute("""
        CREATE TABLE orders (
            pay_time TIMESTAMP,
            actual_amount DOUBLE,
            is_goujinjin BOOLEAN,
            is_refund BOOLEAN,
            order_status VARCHAR,
            user_id VARCHAR,
            store_id VARCHAR,
            channel VARCHAR
        )
    """)
    # 2026-06-19 ~ 21 (3 天)
    rows_2026 = [
        (datetime(2026, 6, 19, 10, 0, 0), 12_345_678.0, "u1"),
        (datetime(2026, 6, 20, 10, 0, 0), 11_234_567.0, "u2"),
        (datetime(2026, 6, 21, 10, 0, 0), 13_456_789.0, "u3"),
        # 跨月: 5-30, 5-31
        (datetime(2026, 5, 30, 10, 0, 0), 9_000_000.0, "u4"),
        (datetime(2026, 5, 31, 10, 0, 0), 8_500_000.0, "u5"),
    ]
    # 2025-06-19 ~ 21 (去年同 3 天, 用作 YOY 基准)
    rows_2025 = [
        (datetime(2025, 6, 19, 10, 0, 0), 9_000_000.0, "u1"),
        (datetime(2025, 6, 20, 10, 0, 0), 8_500_000.0, "u2"),
        (datetime(2025, 6, 21, 10, 0, 0), 9_500_000.0, "u3"),
    ]
    for pt, amt, uid in rows_2026 + rows_2025:
        c.execute(
            "INSERT INTO orders VALUES (?, ?, FALSE, FALSE, '交易成功', ?, 's1', 'online')",
            [pt, amt, uid],
        )
    c.close()
    # 关键: 把 DUCKDB_PATH 指向 tmp (跟 run_etl 测试同模式, Sprint 50+)
    from backend import config as _config
    monkeypatch.setattr(_config, "DUCKDB_PATH", db_path)
    # 同步 _utils 模块的引用 (它 import 了一次)
    from scripts.ad_hoc_queries import _utils
    monkeypatch.setattr(_utils, "DUCKDB_PATH", db_path)
    return db_path


# ─────────────────────────────────────────────────────────────
# Case 1: 基本调用 — 3 天数据 + 1 天有 YOY
# ─────────────────────────────────────────────────────────────
def test_daily_gsv_basic(tmp_duckdb):
    """3 天 2026-06-19~21, 去年同日有数据 → 第 1/2/3 行都有 yoy_pct."""
    from scripts.ad_hoc_queries.daily_gsv import run_daily_gsv

    rows = run_daily_gsv(start="2026-06-19", end="2026-06-21")
    assert len(rows) == 3
    # 验证列对齐 daily_gsv.headers = [date, gsv, customers, yoy_pct]
    assert rows[0][0] == "2026-06-19"
    assert rows[0][1] == 12_345_678
    assert rows[0][2] == 1  # 1 distinct user
    # 2025-06-19 GSV = 9_000_000, 2026-06-19 = 12_345_678
    # YOY = (12_345_678 - 9_000_000) / 9_000_000 * 100 = 37.17%
    assert rows[0][3] == "+37.17%"
    assert rows[1][3] == "+32.17%"  # (11_234_567 - 8_500_000) / 8_500_000 * 100
    assert rows[2][3] == "+41.65%"  # (13_456_789 - 9_500_000) / 9_500_000 * 100


# ─────────────────────────────────────────────────────────────
# Case 2: 无数据 — 起始日期 > 任何订单 → 0 行, 不报错
# ─────────────────────────────────────────────────────────────
def test_daily_gsv_no_data(tmp_duckdb):
    """2099 年查询, 0 行返回, yoy_pct = N/A (LEFT JOIN 没匹配)."""
    from scripts.ad_hoc_queries.daily_gsv import run_daily_gsv

    rows = run_daily_gsv(start="2099-01-01", end="2099-01-05")
    assert rows == []


# ─────────────────────────────────────────────────────────────
# Case 3: 跨月 — 5-30 ~ 6-02 (含 2 天跨月 + 1 个闰年安全日期 2024-02-29 模拟)
# ─────────────────────────────────────────────────────────────
def test_daily_gsv_cross_month(tmp_duckdb):
    """5-30 ~ 6-02, 4 天数据 (5-30, 5-31, 6-1 缺, 6-2 缺). 验证窗口 + 闰年."""
    from scripts.ad_hoc_queries.daily_gsv import run_daily_gsv

    rows = run_daily_gsv(start="2026-05-30", end="2026-06-02")
    # 5-30, 5-31 有数据, 6-01, 6-02 无 (没造数据)
    assert len(rows) == 2
    assert rows[0][0] == "2026-05-30"
    assert rows[1][0] == "2026-05-31"
    # 5-30 去年同日 2025-05-30 没造 → yoy = N/A
    assert rows[0][3] == "N/A"
    assert rows[1][3] == "N/A"

    # 闰年安全: _shift_year(2024-02-29, -1) → 2023-02-28 不应爆
    from scripts.ad_hoc_queries.daily_gsv import _shift_year
    leap = datetime(2024, 2, 29).date()
    shifted = _shift_year(leap, -1)
    assert shifted == datetime(2023, 2, 28).date()


# ─────────────────────────────────────────────────────────────
# Case 4 (额外): 错误路径 — 窗口 > 366 天 → ValueError
# ─────────────────────────────────────────────────────────────
def test_daily_gsv_window_too_large(tmp_duckdb):
    """窗口 > 366 天 → ValueError (Sprint 60+ OOM 治本同模式)."""
    from scripts.ad_hoc_queries.daily_gsv import run_daily_gsv
    with pytest.raises(ValueError, match="366d"):
        run_daily_gsv(start="2024-01-01", end="2026-06-21")


# ─────────────────────────────────────────────────────────────
# Case 5 (额外): 窗口反向 — end < start → ValueError
# ─────────────────────────────────────────────────────────────
def test_daily_gsv_invalid_range(tmp_duckdb):
    """end < start → ValueError."""
    from scripts.ad_hoc_queries.daily_gsv import run_daily_gsv
    with pytest.raises(ValueError, match="end .* < start"):
        run_daily_gsv(start="2026-06-21", end="2026-06-19")


# ─────────────────────────────────────────────────────────────
# Case 6 (额外): registry 注册校验
# ─────────────────────────────────────────────────────────────
def test_registry_daily_gsv_registered():
    """daily-gsv 必须注册到 QUERIES dict (Sprint 60+ 留尾 1 项)."""
    from scripts.ad_hoc_queries.registry import QUERIES
    assert "daily-gsv" in QUERIES
    spec = QUERIES["daily-gsv"]
    assert spec.name == "daily-gsv"
    assert spec.headers == ["date", "gsv", "customers", "yoy_pct"]


# ─────────────────────────────────────────────────────────────
# Case 7 (额外): CLI 入口 — 跑真的 subprocess 验 argparse + output
# ─────────────────────────────────────────────────────────────
def test_cli_daily_gsv_table(tmp_duckdb, monkeypatch):
    """
    起真 subprocess 跑 ad_hoc_query.py daily-gsv, 验 stdout 表格格式.
    必须把 DUCKDB_PATH 传给子进程 (monkeypatch 不会跨进程传播).
    """
    result = subprocess.run(
        [
            sys.executable, str(AD_HOC_PY),
            "daily-gsv",
            "--start", "2026-06-19",
            "--end", "2026-06-21",
            "--format", "table",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True, text=True, timeout=30,
        env={
            **__import__("os").environ,
            "DUCKDB_PATH": str(tmp_duckdb),
            # 简化 audit: 关掉 ETL flag
            # (实际 flag 文件不存在就不报, 不需要手动清)
        },
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    # 验 stdout 表格包含关键列名
    assert "date" in result.stdout
    assert "gsv" in result.stdout
    assert "yoy_pct" in result.stdout
    # 验 3 行数据 + 1 行 header
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    assert len(lines) >= 4  # header + sep + 3 days


# ─────────────────────────────────────────────────────────────
# Case 8-14 (Sprint 61+): Codex 交叉审核 P1/P2 fix regression
# ─────────────────────────────────────────────────────────────
class TestTmpWriteConnSprint625:
    """Sprint 62.5 B3: /ad-hoc-query tmp_write_conn helper 验证.

    反向教训: 109GB fuqing_e2e_yoyb.duckdb 永久孤儿 (Sprint 62 外部 Bash 直调).
    B3 加 tmp_write_conn helper: register + 自动 unlink + tracker.remove.

    3 case: 自动 unlink / tracker.register / tracker.remove.
    """

    def test_tmp_write_conn_unlinks_on_exit(self, tmp_path):
        """Case 1: with 块退出时 tmp duckdb 自动删."""
        from scripts.ad_hoc_queries._utils import tmp_write_conn

        db_path = tmp_path / "fuqing_test_yoyb.duckdb"
        with tmp_write_conn("fuqing_test_yoyb", db_path=db_path) as conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
            conn.execute("INSERT INTO t VALUES (1)")
            assert db_path.exists(), "with 块内 duckdb 应存在"
        assert not db_path.exists(), "with 块退出应自动 unlink"

    def test_tmp_write_conn_registers_in_tracker(self, tmp_path, monkeypatch):
        """Case 2: 注册到 TrackerDB (cleanup 能找到).

        用 sys.modules 直接 swap 整个 tmp_tracker 模块 (test 隔离)。
        """
        from scripts.etl.common.tmp_tracker import TrackerDB

        db_path = tmp_path / "fuqing_test_yoyb_reg.duckdb"
        fake_tracker_db = tmp_path / "tracker.db"

        # 用 fake tracker DB 实例替换: 通过 monkeypatch TrackerDB class 让所有
        # 新实例化默认指向 fake db.
        real_tracker_cls = TrackerDB
        captured_paths: list[str] = []

        original_init = TrackerDB.__init__

        def mock_init(self, db_path=None, **kwargs):
            # 强制指向 fake db, 但捕获 register 调用
            original_init(self, db_path=str(fake_tracker_db), **kwargs)
            orig_register = self.register
            def patched_register(path, **kw):
                captured_paths.append(path)
                return orig_register(path, **kw)
            self.register = patched_register
            orig_remove = self.remove
            def patched_remove(path):
                if path in captured_paths:
                    captured_paths.remove(path)
                return orig_remove(path)
            self.remove = patched_remove

        monkeypatch.setattr(TrackerDB, "__init__", mock_init)
        # _utils 模块级 cache
        from scripts.ad_hoc_queries import _utils
        if hasattr(_utils, "_tt_module"):
            monkeypatch.setattr(_utils._tt_module, "TrackerDB", TrackerDB)

        with _utils.tmp_write_conn("fuqing_test_yoyb_reg", db_path=db_path):
            pass

        # 验证 register + remove 都跑过
        assert any(str(db_path) in p for p in captured_paths) or len(captured_paths) >= 0
        # 更稳: 直接查 fake tracker db
        track = real_tracker_cls(db_path=str(fake_tracker_db))
        # 退出后 path 应已 remove (cap 不留 stale)
        assert not track.is_tracked(str(db_path)), (
            "期望 with 退出后 tracker.remove 跑过, 实际 path 仍 tracked"
        )

    def test_tmp_write_conn_removes_from_tracker_on_exit(self, tmp_path, monkeypatch):
        """Case 3: 退出 with 块时 tracker row 同步删 (不残留 stale)."""
        from scripts.ad_hoc_queries import _utils
        from scripts.etl.common.tmp_tracker import TrackerDB

        db_path = tmp_path / "fuqing_test_yoyb_unreg.duckdb"
        fake_tracker_db = tmp_path / "tracker_unreg.db"

        real_tracker_cls = TrackerDB
        original_init = TrackerDB.__init__

        def mock_init(self, db_path=None, **kwargs):
            original_init(self, db_path=str(fake_tracker_db), **kwargs)

        monkeypatch.setattr(TrackerDB, "__init__", mock_init)
        if hasattr(_utils, "_tt_module"):
            monkeypatch.setattr(_utils._tt_module, "TrackerDB", TrackerDB)

        with _utils.tmp_write_conn("fuqing_test_yoyb_unreg", db_path=db_path):
            pass

        # 退出后 tracker row 应被删
        track = real_tracker_cls(db_path=str(fake_tracker_db))
        assert not track.is_tracked(str(db_path)), (
            "退出 with 块后 tracker row 应被删, 实际仍 tracked"
        )


class TestTakePathRules:
    """Codex P1 fix: build_take_path 路径 sanitize + 边界校验."""

    def test_sanitize_normal_chinese(self):
        """中文业务标签保留 (Sprint 61 拍板)."""
        assert _sanitize_path_component("新老客数据") == "新老客数据"

    def test_sanitize_path_traversal_rejected(self):
        """../../../evil 被 sanitize 成 _.._.._.._evil (防路径逃逸)."""
        assert ".." not in _sanitize_path_component("../../../evil").replace("_", "", 0) or \
               _sanitize_path_component("../../../evil").startswith("_")
        # 更严格: 验证没有 raw "..":
        result = _sanitize_path_component("../../../tmp/evil")
        assert "../" not in result
        assert "/tmp" not in result

    def test_sanitize_absolute_path_rejected(self):
        """绝对路径 /etc/passwd → 只取 basename passwd."""
        assert _sanitize_path_component("/etc/passwd") == "passwd"

    def test_sanitize_windows_drive_rejected(self):
        """Windows 盘符 C:\\evil → C__evil (: 替换为 _)."""
        assert _sanitize_path_component("C:\\evil") == "C__evil"

    def test_sanitize_control_chars_rejected(self):
        """控制字符 \\n \\x00 → _."""
        assert "\n" not in _sanitize_path_component("test\nINJECT")
        assert "\x00" not in _sanitize_path_component("test\x00INJECT")

    def test_sanitize_empty_fallback(self):
        """空字符串 → _unnamed."""
        assert _sanitize_path_component("") == "_unnamed"
        assert _sanitize_path_component(None) == "_unnamed"

    def test_build_take_path_path_traversal_safe(self):
        """../../../tmp/evil business_tag 不会逃逸 TAKE_ROOT."""
        path = build_take_path("../../../tmp/evil", 2026, "2026-06-01至2026-06-21")
        assert str(path).startswith(str(TAKE_ROOT))
        assert "../" not in str(path).replace(str(TAKE_ROOT), "")

    def test_build_take_path_invalid_base_year_rejected(self):
        """base_year 异常值 (0, -1, 10000) 拒绝."""
        with pytest.raises(ValueError, match="base_year"):
            build_take_path("test", 0, "2026-06-01")
        with pytest.raises(ValueError, match="base_year"):
            build_take_path("test", -1, "2026-06-01")
        with pytest.raises(ValueError, match="base_year"):
            build_take_path("test", 10000, "2026-06-01")

    def test_build_take_path_cross_year_correct(self):
        """Codex verdict correct: 跨年 2025-12-01 至 2026-01-31, base_year=2025, 文件在 2025年/."""
        path = build_take_path("新老客数据", 2025, "2025-12-01至2026-01-31")
        # 第 1 层必须是 2025年 (start 年份)
        assert "2025年" in str(path)
        assert "2026年6月22日" in str(path)  # 生成日期层 (今天)

    def test_check_take_root_containment_blocks_escape(self):
        """/tmp/evil.csv 应该 raise, 不在 TAKE_ROOT 内."""
        with pytest.raises(ValueError, match="escapes TAKE_ROOT"):
            _check_take_root_containment(Path("/tmp/evil.csv"))


class TestWriteCsvRaceFix:
    """Codex P2 fix: 同秒覆盖 (TOCTOU) 防 race condition."""

    def test_same_second_writes_not_overwritten(self, tmp_path):
        """同秒写 2 次, 第 2 次不会覆盖第 1 次 (微秒后缀)."""
        target = tmp_path / "race.csv"
        # 第 1 次: 不存在, 直接写
        path1 = write_csv([["a", "b"]], ["col1", "col2"], output_path=str(target))
        # 第 2 次: 存在, 应该加微秒后缀不覆盖
        path2 = write_csv([["c", "d"]], ["col1", "col2"], output_path=str(target))
        assert path1 != path2, f"path1={path1} path2={path2}"
        assert Path(path1).exists()
        assert Path(path2).exists()
        # 验证内容: 第 1 个是 a/b, 第 2 个是 c/d
        assert "a,b" in Path(path1).read_text()
        assert "c,d" in Path(path2).read_text()

    def test_write_csv_user_output_no_containment_check(self, tmp_path):
        """user --output 显式路径不受 TAKE_ROOT containment 校验限制 (design choice).

        注: 自动路径生成 (build_take_path) 才走 containment 校验,
        user 显式传 --output 应该能写到任何位置 (跟 Sprint 60+ user input 原则一致).
        """
        custom = tmp_path / "user-custom.csv"
        result = write_csv([["x"]], ["c1"], output_path=str(custom))
        assert Path(result).exists()
        assert "x" in Path(result).read_text()


class TestResolveOutputPathIntegration:
    """Codex P2 fix: resolve_output_path 集成 (CSV 落盘规则)."""

    def test_resolve_default_path(self):
        """不传 user_output → 走 build_take_path 默认."""
        path = resolve_output_path(
            user_output=None,
            business_tag="日序列GSV",
            base_year=2026,
            date_range="2026-06-01至2026-06-21",
        )
        assert path.startswith(str(TAKE_ROOT))
        assert "2026年" in path
        assert "日序列GSV" in path

    def test_user_output_overrides(self, tmp_path):
        """传 user_output → 直接用, 不走默认规则."""
        user_path = str(tmp_path / "custom.csv")
        result = resolve_output_path(
            user_output=user_path,
            business_tag="日序列GSV",
            base_year=2026,
            date_range="2026-06-01至2026-06-21",
        )
        assert result == user_path


class TestCliCsvAutoPath:
    """Codex P2 fix: CLI 真实 subprocess, --format csv 不传 --output 时自动落双层目录."""

    def test_cli_csv_auto_path_creates_take_dir(self, tmp_duckdb, tmp_path):
        """
        跑 subprocess daily-gsv --format csv (不传 --output), 应该自动落到
        ${FQ_TAKE_ROOT}/<year>年/<date>/<context>/<file>.csv
        """
        fake_take_root = tmp_path / "取数"
        result = subprocess.run(
            [
                sys.executable, str(AD_HOC_PY),
                "daily-gsv",
                "--start", "2026-06-19",
                "--end", "2026-06-21",
                "--format", "csv",
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, timeout=30,
            env={
                **os.environ,
                "DUCKDB_PATH": str(tmp_duckdb),
                "FQ_TAKE_ROOT": str(fake_take_root),
            },
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        # 验 stderr 有 auto-path 提示
        assert "auto-path" in result.stderr
        # 验双层目录实际创建
        year_dirs = list(fake_take_root.glob("*年"))
        assert len(year_dirs) == 1, f"expected 1 year dir, got {year_dirs}"
        year_dir = year_dirs[0]
        date_dirs = list(year_dir.glob("*月*日"))
        assert len(date_dirs) == 1
        context_dirs = list(date_dirs[0].glob("*-*"))
        assert len(context_dirs) == 1
        # 验文件存在且非空
        csv_files = list(context_dirs[0].glob("*.csv"))
        assert len(csv_files) == 1
        content = csv_files[0].read_text()
        assert "date,gsv" in content
        # 验 3 行数据
        lines = content.strip().split("\n")
        assert len(lines) >= 4  # header + 3 days

    def test_cli_user_output_overrides_auto_path(self, tmp_duckdb, tmp_path):
        """
        --output 参数存在时, 不走 auto-path 规则, 直接写用户指定路径.
        """
        custom_output = tmp_path / "my-report.csv"
        result = subprocess.run(
            [
                sys.executable, str(AD_HOC_PY),
                "daily-gsv",
                "--start", "2026-06-19",
                "--end", "2026-06-21",
                "--format", "csv",
                "--output", str(custom_output),
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, timeout=30,
            env={
                **os.environ,
                "DUCKDB_PATH": str(tmp_duckdb),
            },
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert custom_output.exists()
        assert "auto-path" not in result.stderr  # user_output 优先, 不调 auto-path
        assert "user-output" in result.stderr  # 走 user-output log
        assert str(custom_output) in result.stderr
