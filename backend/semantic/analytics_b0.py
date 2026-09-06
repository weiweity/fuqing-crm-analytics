"""The registered B0 synthetic sample, not the B1 channel/cohort metric.

125 invented paid orders: 100 distinct customers, 25 with a second order.
There is no source/customer import, real identifier, cohort inference or ETL.
"""

import hashlib
import json

FIXTURE_ID = "b0-channel-repeat-2026-09-01"
DATA_AS_OF = "2026-09-01"
CHANNEL = "合成渠道 A"
ORDERS = tuple(
    [(i, i, CHANNEL, "2026-08-01") for i in range(1, 101)]
    + [(100 + i, i, CHANNEL, "2026-08-02") for i in range(1, 26)]
)


def rows_digest(rows):
    encoded = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


CONTENT_SHA256 = rows_digest(ORDERS)


def repeat_query():
    """Fixed, parameterized query. No model SQL or inherited FilterSpec."""
    return """WITH customer_orders AS (
        SELECT o.customer_id, count(*) AS order_count
        FROM b0_orders o WHERE o.channel = ? AND o.paid_on <= ?
        GROUP BY o.customer_id
    ) SELECT count(*) AS customers,
        count(*) FILTER (WHERE order_count > 1) AS repeat_customers,
        (count(*) FILTER (WHERE order_count > 1))::DOUBLE / nullif(count(*), 0) AS repeat_ratio
    FROM customer_orders""", [CHANNEL, DATA_AS_OF]
