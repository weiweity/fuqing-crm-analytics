"""A2 call face for cohort features. Fixture-backed until A2 delivers; no RFM copy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from backend.contracts.analytics_query import parse_query_date, parse_query_datetime
from backend.contracts.competition_c0 import InclusiveDateRange, SourceTense
from backend.services.analytics.competition_audience.golden import (
    T05_BRAND_B,
    T05_ENROLLMENT_F,
    T05_ENROLLMENT_END,
    T05_ORIGIN_CHANNEL,
    T05_ORIGIN_SKU,
    T05_OTHER_CHANNEL,
    T05_OTHER_SKU,
    T05_OUTSIDER,
    T05_PINNED,
    T05_SCOPE,
    T05_SCOPE_B,
    T05_TIMEZONE,
)

# Independent A9 HTTP snapshot keyed by cohort_id. Does not replace A8 t05u* gold.
A9_T05_COHORT_ID = "cohort_a9_t05_ly_f4_10"
A9_T05_PINNED = (
    "C01", "C02", "C03", "C04", "C05",
    "C06", "C07", "C08", "C09", "C10",
)
A9_T05_ORIGIN_CHANNEL = "CH_HOME"
A9_T05_OTHER_CHANNEL = "CH_OTHER"
A9_T05_ORIGIN_SKU = "P-HOME"
A9_T05_OTHER_SKU = "P-OTHER"

MemberStatus = Literal["true", "false", "unknown"]


def _instant(value) -> datetime:
    return parse_query_datetime(value)


def _day(value) -> date:
    return parse_query_date(value)


def _shanghai_day(instant: datetime) -> date:
    return instant.astimezone(ZoneInfo(T05_TIMEZONE)).date()


def last_complete_shanghai_day(instant: datetime) -> date:
    local = instant.astimezone(ZoneInfo(T05_TIMEZONE))
    if local.hour == 0 and local.minute == 0 and local.second == 0 and local.microsecond == 0:
        return local.date() - timedelta(days=1)
    return local.date()


def in_inclusive_window(instant: datetime, window: InclusiveDateRange) -> bool:
    day = _shanghai_day(instant)
    return window.start_date <= day <= window.end_date


@dataclass(frozen=True)
class ObservationEvent:
    customer_key: str
    order_id: str
    paid_at: datetime
    channel: str
    product_ids: tuple[str, ...]
    net_paid_minor: int
    refunded_at: datetime | None = None
    permission_scope: str = T05_SCOPE


@dataclass(frozen=True)
class CohortFeatureRow:
    customer_key: str
    synthetic_user_id: str
    first_paid_at: datetime | None
    first_channel: str | None
    first_product_ids: tuple[str, ...]
    last_paid_at: datetime | None
    last_channel: str | None
    last_product_ids: tuple[str, ...]
    valid_order_count_as_of: int
    valid_net_amount_as_of: int
    recency_days_as_of: int | None
    member_status_as_of: MemberStatus
    history_truncated: bool
    source_tense: str
    sample_mode_applied: str
    permission_scope: str
    current_is_member_trap: bool | None = None
    amount_unit: str = "minor"
    recency_unit: str = "calendar_day"


@dataclass(frozen=True)
class FeatureBundle:
    rows: tuple[CohortFeatureRow, ...]
    coverage: dict
    member_history_available: bool
    f_grain_status: Literal["UNKNOWN", "W4_ORDER_GRAIN"]
    source_tense: str
    data_version: str
    rule_version: str
    sample_mode_applied: str
    timezone: str


class CohortFeatureSource(Protocol):
    def pinned_enrollment_keys(
        self, *, permission_scope: str, as_of, enrollment_window: InclusiveDateRange,
        source_tense: str, data_version: str, rule_version: str,
    ) -> tuple[str, ...]:
        ...

    def load_cohort_features(
        self, *, permission_scope: str, customer_keys: tuple[str, ...] | None,
        as_of, timezone: str, history_scope: dict, sample_mode: str,
        member_mode: str, source_tense: str, data_version: str, rule_version: str,
    ) -> FeatureBundle:
        ...

    def load_observation_events(
        self, *, permission_scope: str, customer_keys: tuple[str, ...],
        window: InclusiveDateRange, timezone: str, history_scope: dict,
        sample_mode: str, source_tense: str, published_at,
    ) -> tuple[ObservationEvent, ...]:
        ...


def _row(
    key: str, *, scope: str, last_channel: str, last_products: tuple[str, ...],
    f_count: int, as_of: datetime, source_tense: str, sample_mode: str,
    trap_member: bool | None = None,
    origin_channel: str | None = None,
    origin_products: tuple[str, ...] | None = None,
) -> CohortFeatureRow:
    last_paid = datetime(2025, 12, 15, 4, 0, tzinfo=ZoneInfo("UTC"))
    first_paid = datetime(2025, 3, 1, 4, 0, tzinfo=ZoneInfo("UTC"))
    recency = (as_of.date() - last_paid.astimezone(ZoneInfo(T05_TIMEZONE)).date()).days
    origin_ch = origin_channel or T05_ORIGIN_CHANNEL
    origin_skus = origin_products or (T05_ORIGIN_SKU,)
    return CohortFeatureRow(
        customer_key=key,
        synthetic_user_id=key,
        first_paid_at=first_paid,
        first_channel=origin_ch,
        first_product_ids=origin_skus,
        last_paid_at=last_paid,
        last_channel=last_channel,
        last_product_ids=last_products,
        valid_order_count_as_of=f_count,
        valid_net_amount_as_of=f_count * 10000,
        recency_days_as_of=max(recency, 0),
        member_status_as_of="unknown",
        history_truncated=True,
        source_tense=source_tense,
        sample_mode_applied=sample_mode,
        permission_scope=scope,
        current_is_member_trap=trap_member,
    )


def _a9_t05_events() -> tuple[ObservationEvent, ...]:
    def paid(year: int, month: int, day: int) -> datetime:
        return datetime(year, month, day, 12, 0, tzinfo=ZoneInfo(T05_TIMEZONE))

    return (
        ObservationEvent("C01", "a9o-c01", paid(2026, 3, 1), A9_T05_ORIGIN_CHANNEL, (A9_T05_ORIGIN_SKU,), 2700),
        ObservationEvent("C02", "a9o-c02", paid(2026, 3, 4), A9_T05_ORIGIN_CHANNEL, (A9_T05_OTHER_SKU,), 2700),
        ObservationEvent("C03", "a9o-c03", paid(2026, 3, 7), A9_T05_ORIGIN_CHANNEL, (A9_T05_ORIGIN_SKU,), 2700),
        ObservationEvent("C04", "a9o-c04", paid(2026, 3, 10), A9_T05_ORIGIN_CHANNEL, (A9_T05_ORIGIN_SKU,), 2700),
        ObservationEvent("C05", "a9o-c05", paid(2026, 4, 2), A9_T05_OTHER_CHANNEL, (A9_T05_ORIGIN_SKU,), 2700),
        ObservationEvent("C06", "a9o-c06", paid(2026, 4, 5), A9_T05_OTHER_CHANNEL, (A9_T05_OTHER_SKU,), 2700),
    )


def _t05_events() -> tuple[ObservationEvent, ...]:
    def paid(day: int, hour: int = 12) -> datetime:
        return datetime(2026, 8, day, hour, 0, tzinfo=ZoneInfo(T05_TIMEZONE))

    late_refund = _instant("2026-09-02T04:00:00.000000+00:00")
    return (
        ObservationEvent("t05u01", "t05o-u01", paid(5), T05_ORIGIN_CHANNEL, (T05_ORIGIN_SKU,), 8800, late_refund),
        ObservationEvent("t05u02", "t05o-u02", paid(6), T05_ORIGIN_CHANNEL, (T05_ORIGIN_SKU,), 9900),
        ObservationEvent("t05u03", "t05o-u03", paid(7), T05_ORIGIN_CHANNEL, (T05_ORIGIN_SKU,), 7700),
        ObservationEvent("t05u04", "t05o-u04", paid(8), T05_ORIGIN_CHANNEL, (T05_OTHER_SKU,), 6600),
        ObservationEvent("t05u05", "t05o-u05", paid(9), T05_OTHER_CHANNEL, (T05_ORIGIN_SKU,), 5500),
        ObservationEvent("t05u06", "t05o-u06", paid(10), T05_OTHER_CHANNEL, (T05_OTHER_SKU,), 4400),
        ObservationEvent(
            T05_OUTSIDER, "t05o-new1", paid(11), T05_ORIGIN_CHANNEL, (T05_ORIGIN_SKU,), 3300,
        ),
        ObservationEvent(
            T05_OUTSIDER, "t05o-new2", paid(12), T05_ORIGIN_CHANNEL, (T05_ORIGIN_SKU,), 3300,
        ),
        ObservationEvent(
            T05_OUTSIDER, "t05o-new3", paid(13), T05_ORIGIN_CHANNEL, (T05_ORIGIN_SKU,), 3300,
        ),
        ObservationEvent(
            T05_OUTSIDER, "t05o-new4", paid(14), T05_ORIGIN_CHANNEL, (T05_ORIGIN_SKU,), 3300,
        ),
        ObservationEvent(
            T05_BRAND_B, "t05o-b01", paid(15), T05_ORIGIN_CHANNEL, (T05_ORIGIN_SKU,), 2200,
            permission_scope=T05_SCOPE_B,
        ),
    )


class FixtureFeatureSource:
    """Hand fixture implementing the A2 call face. Does not compute RFM."""

    def __init__(self, *, mutate_pin_on_reload: tuple[str, ...] | None = None):
        self._pinned = T05_PINNED
        self._mutate_pin_on_reload = mutate_pin_on_reload
        self._pin_calls = 0
        self.events = _t05_events()
        self._a9_events = _a9_t05_events()

    def pinned_enrollment_keys(
        self, *, permission_scope: str, as_of, enrollment_window: InclusiveDateRange,
        source_tense: str, data_version: str, rule_version: str, cohort_id: str = "",
    ) -> tuple[str, ...]:
        self._pin_calls += 1
        if cohort_id == A9_T05_COHORT_ID:
            if permission_scope != T05_SCOPE:
                return ()
            return A9_T05_PINNED
        if permission_scope == T05_SCOPE_B:
            return (T05_BRAND_B,)
        if permission_scope != T05_SCOPE:
            return ()
        as_of_dt = _instant(as_of)
        if last_complete_shanghai_day(as_of_dt) != _day(T05_ENROLLMENT_END):
            return ()
        if enrollment_window.end_date != _day(T05_ENROLLMENT_END):
            return ()
        if self._pin_calls > 1 and self._mutate_pin_on_reload is not None:
            return self._mutate_pin_on_reload
        seen: list[str] = []
        # Duplicate t05u01 in the raw list to prove enrollment dedup.
        for key in (T05_PINNED[0], *T05_PINNED):
            if key not in seen:
                seen.append(key)
        return tuple(seen)

    def load_cohort_features(
        self, *, permission_scope: str, customer_keys: tuple[str, ...] | None,
        as_of, timezone: str, history_scope: dict, sample_mode: str,
        member_mode: str, source_tense: str, data_version: str, rule_version: str,
    ) -> FeatureBundle:
        if timezone != T05_TIMEZONE:
            raise ValueError("timezone must be Asia/Shanghai")
        as_of_dt = _instant(as_of)
        if permission_scope == T05_SCOPE_B:
            rows = (
                _row(
                    T05_BRAND_B, scope=T05_SCOPE_B, last_channel=T05_ORIGIN_CHANNEL,
                    last_products=(T05_ORIGIN_SKU,), f_count=4, as_of=as_of_dt,
                    source_tense=source_tense, sample_mode=sample_mode,
                ),
            )
        else:
            wanted = customer_keys if customer_keys is not None else T05_PINNED
            if wanted and set(wanted) <= set(A9_T05_PINNED):
                rows = tuple(
                    _row(
                        key, scope=T05_SCOPE, last_channel=A9_T05_ORIGIN_CHANNEL,
                        last_products=(A9_T05_ORIGIN_SKU,), f_count=4, as_of=as_of_dt,
                        source_tense=source_tense, sample_mode=sample_mode,
                        origin_channel=A9_T05_ORIGIN_CHANNEL,
                        origin_products=(A9_T05_ORIGIN_SKU,),
                    )
                    for key in wanted
                    if permission_scope == T05_SCOPE
                )
            else:
                rows = tuple(
                    _row(
                        key, scope=T05_SCOPE, last_channel=T05_ORIGIN_CHANNEL,
                        last_products=(T05_ORIGIN_SKU,),
                        f_count=int(T05_ENROLLMENT_F.get(key, 4)),
                        as_of=as_of_dt, source_tense=source_tense, sample_mode=sample_mode,
                        trap_member=True if key == "t05u01" else None,
                    )
                    for key in wanted
                    if permission_scope == T05_SCOPE
                )
        return FeatureBundle(
            rows=rows,
            coverage={
                "member_history_available": False,
                "history_truncated": True,
                "f_applied_for_reselect": False,
            },
            member_history_available=False,
            f_grain_status="W4_ORDER_GRAIN",
            source_tense=source_tense,
            data_version=data_version,
            rule_version=rule_version,
            sample_mode_applied=sample_mode,
            timezone=timezone,
        )

    def load_observation_events(
        self, *, permission_scope: str, customer_keys: tuple[str, ...],
        window: InclusiveDateRange, timezone: str, history_scope: dict,
        sample_mode: str, source_tense: str, published_at,
    ) -> tuple[ObservationEvent, ...]:
        published = _instant(published_at)
        allowed = set(customer_keys)
        if allowed and allowed <= set(A9_T05_PINNED):
            events = self._a9_events
        else:
            events = self.events
        out: list[ObservationEvent] = []
        for event in events:
            if event.permission_scope != permission_scope:
                continue
            if event.customer_key not in allowed:
                continue
            if not in_inclusive_window(event.paid_at, window):
                continue
            net = event.net_paid_minor
            if event.refunded_at is not None:
                rebuilt = source_tense == SourceTense.REBUILT_FROM_LATEST_CORRECTIONS.value
                if rebuilt or event.refunded_at <= published:
                    net = 0
            if net <= 0:
                continue
            out.append(event)
        return tuple(out)


def default_fixture_source() -> FixtureFeatureSource:
    return FixtureFeatureSource()


def load_cohort_features(
    *,
    permission_scope: str,
    customer_keys,
    as_of,
    timezone: str = T05_TIMEZONE,
    history_scope,
    sample_mode,
    member_mode: str = "as_of_or_unknown",
    source_tense,
    data_version,
    rule_version,
    source: CohortFeatureSource | None = None,
) -> FeatureBundle:
    """A8 call face. Never copies RFM; delegates to A2 source or the T05 fixture."""
    loader = source or default_fixture_source()
    keys = None if customer_keys is None else tuple(customer_keys)
    return loader.load_cohort_features(
        permission_scope=permission_scope,
        customer_keys=keys,
        as_of=as_of,
        timezone=timezone,
        history_scope=history_scope,
        sample_mode=sample_mode,
        member_mode=member_mode,
        source_tense=source_tense,
        data_version=data_version,
        rule_version=rule_version,
    )
