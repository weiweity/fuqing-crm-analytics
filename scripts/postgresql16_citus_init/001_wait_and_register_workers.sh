#!/usr/bin/env bash
set -euo pipefail

workers_csv="${FQ_CITUS_WORKERS:-citus-worker-1,citus-worker-2,citus-worker-3}"
IFS=',' read -r -a workers <<< "${workers_csv}"

for worker in "${workers[@]}"; do
  echo "[L4.74] waiting for Citus worker ${worker}:5432"
  for _ in $(seq 1 60); do
    if pg_isready -h "${worker}" -p 5432 -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  pg_isready -h "${worker}" -p 5432 -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"
done

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<'SQL'
CREATE EXTENSION IF NOT EXISTS citus;
CREATE SCHEMA IF NOT EXISTS crm_admin;
SQL

for worker in "${workers[@]}"; do
  psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" \
    -v worker_host="${worker}" <<'SQL'
SELECT citus_add_node(:'worker_host', 5432)
WHERE NOT EXISTS (
    SELECT 1
    FROM pg_dist_node
    WHERE nodename = :'worker_host'
      AND nodeport = 5432
);
SQL
done

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<'SQL'
CREATE OR REPLACE FUNCTION crm_admin.distribute_if_exists(
    table_name regclass,
    distribution_column text
)
RETURNS text
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_dist_partition
        WHERE logicalrelid = table_name
    ) THEN
        RETURN format('%s already distributed', table_name);
    END IF;

    PERFORM create_distributed_table(table_name::text, distribution_column);
    RETURN format('%s distributed by %s', table_name, distribution_column);
END;
$$;
SQL
