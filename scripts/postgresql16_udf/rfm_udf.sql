-- L4.74 PostgreSQL 16 RFM semantic UDFs.
CREATE SCHEMA IF NOT EXISTS crm_semantic;

CREATE OR REPLACE FUNCTION crm_semantic.rfm_r_score(last_pay_date date, as_of_date date)
RETURNS integer
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN as_of_date - last_pay_date < 30 THEN 5
        WHEN as_of_date - last_pay_date < 90 THEN 4
        WHEN as_of_date - last_pay_date < 180 THEN 3
        WHEN as_of_date - last_pay_date < 365 THEN 2
        ELSE 1
    END;
$$;

CREATE OR REPLACE FUNCTION crm_semantic.rfm_f_score(order_count bigint)
RETURNS integer
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN order_count >= 5 THEN 5
        WHEN order_count >= 4 THEN 4
        WHEN order_count = 3 THEN 3
        WHEN order_count = 2 THEN 2
        ELSE 1
    END;
$$;

CREATE OR REPLACE FUNCTION crm_semantic.rfm_m_score(gsv numeric)
RETURNS integer
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN gsv >= 1000 THEN 5
        WHEN gsv >= 500 THEN 4
        WHEN gsv >= 300 THEN 3
        WHEN gsv >= 100 THEN 2
        ELSE 1
    END;
$$;

CREATE OR REPLACE FUNCTION crm_semantic.rfm_segment(r_score integer, f_score integer, m_score integer)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '重要价值客户'
        WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN '重要保持客户'
        WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN '重要发展客户'
        WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN '重要挽留客户'
        WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN '一般价值客户'
        WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN '一般保持客户'
        WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN '一般发展客户'
        ELSE '一般挽留客户'
    END;
$$;
