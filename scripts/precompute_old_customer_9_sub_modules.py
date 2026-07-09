#!/usr/bin/env python3
"""L4.72.4 old-customer hot-window precompute runner.

The runner intentionally calls existing customer-health service functions instead
of copying their SQL. Output is JSON snapshots plus a manifest under
data/cache/old_customer_precompute by default.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "cache" / "old_customer_precompute"
HOT_WINDOWS = (7, 30, 180, 365)
DEFAULT_RFM_SEGMENT = os.environ.get("FQ_OLD_CUSTOMER_PRECOMPUTE_RFM_SEGMENT", "重要价值客户")


@dataclass(frozen=True)
class PrecomputeJob:
    slug: str
    callable_path: str
    params: dict[str, Any]
    window_days: int
    end_date: str


SUB_MODULES: tuple[dict[str, str], ...] = (
    {"slug": "overview", "callable": "backend.services.health.overview:get_overview"},
    {"slug": "health-targets", "callable": "backend.services.health.overview:get_health_targets"},
    {"slug": "repurchase-cycle", "callable": "backend.services.health.repurchase:get_repurchase_cycle"},
    {"slug": "cohort-retention", "callable": "backend.services.health.repurchase:get_cohort_retention"},
    {"slug": "value-tiers", "callable": "backend.services.health.tiers:get_value_tiers"},
    {"slug": "tier-flow", "callable": "backend.services.health.tier_flow:get_tier_flow"},
    {"slug": "rfm-analysis", "callable": "backend.services.health.rfm_analysis:get_rfm_analysis"},
    {"slug": "rfm-category-drilldown", "callable": "backend.services.health.rfm_category_drilldown:get_rfm_category_drilldown"},
    {"slug": "new-customer-conversion", "callable": "backend.services.health.conversion:get_new_customer_conversion"},
    {"slug": "promotion-calendar", "callable": "backend.services.health.promotion:get_promotion_calendar"},
    {"slug": "channel-health-scores", "callable": "backend.services.health.channel_scores:get_channel_health_scores"},
)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _month(value: date) -> str:
    return value.strftime("%Y-%m")


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        fh.write("\n")
        tmp_name = fh.name
    Path(tmp_name).replace(path)


def _load_callable(callable_path: str) -> Callable[..., Any]:
    module_name, func_name = callable_path.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, func_name)


def _build_params(slug: str, end_date: date, window_days: int) -> dict[str, Any]:
    start_date = end_date - timedelta(days=window_days - 1)
    if slug in {"overview", "health-targets", "channel-health-scores"}:
        return {"analysis_date": end_date.isoformat(), "period_days": window_days}
    if slug == "repurchase-cycle":
        return {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}
    if slug == "cohort-retention":
        return {"start_month": _month(start_date), "end_month": _month(end_date)}
    if slug == "value-tiers":
        return {"analysis_date": end_date.isoformat(), "lookback_days": window_days}
    if slug in {"tier-flow", "rfm-analysis"}:
        return {"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "metric_type": "GSV"}
    if slug == "rfm-category-drilldown":
        return {
            "rfm_segment": DEFAULT_RFM_SEGMENT,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "metric_type": "GSV",
        }
    if slug == "new-customer-conversion":
        return {"analysis_date": end_date.isoformat(), "lookback_months": max(1, round(window_days / 30))}
    if slug == "promotion-calendar":
        return {"year": end_date.year}
    raise ValueError(f"unknown old-customer precompute module: {slug}")


def build_jobs(end_date: str, windows: tuple[int, ...] = HOT_WINDOWS) -> list[PrecomputeJob]:
    parsed_end = _parse_date(end_date)
    jobs: list[PrecomputeJob] = []
    for window_days in windows:
        for module in SUB_MODULES:
            slug = module["slug"]
            jobs.append(
                PrecomputeJob(
                    slug=slug,
                    callable_path=module["callable"],
                    params=_build_params(slug, parsed_end, window_days),
                    window_days=window_days,
                    end_date=end_date,
                )
            )
    return jobs


def output_path(output_dir: Path, job: PrecomputeJob) -> Path:
    return output_dir / f"window_{job.window_days}d" / job.slug / f"{job.end_date}.json"


def run_job(job: PrecomputeJob, output_dir: Path, dry_run: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    path = output_path(output_dir, job)
    if dry_run:
        return {
            "slug": job.slug,
            "window_days": job.window_days,
            "end_date": job.end_date,
            "status": "dry-run",
            "path": str(path),
            "params": job.params,
        }

    func = _load_callable(job.callable_path)
    result = func(**job.params)
    payload = {
        "meta": {
            "slug": job.slug,
            "callable": job.callable_path,
            "window_days": job.window_days,
            "end_date": job.end_date,
            "params": job.params,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        },
        "data": result,
    }
    _atomic_json_write(path, payload)
    return {
        "slug": job.slug,
        "window_days": job.window_days,
        "end_date": job.end_date,
        "status": "ok",
        "path": str(path),
        "elapsed_ms": payload["meta"]["elapsed_ms"],
    }


def write_manifest(output_dir: Path, end_date: str, results: list[dict[str, Any]]) -> Path:
    manifest = {
        "name": "old_customer_9_sub_modules",
        "end_date": end_date,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "windows": list(HOT_WINDOWS),
        "job_count": len(results),
        "ok_count": sum(1 for item in results if item.get("status") in {"ok", "dry-run"}),
        "error_count": sum(1 for item in results if item.get("status") == "error"),
        "results": results,
    }
    path = output_dir / "manifest.json"
    _atomic_json_write(path, manifest)
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--end-date", default=os.environ.get("FQ_PRECOMPUTE_END_DATE", date.today().isoformat()))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results: list[dict[str, Any]] = []
    for job in build_jobs(args.end_date):
        try:
            result = run_job(job, args.output_dir, dry_run=args.dry_run)
        except Exception as exc:
            result = {
                "slug": job.slug,
                "window_days": job.window_days,
                "end_date": job.end_date,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
            if args.fail_fast:
                results.append(result)
                write_manifest(args.output_dir, args.end_date, results)
                print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
                return 1
        results.append(result)
        print(json.dumps(result, ensure_ascii=False))

    manifest_path = write_manifest(args.output_dir, args.end_date, results)
    print(f"manifest={manifest_path}")
    return 0 if all(item.get("status") != "error" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
