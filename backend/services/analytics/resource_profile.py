"""Explicit B0 resource inputs; deliberately independent of backend.config."""

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MIB = 1024 * 1024


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def content_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class B0ResourceProfile(BaseModel):
    """Required retention caps cannot inherit defaults from the old BI.

    Defaults retain the approved B0 ceilings. Smaller explicit limits support
    bounded fault tests; no override can increase those ceilings. RSS remains
    a sampled threshold, not an instantaneous kernel memory hard limit.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: Literal["b0-run-resource/v1"] = "b0-run-resource/v1"
    active_workers: Literal[1] = 1
    max_queued: Annotated[int, Field(ge=1, le=8)] = 8
    max_actor_inflight: Annotated[int, Field(ge=1, le=3)] = 3
    run_timeout_ms: Annotated[int, Field(ge=1, le=120000)] = 120000
    query_timeout_ms: Annotated[int, Field(ge=1, le=30000)] = 30000
    max_tool_steps: Annotated[int, Field(ge=1, le=8)] = 8
    max_dispatch_attempts: Annotated[int, Field(ge=1, le=3)] = 3
    duckdb_memory_mib: Annotated[int, Field(ge=16, le=512)] = 512
    duckdb_threads: Literal[2] = 2
    worker_temp_mib: Annotated[int, Field(ge=1, le=512)] = 512
    worker_rss_observation_mib: Annotated[int, Field(ge=32, le=1024)] = 1024
    max_result_bytes: Annotated[int, Field(ge=1024, le=MIB)] = MIB
    max_event_bytes: Annotated[int, Field(ge=1024, le=65536)] = 65536
    max_run_event_bytes: Annotated[int, Field(ge=65536, le=4 * MIB)] = 4 * MIB
    # Admission reserves enough space for every accepted run to finish. Never
    # delete evidence or idempotency keys to make room for a new request.
    state_high_water_bytes: Annotated[int, Field(ge=16 * MIB, le=1024 * MIB)]
    max_retained_runs: Annotated[int, Field(ge=1, le=10000)]
    max_retained_runs_per_actor: Annotated[int, Field(ge=1, le=10000)]
    max_retained_conversations: Annotated[int, Field(ge=1, le=1000)]
    max_retained_conversations_per_actor: Annotated[int, Field(ge=1, le=1000)]
    max_cancel_keys_per_run: Annotated[int, Field(ge=1, le=16)] = 16

    @field_validator("active_workers", "duckdb_memory_mib", "duckdb_threads", "worker_temp_mib",
                     "worker_rss_observation_mib", mode="before")
    @classmethod
    def exact_integer_setting(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("resource settings must be integers")
        return value

    @model_validator(mode="after")
    def validate_totals(self):
        if self.max_retained_runs_per_actor > self.max_retained_runs:
            raise ValueError("actor run cap exceeds global cap")
        if self.max_retained_conversations_per_actor > self.max_retained_conversations:
            raise ValueError("actor conversation cap exceeds global cap")
        if self.max_event_bytes > self.max_run_event_bytes:
            raise ValueError("event cap exceeds per-run event cap")
        if self.query_timeout_ms > self.run_timeout_ms:
            raise ValueError("query timeout exceeds run timeout")
        if self.run_reservation_bytes >= self.state_high_water_bytes:
            raise ValueError("state cap cannot reserve a single run")
        return self

    @property
    def run_reservation_bytes(self) -> int:
        return self.max_result_bytes + self.max_run_event_bytes + 256 * 1024

    @property
    def digest(self) -> str:
        return content_hash(self.model_dump(mode="json"))


# Explicit small-fixture retention policy, not environment-derived defaults.
# No automatic pruning. Reaching any cap refuses new work and keeps evidence.
B0_SMALL_FIXTURE_PROFILE = {
    "state_high_water_bytes": 256 * MIB,
    "max_retained_runs": 40,
    "max_retained_runs_per_actor": 20,
    "max_retained_conversations": 20,
    "max_retained_conversations_per_actor": 10,
}
