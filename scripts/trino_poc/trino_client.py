"""Tiny Trino REST client with no third-party dependency."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class TrinoQueryError(RuntimeError):
    pass


@dataclass(frozen=True)
class TrinoResult:
    columns: list[str]
    rows: list[list[Any]]
    stats: dict[str, Any]


class TrinoRestClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:18080",
        user: str = "fuqing-poc",
        timeout_s: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.user = user
        self.timeout_s = timeout_s

    def wait_until_ready(self, timeout_s: float = 120.0) -> None:
        deadline = time.monotonic() + timeout_s
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"{self.base_url}/v1/info", timeout=5) as res:
                    if res.status == 200:
                        return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
            time.sleep(2)
        raise TimeoutError(f"Trino not ready at {self.base_url}: {last_error}")

    def execute(self, sql: str) -> TrinoResult:
        payload = sql.encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/v1/statement",
            data=payload,
            method="POST",
            headers={
                "Content-Type": "text/plain; charset=utf-8",
                "X-Trino-User": self.user,
                "X-Trino-Source": "fuqing-crm-trino-poc",
            },
        )
        response = self._open_json(req)
        rows: list[list[Any]] = []
        columns: list[str] = []
        stats: dict[str, Any] = {}

        while True:
            if "error" in response:
                error = response["error"]
                message = error.get("message", "unknown Trino error")
                raise TrinoQueryError(message)
            if response.get("columns") and not columns:
                columns = [column["name"] for column in response["columns"]]
            rows.extend(response.get("data") or [])
            stats = response.get("stats") or stats
            next_uri = response.get("nextUri")
            if not next_uri:
                break
            response = self._open_json(urllib.request.Request(next_uri, method="GET"))

        return TrinoResult(columns=columns, rows=rows, stats=stats)

    def _open_json(self, req: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise TrinoQueryError(f"HTTP {exc.code}: {body}") from exc

