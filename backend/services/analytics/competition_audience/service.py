"""previewCandidates / saveDraft transport. HTTP registration is not in this module."""

from __future__ import annotations

import json
from uuid import uuid4

from pydantic import ValidationError

from backend.contracts.competition_c0 import (
    CombineOp,
    CompetitionActionDraft,
    CompetitionCandidateSet,
    CompetitionCohortSpec,
    DraftStatus,
)
from backend.services.analytics.access import AnalyticsPrincipal
from backend.services.analytics.competition_audience.candidates import (
    CombineResult,
    combine_rules,
    classify_pinned,
    partition_rules,
    to_candidate_set,
)
from backend.services.analytics.competition_audience.cohort import pin_membership, validate_cohort_windows
from backend.services.analytics.competition_audience.drafts import build_draft, expire_draft
from backend.services.analytics.competition_audience.errors import (
    CompetitionAudienceError,
    conflict,
    forbidden,
    invalid,
    unauthenticated,
)
from backend.services.analytics.competition_audience.features import (
    CohortFeatureSource,
    FixtureFeatureSource,
    ObservationEvent,
)
from backend.services.analytics.competition_audience.store import AudienceStore

CAP_READ = "cohort:read"
CAP_DRAFT = "draft:write"


def _payload(value) -> dict:
    if not isinstance(value, dict) or isinstance(value, bool):
        raise invalid("payload 必须是对象。", param="payload")
    return value


def _authorize(principal, capability: str, scope: str, *, param: str) -> AnalyticsPrincipal:
    if principal is None:
        raise unauthenticated()
    if not isinstance(principal, AnalyticsPrincipal):
        raise unauthenticated()
    if capability not in principal.capabilities or scope not in principal.data_scopes:
        raise forbidden(param=param)
    return principal


def _scope(payload: dict) -> str:
    scope = payload.get("permission_scope")
    if type(scope) is not str or not scope:
        cohort = payload.get("cohort")
        if isinstance(cohort, dict):
            scope = cohort.get("permission_scope")
        elif isinstance(cohort, CompetitionCohortSpec):
            scope = cohort.permission_scope
    if type(scope) is not str or not scope:
        raise invalid("需要 permission_scope。", param="permission_scope")
    return scope


def _cohort_spec(payload: dict) -> tuple[CompetitionCohortSpec, list[dict]]:
    raw = payload.get("cohort") if "cohort" in payload else payload
    if isinstance(raw, CompetitionCohortSpec):
        accepted, rejected = partition_rules(list(raw.rules))
        if not accepted:
            return raw, rejected
        if rejected:
            return raw.model_copy(update={"rules": accepted}), rejected
        return raw, rejected
    if not isinstance(raw, dict):
        raise invalid("人群规则不合法。", param="cohort")
    accepted, rejected = partition_rules(raw.get("rules"))
    body = dict(raw)
    if accepted:
        body["rules"] = [item.model_dump(mode="json") for item in accepted]
    elif rejected:
        raise CompetitionAudienceError(
            422, rejected[0]["error"]["code"], rejected[0]["error"]["message"],
            param=rejected[0]["error"].get("param"),
            doc_ref=rejected[0]["error"].get("doc_ref"),
            request_id=rejected[0]["error"].get("request_id"),
        )
    try:
        return CompetitionCohortSpec.model_validate(body), rejected
    except ValidationError as error:
        raise invalid("人群规则不合法。", param="cohort") from error


def _combine(payload: dict) -> CombineOp:
    raw = payload.get("combine", CombineOp.AND.value)
    try:
        return CombineOp(raw)
    except ValueError as error:
        raise invalid("combine 必须是 AND 或 OR。", param="combine") from error


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _origin_map(pinned: tuple[str, ...], bundle_rows) -> dict[str, tuple[str, tuple[str, ...]]]:
    out: dict[str, tuple[str, tuple[str, ...]]] = {}
    by_key = {row.customer_key: row for row in bundle_rows}
    for key in pinned:
        row = by_key.get(key)
        if row is None:
            continue
        channel = row.first_channel or row.last_channel or ""
        products = tuple(row.first_product_ids or row.last_product_ids)
        out[key] = (channel, products)
    return out


def _events_by_key(events: tuple[ObservationEvent, ...]) -> dict[str, tuple[ObservationEvent, ...]]:
    grouped: dict[str, list[ObservationEvent]] = {}
    for event in events:
        grouped.setdefault(event.customer_key, []).append(event)
    return {key: tuple(items) for key, items in grouped.items()}


class CompetitionAudienceService:
    def __init__(self, directory, feature_source: CohortFeatureSource | None = None):
        self.store = AudienceStore(directory)
        self.features = feature_source or FixtureFeatureSource()

    def _visible_cohort(self, principal: AnalyticsPrincipal, cohort_id: str, scope: str):
        row = self.store.get_cohort(cohort_id)
        if row is None or row["permission_scope"] != scope or scope not in principal.data_scopes:
            raise forbidden(param="cohort_id")
        return row

    def pin_cohort(self, principal, payload) -> tuple[CompetitionCohortSpec, tuple[str, ...], str]:
        body = _payload(payload)
        spec, _rejected_at_pin = _cohort_spec(body)
        owner = _authorize(principal, CAP_READ, spec.permission_scope, param="cohort_id")
        validate_cohort_windows(spec)
        existing = self.store.get_cohort(spec.cohort_id)
        source_ref = body.get("source_result_ref")
        if existing is not None:
            if existing["permission_scope"] != spec.permission_scope or spec.permission_scope not in owner.data_scopes:
                raise forbidden(param="cohort_id")
            pinned = tuple(json.loads(existing["pinned_json"]))
            previous = json.loads(existing["spec_json"])
            changed_rule = (
                existing["rule_version"] != spec.enrollment_rule_version
                or previous.get("rules") != spec.model_dump(mode="json").get("rules")
            )
            changed_source = existing["source_tense"] != spec.source_tense.value or (
                source_ref is not None
                and existing["source_result_ref"] not in (None, source_ref)
            )
            self.store.put_cohort(
                spec, pinned, existing["membership_digest"],
                source_result_ref=source_ref or existing["source_result_ref"],
            )
            if changed_rule:
                self._expire_cohort_drafts(spec.cohort_id, "RULE_CHANGED")
            elif changed_source:
                self._expire_cohort_drafts(spec.cohort_id, "SOURCE_CHANGED")
            return spec, pinned, existing["membership_digest"]
        pinned, digest = pin_membership(spec, self.features)
        self.store.put_cohort(spec, pinned, digest, source_result_ref=source_ref)
        return spec, pinned, digest

    def preview_candidates(self, principal, payload) -> dict:
        body = _payload(payload)
        spec, rejected_rules = _cohort_spec(body)
        owner = _authorize(principal, CAP_READ, spec.permission_scope, param="customer_key")
        if body.get("auto_send") not in (None, False):
            raise invalid("候选预览不得自动发送。", param="auto_send")
        source_ref = body.get("source_result_ref")
        if type(source_ref) is not str or not source_ref:
            raise invalid("需要 source_result_ref。", param="source_result_ref")
        combine = _combine(body)
        if rejected_rules and combine is CombineOp.AND:
            raise CompetitionAudienceError(
                422, rejected_rules[0]["error"]["code"], rejected_rules[0]["error"]["message"],
                param=rejected_rules[0]["error"].get("param"),
                doc_ref=rejected_rules[0]["error"].get("doc_ref"),
                request_id=rejected_rules[0]["error"].get("request_id"),
            )
        spec, pinned, _digest = self.pin_cohort(owner, {**body, "cohort": spec, "source_result_ref": source_ref})
        bundle = self.features.load_cohort_features(
            permission_scope=spec.permission_scope,
            customer_keys=pinned,
            as_of=spec.as_of,
            timezone="Asia/Shanghai",
            history_scope={"kind": "ALL", "channel_ids": [], "product_ids": []},
            sample_mode="INCLUDE",
            member_mode="as_of_or_unknown",
            source_tense=spec.source_tense.value,
            data_version=spec.enrollment_rule_version,
            rule_version=spec.enrollment_rule_version,
        )
        events = self.features.load_observation_events(
            permission_scope=spec.permission_scope,
            customer_keys=pinned,
            window=spec.observation_window,
            timezone="Asia/Shanghai",
            history_scope={"kind": "ALL", "channel_ids": [], "product_ids": []},
            sample_mode="INCLUDE",
            source_tense=spec.source_tense.value,
            published_at=spec.published_at,
        )
        classified = classify_pinned(pinned, _origin_map(pinned, bundle.rows), _events_by_key(events))
        combined = combine_rules(spec, classified, pinned, combine)
        if rejected_rules:
            combined = CombineResult(
                "PARTIAL" if combined.keys else "FAILED",
                combined.keys,
                combined.explanations,
                tuple(rejected_rules) + combined.rejected,
            )
        if combined.status == "FAILED":
            raise CompetitionAudienceError(
                422, combined.rejected[0]["error"]["code"], combined.rejected[0]["error"]["message"],
                param=combined.rejected[0]["error"].get("param"),
                doc_ref=combined.rejected[0]["error"].get("doc_ref"),
                request_id=combined.rejected[0]["error"].get("request_id"),
            )
        candidate_set_id = body.get("candidate_set_id") or _new_id("cand")
        candidates = to_candidate_set(
            candidate_set_id=candidate_set_id, spec=spec, source_result_ref=source_ref,
            combine=combine, result=combined,
        )
        self.store.put_candidates(candidates)
        stored = self.store.get_cohort(spec.cohort_id)
        out = {
            "status": combined.status,
            "candidates": candidates,
            "pinned_count": len(pinned),
            "membership_digest": stored["membership_digest"] if stored else None,
            "member_history_status": "UNKNOWN",
            "auto_send": False,
            "rejected": list(combined.rejected),
        }
        return out

    def get_candidates(self, principal, candidate_set_id: str, *, permission_scope: str) -> CompetitionCandidateSet:
        owner = _authorize(principal, CAP_READ, permission_scope, param="customer_key")
        row = self.store.get_candidates(candidate_set_id)
        if row is None or row["permission_scope"] != permission_scope or permission_scope not in owner.data_scopes:
            raise forbidden(param="customer_key")
        return CompetitionCandidateSet.model_validate(json.loads(row["payload_json"]))

    def save_draft(self, principal, payload) -> CompetitionActionDraft:
        body = _payload(payload)
        scope = _scope(body)
        owner = _authorize(principal, CAP_DRAFT, scope, param="draft_id")
        if body.get("auto_send") not in (None, False):
            raise invalid("行动草稿不得自动发送。", param="auto_send")
        candidate_set_id = body.get("candidate_set_id")
        if type(candidate_set_id) is not str or not candidate_set_id:
            raise invalid("需要 candidate_set_id。", param="candidate_set_id")
        candidates = self.get_candidates(owner, candidate_set_id, permission_scope=scope)
        claimed_owner = body.get("owner_id") or owner.actor_id
        if claimed_owner != owner.actor_id:
            raise forbidden(param="owner_id", message="当前身份无权以他人名义保存草稿。")
        draft_id = body.get("draft_id") or _new_id("draft")
        current = self.store.latest_draft(draft_id)
        copy_only = bool(body.get("copy_only_change"))
        if current is None:
            draft = build_draft(
                draft_id=draft_id, version=1, candidates=candidates,
                owner_id=owner.actor_id, payload=body,
            )
            self.store.insert_draft(draft, scope)
            return draft
        if current["permission_scope"] != scope or current["owner"] != owner.actor_id:
            raise forbidden(param="draft_id")
        base = body.get("base_version", current["version"])
        if base != current["version"]:
            raise conflict()
        latest = CompetitionActionDraft.model_validate(json.loads(current["payload_json"]))
        if copy_only:
            merged = {
                **latest.model_dump(mode="json"),
                "control_design": body.get("control_design", latest.control_design),
                "stop_condition": body.get("stop_condition", latest.stop_condition),
                "channel": body.get("channel", latest.channel),
                "product_id": body.get("product_id", latest.product_id),
                "unknowns": body.get("unknowns", latest.unknowns),
                "reviewer_id": body.get("reviewer_id", latest.reviewer_id),
                "review_by": body.get("review_by", latest.review_by.isoformat() if latest.review_by else None),
                "budget_cap_minor": body.get("budget_cap_minor", latest.budget_cap_minor),
            }
            status = latest.status
            reason = latest.expired_reason
            draft = build_draft(
                draft_id=draft_id, version=latest.version + 1, candidates=candidates,
                owner_id=owner.actor_id, payload=merged, status=status,
                expired_reason=reason, copy_only_change=reason is None,
            )
        else:
            draft = build_draft(
                draft_id=draft_id, version=latest.version + 1, candidates=candidates,
                owner_id=owner.actor_id, payload=body,
            )
        self.store.insert_draft(draft, scope)
        return draft

    def get_draft(self, principal, draft_id: str, *, permission_scope: str) -> CompetitionActionDraft:
        owner = _authorize(principal, CAP_DRAFT, permission_scope, param="draft_id")
        row = self.store.latest_draft(draft_id)
        if row is None or row["permission_scope"] != permission_scope or row["owner"] != owner.actor_id:
            raise forbidden(param="draft_id")
        return CompetitionActionDraft.model_validate(json.loads(row["payload_json"]))

    def _expire_cohort_drafts(self, cohort_id: str, reason: str) -> None:
        for row in self.store.drafts_for_cohort(cohort_id):
            current = self.store.latest_draft(row["draft_id"])
            if current is None or current["status"] == DraftStatus.EXPIRED.value:
                continue
            draft = CompetitionActionDraft.model_validate(json.loads(current["payload_json"]))
            expired = expire_draft(draft, reason)
            self.store.insert_draft(expired, current["permission_scope"])


def preview_candidates(principal, payload, *, service: CompetitionAudienceService | None = None, directory=None):
    active = service or CompetitionAudienceService(directory)
    return active.preview_candidates(principal, payload)


def save_draft(principal, payload, *, service: CompetitionAudienceService | None = None, directory=None):
    active = service or CompetitionAudienceService(directory)
    return active.save_draft(principal, payload)
