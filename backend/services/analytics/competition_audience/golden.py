"""Independent T05 10-person gold. Hand-calculated; not A2 C_XCH and not RFM."""

from __future__ import annotations

from types import MappingProxyType

# Last-year F≥4 pinned at 2025-12-31. Observation 2026-08 inclusive.
# Origin channel repurchase 4, switch-channel 2, storewide absent 4.
# ORIGIN_CHANNEL_ABSENT 6 ≠ STOREWIDE_ABSENT 4.
T05_COHORT_ID = "cohort_t05_ly_f4_10"
T05_SCOPE = "scope-brand-a"
T05_SCOPE_B = "scope-brand-b"
T05_RULE_VERSION = "competition-cohort-rule/v1"
T05_DATA_VERSION = "synthetic-t05-cohort-features/v1"
T05_TIMEZONE = "Asia/Shanghai"
T05_ENROLLMENT_START = "2025-01-01"
T05_ENROLLMENT_END = "2025-12-31"
T05_OBSERVATION_START = "2026-08-01"
T05_OBSERVATION_END = "2026-08-31"
T05_ENROLLMENT_AS_OF = "2025-12-31T16:00:00.000000+00:00"
T05_PUBLISHED_AT = "2026-08-31T16:00:00.000000+00:00"
T05_ORIGIN_CHANNEL = "t05-ch-origin"
T05_OTHER_CHANNEL = "t05-ch-other"
T05_ORIGIN_SKU = "t05-sku-origin"
T05_OTHER_SKU = "t05-sku-other"

T05_PINNED = (
    "t05u01", "t05u02", "t05u03", "t05u04", "t05u05",
    "t05u06", "t05u07", "t05u08", "t05u09", "t05u10",
)
T05_ORIGIN_CHANNEL_RETURNED = ("t05u01", "t05u02", "t05u03", "t05u04")
T05_CHANNEL_SWITCHED = ("t05u05", "t05u06")
T05_STOREWIDE_ABSENT = ("t05u07", "t05u08", "t05u09", "t05u10")
T05_ORIGIN_CHANNEL_ABSENT = T05_CHANNEL_SWITCHED + T05_STOREWIDE_ABSENT
T05_ORIGIN_PRODUCT_ABSENT = ("t05u04", "t05u06") + T05_STOREWIDE_ABSENT
T05_OUTSIDER = "t05new"
T05_BRAND_B = "t05b01"

# Enrollment F is evidence only. A8 must not re-filter observation by these counts.
T05_ENROLLMENT_F = MappingProxyType({
    "t05u01": 4, "t05u02": 5, "t05u03": 6, "t05u04": 4, "t05u05": 4,
    "t05u06": 7, "t05u07": 4, "t05u08": 8, "t05u09": 4, "t05u10": 5,
})

T05_HAND_TRACE = MappingProxyType({
    "t05u01": "原渠道原产品回购；发布后晚到退款只影响 REBUILT 分类，不踢出去年名单",
    "t05u02": "原渠道原产品回购",
    "t05u03": "原渠道原产品回购",
    "t05u04": "原渠道回购但换产品 → ORIGIN_PRODUCT_ABSENT",
    "t05u05": "转渠道且原产品仍买到 → ORIGIN_CHANNEL_ABSENT only",
    "t05u06": "转渠道且换产品 → 渠道未回+产品未复购",
    "t05u07": "全店未回",
    "t05u08": "全店未回",
    "t05u09": "全店未回",
    "t05u10": "全店未回",
    T05_OUTSIDER: "今年 F≥4 新人，不得进入去年固定 cohort",
})

assert len(T05_PINNED) == 10
assert len(T05_ORIGIN_CHANNEL_RETURNED) == 4
assert len(T05_CHANNEL_SWITCHED) == 2
assert len(T05_STOREWIDE_ABSENT) == 4
assert len(T05_ORIGIN_CHANNEL_ABSENT) == 6
assert len(T05_ORIGIN_CHANNEL_ABSENT) != len(T05_STOREWIDE_ABSENT)
assert set(T05_ORIGIN_CHANNEL_ABSENT) == set(T05_CHANNEL_SWITCHED) | set(T05_STOREWIDE_ABSENT)
assert set(T05_ORIGIN_CHANNEL_RETURNED).isdisjoint(T05_ORIGIN_CHANNEL_ABSENT)
assert set(T05_PINNED) == set(T05_ORIGIN_CHANNEL_RETURNED) | set(T05_ORIGIN_CHANNEL_ABSENT)

def t05_rule(rule_id: str, kind: str, *, channel_ids=None, product_ids=None) -> dict:
    return {
        "rule_id": rule_id,
        "kind": "NON_REPURCHASE",
        "non_repurchase": kind,
        "member_mark": "UNKNOWN",
        "f_threshold": None,
        "f_grain_status": "UNKNOWN",
        "channel_ids": list(channel_ids or []),
        "product_ids": list(product_ids or []),
    }


def t05_cohort_payload(*, rules=None, **overrides) -> dict:
    payload = {
        "cohort_id": T05_COHORT_ID,
        "enrollment_window": {
            "start_date": T05_ENROLLMENT_START,
            "end_date": T05_ENROLLMENT_END,
        },
        "observation_window": {
            "start_date": T05_OBSERVATION_START,
            "end_date": T05_OBSERVATION_END,
        },
        "enrollment_rule_version": T05_RULE_VERSION,
        "as_of": T05_ENROLLMENT_AS_OF,
        "published_at": T05_PUBLISHED_AT,
        "source_tense": "PUBLISHED_SNAPSHOT",
        "member_history_status": "UNKNOWN",
        "existing_family": "none",
        "rules": rules or [t05_rule("rule_origin_channel", "ORIGIN_CHANNEL_ABSENT")],
        "permission_scope": T05_SCOPE,
        "limitations": [
            "T05 独立金标准：去年 F≥4 十人固定入组，不用今年 RFM 重选。",
            "handoff-audience 不得冒充本 cohort。",
        ],
    }
    payload.update(overrides)
    return payload


T05_GOLD = MappingProxyType({
    "cohort_id": T05_COHORT_ID,
    "permission_scope": T05_SCOPE,
    "pinned": T05_PINNED,
    "origin_channel_returned": T05_ORIGIN_CHANNEL_RETURNED,
    "channel_switched": T05_CHANNEL_SWITCHED,
    "storewide_absent": T05_STOREWIDE_ABSENT,
    "origin_channel_absent": T05_ORIGIN_CHANNEL_ABSENT,
    "origin_product_absent": T05_ORIGIN_PRODUCT_ABSENT,
    "outsider": T05_OUTSIDER,
    "method": "hand_calculated",
    "not_a2_c_xch": True,
    "not_rfm_reselect": True,
})
