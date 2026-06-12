"""
Tests for backend.config path resolution.

Sprint 21+ housekeeping: ensure `fuqin date` (with space) → `fuqin-date` (with hyphen)
rename is regression-protected. Without these, a future PR that re-introduces
the space-in-path bug ships silently — no test would catch it.

Related: commit 7dfb02c (initial rename, 2026-06-12) + commit on
fix/fuqin-date-paths branch (completing sweep, 2026-06-13).
"""
import importlib
from pathlib import Path

import pytest


def test_default_crm_base_uses_hyphenated_dir():
    """`_DEFAULT_CRM_BASE` must contain `fuqin-date` (hyphen), not `fuqin date` (space).

    Spaces in paths break shell escaping in install scripts, plists, and
    cross-platform tooling. The 2026-06-12 → 2026-06-13 rename sweep is
    incomplete if this string still contains a space.
    """
    from backend import config

    default_str = str(config._DEFAULT_CRM_BASE)
    assert "fuqin date" not in default_str, (
        f"_DEFAULT_CRM_BASE still contains space-in-path: {default_str!r}. "
        "Rename to 'fuqin-date' (hyphen)."
    )
    assert "fuqin-date" in default_str, (
        f"_DEFAULT_CRM_BASE missing 'fuqin-date' (hyphen): {default_str!r}"
    )


def test_default_crm_base_ends_with_canonical_data_root():
    """The path must resolve to `芙清CRM数据库/芙清crm原始数据库` — the canonical data root."""
    from backend import config

    assert config._DEFAULT_CRM_BASE.name == "芙清crm原始数据库"
    assert config._DEFAULT_CRM_BASE.parent.name == "芙清CRM数据库"


def test_shop_data_source_fallback_when_env_unset(monkeypatch):
    """With `SHOP_DATA_SOURCE` env var removed, fallback to `<_DEFAULT_CRM_BASE>/店铺数据库`."""
    from backend import config
    import importlib

    monkeypatch.delenv("SHOP_DATA_SOURCE", raising=False)
    reloaded = importlib.reload(config)
    expected = reloaded._DEFAULT_CRM_BASE / "店铺数据库"
    assert reloaded.SHOP_DATA_SOURCE == expected


def test_env_override_takes_precedence(monkeypatch):
    """When `SHOP_DATA_SOURCE` env var is set, it wins over the default."""
    from backend import config
    import importlib

    monkeypatch.setenv("SHOP_DATA_SOURCE", "/tmp/test-override-path")
    reloaded = importlib.reload(config)
    assert str(reloaded.SHOP_DATA_SOURCE) == "/tmp/test-override-path"


def test_member_data_source_fallback_when_env_unset(monkeypatch):
    """Same fallback semantics for `MEMBER_DATA_SOURCE`."""
    from backend import config
    import importlib

    monkeypatch.delenv("MEMBER_DATA_SOURCE", raising=False)
    reloaded = importlib.reload(config)
    expected = reloaded._DEFAULT_CRM_BASE / "会员数据库"
    assert reloaded.MEMBER_DATA_SOURCE == expected


@pytest.mark.skipif(
    "CI" in __import__("os").environ,
    reason="Dev-only: only relevant on the macOS dev host where the data dir physically exists",
)
def test_default_crm_base_exists_on_dev_machine():
    """On the dev Mac, the default path should resolve to an existing directory.

    Skipped in CI (no Desktop). On a fresh dev box, this catches the
    disk-vs-config drift that the 8-file rename sweep verified.
    """
    from backend import config

    assert config._DEFAULT_CRM_BASE.exists(), (
        f"_DEFAULT_CRM_BASE does not exist on disk: {config._DEFAULT_CRM_BASE}. "
        "Did the parent directory rename happen on this host?"
    )
    assert config._DEFAULT_CRM_BASE.is_dir()
