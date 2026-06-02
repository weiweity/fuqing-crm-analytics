"""ETL 性能埋点（QW4 工单 0）

轻量级 perf_counter 埋点 + 6 道 ETL 门禁 + baseline JSON 落盘。

设计原则：
- 单进程内 _RECORDS 列表收集所有 step 记录
- 6 道门禁是 callable hook：在 ETL 关键节点手动 gate_* 写入 measurements，最后 save_baseline 时汇总判定
- baseline JSON 不放在 .gitignore 的 data/ 目录，放在 scripts/etl/baselines/（已被 git 跟踪）

6 道门禁（QW4 阶段 A 定义）：
1. date_sanity   — 付款时间字段在合理窗口（无未来日期、无超 5 年前日期）
2. cross_day     — ETL 前后 max(pay_time) 连续，无跨日丢失
3. api_health    — ETL 过程中 DuckDB / Parquet 写入无致命异常
4. business_smooth — 退款率 <40%、购物金率 <40%（数据验收门卫）
5. dedup         — 重复订单写入不增长（净增量在合理范围）
6. wall_time_stdev — 多次跑批的 wall time 标准差（单次跑批输出 N/A）
"""
from __future__ import annotations

import json
import os
import platform
import resource
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────
# 路径 & 落盘
# ─────────────────────────────────────────────────────────────

# scripts/etl/perf.py → scripts/etl/baselines/baseline_<DATE>.json
PERF_DIR = Path(__file__).parent
BASELINES_DIR = PERF_DIR / "baselines"
BASELINE_DATE = os.environ.get("ETL_BASELINE_DATE", "2026_06_02")
BASELINE_PATH = BASELINES_DIR / f"baseline_{BASELINE_DATE}.json"


# ─────────────────────────────────────────────────────────────
# 性能记录
# ─────────────────────────────────────────────────────────────

@dataclass
class PerfRecord:
    """单个 step 的性能记录"""
    step_name: str
    timestamp: str
    wall_time: float
    cpu_time: float
    memory_peak_kb: int
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_name": self.step_name,
            "timestamp": self.timestamp,
            "wall_time": round(self.wall_time, 4),
            "cpu_time": round(self.cpu_time, 4),
            "memory_peak_kb": self.memory_peak_kb,
            **({"extra": {k: _safe(v) for k, v in self.extra.items()}} if self.extra else {}),
        }


def _safe(v: Any) -> Any:
    """JSON 序列化安全化：datetime / Path / set 等"""
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, Path):
        return str(v)
    if isinstance(v, set):
        return sorted(v)
    if isinstance(v, (int, float, str, bool, type(None))):
        return v
    if isinstance(v, (list, tuple)):
        return [_safe(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _safe(x) for k, x in v.items()}
    return str(v)


# ─────────────────────────────────────────────────────────────
# 全局 registry
# ─────────────────────────────────────────────────────────────

_RECORDS: list[PerfRecord] = []
_GATES: dict[str, dict[str, Any]] = {
    "date_sanity": {"status": "skipped", "measurements": {}},
    "cross_day": {"status": "skipped", "measurements": {}},
    "api_health": {"status": "skipped", "measurements": {}},
    "business_smooth": {"status": "skipped", "measurements": {}},
    "dedup": {"status": "skipped", "measurements": {}},
    "wall_time_stdev": {"status": "skipped", "measurements": {}},
}
_ERRORS: list[str] = []


def reset() -> None:
    """清空 registry（测试用）"""
    _RECORDS.clear()
    for k in _GATES:
        _GATES[k] = {"status": "skipped", "measurements": {}}
    _ERRORS.clear()


def get_records() -> list[PerfRecord]:
    return list(_RECORDS)


# ─────────────────────────────────────────────────────────────
# PerfTimer 上下文管理器
# ─────────────────────────────────────────────────────────────

class PerfTimer:
    """上下文管理器：包裹一段 ETL 步骤，自动打 wall_time / cpu_time / memory_peak。

    用法：
        with PerfTimer("step1_etl_inc", mode=run_mode):
            ...  # 业务代码
    """

    def __init__(self, step_name: str, **extra: Any):
        self.step_name = step_name
        self.extra = extra
        self._wall_start = 0.0
        self._cpu_start = 0.0
        self._mem_start = 0
        self._record: PerfRecord | None = None

    def __enter__(self) -> "PerfTimer":
        self._wall_start = time.perf_counter()
        self._cpu_start = time.process_time()
        self._mem_start = _peak_rss_kb()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        wall = time.perf_counter() - self._wall_start
        cpu = time.process_time() - self._cpu_start
        mem = max(_peak_rss_kb(), self._mem_start)
        rec = PerfRecord(
            step_name=self.step_name,
            timestamp=datetime.now().isoformat(),
            wall_time=wall,
            cpu_time=cpu,
            memory_peak_kb=mem,
            extra=dict(self.extra),
        )
        _RECORDS.append(rec)
        self._record = rec
        if exc is not None:
            _ERRORS.append(f"{self.step_name}: {type(exc).__name__}: {exc}")


def _peak_rss_kb() -> int:
    """当前进程峰值 RSS（KB）。macOS 单位是 bytes，Linux 是 KB。"""
    rusage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == "Darwin":
        return int(rusage / 1024)  # bytes → KB
    return int(rusage)  # already KB


# ─────────────────────────────────────────────────────────────
# 6 道门禁 — 写 measurements，由 ETL 关键节点调用
# ─────────────────────────────────────────────────────────────

def gate_set(gate_name: str, status: str, **measurements: Any) -> None:
    """写单个门禁的状态和测量值。status: pass / fail / skipped"""
    if gate_name not in _GATES:
        raise KeyError(f"Unknown gate: {gate_name}")
    _GATES[gate_name]["status"] = status
    _GATES[gate_name]["measurements"].update(
        {k: _safe(v) for k, v in measurements.items()}
    )


def gate_record_error(step_name: str, exc: BaseException) -> None:
    """记录 ETL 过程中的异常（被 PerfTimer 自动调用，也可手动）"""
    _ERRORS.append(f"{step_name}: {type(exc).__name__}: {exc}")


# ─────────────────────────────────────────────────────────────
# 门禁预制常量（业务阈值）
# ─────────────────────────────────────────────────────────────

REFUND_THRESHOLD = 0.40
GOUJINJIN_THRESHOLD = 0.40
DEDUP_NET_CHANGE_LIMIT = 100  # 刷新后净减少不超过 100 行
DATE_SANITY_FUTURE_DAYS = 1   # 允许 pay_time 最多比今天多 1 天（时区/写入时钟漂移）
DATE_SANITY_PAST_YEARS = 10   # pay_time 不应早于 10 年前（芙清业务始于 2020）


# ─────────────────────────────────────────────────────────────
# 落盘
# ─────────────────────────────────────────────────────────────

def save_baseline(
    path: Path | None = None,
    host: str | None = None,
    run_id: str = "1/3",
) -> dict[str, Any]:
    """汇总 + 落盘 baseline JSON。返回 payload 供调用方继续使用。

    可重复调用（每次写入同一文件、累积所有已记录的 step），
    用于长跑批任务在每步结束/中断时保留 partial baseline。
    """
    out_path = Path(path) if path else BASELINE_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total_wall = sum(r.wall_time for r in _RECORDS)
    total_cpu = sum(r.cpu_time for r in _RECORDS)
    peak_mem = max((r.memory_peak_kb for r in _RECORDS), default=0)

    payload = {
        "meta": {
            "baseline_date": BASELINE_DATE,
            "host": host or _detect_host(),
            "run_id": run_id,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "started_at": _RECORDS[0].timestamp if _RECORDS else None,
            "ended_at": _RECORDS[-1].timestamp if _RECORDS else None,
            "total_wall_time": round(total_wall, 4),
            "total_cpu_time": round(total_cpu, 4),
            "peak_memory_kb": peak_mem,
            "step_count": len(_RECORDS),
        },
        "steps": [r.to_dict() for r in _RECORDS],
        "gates": _build_gates_block(),
        "errors": list(_ERRORS),
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def _build_gates_block() -> dict[str, Any]:
    """汇总 6 道门禁 + 给出整体通过状态"""
    gates = {name: dict(v) for name, v in _GATES.items()}
    # 整体 pass / fail
    fail_count = sum(1 for v in gates.values() if v.get("status") == "fail")
    pass_count = sum(1 for v in gates.values() if v.get("status") == "pass")
    skipped = sum(1 for v in gates.values() if v.get("status") == "skipped")
    gates["_summary"] = {
        "total": len(gates),
        "pass": pass_count,
        "fail": fail_count,
        "skipped": skipped,
        "overall": "pass" if fail_count == 0 and (pass_count + skipped) == 6 else "fail",
    }
    return gates


def _detect_host() -> str:
    p = platform.system().lower()
    if p == "darwin":
        return "mac"
    if p.startswith("win"):
        return "windows"
    return p


# ─────────────────────────────────────────────────────────────
# 6 道门禁判定函数（在 save_baseline 后可选调用，输出人类可读报告）
# ─────────────────────────────────────────────────────────────

def evaluate_gates(payload: dict[str, Any] | None = None) -> dict[str, str]:
    """根据已记录的 measurements 判定每道门禁的 pass/fail。

    返回 {gate_name: status}。不修改 _GATES。
    """
    payload = payload or _GATES
    out: dict[str, str] = {}

    # 1. date_sanity
    m = payload.get("date_sanity", {}).get("measurements", {})
    if m.get("checked"):
        future = m.get("future_days", 0)
        past = m.get("past_years", 0)
        ok = future <= DATE_SANITY_FUTURE_DAYS and past <= DATE_SANITY_PAST_YEARS
        out["date_sanity"] = "pass" if ok else "fail"
    else:
        out["date_sanity"] = payload.get("date_sanity", {}).get("status", "skipped")

    # 2. cross_day
    m = payload.get("cross_day", {}).get("measurements", {})
    if m.get("checked"):
        before_max = m.get("before_max_pay_time")
        after_max = m.get("after_max_pay_time")
        # 增量模式后 max 应 >= 前 max
        ok = after_max is not None and (before_max is None or after_max >= before_max)
        out["cross_day"] = "pass" if ok else "fail"
    else:
        out["cross_day"] = payload.get("cross_day", {}).get("status", "skipped")

    # 3. api_health
    m = payload.get("api_health", {}).get("measurements", {})
    if m.get("checked"):
        err_count = m.get("error_count", 0)
        out["api_health"] = "pass" if err_count == 0 else "fail"
    else:
        out["api_health"] = payload.get("api_health", {}).get("status", "skipped")

    # 4. business_smooth
    m = payload.get("business_smooth", {}).get("measurements", {})
    if m.get("checked"):
        refund = m.get("refund_rate", 0)
        goujinjin = m.get("goujinjin_rate", 0)
        ok = refund < REFUND_THRESHOLD and goujinjin < GOUJINJIN_THRESHOLD
        out["business_smooth"] = "pass" if ok else "fail"
    else:
        out["business_smooth"] = payload.get("business_smooth", {}).get("status", "skipped")

    # 5. dedup
    m = payload.get("dedup", {}).get("measurements", {})
    if m.get("checked"):
        net = m.get("net_change", 0)
        # 净变化：新增 + 刷新 - 删除；净减少（负数）|净变化| > 阈值 = 异常
        ok = abs(min(0, net)) <= DEDUP_NET_CHANGE_LIMIT
        out["dedup"] = "pass" if ok else "fail"
    else:
        out["dedup"] = payload.get("dedup", {}).get("status", "skipped")

    # 6. wall_time_stdev（单次跑批 N/A，需要 ≥ 3 次才有意义）
    m = payload.get("wall_time_stdev", {}).get("measurements", {})
    if m.get("checked"):
        stdev = m.get("stdev_seconds")
        mean = m.get("mean_seconds", 0)
        cv = (stdev / mean) if (mean and stdev is not None) else None
        # CV < 20% 算稳定
        ok = cv is not None and cv < 0.20
        out["wall_time_stdev"] = "pass" if ok else "fail"
    else:
        out["wall_time_stdev"] = "n/a (单次跑批，需要 ≥3 次 Mac + 3 次 Windows)"

    return out
