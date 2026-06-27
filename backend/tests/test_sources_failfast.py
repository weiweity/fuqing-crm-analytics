"""
Tests for scripts/etl/sources.py fail-fast mechanism.

Covers:
- _check_source(): strict mode raises, lenient mode warns and returns False
- load_channel_rules(): strict raises on missing file, lenient returns ([], [])
- load_taoke_order_ids(): strict raises on missing dir, lenient returns set()
- load_live_order_ids(): strict raises on missing dir, lenient returns set()
- load_taoke_product_rules(): strict raises on missing file, lenient returns {}
"""
import pytest


# ── _check_source ──────────────────────────────────────────────────────────────

class TestCheckSource:
    def test_exists_no_error(self, tmp_path):
        from scripts.etl.sources import _check_source
        p = tmp_path / "exists.txt"
        p.write_text("data")
        assert _check_source(p) is True

    def test_missing_strict_raises(self, tmp_path):
        from scripts.etl.sources import _check_source
        missing = tmp_path / "nope.txt"
        with pytest.raises(FileNotFoundError, match="ETL 数据源缺失"):
            _check_source(missing)

    def test_missing_strict_raises_with_label(self, tmp_path):
        from scripts.etl.sources import _check_source
        missing = tmp_path / "nope.txt"
        with pytest.raises(FileNotFoundError, match="渠道判定规则"):
            _check_source(missing, label="渠道判定规则")

    def test_missing_lenient_returns_false(self, tmp_path, monkeypatch):
        from scripts.etl.sources import _check_source
        monkeypatch.setenv("FQ_ETL_LENIENT_LOAD", "1")
        missing = tmp_path / "nope.txt"
        assert _check_source(missing) is False

    def test_missing_lenient_prints_warning(self, tmp_path, monkeypatch, capsys):
        from scripts.etl.sources import _check_source
        monkeypatch.setenv("FQ_ETL_LENIENT_LOAD", "1")
        missing = tmp_path / "nope.txt"
        _check_source(missing, label="测试标签")
        captured = capsys.readouterr()
        assert "⚠️" in captured.out
        assert "测试标签" in captured.out
        assert "nope.txt" in captured.out

    def test_exists_lenient_returns_true(self, tmp_path, monkeypatch):
        from scripts.etl.sources import _check_source
        monkeypatch.setenv("FQ_ETL_LENIENT_LOAD", "1")
        p = tmp_path / "exists.txt"
        p.write_text("data")
        assert _check_source(p) is True


# ── load_channel_rules fail-fast ──────────────────────────────────────────────

class TestLoadChannelRulesFailFast:
    def test_missing_strict_raises(self, monkeypatch):
        from scripts.etl.sources import load_channel_rules
        monkeypatch.setattr(
            "scripts.etl.sources.CHANNEL_RULES_SOURCE",
            type("P", (), {"exists": lambda self: False, "__str__": lambda s: "/fake/missing.csv"})()
        )
        with pytest.raises(FileNotFoundError):
            load_channel_rules()

    def test_missing_lenient_returns_empty_lists(self, monkeypatch):
        from scripts.etl.sources import load_channel_rules
        monkeypatch.setenv("FQ_ETL_LENIENT_LOAD", "1")
        monkeypatch.setattr(
            "scripts.etl.sources.CHANNEL_RULES_SOURCE",
            type("P", (), {"exists": lambda self: False, "__str__": lambda s: "/fake/missing.csv"})()
        )
        result = load_channel_rules()
        assert result == ([], [])


# ── load_taoke_order_ids fail-fast ────────────────────────────────────────────

class TestLoadTaokeOrderIdsFailFast:
    def test_missing_strict_raises(self, monkeypatch):
        from scripts.etl import sources
        sources._TAOKE_ORDER_IDS_CACHE = None  # reset cache
        monkeypatch.setattr(
            sources, "TAOKE_DATA_SOURCE",
            type("P", (), {"exists": lambda self: False, "__str__": lambda s: "/fake/taoke_dir"})()
        )
        with pytest.raises(FileNotFoundError):
            sources.load_taoke_order_ids()

    def test_missing_lenient_returns_empty_set(self, monkeypatch):
        from scripts.etl import sources
        sources._TAOKE_ORDER_IDS_CACHE = None  # reset cache
        monkeypatch.setenv("FQ_ETL_LENIENT_LOAD", "1")
        monkeypatch.setattr(
            sources, "TAOKE_DATA_SOURCE",
            type("P", (), {"exists": lambda self: False, "__str__": lambda s: "/fake/taoke_dir"})()
        )
        result = sources.load_taoke_order_ids()
        assert result == set()


# ── load_live_order_ids fail-fast ─────────────────────────────────────────────

class TestLoadLiveOrderIdsFailFast:
    def test_missing_strict_raises(self, monkeypatch):
        from scripts.etl import sources
        sources._LIVE_ORDER_IDS_CACHE = None  # reset cache
        monkeypatch.setattr(
            sources, "LIVE_DATA_SOURCE",
            type("P", (), {"exists": lambda self: False, "__str__": lambda s: "/fake/live_dir"})()
        )
        with pytest.raises(FileNotFoundError):
            sources.load_live_order_ids()

    def test_missing_lenient_returns_empty_set(self, monkeypatch):
        from scripts.etl import sources
        sources._LIVE_ORDER_IDS_CACHE = None  # reset cache
        monkeypatch.setenv("FQ_ETL_LENIENT_LOAD", "1")
        monkeypatch.setattr(
            sources, "LIVE_DATA_SOURCE",
            type("P", (), {"exists": lambda self: False, "__str__": lambda s: "/fake/live_dir"})()
        )
        result = sources.load_live_order_ids()
        assert result == set()


# ── load_taoke_product_rules fail-fast ────────────────────────────────────────

class TestLoadTaokeProductRulesFailFast:
    def test_missing_strict_raises(self, monkeypatch):
        from scripts.etl import sources
        sources._TAOKE_PRODUCT_RULES_CACHE = None  # reset cache
        monkeypatch.setattr(
            sources, "TAOKE_PRODUCT_SOURCE",
            type("P", (), {"exists": lambda self: False, "__str__": lambda s: "/fake/taoke_product.csv"})()
        )
        with pytest.raises(FileNotFoundError):
            sources.load_taoke_product_rules()

    def test_missing_lenient_returns_empty_dict(self, monkeypatch):
        from scripts.etl import sources
        sources._TAOKE_PRODUCT_RULES_CACHE = None  # reset cache
        monkeypatch.setenv("FQ_ETL_LENIENT_LOAD", "1")
        monkeypatch.setattr(
            sources, "TAOKE_PRODUCT_SOURCE",
            type("P", (), {"exists": lambda self: False, "__str__": lambda s: "/fake/taoke_product.csv"})()
        )
        result = sources.load_taoke_product_rules()
        assert result == {}
