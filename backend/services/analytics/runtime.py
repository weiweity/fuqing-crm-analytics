"""Single FastAPI-owned dispatcher; DSH remains the sole model loop.

The Host bridge proves request-correlated journal outcomes AND whenIdle/flush.
No stream, browser acknowledgement, PID probe or model text is exit evidence.
"""

import fcntl
import json
import logging
import os
import sqlite3
import stat
from dataclasses import asdict
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

from backend.contracts.analytics_query_run import (
    QUERY_RUN_FAMILY, AnalyticsQueryNativeReceipt,
)
from backend.contracts.analytics_first_purchase_kernel import FirstPurchaseNativeReceipt

from .access import AnalyticsError
from .jobs import ExecutionObservation, TERMINAL


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError("B0 bridge redirects are forbidden")


class HostBridge:
    def __init__(self, origin: str, token: str):
        if origin != "http://127.0.0.1:4316" or len(token) < 32:
            raise ValueError("explicit loopback B0 bridge configuration required")
        self.origin, self.token = origin, token
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())

    def call(self, operation, payload):
        if operation not in {"health", "dispatch", "observe", "cancel"}:
            raise ValueError("unsupported bridge operation")
        request = Request(self.origin + "/" + operation, data=json.dumps(payload).encode(), method="POST",
                          headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.token})
        with self.opener.open(request, timeout=3) as response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError("bridge response exceeds B0 bound")
            return json.loads(raw)


class RunDispatcher:
    def __init__(self, store, resolve_actor, bridge, *, workers=None):
        self.store, self.resolve_actor, self.bridge = store, resolve_actor, bridge
        self.workers = workers
        self._lock = None
        self.ready = False
        self.last_error = None

    def start(self):
        """One owner across API restarts; never adopt or unlink foreign locks."""
        fd = os.open(self.store.directory / ".dispatcher.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
                raise ValueError("invalid dispatcher lock")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.store.recover()  # No resend, new attempt or budget reset.
        except BaseException:
            os.close(fd)
            raise
        self._lock = fd

    def close(self):
        self.ready = False
        if self._lock is not None:
            os.close(self._lock)
            self._lock = None

    def _apply(self, work, evidence):
        intent = work["intent"]
        fields = ("run_id", "attempt_id", "session_id", "request_id")
        if any(evidence.get(key) != getattr(intent, key) for key in fields):
            raise ValueError("uncorrelated runtime observation")
        exited = evidence.get("execution_exited")
        outcome = evidence.get("outcome")
        if type(exited) is not bool or outcome not in {"RUNNING", "UNKNOWN", "SUCCEEDED", "FAILED", "CANCELLED", "NEEDS_INPUT"}:
            raise ValueError("invalid runtime observation")
        primary = None
        error = None
        if outcome == "SUCCEEDED":
            # The tool can finish during the Host's whenIdle wait. Refresh the
            # committed step read model AFTER receiving the journal proof.
            work = self.store.runtime_work(session_id=intent.session_id, request_id=intent.request_id)[0]
            calls = evidence.get("successful_call_ids")
            if not isinstance(calls, list) or any(not isinstance(call, str) for call in calls):
                raise ValueError("invalid native tool evidence")
            primary = next((work["steps"][call] for call in reversed(calls) if call in work["steps"]), None)
            if primary is None or work["pending_steps"]:
                outcome, error = "FAILED", "TOOL_FAILED"
        elif outcome == "FAILED":
            error = evidence.get("error_code", "MODEL_FAILED")
            if error not in {"MODEL_FAILED", "EXECUTION_UNKNOWN"}:
                raise ValueError("unsupported native failure evidence")
        self.store.observe(self.resolve_actor(work["owner"]), ExecutionObservation(
            *(getattr(intent, key) for key in fields), exited, outcome, primary, error))

    def tick(self):
        if self._lock is None:
            raise RuntimeError("dispatcher is not started")
        try:
            self._tick()
            self.last_error = None
        except (AnalyticsError, sqlite3.DatabaseError):
            # A held SQLite writer must pause new admissions, not terminate the
            # background task forever with an old ready=True value. Next tick
            # reconciles original intents; it never retries external dispatch.
            self.ready = False
            if self.last_error != "STATE_UNAVAILABLE":
                logging.getLogger(__name__).warning("B0 state unavailable; new dispatch paused until reconciliation")
            self.last_error = "STATE_UNAVAILABLE"

    def _tick(self):
        if self.workers is not None:
            self.workers.recover()
        try:
            self.ready = self.bridge.call("health", {}).get("ready") is True
        except Exception:
            self.ready = False
        self.store.enforce_deadlines()
        work = self.store.runtime_work()
        for item in work:
            intent = item["intent"]
            payload = asdict(intent)
            try:
                evidence = self.bridge.call("observe", payload)
                self._apply(item, evidence)
                # Re-resolve permissions and inspect state after observe; a
                # revoked actor requests stop before another tool can execute.
                current = self.store.runtime_work(session_id=intent.session_id, request_id=intent.request_id)[0]
                if current["cancel_requested"] and current["status"] not in {"CANCELLED", "FAILED", "SUCCEEDED", "NEEDS_INPUT"}:
                    self.bridge.call("cancel", payload)  # Receipt is NOT exit.
            except Exception:
                self.ready = False
                self.store.observe(self.resolve_actor(item["owner"]), ExecutionObservation(
                    intent.run_id, intent.attempt_id, intent.session_id, intent.request_id, False, "UNKNOWN"))
        if not self.ready:
            return
        intent = self.store.claim_next(self.resolve_actor)
        if intent is None:
            return
        # Persisted dispatch intent precedes this external call. Even an
        # ambiguous receipt is reconciled read-only; never blindly call twice.
        try:
            receipt = self.bridge.call("dispatch", asdict(intent))
            if receipt.get("accepted") is not True:
                raise ValueError("dispatch was not accepted")
        except Exception:
            item = self.store.runtime_work(session_id=intent.session_id, request_id=intent.request_id)[0]
            self.store.observe(self.resolve_actor(item["owner"]), ExecutionObservation(
                intent.run_id, intent.attempt_id, intent.session_id, intent.request_id, False, "UNKNOWN"))


def execute_native_fixture(store, resolve_actor, session_id, request_id, call_id, query, *, workers):
    """Trusted tool context lookup, never 'whatever run is currently active'."""
    matches = store.runtime_work(session_id=session_id, request_id=request_id)
    if len(matches) != 1:
        raise AnalyticsError(409, "UNBOUND_NATIVE_REQUEST", "当前原生请求没有已登记的任务绑定。")
    work = matches[0]
    principal = resolve_actor(work["owner"])
    if principal is None:
        raise AnalyticsError(403, "FORBIDDEN", "当前任务身份已失效。")
    intent = work["intent"]
    step = store.reserve_step(principal, intent.run_id, intent.attempt_id, call_id, query=query)
    if step.disposition == "PENDING":
        raise AnalyticsError(409, "STEP_PENDING", "原工具步骤尚未确认，不能重复执行。")
    result = (workers.execute(principal, intent, step) if step.disposition == "EXECUTE"
              else store.step_result(principal, intent.run_id, intent.attempt_id, step.step_id))
    return {"step_id": step.step_id, "disposition": step.disposition, "result": {
        "schema_version": "analytics-b0/v1", "answer_mode": "STUB", "data_source": "SYNTHETIC_FIXTURE",
        "fixture_id": result.fixture_id, "data_as_of": result.data_as_of, "channel": "合成渠道 A",
        "customers": result.facts.customers, "repeat_customers": result.facts.repeat_customers,
        "repeat_rate": result.facts.repeat_ratio,
    }}


def execute_native_query(store, resolve_actor, session_id, request_id, call_id, query_request, *, workers):
    """Trusted query-tool lookup, never the latest run and never a model-supplied path."""
    if store.family != QUERY_RUN_FAMILY:
        raise AnalyticsError(409, "FAMILY_MISMATCH", "任务合同与当前实例不一致。")
    matches = store.runtime_work(session_id=session_id, request_id=request_id)
    if len(matches) != 1:
        raise AnalyticsError(409, "UNBOUND_NATIVE_REQUEST", "当前原生请求没有已登记的任务绑定。")
    work = matches[0]
    principal = resolve_actor(work["owner"])
    if principal is None:
        raise AnalyticsError(403, "FORBIDDEN", "当前任务身份已失效。")
    intent = work["intent"]
    step = store.reserve_step(principal, intent.run_id, intent.attempt_id, call_id, request=query_request)
    if step.disposition == "PENDING":
        raise AnalyticsError(409, "STEP_PENDING", "原工具步骤尚未确认，不能重复执行。")
    result = (workers.execute(principal, intent, step) if step.disposition == "EXECUTE"
              else store.step_result(principal, intent.run_id, intent.attempt_id, step.step_id))
    return AnalyticsQueryNativeReceipt(
        run_id=intent.run_id, attempt_id=intent.attempt_id, step_id=step.step_id,
        disposition=step.disposition, result=result,
    ).model_dump(mode="json")


def execute_native_first_purchase(store, resolve_actor, session_id, request_id, call_id, query_request, *, workers):
    """Trusted first-purchase tool lookup. Same run for in-flight retry; never a new key."""
    if store.family != "first_purchase":
        raise AnalyticsError(409, "FAMILY_MISMATCH", "任务合同与当前实例不一致。")
    matches = store.runtime_work(session_id=session_id, request_id=request_id)
    if len(matches) != 1:
        raise AnalyticsError(409, "UNBOUND_NATIVE_REQUEST", "当前原生请求没有已登记的任务绑定。")
    work = matches[0]
    principal = resolve_actor(work["owner"])
    if principal is None:
        raise AnalyticsError(403, "FORBIDDEN", "当前任务身份已失效。")
    intent = work["intent"]
    snapshot = store.get(principal, intent.run_id)
    if snapshot.status == "CANCELLED":
        raise AnalyticsError(409, "RUN_CANCELLED", "查询任务已取消，未得到可绑定结果。")
    if snapshot.status == "FAILED":
        raise AnalyticsError(409, "TOOL_FAILED", "查询执行未得到可绑定结果。")
    if snapshot.status in TERMINAL and snapshot.status != "SUCCEEDED":
        raise AnalyticsError(409, "TOOL_FAILED", "查询执行未得到可绑定结果。")
    if snapshot.status == "SUCCEEDED":
        if snapshot.result is None or snapshot.primary_result_ref is None:
            raise AnalyticsError(409, "TOOL_FAILED", "查询执行未得到可绑定结果。")
        return 200, FirstPurchaseNativeReceipt(
            run_id=intent.run_id, request_id=request_id, call_id=call_id,
            attempt_id=intent.attempt_id, step_id=snapshot.primary_result_ref,
            disposition="REUSE_RESULT", run_status=snapshot.status, result=snapshot.result,
        ).model_dump(mode="json")
    if snapshot.status in {"QUEUED", "CANCELLING", "UNKNOWN"} or snapshot.status != "RUNNING":
        return 202, FirstPurchaseNativeReceipt(
            run_id=intent.run_id, request_id=request_id, call_id=call_id,
            attempt_id=intent.attempt_id, disposition="IN_FLIGHT",
            run_status=snapshot.status, result=None,
        ).model_dump(mode="json")
    try:
        step = store.reserve_step(principal, intent.run_id, intent.attempt_id, call_id, request=query_request)
    except AnalyticsError as error:
        if error.status == 409 and error.code in {"CONFLICT", "STEP_PENDING"}:
            current = store.get(principal, intent.run_id)
            if current.status in {"CANCELLED"}:
                raise AnalyticsError(409, "RUN_CANCELLED", "查询任务已取消，未得到可绑定结果。") from error
            if current.status in {"FAILED"}:
                raise AnalyticsError(409, "TOOL_FAILED", "查询执行未得到可绑定结果。") from error
            return 202, FirstPurchaseNativeReceipt(
                run_id=intent.run_id, request_id=request_id, call_id=call_id,
                attempt_id=intent.attempt_id, disposition="IN_FLIGHT",
                run_status=current.status, result=None,
            ).model_dump(mode="json")
        raise
    if step.disposition == "PENDING":
        return 202, FirstPurchaseNativeReceipt(
            run_id=intent.run_id, request_id=request_id, call_id=call_id,
            attempt_id=intent.attempt_id, disposition="IN_FLIGHT",
            run_status="RUNNING", result=None,
        ).model_dump(mode="json")
    result = (workers.execute(principal, intent, step) if step.disposition == "EXECUTE"
              else store.step_result(principal, intent.run_id, intent.attempt_id, step.step_id))
    snapshot = store.observe(principal, ExecutionObservation(
        intent.run_id, intent.attempt_id, intent.session_id, intent.request_id,
        True, "SUCCEEDED", step.step_id,
    ))
    return 200, FirstPurchaseNativeReceipt(
        run_id=intent.run_id, request_id=request_id, call_id=call_id,
        attempt_id=intent.attempt_id, step_id=step.step_id,
        disposition=step.disposition, run_status=snapshot.status, result=result,
    ).model_dump(mode="json")
