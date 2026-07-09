-- L4.74 Citus resource governance baseline.
-- PostgreSQL/Citus does not provide Trino-style resource groups, so the POC
-- maps query classes to roles with connection, timeout, memory, and temp-file
-- limits. PgBouncer can route application users into these roles later.

CREATE SCHEMA IF NOT EXISTS crm_admin;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'crm_interactive') THEN
        CREATE ROLE crm_interactive;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'crm_batch') THEN
        CREATE ROLE crm_batch;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'crm_shadow_read') THEN
        CREATE ROLE crm_shadow_read;
    END IF;
END;
$$;

ALTER ROLE crm_interactive CONNECTION LIMIT 20;
ALTER ROLE crm_interactive SET statement_timeout = '8s';
ALTER ROLE crm_interactive SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE crm_interactive SET work_mem = '64MB';
ALTER ROLE crm_interactive SET temp_file_limit = '4GB';

ALTER ROLE crm_shadow_read CONNECTION LIMIT 10;
ALTER ROLE crm_shadow_read SET statement_timeout = '15s';
ALTER ROLE crm_shadow_read SET idle_in_transaction_session_timeout = '45s';
ALTER ROLE crm_shadow_read SET work_mem = '64MB';
ALTER ROLE crm_shadow_read SET temp_file_limit = '6GB';

ALTER ROLE crm_batch CONNECTION LIMIT 4;
ALTER ROLE crm_batch SET statement_timeout = '30min';
ALTER ROLE crm_batch SET idle_in_transaction_session_timeout = '5min';
ALTER ROLE crm_batch SET work_mem = '256MB';
ALTER ROLE crm_batch SET temp_file_limit = '32GB';

CREATE OR REPLACE VIEW crm_admin.resource_governance AS
SELECT
    r.rolname AS role_name,
    s.setconfig AS role_settings
FROM pg_roles r
LEFT JOIN pg_db_role_setting s ON s.setrole = r.oid
WHERE r.rolname IN ('crm_interactive', 'crm_shadow_read', 'crm_batch')
ORDER BY r.rolname;
