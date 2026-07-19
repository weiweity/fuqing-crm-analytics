# scripts/ops — 跨 sprint 运维监控

Monitor scripts invoked by launchd (see `scripts/launchd/*.plist`).

| Script | Plist / purpose |
|---|---|
| `pre_existing_fail_monitor.py` | weekly pre-existing fail |
| `memory_size_monitor.py` | MEMORY.md size |
| `adhoc_query_hitrate_monitor.py` | ad-hoc tool count + symlink |
| `clickhouse_poc_monitor.py` | ClickHouse POC start conditions |
| `check_db_size.py` | DuckDB size alert |

**REPO_ROOT** = `Path(__file__).resolve().parents[2]` (file under `scripts/ops/`).
