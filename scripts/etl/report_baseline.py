"""ETL baseline 报告生成器

读取 scripts/etl/baselines/baseline_<DATE>.json，输出人类可读报告：
  - 总耗时 / 步数 / 内存峰值
  - 6 道门禁 pass / fail 状态
  - 步级耗时排行（找出 top 5 hot spot）
  - 与北极星指标 25min 对比

用法：
  python scripts/etl/report_baseline.py                       # 默认 baseline_2026_06_02.json
  python scripts/etl/report_baseline.py path/to/baseline.json # 指定文件
  python scripts/etl/report_baseline.py --json                # 输出 JSON 报告
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# 北极星指标（用户维持不变的目标）
NORTH_STAR_SECONDS = 25 * 60  # 25 min
HISTORICAL_BASELINE_SECONDS = 41 * 60  # 用户 2026-06-02 实测 41 min


def load_baseline(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt_duration(seconds: float) -> str:
    """秒 → 人类可读 (mm:ss.ss / hh:mm:ss)"""
    s = float(seconds)
    if s < 60:
        return f"{s:.2f}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{int(m)}m{s:05.2f}s"
    h, m = divmod(m, 60)
    return f"{int(h)}h{int(m):02d}m{s:05.2f}s"


def fmt_bytes(kb: int) -> str:
    if kb < 1024:
        return f"{kb:,} KB"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f} MB"
    return f"{mb/1024:.2f} GB"


def render_text_report(payload: dict[str, Any], source: Path) -> str:
    """渲染人类可读文本报告"""
    lines: list[str] = []
    add = lines.append

    meta = payload.get("meta", {})
    steps = payload.get("steps", [])
    gates = payload.get("gates", {})
    errors = payload.get("errors", [])

    add("=" * 70)
    add(f"ETL Baseline 报告 — {meta.get('baseline_date', 'unknown')}")
    add("=" * 70)
    add(f"源文件:    {source}")
    add(f"主机:      {meta.get('host', 'unknown')}  "
        f"(Python {meta.get('python_version', '?')})")
    add(f"运行编号:  {meta.get('run_id', '?')}")
    add(f"开始:      {meta.get('started_at', '?')}")
    add(f"结束:      {meta.get('ended_at', '?')}")
    add("")
    add("─── 总体 ───")
    add(f"  总 wall time:   {fmt_duration(meta.get('total_wall_time', 0))}  "
        f"(北极星 25m00.00s / 历史 41m00.00s)")
    add(f"  总 CPU time:    {fmt_duration(meta.get('total_cpu_time', 0))}  "
        f"(CPU 利用率: {meta.get('total_cpu_time', 0)/max(meta.get('total_wall_time', 1), 0.001)*100:.1f}%)")
    add(f"  内存峰值:       {fmt_bytes(meta.get('peak_memory_kb', 0))}")
    add(f"  步数:           {meta.get('step_count', len(steps))}")
    add(f"  错误数:         {len(errors)}")

    # 6 道门禁
    add("")
    add("─── 6 道门禁（QW4 阶段 A）───")
    gate_names = [
        ("date_sanity",      "1. date_sanity   付款时间在合理窗口"),
        ("cross_day",        "2. cross_day     ETL 前后 max(pay_time) 连续"),
        ("api_health",       "3. api_health    ETL 过程无致命异常"),
        ("business_smooth",  "4. business_smooth 退款率 <40% / 购物金率 <40%"),
        ("dedup",            "5. dedup         净增/减行数在合理范围"),
        ("wall_time_stdev",  "6. wall_time_stdev 多次跑批稳定性（单次 N/A）"),
    ]
    for key, label in gate_names:
        g = gates.get(key, {})
        status = g.get("status", "missing")
        m = g.get("measurements", {})
        sym = {"pass": "✅", "fail": "❌", "skipped": "⏭️ ", "n/a": "ℹ️ "}.get(status, "?")
        add(f"  {sym} {label}: {status}")
        # 关键 measurements
        for k, v in sorted(m.items()):
            if k == "errors":
                continue
            add(f"        {k}: {v}")
    if errors:
        add("")
        add(f"  ⚠️  errors ({len(errors)}):")
        for e in errors[:10]:
            add(f"    - {e}")
        if len(errors) > 10:
            add(f"    ... ({len(errors) - 10} more)")

    # 步级 hot spot
    add("")
    add("─── 步级耗时排行（top 10）───")
    ranked = sorted(steps, key=lambda s: s.get("wall_time", 0), reverse=True)
    add(f"  {'step_name':<35} {'wall':>10} {'cpu':>10} {'mem':>10}  extra")
    add("  " + "-" * 90)
    for s in ranked[:10]:
        name = s.get("step_name", "?")
        wall = fmt_duration(s.get("wall_time", 0))
        cpu = fmt_duration(s.get("cpu_time", 0))
        mem = fmt_bytes(s.get("memory_peak_kb", 0))
        extra = s.get("extra", {})
        extra_str = ", ".join(f"{k}={v}" for k, v in extra.items()) if extra else ""
        add(f"  {name:<35} {wall:>10} {cpu:>10} {mem:>10}  {extra_str}")

    # vs 北极星
    wall = meta.get("total_wall_time", 0)
    add("")
    add("─── 北极星对比 ───")
    if wall <= NORTH_STAR_SECONDS:
        add(f"  ✅ wall_time {fmt_duration(wall)} ≤ 25m 北极星")
    else:
        delta = wall - NORTH_STAR_SECONDS
        ratio = wall / NORTH_STAR_SECONDS
        add(f"  ❌ wall_time {fmt_duration(wall)} > 25m 北极星")
        add(f"      超出 {fmt_duration(delta)} ({ratio:.2f}x)")

    hist_delta = wall - HISTORICAL_BASELINE_SECONDS
    if hist_delta < 0:
        add(f"  相对历史 41m 改善 {fmt_duration(-hist_delta)} ({(1 - wall/HISTORICAL_BASELINE_SECONDS)*100:.1f}%)")
    else:
        add(f"  相对历史 41m 退步 {fmt_duration(hist_delta)} (+{hist_delta/HISTORICAL_BASELINE_SECONDS*100:.1f}%)")

    # 错误（如有）
    summary = gates.get("_summary", {})
    add("")
    add("─── 总结 ───")
    add(f"  门禁: pass={summary.get('pass', 0)} / fail={summary.get('fail', 0)} / "
        f"skipped={summary.get('skipped', 0)} / overall={summary.get('overall', '?')}")
    add("=" * 70)
    return "\n".join(lines)


def render_json_report(payload: dict[str, Any], source: Path) -> dict[str, Any]:
    """JSON 报告：突出 top hot spots + 6 道门禁结果"""
    steps = payload.get("steps", [])
    ranked = sorted(steps, key=lambda s: s.get("wall_time", 0), reverse=True)
    return {
        "source": str(source),
        "meta": payload.get("meta", {}),
        "hotspots": [
            {
                "step_name": s.get("step_name"),
                "wall_time": s.get("wall_time"),
                "cpu_time": s.get("cpu_time"),
                "memory_peak_kb": s.get("memory_peak_kb"),
                "extra": s.get("extra", {}),
            }
            for s in ranked[:10]
        ],
        "gates": payload.get("gates", {}),
        "errors": payload.get("errors", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="ETL baseline 报告生成器")
    default_path = Path(__file__).parent / "baselines" / "baseline_2026_06_02.json"
    parser.add_argument(
        "baseline", nargs="?", type=Path, default=default_path,
        help=f"baseline JSON 路径（默认: {default_path}）",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告而非文本")
    args = parser.parse_args()

    if not args.baseline.exists():
        print(f"错误: baseline 文件不存在: {args.baseline}", file=sys.stderr)
        print("提示: 先跑 ETL 跑批生成 baseline_*.json：", file=sys.stderr)
        print("      PYTHONPATH=$(pwd) /Users/hutou/homebrew/bin/python3 scripts/run_etl.py --update",
              file=sys.stderr)
        return 2

    payload = load_baseline(args.baseline)

    if args.json:
        report = render_json_report(payload, args.baseline)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text_report(payload, args.baseline))

    return 0


if __name__ == "__main__":
    sys.exit(main())
