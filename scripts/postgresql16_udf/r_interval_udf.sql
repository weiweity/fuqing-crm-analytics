-- L4.74 PostgreSQL 16 R-interval UDF.
-- SSOT verified against backend/semantic/segments.py:R_INTERVALS.
CREATE SCHEMA IF NOT EXISTS crm_semantic;

CREATE OR REPLACE FUNCTION crm_semantic.r_interval(last_pay_date date, as_of_date date)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN last_pay_date IS NULL OR as_of_date IS NULL THEN NULL
        WHEN as_of_date < last_pay_date THEN '近1个月已购客'
        WHEN as_of_date - last_pay_date BETWEEN 0 AND 30 THEN '近1个月已购客'
        WHEN as_of_date - last_pay_date BETWEEN 31 AND 90 THEN '近2-3个月已购客'
        WHEN as_of_date - last_pay_date BETWEEN 91 AND 180 THEN '近4-6月已购客'
        WHEN as_of_date - last_pay_date BETWEEN 181 AND 365 THEN '近7-12个月已购客'
        WHEN as_of_date - last_pay_date BETWEEN 366 AND 730 THEN '近13个月-近24个月已购客'
        ELSE '2年外已购客'
    END;
$$;
