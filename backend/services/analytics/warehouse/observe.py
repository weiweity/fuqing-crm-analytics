"""Per-stage warehouse observation. Stage memory is tracemalloc, not ru_maxrss."""

from __future__ import annotations

import resource
import sys
import time
import tracemalloc
from dataclasses import dataclass, field


def process_ru_maxrss_bytes() -> int:
    """Process historical watermark only. Never treat this as a single-stage peak."""
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(value)
    return int(value) * 1024


@dataclass
class StageObservation:
    name: str
    rows_in: int = 0
    rows_out: int = 0
    bytes_read: int = 0
    duration_ns: int = 0
    stage_memory_peak_bytes: int = 0
    memory_method: str = "tracemalloc_reset_peak"
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        payload = {
            "name": self.name,
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "bytes_read": self.bytes_read,
            "duration_ns": self.duration_ns,
            "stage_memory_peak_bytes": self.stage_memory_peak_bytes,
            "memory_method": self.memory_method,
            "uses_ru_maxrss": False,
        }
        if self.extra:
            payload["extra"] = dict(self.extra)
        return payload


@dataclass
class PipelineObservation:
    stages: list[StageObservation] = field(default_factory=list)
    timer_start_mark: str = "before_generate"
    timer_end_mark: str = ""
    total_duration_ns: int = 0
    checkpoint: bool = False
    connection_closed: bool = False
    manifest_written: bool = False
    published: bool = False
    process_ru_maxrss_bytes: int = 0
    process_ru_maxrss_is_stage_peak: bool = False
    resource_limits: dict = field(default_factory=dict)
    marks_ns: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "stages": [stage.to_dict() for stage in self.stages],
            "timer_start_mark": self.timer_start_mark,
            "timer_end_mark": self.timer_end_mark,
            "total_duration_ns": self.total_duration_ns,
            "sum_stage_duration_ns": sum(stage.duration_ns for stage in self.stages),
            "checkpoint": self.checkpoint,
            "connection_closed": self.connection_closed,
            "manifest_written": self.manifest_written,
            "published": self.published,
            "process_ru_maxrss_bytes": self.process_ru_maxrss_bytes,
            "process_ru_maxrss_is_stage_peak": False,
            "process_ru_maxrss_note": "process_watermark_not_stage_peak",
            "resource_limits": dict(self.resource_limits),
            "marks_ns": dict(self.marks_ns),
        }


class StageTimer:
    def __init__(self, observation: PipelineObservation, name: str, *, rows_in: int = 0):
        self.observation = observation
        self.name = name
        self.rows_in = rows_in
        self._started_tracing = False
        self._t0 = 0
        self.stage = StageObservation(name=name, rows_in=rows_in)

    def __enter__(self) -> StageObservation:
        self._started_tracing = not tracemalloc.is_tracing()
        if self._started_tracing:
            tracemalloc.start()
        tracemalloc.reset_peak()
        self._t0 = time.perf_counter_ns()
        return self.stage

    def __exit__(self, exc_type, exc, tb) -> None:
        duration = time.perf_counter_ns() - self._t0
        _current, peak = tracemalloc.get_traced_memory()
        self.stage.duration_ns = duration
        self.stage.stage_memory_peak_bytes = int(peak)
        self.stage.memory_method = "tracemalloc_reset_peak"
        self.stage.rows_in = self.rows_in if self.stage.rows_in == 0 else self.stage.rows_in
        self.observation.stages.append(self.stage)
        if self._started_tracing:
            tracemalloc.stop()
