"""Small Prometheus-compatible query metrics without extra dependencies."""
from __future__ import annotations

from collections import defaultdict
import threading

_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
_lock = threading.Lock()
_totals: dict[tuple[str, str], int] = defaultdict(int)
_duration_sum: dict[tuple[str, str], float] = defaultdict(float)
_duration_buckets: dict[tuple[str, str, float], int] = defaultdict(int)


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _labels(endpoint: str, query_type: str, extra: str = "") -> str:
    base = f'endpoint="{_escape_label(endpoint)}",query_type="{_escape_label(query_type)}"'
    if extra:
        base = f"{base},{extra}"
    return "{" + base + "}"


def record_query(endpoint: str, query_type: str, duration_seconds: float) -> None:
    """Record one completed HTTP query."""

    key = (endpoint, query_type)
    with _lock:
        _totals[key] += 1
        _duration_sum[key] += max(duration_seconds, 0.0)
        for bucket in _BUCKETS:
            if duration_seconds <= bucket:
                _duration_buckets[(endpoint, query_type, bucket)] += 1


def render_prometheus() -> str:
    """Render metrics in Prometheus text exposition format."""

    lines = [
        "# HELP fq_query_total Total HTTP queries by endpoint and query type.",
        "# TYPE fq_query_total counter",
    ]
    with _lock:
        total_items = sorted(_totals.items())
        for (endpoint, query_type), count in total_items:
            lines.append(f"fq_query_total{_labels(endpoint, query_type)} {count}")

        lines.extend(
            [
                "# HELP fq_query_duration_seconds HTTP query duration.",
                "# TYPE fq_query_duration_seconds histogram",
            ]
        )
        for (endpoint, query_type), count in total_items:
            cumulative = 0
            for bucket in _BUCKETS:
                cumulative = _duration_buckets.get((endpoint, query_type, bucket), cumulative)
                lines.append(
                    "fq_query_duration_seconds_bucket"
                    f"{_labels(endpoint, query_type, f'le=\"{bucket:g}\"')} {cumulative}"
                )
            lines.append(
                "fq_query_duration_seconds_bucket"
                f"{_labels(endpoint, query_type, 'le=\"+Inf\"')} {count}"
            )
            duration_sum = _duration_sum[(endpoint, query_type)]
            lines.append(f"fq_query_duration_seconds_sum{_labels(endpoint, query_type)} {duration_sum:.6f}")
            lines.append(f"fq_query_duration_seconds_count{_labels(endpoint, query_type)} {count}")
    lines.append("")
    return "\n".join(lines)


def reset_query_metrics() -> None:
    """Reset metrics for focused tests."""

    with _lock:
        _totals.clear()
        _duration_sum.clear()
        _duration_buckets.clear()
