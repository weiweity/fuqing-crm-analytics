"""
W6 (ETL 跑完 lark-cli 通知) — graceful degrade + 推送内容 + 多 oid 验证

设计: docs/design/etl-phase4-architecture.md §W6
"""
from pathlib import Path
from unittest import mock

import pytest

# Add project root to path
ROOT = Path(__file__).parent.parent.parent
import sys
sys.path.insert(0, str(ROOT))

from scripts.etl import notify as notify_mod  # noqa: E402


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def mock_send_lark_alert():
    """mock scraper._send_lark_alert，避免真调 lark-cli subprocess。"""
    with mock.patch.object(notify_mod, "_send_lark_alert") as m:
        m.return_value = (True, "OK")
        yield m


@pytest.fixture
def sample_stats():
    """典型 ETL 跑完 stats dict。"""
    return {
        "orders_count": 10_654_714,
        "user_rfm_count": 72_400_000,
        "wall_min": 63.2,
        "mode": "auto",
        "run_mode": "incremental",
        "gates_overall": "pass",
    }


# ============================================================
# Test cases
# ============================================================

class TestW6Notify:
    """W6 lark-cli 通知：graceful degrade + 推送内容 + 多 oid。"""

    def test_no_oids_skips_gracefully(self, monkeypatch, mock_send_lark_alert):
        """未配置 NOTIFY_OPEN_IDS → 返回 False + skip + 不调 lark-cli。"""
        monkeypatch.delenv("NOTIFY_OPEN_IDS", raising=False)

        success, reason = notify_mod.notify_etl_complete({"wall_min": 1.0})

        assert success is False
        assert "未配置 NOTIFY_OPEN_IDS" in reason
        mock_send_lark_alert.assert_not_called()

    def test_single_oid_success(self, monkeypatch, mock_send_lark_alert, sample_stats):
        """单 oid 推送成功 → 返回 True。"""
        monkeypatch.setenv("NOTIFY_OPEN_IDS", "ou_test123456789")

        success, reason = notify_mod.notify_etl_complete(sample_stats, status="success")

        assert success is True
        assert "1/1 推送成功" in reason
        # 验证 _send_lark_alert 收到正确 msg
        mock_send_lark_alert.assert_called_once()
        call_args = mock_send_lark_alert.call_args
        msg = call_args[0][0]  # 第 1 个 positional arg
        oid = call_args.kwargs.get("open_id") or call_args[1].get("open_id")
        assert oid == "ou_test123456789"
        # msg 内容校验
        assert "✅ ETL 跑完" in msg
        assert "orders: 10654714" in msg
        assert "user_rfm: 72400000" in msg
        assert "wall time: 63.2min" in msg
        assert "mode: auto / incremental" in msg
        assert "6 道门禁: pass" in msg

    def test_multiple_oids_all_success(self, monkeypatch, mock_send_lark_alert, sample_stats):
        """多 oid 全部成功 → 返回 True + 'N/N 推送成功'。"""
        monkeypatch.setenv("NOTIFY_OPEN_IDS", "ou_boss123,ou_op456,ou_eng789")

        success, reason = notify_mod.notify_etl_complete(sample_stats)

        assert success is True
        assert "3/3 推送成功" in reason
        assert mock_send_lark_alert.call_count == 3

    def test_partial_failure(self, monkeypatch, sample_stats):
        """部分 oid 失败 → 返回 False + 'N/M 推送成功'。"""
        monkeypatch.setenv("NOTIFY_OPEN_IDS", "ou_ok1,ou_fail,ou_ok2")

        with mock.patch.object(notify_mod, "_send_lark_alert") as m:
            m.side_effect = [
                (True, "OK"),
                (False, "lark-cli 拒绝: invalid_user"),
                (True, "OK"),
            ]

            success, reason = notify_mod.notify_etl_complete(sample_stats)

        assert success is False
        assert "2/3 推送成功" in reason
        assert m.call_count == 3

    def test_status_failed_uses_error_emoji(self, monkeypatch, mock_send_lark_alert, sample_stats):
        """status='failed' → 消息含 ❌ 和 'ETL 失败'。"""
        monkeypatch.setenv("NOTIFY_OPEN_IDS", "ou_test123")

        notify_mod.notify_etl_complete(sample_stats, status="failed")

        msg = mock_send_lark_alert.call_args[0][0]
        assert "❌ ETL 失败" in msg
        assert "✅" not in msg

    def test_missing_stats_keys_uses_question_mark(self, monkeypatch, mock_send_lark_alert):
        """stats 缺字段 → 消息用 '?' 占位（不抛 KeyError）。"""
        monkeypatch.setenv("NOTIFY_OPEN_IDS", "ou_test123")

        # 缺 wall_min, gates_overall
        notify_mod.notify_etl_complete({"orders_count": 100})

        msg = mock_send_lark_alert.call_args[0][0]
        assert "orders: 100" in msg
        assert "wall time: ?min" in msg
        assert "6 道门禁: ?" in msg

    def test_oids_env_with_whitespace(self, monkeypatch, mock_send_lark_alert, sample_stats):
        """NOTIFY_OPEN_IDS 含空格 → trim 后推送。"""
        monkeypatch.setenv("NOTIFY_OPEN_IDS", " ou_a , ou_b ,  ou_c  ")

        success, reason = notify_mod.notify_etl_complete(sample_stats)

        assert success is True
        assert "3/3 推送成功" in reason
        # 验证三个 oid 被 trim 后传入
        called_oids = [c.kwargs.get("open_id") for c in mock_send_lark_alert.call_args_list]
        assert called_oids == ["ou_a", "ou_b", "ou_c"]

    def test_empty_oids_string_after_split(self, monkeypatch, mock_send_lark_alert):
        """NOTIFY_OPEN_IDS 全是分隔符 (",,, ") → 0 oids → skip。"""
        monkeypatch.setenv("NOTIFY_OPEN_IDS", "  ,  ,  ")

        success, reason = notify_mod.notify_etl_complete({"wall_min": 1.0})

        assert success is False
        assert "未配置 NOTIFY_OPEN_IDS" in reason
        mock_send_lark_alert.assert_not_called()

    def test_send_lark_alert_unavailable(self, monkeypatch, mock_send_lark_alert, sample_stats):
        """scraper._send_lark_alert 不可用 (ImportError) → 返回 False + 不抛异常。"""
        monkeypatch.setattr(notify_mod, "_send_lark_alert", None)
        monkeypatch.setenv("NOTIFY_OPEN_IDS", "ou_test123")

        success, reason = notify_mod.notify_etl_complete(sample_stats)

        assert success is False
        assert "不可用" in reason
