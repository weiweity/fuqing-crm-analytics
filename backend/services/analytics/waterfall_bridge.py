"""Sales-channel WATERFALL facts. Pack-owned; computed.py still attaches them to GSV v5."""
from math import fsum

from backend.contracts.competition_computed import MAX_CHANNEL_CONTRIBUTIONS, GsvChannelBridge


def channel_bridge(connection, periods, orders_by_period, money_unit) -> GsvChannelBridge:
    def unavailable(reason):
        return GsvChannelBridge(status="UNAVAILABLE", unavailable_reason=reason, contributions=[])

    if any(period.gsv is None for period in periods):
        return unavailable("PERIOD_UNAVAILABLE")
    if money_unit.status != "KNOWN":
        return unavailable("MONEY_UNIT_UNKNOWN")
    # The existing order-grain calculator keeps the first line's channel. Do not
    # turn that implementation detail into an attribution claim for mixed orders.
    selected = {order["order_id"] for orders in orders_by_period for order in orders}
    channels_by_order = {}
    for order_id, channel in connection.execute("SELECT DISTINCT order_id, channel FROM orders").fetchall():
        if order_id in selected:
            channels_by_order.setdefault(order_id, set()).add(channel)
    if any(len(channels) != 1 for channels in channels_by_order.values()):
        return unavailable("AMBIGUOUS_ORDER_CHANNEL")
    if any(not isinstance(channel, str) or not channel.strip() or len(channel) > 160
           for channels in channels_by_order.values() for channel in channels):
        return unavailable("INVALID_CHANNEL")
    grouped = []
    for orders in orders_by_period:
        values = {}
        for order in orders:
            values.setdefault(order["channel"], []).append(order["net"])
        grouped.append({channel: round(fsum(amounts), 4) for channel, amounts in values.items()})
    channels = sorted(set(grouped[0]) | set(grouped[1]))
    if len(channels) > MAX_CHANNEL_CONTRIBUTIONS:
        return unavailable("CHANNEL_LIMIT_EXCEEDED")
    contributions = [{"channel": channel, "current_gsv": grouped[0].get(channel, 0),
                      "comparison_gsv": grouped[1].get(channel, 0),
                      "delta": round(grouped[0].get(channel, 0) - grouped[1].get(channel, 0), 4)}
                     for channel in channels]
    return GsvChannelBridge(status="AVAILABLE", unavailable_reason=None, contributions=contributions)
