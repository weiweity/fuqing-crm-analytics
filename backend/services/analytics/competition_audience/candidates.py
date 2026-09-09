"""Three non-repurchase sets, explicit AND/OR, and authorization-scope dedup."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from backend.contracts.competition_c0 import (
    CandidateExplanation,
    CohortRule,
    CombineOp,
    CompetitionCandidateSet,
    CompetitionCohortSpec,
    NonRepurchaseKind,
)
from backend.services.analytics.competition_audience.errors import (
    CompetitionAudienceError,
    invalid,
    unsupported,
)
from backend.services.analytics.competition_audience.features import ObservationEvent
from backend.services.analytics.competition_audience.golden import (
    T05_ORIGIN_CHANNEL,
    T05_ORIGIN_SKU,
)

LIMITATIONS = (
    "观察期未回购候选，不能确定为永久流失。",
    "成员固定在入组 as_of，不得用今年 RFM 重选人。",
    "会员历史 UNKNOWN；handoff-audience 不得冒充本 cohort。",
    "合成 customer_key，不导出真实名单；auto_send 恒为 false。",
)

REASON_ORDER = (
    NonRepurchaseKind.ORIGIN_CHANNEL_ABSENT.value,
    NonRepurchaseKind.ORIGIN_PRODUCT_ABSENT.value,
    NonRepurchaseKind.STOREWIDE_ABSENT.value,
    "ENROLLMENT_SNAPSHOT",
)


@dataclass(frozen=True)
class ClassifiedMember:
    customer_key: str
    origin_channel: str
    origin_product_ids: tuple[str, ...]
    kinds: frozenset[str]


@dataclass(frozen=True)
class CombineResult:
    status: str
    keys: tuple[str, ...]
    explanations: tuple[CandidateExplanation, ...]
    rejected: tuple[dict, ...]


def classify_member(
    customer_key: str,
    origin_channel: str,
    origin_product_ids: tuple[str, ...],
    events: tuple[ObservationEvent, ...],
) -> ClassifiedMember:
    kinds: set[str] = set()
    if not events:
        kinds.add(NonRepurchaseKind.STOREWIDE_ABSENT.value)
        if origin_channel:
            kinds.add(NonRepurchaseKind.ORIGIN_CHANNEL_ABSENT.value)
        if origin_product_ids:
            kinds.add(NonRepurchaseKind.ORIGIN_PRODUCT_ABSENT.value)
        return ClassifiedMember(customer_key, origin_channel, origin_product_ids, frozenset(kinds))
    if origin_channel and not any(item.channel == origin_channel for item in events):
        kinds.add(NonRepurchaseKind.ORIGIN_CHANNEL_ABSENT.value)
    bought: set[str] = set()
    for item in events:
        bought.update(item.product_ids)
    if origin_product_ids and set(origin_product_ids).isdisjoint(bought):
        kinds.add(NonRepurchaseKind.ORIGIN_PRODUCT_ABSENT.value)
    return ClassifiedMember(customer_key, origin_channel, origin_product_ids, frozenset(kinds))


def classify_pinned(
    pinned: tuple[str, ...],
    origin_by_key: dict[str, tuple[str, tuple[str, ...]]],
    events_by_key: dict[str, tuple[ObservationEvent, ...]],
) -> dict[str, ClassifiedMember]:
    out: dict[str, ClassifiedMember] = {}
    for key in pinned:
        channel, products = origin_by_key.get(key, (T05_ORIGIN_CHANNEL, (T05_ORIGIN_SKU,)))
        out[key] = classify_member(key, channel, products, events_by_key.get(key, ()))
    return out


def partition_rules(raw_rules) -> tuple[list[CohortRule], list[dict]]:
    if not isinstance(raw_rules, list) or not raw_rules:
        raise invalid("rules 至少一条。", param="rules")
    accepted: list[CohortRule] = []
    rejected: list[dict] = []
    for item in raw_rules:
        try:
            rule = item if isinstance(item, CohortRule) else CohortRule.model_validate(item)
        except ValidationError:
            payload = item if isinstance(item, dict) else {}
            if payload.get("f_threshold") is not None and payload.get("f_grain_status") == "UNKNOWN":
                error = unsupported("F 粒度 UNKNOWN，拒绝应用 f_threshold。", param="f_threshold")
                rejected.append({"rule_id": payload.get("rule_id") or "rule_unknown", "error": error.to_detail().model_dump(mode="json")})
                continue
            raise invalid("人群规则不合法。", param="rules")
        extra = _reject_rule(rule)
        if extra is not None:
            rejected.append({"rule_id": rule.rule_id, "error": extra.to_detail().model_dump(mode="json")})
            continue
        accepted.append(rule)
    return accepted, rejected


def _reject_rule(rule: CohortRule) -> CompetitionAudienceError | None:
    if rule.f_threshold is not None and rule.f_grain_status == "UNKNOWN":
        return unsupported("F 粒度 UNKNOWN，拒绝应用 f_threshold。", param="f_threshold")
    if rule.kind == "MEMBER_CROSS" and rule.member_mark.value != "UNKNOWN":
        return unsupported("会员历史不存在，拒绝按 MEMBER/NON_MEMBER 筛选。", param="member_mark")
    if rule.kind == "NON_REPURCHASE" and rule.non_repurchase is None:
        return invalid("NON_REPURCHASE 需要 non_repurchase。", param="non_repurchase")
    return None


def _hits_for_rule(rule: CohortRule, classified: dict[str, ClassifiedMember], pinned: tuple[str, ...]) -> set[str]:
    if rule.kind == "ENROLLMENT_SNAPSHOT":
        return set(pinned)
    if rule.kind == "MEMBER_CROSS":
        return set(pinned)
    kind = rule.non_repurchase.value if rule.non_repurchase is not None else ""
    return {key for key, row in classified.items() if kind in row.kinds}


def combine_rules(
    spec: CompetitionCohortSpec,
    classified: dict[str, ClassifiedMember],
    pinned: tuple[str, ...],
    combine: CombineOp,
) -> CombineResult:
    successful: list[tuple[CohortRule, set[str]]] = []
    rejected: list[dict] = []
    for rule in spec.rules:
        error = _reject_rule(rule)
        if error is not None:
            rejected.append({"rule_id": rule.rule_id, "error": error.to_detail().model_dump(mode="json")})
            continue
        successful.append((rule, _hits_for_rule(rule, classified, pinned)))
    if rejected and combine is CombineOp.AND:
        return CombineResult("FAILED", (), (), tuple(rejected))
    if not successful and rejected:
        return CombineResult("FAILED", (), (), tuple(rejected))
    if not successful:
        return CombineResult("SUCCEEDED", (), (), ())
    keys: set[str] = set(successful[0][1])
    if combine is CombineOp.AND:
        for _rule, hits in successful[1:]:
            keys &= hits
    else:
        for _rule, hits in successful[1:]:
            keys |= hits
    ordered = tuple(sorted(keys))
    explanations = []
    for key in ordered:
        reasons: list[str] = []
        for rule, hits in successful:
            if key not in hits:
                continue
            if rule.kind == "NON_REPURCHASE" and rule.non_repurchase is not None:
                label = rule.non_repurchase.value
            else:
                label = rule.kind
            if label not in reasons:
                reasons.append(label)
        reasons.sort(key=lambda item: REASON_ORDER.index(item) if item in REASON_ORDER else 99)
        explanations.append(CandidateExplanation(customer_key=key, reasons=reasons))
    status = "PARTIAL" if rejected else "SUCCEEDED"
    return CombineResult(status, ordered, tuple(explanations), tuple(rejected))


def to_candidate_set(
    *,
    candidate_set_id: str,
    spec: CompetitionCohortSpec,
    source_result_ref: str,
    combine: CombineOp,
    result: CombineResult,
) -> CompetitionCandidateSet:
    limitations = list(LIMITATIONS)
    if not result.keys:
        limitations = ["零候选不得伪造建议名单。", *LIMITATIONS]
    return CompetitionCandidateSet.model_validate({
        "candidate_set_id": candidate_set_id,
        "cohort_id": spec.cohort_id,
        "source_result_ref": source_result_ref,
        "combine": combine.value,
        "unique_count": len(result.keys),
        "customer_keys": list(result.keys),
        "explanations": [item.model_dump(mode="json") for item in result.explanations],
        "auto_send": False,
        "permission_scope": spec.permission_scope,
        "limitations": limitations,
    })
