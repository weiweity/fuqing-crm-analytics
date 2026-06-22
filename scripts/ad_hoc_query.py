#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
芙清 CRM - 即席查询 CLI (Sprint 61 MVP)

ad_hoc_query.py — argparse 子命令 dispatch + registry 加载.

MVP 范围 (不追求全功能):
- 1 个子命令: daily-gsv (日序列 GSV + customers + YOY%)
- 2 个输出格式: stdout 表格 + CSV
- 0 HTTP server / 0 web UI

设计原则 (Sprint 60+ 沉淀):
- 复用 backend/semantic/ 口径层, 禁 inline SQL
- 复用 backend/services/ + backend/contracts/schemas.py
- read_only DuckDB 连接 (跟 uvicorn 共存, 跟 Sprint 53 race flake 治本同模式)
- audit log → /tmp/fuqing_adhoc_audit.log (跟 /ship .ship-audit.log 同模式)

留 Sprint 62+:
- channel-slice / yoy-battle / rfm-distribution / customer-segment (4 个 query)
- rich table + XLSX 输出 (openpyxl 已在)
- list-endpoints / health-check / export 元查询
- ratio ≤ 1.0 / YOY 范围 CI lint

用法:
  python scripts/ad_hoc_query.py daily-gsv --start 2026-06-19 --end 2026-06-21
  python scripts/ad_hoc_query.py daily-gsv --start 2026-06-19 --end 2026-06-21 --format csv
  python scripts/ad_hoc_query.py daily-gsv --start 2026-06-19 --end 2026-06-21 --format csv --output /tmp/gsv.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 把项目根加进 path, 跟 scripts/run_etl.py 一致
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ad_hoc_queries.registry import QUERIES, get  # noqa: E402
from scripts.ad_hoc_queries._utils import (  # noqa: E402
    check_etl_running,
    format_stdout_table,
    log_audit,
    resolve_output_path,
    write_csv,
)


def _build_parser() -> argparse.ArgumentParser:
    """构造顶层 parser + 动态 subparser (从 QUERIES 注册表生成)."""
    parser = argparse.ArgumentParser(
        prog="ad_hoc_query.py",
        description="芙清 CRM 即席查询 CLI (Sprint 61 MVP — daily-gsv only)",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for name, spec in sorted(QUERIES.items()):
        p = sub.add_parser(name, help=spec.description, description=spec.description)
        for arg in spec.args:
            flags = arg["flags"]
            kwargs = {
                "required": arg.get("required", False),
                "help": arg.get("help", ""),
            }
            if "default" in arg:
                kwargs["default"] = arg["default"]
            if "choices" in arg:
                kwargs["choices"] = arg["choices"]
            p.add_argument(*flags, **kwargs)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    spec = get(args.command)

    # 1) 风险检查: ETL 跑批中 → 警告但继续 (Sprint 60+ 沉淀)
    etl_running = check_etl_running()
    if etl_running:
        print(
            "[WARN] ETL 跑批中 (flag 存在), 查询可能锁冲突或卡顿. "
            "建议 ETL 跑完再跑.",
            file=sys.stderr,
        )

    # 2) 抓 kwarg 传给 spec.run (**)
    kwargs = vars(args)
    cmd = kwargs.pop("command")
    fmt = kwargs.pop("format", "table")
    output = kwargs.pop("output", None)
    try:
        rows = spec.run(**kwargs)
    except (ValueError, KeyError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        log_audit(cmd, "error", error=str(exc))
        return 2
    except Exception as exc:
        # Sprint 60+ 沉淀: 真异常必 audit (防盲区)
        print(f"[ERROR] unexpected: {exc}", file=sys.stderr)
        log_audit(cmd, "unexpected", error=str(exc))
        return 1

    # 3) Sprint 61+ 自动按双层目录规则生成路径 (user 拍板)
    if fmt == "csv" and not output and spec.business_tag:
        base_year_arg = kwargs.get(spec.base_year_arg, "")
        date_range = (
            f"{base_year_arg}至{kwargs.get('end', '')}"
            if base_year_arg and kwargs.get("end")
            else base_year_arg
        )
        try:
            base_year = int(base_year_arg.split("-")[0]) if base_year_arg else 0
        except (ValueError, IndexError):
            base_year = 0
        if base_year:
            output = resolve_output_path(
                user_output=None,
                business_tag=spec.business_tag,
                base_year=base_year,
                date_range=date_range,
            )
            print(f"[INFO] auto-path: {output}", file=sys.stderr)
    elif fmt == "csv" and output:
        # user --output 显式路径, 不走 auto-path log (避免误报)
        print(f"[INFO] user-output: {output}", file=sys.stderr)

    # 4) 输出
    if fmt == "csv":
        path = write_csv(rows, spec.headers, output_path=output)
        if output:
            print(f"[OK] CSV written to {path}", file=sys.stderr)
        else:
            sys.stdout.write(path)
    else:  # table (default)
        out = format_stdout_table(rows, spec.headers)
        sys.stdout.write(out)
        sys.stdout.write("\n")

    # 4) audit trail
    log_audit(
        cmd, "ok", etl_running=etl_running, fmt=fmt, rows=len(rows),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
