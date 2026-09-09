"""HTTP orchestration over the shared RunStore and owned physical worker."""
import json
import os
import fcntl
import stat
from backend.contracts.analytics_first_purchase_kernel import FirstPurchaseConversationRequest, FirstPurchaseKernelRequest
from backend.services.analytics.first_purchase.adapter import frozen_request
from backend.services.analytics.jobs import ExecutionObservation
from backend.services.analytics.resource_profile import content_hash, canonical_json
from backend.services.analytics.worker import WorkerManager
from backend.services.analytics.access import AnalyticsError

METHOD_DIGEST = content_hash({"adapter": "first-purchase-json-shared-worker/v1"})

class FirstPurchaseRuntime:
    def __init__(self, store, fixture, resolve_actor):
        if store.family != "first_purchase":
            raise ValueError("first-purchase shared RunStore required")
        self.store = store
        self.fixture = fixture
        self.resolve_actor = resolve_actor
        self.manager = WorkerManager(store, resolve_actor, fixture)

    def submit_and_execute(self, principal, key, request):
        request = frozen_request(request)
        # Validate against the actual sealed fixture before accepting a task.
        from backend.contracts.analytics_first_purchase import bind_resolved_filters
        try:
            bind_resolved_filters(request, self.fixture.validate(), self.store._permission_scope(principal))
        except ValueError as error:
            raise AnalyticsError(422, "INVALID_REQUEST", "首购请求与封存快照不匹配。") from error
        conv = self.store.create_conversation(principal, "first-purchase-http", FirstPurchaseConversationRequest())
        accepted = self.store.accept(principal, conv.conversation_id, key,
            FirstPurchaseKernelRequest(question=canonical_json(request.model_dump(mode="json"))),
            method_package_digest=METHOD_DIGEST, fixture_descriptor=self.fixture.binding_descriptor())
        self.tick()
        return self.store.get(principal, accepted.run_id)

    def tick(self):
        """One bounded queue turn, serialized across runtime instances/processes."""
        fd = os.open(self.store.directory / ".first-purchase-dispatch.lock",
                     os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_uid != os.getuid() or info.st_mode & 0o077):
                raise ValueError("unsafe dispatcher lock")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return  # Another owner will complete or leave recoverable state.
            self._reconcile()
            self.store.enforce_deadlines()
            self._tick_owned()
        finally:
            os.close(fd)

    def _reconcile(self):
        # The dispatcher lock proves no live adapter is still dispatching.
        # A surviving child must independently release its inherited lease.
        self.manager.recover()
        for intent in self.store.recover():
            records = [r for r in self.store.worker_records(active_only=False) if r["run_id"] == intent.run_id]
            if any(r["active_slot"] is not None for r in records):
                continue
            work = next(w for w in self.store.runtime_work() if w["intent"].run_id == intent.run_id)
            actor = self.resolve_actor(work["owner"])
            primary = None
            for record in records:
                if record["state"] == "EXITED" and record["exit_code"] == 0 and record["error_code"] is None:
                    try:
                        self.store.step_result(actor, intent.run_id, intent.attempt_id, record["step_id"])
                        primary = record["step_id"]
                    except AnalyticsError:
                        pass
            self.store.observe(actor, ExecutionObservation(intent.run_id, intent.attempt_id,
                intent.session_id, intent.request_id, True, "SUCCEEDED" if primary else "FAILED",
                primary_result_ref=primary, error_code=None if primary else "EXECUTION_UNKNOWN"))

    def _tick_owned(self):
        intent = self.store.claim_next(self.resolve_actor)
        if intent is None:
            return
        # Resolve from durable work, never a caller-provided identity.
        work = next(item for item in self.store.runtime_work() if item["intent"].run_id == intent.run_id)
        actor = self.resolve_actor(work["owner"])
        step = None
        try:
            request = json.loads(intent.payload["question"])
            step = self.store.reserve_step(actor, intent.run_id, intent.attempt_id, "first-purchase-compute", request=request)
            if step.disposition == "EXECUTE":
                self.manager.execute(actor, intent, step)
            elif step.disposition != "REUSE_RESULT":
                return
            current = self.resolve_actor(work["owner"])
            self.store.observe(current, ExecutionObservation(intent.run_id, intent.attempt_id,
                intent.session_id, intent.request_id, True, "SUCCEEDED", primary_result_ref=step.step_id))
        except AnalyticsError:
            # WorkerManager has already recorded exit before raising. Preserve
            # its durable failure/cancellation; do not invent a successful exit.
            current = self.resolve_actor(work["owner"])
            self.store.observe(current, ExecutionObservation(intent.run_id, intent.attempt_id,
                intent.session_id, intent.request_id, True, "FAILED", error_code="TOOL_FAILED"))

    def get(self, principal, run_id):
        return self.store.get(principal, run_id)

    def cancel(self, principal, run_id, key, version, request):
        return self.store.cancel(principal, run_id, key, version, request)
