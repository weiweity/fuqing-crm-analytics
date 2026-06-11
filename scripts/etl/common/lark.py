#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ETL 自己的 lark 告警通道 (抽自 scraper/core/sanity_check.py:_send_lark_alert)

B1 治根 (Sprint 16.5+1): 3 个 ETL 脚本 (notify.py / assertions.py / dq_monitor.py)
原本跨子项目 import `scraper.core.sanity_check._send_lark_alert`, 违反
CLAUDE.md "层边界不可跨越" 约束. 此模块为 ETL 提供自己的 lark 通道,
3 个脚本改 import 到这里.

设计:
  - 走 lark-cli subprocess (与原实现一致, 不引入 lark_oapi SDK 依赖)
  - graceful degrade: 失败不抛异常, 不影响主流程
  - 调用方传入 content, 可选传入 open_id / lark_bin / timeout

环境变量:
    LARK_OPEN_ID         - 收件人 user open_id (未设时 skip 告警, 不报错)
    LARK_BIN             - lark-cli 路径 (默认 /Users/hutou/homebrew/bin/lark-cli)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess


# ============================================================
# lark 告警通道
# ============================================================

def _send_lark_alert(content: str, open_id: str | None = None,
                     lark_bin: str | None = None,
                     timeout: float = 5.0) -> tuple[bool, str]:
    """推 lark-cli 私聊告警。

    通过 lark-cli subprocess 调 `im +messages-send --user-id --text` 发消息。
    走 bot 身份 (appsecret_cli_xxx 已在 keychain), 无需用户交互。
    默认 0 限频: 同 1 门禁在 1 日内可能触发多次 (如需要去重由调用方做)。

    Args:
        content: 文本内容
        open_id: 收件人 user open_id (不传走 env LARK_OPEN_ID)
        lark_bin: lark-cli 路径 (不传走 env LARK_BIN, 默认 /Users/hutou/homebrew/bin/lark-cli)
        timeout: subprocess 超时秒

    Returns:
        (sent: bool, reason: str)
        - sent=True 表示 subprocess 成功 + lark-cli 响应 ok=true
        - sent=False 时 reason 说明为何 skip / 失败 (never raises)
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

    # lark-cli 成功响应: {"ok": true, "identity": "bot", "data": {...}}
    try:
        resp = json.loads(proc.stdout)
    except (ValueError, TypeError):
        return True, "OK (non-JSON stdout)"

    if resp.get("ok") is True:
        return True, "OK"
    err = resp.get("error", {})
    return False, f"lark-cli 拒绝: {err.get('type','?')}: {err.get('message','')[:200]}"
