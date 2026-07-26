#!/usr/bin/env python3
"""Sprint 203 R2 Finding 4.1 + R4+ b/c 件真接入: ClickHouse POC 启动条件监控 (L4.58 + L4.59 永久规则化)

- 每周日 04:45 launchd 触发 (跟 R6 04:00 / R7 04:15 / R8 04:30 错开)
- 监控 a/b/c 3 件启动条件:
  - (a) DuckDB file size > 200GB (R2 接入, 走本地 Path stat)
  - (b) query P95 > 30s 持续 1 周 (R4 真接入 /metrics endpoint)
  - (c) 5+ 业务分析师并发取数 (R4 真接入 /api/v1/health/pool semaphore_in_use)
- 0 触发 → print CLICKHOUSE_POC_MONITOR_PASS
- 任意触发 → exit 0 (fail-open) + write TECH-DEBT.md 跨 sprint 留尾告警
- 普通采集异常 → exit 0 (跟 L4.40 post-merge hook 1:1 stable)
- 管理员凭据缺失/被拒绝 → exit 2 (fail-closed，禁止把 b/c 盲区误报为 PASS)

Sprint 203 R4+ 注: Sprint 203 R4 已真接入 b/c 件 (Phase 1 闭环), Sprint 203 R5+ 持续演进 (Phase 2 跨 sprint 维护性, 跟 L4.59 1:1 stable).

L4.61 跨 CI runner 适配:
- Linux CI runner 跑: 没 production DuckDB + 没 macOS path → 视作 0 触发 → PASS
- main() 加 sys.platform != "darwin" 平台守卫

L4.60 跨平台: REPO_ROOT = Path(__file__).resolve().parents[2] (scripts/ops/ → repo root

Sprint 203 R4 b/c 件真接入设计 (跟 L4.59 跨 sprint 维护性 SOP 1:1 stable):
- b 件: 管理员 Bearer GET ${BACKEND_URL}/api/v1/health/metrics → parse fq_query_duration_seconds_bucket → 推 P95 → > 30s 触发
- c 件: 管理员 Bearer GET ${BACKEND_URL}/api/v1/health/pool → parse semaphore_in_use → > 5 触发
- 普通网络异常 / 超时 → 视作 0 触发 (fail-open, 跟 L4.40 1:1 stable)
- 凭据缺失、登录失败、401/403 → 明确 AUTH_FAILURE + exit 2；密码/token 永不写日志
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[2]  # L4.60: scripts/ops/ → repo root
DUCKDB_PATH = Path(os.environ.get("DUCKDB_PATH", str(REPO_ROOT / "data" / "processed" / "fuqing_crm.duckdb")))
LOG_FILE = Path.home() / "Library" / "Logs" / "fuqing-clickhouse-poc-monitor.log"
TECH_DEBT = REPO_ROOT / "docs" / "TECH-DEBT.md"

# Sprint 203 R4: b/c 件真接入 backend HTTP endpoint
BACKEND_URL = os.environ.get("FQ_BACKEND_URL", "http://127.0.0.1:8000")
HTTP_TIMEOUT_S = float(os.environ.get("FQ_POC_MONITOR_TIMEOUT_S", "3"))

# ClickHouse POC 启动条件阈值 (跟 docs/architecture/clickhouse-poc-decision-memo.md §1.3 1:1 stable)
DUCKDB_SIZE_TRIGGER_GB = 200
QUERY_P95_TRIGGER_S = 30
CONCURRENT_USER_TRIGGER = 5


class MonitorAuthError(RuntimeError):
    """管理员鉴权缺失或被 endpoint 拒绝；错误文本不得包含密码/token。"""


def _duckdb_size_gb() -> float | None:
    """DuckDB file size in GB; None if file not found."""
    try:
        if not DUCKDB_PATH.exists():
            return None
        return DUCKDB_PATH.stat().st_size / (1024 ** 3)
    except Exception as e:
        print(f"[CLICKHOUSE_POC_MONITOR] DuckDB size check exception: {e}", file=sys.stderr)
        return None


def _check_trigger_a(size_gb: float | None) -> str | None:
    """(a) DuckDB > 200GB → return alert msg."""
    if size_gb is None:
        return None
    if size_gb > DUCKDB_SIZE_TRIGGER_GB:
        return f"(a) DuckDB size {size_gb:.1f}GB > {DUCKDB_SIZE_TRIGGER_GB}GB threshold"
    return None


# --- 管理员凭据解析 + Bearer 登录 ---


def _runtime_config() -> dict[str, str]:
    """读取 repo ``.env`` 后用进程环境覆盖；不打印任何配置值。

    launchd 不继承交互 shell 环境，因此需要显式读取与 backend 相同的 ``.env``。
    """
    config: dict[str, str] = {}
    env_path = REPO_ROOT / ".env"
    try:
        if env_path.is_file():
            config.update(
                {
                    key: value
                    for key, value in dotenv_values(env_path).items()
                    if isinstance(value, str)
                }
            )
    except (OSError, ValueError) as exc:
        print(
            f"[CLICKHOUSE_POC_MONITOR] .env read failed: {type(exc).__name__}",
            file=sys.stderr,
        )
    config.update(os.environ)
    return config


def _parse_credentials(raw: str) -> dict[str, str]:
    """跟 backend auth 的 ``user:password,user2:password2`` 格式保持一致。"""
    credentials: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" not in pair:
            continue
        username, password = pair.split(":", 1)
        if username.strip() and password.strip():
            credentials[username.strip()] = password.strip()
    return credentials


def _select_monitor_admin_credentials() -> tuple[str, str] | None:
    """选择明确的管理员凭据，歧义或配置错误一律 fail-closed。

    必须给监控配置专用账号，并同时加入 ``FQ_CRM_ADMINS`` 和
    ``FQ_CRM_PASSWORDS``；通过 ``FQ_POC_MONITOR_ADMIN_USERNAME`` 显式指定。
    ``FQ_POC_MONITOR_ADMIN_PASSWORD`` 可覆盖登录明文（例如 backend 配的是
    bcrypt hash，监控端另由 launchd 环境注入明文）。
    """
    config = _runtime_config()
    admins = [
        item.strip()
        for item in config.get("FQ_CRM_ADMINS", "").split(",")
        if item.strip()
    ]
    credentials = _parse_credentials(config.get("FQ_CRM_PASSWORDS", ""))
    selected_username = config.get("FQ_POC_MONITOR_ADMIN_USERNAME", "").strip()
    selected_password = config.get("FQ_POC_MONITOR_ADMIN_PASSWORD", "").strip()
    dedicated_account = config.get(
        "FQ_POC_MONITOR_DEDICATED_ACCOUNT", ""
    ).strip()

    if not selected_username:
        print(
            "[CLICKHOUSE_POC_MONITOR] AUTH_CONFIG_ERROR: "
            "FQ_POC_MONITOR_ADMIN_USERNAME is required for a dedicated monitor "
            "account",
            file=sys.stderr,
        )
        return None

    if dedicated_account != selected_username:
        print(
            "[CLICKHOUSE_POC_MONITOR] AUTH_CONFIG_ERROR: set "
            "FQ_POC_MONITOR_DEDICATED_ACCOUNT to the same username only after "
            "confirming this account is not used by a person",
            file=sys.stderr,
        )
        return None

    if selected_username not in admins:
        print(
            "[CLICKHOUSE_POC_MONITOR] AUTH_CONFIG_ERROR: dedicated monitor user "
            "is not listed in FQ_CRM_ADMINS",
            file=sys.stderr,
        )
        return None
    configured_password = credentials.get(selected_username)
    if configured_password is None:
        print(
            "[CLICKHOUSE_POC_MONITOR] AUTH_CONFIG_ERROR: dedicated monitor user "
            "is missing from FQ_CRM_PASSWORDS",
            file=sys.stderr,
        )
        return None
    if selected_password:
        if not configured_password.startswith(("$2a$", "$2b$", "$2y$")):
            if selected_password != configured_password:
                print(
                    "[CLICKHOUSE_POC_MONITOR] AUTH_CONFIG_ERROR: dedicated "
                    "monitor password does not match FQ_CRM_PASSWORDS",
                    file=sys.stderr,
                )
                return None
        return selected_username, selected_password
    if configured_password.startswith(("$2a$", "$2b$", "$2y$")):
        print(
            "[CLICKHOUSE_POC_MONITOR] AUTH_CONFIG_ERROR: bcrypt credential requires "
            "FQ_POC_MONITOR_ADMIN_PASSWORD for monitor login",
            file=sys.stderr,
        )
        return None
    return selected_username, configured_password


# --- Sprint 203 R4 b/c 件真接入: HTTP fetch + Prometheus parse + pool semaphore parse ---


def _fetch_url_text(
    url: str,
    *,
    authorization: str | None = None,
    method: str = "GET",
    body: bytes | None = None,
    require_admin: bool = False,
) -> str | None:
    """urllib request；普通网络错误 fail-open，管理员拒绝 fail-closed。"""
    if require_admin and not authorization:
        raise MonitorAuthError("admin authorization is required")
    headers = {"Accept": "application/json, text/plain"}
    if authorization:
        headers["Authorization"] = authorization
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if require_admin and e.code in (401, 403):
            raise MonitorAuthError(f"admin endpoint rejected bearer ({e.code})") from e
        print(f"[CLICKHOUSE_POC_MONITOR] HTTP fetch {url} exception: HTTPError: {e.code}", file=sys.stderr)
        return None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"[CLICKHOUSE_POC_MONITOR] HTTP fetch {url} exception: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def _fetch_url_json(
    url: str,
    *,
    authorization: str | None = None,
    require_admin: bool = False,
) -> dict | None:
    """urllib GET + json parse, fail-open."""
    text = _fetch_url_text(
        url,
        authorization=authorization,
        require_admin=require_admin,
    )
    if text is None:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[CLICKHOUSE_POC_MONITOR] JSON parse {url} exception: {e}", file=sys.stderr)
        return None


def _get_monitor_authorization() -> str | None:
    """登录专用管理员并返回 Bearer header；密码/token 不进入 URL 或日志。"""
    selected = _select_monitor_admin_credentials()
    if selected is None:
        return None
    username, password = selected
    body = json.dumps(
        {"username": username, "password": password},
        separators=(",", ":"),
    ).encode("utf-8")
    text = _fetch_url_text(
        f"{BACKEND_URL}/api/v1/auth/login",
        method="POST",
        body=body,
    )
    if text is None:
        print(
            "[CLICKHOUSE_POC_MONITOR] AUTH_LOGIN_FAILED: admin login request failed; "
            "use a dedicated monitor account",
            file=sys.stderr,
        )
        return None
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        print(
            "[CLICKHOUSE_POC_MONITOR] AUTH_LOGIN_FAILED: login returned invalid JSON",
            file=sys.stderr,
        )
        return None
    token = payload.get("token")
    if not isinstance(token, str) or not token or payload.get("is_admin") is not True:
        print(
            "[CLICKHOUSE_POC_MONITOR] AUTH_LOGIN_FAILED: login did not return an "
            "admin token",
            file=sys.stderr,
        )
        return None
    return f"Bearer {token}"


def _logout_monitor_token(authorization: str) -> None:
    """尽力注销临时 token；清理失败不覆盖主要监控结果。"""
    _fetch_url_text(
        f"{BACKEND_URL}/api/v1/auth/logout",
        authorization=authorization,
        method="POST",
    )


def _parse_query_p95(authorization: str) -> float | None:
    """Parse admin health metrics → 推 global P95 latency (秒).

    Strategy: per-series P95 (per endpoint × query_type) → 取 MAX 跨 series.

    Prometheus histogram bucket 是 per-series cumulative (即每个 endpoint/query_type
    一组独立的 cumulative bucket). 简单跨 series 加总会歪曲 P95 (e.g. 一个 fast endpoint
    1M query + 一个 slow endpoint 10 query, 加总会让 slow endpoint P95 被淹没).
    正确做法: per-series P95 → MAX (worst-case latency as trigger condition).

    Returns P95 in seconds (MAX across all series), None if no data or parse fail.

    L4.40 fail-open: None on any exception.
    """
    text = _fetch_url_text(
        f"{BACKEND_URL}/api/v1/health/metrics",
        authorization=authorization,
        require_admin=True,
    )
    if text is None:
        return None
    try:
        # 匹配: fq_query_duration_seconds_bucket{endpoint="X",query_type="Y",le="Z"} N
        bucket_re = re.compile(
            r'^fq_query_duration_seconds_bucket\{([^}]*)\}\s+(\d+(?:\.\d+)?)',
            re.MULTILINE,
        )
        # 匹配: fq_query_duration_seconds_count{endpoint="X",query_type="Y"} N
        count_re = re.compile(
            r'^fq_query_duration_seconds_count\{([^}]*)\}\s+(\d+(?:\.\d+)?)',
            re.MULTILINE,
        )

        # group by series (endpoint + query_type, 不含 le)
        def series_key(labels_str: str) -> tuple[str, str]:
            ep_match = re.search(r'endpoint="([^"]+)"', labels_str)
            qt_match = re.search(r'query_type="([^"]+)"', labels_str)
            return (ep_match.group(1) if ep_match else "", qt_match.group(1) if qt_match else "")

        series_totals: dict[tuple[str, str], float] = {}
        for m in count_re.finditer(text):
            key = series_key(m.group(1))
            series_totals[key] = series_totals.get(key, 0.0) + float(m.group(2))

        if not series_totals:
            return None

        # 每 series 单独算 P95
        series_buckets: dict[tuple[str, str], dict[float, float]] = {}
        for m in bucket_re.finditer(text):
            labels_str = m.group(1)
            le_str_match = re.search(r'le="([^"]+)"', labels_str)
            if le_str_match is None:
                continue
            le_str = le_str_match.group(1)
            if le_str in ("+Inf", "Inf"):
                continue
            try:
                le = float(le_str)
            except ValueError:
                continue
            key = series_key(labels_str)
            if key not in series_buckets:
                series_buckets[key] = {}
            series_buckets[key][le] = series_buckets[key].get(le, 0.0) + float(m.group(2))

        # 每 series 找 P95
        series_p95s: list[float] = []
        for key, total in series_totals.items():
            if total <= 0:
                continue
            buckets = series_buckets.get(key, {})
            threshold = 0.95 * total
            for le in sorted(buckets.keys()):
                if buckets[le] >= threshold:
                    series_p95s.append(le)
                    break

        if not series_p95s:
            return None
        # MAX 跨 series (worst-case latency as ClickHouse POC trigger)
        return max(series_p95s)
    except Exception as e:
        print(f"[CLICKHOUSE_POC_MONITOR] P95 parse exception: {e}", file=sys.stderr)
        return None


def _get_pool_in_use(authorization: str) -> int | None:
    """GET /api/v1/health/pool → semaphore_in_use count, None on fail-open."""
    data = _fetch_url_json(
        f"{BACKEND_URL}/api/v1/health/pool",
        authorization=authorization,
        require_admin=True,
    )
    if data is None:
        return None
    try:
        return int(data.get("semaphore_in_use", 0))
    except (TypeError, ValueError) as e:
        print(f"[CLICKHOUSE_POC_MONITOR] pool parse exception: {e}", file=sys.stderr)
        return None


def _check_trigger_b(authorization: str) -> str | None:
    """(b) query P95 > 30s 持续 1 周 → return alert msg.

    Sprint 203 R4 真接入 admin metrics endpoint: 解析 Prometheus text format, 累计所有
    endpoint × query_type 维度的 histogram bucket, 推全局 P95 latency.
    > 30s 触发. None 表示 0 触发 (含 fail-open + 数据不够).
    """
    p95 = _parse_query_p95(authorization)
    if p95 is None:
        return None
    if p95 > QUERY_P95_TRIGGER_S:
        return f"(b) Query P95 {p95:.1f}s > {QUERY_P95_TRIGGER_S}s threshold"
    return None


def _check_trigger_c(authorization: str) -> str | None:
    """(c) 5+ 业务分析师并发取数 → return alert msg.

    Sprint 203 R4 真接入 /api/v1/health/pool: 读 semaphore_in_use count,
    > 5 触发 (跟 READ_POOL_SIZE * 2 / 2 = 5 阈值一致).
    """
    in_use = _get_pool_in_use(authorization)
    if in_use is None:
        return None
    if in_use > CONCURRENT_USER_TRIGGER:
        return f"(c) Read pool in use {in_use} > {CONCURRENT_USER_TRIGGER} concurrent users threshold"
    return None


def append_tech_debt(msgs: list[str]) -> None:
    """跨 sprint 留尾告警 (跟 L4.12 SSOT 配套)."""
    try:
        if not TECH_DEBT.exists():
            TECH_DEBT.write_text("# Tech Debt (Sprint 67+ L4.12 SSOT)\n\n")
        with TECH_DEBT.open("a") as f:
            f.write("\n## ClickHouse POC 启动条件触发告警 (Sprint 203 R2/R4)\n\n")
            for msg in msgs:
                f.write(f"- {msg}\n")
            f.write("\n")
    except Exception as e:
        print(f"[CLICKHOUSE_POC_MONITOR] TECH_DEBT write failed: {e}", file=sys.stderr)


def _record_trigger_alerts(alerts: list[str], size_gb: float | None) -> None:
    """持久化已经独立判定的触发项；后续鉴权失败也不能吞掉它们。"""
    msg = (
        f"[CLICKHOUSE_POC_MONITOR] TRIGGER HIT: {'; '.join(alerts)} "
        f"(DuckDB size {size_gb or 'N/A'}GB)"
    )
    print(msg)
    try:
        with LOG_FILE.open("a") as f:
            f.write(f"{msg}\n")
    except Exception:
        pass
    append_tech_debt(
        alerts
        + [
            f"DuckDB file size: {size_gb:.1f}GB"
            if size_gb
            else "DuckDB file size: N/A"
        ]
    )


def main() -> int:
    # L4.61 跨 CI runner 适配: Linux runner 视作 0 触发 → PASS
    if sys.platform != "darwin":
        msg = (
            f"CLICKHOUSE_POC_MONITOR_PASS (Linux/CI runner, "
            f"size={_duckdb_size_gb() or 'N/A'}GB, "
            f"triggers: a/b/c 0 命中 — 跨 CI runner 适配, R4 b/c 件真接入 HTTP fetch 跳过)"
        )
        print(msg)
        try:
            with LOG_FILE.open("a") as f:
                f.write(f"{msg}\n")
        except Exception:
            pass
        return 0

    size_gb: float | None = None
    alerts: list[str] = []
    try:
        size_gb = _duckdb_size_gb()

        a = _check_trigger_a(size_gb)
        if a:
            alerts.append(a)
        authorization = _get_monitor_authorization()
        if authorization is None:
            if alerts:
                _record_trigger_alerts(alerts, size_gb)
            warn = (
                "[CLICKHOUSE_POC_MONITOR] AUTH_FAILURE: b/c checks were not "
                "executed; configure a dedicated admin monitor account"
            )
            print(warn, file=sys.stderr)
            try:
                with LOG_FILE.open("a") as f:
                    f.write(f"{warn}\n")
            except Exception:
                pass
            return 2
        try:
            b = _check_trigger_b(authorization)
            if b:
                alerts.append(b)
            c = _check_trigger_c(authorization)
            if c:
                alerts.append(c)
        finally:
            _logout_monitor_token(authorization)

        if alerts:
            _record_trigger_alerts(alerts, size_gb)
            # fail-open: 监控不阻 commit, 只告警
            return 0

        msg = (
            f"CLICKHOUSE_POC_MONITOR_PASS (DuckDB {size_gb or 'N/A'}GB, "
            f"triggers: a/b/c 0 命中 — Sprint 203 R4 b/c 件真接入 HTTP fetch cross-sprint stable)"
        )
        print(msg)
        with LOG_FILE.open("a") as f:
            f.write(f"{msg}\n")
        return 0

    except MonitorAuthError as e:
        if alerts:
            _record_trigger_alerts(alerts, size_gb)
        warn = (
            "[CLICKHOUSE_POC_MONITOR] AUTH_FAILURE: "
            f"{e}; b/c checks were not completed"
        )
        print(warn, file=sys.stderr)
        try:
            with LOG_FILE.open("a") as f:
                f.write(f"{warn}\n")
        except Exception:
            pass
        return 2
    except Exception as e:
        if alerts:
            _record_trigger_alerts(alerts, size_gb)
        # fail-open: 异常不阻 commit (跟 L4.40 post-merge hook 1:1 stable)
        # 不输出异常正文，避免畸形 URL/配置值意外进入日志。
        warn = f"[CLICKHOUSE_POC_MONITOR] EXCEPTION (fail-open): {type(e).__name__}"
        print(warn, file=sys.stderr)
        try:
            with LOG_FILE.open("a") as f:
                f.write(f"{warn}\n")
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())
