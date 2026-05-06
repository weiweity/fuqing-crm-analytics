"""
Tests for backend/semantic/channels.py - channel definitions and mappings.

Covers:
- CHANNEL_FUNNEL: 9-layer funnel definitions
- DB_TO_UI / UI_TO_DB: bidirectional mapping
- CHANNEL_ORDER: display order
- ACTIVE_CHANNELS / ACTIVE_UI_CHANNELS: active channel lists
- get_channel_def: channel lookup
"""
import pytest
from backend.semantic.channels import (
    CHANNEL_FUNNEL,
    CHANNEL_PRIORITY,
    DB_TO_UI,
    UI_TO_DB,
    CHANNEL_ORDER,
    ACTIVE_CHANNELS,
    ACTIVE_UI_CHANNELS,
    get_channel_def,
)


class TestChannelFunnel:
    """Test channel funnel definitions."""

    def test_funnel_has_9_layers(self):
        """9-layer funnel: P1-P9 (P4 has 达播+微博)."""
        assert len(CHANNEL_FUNNEL) == 10  # 10 entries (9 layers, P4 has 2)

    def test_funnel_keys_unique(self):
        keys = [c.key for c in CHANNEL_FUNNEL]
        assert len(keys) == len(set(keys))

    def test_no_shopping_gold_in_active(self):
        """购物金 should be excluded from active channels."""
        assert "购物金" not in ACTIVE_CHANNELS

    def test_active_channels_count(self):
        """Active channels = all minus 购物金 = 9."""
        assert len(ACTIVE_CHANNELS) == 9

    def test_priority_ordering(self):
        """Priorities should be 1-9."""
        priorities = sorted(CHANNEL_PRIORITY.values())
        assert priorities == [1, 2, 3, 4, 4, 5, 6, 7, 8, 9]


class TestChannelMapping:
    """Test DB <-> UI channel name mapping."""

    def test_db_to_ui_roundtrip(self):
        """DB -> UI -> DB should preserve channel names."""
        for db_name in DB_TO_UI:
            ui_name = DB_TO_UI[db_name]
            assert UI_TO_DB[ui_name] == db_name

    def test_ui_to_db_roundtrip(self):
        """UI -> DB -> UI should preserve channel names."""
        for ui_name in UI_TO_DB:
            db_name = UI_TO_DB[ui_name]
            assert DB_TO_UI[db_name] == ui_name

    def test_special_mapping_gift_channel(self):
        """赠品&0.01 (UI) <=> 赠品&0.01渠道 (DB)."""
        assert DB_TO_UI["赠品&0.01渠道"] == "赠品&0.01"
        assert UI_TO_DB["赠品&0.01"] == "赠品&0.01渠道"

    def test_u_xian_mapping(self):
        """U先派样: DB and UI use the same name (大写U)."""
        assert DB_TO_UI["U先派样"] == "U先派样"

    def test_channel_order_count(self):
        """CHANNEL_ORDER should list all active UI channels."""
        assert len(CHANNEL_ORDER) == len(ACTIVE_UI_CHANNELS)


class TestGetChannelDef:
    """Test channel definition lookup."""

    def test_known_channel(self):
        ch = get_channel_def("直播")
        assert ch.name == "直播"
        assert ch.priority == 5

    def test_unknown_channel_fallback(self):
        ch = get_channel_def("不存在的渠道")
        assert ch.priority == 99
        assert ch.key == "不存在的渠道"
