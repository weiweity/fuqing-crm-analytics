"""_dispatch — 18 MCP tool inputSchema + arg_map + handler factory (Sprint 203 R5 14 → 18 tool).

L4.19/4.20/4.21 不适用 (本文件是 MCP 层, 不引 SQL, 不重 service).
17 query tool + 1 ask router = 18 tools (Sprint 198 14 → Sprint 203 R5 18 tool, 跟 L4.37 registry 显式 import 1:1 stable).
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
                "order_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "订单号列表，仅统计匹配订单; 5000+ 自动走 DuckDB temp table",
                },
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string"},
            },
        },
        "arg_map": {
            "year": "--year", "period": "--period", "start": "--start", "end": "--end",
            "channel": "--channel", "exclude_channels": "--exclude-channels",
            "order_ids": "--order-ids",
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
    {
        "name": "daily-gsv-multi-period",
        "command": "daily-gsv-multi-period",
        "description": "多周期 × 8 维度 (sample/member × GMV/GSV + new/old × users/GSV) 一次跑, 输出 8 列宽表 daily rows. 替代 WorkBuddy 临时 adhoc_daily_segments.py (Sprint 183 真业务触发).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "periods": {
                    "type": "array",
                    "items": {"type": "string", "description": "YYYY-MM-DD"},
                    "description": "多周期列表, 格式 ['2026-05-06', '2026-06-21', '2025-05-06', '2025-06-21', ...] (start/end 成对)"
                },
                "metrics": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "sample_gmv", "sample_gsv",
                            "member_gmv", "member_gsv",
                            "new_users", "new_gsv",
                            "old_users", "old_gsv",
                        ]
                    },
                    "description": "8 个 metric 名 (默认全 8 个), 见 inputSchema enum"
                },
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string", "description": "输出文件路径"},
            },
            "required": ["periods"],
        },
        "arg_map": {
            "periods": "--periods",
            "metrics": "--metrics",
            "format": "--format",
            "output": "--output",
        },
    },
    {
        "name": "fixed_product_list_compare",
        "command": "fixed-product-list-compare",
        "description": "固定 product_id 清单 + 新老客 + 两年对比 + TTL/单品层级 (Sprint 196)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                "product_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "产品 ID 列表; 不传则用归档固定清单",
                },
                "mom_start_date": {"type": "string", "description": "环比期起始日期 YYYY-MM-DD"},
                "mom_end_date": {"type": "string", "description": "环比期结束日期 YYYY-MM-DD"},
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string", "description": "输出文件路径"},
            },
            "required": ["start_date", "end_date"],
        },
        "arg_map": {
            "start_date": "--start-date",
            "end_date": "--end-date",
            "product_ids": "--product-ids",
            "mom_start_date": "--mom-start-date",
            "mom_end_date": "--mom-end-date",
            "format": "--format",
            "output": "--output",
        },
    },
    {
        "name": "fixed_product_list_compare_http",
        "command": "fixed-product-list-compare-http",
        "description": "固定 product_id 清单新老客对比 (HTTP API, Sprint 197, 0 DuckDB 子进程锁冲突)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                "product_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "产品 ID 列表; 不传则用归档固定清单",
                },
                "mom_start_date": {"type": "string", "description": "环比期起始日期 YYYY-MM-DD"},
                "mom_end_date": {"type": "string", "description": "环比期结束日期 YYYY-MM-DD"},
                "auth_token": {"type": "string", "description": "Bearer token; 默认读 FQ_CRM_AUTH_TOKEN"},
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string", "description": "输出文件路径"},
            },
            "required": ["start_date", "end_date"],
        },
        "arg_map": {
            "start_date": "--start-date",
            "end_date": "--end-date",
            "product_ids": "--product-ids",
            "mom_start_date": "--mom-start-date",
            "mom_end_date": "--mom-end-date",
            "auth_token": "--auth-token",
            "format": "--format",
            "output": "--output",
        },
    },
    {
        "name": "ai_sandbox_execute",
        "command": "ai-sandbox-execute",
        "description": "AI 命中不到固定 tool 时走 backend sandbox service + audit log (Sprint 198)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "单条 SELECT/WITH 只读 SQL"},
                "sandbox_type": {
                    "type": "string",
                    "enum": ["aggregate", "timeseries", "rfm", "ltv"],
                    "default": "aggregate",
                },
                "audit_id": {"type": "string", "description": "审计 ID"},
                "auth_token": {"type": "string", "description": "Bearer token; 默认读 FQ_CRM_AUTH_TOKEN"},
                "format": {"type": "string", "enum": ["table", "csv"], "default": "table"},
                "output": {"type": "string", "description": "输出文件路径"},
            },
            "required": ["sql"],
        },
        "arg_map": {
            "sql": "--sql",
            "sandbox_type": "--sandbox-type",
            "audit_id": "--audit-id",
            "auth_token": "--auth-token",
            "format": "--format",
            "output": "--output",
        },
    },
    # === Sprint 203 R5: 4 件新 tool (channel-monthly / member-monthly / refund-monthly / cross-dimension-monthly, 14 → 18 tool) ===
    {
        "name": "channel_monthly",
        "command": "channel-monthly",
        "description": "按 channel 切片月维度 (Sprint 199 R1 留尾任务 A 实证, Sprint 203 R5 实施)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "起始月份 YYYY-MM"},
                "end": {"type": "string", "description": "结束月份 YYYY-MM (含)"},
                "channel": {"type": "string", "default": "all", "description": "渠道过滤 (all/online/offline/具体渠道名)"},
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string", "description": "输出文件路径"},
            },
            "required": ["start", "end"],
        },
        "arg_map": {"start": "--start", "end": "--end", "channel": "--channel", "format": "--format", "output": "--output"},
    },
    {
        "name": "member_monthly",
        "command": "member-monthly",
        "description": "按 is_member 切片月维度 (Sprint 203 R5 业务空白点补全)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "起始月份 YYYY-MM"},
                "end": {"type": "string", "description": "结束月份 YYYY-MM (含)"},
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string", "description": "输出文件路径"},
            },
            "required": ["start", "end"],
        },
        "arg_map": {"start": "--start", "end": "--end", "format": "--format", "output": "--output"},
    },
    {
        "name": "refund_monthly",
        "command": "refund-monthly",
        "description": "按 is_refund 切片月维度 (Sprint 203 R5 退款监控必备)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "起始月份 YYYY-MM"},
                "end": {"type": "string", "description": "结束月份 YYYY-MM (含)"},
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string", "description": "输出文件路径"},
            },
            "required": ["start", "end"],
        },
        "arg_map": {"start": "--start", "end": "--end", "format": "--format", "output": "--output"},
    },
    {
        "name": "cross_dimension_monthly",
        "command": "cross-dimension-monthly",
        "description": "通用多维度交叉按月 (channel × is_member / spu × channel / is_goujinjin × channel, 6 维白名单)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "起始月份 YYYY-MM"},
                "end": {"type": "string", "description": "结束月份 YYYY-MM (含)"},
                "dim1": {"type": "string", "enum": ["channel", "is_member", "is_goujinjin", "spu_category", "spu_tier", "spu_product_class"], "description": "维度 1 (6 维白名单)"},
                "dim2": {"type": "string", "enum": ["channel", "is_member", "is_goujinjin", "spu_category", "spu_tier", "spu_product_class"], "description": "维度 2 (6 维白名单)"},
                "format": {"type": "string", "enum": ["table", "csv", "xlsx"], "default": "table"},
                "output": {"type": "string", "description": "输出文件路径"},
            },
            "required": ["start", "end", "dim1", "dim2"],
        },
        "arg_map": {"start": "--start", "end": "--end", "dim1": "--dim1", "dim2": "--dim2", "format": "--format", "output": "--output"},
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
            if isinstance(v, list):
                argv.append(flag)
                argv.extend(str(item) for item in v)
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


# 18 个 tool → 18 个 handler, server.py 启动期一次性建好 (Sprint 203 R5 14 → 18 tool)
HANDLERS: dict[str, Callable[[dict[str, Any]], list[str]]] = {
    td["name"]: _make_handler(td) for td in TOOL_DEFS
}
