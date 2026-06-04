# -*- coding: utf-8 -*-
"""sanity_check.py 单元测试

覆盖：
  - 6 道门禁各自的 happy / sad path
  - run_all 统一入口的失败汇总 + likely-wrong flag
  - 飞书 webhook 调用（mock urlopen）+ env var fallback + graceful degrade
  - 18 行 likely-wrong 复现场景：构造 1 个复制日数据点应该被标 likely-wrong
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 把 scraper/core/ 加入 sys.path（独立 import sanity_check 模块）
SCRAPER_CORE = Path(__file__).resolve().parent.parent / "scraper" / "core"
sys.path.insert(0, str(SCRAPER_CORE))

import sanity_check  # noqa: E402


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def good_data():
    """通过所有门禁的健康数据"""
    return {
        "item_id": "587051744204",
        "date": "2026/05/22",
        "zichan_zongliang": 1_800_000,
        "qian_zhongcao": 200_000,
        "shen_zhongcao": 150_000,
        "shougou": 50_000,
        "fugou": 30_000,
        "liandai": 10_000,
    }


@pytest.fixture
def csv_with_prev_day(tmp_path, good_data):
    """构造一个 CSV，含 good_data['item_id'] 前一天的数据 (5/21)"""
    csv_file = tmp_path / "data3.csv"
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "ID", "时间", "资产总量", "浅种草", "深种草",
                "首购资产", "复购资产", "连带资产", "data_quality_flag",
            ],
        )
        writer.writeheader()
        # 前一日 5/21 数据：资产 1,800,000（与 good_data 几乎一致 → 平滑）
        writer.writerow({
            "ID": good_data["item_id"],
            "时间": "2026/05/21",
            "资产总量": "1,800,000",  # 含逗号格式（CSV 真实场景）
            "浅种草": "200000",
            "深种草": "150000",
            "首购资产": "50000",
            "复购资产": "30000",
            "连带资产": "10000",
            "data_quality_flag": "verified",
        })
    return str(csv_file)


# ============================================================
# 门禁 1: date_sanity
# ============================================================

class TestCheckDateSanity:
    def test_match_dash_format(self):
        ok, _ = sanity_check.check_date_sanity("2026-05-20", "2026-05-20")
        assert ok is True

    def test_match_slash_format(self):
        ok, _ = sanity_check.check_date_sanity("2026/05/20", "2026/05/20")
        assert ok is True

    def test_cross_format_dash_vs_slash(self):
        # SPA 返回 slash，target 是 dash → 应识别
        ok, _ = sanity_check.check_date_sanity("trigger: 2026/05/20", "2026-05-20")
        assert ok is True

    def test_mismatch(self):
        ok, reason = sanity_check.check_date_sanity("2026-05-31", "2026-05-20")
        assert ok is False
        assert "≠" in reason

    def test_spa_empty(self):
        ok, reason = sanity_check.check_date_sanity("", "2026-05-20")
        assert ok is False
        assert "未返回" in reason

    def test_target_empty_skips(self):
        # 没有 target → 跳过，认为 OK
        ok, _ = sanity_check.check_date_sanity("2026-05-20", "")
        assert ok is True


# ============================================================
# 门禁 2: item_data_validity
# ============================================================

class TestCheckItemDataValidity:
    def test_good_data(self, good_data):
        ok, _ = sanity_check.check_item_data_validity(good_data)
        assert ok is True

    def test_none(self):
        ok, reason = sanity_check.check_item_data_validity(None)
        assert ok is False
        assert "数据为空" in reason

    def test_zero_total(self, good_data):
        good_data["zichan_zongliang"] = 0
        ok, reason = sanity_check.check_item_data_validity(good_data)
        assert ok is False
        assert "为 0" in reason

    def test_total_lt_shougou(self, good_data):
        good_data["zichan_zongliang"] = 100
        good_data["shougou"] = 200
        ok, reason = sanity_check.check_item_data_validity(good_data)
        assert ok is False
        assert "< 首购" in reason

    def test_zhongcao_overflow(self, good_data):
        good_data["zichan_zongliang"] = 100_000
        good_data["qian_zhongcao"] = 100_000
        good_data["shen_zhongcao"] = 100_000
        ok, reason = sanity_check.check_item_data_validity(good_data)
        assert ok is False
        assert "种草" in reason


# ============================================================
# 门禁 3: cross_day
# ============================================================

class TestCheckCrossDay:
    def test_no_prev_data_skips(self, good_data, tmp_path):
        empty_csv = tmp_path / "empty.csv"
        empty_csv.write_text(
            "ID,时间,资产总量,浅种草,深种草,首购资产,复购资产,连带资产,data_quality_flag\n",
            encoding="utf-8",
        )
        ok, _ = sanity_check.check_cross_day(str(empty_csv), good_data)
        assert ok is True

    def test_smooth_change_passes(self, good_data, csv_with_prev_day):
        # good_data 1.8M vs prev 1.8M → 0% 变化，应该过
        ok, _ = sanity_check.check_cross_day(csv_with_prev_day, good_data)
        assert ok is True

    def test_collapse_50pct_rejected(self, good_data, csv_with_prev_day):
        # 跌到 800k（从 1.8M）= -55% → 应拒绝
        good_data["zichan_zongliang"] = 800_000
        ok, reason = sanity_check.check_cross_day(csv_with_prev_day, good_data)
        assert ok is False
        assert "降" in reason

    def test_spike_100pct_rejected(self, good_data, csv_with_prev_day):
        # 涨到 4M（从 1.8M）= +122% → 应拒绝
        good_data["zichan_zongliang"] = 4_000_000
        ok, reason = sanity_check.check_cross_day(csv_with_prev_day, good_data)
        assert ok is False
        assert "升" in reason

    def test_zero_total_rejected(self, good_data, csv_with_prev_day):
        good_data["zichan_zongliang"] = 0
        ok, reason = sanity_check.check_cross_day(csv_with_prev_day, good_data)
        assert ok is False
        assert "T+1" in reason

    def test_csv_file_none_skips(self, good_data):
        ok, _ = sanity_check.check_cross_day(None, good_data)
        assert ok is True


# ============================================================
# 门禁 4: api_health
# ============================================================

class TestCheckApiHealth:
    def test_good(self, good_data):
        ok, _ = sanity_check.check_api_health(good_data)
        assert ok is True

    def test_all_zero(self):
        data = {"zichan_zongliang": 0, "qian_zhongcao": 0, "shen_zhongcao": 0,
                "shougou": 0, "fugou": 0, "liandai": 0}
        ok, reason = sanity_check.check_api_health(data)
        assert ok is False
        assert "全 0" in reason

    def test_sub_sum_overflow(self):
        # 子字段和 > 总资产*1.5 → 拒绝
        data = {"zichan_zongliang": 100, "qian_zhongcao": 100, "shen_zhongcao": 100,
                "shougou": 100, "fugou": 100, "liandai": 100}
        ok, reason = sanity_check.check_api_health(data)
        assert ok is False
        assert "子字段和" in reason

    def test_none(self):
        ok, _ = sanity_check.check_api_health(None)
        assert ok is False


# ============================================================
# 门禁 5: business_smoothness
# ============================================================

class TestCheckBusinessSmoothness:
    def test_smooth_passes(self, good_data, csv_with_prev_day):
        ok, _ = sanity_check.check_business_smoothness(csv_with_prev_day, good_data)
        assert ok is True

    def test_31pct_drop_warns(self, good_data, csv_with_prev_day):
        good_data["zichan_zongliang"] = int(1_800_000 * 0.69)  # -31% （触发 30% 阈值）
        ok, reason = sanity_check.check_business_smoothness(csv_with_prev_day, good_data)
        assert ok is False
        assert "下跌" in reason

    def test_31pct_jump_warns(self, good_data, csv_with_prev_day):
        good_data["zichan_zongliang"] = int(1_800_000 * 1.35)  # +35%
        ok, reason = sanity_check.check_business_smoothness(csv_with_prev_day, good_data)
        assert ok is False
        assert "上涨" in reason

    def test_no_prev_skips(self, good_data, tmp_path):
        empty_csv = tmp_path / "empty.csv"
        empty_csv.write_text("ID,时间,资产总量\n", encoding="utf-8")
        ok, _ = sanity_check.check_business_smoothness(str(empty_csv), good_data)
        assert ok is True


# ============================================================
# 门禁 6: copy_day（最关键 — 18 行 likely-wrong 的主因）
# ============================================================

class TestCheckCopyDay:
    def test_not_copy(self, good_data, csv_with_prev_day):
        # good_data 资产 1.8M vs prev 1.8M（但子字段相同）
        # good_data 浅种草 200k = prev 200k → 复制风险
        # 实际上 good_data 和 prev 6 字段全相同 → 触发复制日
        ok, reason = sanity_check.check_copy_day(csv_with_prev_day, good_data)
        # good_data 完全等于 prev → 是复制日
        assert ok is False
        assert "完全相同" in reason

    def test_one_field_differs(self, good_data, csv_with_prev_day):
        # 改一个字段 → 不是复制日
        good_data["fugou"] = 99_999
        ok, _ = sanity_check.check_copy_day(csv_with_prev_day, good_data)
        assert ok is True

    def test_no_prev_skips(self, good_data, tmp_path):
        empty_csv = tmp_path / "empty.csv"
        empty_csv.write_text("ID,时间,资产总量\n", encoding="utf-8")
        ok, _ = sanity_check.check_copy_day(str(empty_csv), good_data)
        assert ok is True


# ============================================================
# lark-cli 告警（替代原飞书 webhook）
# ============================================================

class TestLarkCliAlert:
    """Mock subprocess.run 模拟 lark-cli 输出。"""

    def test_skip_when_no_open_id(self, monkeypatch):
        monkeypatch.delenv("LARK_OPEN_ID", raising=False)
        sent, reason = sanity_check._send_lark_alert("test message")
        assert sent is False
        assert "未配置" in reason

    def test_skip_when_open_id_blank(self, monkeypatch):
        monkeypatch.setenv("LARK_OPEN_ID", "   ")
        sent, reason = sanity_check._send_lark_alert("test message")
        assert sent is False
        assert "未配置" in reason

    def test_success_call(self, monkeypatch):
        monkeypatch.setenv("LARK_OPEN_ID", "ou_test")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({
            "ok": True, "identity": "bot",
            "data": {"chat_id": "oc_xxx", "message_id": "om_xxx"},
        })
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            sent, reason = sanity_check._send_lark_alert("hello lark")
            assert sent is True
            assert reason == "OK"
            # 验证 subprocess.run 调用确实发生 + 参数正确
            assert mock_run.call_count == 1
            args = mock_run.call_args[0][0]
            assert args[0] == "/Users/hutou/homebrew/bin/lark-cli"
            assert args[1:3] == ["im", "+messages-send"]
            assert "--user-id" in args
            assert "ou_test" in args
            assert "--text" in args
            assert "hello lark" in args
            assert "--as" in args
            assert "bot" in args

    def test_lark_cli_rejected_ok_false(self, monkeypatch):
        monkeypatch.setenv("LARK_OPEN_ID", "ou_test")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({
            "ok": False, "identity": "bot",
            "error": {"type": "validation", "message": "user not found"},
        })
        with patch("subprocess.run", return_value=mock_proc):
            sent, reason = sanity_check._send_lark_alert("x")
        assert sent is False
        assert "lark-cli 拒绝" in reason
        assert "user not found" in reason

    def test_lark_cli_nonzero_exit(self, monkeypatch):
        monkeypatch.setenv("LARK_OPEN_ID", "ou_test")
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "ERROR: not logged in"
        with patch("subprocess.run", return_value=mock_proc):
            sent, reason = sanity_check._send_lark_alert("x")
        assert sent is False
        assert "exit=1" in reason
        assert "not logged in" in reason

    def test_subprocess_timeout(self, monkeypatch):
        monkeypatch.setenv("LARK_OPEN_ID", "ou_test")
        with patch("subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="lark-cli", timeout=5)):
            sent, reason = sanity_check._send_lark_alert("x")
        assert sent is False
        assert "超时" in reason

    def test_lark_bin_not_found(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LARK_OPEN_ID", "ou_test")
        monkeypatch.setenv("LARK_BIN", "/nonexistent/lark-cli")
        sent, reason = sanity_check._send_lark_alert("x")
        assert sent is False
        assert "二进制不存在" in reason

    def test_arbitrary_exception_graceful(self, monkeypatch):
        monkeypatch.setenv("LARK_OPEN_ID", "ou_test")
        with patch("subprocess.run", side_effect=RuntimeError("boom")):
            sent, reason = sanity_check._send_lark_alert("x")
        # graceful degrade：不应抛异常，只返回 False
        assert sent is False
        assert "RuntimeError" in reason

    def test_non_json_stdout_treated_as_success(self, monkeypatch):
        """lark-cli 偶尔返回非 JSON stdout（如警告）应视为成功（不阻断主流程）"""
        monkeypatch.setenv("LARK_OPEN_ID", "ou_test")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Warning: deprecated flag\n"
        with patch("subprocess.run", return_value=mock_proc):
            sent, reason = sanity_check._send_lark_alert("x")
        assert sent is True
        assert "non-JSON" in reason


# ============================================================
# run_all 统一入口
# ============================================================

class TestRunAll:
    def test_all_pass_no_alert(self, tmp_path, monkeypatch):
        """所有门禁通过 → 不告警，不标 likely-wrong"""
        monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text(
            "ID,时间,资产总量\n", encoding="utf-8"
        )
        data = {
            "item_id": "999",
            "date": "2026/05/22",
            "zichan_zongliang": 1_000_000,
            "qian_zhongcao": 100_000,
            "shen_zhongcao": 100_000,
            "shougou": 50_000,
            "fugou": 30_000,
            "liandai": 10_000,
        }
        result = sanity_check.run_all(
            data=data,
            csv_file=str(csv_file),
            spa_date="2026-05-22",
            target_date="2026-05-22",
        )
        assert result["overall_ok"] is True
        assert result["should_flag_likely_wrong"] is False
        assert result["failed_gates"] == []
        assert result["alert"]["sent"] is False

    def test_copy_day_triggers_likely_wrong(self, good_data, csv_with_prev_day,
                                           monkeypatch):
        """复现 18 行 likely-wrong 场景：6 字段与前一日完全相同 → 标 likely-wrong"""
        monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
        # good_data 与 csv_with_prev_day 前一日 6 字段完全相同 → copy_day 触发
        result = sanity_check.run_all(
            data=good_data,
            csv_file=csv_with_prev_day,
            spa_date="2026/05/22",
            target_date="2026/05/22",
        )
        assert result["should_flag_likely_wrong"] is True
        assert "copy_day" in dict(result["failed_gates"])

    def test_lark_alert_called_on_failure(self, good_data, csv_with_prev_day,
                                       monkeypatch):
        """门禁失败时确实调 lark-cli（mock subprocess.run）"""
        monkeypatch.setenv("LARK_OPEN_ID", "ou_test")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({"ok": True, "identity": "bot", "data": {}})
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            result = sanity_check.run_all(
                data=good_data,
                csv_file=csv_with_prev_day,
                spa_date="2026/05/22",
                target_date="2026/05/22",
            )
        assert result["alert"]["sent"] is True
        assert mock_run.call_count == 1
        # 告警消息正文应包含商品 ID、日期、失败门禁名
        args = mock_run.call_args[0][0]
        text = args[args.index("--text") + 1]
        assert good_data["item_id"] in text
        assert "copy_day" in text
        assert "DMP Sanity Alert" in text  # 告警关键词（lark 消息前缀）

    def test_lark_alert_skip_no_alert_when_pass(self, monkeypatch, tmp_path):
        """全过时 lark-cli 不调（即使 env 配了）"""
        monkeypatch.setenv("LARK_OPEN_ID", "ou_test")
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("ID,时间,资产总量\n", encoding="utf-8")
        data = {
            "item_id": "1", "date": "2026/05/22",
            "zichan_zongliang": 1_000_000,
            "qian_zhongcao": 100_000, "shen_zhongcao": 100_000,
            "shougou": 50_000, "fugou": 30_000, "liandai": 10_000,
        }
        with patch("subprocess.run") as mock_run:
            sanity_check.run_all(data=data, csv_file=str(csv_file),
                                 spa_date="2026-05-22", target_date="2026-05-22")
        assert mock_run.call_count == 0

    def test_multiple_gate_failures(self, good_data, csv_with_prev_day, monkeypatch):
        """同时违反多条门禁 → failed_gates 应聚合"""
        monkeypatch.delenv("LARK_OPEN_ID", raising=False)
        # 篡改数据：date_sanity 不一致 + 全 0（触发 api_health "全 0"）
        for k in ("zichan_zongliang", "qian_zhongcao", "shen_zhongcao",
                  "shougou", "fugou", "liandai"):
            good_data[k] = 0
        result = sanity_check.run_all(
            data=good_data,
            csv_file=csv_with_prev_day,
            spa_date="2026/05/31",  # 与 target 不一致
            target_date="2026/05/22",
        )
        failed_names = [n for n, _ in result["failed_gates"]]
        assert "date_sanity" in failed_names
        assert "item_data_validity" in failed_names
        assert "api_health" in failed_names
        assert result["should_flag_likely_wrong"] is True

    def test_18_rows_likely_wrong_scenario(self, tmp_path, monkeypatch):
        """复现 5/28 那 18 行 likely-wrong：构造 1 个数据点应该被标 likely-wrong

        场景：5/27 数据 6 字段全等于 5/26（T+1 未生成，API 返回旧快照）
        → 复制日门禁触发 → should_flag_likely_wrong=True
        """
        monkeypatch.delenv("LARK_OPEN_ID", raising=False)
        csv_file = tmp_path / "data3.csv"
        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "ID", "时间", "资产总量", "浅种草", "深种草",
                    "首购资产", "复购资产", "连带资产", "data_quality_flag",
                ],
            )
            writer.writeheader()
            # 5/26 真实数据
            writer.writerow({
                "ID": "587051744204",  # 凉茶次抛
                "时间": "2026/05/26",
                "资产总量": "1843973",
                "浅种草": "250000",
                "深种草": "180000",
                "首购资产": "60000",
                "复购资产": "40000",
                "连带资产": "15000",
                "data_quality_flag": "verified",
            })

        # 5/27 数据：6 字段全等于 5/26（模拟 T+1 未生成）
        suspect_data = {
            "item_id": "587051744204",
            "date": "2026/05/27",
            "zichan_zongliang": 1843973,
            "qian_zhongcao": 250000,
            "shen_zhongcao": 180000,
            "shougou": 60000,
            "fugou": 40000,
            "liandai": 15000,
        }
        result = sanity_check.run_all(
            data=suspect_data,
            csv_file=str(csv_file),
            spa_date="2026/05/27",
            target_date="2026/05/27",
        )
        # 必须被标 likely-wrong（修复 5/28 那场漏报）
        assert result["should_flag_likely_wrong"] is True
        # 应至少由 copy_day 门禁触发
        failed = dict(result["failed_gates"])
        assert "copy_day" in failed
        assert "完全相同" in failed["copy_day"]


# ============================================================
# 辅助函数
# ============================================================

class TestHelpers:
    def test_strip_int_comma_format(self):
        assert sanity_check._strip_int("1,800,000") == 1_800_000

    def test_strip_int_quoted(self):
        assert sanity_check._strip_int('"1,234"') == 1_234

    def test_strip_int_blank(self):
        assert sanity_check._strip_int("") == 0
        assert sanity_check._strip_int(None) == 0

    def test_strip_int_invalid(self):
        assert sanity_check._strip_int("abc") == 0

    def test_parse_date_slash(self):
        d = sanity_check._parse_date("2026/05/20")
        assert d is not None and d.year == 2026 and d.month == 5 and d.day == 20

    def test_parse_date_dash(self):
        d = sanity_check._parse_date("2026-05-20")
        assert d is not None and d.year == 2026

    def test_parse_date_invalid(self):
        assert sanity_check._parse_date("bad date") is None
        assert sanity_check._parse_date("") is None
