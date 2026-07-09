-- L4.70: speed up RFM period scans by pay_time + user_id.
-- Idempotent for repeated launchd/manual runs.
CREATE INDEX IF NOT EXISTS idx_orders_pay_time_user_id
    ON orders (pay_time, user_id);
