"""PR3 — 临时导出 / 审计日志权限与路径安全."""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestPrivateTmp:
    def test_get_private_tmp_0700(self, tmp_path, monkeypatch):
        from scripts.etl.common.private_tmp import get_private_tmp_dir

        target = tmp_path / "priv"
        monkeypatch.setenv("FQ_PRIVATE_TMP", str(target))
        d = get_private_tmp_dir(create=True)
        mode = stat.S_IMODE(d.stat().st_mode)
        assert mode == 0o700
        assert d.stat().st_uid == os.getuid()

    def test_secure_open_unpredictable_and_0600(self, tmp_path, monkeypatch):
        from scripts.etl.common.private_tmp import secure_open_path

        monkeypatch.setenv("FQ_PRIVATE_TMP", str(tmp_path / "priv"))
        p1 = secure_open_path(prefix="export-", suffix=".xlsx")
        p2 = secure_open_path(prefix="export-", suffix=".xlsx")
        assert p1 != p2
        assert p1.name != "ad-hoc-export.xlsx"
        assert "ad-hoc-export.xlsx" not in p1.name
        mode = stat.S_IMODE(p1.stat().st_mode)
        assert mode == 0o600

    def test_is_under_allowed_root(self, tmp_path, monkeypatch):
        from scripts.etl.common.private_tmp import get_private_tmp_dir, is_under_allowed_root

        monkeypatch.setenv("FQ_PRIVATE_TMP", str(tmp_path / "priv"))
        priv = get_private_tmp_dir(create=True)
        inside = priv / "a.bin"
        inside.write_text("x")
        outside = tmp_path / "out.bin"
        outside.write_text("y")
        assert is_under_allowed_root(inside, private_tmp=priv) is True
        assert is_under_allowed_root(outside, private_tmp=priv) is False
        assert is_under_allowed_root("/private/tmp/fuqing_x.duckdb", private_tmp=priv) is True


class TestRedactSensitive:
    def test_redact_bearer_and_password(self):
        from scripts.etl.common.private_tmp import redact_sensitive

        s = "Authorization: Bearer supersecrettoken123 password=hunter2"
        out = redact_sensitive(s)
        assert "supersecrettoken123" not in out
        assert "hunter2" not in out
        assert "***" in out

    def test_redact_long_sql_literal(self):
        from scripts.etl.common.private_tmp import redact_sensitive

        long_lit = "a" * 80
        sql = f"SELECT * FROM t WHERE note = '{long_lit}'"
        out = redact_sensitive(sql, max_len=500)
        assert long_lit not in out
        assert "redacted" in out


class TestReserveOutputPath:
    def test_default_not_fixed_tmp_name(self, tmp_path, monkeypatch):
        from scripts.ad_hoc_query_excel_styles import reserve_output_path

        monkeypatch.setenv("FQ_PRIVATE_TMP", str(tmp_path / "priv"))
        p = reserve_output_path(None, default_name="ad-hoc-export.xlsx")
        assert p.parent == (tmp_path / "priv").resolve() or p.parent == Path(
            str(tmp_path / "priv")
        ).resolve()
        assert p.name != "ad-hoc-export.xlsx"
        assert p.suffix == ".xlsx"
        mode = stat.S_IMODE(p.stat().st_mode)
        assert mode == 0o600

    def test_explicit_path_uses_0600(self, tmp_path):
        from scripts.ad_hoc_query_excel_styles import reserve_output_path

        out = tmp_path / "custom.xlsx"
        p = reserve_output_path(str(out))
        mode = stat.S_IMODE(p.stat().st_mode)
        assert mode == 0o600


class TestUmaskStartup:
    def test_main_module_sets_umask(self):
        """backend.main import 时应设置 umask 077 (best-effort 可读源码断言)."""
        import inspect
        import backend.main as main_mod

        src = inspect.getsource(main_mod)
        assert "umask" in src
        assert "0o077" in src or "0o77" in src
