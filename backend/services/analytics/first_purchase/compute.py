"""Pure JSON snapshot transform for first-purchase → finished conversion.

fixture in → result out. No DuckDB, HTTP, or worker.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from backend.contracts.analytics_first_purchase import (
    DISPLAY_NAME,
    LIMITATIONS,
    MISSING_PRODUCT_ROLE,
    QUERY_ID,
    QUERY_SCHEMA,
    QUERY_VERSION,
    DATA_VERSION,
    HASH_VERSION,
    METRIC_ID,
    METRIC_VERSION,
    SNAPSHOT_ID,
    FirstPurchaseFacts,
    FirstPurchaseProductRow,
    FirstPurchaseQueryRequest,
    FirstPurchaseResolvedFilters,
    FirstPurchaseResult,
    FirstPurchaseSnapshot,
    bind_resolved_filters,
    encode_key,
    revalidate_model,
    result_to_json,
)


def _net_paid(order, refunds_by_key: dict, as_of: datetime) -> int:
    key = (order.synthetic_user_id, order.order_id)
    refunded = 0
    for refund in refunds_by_key.get(key, ()):
        if refund.refunded_at <= as_of:
            refunded += refund.refund_minor
    return order.gross_paid_minor - refunded


def _order_sort_key(order) -> tuple[datetime, bytes]:
    return (order.paid_at, encode_key(order.order_id))


def _is_after(left, right) -> bool:
    return _order_sort_key(left) > _order_sort_key(right)


def execute_first_purchase_path_query(
    *,
    request: dict,
    snapshot: dict,
    permission_scope: str,
) -> dict[str, Any]:
    parsed_request = revalidate_model(FirstPurchaseQueryRequest, request)
    parsed_snapshot = revalidate_model(FirstPurchaseSnapshot, snapshot)
    resolved = bind_resolved_filters(parsed_request, parsed_snapshot, permission_scope)
    missing = parsed_snapshot.unmapped_product_ids()
    if missing:
        return result_to_json(_rejected_result(resolved, parsed_snapshot, missing))
    facts = _compute_facts(parsed_snapshot, resolved)
    return result_to_json(_ok_result(resolved, parsed_snapshot, facts))


def _ok_result(
    resolved: FirstPurchaseResolvedFilters,
    snapshot: FirstPurchaseSnapshot,
    facts: FirstPurchaseFacts,
) -> FirstPurchaseResult:
    return FirstPurchaseResult(
        schema_version=QUERY_SCHEMA,
        answer_mode="DETERMINISTIC_TOOL",
        query_id=QUERY_ID,
        query_version=QUERY_VERSION,
        metric_id=METRIC_ID,
        metric_version=METRIC_VERSION,
        data_version=DATA_VERSION,
        hash_version=HASH_VERSION,
        contains_real_data=False,
        data_source="SYNTHETIC_SNAPSHOT",
        data_snapshot_ref=SNAPSHOT_ID,
        as_of=snapshot.as_of,
        resolved_filters=resolved,
        filter_hash=resolved.filter_hash,
        status="OK",
        reason_code=None,
        missing_product_ids=[],
        facts=facts,
        limitations=list(LIMITATIONS),
    )


def _rejected_result(
    resolved: FirstPurchaseResolvedFilters,
    snapshot: FirstPurchaseSnapshot,
    missing: tuple[str, ...],
) -> FirstPurchaseResult:
    return FirstPurchaseResult(
        schema_version=QUERY_SCHEMA,
        answer_mode="DETERMINISTIC_TOOL",
        query_id=QUERY_ID,
        query_version=QUERY_VERSION,
        metric_id=METRIC_ID,
        metric_version=METRIC_VERSION,
        data_version=DATA_VERSION,
        hash_version=HASH_VERSION,
        contains_real_data=False,
        data_source="SYNTHETIC_SNAPSHOT",
        data_snapshot_ref=SNAPSHOT_ID,
        as_of=snapshot.as_of,
        resolved_filters=resolved,
        filter_hash=resolved.filter_hash,
        status="REJECTED",
        reason_code=MISSING_PRODUCT_ROLE,
        missing_product_ids=list(missing),
        facts=None,
        limitations=list(LIMITATIONS),
    )


def _compute_facts(
    snapshot: FirstPurchaseSnapshot,
    resolved: FirstPurchaseResolvedFilters,
) -> FirstPurchaseFacts:
    as_of = snapshot.as_of
    roles = snapshot.role_map()
    refunds_by_key: dict[tuple[str, str], list] = defaultdict(list)
    for refund in snapshot.refunds:
        refunds_by_key[(refund.synthetic_user_id, refund.order_id)].append(refund)
    lines_by_key: dict[tuple[str, str], list] = defaultdict(list)
    for line in snapshot.lines:
        lines_by_key[(line.synthetic_user_id, line.order_id)].append(line)

    valid_by_user: dict[str, list] = defaultdict(list)
    for order in snapshot.orders:
        if order.status != "PAID" or order.paid_at > as_of:
            continue
        if _net_paid(order, refunds_by_key, as_of) <= 0:
            continue
        valid_by_user[order.synthetic_user_id].append(order)
    for orders in valid_by_user.values():
        orders.sort(key=_order_sort_key)

    allowed_channels = set(resolved.channel_ids)
    horizon = timedelta(hours=24 * resolved.observation_days)
    enrolled: list[tuple] = []
    for user_id, orders in valid_by_user.items():
        first = orders[0]
        if first.paid_at < resolved.resolved_cohort_start or first.paid_at >= resolved.resolved_cohort_end:
            continue
        if first.channel not in allowed_channels:
            continue
        products = tuple(sorted(
            {line.product_id for line in lines_by_key[(first.synthetic_user_id, first.order_id)]},
            key=encode_key,
        ))
        window_end = first.paid_at + horizon
        converted = False
        for later in orders[1:]:
            if later.paid_at > window_end:
                continue
            if not _is_after(later, first):
                continue
            later_products = lines_by_key[(later.synthetic_user_id, later.order_id)]
            if any(roles[line.product_id] == "finished" for line in later_products):
                converted = True
                break
        enrolled.append((user_id, first, products, as_of >= window_end, converted))

    by_product: dict[str, dict[str, int]] = {}
    cohort_mature = 0
    cohort_immature = 0
    for _user_id, _first, products, is_mature, converted in enrolled:
        if is_mature:
            cohort_mature += 1
        else:
            cohort_immature += 1
        for product_id in products:
            row = by_product.setdefault(
                product_id,
                {"enrolled": 0, "mature": 0, "immature": 0, "converted": 0},
            )
            row["enrolled"] += 1
            if is_mature:
                row["mature"] += 1
                if converted:
                    row["converted"] += 1
            else:
                row["immature"] += 1

    product_rows = []
    for product_id in sorted(by_product, key=encode_key):
        counts = by_product[product_id]
        mature = counts["mature"]
        converted = counts["converted"]
        if mature == 0:
            ratio = None
            empty = "EMPTY_MATURE_COHORT"
        else:
            ratio = converted / mature
            empty = None
        product_rows.append(
            FirstPurchaseProductRow(
                product_id=product_id,
                role=roles[product_id],
                enrolled_count=counts["enrolled"],
                mature_count=mature,
                immature_count=counts["immature"],
                finished_conversion_count=converted if mature else 0,
                finished_conversion_ratio=ratio,
                empty_reason=empty,
            )
        )
    return FirstPurchaseFacts(
        display_name=DISPLAY_NAME,
        currency="CNY",
        amount_unit="minor",
        amount_precision="integer_fen",
        observation_days=resolved.observation_days,
        cohort_enrolled_count=len(enrolled),
        cohort_mature_count=cohort_mature,
        cohort_immature_count=cohort_immature,
        products=product_rows,
    )
