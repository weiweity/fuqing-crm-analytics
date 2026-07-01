"""_dispatch — 9 MCP tool inputSchema + arg_map + handler factory.

L4.19/4.20/4.21 不适用 (本文件是 MCP 层, 不引 SQL, 不重 service).
8 query tool + 1 ask router = 9 tools (跟 Sprint 182 D2 决策一致).
每个 tool: name + description + inputSchema (JSON Schema) + arg_map (MCP param → CLI --flag).
"""
from __future__ import annotations

from typing import Any, Callable

# (mcp_name, command, description, inputSchema, arg_map)
# arg_map: MCP param key → CLI flag (e.g. "start" → "--start")
TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "daily_gsv",
        "command": "daily-gsv",
        "description": "日序列 GSV + customers + YOY 百分比",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
                "end": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string", "description": "输出文件路径"},
            },
            "required": ["start", "end"],
        },
        "arg_map": {"start": "--start", "end": "--end", "format": "--format", "output": "--output"},
    },
    {
        "name": "yoy_battle",
        "command": "yoy-battle",
        "description": "baseline vs current 双窗口 YOY 战斗 (gsv/orders/customers/aov)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "baseline_start": {"type": "string"},
                "baseline_end": {"type": "string"},
                "current_start": {"type": "string"},
                "current_end": {"type": "string"},
                "metric": {"type": "string", "default": "all"},
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string"},
            },
            "required": ["baseline_start", "baseline_end", "current_start", "current_end"],
        },
        "arg_map": {
            "baseline_start": "--baseline-start", "baseline_end": "--baseline-end",
            "current_start": "--current-start", "current_end": "--current-end",
            "metric": "--metric", "format": "--format", "output": "--output",
        },
    },
    {
        "name": "channel_slice",
        "command": "channel-slice",
        "description": "按 channel 切片日维度 (GSV + orders + customers + aov + 可选 YOY)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string"},
                "channel": {"type": "string", "default": "all"},
                "store_id": {"type": "string"},
                "compare": {"type": "string", "enum": ["", "yoy"], "default": ""},
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string"},
            },
            "required": ["date"],
        },
        "arg_map": {
            "date": "--date", "channel": "--channel", "store_id": "--store-id",
            "compare": "--compare", "format": "--format", "output": "--output",
        },
    },
    {
        "name": "two_year_overview",
        "command": "two-year-overview",
        "description": "两年新老客/会员核心指标对比",
        "inputSchema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "default": 2026},
                "period": {"type": "string"},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "channel": {"type": "string"},
                "exclude_channels": {"type": "string"},
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string"},
            },
        },
        "arg_map": {
            "year": "--year", "period": "--period", "start": "--start", "end": "--end",
            "channel": "--channel", "exclude_channels": "--exclude-channels",
            "format": "--format", "output": "--output",
        },
    },
    {
        "name": "new_old_customer",
        "command": "new-old-customer",
        "description": "新老客拆分对比 (L4.25 前缀隔离)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start": {"type": "string"},
                "end": {"type": "string"},
                "exclude_channels": {"type": "string"},
                "dimension": {"type": "string", "default": "channel"},
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string"},
            },
            "required": ["start", "end"],
        },
        "arg_map": {
            "start": "--start", "end": "--end",
            "exclude_channels": "--exclude-channels", "dimension": "--dimension",
            "format": "--format", "output": "--output",
        },
    },
    {
        "name": "rfm_repurchase",
        "command": "rfm-repurchase",
        "description": "R 区间复购周期分布，复用 get_rfm_r_flow",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start": {"type": "string"},
                "end": {"type": "string"},
                "channel": {"type": "string"},
                "exclude_channels": {"type": "string"},
                "year": {"type": "integer", "default": 2026},
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string"},
            },
            "required": ["start", "end"],
        },
        "arg_map": {
            "start": "--start", "end": "--end", "channel": "--channel",
            "exclude_channels": "--exclude-channels", "year": "--year",
            "format": "--format", "output": "--output",
        },
    },
    {
        "name": "top_n",
        "command": "top-n",
        "description": "TOP N 品类/产品层级两年对比",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dimension": {"type": "string", "default": "spu_category"},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "exclude_channels": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string"},
            },
            "required": ["start", "end"],
        },
        "arg_map": {
            "dimension": "--dimension", "start": "--start", "end": "--end",
            "exclude_channels": "--exclude-channels", "limit": "--limit",
            "format": "--format", "output": "--output",
        },
    },
    {
        "name": "export_excel",
        "command": "export-excel",
        "description": "导出 11 sheet Excel 整份报告",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start": {"type": "string"},
                "end": {"type": "string"},
                "exclude_channels": {"type": "string"},
                "year": {"type": "integer", "default": 2026},
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string"},
            },
            "required": ["start", "end"],
        },
        "arg_map": {
            "start": "--start", "end": "--end",
            "exclude_channels": "--exclude-channels", "year": "--year",
            "format": "--format", "output": "--output",
        },
    },
    {
        "name": "dq_report",
        "command": "dq-report",
        "description": "数据质量 5/15 项规则报告 (ETL 跑批后校验)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start": {"type": "string"},
                "end": {"type": "string"},
                "full": {"type": "boolean", "default": False},
                "force": {"type": "boolean", "default": False},
                "exclude_channels": {"type": "string"},
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string"},
            },
            "required": ["start", "end"],
        },
        "arg_map": {
            "start": "--start", "end": "--end", "full": "--full", "force": "--force",
            "exclude_channels": "--exclude-channels",
            "format": "--format", "output": "--output",
        },
    },
    {
        "name": "ask",
        "command": "ask",
        "description": "自然语言关键词路由 (不调 LLM, 纯规则)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "自然语言问数文本"},
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
            },
            "required": ["text"],
        },
        "arg_map": {"text": "--text", "format": "--format"},
    },
]


def _make_handler(tool_def: dict[str, Any]) -> Callable[[dict[str, Any]], list[str]]:
    """Factory: 把 MCP call kwargs → CLI argv.

    跳过 None 值 (CLI argparse 用 required=True/False 标记, 缺省值由 CLI 兜底).
    boolean store_true flag 用值传 (CLI 接受 true/false 自动 normalize).

    Sprint 182 Phase 4 adversarial fix (confidence 8/10): output 路径 sanitize.
    LLM prompt injection 可能写 ~/.ssh/authorized_keys / /etc/cron.d/exploit.
    复用 scripts.ad_hoc_queries._utils._sanitize_path_component (L4.34 配套
    sanitization: 禁绝对路径 / 盘符 / 路径遍历 / 控制字符).
    """
    command = tool_def["command"]
    arg_map: dict[str, str] = tool_def["arg_map"]

    def handler(kwargs: dict[str, Any]) -> list[str]:
        argv: list[str] = [command]
        for k, v in kwargs.items():
            if v is None:
                continue
            flag = arg_map.get(k)
            if flag is None:
                continue
            value_str = str(v)
            # Sprint 182 Phase 4: --output / --file 等路径类参数必须 sanitize
            if k in ("output", "file"):
                try:
                    from scripts.ad_hoc_queries._utils import _sanitize_path_component
                    value_str = _sanitize_path_component(value_str)
                except ImportError:
                    # 测试环境 / module 找不到时 fail-closed 拒绝, 不让 raw 路径透传
                    raise ValueError(
                        f"Sprint 182 Phase 4 安全护栏: 路径 sanitize 失败 "
                        f"({k}={v!r}); _utils 模块不可用, 拒绝路径类参数"
                    )
            argv.extend([flag, value_str])
        return argv

    return handler


# 10 个 tool → 10 个 handler, server.py 启动期一次性建好
HANDLERS: dict[str, Callable[[dict[str, Any]], list[str]]] = {
    td["name"]: _make_handler(td) for td in TOOL_DEFS
}
