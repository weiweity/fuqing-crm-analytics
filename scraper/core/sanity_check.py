#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DMP 抓数 6 道门禁 + lark-cli 告警 (独立模块)

背景：5/28 出现 18 行 likely-wrong 脏数据时**没有主动告警**，要靠运营自己发现。
本模块把 MEMO_2026-06-02.md / MEMO_2026-06-01.md 识别的 6 道门禁集中到独立
可 import 的模块，并集成 lark-cli 告警（私聊推送）。

6 道门禁（与现有 dmp_item_insight_scraper.py 内嵌实现一致）：
    1. date_sanity          - SPA 实际显示日期 vs 目标日期
    2. item_data_validity   - 单品数据合理性（字段范围 / 全 0）
    3. cross_day            - 跨日期校验（环比涨跌幅 >50%/<200% 拒绝）
    4. api_health           - API 健康（子字段和 vs 总资产，全 0 拒绝）
    5. business_smoothness  - 业务平滑（环比 > 30% 告警）
    6. copy_day             - 复制日（6 字段与前一日完全相同 → likely-wrong）

每个门禁是独立函数：(args) -> (ok: bool, reason: str)
统一入口：run_all(data, csv_file, spa_date, target_date) -> result dict

调用方（如 dmp_master.py）：
    result = sanity_check.run_all(data, csv_file=Config.ITEM_DATA_FILE, ...)
    if result['should_flag_likely_wrong']:
        data['_sanity'] = 'likely-wrong'  # append_tocsv 会落到 data_quality_flag
    # lark-cli 告警已在 run_all 内自动触发

环境变量：
    LARK_OPEN_ID         - 收件人 user open_id（未设时 skip 告警，不报错）
    LARK_BIN            - lark-cli 路径（默认 /Users/hutou/homebrew/bin/lark-cli）
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from typing import Any


# ============================================================
# lark-cli 告警（graceful degrade：失败不抛异常，不影响主流程）
# ============================================================

def _send_lark_alert(content: str, open_id: str | None = None,
                     lark_bin: str | None = None,
                     timeout: float = 5.0) -> tuple[bool, str]:
    """推 lark-cli 私聊告警。

    通过 lark-cli subprocess 调 `im +messages-send --user-id --text` 发消息。
    走 bot 身份（appsecret_cli_xxx 已在 keychain），无需用户交互。
    默认 0 限频：同 1 门禁在 1 日内可能触发多次（如需要去重由调用方做）。

    Args:
        content: 文本内容
        open_id: 收件人 user open_id（不传走 env LARK_OPEN_ID）
        lark_bin: lark-cli 路径（不传走 env LARK_BIN，默认 /Users/hutou/homebrew/bin/lark-cli）
        timeout: subprocess 超时秒

    Returns:
        (sent: bool, reason: str)
        - sent=True 表示 subprocess 成功 + lark-cli 响应 ok=true
        - sent=False 时 reason 说明为何 skip / 失败（never raises）
    """
    oid = (open_id or os.environ.get("LARK_OPEN_ID", "")).strip()
    if not oid:
        return False, "未配置 LARK_OPEN_ID，跳过告警（不报错）"

    bin_path = (
        lark_bin
        or os.environ.get("LARK_BIN", "").strip()
        or shutil.which("lark-cli")
        or "/Users/hutou/homebrew/bin/lark-cli"
    )
    if not os.path.exists(bin_path):
        return False, f"lark-cli 二进制不存在: {bin_path}"

    try:
        proc = subprocess.run(
            [
                bin_path, "im", "+messages-send",
                "--user-id", oid,
                "--text", content,
                "--as", "bot",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"lark-cli 超时（>{timeout}s）"
    except Exception as e:
        return False, f"lark-cli 启动失败: {type(e).__name__}: {str(e)[:200]}"

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()[:200]
        return False, f"lark-cli exit={proc.returncode}: {stderr}"

    # lark-cli 成功响应：{"ok": true, "identity": "bot", "data": {...}}
    try:
        resp = json.loads(proc.stdout)
    except (ValueError, TypeError):
        return True, "OK (non-JSON stdout)"

    if resp.get("ok") is True:
        return True, "OK"
    err = resp.get("error", {})
    return False, f"lark-cli 拒绝: {err.get('type','?')}: {err.get('message','')[:200]}"


# ============================================================
# 辅助函数
# ============================================================

def _strip_int(value: Any) -> int:
    """CSV 单元格 → int（去除逗号 / 引号 / 空白）。"""
    if value is None:
        return 0
    s = str(value).replace('"', "").replace(",", "").strip()
    if not s:
        return 0
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def _read_prev_row(csv_file: str | None, item_id: str,
                   prev_date_str: str) -> dict | None:
    """读 CSV 中 (item_id, prev_date_str) 对应的行（首条匹配）。"""
    if not csv_file or not os.path.exists(csv_file):
        return None
    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("ID", "") == str(item_id) and row.get("时间", "") == prev_date_str:
                    return row
    except Exception:
        return None
    return None


def _parse_date(date_str: str) -> datetime | None:
    """解析 'YYYY/MM/DD' 或 'YYYY-MM-DD'。失败返回 None。"""
    if not date_str:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


# ============================================================
# 门禁 1: date_sanity — SPA 实际显示日期 vs 目标日期
# ============================================================

def check_date_sanity(spa_date: str | None, target_date: str | None) -> tuple[bool, str]:
    """SPA 当前 trigger 显示日期 vs 抓取目标日期。

    SPA bug 表现（5/27 = 5/26 复制根因之一）：
      - date picker 没选中目标日 → API 仍返回"今天"快照
      - 修复 = 抓完后读 trigger，对比目标日；不一致 → return None 触发重试

    Args:
        spa_date: SPA 当前 trigger 显示的日期字符串
        target_date: 抓取目标日期字符串

    都允许 'YYYY-MM-DD' 或 'YYYY/MM/DD' 任一格式。
    """
    if not target_date:
        return True, "OK (无 target_date，跳过校验)"
    if not spa_date:
        return False, f"SPA 未返回 trigger 日期（目标 {target_date}）"

    # 同时尝试两种格式比对
    candidates = {
        target_date,
        target_date.replace("-", "/"),
        target_date.replace("/", "-"),
    }
    for c in candidates:
        if c in spa_date:
            return True, "OK"
    return False, f"SPA 日期 ({spa_date}) ≠ 目标日期 ({target_date})"


# ============================================================
# 门禁 2: item_data_validity — 单品数据合理性
# ============================================================

def check_item_data_validity(data: dict | None) -> tuple[bool, str]:
    """单品数据字段合理性校验。

    复刻 dmp_item_insight_scraper.validate_item_data (line 1968-2001)。
    """
    if not data:
        return False, "数据为空"
    total = int(data.get("zichan_zongliang", 0) or 0)
    shougou = int(data.get("shougou", 0) or 0)
    qian = int(data.get("qian_zhongcao", 0) or 0)
    shen = int(data.get("shen_zhongcao", 0) or 0)

    if total <= 0:
        return False, "资产总量为 0，数据未刷新"
    if total < shougou:
        return False, f"资产总量({total}) < 首购({shougou})，数据异常"
    if qian + shen > total * 1.5:
        return False, f"种草({qian}+{shen}={qian+shen}) > 资产总量({total})*1.5，异常"
    if shougou < 0 or shougou > total:
        return False, f"首购({shougou})超出合理范围"
    return True, "OK"


# ============================================================
# 门禁 3: cross_day — 跨日期校验
# ============================================================

def check_cross_day(csv_file: str | None, data: dict,
                    max_drop_ratio: float = 0.5,
                    max_jump_ratio: float = 2.0) -> tuple[bool, str]:
    """与前一日数据对比，跌幅 > 50% 或涨幅 > 100% 拒绝。

    复刻 dmp_item_insight_scraper.validate_cross_day (line 2219-2265)。
    """
    item_id = str(data.get("item_id", ""))
    current_date_str = data.get("date", "")
    if not item_id or not current_date_str:
        return True, "OK (缺 item_id/date，跳过)"

    current_date = _parse_date(current_date_str)
    if current_date is None:
        return True, "OK (日期格式不识别，跳过)"

    prev_date_str = (current_date - timedelta(days=1)).strftime("%Y/%m/%d")
    prev_row = _read_prev_row(csv_file, item_id, prev_date_str)
    if prev_row is None:
        return True, "OK (无前一日数据，跳过)"

    prev_total = _strip_int(prev_row.get("资产总量", 0))
    if prev_total == 0:
        return True, "OK (前一日为 0，跳过)"

    current_total = int(data.get("zichan_zongliang", 0) or 0)
    if current_total == 0:
        return False, f"资产从 {prev_total:,} 跌至 0，疑似 T+1 未生成"

    ratio = current_total / prev_total
    if ratio < (1 - max_drop_ratio):
        drop_pct = (1 - ratio) * 100
        return False, (
            f"资产从 {prev_total:,} 降至 {current_total:,} "
            f"(-{drop_pct:.1f}%)，超过 {max_drop_ratio*100:.0f}% 跌幅阈值"
        )
    if ratio > max_jump_ratio:
        jump_pct = (ratio - 1) * 100
        return False, (
            f"资产从 {prev_total:,} 升至 {current_total:,} "
            f"(+{jump_pct:.1f}%)，超过 {(max_jump_ratio-1)*100:.0f}% 涨幅阈值"
        )
    return True, "OK"


# ============================================================
# 门禁 4: api_health — API 子字段健康
# ============================================================

def check_api_health(data: dict | None) -> tuple[bool, str]:
    """子字段和 vs 总资产；全 0 拒绝。

    复刻 dmp_item_insight_scraper._check_api_health (line 2405-2421)。
    """
    if not data:
        return False, "数据为空"
    total = int(data.get("zichan_zongliang", 0) or 0)
    sub_sum = (
        int(data.get("qian_zhongcao", 0) or 0)
        + int(data.get("shen_zhongcao", 0) or 0)
        + int(data.get("shougou", 0) or 0)
        + int(data.get("fugou", 0) or 0)
        + int(data.get("liandai", 0) or 0)
    )
    if total > 0 and sub_sum > total * 1.5:
        return False, f"子字段和({sub_sum:,}) > 总资产({total:,})*1.5，API 异常"
    if total == 0 and sub_sum == 0:
        return False, "全 0 数据，T+1 未生成或 SPA 抓取失败"
    return True, "OK"


# ============================================================
# 门禁 5: business_smoothness — 业务平滑（环比 > 30% 告警）
# ============================================================

def check_business_smoothness(csv_file: str | None, data: dict,
                              threshold: float = 0.30) -> tuple[bool, str]:
    """环比涨跌 > threshold 视为业务异常（不阻塞写入，仅告警 + flag）。

    复刻 dmp_item_insight_scraper._check_business_smoothness (line 2315-2348)。
    """
    item_id = str(data.get("item_id", ""))
    current_date_str = data.get("date", "")
    if not item_id or not current_date_str:
        return True, "OK (缺 item_id/date，跳过)"

    current_date = _parse_date(current_date_str)
    if current_date is None:
        return True, "OK (日期格式不识别，跳过)"

    prev_date_str = (current_date - timedelta(days=1)).strftime("%Y/%m/%d")
    prev_row = _read_prev_row(csv_file, item_id, prev_date_str)
    if prev_row is None:
        return True, "OK (无前一日数据，跳过)"

    prev_total = _strip_int(prev_row.get("资产总量", 0))
    if prev_total == 0:
        return True, "OK (前一日为 0，跳过)"

    current_total = int(data.get("zichan_zongliang", 0) or 0)
    if current_total == 0:
        return True, "OK (当前为 0，由 api_health 门禁处理)"

    change_ratio = (current_total - prev_total) / prev_total
    if abs(change_ratio) > threshold:
        direction = "上涨" if change_ratio > 0 else "下跌"
        return False, (
            f"商品 {item_id} 日期 {current_date_str} 资产从 {prev_total:,} "
            f"{direction}到 {current_total:,} ({change_ratio*100:+.1f}%)，"
            f"超过 {threshold*100:.0f}% 阈值"
        )
    return True, "OK"


# ============================================================
# 门禁 6: copy_day — 复制日检测
# ============================================================

_COPY_DAY_FIELDS = (
    ("资产总量", "zichan_zongliang"),
    ("浅种草", "qian_zhongcao"),
    ("深种草", "shen_zhongcao"),
    ("首购资产", "shougou"),
    ("复购资产", "fugou"),
    ("连带资产", "liandai"),
)


def check_copy_day(csv_file: str | None, data: dict) -> tuple[bool, str]:
    """当前 6 字段是否与前一日完全相同（T+1 未生成 → API 返回旧快照）。

    复刻 dmp_item_insight_scraper._detect_copy_day (line 2355-2399)。
    返回 ok=False 表示是复制日（应标 likely-wrong）。
    """
    item_id = str(data.get("item_id", ""))
    current_date_str = data.get("date", "")
    if not item_id or not current_date_str:
        return True, "OK (缺 item_id/date，跳过)"

    current_date = _parse_date(current_date_str)
    if current_date is None:
        return True, "OK (日期格式不识别，跳过)"

    prev_date_str = (current_date - timedelta(days=1)).strftime("%Y/%m/%d")
    prev_row = _read_prev_row(csv_file, item_id, prev_date_str)
    if prev_row is None:
        return True, "OK (无前一日数据，跳过)"

    for csv_field, data_field in _COPY_DAY_FIELDS:
        prev_val = _strip_int(prev_row.get(csv_field, 0))
        curr_val = int(data.get(data_field, 0) or 0)
        if prev_val != curr_val:
            return True, "OK"  # 任一不同 → 非复制日
    return False, (
        f"商品 {item_id} 日期 {current_date_str} 6 字段与 {prev_date_str} "
        f"完全相同，疑似 T+1 延迟复制日"
    )


# ============================================================
# 统一入口
# ============================================================

# 门禁注册表（顺序 = 调用顺序 = 告警显示顺序）
GATE_NAMES = (
    "date_sanity",
    "item_data_validity",
    "cross_day",
    "api_health",
    "business_smoothness",
    "copy_day",
)


def run_all(data: dict, csv_file: str | None = None,
            spa_date: str | None = None,
            target_date: str | None = None,
            scraper_name: str = "dmp_item_insight",
            open_id: str | None = None) -> dict:
    """跑全部 6 道门禁；任一 fail → 告警 + 标 likely-wrong。

    Args:
        data: 单条抓数结果（含 item_id, date, zichan_zongliang, ...）
        csv_file: 历史 CSV 路径（跨日期/复制日校验用）
        spa_date: SPA trigger 实际显示日期（date_sanity 用）
        target_date: 抓取目标日期（date_sanity 用）
        scraper_name: 写到告警消息（区分 assets/flow/items）
        open_id: 收件人 user open_id（不传走 env LARK_OPEN_ID）

    Returns:
        dict:
            gates: {gate_name: (ok, reason), ...}
            overall_ok: bool（全部门禁通过）
            should_flag_likely_wrong: bool（任一失败 → True）
            failed_gates: [(name, reason), ...]
            alert: {sent: bool, reason: str}
    """
    gates: dict[str, tuple[bool, str]] = {
        "date_sanity": check_date_sanity(spa_date, target_date),
        "item_data_validity": check_item_data_validity(data),
        "cross_day": check_cross_day(csv_file, data),
        "api_health": check_api_health(data),
        "business_smoothness": check_business_smoothness(csv_file, data),
        "copy_day": check_copy_day(csv_file, data),
    }

    failed = [(name, gates[name][1]) for name in GATE_NAMES if not gates[name][0]]
    overall_ok = len(failed) == 0
    should_flag_likely_wrong = not overall_ok

    alert_result = {"sent": False, "reason": "无失败门禁，跳过告警"}
    if failed:
        msg = _format_alert_message(data, scraper_name, failed)
        sent, reason = _send_lark_alert(msg, open_id=open_id)
        alert_result = {"sent": sent, "reason": reason}

    return {
        "gates": gates,
        "overall_ok": overall_ok,
        "should_flag_likely_wrong": should_flag_likely_wrong,
        "failed_gates": failed,
        "alert": alert_result,
    }


def _format_alert_message(data: dict, scraper_name: str,
                          failed: list[tuple[str, str]]) -> str:
    """格式化飞书告警消息。"""
    lines = [
        f"[DMP Sanity Alert] {scraper_name} 抓数门禁失败",
        f"商品 ID: {data.get('item_id', '?')}",
        f"日期: {data.get('date', '?')}",
        f"资产总量: {data.get('zichan_zongliang', '?')}",
        f"失败门禁: {len(failed)}/{len(GATE_NAMES)}",
        "",
    ]
    for name, reason in failed:
        lines.append(f"- {name}: {reason}")
    lines.append("")
    lines.append("已自动标记 data_quality_flag=likely-wrong")
    lines.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(lines)
